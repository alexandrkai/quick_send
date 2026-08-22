# app/crud/channel.py
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.models import Channel
from app.schemas.channel import ChannelCreate, ChannelUpdate

class CRUDChannel(CRUDBase[Channel, ChannelCreate, ChannelUpdate]):
    def get_by_code(self, db: Session, *, code: str):
        return db.query(Channel).filter(Channel.code == code).first()

channel = CRUDChannel(Channel)