from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import (
    DB,
    AppSettings,
    Claims,
    CurrentUser,
    Limiter,
    client_ip,
    require_csrf_header,
)
from app.core.config import Settings
from app.core.ratelimit import RateLimiter
from app.core.security import decode_access_token
from app.schemas.auth import SessionOut, Token, UserOut
from app.services import users

router = APIRouter(prefix="/auth", tags=["auth"])

LoginForm = Annotated[OAuth2PasswordRequestForm, Depends()]
# The cookie is only needed by the API, so static files never carry it.
COOKIE_PATH = "/api"


def _expiry(claims: dict) -> datetime:
    return datetime.fromtimestamp(claims["exp"], UTC)


def _sign_in(
    request: Request,
    form: OAuth2PasswordRequestForm,
    db: Session,
    settings: Settings,
    limiter: RateLimiter,
) -> Token:
    limiter.hit("login", client_ip(request))
    limiter.hit("login_account", form.username.strip().lower())
    try:
        return users.authenticate(db, settings, form.username, form.password)
    except users.InvalidCredentials as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/login", response_model=Token)
def login(request: Request, form: LoginForm, db: DB, settings: AppSettings, limiter: Limiter):
    """OAuth2 password flow for API clients: `username` is the user's email. The token comes
    back in the body; send it as `Authorization: Bearer <token>`."""
    return _sign_in(request, form, db, settings, limiter)


@router.post("/session", response_model=SessionOut)
def start_session(
    request: Request,
    response: Response,
    form: LoginForm,
    db: DB,
    settings: AppSettings,
    limiter: Limiter,
):
    """Sign in for the dashboard. The token goes into an HttpOnly cookie that page scripts
    cannot read, instead of the body. Needs the X-Requested-With header."""
    require_csrf_header(request)
    token = _sign_in(request, form, db, settings, limiter)
    response.set_cookie(
        settings.session_cookie_name,
        token.access_token,
        max_age=token.expires_in,
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    claims = decode_access_token(token.access_token, settings.jwt_secret.get_secret_value())
    return SessionOut(user=token.user, expires_at=_expiry(claims))


@router.get("/session", response_model=SessionOut)
def current_session(user: CurrentUser, claims: Claims):
    """Who is signed in, and when the session ends."""
    return SessionOut(user=UserOut.model_validate(user), expires_at=_expiry(claims))


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def end_session(request: Request, settings: AppSettings):
    """Sign out: the browser drops the session cookie. Needs the X-Requested-With header."""
    require_csrf_header(request)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        settings.session_cookie_name,
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return response


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
