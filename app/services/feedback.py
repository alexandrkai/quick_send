from sqlalchemy.orm import Session
from app.crud.feedback import feedback
from app.schemas.feedback import FeedbackCreate
from app.models.models import Feedback


class FeedbackService:
    def __init__(self, db: Session):
        self.db = db

    def create_feedback(self, data: FeedbackCreate) -> Feedback:
        return feedback.create(self.db, obj_in=data)