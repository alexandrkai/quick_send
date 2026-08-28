from sqlalchemy.orm import Session
from app.models.models import Feedback
from app.schemas.feedback import FeedbackCreate

class CRUDFeedback:
    
    def create(self, db: Session, *, obj_in: FeedbackCreate) -> Feedback:
        db_obj = Feedback(
            name=obj_in.user_name,
            phone=obj_in.user_phone,
            email=obj_in.user_email,
            topic=obj_in.topic,
            message=obj_in.message,
            page_url=obj_in.page_url,
            user_agent=obj_in.user_agent
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

feedback = CRUDFeedback()
