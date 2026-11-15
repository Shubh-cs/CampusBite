from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.order import Order
from app.models.reminder_log import ReminderLog
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.reminders import PaginatedOwnerReminders

router = APIRouter(prefix="/owner/reminders", tags=["owner reminders"])
owner_only = require_roles("OWNER")


@router.get("", response_model=PaginatedOwnerReminders)
def list_owner_reminders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    owner: User = Depends(owner_only),
) -> dict:
    filters = (
        ReminderLog.owner_id == owner.id,
        Restaurant.owner_id == owner.id,
        Order.restaurant_id == ReminderLog.restaurant_id,
    )
    scoped = select(ReminderLog).join(
        Restaurant, Restaurant.id == ReminderLog.restaurant_id
    ).join(Order, Order.id == ReminderLog.order_id).where(*filters)
    count_query = select(ReminderLog.id).join(
        Restaurant, Restaurant.id == ReminderLog.restaurant_id
    ).join(Order, Order.id == ReminderLog.order_id).where(*filters)
    total = db.scalar(select(func.count()).select_from(count_query.subquery())) or 0
    reminders = db.scalars(
        scoped.options(
            joinedload(ReminderLog.order).joinedload(Order.customer),
        )
        .order_by(ReminderLog.created_at.desc(), ReminderLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"items": reminders, "page": page, "page_size": page_size, "total": total}
