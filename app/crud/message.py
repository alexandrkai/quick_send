# app/crud/message.py
from typing import Optional, List
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.models import Message
from app.schemas.message import MessageCreate, MessageUpdate

class CRUDMessage(CRUDBase[Message, MessageCreate, MessageUpdate]):
    def get_by_order_id(self, db: Session, *, order_id: str) -> List[Message]:
        return db.query(Message).filter(Message.order_id == order_id).all()

    def get_by_sender_phone(self, db: Session, *, sender_phone: str, skip: int = 0, limit: int = 100) -> List[Message]:
        return db.query(Message).filter(Message.sender_phone == sender_phone).offset(skip).limit(limit).all()

message = CRUDMessage(Message)