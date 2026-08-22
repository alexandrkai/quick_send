# app/crud/verification_code.py
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.crud.base import CRUDBase
from app.models.models import VerificationCode,Channel
from app.schemas.verification_code import VerificationCodeCreate, VerificationCodeUpdate

class CRUDVerificationCode(CRUDBase[VerificationCode, VerificationCodeCreate, VerificationCodeUpdate]):
    def get_valid_code(self, db: Session, *, channel:Channel,value: str, code: str, type: str) -> Optional[VerificationCode]:
        return db.query(VerificationCode).filter(
            VerificationCode.value == value,
            VerificationCode.code == code,
            VerificationCode.type == type,
            VerificationCode.used == False,
            VerificationCode.channel_id==channel.id,
            VerificationCode.expires_at > datetime.now()
        ).first()

    def mark_used(self, db: Session, *, code_obj: VerificationCode) -> VerificationCode:
        return self.update(db, db_obj=code_obj, obj_in={"used": True})

verification_code = CRUDVerificationCode(VerificationCode)