from sqlalchemy.orm import Session
from app.crud.feedback import crud_feedback
from app.schemas import FeedbackCreate
from app.models import Feedback


class FeedbackService:
    def __init__(self, db: Session):
        self.db = db

    def create_feedback(self, data: FeedbackCreate) -> Feedback:
        return crud_feedback.create(self.db, obj_in=data)