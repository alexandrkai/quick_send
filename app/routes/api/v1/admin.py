# app/api/v1/admin.py
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.models.models import engine, Base, get_db, SessionLocal,create_engine,text
import logging
from app.models.init_data import *
from app.crud.feedback import crud_feedback
from app.schemas import ChannelCreate,ChannelIdentifierCreate
from sqlalchemy.exc import OperationalError

import re

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/reset-db")
async def reset_database(db: Session = Depends(get_db)):
    """
    Пересоздаёт все таблицы в базе данных.
    ВНИМАНИЕ: все данные будут потеряны! Используйте только в разработке.
    """
    try:
        return init_db()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        

@router.get("/feedbacks")
async def get_feedbacks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user) # позже добавим авторизацию
):
    # if current_user.role != "admin":
    #     raise HTTPException(status_code=403, detail="Доступ запрещён")
    feedbacks = crud_feedback.get_multi(db, skip=skip, limit=limit)
    return feedbacks