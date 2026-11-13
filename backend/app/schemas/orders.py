from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CheckoutItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    menu_item_id: int = Field(gt=0)
    quantity: int = Field(strict=True, ge=1)
    expected_unit_price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CheckoutItem] = Field(min_length=1)
    delivery_address: str = Field(min_length=1)

    @field_validator("delivery_address", mode="before")
    @classmethod
    def trim_delivery_address(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def reject_duplicate_menu_items(self):
        item_ids = [item.menu_item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Include each menu item once and set its quantity.")
        return self


OrderStatus = Literal[
    "PLACED",
    "ACCEPTED",
    "PREPARING",
    "READY",
    "ASSIGNED",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "CANCELLED",
    "REFUNDED",
]
OwnerPreparationStatus = Literal["PREPARING", "READY"]
DeliveryStatus = Literal["OUT_FOR_DELIVERY", "DELIVERED"]
DeliveryFilterStatus = Literal["ASSIGNED", "OUT_FOR_DELIVERY", "DELIVERED"]


class OwnerStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OwnerPreparationStatus


class DeliveryStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DeliveryStatus


class DeliveryAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_partner_id: int = Field(gt=0)


class OrderItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int
    item_name: str
    unit_price: Decimal
    quantity: int


class OrderPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    restaurant_id: int
    delivery_partner_id: int | None
    status: OrderStatus
    payment_status: str
    delivery_address: str
    total_amount: Decimal
    placed_at: datetime
    updated_at: datetime
    delivered_at: datetime | None
    items: list[OrderItemPublic]


class PaginatedOrders(BaseModel):
    items: list[OrderPublic]
    page: int
    page_size: int
    total: int


class DeliveryPartnerPublic(BaseModel):
    id: int
    full_name: str


def validate_date_range(placed_from: date | None, placed_to: date | None) -> None:
    if placed_from is not None and placed_to is not None and placed_from > placed_to:
        raise ValueError("placed_from must not be later than placed_to.")
