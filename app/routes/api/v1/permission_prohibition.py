# app/api/v1/permission_prohibition.py
from fastapi import APIRouter, Depends, HTTPException,Query
from sqlalchemy.orm import Session

from app.models import get_db,PermissionProhibitionType
from app.services.permission_prohibition import PermissionProhibitionService
from app.schemas import (
    PermissionProhibitionRequestSMS,
    PermissionProhibitionConfirmSMS,
    PermissionProhibitionApiResponse,
    ContactCheckResponse
)

router = APIRouter(
    prefix="/permission_prohibition",
    tags=["Работа контактов со своими согласиями/запретами на рассылку сообщений"]
)


@router.post("/request", response_model=PermissionProhibitionApiResponse)
def request_permission_code(
    payload: PermissionProhibitionRequestSMS,
    db: Session = Depends(get_db),
):
    try:
        service = PermissionProhibitionService(db)
        return service.request_code(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/confirm", response_model=PermissionProhibitionApiResponse)
def confirm_permission_code(
    payload: PermissionProhibitionConfirmSMS,
    db: Session = Depends(get_db),
):
    try:
        service = PermissionProhibitionService(db)
        return service.confirm_code(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/check-recipient", response_model=ContactCheckResponse)
def check_recipient_permission(
    channel: str = Query(..., pattern="^(phone|email)$"),
    value: str = Query(...),
    db: Session = Depends(get_db)
):
    service = PermissionProhibitionService(db)
    # Используем метод поиска активного правила по дефолтному идентификатору
    rule = service.get_permission_prohibition_by_is_default_channel_identifier_and_value(
        value=value, 
        channel_identifier_name=channel
    )
    
    if rule and rule.type == PermissionProhibitionType.BLOCKED:
        channel_title = "телефоном" if channel == "phone" else "email"
        return ContactCheckResponse(
            allowed=False,
            channel=channel,
            value=value,
            message=f"Получатель с данным {channel_title} установил запрет на получение рассылок."
        )

    return ContactCheckResponse(
        allowed=True,
        channel=channel,
        value=value,
        message="Рассылка разрешена"
    )