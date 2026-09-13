from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.contact import ContactService
from app.core.dependencies import get_current_user
from app.models.models import User,get_db

router = APIRouter(prefix="/contacts", tags=["contacts"])

@router.get("/")
def get_my_contacts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ContactService(db)
    contacts = service.get_user_contacts(current_user.id, skip=skip, limit=limit)
    return contacts

@router.post("/add")
def add_contact_to_user(
    channel_identifier_id: int,
    value: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ContactService(db)
    try:
        contact = service.add_contact_to_user(
            current_user.id,
            channel_identifier_id,
            value,
            is_active=True
        )
        return contact
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))