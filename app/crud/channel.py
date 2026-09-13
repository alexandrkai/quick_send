# app/crud/channel.py
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.models import *
from app.schemas import ChannelCreate, ChannelUpdate,Tuple,Optional

class CRUDChannel(CRUDBase[S_Channel, ChannelCreate, ChannelUpdate]):
    def get_by_code(self, db: Session, *, code: str):
        return db.query(S_Channel).filter(S_Channel.code == code).first()
    
    def get_channel_and_default_channel_identifier(self, db: Session, *, code: str)->Tuple[Optional[S_Channel],Optional[S_ChannelIdentifier]]:
        channel=self.get_by_code(db,code=code)
        if channel:
            channel_identifier=next((d for d in channel.identifiers if d.is_default == True), None)
            return channel,channel_identifier
        return None,None

crud_channel = CRUDChannel(S_Channel)