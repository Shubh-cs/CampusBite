from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.orders import OrderPublic

RefundStatus = Literal["PENDING", "APPROVED", "REJECTED"]
RefundDecisionStatus = Literal["APPROVED", "REJECTED"]


class RefundRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RefundDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RefundDecisionStatus


class RefundRequestPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    customer_id: int
    reason: str
    status: RefundStatus
    reviewed_by_id: int | None
    created_at: datetime
    reviewed_at: datetime | None


class RefundCustomerPublic(BaseModel):
    id: int
    full_name: str
    email: str


class OwnerRefundRequestPublic(RefundRequestPublic):
    order: OrderPublic
    customer: RefundCustomerPublic


class PaginatedRefundRequests(BaseModel):
    items: list[OwnerRefundRequestPublic]
    page: int
    page_size: int
    total: int
