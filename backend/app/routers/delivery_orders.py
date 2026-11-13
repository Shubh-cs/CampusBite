from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.order import Order
from app.models.user import User
from app.schemas.orders import DeliveryFilterStatus, DeliveryStatusUpdate, OrderPublic, PaginatedOrders
from app.services.orders import validate_transition

router = APIRouter(prefix="/delivery/orders", tags=["delivery orders"])
delivery_only = require_roles("DELIVERY_PARTNER")


@router.get("", response_model=PaginatedOrders)
def list_assigned_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    order_status: DeliveryFilterStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    partner: User = Depends(delivery_only),
) -> dict:
    filters = [Order.delivery_partner_id == partner.id]
    if order_status:
        filters.append(Order.status == order_status)
    total = db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    orders = db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(*filters)
        .order_by(Order.placed_at.desc(), Order.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"items": orders, "page": page, "page_size": page_size, "total": total}


@router.get("/{order_id}", response_model=OrderPublic)
def get_assigned_order(
    order_id: int,
    db: Session = Depends(get_db),
    partner: User = Depends(delivery_only),
) -> Order:
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.delivery_partner_id == partner.id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


@router.patch("/{order_id}/status", response_model=OrderPublic)
def update_delivery_status(
    order_id: int,
    payload: DeliveryStatusUpdate,
    db: Session = Depends(get_db),
    partner: User = Depends(delivery_only),
) -> Order:
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.delivery_partner_id == partner.id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    expected_status = "ASSIGNED" if payload.status == "OUT_FOR_DELIVERY" else "OUT_FOR_DELIVERY"
    validate_transition(order, expected_status, payload.status)
    if payload.status == "DELIVERED":
        order.delivered_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(order)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The delivery status could not be saved. Please retry.",
        ) from exc
    return order
