# app/api/v1/users.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.models.models import User,get_db
from app.schemas.user import UserUpdate
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Получить информацию о текущем пользователе."""
    return current_user

@router.put("/me")
def update_me(
    update_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновить профиль пользователя."""
    user_service = UserService(db)
    updated = user_service.update_user(current_user, update_data)
    return updated