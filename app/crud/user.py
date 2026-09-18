from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
from app.crud.base import CRUDBase
from app.models.models import User, UserRole,Boolean
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


    def block_user(self,db: Session, user: User, reason: str) -> User:
        """Блокировка пользователя с фиксацией времени и причины."""
        user.is_blocked = True
        user.blocked_at = datetime.now()
        user.blocked_reason = reason
        db.commit()
        db.refresh(user)
        return user

    def unblock_user(self,db: Session, user: User) -> User:
        """Разблокировка пользователя и сброс метаданных блокировки."""
        user.is_blocked = False
        user.blocked_at = None
        user.blocked_reason = None
        db.commit()
        db.refresh(user)
        return user
    
    def __is_blocked(user:Optional[User]=None)->Optional[Boolean]:
        if not user: return None
        return user.is_blocked
    
    def is_blocked_phone(self,db:Session,phone)->Optional[Boolean]:
        user=self.get_by_phone(db,phone=phone)
        return self.__is_blocked(user)
    
crud_user = CRUDUser(User)