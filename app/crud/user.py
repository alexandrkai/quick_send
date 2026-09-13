from typing import Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.models import User, UserRole
from app.schemas import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_phone(self, db: Session, *, phone: str) -> Optional[User]:
        return db.query(User).filter(User.phone == phone).first()

    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    def create_with_phone(
        self,
        db: Session,
        *,
        phone: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        password_hash: Optional[str] = None,
        role: UserRole = UserRole.USER,
        flush_only: bool = True
    ) -> User:
        user_in = UserCreate(
            phone=phone,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            role=role,
            is_active=True
        )
        if flush_only:
            # Создание в рамках внешней транзакции сервиса
            db_obj = User(**user_in.model_dump())
            db.add(db_obj)
            db.flush()
            db.refresh(db_obj)
            return db_obj
        return self.create(db, obj_in=user_in)


crud_user = CRUDUser(User)