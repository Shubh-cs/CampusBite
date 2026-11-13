import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
UserRole = Literal["CUSTOMER", "OWNER", "DELIVERY_PARTNER"]


class _EmailInput(BaseModel):
    email: str = Field(min_length=3, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Enter a valid email address.")
        normalized = value.strip().lower()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class CustomerRegistrationRequest(_EmailInput):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8)

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Enter a valid name.")
        return value.strip()

    @field_validator("password")
    @classmethod
    def validate_bcrypt_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes.")
        return value


class LoginRequest(_EmailInput):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1)


class UserPublic(BaseModel):
    id: int
    full_name: str
    email: str
    role: UserRole


class RegistrationResponse(BaseModel):
    user: UserPublic


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserPublic
