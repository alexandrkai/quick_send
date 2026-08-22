# app/crud/user_contact.py
from sqlalchemy.orm import Session
from typing import Optional
from app.crud.base import CRUDBase
from app.models.models import UserContact
from app.schemas.user_contact import UserContactCreate, UserContactUpdate

class CRUDUserContact(CRUDBase[UserContact, UserContactCreate, UserContactUpdate]):
    def get_by_value(self, db: Session, *, value: str) -> Optional[UserContact]:
        return db.query(UserContact).filter(UserContact.channel_identifier_value == value).first()

    def get_by_user_and_channel_identifier(self, db: Session, *, user_id: int, channel_identifier_id: int) -> Optional[UserContact]:
        return db.query(UserContact).filter(
            UserContact.user_id == user_id,
            UserContact.channel_identifier_id == channel_identifier_id
        ).first()

user_contact = CRUDUserContact(UserContact)