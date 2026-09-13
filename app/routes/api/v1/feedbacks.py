from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.models import get_db
from app.schemas import FeedbackCreate
from app.services.feedback import FeedbackService
from app.services.email import send_feedback_email
from app.crud.feedback import crud_feedback as crud_feedback

router = APIRouter(prefix="/feedback", tags=["Обратная связь"])


def get_client_ip(request: Request) -> str:
    # 1. Если приложение за прокси (Nginx, Traefik, балансировщик)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # 2. Прямое TCP-соединение (без обратного прокси)
    if request.client:
        return request.client.host

    return "unknown"


@router.post("/", summary="Создать обратную связь")
async def send_feedback(
    data: FeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    # Получаем User-Agent
    raw_ua = request.headers.get("user-agent")
    user_agent = raw_ua[:255] if raw_ua else None

    # Получаем IP-адрес
    client_ip = get_client_ip(request)
    data.user_agent = user_agent
    data.ip = client_ip
    service = FeedbackService(db)
    feedback = service.create_feedback(data)

    return {
        "status": "ok",
        "message": "Сообщение отправлено. Мы свяжемся с вами в ближайшее время.",
    }


@router.get("/")
async def get_feedbacks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получение списка всех сообщений (для администратора)."""
    # Здесь можно добавить проверку прав администратора
    return crud_feedback.get_multi(db, skip=skip, limit=limit)
