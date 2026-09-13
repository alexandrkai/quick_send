from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.models import VerificationCode, VerificationType, Contact, User
from app.schemas.schemas import VerificationCodeCreate, VerificationCodeUpdate


class CRUDVerificationCode(CRUDBase[VerificationCode, VerificationCodeCreate, VerificationCodeUpdate]):

    def get_valid_code(
        self,
        db: Session,
        *,
        type: VerificationType,
        code: str,
        contact: Optional[Contact] = None,
        user: Optional[User] = None
    ) -> Optional[VerificationCode]:
        now = datetime.now()
        conditions = [
            VerificationCode.type == type,
            VerificationCode.used.is_(False),
            VerificationCode.expires_at > now,
            VerificationCode.code == code
        ]
        if user:
            conditions.append(VerificationCode.user_id == user.id)
        if contact:
            conditions.append(VerificationCode.contact_id == contact.id)

        return db.query(VerificationCode).filter(*conditions).order_by(VerificationCode.created_at.desc()).first()

    def mark_used(self, db: Session, *, code_obj: VerificationCode) -> VerificationCode:
        return self.update(db, db_obj=code_obj, obj_in={"used": True})

    def get_active_code(
        self,
        db: Session,
        *,
        type: VerificationType,
        contact_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Optional[VerificationCode]:
        if not user_id and not contact_id:
            raise ValueError("Не указан один из обязательных параметров: user_id или contact_id")

        now = datetime.now()
        conditions = [
            VerificationCode.type == type,
            VerificationCode.used.is_(False),
            VerificationCode.expires_at > now
        ]
        if contact_id:
            conditions.append(VerificationCode.contact_id == contact_id)
        if user_id:
            conditions.append(VerificationCode.user_id == user_id)

        return db.query(VerificationCode).filter(*conditions).order_by(VerificationCode.created_at.desc()).first()

    def count_recent_codes_for_contact(
        self,
        db: Session,
        *,
        contact_id: Optional[int] = None,
        user_id: Optional[int] = None,
        hours: int = 1
    ) -> int:
        since = datetime.now() - timedelta(hours=hours)
        conditions = [VerificationCode.created_at >= since]

        if contact_id:
            conditions.append(VerificationCode.contact_id == contact_id)
        if user_id:
            conditions.append(VerificationCode.user_id == user_id)

        return db.query(VerificationCode).filter(*conditions).count()


crud_verification_code = CRUDVerificationCode(VerificationCode)