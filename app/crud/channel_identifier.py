# app/crud/channel_identifier.py
from app.crud.base import CRUDBase
from app.models import S_ChannelIdentifier,Session,S_Channel
from app.schemas import ChannelIdentifierCreate, ChannelIdentifierUpdate,List
from sqlalchemy.orm import joinedload

class CRUDChannelIdentifier(CRUDBase[S_ChannelIdentifier, ChannelIdentifierCreate, ChannelIdentifierUpdate]):
    
    def get_by_channel_and_field(self, db: Session, *, channel: S_Channel, name: str):
        return db.query(S_ChannelIdentifier).filter(
            S_ChannelIdentifier.channel_id == channel.id,
            S_ChannelIdentifier.name == name
        ).first()

    def get_defaults_with_channels(self, db: Session) -> List[S_ChannelIdentifier]:
        """
        Возвращает список дефолтных идентификаторов вместе со связанными каналами.
        Доступ к объекту канала: identifier.channel
        """
        return (
            db.query(S_ChannelIdentifier)
            .options(joinedload(S_ChannelIdentifier.channel))
            .filter(S_ChannelIdentifier.is_default.is_(True))
            .all()
        )
crud_channel_identifier = CRUDChannelIdentifier(S_ChannelIdentifier)