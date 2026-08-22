# app/core/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.models.models import get_db
from app.core.security import get_current_user as security_get_current_user
from app.services.user import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    return security_get_current_user(db=db, token=token)

def get_user_service(db: Session = Depends(get_db)):
    return UserService(db)