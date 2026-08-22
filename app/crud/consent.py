# app/crud/consent.py
from sqlalchemy.orm import Session
from typing import Optional
from app.crud.base import CRUDBase
from app.models.models import Consent,Channel
from app.schemas.consent import ConsentCreate, ConsentUpdate

class CRUDConsent(CRUDBase[Consent, ConsentCreate, ConsentUpdate]):
    
    def get_by_channel_and_value(self, db: Session, *, channel: Channel, value: str) -> Optional[Consent]:
        """_summary_
        поиск соглашения по каналу и значению
        Args:
            db (Session): _description_
            channel (Channel): _description_
            value (str): _description_

        Returns:
            Optional[Consent]: _description_
        """
        return db.query(Consent).filter(
            Consent.channel_id == channel.id,
            Consent.value == value
        ).first()

consent = CRUDConsent(Consent)