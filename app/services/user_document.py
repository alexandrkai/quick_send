# app/services/user_document.py
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    User,
    S_Document,
    UserDocument,
    ApprovalStatus,
    VerificationCode,
)
from app.crud.user_document import crud_user_document


class UserDocumentService:
    def __init__(self, db: Session):
        self.db = db

    from sqlalchemy import func

    def get_all_active_system_documents(self) -> List[S_Document]:
        """Возвращает самые актуальные версии активных системных документов."""
        # В PostgreSQL через DISTINCT ON по коду документа берем самую свежую версию:
        return (
            self.db.query(S_Document)
            .filter(S_Document.is_active.is_(True))
            .distinct(S_Document.code)
            .order_by(S_Document.code, S_Document.effective_date.desc())
            .all()
        )
    
    def check_user_documents_status(
        self, user_id: int
    ) -> Tuple[bool, List[S_Document]]:
        """
        Проверяет, все ли активные документы приняты пользователем.
        Возвращает кортеж (need_consent, missing_documents).
        """
        active_docs = self.get_all_active_system_documents()
        if not active_docs:
            return False, []

        approved_doc_ids = set(
            crud_user_document.get_user_approved_document_ids(
                self.db, user_id=user_id
            )
        )

        missing_docs = [doc for doc in active_docs if doc.id not in approved_doc_ids]
        need_consent = len(missing_docs) > 0

        return need_consent, missing_docs

    def check_documents_by_phone(
        self, phone: str
    ) -> Dict[str, any]:
        """
        Метод для эндпоинта /api/v1/auth/check-user-documents:
        Проверяет наличие пользователя по телефону и возвращает статус согласий.
        """
        user = self.db.query(User).filter(User.phone == phone).first()

        if not user:
            # Новый пользователь — нужны все активные документы
            all_docs = self.get_all_active_system_documents()
            terms_doc = next((d for d in all_docs if d.code == "terms"), None)
            privacy_doc = next((d for d in all_docs if d.code == "privacy"), None)
            return {
                "need_consent": True,
                "terms": {"id": terms_doc.id if terms_doc else None, "content": terms_doc.content if terms_doc else ""},
                "privacy": {"id": privacy_doc.id if privacy_doc else None, "content": privacy_doc.content if privacy_doc else ""},
            }

        need_consent, missing_docs = self.check_user_documents_status(user.id)
        terms_doc = next((d for d in missing_docs if d.code == "terms"), None)
        privacy_doc = next((d for d in missing_docs if d.code == "privacy"), None)

        return {
            "need_consent": need_consent,
            "terms": {
                "id": terms_doc.id if terms_doc else None,
                "content": terms_doc.content if terms_doc else "",
            },
            "privacy": {
                "id": privacy_doc.id if privacy_doc else None,
                "content": privacy_doc.content if privacy_doc else "",
            },
        }

    def create_document_drafts_for_verification(
        self,
        *,
        user_id: int,
        verification_code_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> List[UserDocument]:
        """
        Создает черновики (DRAFT) для документов, которые еще не приняты,
        привязывая их к высланному коду подтверждения.
        """
        need_consent, missing_docs = self.check_user_documents_status(user_id)
        if not need_consent:
            return []

        drafts = []
        for doc in missing_docs:
            draft = crud_user_document.upsert_draft(
                self.db,
                user_id=user_id,
                document_id=doc.id,
                verification_code_id=verification_code_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            drafts.append(draft)

        return drafts

    def confirm_user_documents(
        self,
        *,
        user_id: int,
        verification_code_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> int:
        """
        Фиксирует согласие с документами (переводит в APPROVED).
        Вызывается внутри единой сервисной транзакции после успешной валидации SMS-кода.
        """
        active_docs = self.get_all_active_system_documents()
        doc_ids = [d.id for d in active_docs]

        # 1. Обновляем черновики, привязанные к этому проверочному коду
        updated_count = crud_user_document.approve_documents_by_code(
            self.db,
            user_id=user_id,
            verification_code_id=verification_code_id,
            document_ids=doc_ids,
        )

        # 2. Если пользователь подтверждает документы без предсозданного черновика
        # (или если черновик не был привязан к коду), создаем сразу APPROVED
        approved_ids = set(
            crud_user_document.get_user_approved_document_ids(
                self.db, user_id=user_id
            )
        )
        for doc_id in doc_ids:
            if doc_id not in approved_ids:
                crud_user_document.create(
                    self.db,
                    obj_in={
                        "user_id": user_id,
                        "document_id": doc_id,
                        "status": ApprovalStatus.APPROVED,
                        "verification_code_id": verification_code_id,
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                    },
                )
                updated_count += 1

        return updated_count