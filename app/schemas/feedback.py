from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class FeedbackCreate(BaseModel):
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    user_email: EmailStr  # сделаем обязательным
    topic: Optional[str] = None
    message: str
    page_url: Optional[str] = None
    user_agent: Optional[str] = None

class FeedbackInDB(FeedbackCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True