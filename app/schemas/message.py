from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.models.models import MessageStatus

class MessageBase(BaseModel):
    recipient_value: str
    text: str

class MessageCreate(MessageBase):
    user_id: Optional[int] = None
    channel_identifier_id: int
    order_id: int

class MessageUpdate(BaseModel):
    status: Optional[MessageStatus] = None
    error_message: Optional[str] = None
    delivered_at: Optional[datetime] = None

class MessageInDB(MessageBase):
    id: int
    order_id: int
    status: MessageStatus
    error_message: Optional[str]
    delivered_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True