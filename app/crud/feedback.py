from sqlalchemy.orm import Session
from app.models.models import Feedback
from app.schemas import FeedbackCreate

class CRUDFeedback:
    
    def create(self, db: Session, *, obj_in: FeedbackCreate) -> Feedback:
        db_obj = Feedback(
            name=obj_in.name,
            email=obj_in.email,
            topic=obj_in.topic,
            message=obj_in.message,
            user_agent=obj_in.user_agent,
            ip=obj_in.ip
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

crud_feedback = CRUDFeedback()
