from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RestaurantPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    address: str


class PaginatedRestaurants(BaseModel):
    items: list[RestaurantPublic]
    page: int
    page_size: int
    total: int


class RestaurantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    address: str | None = Field(default=None, min_length=1, max_length=300)

    @field_validator("name", "address", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_non_nullable_fields(self):
        for field_name in ("name", "address"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        if not self.model_fields_set:
            raise ValueError("Provide at least one restaurant field to update.")
        return self
