from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.rules import load_rules

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request):
    """Readiness: the database answers, a model is loaded and the business rules are read.

    A model activated or rules put in place after startup are picked up here, so a stack
    seeded while running becomes ready without a restart.
    """
    state = request.app.state
    checks = {"database": False, "model": None, "rules": False}
    try:
        with state.sessionmaker() as db:
            db.execute(text("SELECT 1"))
            checks["database"] = True
            checks["model"] = state.registry.current(db).version
    except Exception:  # any failure means not ready
        pass
    if state.rules is None:
        state.rules = load_rules(state.settings)
    checks["rules"] = state.rules is not None
    ok = checks["database"] and checks["model"] is not None and checks["rules"]
    return JSONResponse(
        {"status": "ready" if ok else "not ready", **checks}, status_code=200 if ok else 503
    )
