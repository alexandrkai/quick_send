from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.models import Message
from app.schemas.message import MessageCreate, MessageUpdate

class CRUDMessage(CRUDBase[Message, MessageCreate, MessageUpdate]):
    def get_by_order_id(self, db: Session, order_id: str):
        return db.query(Message).filter(Message.order_id == order_id).all()

    def get_by_recipient(self, db: Session, recipient_value: str):
        return db.query(Message).filter(Message.recipient_value == recipient_value).all()

message = CRUDMessage(Message)