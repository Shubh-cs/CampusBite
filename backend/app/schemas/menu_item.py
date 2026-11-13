from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class MenuItemFields(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    category: str = Field(min_length=1, max_length=80)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    image_url: HttpUrl | None = None

    @field_validator("name", "category", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class MenuItemCreate(MenuItemFields):
    model_config = ConfigDict(extra="forbid")


class MenuItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    category: str | None = Field(default=None, min_length=1, max_length=80)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    image_url: HttpUrl | None = None
    is_available: bool | None = None

    @field_validator("name", "category", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one menu field to update.")
        for field_name in ("name", "category", "price", "is_available"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class MenuItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    category: str
    price: Decimal
    image_url: str | None
    is_available: bool


class PaginatedMenuItems(BaseModel):
    items: list[MenuItemPublic]
    page: int
    page_size: int
    total: int
