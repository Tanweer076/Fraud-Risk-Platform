from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from fraudml.ingest.rules import Rule
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import Forbidden, Unavailable
from app.core.ratelimit import RateLimiter
from app.core.rules import load_rules
from app.core.security import decode_access_token
from app.db.session import get_db
from app.ml.registry import ModelRegistry
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_registry(request: Request) -> ModelRegistry:
    return request.app.state.registry


def get_rules(request: Request) -> list[Rule]:
    state = request.app.state
    if state.rules is None:  # not there at startup; it may have been put in place since
        state.rules = load_rules(state.settings)
    if state.rules is None:
        raise Unavailable("Business rules are not loaded; check RULES_PATH")
    return state.rules


def get_limiter(request: Request) -> RateLimiter:
    return request.app.state.limiter


def client_ip(request: Request) -> str:
    """The caller's address; behind the proxy, uvicorn takes it from X-Forwarded-For."""
    return request.client.host if request.client else "unknown"


AppSettings = Annotated[Settings, Depends(get_settings)]
Registry = Annotated[ModelRegistry, Depends(get_registry)]
Rules = Annotated[list[Rule], Depends(get_rules)]
Limiter = Annotated[RateLimiter, Depends(get_limiter)]

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CSRF_HEADER = "X-Requested-With"


def require_csrf_header(request: Request) -> None:
    """Browsers send the session cookie on their own, even for a form posted from another site.
    Such a form cannot add a custom header (CORS would have to allow it), so a request that
    changes something with the cookie must carry X-Requested-With."""
    if not request.headers.get(CSRF_HEADER):
        raise Forbidden(f"Requests signed in with the session cookie need an {CSRF_HEADER} header")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


def get_token(
    request: Request, settings: AppSettings, bearer: Annotated[str | None, Depends(oauth2_scheme)]
) -> str | None:
    """The access token: a Bearer header (API clients) or the session cookie (the dashboard)."""
    if bearer:
        return bearer
    cookie = request.cookies.get(settings.session_cookie_name)
    if cookie and request.method not in SAFE_METHODS:
        require_csrf_header(request)
    return cookie or None


def get_claims(settings: AppSettings, token: Annotated[str | None, Depends(get_token)]) -> dict:
    if not token:
        raise _unauthorized("Not authenticated")
    try:
        claims = decode_access_token(token, settings.jwt_secret.get_secret_value())
        int(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise _unauthorized("Invalid or expired token") from exc
    return claims


Claims = Annotated[dict, Depends(get_claims)]


def get_current_user(db: DB, claims: Claims) -> User:
    user = db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise _unauthorized("User not found or deactivated")
    return user


def require_role(*roles: str):
    def check(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"Requires the {' or '.join(roles)} role"
            )
        return user

    return check


CurrentUser = Annotated[User, Depends(get_current_user)]
Maker = Annotated[User, Depends(require_role("analyst", "admin"))]
Checker = Annotated[User, Depends(require_role("approver", "admin"))]
Admin = Annotated[User, Depends(require_role("admin"))]
AuditReader = Annotated[User, Depends(require_role("approver", "admin"))]
