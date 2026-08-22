# app/crud/channel_identifier.py
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.models import ChannelIdentifier
from app.schemas.channel_identifier import ChannelIdentifierCreate, ChannelIdentifierUpdate

class CRUDChannelIdentifier(CRUDBase[ChannelIdentifier, ChannelIdentifierCreate, ChannelIdentifierUpdate]):
    def get_by_channel_and_field(self, db: Session, *, channel_id: int, field_name: str):
        return db.query(ChannelIdentifier).filter(
            ChannelIdentifier.channel_id == channel_id,
            ChannelIdentifier.field_name == field_name
        ).first()

channel_identifier = CRUDChannelIdentifier(ChannelIdentifier)