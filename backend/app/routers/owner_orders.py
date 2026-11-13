from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.order import Order
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.orders import (
    DeliveryAssignmentRequest,
    DeliveryPartnerPublic,
    OrderPublic,
    OrderStatus,
    OwnerStatusUpdate,
    PaginatedOrders,
    validate_date_range,
)
from app.services.orders import local_day_after, local_day_start, validate_transition

router = APIRouter(prefix="/owner/orders", tags=["owner orders"])
owner_only = require_roles("OWNER")


def _owned_order(db: Session, owner_id: int, order_id: int) -> Order:
    order = db.scalar(
        select(Order)
        .join(Restaurant, Restaurant.id == Order.restaurant_id)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Restaurant.owner_id == owner_id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


@router.get("", response_model=PaginatedOrders)
def list_owner_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    placed_from: date | None = None,
    placed_to: date | None = None,
    db: Session = Depends(get_db),
    owner: User = Depends(owner_only),
) -> dict:
    try:
        validate_date_range(placed_from, placed_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    restaurant_id = db.scalar(select(Restaurant.id).where(Restaurant.owner_id == owner.id))
    if restaurant_id is None:
        raise HTTPException(status_code=404, detail="No restaurant is associated with this owner.")
    filters = [Order.restaurant_id == restaurant_id]
    if order_status:
        filters.append(Order.status == order_status)
    if placed_from:
        filters.append(Order.placed_at >= local_day_start(placed_from))
    if placed_to:
        filters.append(Order.placed_at < local_day_after(placed_to))
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


@router.get("/delivery-partners", response_model=list[DeliveryPartnerPublic])
def list_delivery_partners(
    db: Session = Depends(get_db), owner: User = Depends(owner_only)
) -> list[User]:
    if db.scalar(select(Restaurant.id).where(Restaurant.owner_id == owner.id)) is None:
        raise HTTPException(status_code=404, detail="No restaurant is associated with this owner.")
    return db.scalars(
        select(User)
        .where(User.role == "DELIVERY_PARTNER", User.is_active.is_(True))
        .order_by(User.id)
    ).all()


@router.post("/{order_id}/accept", response_model=OrderPublic)
def accept_order(
    order_id: int,
    db: Session = Depends(get_db),
    owner: User = Depends(owner_only),
) -> Order:
    order = _owned_order(db, owner.id, order_id)
    validate_transition(order, "PLACED", "ACCEPTED")
    db.commit()
    db.refresh(order)
    return order


@router.patch("/{order_id}/status", response_model=OrderPublic)
def update_preparation_status(
    order_id: int,
    payload: OwnerStatusUpdate,
    db: Session = Depends(get_db),
    owner: User = Depends(owner_only),
) -> Order:
    order = _owned_order(db, owner.id, order_id)
    expected_status = "ACCEPTED" if payload.status == "PREPARING" else "PREPARING"
    validate_transition(order, expected_status, payload.status)
    db.commit()
    db.refresh(order)
    return order


@router.post("/{order_id}/assign-delivery", response_model=OrderPublic)
def assign_delivery_partner(
    order_id: int,
    payload: DeliveryAssignmentRequest,
    db: Session = Depends(get_db),
    owner: User = Depends(owner_only),
) -> Order:
    order = _owned_order(db, owner.id, order_id)
    if order.status != "READY":
        raise HTTPException(status_code=409, detail="Only READY orders can be assigned.")
    partner = db.scalar(
        select(User).where(
            User.id == payload.delivery_partner_id,
            User.role == "DELIVERY_PARTNER",
            User.is_active.is_(True),
        )
    )
    if partner is None:
        raise HTTPException(status_code=404, detail="Active delivery partner not found.")
    order.delivery_partner_id = partner.id
    validate_transition(order, "READY", "ASSIGNED")
    db.commit()
    db.refresh(order)
    return order
