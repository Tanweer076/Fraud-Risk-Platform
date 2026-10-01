"""FastAPI application factory."""

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app import __version__
from app.api.v1 import api_router
from app.core import metrics
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, request_id_var
from app.core.ratelimit import RateLimiter
from app.core.rules import load_rules
from app.db.session import make_engine, make_sessionmaker
from app.ml.registry import ModelRegistry

log = logging.getLogger("app")
REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.rules = load_rules(settings)
        try:
            with app.state.sessionmaker() as db:
                app.state.registry.sync(db)
        except Exception:  # keep serving; /ready reports what is missing
            log.exception("Could not sync the model registry at startup")
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )
    engine = make_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.registry = ModelRegistry(settings.model_dir)
    app.state.rules = None
    app.state.limiter = RateLimiter(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("Unhandled error on %s %s", request.method, request.url.path)
            response = JSONResponse(
                {"detail": "Internal server error", "request_id": request_id}, status_code=500
            )
        elapsed = time.perf_counter() - started
        response.headers["X-Request-ID"] = request_id
        log.info(
            "%s %s %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "extra_fields": {
                    "status": response.status_code,
                    "duration_ms": round(elapsed * 1000, 1),
                }
            },
        )
        # Label by route template (/transactions/{transaction_id}, within /api/v1), not the raw
        # path, so the number of series stays small; a path that matched no route is "unmatched".
        route = getattr(request.scope.get("route"), "path", "unmatched")
        if route != "/metrics":
            metrics.HTTP_REQUESTS.labels(request.method, route, response.status_code).inc()
            metrics.HTTP_LATENCY.labels(request.method, route).observe(elapsed)
        request_id_var.reset(token)
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return JSONResponse(
            {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
        )

    app.include_router(api_router, prefix="/api/v1")

    if settings.metrics_enabled:
        # Outside /api, so the web proxy does not publish it; Prometheus scrapes the API directly.
        @app.get("/metrics", include_in_schema=False)
        def metrics_page():
            body, content_type = metrics.render()
            return Response(body, media_type=content_type)

    return app
