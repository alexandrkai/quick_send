from sqlalchemy.orm import Session
from typing import List
from app.crud.channel_identifier import crud_channel_identifier
from app.models import S_ChannelIdentifier,S_Channel

class ChannelIdentifierService:
    def __init__(self, db: Session):
        self.db = db
        
    def get_by_id(self,id):
        return crud_channel_identifier.get(self.db,id)
        
    def get(self,channel:S_Channel,name:str)->S_ChannelIdentifier:
        return crud_channel_identifier.get_by_channel_and_field(self.db,channel=channel,name=name)
    
    def get_default_channel_identifiers(self)->List[S_ChannelIdentifier] :
        return crud_channel_identifier.get_defaults_with_channels(self.db)