from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.models import get_db,UserDocumentType
from app.schemas.schemas import CodeRequest
from app.services.feedback import FeedbackService
from app.services.email import send_feedback_email
from app.crud.approval import crud_approval

router = APIRouter(prefix="/user_document_consent", tags=["User Document Consent"])

@router.post("/verify-sms")
def verify_sms_code(data: CodeRequest, db: Session = Depends(get_db)):
    # ... верификация кода ...
    user = get_or_create_user(db, data.phone)
    token = create_access_token({"sub": user.phone})

    # Фиксируем согласие с текущими активными версиями
    terms_version = document_version.get_active(db, UserDocumentType.TERMS)
    privacy_version = document_version.get_active(db, UserDocumentType.PRIVACY)
    if terms_version and privacy_version:
        # Проверим, есть ли уже согласие с этими версиями
        existing = user_consent.get_by_phone_and_versions(db, data.phone, terms_version.id, privacy_version.id)
        if not existing:
            consent_in = UserConsentCreate(
                phone=data.phone,
                terms_version_id=terms_version.id,
                privacy_version_id=privacy_version.id,
                verification_code_id=verification_code.id
            )
            user_consent.create(db, obj_in=consent_in)

    response = JSONResponse({"status": "ok", "user_id": user.id})
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="lax")
    return response