from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.order import Order
from app.models.payment_ledger import PaymentLedgerEntry
from app.models.refund_request import RefundRequest
from app.models.restaurant import Restaurant
from app.models.review import Review
from app.models.user import User
from app.schemas.refunds import RefundDecision
from app.schemas.reviews import ReviewCreate


def _customer_order(db: Session, order_id: int, customer_id: int) -> Order:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.customer_id == customer_id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order


def get_customer_review(db: Session, order_id: int, customer_id: int) -> Review:
    _customer_order(db, order_id, customer_id)
    review = db.scalar(select(Review).where(Review.order_id == order_id, Review.customer_id == customer_id))
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No review has been submitted for this order.")
    return review


def create_customer_review(db: Session, order_id: int, customer_id: int, payload: ReviewCreate) -> Review:
    order = _customer_order(db, order_id, customer_id)
    if order.delivered_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A review can be submitted after delivery.")
    if db.scalar(select(Review.id).where(Review.order_id == order.id)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A review already exists for this order.")

    review = Review(order_id=order.id, customer_id=customer_id, rating=payload.rating, comment=payload.comment)
    db.add(review)
    try:
        db.commit()
        db.refresh(review)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A review already exists for this order.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The review could not be saved. Please retry.") from exc
    return review


def get_customer_refund_request(db: Session, order_id: int, customer_id: int) -> RefundRequest:
    _customer_order(db, order_id, customer_id)
    refund_request = db.scalar(
        select(RefundRequest).where(
            RefundRequest.order_id == order_id,
            RefundRequest.customer_id == customer_id,
        )
    )
    if refund_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No refund request exists for this order.")
    return refund_request


def create_customer_refund_request(
    db: Session, order_id: int, customer_id: int, reason: str
) -> RefundRequest:
    order = _customer_order(db, order_id, customer_id)
    if order.delivered_at is None or order.status != "DELIVERED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A refund request can be submitted only for a delivered order.",
        )
    if db.scalar(select(RefundRequest.id).where(RefundRequest.order_id == order.id)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A refund request already exists for this order.")

    request = RefundRequest(order_id=order.id, customer_id=customer_id, reason=reason, status="PENDING")
    db.add(request)
    try:
        db.commit()
        db.refresh(request)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A refund request already exists for this order.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The refund request could not be saved. Please retry.") from exc
    return request


def list_owner_refund_requests(
    db: Session,
    owner_id: int,
    page: int,
    page_size: int,
    refund_status: str | None,
) -> tuple[list[RefundRequest], int]:
    restaurant_id = db.scalar(select(Restaurant.id).where(Restaurant.owner_id == owner_id))
    if restaurant_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No restaurant is associated with this owner.")
    filters = [Order.restaurant_id == restaurant_id]
    if refund_status is not None:
        filters.append(RefundRequest.status == refund_status)
    query = select(RefundRequest).join(Order, Order.id == RefundRequest.order_id).where(*filters)
    count_query = select(RefundRequest.id).join(Order, Order.id == RefundRequest.order_id).where(*filters)
    total = db.scalar(select(func.count()).select_from(count_query.subquery())) or 0
    requests = db.scalars(
        query.options(
            selectinload(RefundRequest.order).selectinload(Order.items),
            selectinload(RefundRequest.customer),
        )
        .order_by(RefundRequest.created_at.desc(), RefundRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return requests, total


def decide_owner_refund_request(
    db: Session, request_id: int, owner_id: int, decision: RefundDecision
) -> RefundRequest:
    refund_request = db.scalar(
        select(RefundRequest)
        .join(Order, Order.id == RefundRequest.order_id)
        .join(Restaurant, Restaurant.id == Order.restaurant_id)
        .options(
            selectinload(RefundRequest.order).selectinload(Order.items),
            selectinload(RefundRequest.customer),
        )
        .where(RefundRequest.id == request_id, Restaurant.owner_id == owner_id)
        .with_for_update()
    )
    if refund_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund request not found.")
    if refund_request.status != "PENDING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending refund requests can be decided.")

    order = refund_request.order
    refund_entry = None
    if decision.status == "APPROVED":
        if order.delivered_at is None or order.status != "DELIVERED" or order.payment_status != "MOCK_PAID":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only delivered orders with a completed mock payment can be refunded.",
            )
        payments = db.scalars(
            select(PaymentLedgerEntry)
            .where(PaymentLedgerEntry.order_id == order.id, PaymentLedgerEntry.entry_type == "PAYMENT")
            .order_by(PaymentLedgerEntry.id)
        ).all()
        if len(payments) != 1 or payments[0].status != "MOCK_PAID":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The original payment record is unavailable.")
        refund_entry = PaymentLedgerEntry(
            order_id=order.id,
            entry_type="REFUND",
            status="REFUNDED",
            amount=payments[0].amount,
        )

    refund_request.status = decision.status
    refund_request.reviewed_by_id = owner_id
    refund_request.reviewed_at = datetime.now(timezone.utc)
    if decision.status == "APPROVED":
        order.status = "REFUNDED"
        order.payment_status = "REFUNDED"
        db.add(refund_entry)

    try:
        db.commit()
        db.refresh(refund_request)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The refund decision could not be saved. Please retry.",
        ) from exc
    return refund_request
