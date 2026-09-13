from sqlalchemy.orm import Session
from typing import Optional,Tuple
from app.crud.channel import crud_channel
from app.models.models import S_Channel,S_ChannelIdentifier

class ChannelService:
    def __init__(self, db: Session):
        self.db = db
        
    def get_channel_by_code(self,code:str)->Optional[S_Channel] :
        return crud_channel.get_by_code(self.db,code=code)
    
    def get_channel_by_id(self,id:int)->Optional[S_Channel] :
        return crud_channel.get(self.db,id=id)
    
    def get_channel_and_default_channel_identifier(self, code: str)->Tuple[Optional[S_Channel],Optional[S_ChannelIdentifier]]:
        return crud_channel.get_channel_and_default_channel_identifier(self.db,code=code)
    
    def get_channel_and_identifier_by_codes(
        self, channel_code: str, identifier_name: str
    ) -> Tuple[Optional[S_Channel], Optional[S_ChannelIdentifier]]:
        """
        Находит канал по code и его идентификатор по name.
        Возвращает кортеж (channel, identifier) либо (None, None).
        """
        result = (
            self.db.query(S_Channel, S_ChannelIdentifier)
            .join(
                S_ChannelIdentifier,
                S_ChannelIdentifier.channel_id == S_Channel.id
            )
            .filter(
                S_Channel.code == channel_code,
                S_Channel.is_active.is_(True),
                S_ChannelIdentifier.name == identifier_name,
                S_ChannelIdentifier.is_active.is_(True),
            )
            .first()
        )

        if not result:
            return None, None

        channel, identifier = result
        return channel, identifier