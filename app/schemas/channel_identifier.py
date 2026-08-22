from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChannelIdentifierBase(BaseModel):
    channel_id: int
    field_name: str
    validation_regex: Optional[str] = None

class ChannelIdentifierCreate(ChannelIdentifierBase):
    pass

class ChannelIdentifierUpdate(BaseModel):
    field_name: Optional[str] = None
    validation_regex: Optional[str] = None

class ChannelIdentifierInDB(ChannelIdentifierBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True