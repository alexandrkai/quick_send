from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.models import VerificationType

class VerificationCodeBase(BaseModel):
    user_id: Optional[int] = None
    value: str
    channel_id:int
    code: str
    type: VerificationType
    expires_at: datetime

class VerificationCodeCreate(VerificationCodeBase):
    pass

class VerificationCodeUpdate(BaseModel):
    used: Optional[bool] = None

class VerificationCodeInDB(VerificationCodeBase):
    id: int
    used: bool
    created_at: datetime

    class Config:
        from_attributes = True