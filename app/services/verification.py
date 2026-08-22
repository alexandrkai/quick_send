# app/services/verification.py
import random
import string
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.crud.verification_code import verification_code as crud_verification_code

from app.models.models import VerificationCode,Channel
from app.schemas.verification_code import VerificationCodeCreate

from typing import Optional

class VerificationService:
    def __init__(self, db: Session):
        self.db = db

    def generate_code(self, value: str, channel:Channel,type: str = "login") -> str:
        code = ''.join(random.choices(string.digits, k=6))
        expires_at = datetime.now() + timedelta(minutes=5)
        vc_in = VerificationCodeCreate(
            value=value,
            code=code,
            type=type,
            channel_id=channel.id,
            expires_at=expires_at
        )
        vc = crud_verification_code.create(self.db, obj_in=vc_in)
        return vc

    def verify_code(self, channel:Channel,value: str, code: str, type: str) -> Optional[VerificationCode]:
        vc = crud_verification_code.get_valid_code(self.db, channel=channel,value=value, code=code, type=type)
        if not vc:
            return None
        crud_verification_code.mark_used(self.db, code_obj=vc)
        return vc
    
    def get_active_code(self, channel: Channel, value: str,type:str) -> VerificationCode:
        """
        Проверяет наличие активного (неиспользованного и неистекшего) кода
        для указанного канала и значения.

        :param channel_id: ID канала (из таблицы channels)
        :param value: телефон или email
        :return: (код, оставшееся время в секундах) или (None, 0)
        """
    
        # Ищем последний созданный активный код
        vc = self.db.query(VerificationCode).filter(
            VerificationCode.channel_id == channel.id,
            VerificationCode.value == value,
            VerificationCode.used == False,
            VerificationCode.type==type
        ).order_by(VerificationCode.created_at.desc()).first()
        now = datetime.now()
        if vc:
            if vc.expires_at > now:
                return vc
            else:
                vc.used=True
        return None