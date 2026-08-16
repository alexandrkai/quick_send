# app/schemas/message.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models.models import ChannelType, MessageStatus

class MessageBase(BaseModel):
    sender_phone: str
    recipient_phone: Optional[str] = None
    recipient_email: Optional[str] = None
    text: str
    channels: ChannelType

class MessageCreate(MessageBase):
    sender_user_id: Optional[int] = None
    order_id: Optional[UUID] = None

class MessageUpdate(BaseModel):
    status: Optional[MessageStatus] = None
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None

class MessageInDB(MessageBase):
    id: int
    sender_user_id: Optional[int]
    order_id: UUID
    status: MessageStatus
    external_ids: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    delivered_at: Optional[datetime]

    class Config:
        from_attributes = True