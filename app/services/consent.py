# app/services/consent.py
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from app.crud.channel_identifier import channel_identifier as crud_channel_identifier
from app.crud.consent import consent as crud_consent
from app.crud.verification_code import verification_code as crud_verification_code
from app.crud.channel import channel as crud_channel
from app.models.models import Consent, ConsentStatus,ChannelType,Channel,ContactType
from app.schemas.consent import ConsentCreate, ConsentUpdate
from app.services.verification import VerificationService
from app.core.exceptions import ConsentException

class ConsentRequest(BaseModel):
    channel: ChannelType
    value: str
    status: ConsentStatus

class ConsentConfirm(ConsentRequest):
    code: str

class ConsentService:
    def __init__(self, db: Session):
        self.db = db
        self.verification_service = VerificationService(db)

    def get_consent_by_channel_code_and_value(self, value: str, *, channel_code: Optional[str]=None, channel:Optional[str]=None) -> Optional[Consent]:
        if channel_code:
            channel=crud_channel.get_by_code(self.db,code=channel_code)
        return crud_consent.get_by_channel_and_value(self.db, channel=channel, value=value)

    def create_or_update_consent(self, channel:Channel, value: str, status: ConsentStatus, verification_code_id: Optional[int] = None,consent: Optional[Consent] = None) -> Consent:
        if not consent:
            consent = self.get_consent_by_channel_code_and_value( value,channel=channel)
        if consent:
            # обновляем
            consent = crud_consent.update(self.db, db_obj=consent, obj_in={
                "status": status,
                "confirmed_at": datetime.now(),
                "verification_code_id": verification_code_id
            })
        else:
            consent_in = ConsentCreate(
                channel_id=channel.id,
                value=value,
                status=status,
                confirmed_at=datetime.now(),
                verification_code_id=verification_code_id
            )
            consent = crud_consent.create(self.db, obj_in=consent_in)
        return consent

    def request_verification(self, data: ConsentRequest,type:str) -> dict:
        """Генерирует код и отправляет его на указанный контакт."""
        # 1. проверяем наличие текущего соглашения
        result=dict()
        consent=self.get_consent_by_channel_code_and_value(data.value,channel_code=data.channel)
        # if not consent:
        #     result['consent']=consent
        if data.status==ConsentStatus.BLOCKED:
            if consent and consent.status==ConsentStatus.BLOCKED:
                result.update({"status": "ok"})
                if data.channel == ContactType.EMAIL:
                    result.update({"message": "Вы уже ранее запретили рассылку с нашего сервиса на Ваш email"})
                elif data.channel == ContactType.PHONE:
                    result.update({"message": "Вы уже ранее запретили рассылку СМС с нашего сервиса на Ваш телефон"})
                return result
        elif data.status==ConsentStatus.ALLOWED:
            if not consent or (consent and consent.status==ConsentStatus.ALLOWED):
                result.update({"status": "ok"})
                if data.channel == ContactType.EMAIL:
                    result.update({"message": "У Вас уже есть разрешение на рассылку с нашего сервиса на Ваш email"})
                elif data.channel == ContactType.PHONE:
                    result.update({"message": "У Вас уже есть разрешение на рассылку СМС с нашего сервиса на Ваш телефон"})
                return result
            pass
        # 2. проверяем, отправляли мы ранее код
        channel=crud_channel.get_by_code(self.db,code=data.channel) 
        vc=self.verification_service.get_active_code(channel,data.value,type)
        if vc:
            result.update( {"vc":vc,"is_new":False})
            return result
        # 3. Генерируем код через VerificationService
        vc = self.verification_service.generate_code(
            value=data.value,
            channel=channel,
            type=type
        )
        result.update( {"vc":vc,"is_new":True})
        return result

    def confirm_consent(self, channel_code: str, value: str, code: str, status: ConsentStatus) -> bool:
        """Подтверждение кода и установка статуса."""
        channel=crud_channel.get_by_code(self.db,code=channel_code)
        # Проверяем код
        vc = self.verification_service.verify_code(
            channel=channel,
            value=value,
            code=code,
            type="consent"
        )
        if not vc:
            return False
        # Создаём или обновляем согласие
        self.create_or_update_consent(
            channel=channel,
            value=value,
            status=status,
            verification_code_id=vc.id
        )
        return True