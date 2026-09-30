"""Password hashing (bcrypt) and access tokens (JWT, HS256)."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import bcrypt
import jwt

ALGORITHM = "HS256"
BCRYPT_MAX_BYTES = 72  # bcrypt ignores (bcrypt>=5 rejects) anything longer

ROLES = ("analyst", "approver", "admin")


def hash_password(password: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode()
    if len(encoded) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, password_hash.encode())
    except ValueError:  # malformed stored hash
        return False


@lru_cache
def dummy_hash(rounds: int) -> str:
    """Checked when the email is unknown, so a login takes as long whether or not it exists."""
    return hash_password("not-a-real-password", rounds)


def create_access_token(user_id: int, role: str, secret: str, expire_minutes: int) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict:
    """Return the token's claims; raises jwt.PyJWTError when it is invalid or expired."""
    return jwt.decode(token, secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
