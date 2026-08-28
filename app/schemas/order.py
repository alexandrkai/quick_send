from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.models.models import OrderStatus,ChannelType

class OrderBase(BaseModel):
    user_id: Optional[int] = None
    sender_phone: Optional[str] = None
    channel_type: ChannelType
    total_recipients: int = 0
    text_preview: Optional[str] = None

class OrderCreate(OrderBase):
    pass

class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    total_recipients: Optional[int] = None

class OrderInDB(OrderBase):
    id: int
    uuid: UUID
    status: OrderStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True