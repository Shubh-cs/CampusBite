from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(strict=True, ge=1, le=5)
    comment: str | None = None

    @field_validator("comment")
    @classmethod
    def trim_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ReviewPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    customer_id: int
    rating: int
    comment: str | None
    created_at: datetime
