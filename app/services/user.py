from sqlalchemy.orm import Session
from app.config.config import settings
from app.crud.user import crud_user
from app.models.models import User,VerificationType
from app.schemas import  LoginApiResponse,PhoneRequest
from app.core.security import get_password_hash, verify_password,create_access_token
from app.services.channel import ChannelService
# from app.services.verification import VerificationService


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.channel_service=ChannelService(self.db)
        # self.verification_service = VerificationService(db)

    def get_user_by_phone(self, phone: str) -> User | None:
        return crud_user.get_by_phone(self.db, phone=phone)

    def get_user_by_email(self, email: str) -> User | None:
        return crud_user.get_by_email(self.db, email=email)

    def create_user(self, phone: str, email: str = None, full_name: str = None, password: str = None) -> User:
        password_hash = get_password_hash(password) if password else None
        return crud_user.create_with_phone(
            self.db,
            phone=phone,
            email=email,
            full_name=full_name,
            password_hash=password_hash
        )

    def authenticate(self, phone: str, password: str) -> User | None:
        user = self.get_user_by_phone(phone)
        if not user or not user.password_hash:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
    
    def find_and_create_user(self,phone):
        user=self.get_user_by_phone(phone)
        if not user: 
            user=crud_user.create_with_phone(self.db,phone=phone)
        return user
    
    def create_token(self,phone,user=None):
        if not user:
            user = self.find_and_create_user(phone)
        # Создаём токен
        token = create_access_token({"sub": user.phone})
        return token
    
    