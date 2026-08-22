from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.models import UserRole

class UserBase(BaseModel):
    contact_data: Dict[str, Any] = {}
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True
    is_verified: bool = False

class UserCreate(UserBase):
    password_hash: Optional[str] = None

class UserUpdate(BaseModel):
    contact_data: Optional[Dict[str, Any]] = None
    full_name: Optional[str] = None
    password_hash: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None

class UserInDB(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True