# app/crud/user_document.py
from typing import List, Optional, Union, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from app.models import UserDocument, ApprovalStatus


class CRUDUserDocument:
    def get(self, db: Session, id: int) -> Optional[UserDocument]:
        """Получить запись по ID."""
        return db.query(UserDocument).filter(UserDocument.id == id).first()

    def get_by_user_and_document(
        self, db: Session, *, user_id: int, document_id: int
    ) -> Optional[UserDocument]:
        """Получить документ пользователя по составному ключу user_id + document_id."""
        return (
            db.query(UserDocument)
            .filter(
                UserDocument.user_id == user_id,
                UserDocument.document_id == document_id,
            )
            .first()
        )

    def get_user_approved_document_ids(
        self, db: Session, *, user_id: int
    ) -> List[int]:
        """Получить список ID всех документов, которые пользователь уже подтвердил."""
        records = (
            db.query(UserDocument.document_id)
            .filter(
                UserDocument.user_id == user_id,
                UserDocument.status == ApprovalStatus.ACTIVE,
            )
            .all()
        )
        return [r[0] for r in records]

    def create(
        self, db: Session, *, obj_in: Union[Dict[str, Any], Any]
    ) -> UserDocument:
        """Создать новую запись согласия/ознакомления."""
        if isinstance(obj_in, dict):
            create_data = obj_in
        else:
            create_data = obj_in.model_dump()

        db_obj = UserDocument(**create_data)
        db.add(db_obj)
        db.flush()
        return db_obj

    def upsert_draft(
        self,
        db: Session,
        *,
        user_id: int,
        document_id: int,
        verification_code_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserDocument:
        """
        Создает черновик (DRAFT) или обновляет существующую запись, 
        если она ещё не была подтверждена.
        """
        record = self.get_by_user_and_document(
            db, user_id=user_id, document_id=document_id
        )
        if record:
            if record.status != ApprovalStatus.ACTIVE:
                record.status = ApprovalStatus.DRAFT
                record.verification_code_id = verification_code_id
                record.ip_address = ip_address
                record.user_agent = user_agent
                db.add(record)
                db.flush()
            return record

        return self.create(
            db,
            obj_in={
                "user_id": user_id,
                "document_id": document_id,
                "status": ApprovalStatus.DRAFT,
                "verification_code_id": verification_code_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
            },
        )

    def approve_documents_by_code(
        self,
        db: Session,
        *,
        user_id: int,
        verification_code_id: int,
        document_ids: Optional[List[int]] = None,
    ) -> int:
        """
        Массово переводит черновики пользователя в статус APPROVED 
        после успешной проверки SMS-кода.
        """
        query = (
            update(UserDocument)
            .where(
                UserDocument.user_id == user_id,
                UserDocument.verification_code_id == verification_code_id,
                UserDocument.status == ApprovalStatus.DRAFT,
            )
        )
        if document_ids:
            query = query.where(UserDocument.document_id.in_(document_ids))

        result = db.execute(
            query.values(status=ApprovalStatus.ACTIVE)
        )
        db.flush()
        return result.rowcount

    def update(
        self,
        db: Session,
        *,
        db_obj: UserDocument,
        obj_in: Union[Dict[str, Any], Any],
    ) -> UserDocument:
        """Обновить существующую запись."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.add(db_obj)
        db.flush()
        return db_obj


crud_user_document = CRUDUserDocument()