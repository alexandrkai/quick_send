# app/crud/consent.py
from sqlalchemy.orm import Session
from typing import Optional
from app.crud.base import CRUDBase
from app.models.models import *
from app.schemas import *

# работа с договоренностями:запрет/разрешение рассылки
class CRUDPermissionProhibition(CRUDBase[PermissionProhibition, PermissionProhibitionCreate, PermissionProhibitionUpdate]):
    
    def get_by_contact(self, db: Session, *, contact: Contact) -> Optional[PermissionProhibition]:
        """_summary_
        поиск соглашения по каналу и значению
        Args:
            db (Session): _description_
            channel (Channel): _description_
            value (str): _description_

        Returns:
            Optional[PermissionProhibition]: _description_
        """
        return db.query(PermissionProhibition).filter(
            PermissionProhibition.contact_id == contact.id,
        ).first()
        
    def get_active_by_contact(self, db: Session, *, contact: Contact) -> Optional[PermissionProhibition]:
        """_summary_
        поиск соглашения по каналу и значению
        Args:
            db (Session): _description_
            channel (Channel): _description_
            value (str): _description_

        Returns:
            Optional[PermissionProhibition]: _description_
        """
        return db.query(PermissionProhibition).filter(
            PermissionProhibition.contact_id == contact.id,
            PermissionProhibition.status== PermissionProhibitionStatus.ACTIVE.value,
            PermissionProhibition.is_active==True).order_by(PermissionProhibition.created_at.desc()).first()
        
    def get_draft_by_contact_id(self, db: Session, *, contact_id: int) -> Optional[PermissionProhibition]:
        return (
            db.query(PermissionProhibition)
            .filter(PermissionProhibition.contact_id == contact_id
                    ,PermissionProhibition.status==PermissionProhibitionStatus.DRAFT)
            .order_by(PermissionProhibition.created_at.desc())
            .first()
        )

    def upsert_draft(
        self,
        db: Session,
        *,
        contact: Contact,
        perm_type: PermissionProhibitionType,
        code_id: int
    ) -> PermissionProhibition:
        record = self.get_draft_by_contact_id(db, contact_id=contact.id)
        if record:
            record.type = perm_type
            record.status = PermissionProhibitionStatus.DRAFT
            record.verification_code_id = code_id
            record.is_active = False
            db.commit()
            db.refresh(record)
            return record

        record = PermissionProhibition(
            contact_id=contact.id,
            type=perm_type,
            status=PermissionProhibitionStatus.DRAFT,
            verification_code_id=code_id,
            is_active=False
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def activate_permission(self, db: Session, *, record: PermissionProhibition, isCommit:bool=True) -> PermissionProhibition:
        record.status = PermissionProhibitionStatus.ACTIVE
        record.confirmed_at = datetime.now()
        record.is_active = True
        db.add(record)
        if isCommit:
            db.commit()
        else:
            db.flush()
        db.refresh(record)
        return record

crud_permission_prohibition = CRUDPermissionProhibition(PermissionProhibition)
