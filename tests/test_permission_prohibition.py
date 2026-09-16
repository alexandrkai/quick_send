# tests/test_permission_prohibition.py

from datetime import datetime, timedelta
import pytest
from fastapi import HTTPException
from unittest.mock import patch

from app.models.models import (
    Contact,
    PermissionProhibition,
    PermissionProhibitionStatus,
    PermissionProhibitionType,
    VerificationCode,
    VerificationType,
)
from app.schemas.schemas import (
    PermissionProhibitionRequestSMS,
    PermissionProhibitionConfirmSMS,
)
from app.services.permission_prohibition import PermissionProhibitionService


@pytest.fixture
def fake_redis():
    """In-memory хранилище для мока функций Redis"""
    store = {}

    def mock_write_value(key, data, expires_in=300):
        token = "test-token-uuid-12345"
        store[token] = data
        return {"verification_token": token}

    def mock_read_value(key, token):
        return store.get(token)

    def mock_check_exists(key, token):
        return token in store

    def mock_delete_value(key, token):
        store.pop(token, None)

    with patch("app.services.permission_prohibition.write_value", side_effect=mock_write_value), \
         patch("app.services.permission_prohibition.read_value", side_effect=mock_read_value), \
         patch("app.services.permission_prohibition.check_exists", side_effect=mock_check_exists), \
         patch("app.services.permission_prohibition.delete_value", side_effect=mock_delete_value):
        yield store


def test_request_code_creates_contact_code_and_draft(db_session, fake_redis):
    """Проверка генерации кода, создания Contact и черновика DRAFT через request_code"""
    service = PermissionProhibitionService(db_session)
    phone = "+79990001122"

    req_schema = PermissionProhibitionRequestSMS(
        channel_identifier="phone",
        value=phone,
        type=PermissionProhibitionType.BLOCKED
    )

    response = service.request_code(req_schema)

    # 1. Проверяем ответ сервиса
    assert response.status_code == 1
    assert response.token is not None

    # 2. Проверяем создание системного контакта
    contact = db_session.query(Contact).filter_by(value=phone).first()
    assert contact is not None

    # 3. Проверяем генерацию кода
    vc = (
        db_session.query(VerificationCode)
        .filter_by(contact_id=contact.id, type=VerificationType.PERMISSION, used=False)
        .first()
    )
    assert vc is not None

    # 4. Проверяем создание записи PermissionProhibition в статусе DRAFT
    draft = (
        db_session.query(PermissionProhibition)
        .filter_by(contact_id=contact.id)
        .first()
    )
    assert draft is not None
    assert draft.status == PermissionProhibitionStatus.DRAFT
    assert draft.type == PermissionProhibitionType.BLOCKED
    assert draft.verification_code_id == vc.id


def test_confirm_code_success(db_session, fake_redis):
    """Успешное подтверждение через токен и SMS-код переводит DRAFT в ACTIVE"""
    service = PermissionProhibitionService(db_session)
    phone = "+79991112233"

    req_schema = PermissionProhibitionRequestSMS(
        channel_identifier="phone",
        value=phone,
        type=PermissionProhibitionType.BLOCKED
    )
    req_res = service.request_code(req_schema)

    contact = db_session.query(Contact).filter_by(value=phone).first()
    vc = db_session.query(VerificationCode).filter_by(contact_id=contact.id).first()

    confirm_schema = PermissionProhibitionConfirmSMS(
        channel_identifier="phone",
        value=phone,
        code=vc.code,
        token=req_res.token,
        type=PermissionProhibitionType.BLOCKED
    )

    confirm_res = service.confirm_code(confirm_schema)

    # 1. Проверяем ответ
    assert confirm_res.status_code == 0
    assert "запрещена" in confirm_res.message

    # 2. Проверяем статус в БД
    db_session.refresh(vc)
    assert vc.used is True

    rule = (
        db_session.query(PermissionProhibition)
        .filter_by(contact_id=contact.id)
        .first()
    )
    assert rule.status == PermissionProhibitionStatus.ACTIVE
    assert rule.is_active is True


def test_confirm_code_invalid_code(db_session, fake_redis):
    """Передача неверного кода вызывает ошибку 400 и не меняет статус DRAFT"""
    service = PermissionProhibitionService(db_session)
    phone = "+79992223344"

    req_res = service.request_code(
        PermissionProhibitionRequestSMS(
            channel_identifier="phone",
            value=phone,
            type=PermissionProhibitionType.BLOCKED
        )
    )

    confirm_schema = PermissionProhibitionConfirmSMS(
        channel_identifier="phone",
        value=phone,
        code="999999",  # неверный код
        token=req_res.token,
        type=PermissionProhibitionType.BLOCKED
    )

    with pytest.raises(HTTPException) as exc_info:
        service.confirm_code(confirm_schema)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error_code"] == "-2"

    contact = db_session.query(Contact).filter_by(value=phone).first()
    rule = db_session.query(PermissionProhibition).filter_by(contact_id=contact.id).first()
    assert rule.status == PermissionProhibitionStatus.DRAFT


def test_confirm_code_invalid_token(db_session, fake_redis):
    """Попытка подтверждения с несуществующим токеном сессии"""
    service = PermissionProhibitionService(db_session)

    confirm_schema = PermissionProhibitionConfirmSMS(
        channel_identifier="phone",
        value="+79990000000",
        code="123456",
        token="non-existent-token",
        type=PermissionProhibitionType.BLOCKED
    )

    with pytest.raises(HTTPException) as exc_info:
        service.confirm_code(confirm_schema)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error_code"] == "-5"


def test_request_code_already_has_active_rule(db_session, fake_redis):
    """Если контакт уже имеет этот активный статус, код не высылается повторно"""
    service = PermissionProhibitionService(db_session)
    phone = "+79995556677"

    # 1. Первый раз ставим запрет
    req_res1 = service.request_code(
        PermissionProhibitionRequestSMS(
            channel_identifier="phone",
            value=phone,
            type=PermissionProhibitionType.BLOCKED
        )
    )
    contact = db_session.query(Contact).filter_by(value=phone).first()
    vc = db_session.query(VerificationCode).filter_by(contact_id=contact.id).first()
    service.confirm_code(
        PermissionProhibitionConfirmSMS(
            channel_identifier="phone",
            value=phone,
            code=vc.code,
            token=req_res1.token,
            type=PermissionProhibitionType.BLOCKED
        )
    )

    # 2. Повторно запрашиваем тот же самый статус
    req_res2 = service.request_code(
        PermissionProhibitionRequestSMS(
            channel_identifier="phone",
            value=phone,
            type=PermissionProhibitionType.BLOCKED
        )
    )

    assert req_res2.status_code == 2
    assert "уже запрещена" in req_res2.message
    assert req_res2.token is None