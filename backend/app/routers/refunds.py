from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.user import User
from app.schemas.refunds import (
    PaginatedRefundRequests,
    RefundDecision,
    RefundRequestCreate,
    RefundRequestPublic,
    RefundStatus,
)
from app.services.reviews_refunds import (
    create_customer_refund_request,
    decide_owner_refund_request,
    get_customer_refund_request,
    list_owner_refund_requests,
)

customer_router = APIRouter(prefix="/orders", tags=["customer refunds"])
owner_router = APIRouter(prefix="/owner/refund-requests", tags=["owner refunds"])
customer_only = require_roles("CUSTOMER")
owner_only = require_roles("OWNER")


@customer_router.post("/{order_id}/refund-request", response_model=RefundRequestPublic, status_code=201)
def request_refund(
    order_id: int,
    payload: RefundRequestCreate,
    db: Session = Depends(get_db),
    customer: User = Depends(customer_only),
):
    return create_customer_refund_request(db, order_id, customer.id, payload.reason)


@customer_router.get("/{order_id}/refund-request", response_model=RefundRequestPublic)
def read_refund_request(
    order_id: int,
    db: Session = Depends(get_db),
    customer: User = Depends(customer_only),
):
    return get_customer_refund_request(db, order_id, customer.id)


@owner_router.get("", response_model=PaginatedRefundRequests)
def list_refund_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    request_status: RefundStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    owner: User = Depends(owner_only),
):
    requests, total = list_owner_refund_requests(db, owner.id, page, page_size, request_status)
    return {"items": requests, "page": page, "page_size": page_size, "total": total}


@owner_router.patch("/{request_id}", response_model=RefundRequestPublic)
def decide_refund_request(
    request_id: int,
    payload: RefundDecision,
    db: Session = Depends(get_db),
    owner: User = Depends(owner_only),
):
    return decide_owner_refund_request(db, request_id, owner.id, payload)
