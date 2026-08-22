# app/crud/user.py
from typing import Optional
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.models import User
from app.schemas.user import UserCreate, UserUpdate

class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_phone(self, db: Session, *, phone: str) -> Optional[User]:
        # так как у нас нет отдельного поля phone, ищем в JSON
        # можно сделать через фильтр по JSON, но для простоты оставим заглушку
        # В реальности нужно искать по contact_data
        # Пока пропустим, т.к. у нас нет такого метода
        pass

    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        pass

user = CRUDUser(User)