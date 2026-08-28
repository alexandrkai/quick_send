# app/core/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.models.models import get_db, User
from app.core.security import get_current_user as security_get_current_user,decode_access_token
from app.services.user import UserService
from typing import Optional
from app.crud.user import user as crud_user

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    return security_get_current_user(db=db, token=token)

def get_user_service(db: Session = Depends(get_db)):
    return UserService(db)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

def get_current_user_optional(
    db: Session = Depends(get_db), 
    token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[User]:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    phone: str = payload.get("sub")
    if not phone:
        return None
    user = crud_user.get_by_phone(db, phone=phone)
    if not user or not user.is_active:
        return None
    return user