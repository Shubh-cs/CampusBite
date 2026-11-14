from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderInsightsQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)

    @field_validator("question", mode="before")
    @classmethod
    def trim_question(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ItemInsightFact(BaseModel):
    item_name: str
    quantity_ordered: int
    snapshot_spend: Decimal


class OrderLineInsightFact(BaseModel):
    item_name: str
    quantity: int
    unit_price: Decimal


class RecentOrderInsightFact(BaseModel):
    order_id: int
    placed_at: datetime
    status: str
    restaurant_name: str
    items: list[OrderLineInsightFact]


class VerifiedOrderFacts(BaseModel):
    currency: Literal["INR"] = "INR"
    timezone: Literal["Asia/Kolkata"] = "Asia/Kolkata"
    order_count: int
    order_counts_by_status: dict[str, int]
    gross_successful_payments: Decimal
    voided_amounts: Decimal
    refunded_amounts: Decimal
    net_spending: Decimal
    most_ordered_items: list[ItemInsightFact]
    recent_orders: list[RecentOrderInsightFact]
    recent_order_limit: int


class OrderInsightsResponse(BaseModel):
    answer: str
    verified_facts: VerifiedOrderFacts
