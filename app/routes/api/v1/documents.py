# app/api/v1/documents.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.crud.document import crud_document
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.core.dependencies import get_current_user
from app.models.models import User, UserRole,get_db

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("/active/{doc_type}")
def get_active_document(doc_type: str, db: Session = Depends(get_db)):
    # Получить активную версию для публичного доступа
    from app.models.models import ApprovalType
    try:
        doc_type_enum = ApprovalType(doc_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document type")
    doc = crud_document.get_active(db, doc_type_enum)
    if not doc:
        raise HTTPException(status_code=404, detail="Active version not found")
    return doc

@router.post("/")
def create_document_version(
    data: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")
    # Если новая версия активна, деактивируем предыдущую
    if data.is_active:
        old_active = crud_document.get_active(db, data.doc_type)
        if old_active:
            crud_document.update(db, db_obj=old_active, obj_in={"is_active": False})
    return crud_document.create(db, obj_in=data)