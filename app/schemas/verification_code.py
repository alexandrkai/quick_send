# app/schemas/verification_code.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.models import VerificationType

class VerificationCodeBase(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    code: str
    type: VerificationType
    expires_at: datetime

class VerificationCodeCreate(VerificationCodeBase):
    user_id: Optional[int] = None

# Добавляем схему для обновления (пока только used)
class VerificationCodeUpdate(BaseModel):
    used: Optional[bool] = None

class VerificationCodeInDB(VerificationCodeBase):
    id: int
    user_id: Optional[int]
    used: bool
    created_at: datetime

    class Config:
        from_attributes = True