# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import timedelta

from app.core.database import get_db
from app.services.user import UserService
from app.services.verification import VerificationService
from app.core.security import create_access_token, verify_password, get_password_hash
from app.crud import user as crud_user
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

class PhoneRequest(BaseModel):
    phone: str

class CodeRequest(BaseModel):
    phone: str
    code: str

class PasswordLoginRequest(BaseModel):
    phone: str
    password: str

class RegisterRequest(BaseModel):
    phone: str
    password: str
    full_name: str = None
    email: str = None

@router.post("/request-sms")
def request_sms_code(data: PhoneRequest, db: Session = Depends(get_db)):
    """Запрос кода для входа по СМС."""
    verification_service = VerificationService(db)
    # Генерируем и отправляем код
    code = verification_service.generate_code(phone=data.phone, type="login")
    return {"status": "ok", "data": "Код отправлен"}

@router.post("/verify-sms")
def verify_sms_code(data: CodeRequest, db: Session = Depends(get_db)):
    """Подтверждение СМС-кода и выдача JWT."""
    verification_service = VerificationService(db)
    if not verification_service.verify_code(phone=data.phone, code=data.code):
        raise HTTPException(status_code=400, detail="Неверный или просроченный код")
    # Найти или создать пользователя
    user_service = UserService(db)
    user = user_service.get_user_by_phone(data.phone)
    if not user:
        user = user_service.create_user(phone=data.phone)
    # Создаём токен
    token = create_access_token({"sub": user.phone})
    return {"access_token": token, "token_type": "bearer", "user_id": user.id}

@router.post("/login")
def login_password(data: PasswordLoginRequest, db: Session = Depends(get_db)):
    """Вход по паролю (если есть)."""
    user_service = UserService(db)
    user = user_service.get_user_by_phone(data.phone)
    if not user or not user.password_hash:
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    token = create_access_token({"sub": user.phone})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/register")
def register_user(data: RegisterRequest, db: Session = Depends(get_db)):
    """Регистрация с паролем."""
    user_service = UserService(db)
    existing = user_service.get_user_by_phone(data.phone)
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким телефоном уже существует")
    # Можно добавить проверку, что телефон подтверждён, но пока пропускаем
    user = user_service.create_user(
        phone=data.phone,
        email=data.email,
        full_name=data.full_name,
        password=data.password
    )
    token = create_access_token({"sub": user.phone})
    return {"access_token": token, "token_type": "bearer", "user_id": user.id}