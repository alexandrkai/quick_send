from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.models import ConsentStatus

class ConsentBase(BaseModel):
    channel_id: int
    value: str
    status: ConsentStatus = ConsentStatus.ALLOWED

class ConsentCreate(ConsentBase):
    confirmed_at: Optional[datetime] = None
    verification_code_id: Optional[int] = None

class ConsentUpdate(BaseModel):
    status: Optional[ConsentStatus] = None
    confirmed_at: Optional[datetime] = None
    verification_code_id: Optional[int] = None

class ConsentInDB(ConsentBase):
    id: int
    confirmed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True