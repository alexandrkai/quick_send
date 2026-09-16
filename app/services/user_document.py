from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.crud.user_document import crud_user_document
from app.models.models import ApprovalStatus, S_Document, User, UserDocument


class UserDocumentService:
    def __init__(self, db: Session):
        self.db = db

    def get_all_active_system_documents(self) -> List[S_Document]:
        """
        Возвращает самые актуальные версии активных системных документов (Terms, Privacy).
        Используется DISTINCT ON (doc_type) с сортировкой по дате вступления в силу.
        """
        return (
            self.db.query(S_Document)
            .filter(S_Document.is_active.is_(True))
            .distinct(S_Document.doc_type)
            .order_by(S_Document.doc_type, S_Document.effective_date.desc())
            .all()
        )

    def check_user_documents_status(
        self, user_id: int
    ) -> Tuple[bool, List[S_Document]]:
        """
        Проверяет, все ли активные системные документы приняты пользователем.
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
    ) -> Dict[str, Any]:
        """
        Эндпоинт проверки статуса документов:
        Проверяет наличие пользователя по номеру телефона и возвращает статус согласий.
        """
        user = self.db.query(User).filter(User.phone == phone).first()

        if not user:
            # Новый пользователь — требуются все активные документы
            all_docs = self.get_all_active_system_documents()
            terms_doc = next((d for d in all_docs if str(d.doc_type) == "terms"), None)
            privacy_doc = next((d for d in all_docs if str(d.doc_type) == "privacy"), None)
            
            return {
                "need_consent": True,
                "terms": {
                    "id": terms_doc.id if terms_doc else None,
                    "content": terms_doc.content if terms_doc else "",
                    
                },
                "privacy": {
                    "id": privacy_doc.id if privacy_doc else None,
                    "content": privacy_doc.content if privacy_doc else "",
                },
            }

        need_consent, missing_docs = self.check_user_documents_status(user.id)
        terms_doc = next((d for d in missing_docs if str(d.doc_type) == "terms"), None)
        privacy_doc = next((d for d in missing_docs if str(d.doc_type) == "privacy"), None)

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

        # ищем драфтовые документы
        user_drafts_exists=crud_user_document.get_all(self.db,user_id=user_id,status=ApprovalStatus.DRAFT)
        user_terms_doc = next((d for d in user_drafts_exists if str(d.doc_type) == "terms"), None)
        user_privacy_doc = next((d for d in user_drafts_exists if str(d.doc_type) == "privacy"), None)
        
        drafts = []
        for doc in missing_docs:
            if user_privacy_doc:
                if doc.id==user_privacy_doc.document_id:
                    crud_user_document.update(self.db,db_obj=user_privacy_doc,obj_in={"verification_code_id":verification_code_id})
                    continue
            if user_terms_doc:
                if doc.id==user_terms_doc.document_id:
                    crud_user_document.update(self.db,db_obj=user_terms_doc,obj_in={"verification_code_id":verification_code_id})
                    continue
                
            draft = crud_user_document.upsert_draft(
                self.db,
                user_id=user_id,
                document_id=doc.id,
                verification_code_id=verification_code_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            drafts.append(draft)
        self.db.commit()
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
        Переводит предсозданные DRAFT документы в статус ACTIVE строго по verification_code_id.
        Если черновиков не было, проверяет, акцептованы ли уже актуальные версии.
        Если документы не приняты и нет валидного черновика к этому коду — бросает ошибку безопасности.
        """
        # 1. Проверяем, есть ли вообще документы, требующие согласия
        need_consent, missing_docs = self.check_user_documents_status(user_id)
        
        # Пользователь уже ранее подписал все актуальные версии документов — всё в порядке
        if not need_consent:
            return 0

        # 2. Активируем ТОЛЬКО те черновики, которые были привязаны к этому проверочному коду
        missing_doc_ids = [d.id for d in missing_docs]
        updated_count = crud_user_document.approve_documents_by_code(
            self.db,
            user_id=user_id,
            verification_code_id=verification_code_id,
            document_ids=missing_doc_ids,
        )

        # 3. Если остались документы, для которых не существовало черновика с этим кодом — прерываем операцию
        if updated_count < len(missing_doc_ids):
            raise Exception(
                # status_code=status.HTTP_403_FORBIDDEN,
                # detail="Юридические документы не были запрошены или привязаны к коду подтверждения",
                "Юридические документы не были запрошены или привязаны к коду подтверждения"
            )

        return updated_count