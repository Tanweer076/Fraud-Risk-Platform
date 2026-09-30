from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DB, AppSettings, CurrentUser
from app.schemas.auth import Token, UserOut
from app.services import users

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB, settings: AppSettings):
    """OAuth2 password flow: `username` is the user's email."""
    try:
        return users.authenticate(db, settings, form.username, form.password)
    except users.InvalidCredentials as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
