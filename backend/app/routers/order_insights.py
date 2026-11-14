from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.user import User
from app.schemas.order_insights import OrderInsightsQuestion, OrderInsightsResponse
from app.services.order_insights import answer_customer_order_question

router = APIRouter(prefix="/insights", tags=["customer order insights"])
customer_only = require_roles("CUSTOMER")


@router.post("/orders", response_model=OrderInsightsResponse)
def ask_about_orders(
    payload: OrderInsightsQuestion,
    db: Session = Depends(get_db),
    customer: User = Depends(customer_only),
) -> OrderInsightsResponse:
    return answer_customer_order_question(db, customer.id, payload)
