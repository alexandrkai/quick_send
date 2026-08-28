from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.models import get_db
from app.schemas.feedback import FeedbackCreate
from app.services.feedback import FeedbackService
from app.services.email import send_feedback_email
from app.crud.feedback import feedback as crud_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])

@router.post("/")
async def send_feedback(
    data: FeedbackCreate,
    db: Session = Depends(get_db)
):
    # 1. Сохраняем в БД
    service = FeedbackService(db)
    # просто сохраняем фидбэк
    feedback = service.create_feedback(data)

    # 2. Отправляем email администратору
    # email_sent = send_feedback_email(
    #     name=data.user_name or "Аноним",
    #     email=data.user_email,
    #     subject=data.topic or "Без темы",
    #     message=data.message
    # )

    # if not email_sent:
    #     return {
    #         "status": "ok",
    #         "message": "Сообщение сохранено, но возникла проблема с отправкой письма. Мы свяжемся с вами в ближайшее время."
    #     }

    return {
        "status": "ok",
        "message": "Сообщение отправлено. Мы свяжемся с вами в ближайшее время."
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