from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.security import create_access_token, dummy_hash, hash_password, verify_password
from app.models import User
from app.schemas.auth import Token, UserCreate, UserOut, UserUpdate
from app.services import audit


class InvalidCredentials(Exception):
    pass


def authenticate(db: Session, settings: Settings, email: str, password: str) -> Token:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        verify_password(password, dummy_hash(settings.bcrypt_rounds))
        raise InvalidCredentials
    if not verify_password(password, user.password_hash):
        raise InvalidCredentials
    if not user.is_active:
        raise Forbidden("This user is deactivated")
    token = create_access_token(
        user.id, user.role, settings.jwt_secret.get_secret_value(), settings.jwt_expire_minutes
    )
    return Token(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


def create_user(db: Session, settings: Settings, data: UserCreate, actor: User | None) -> User:
    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        password_hash=hash_password(data.password, settings.bcrypt_rounds),
        role=data.role,
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(f"A user with email {data.email} already exists") from exc
    audit.record(db, actor, "user.create", "user", user.id, after=_public(user))
    db.commit()
    return user


def update_user(
    db: Session, settings: Settings, user_id: int, data: UserUpdate, actor: User
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound(f"User {user_id} not found")
    before = _public(user)
    changes = data.model_dump(exclude_unset=True, exclude={"password"})
    if user.id == actor.id and (
        changes.get("is_active") is False or changes.get("role", "admin") != "admin"
    ):
        raise Conflict("Admins cannot deactivate or demote themselves")
    for key, value in changes.items():
        if value is not None:
            setattr(user, key, value)
    if data.password:
        user.password_hash = hash_password(data.password, settings.bcrypt_rounds)
    after = _public(user) | ({"password": "changed"} if data.password else {})
    audit.record(db, actor, "user.update", "user", user.id, before=before, after=after)
    db.commit()
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


def _public(user: User) -> dict:
    return UserOut.model_validate(user).model_dump(exclude={"created_at"})
