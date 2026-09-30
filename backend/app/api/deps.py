from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from fraudml.ingest.rules import Rule
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import Unavailable
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
    rules = getattr(request.app.state, "rules", None)
    if rules is None:
        raise Unavailable("Business rules are not loaded; check RULES_PATH")
    return rules


AppSettings = Annotated[Settings, Depends(get_settings)]
Registry = Annotated[ModelRegistry, Depends(get_registry)]
Rules = Annotated[list[Rule], Depends(get_rules)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(
    db: DB, settings: AppSettings, token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User:
    if not token:
        raise _unauthorized("Not authenticated")
    try:
        claims = decode_access_token(token, settings.jwt_secret.get_secret_value())
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise _unauthorized("Invalid or expired token") from exc
    user = db.get(User, user_id)
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
