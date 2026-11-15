from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ReminderCustomerContext(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str


class ReminderOrderContext(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    placed_at: datetime
    total_amount: Decimal
    customer: ReminderCustomerContext


class OwnerReminderPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    created_at: datetime
    order: ReminderOrderContext


class PaginatedOwnerReminders(BaseModel):
    items: list[OwnerReminderPublic]
    page: int
    page_size: int
    total: int
