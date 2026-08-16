# app/crud/verification_code.py
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
from app.crud.base import CRUDBase
from app.models.models import VerificationCode
from app.schemas.verification_code import VerificationCodeCreate, VerificationCodeUpdate

class CRUDVerificationCode(CRUDBase[VerificationCode, VerificationCodeCreate, VerificationCodeUpdate]):
    def get_valid_code(self, db: Session, *, phone: Optional[str] = None, email: Optional[str] = None, code: str) -> Optional[VerificationCode]:
        query = db.query(VerificationCode).filter(
            VerificationCode.code == code,
            VerificationCode.used == False,
            VerificationCode.expires_at > datetime.utcnow()
        )
        if phone:
            query = query.filter(VerificationCode.phone == phone)
        elif email:
            query = query.filter(VerificationCode.email == email)
        return query.first()

    def mark_used(self, db: Session, *, code_obj: VerificationCode) -> VerificationCode:
        return self.update(db, db_obj=code_obj, obj_in={"used": True})

verification_code = CRUDVerificationCode(VerificationCode)