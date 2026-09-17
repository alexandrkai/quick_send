from typing import Optional,List
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models import S_Document, UserDocumentType
from app.schemas import DocumentCreate, DocumentUpdate

class CRUDDocument(CRUDBase[S_Document, DocumentCreate, DocumentUpdate]):
    def get_active(self, db: Session, doc_type: UserDocumentType) -> Optional[S_Document]:
        return db.query(S_Document).filter(
            S_Document.doc_type == doc_type,
            S_Document.is_active == True
        ).first()
        
    def get_active_terms_and_privacy(self, db: Session) -> List[S_Document]:
        """Возвращает строго последние актуальные версии документов terms и privacy."""
        return (
        db.query(S_Document)
        .filter(
            S_Document.doc_type.in_([
                getattr(UserDocumentType.TERMS, "value", UserDocumentType.TERMS),
                getattr(UserDocumentType.PRIVACY, "value", UserDocumentType.PRIVACY),
            ]),
            S_Document.is_active.is_(True),
        )
        .distinct(S_Document.doc_type)
        .order_by(
            S_Document.doc_type,
            S_Document.effective_date.desc(),
            S_Document.id.desc(),
        )
        .all()
        )

    def get_by_version(self, db: Session, doc_type: UserDocumentType, version: str) -> Optional[S_Document]:
        return db.query(S_Document).filter(
            S_Document.doc_type == doc_type,
            S_Document.version == version
        ).first()

    def get_history(self, db: Session, doc_type: UserDocumentType, skip: int = 0, limit: int = 100):
        return db.query(S_Document).filter(
            S_Document.doc_type == doc_type
        ).order_by(S_Document.effective_date.desc()).offset(skip).limit(limit).all()

crud_document = CRUDDocument(S_Document)