from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.crud.channel_identifier import channel_identifier as crud_channel_identifier
from app.crud.consent import consent as crud_consent
from app.crud.verification_code import verification_code as crud_verification_code
from app.crud.channel import channel as crud_channel
from app.models.models import Channel


class ChannelService:
    def __init__(self, db: Session):
        self.db = db
        
    def get_channel_by_code(self,code:str)->Optional[Channel] :
        return crud_channel.get_by_code(self.db,code=code)