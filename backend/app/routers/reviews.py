from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.user import User
from app.schemas.reviews import ReviewCreate, ReviewPublic
from app.services.reviews_refunds import create_customer_review, get_customer_review

router = APIRouter(prefix="/orders", tags=["customer reviews"])
customer_only = require_roles("CUSTOMER")


@router.post("/{order_id}/review", response_model=ReviewPublic, status_code=status.HTTP_201_CREATED)
def submit_review(
    order_id: int,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    customer: User = Depends(customer_only),
):
    return create_customer_review(db, order_id, customer.id, payload)


@router.get("/{order_id}/review", response_model=ReviewPublic)
def read_review(
    order_id: int,
    db: Session = Depends(get_db),
    customer: User = Depends(customer_only),
):
    return get_customer_review(db, order_id, customer.id)
