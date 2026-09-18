# api_service/routes/order_ws.py

import asyncio
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.models.models import SessionLocal
from sqlalchemy.orm import Session
from app.models.models import Order, Message, MessageStatus

router = APIRouter(prefix="/ws/orders", tags=["orders"])

def get_order_snapshot(db: Session, order_uuid: UUID) -> Dict[str, Any]:
    """
    Формирует полный слепок состояния заказа и связанных сообщений
    для отправки через WebSocket на страницу мониторинга.
    """
    order = db.query(Order).filter(Order.uuid == order_uuid).first()
    if not order:
        return {
            "type": "ERROR",
            "message": "Заказ не найден"
        }

    # Выбираем только необходимые поля сообщений
    messages = (
        db.query(
            Message.id,
            Message.recipient_value,
            Message.status,
            Message.error_message,
        )
        .filter(Message.order_id == order.id)
        .order_by(Message.id.asc())
        .all()
    )

    total = len(messages)
    delivered = sum(1 for m in messages if m.status == MessageStatus.DELIVERED)
    failed = sum(1 for m in messages if m.status == MessageStatus.FAILED)
    # Сообщения, которые еще в очереди или в процессе отправки воркером
    pending = sum(
        1 for m in messages 
        if m.status in (MessageStatus.PENDING, getattr(MessageStatus, "PROCESSING", "processing"))
    )

    progress_percent = int(((delivered + failed) / total) * 100) if total > 0 else 0

    return {
        "type": "SNAPSHOT",
        "order": {
            "uuid": str(order.uuid),
            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
            "text_preview": order.text_preview,
            "is_flagged": order.is_flagged,
        },
        "stats": {
            "total": total,
            "delivered": delivered,
            "failed": failed,
            "pending": pending,
            "progress_percent": progress_percent,
        },
        "messages": [
            {
                "id": m.id,
                "recipient": m.recipient_value,
                "status": m.status.value if hasattr(m.status, "value") else str(m.status),
                "error": m.error_message,
            }
            for m in messages
        ],
    }



@router.websocket("/{order_uuid}")
async def order_status_ws(websocket: WebSocket, order_uuid: str):
    await websocket.accept()
    
    try:
        while True:
            # Открываем короткую сессию только на чтение
            with SessionLocal() as db:
                snapshot = get_order_snapshot(db, UUID(order_uuid))
                await websocket.send_json(snapshot)
                
                # Если все сообщения обработаны — завершаем цикл
                if snapshot["stats"]["pending"] == 0 and snapshot["stats"]["total"] > 0:
                    break

            await asyncio.sleep(1.0)  # Интервал опроса БД
            
    except WebSocketDisconnect:
        pass