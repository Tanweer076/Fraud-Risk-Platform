from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request):
    """Readiness: the database answers, a model is loaded and the business rules are read."""
    state = request.app.state
    checks = {"database": False, "model": state.registry.loaded_version, "rules": False}
    try:
        with state.sessionmaker() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:  # any failure means not ready
        pass
    checks["rules"] = getattr(state, "rules", None) is not None
    ok = checks["database"] and checks["model"] is not None and checks["rules"]
    return JSONResponse(
        {"status": "ready" if ok else "not ready", **checks}, status_code=200 if ok else 503
    )
