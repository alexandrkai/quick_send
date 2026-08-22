from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.models import MessageStatus, ChannelType

class MessageBase(BaseModel):
    user_id: int
    channel_identifier_id: int
    recipient_value: str
    text: str
    channel_type: ChannelType

class MessageCreate(MessageBase):
    order_id: Optional[UUID] = None

class MessageUpdate(BaseModel):
    status: Optional[MessageStatus] = None
    error_message: Optional[str] = None
    delivered_at: Optional[datetime] = None

class MessageInDB(MessageBase):
    id: int
    status: MessageStatus
    order_id: UUID
    error_message: Optional[str]
    delivered_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True