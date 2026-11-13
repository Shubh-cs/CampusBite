from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.order import Order
from app.models.user import User
from app.schemas.orders import CheckoutRequest, OrderPublic, OrderStatus, PaginatedOrders, validate_date_range
from app.services.orders import cancel_placed_order, create_order, local_day_after, local_day_start

router = APIRouter(prefix="/orders", tags=["customer orders"])
customer_only = require_roles("CUSTOMER")


@router.post("", response_model=OrderPublic, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    customer: User = Depends(customer_only),
) -> Order:
    return create_order(db, customer.id, payload)


@router.get("", response_model=PaginatedOrders)
def list_customer_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    placed_from: date | None = None,
    placed_to: date | None = None,
    db: Session = Depends(get_db),
    customer: User = Depends(customer_only),
) -> dict:
    try:
        validate_date_range(placed_from, placed_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    filters = [Order.customer_id == customer.id]
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


@router.get("/{order_id}", response_model=OrderPublic)
def get_customer_order(
    order_id: int,
    db: Session = Depends(get_db),
    customer: User = Depends(customer_only),
) -> Order:
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.customer_id == customer.id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


@router.post("/{order_id}/cancel", response_model=OrderPublic)
def cancel_customer_order(
    order_id: int,
    db: Session = Depends(get_db),
    customer: User = Depends(customer_only),
) -> Order:
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.customer_id == customer.id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return cancel_placed_order(db, order)
