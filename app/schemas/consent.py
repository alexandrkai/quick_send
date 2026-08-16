# app/schemas/consent.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.models import ConsentStatus

class ConsentBase(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    status: ConsentStatus = ConsentStatus.ALLOWED

class ConsentCreate(ConsentBase):
    pass

class ConsentUpdate(BaseModel):
    status: Optional[ConsentStatus] = None
    confirmed_at: Optional[datetime] = None

class ConsentInDB(ConsentBase):
    id: int
    user_id: Optional[int]
    confirmed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True