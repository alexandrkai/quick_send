from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChannelBase(BaseModel):
    code: str

class ChannelCreate(ChannelBase):
    pass

class ChannelUpdate(BaseModel):
    code: Optional[str] = None

class ChannelInDB(ChannelBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True