from fastapi import APIRouter, status

from app.api.deps import DB, Admin, AppSettings
from app.schemas.auth import UserCreate, UserOut, UserUpdate
from app.services import users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: DB, _: Admin):
    return users.list_users(db)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: DB, settings: AppSettings, admin: Admin):
    return users.create_user(db, settings, data, admin)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: DB, settings: AppSettings, admin: Admin):
    return users.update_user(db, settings, user_id, data, admin)
