# app/services/user.py
from sqlalchemy.orm import Session
from app.crud import user as crud_user
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
from app.models.models import User

class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_phone(self, phone: str) -> User | None:
        return crud_user.get_by_phone(self.db, phone=phone)

    def get_user_by_email(self, email: str) -> User | None:
        return crud_user.get_by_email(self.db, email=email)

    def create_user(self, phone: str, email: str = None, full_name: str = None, password: str = None) -> User:
        user_in = UserCreate(
            phone=phone,
            email=email,
            full_name=full_name,
            password_hash=get_password_hash(password) if password else None
        )
        return crud_user.create(self.db, obj_in=user_in)

    def authenticate(self, phone: str, password: str) -> User | None:
        user = self.get_user_by_phone(phone)
        if not user or not user.password_hash:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def update_user(self, user: User, update_data: UserUpdate) -> User:
        return crud_user.update(self.db, db_obj=user, obj_in=update_data)