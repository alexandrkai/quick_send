# app/crud/consent.py
from typing import Optional
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.models import Consent
from app.schemas.consent import ConsentCreate, ConsentUpdate

class CRUDConsent(CRUDBase[Consent, ConsentCreate, ConsentUpdate]):
    def get_by_phone(self, db: Session, *, phone: str) -> Optional[Consent]:
        return db.query(Consent).filter(Consent.phone == phone).first()

    def get_by_email(self, db: Session, *, email: str) -> Optional[Consent]:
        return db.query(Consent).filter(Consent.email == email).first()

    def set_status(self, db: Session, *, consent: Consent, status: str) -> Consent:
        return self.update(db, db_obj=consent, obj_in={"status": status})

consent = CRUDConsent(Consent)