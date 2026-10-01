from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import BCRYPT_MAX_BYTES
from app.schemas.common import ORMModel, Role


def _check_password(value: str | None) -> str | None:
    if value is not None and len(value.encode()) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes")
    return value


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field("", max_length=120)
    password: str = Field(min_length=12)
    role: Role

    _password = field_validator("password")(_check_password)


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=120)
    password: str | None = Field(None, min_length=12)
    role: Role | None = None
    is_active: bool | None = None

    _password = field_validator("password")(_check_password)


class SessionOut(BaseModel):
    user: UserOut
    expires_at: datetime
