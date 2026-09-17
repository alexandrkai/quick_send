# app/crud/user_consent_document.py
from typing import List, Optional
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.models import UserDocument
from app.schemas.approval import (
    ApprovalCreate,
    ApprovalUpdate,
)


class CRUDApproval(
    CRUDBase[UserDocument, ApprovalCreate, ApprovalUpdate]
):
    def get_by_document_and_identifier(
        self, db: Session, *, document_id: int, identifier_value: str
    ) -> Optional[UserDocument]:
        """Проверяет наличие согласия конкретного контакта на конкретный документ."""
        return (
            db.query(UserDocument)
            .filter(
                UserDocument.document_id == document_id,
                UserDocument.identifier_value == identifier_value,
            )
            .first()
        )

    def get_by_identifier(
        self, db: Session, *, identifier_value: str
    ) -> List[UserDocument]:
        """Возвращает историю всех принятых документов по номеру телефона/email."""
        return (
            db.query(UserDocument)
            .filter(UserDocument.identifier_value == identifier_value)
            .all()
        )

    def create_consent(
        self,
        db: Session,
        *,
        document_id: int,
        identifier_value: str,
        user_id: Optional[int] = None,
        verification_code_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserDocument:
        """Создаёт запись согласия на документ."""
        obj_in = ApprovalCreate(
            document_id=document_id,
            identifier_value=identifier_value,
            user_id=user_id,
            verification_code_id=verification_code_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return self.create(db, obj_in=obj_in)


crud_approval = CRUDApproval(UserDocument)