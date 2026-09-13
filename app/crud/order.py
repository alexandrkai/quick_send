from app.crud.base import CRUDBase
from app.models import Order
from app.schemas import OrderCreate, OrderUpdate
from sqlalchemy.orm import Session

class CRUDOrder(CRUDBase[Order, OrderCreate, OrderUpdate]):
    def get_by_uuid(self, db: Session, uuid: str):
        return db.query(Order).filter(Order.uuid == uuid).first()

crud_order = CRUDOrder(Order)