# app/crud/user_document.py
from typing import List, Optional, Union, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, update

from app.models import UserDocument, UserDocumentStatus,S_Document


class CRUDUserDocument:
    def get(self, db: Session, id: int) -> Optional[UserDocument]:
        """Получить запись по ID."""
        return db.query(UserDocument).filter(UserDocument.id == id).first()

    def get_all(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        document_id: Optional[int] = None,
        status: Optional[UserDocumentStatus] = None,
        with_relations: bool = True
    ) -> List[UserDocument]:
        """
        Получить список документов согласий с возможностью фильтрации и пагинации.

        :param skip: Смещение для пагинации
        :param limit: Количество записей
        :param user_id: Фильтр по конкретному пользователю
        :param document_id: Фильтр по ID юридического документа (S_Document)
        :param status: Фильтр по статусу (ACTIVE, DRAFT, DELETED)
        :param with_relations: Если True — жадно подгружает связанные сущности (User, Document, Code)
        """
        query = db.query(UserDocument)

        # Оптимизация: загружаем связанные объекты, чтобы избежать проблемы N+1
        if with_relations:
            query = query.options(
                joinedload(UserDocument.document),
                joinedload(UserDocument.user),
                joinedload(UserDocument.verification_code),
            )

        # Фильтры
        if user_id is not None:
            query = query.filter(UserDocument.user_id == user_id)

        if document_id is not None:
            query = query.filter(UserDocument.document_id == document_id)

        if status is not None:
            query = query.filter(UserDocument.status == status)

        return (
            query.order_by(UserDocument.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        only_active: bool = True
    ) -> List[UserDocument]:
        """
        Удобный метод для быстрого получения всех подписанных/активных документов пользователя.
        """
        target_status = UserDocumentStatus.ACTIVE if only_active else None
        return self.get_all(
            db,
            user_id=user_id,
            status=target_status,
            skip=0,
            limit=1000,
            with_relations=True
        )

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
    self,
    db: Session,
    *,
    user_id: int,
    doc_type_list: Optional[List[Any]] = None,
) -> List[int]:
        """Получить список ID всех документов (S_Document.id), которые пользователь уже подтвердил."""
        query = db.query(UserDocument.document_id).filter(
            UserDocument.user_id == user_id,
            UserDocument.status == UserDocumentStatus.ACTIVE,
        )

        if doc_type_list:
            # Приводим к строковым значениям .value, если переданы Enum
            clean_types = [
                getattr(item, "value", str(item)) for item in doc_type_list
            ]
            query = query.join(
                S_Document, S_Document.id == UserDocument.document_id
            ).filter(
                S_Document.doc_type.in_(clean_types),
                S_Document.is_active.is_(True),
            )

        records = query.all()
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
        db.commit()
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
            if record.status != UserDocumentStatus.ACTIVE:
                record.status = UserDocumentStatus.DRAFT
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
                "status": UserDocumentStatus.DRAFT,
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
                UserDocument.status == UserDocumentStatus.DRAFT,
            )
        )
        if document_ids:
            query = query.where(UserDocument.document_id.in_(document_ids))

        result = db.execute(
            query.values(status=UserDocumentStatus.ACTIVE)
        )
        db.flush()
        db.commit()
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
        db.commit()
        return db_obj


crud_user_document = CRUDUserDocument()
