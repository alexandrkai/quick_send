# app/api/v1/consent.py
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.orm import Session

from typing import Optional
from app.models.models import get_db,ContactType
from app.services.consent import ConsentService,ConsentRequest,ConsentConfirm
from app.services.verification import VerificationService
from app.services.channel import ChannelService
from app.models.models import ConsentStatus,ChannelType
from app.utils.sms_provider import send_sms
from app.utils.email_provider import send_email
from app.core.exceptions import ChannelException
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


router = APIRouter(prefix="/consent", tags=["consent"])

@router.post("/request")
def request_consent_verification(data: ConsentRequest, db: Session = Depends(get_db)):
    """Запрос кода для изменения согласия."""
    consent_service = ConsentService(db)
    try:
        result = consent_service.request_verification(data,"consent")
        # если код был ранее отправлен
        if "message" in result:
            return result
        if "vc" in result:
            vc=result['vc']
            time_wait=int((vc.expires_at - datetime.now()).total_seconds())
        if "is_new" in result:
            if result["is_new"]:
                # TODO этот код надо отправить!!
                # Отправка на контакт
                if data.value.startswith('+') or data.value.isdigit():
                    send_sms(data.value, f"Ваш код: {vc.code}. У вас {time_wait} секунд на его активацию")
                else:
                    send_email(data.value, "Код подтверждения", f"Ваш код: {vc.code}. У вас {time_wait} секунд на его активацию")
        if data.channel == 'email':
            channel_message="Провверьте почтовый яцщик."
        else:
            channel_message="Провверьте телефон."
        return {"status": "ok", "message": f"Код отправлен. {channel_message} Ваш код: {vc.code}. {time_wait} секунд на его активацию"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/confirm")
def confirm_consent(data: ConsentConfirm, db: Session = Depends(get_db)):
    """Подтверждение кода и установка статуса."""
    service = ConsentService(db)
    try:
        success = service.confirm_consent(
            channel_code=data.channel,
            value=data.value,
            code=data.code,
            status=data.status
        )
        if not success:
            raise HTTPException(status_code=400, detail="Неверный или просроченный код")
        if data.status.value==ConsentStatus.BLOCKED:
            message="Установлен запрет "
        else:
            message="Дано согласие "
        if data.channel=="phone":
            message+="на рассылку с нашего сервиса смс-сообщений"
        else:
            message+="на рассылку с нашего сервиса почтовых сообщений"
        return {"status": "ok", "message": message}
            
    except Exception as e:
        # raise HTTPException(status_code=400, detail=str(e))
        return JSONResponse(
        status_code=400,
        content={"detail": str(e)}
    )

@router.get("/status")
def get_consent_status(channel_code: str, value: str, db: Session = Depends(get_db)):
    """Получить текущий статус согласия."""
    service = ConsentService(db)
    
    consent = service.get_consent_by_channel_and_value(channel_code, value)
    if not consent:
        return {
            "channel_code": channel_code,
            "value": value,
            "status": ConsentStatus.ALLOWED,
            "confirmed_at": None,
            "message": "По умолчанию разрешено"
        }
    return {
        "channel_id": consent.channel_id,
        "value": consent.value,
        "status": consent.status,
        "confirmed_at": consent.confirmed_at
    }