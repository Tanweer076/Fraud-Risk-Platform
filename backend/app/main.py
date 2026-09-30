"""FastAPI application factory."""

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fraudml.errors import IngestionError
from fraudml.ingest.rules import parse_rules

from app import __version__
from app.api.v1 import api_router
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, request_id_var
from app.db.session import make_engine, make_sessionmaker
from app.ml.registry import ModelRegistry

log = logging.getLogger("app")
REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def load_rules(settings: Settings):
    try:
        rules = parse_rules(settings.rules_path)
    except IngestionError as exc:
        log.error("Business rules not loaded: %s", exc)
        return None
    log.info("Loaded %d business rules from %s", len(rules), settings.rules_path)
    return rules


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
        response.headers["X-Request-ID"] = request_id
        log.info(
            "%s %s %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "extra_fields": {
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            },
        )
        request_id_var.reset(token)
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    app.include_router(api_router, prefix="/api/v1")
    return app
