from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserContactBase(BaseModel):
    user_id: int
    channel_identifier_id: int
    channel_identifier_value: str

class UserContactCreate(UserContactBase):
    pass

class UserContactUpdate(BaseModel):
    channel_identifier_value: Optional[str] = None

class UserContactInDB(UserContactBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True