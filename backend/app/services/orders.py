from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.menu_item import MenuItem
from app.models.order import Order, OrderItem
from app.models.payment_ledger import PaymentLedgerEntry
from app.schemas.orders import CheckoutRequest

_MAX_ORDER_TOTAL = Decimal("99999999.99")
_LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


def local_day_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=_LOCAL_TIMEZONE)


def local_day_after(value: date) -> datetime:
    return local_day_start(value + timedelta(days=1))


def validate_transition(order: Order, expected_status: str, new_status: str) -> None:
    if order.status != expected_status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order status must be {expected_status} before it can become {new_status}.",
        )
    order.status = new_status


def create_order(db: Session, customer_id: int, payload: CheckoutRequest) -> Order:
    requested_ids = [line.menu_item_id for line in payload.items]
    menu_items = db.scalars(
        select(MenuItem)
        .where(MenuItem.id.in_(requested_ids))
        .with_for_update()
    ).all()
    menu_by_id = {item.id: item for item in menu_items}

    missing_ids = [item_id for item_id in requested_ids if item_id not in menu_by_id]
    if missing_ids:
        raise HTTPException(status_code=404, detail={"code": "MENU_ITEM_NOT_FOUND", "menu_item_ids": missing_ids})

    restaurant_ids = {menu_by_id[item_id].restaurant_id for item_id in requested_ids}
    if len(restaurant_ids) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An order can contain items from only one restaurant.",
        )

    unavailable = [
        {"menu_item_id": item_id, "name": menu_by_id[item_id].name}
        for item_id in requested_ids
        if not menu_by_id[item_id].is_available
    ]
    if unavailable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ITEM_UNAVAILABLE", "items": unavailable},
        )

    changed_prices = []
    total = Decimal("0.00")
    for line in payload.items:
        menu_item = menu_by_id[line.menu_item_id]
        if line.expected_unit_price is not None and line.expected_unit_price != menu_item.price:
            changed_prices.append(
                {
                    "menu_item_id": menu_item.id,
                    "name": menu_item.name,
                    "expected_unit_price": format(line.expected_unit_price, ".2f"),
                    "current_unit_price": format(menu_item.price, ".2f"),
                }
            )
        total += menu_item.price * line.quantity

    if changed_prices:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PRICE_CHANGED", "message": "Review the current menu prices and try checkout again.", "items": changed_prices},
        )
    if total > _MAX_ORDER_TOTAL:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The order total exceeds the supported maximum.",
        )

    order = Order(
        customer_id=customer_id,
        restaurant_id=next(iter(restaurant_ids)),
        status="PLACED",
        payment_status="MOCK_PAID",
        delivery_address=payload.delivery_address,
        total_amount=total,
    )
    order.items = [
        OrderItem(
            menu_item_id=line.menu_item_id,
            item_name=menu_by_id[line.menu_item_id].name,
            unit_price=menu_by_id[line.menu_item_id].price,
            quantity=line.quantity,
        )
        for line in payload.items
    ]
    db.add(order)
    try:
        db.flush()
        db.add(
            PaymentLedgerEntry(
                order_id=order.id,
                entry_type="PAYMENT",
                status="MOCK_PAID",
                amount=total,
            )
        )
        db.commit()
        db.refresh(order)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The order could not be saved. Please retry checkout.",
        ) from exc
    return order


def cancel_placed_order(db: Session, order: Order) -> Order:
    validate_transition(order, "PLACED", "CANCELLED")
    order.payment_status = "VOIDED"
    db.add(
        PaymentLedgerEntry(
            order_id=order.id,
            entry_type="VOIDED",
            status="VOIDED",
            amount=order.total_amount,
        )
    )
    try:
        db.commit()
        db.refresh(order)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The cancellation could not be saved. Please retry.",
        ) from exc
    return order
