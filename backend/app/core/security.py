from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from pydantic import SecretStr

from app.core.config import settings

JWT_ALGORITHM = "HS256"
_UNSAFE_SECRET_PREFIXES = ("replace-with-", "development-only-")


class JWTConfigurationError(RuntimeError):
    """Raised when authentication has no usable signing secret."""


def _get_jwt_secret() -> str:
    configured = settings.jwt_secret_key
    secret = configured.get_secret_value().strip() if isinstance(configured, SecretStr) else ""
    if (
        len(secret.encode("utf-8")) < 32
        or secret.lower().startswith(_UNSAFE_SECRET_PREFIXES)
    ):
        raise JWTConfigurationError(
            "Set JWT_SECRET_KEY to a random secret of at least 32 bytes before using authentication."
        )
    return secret


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password must be no more than 72 UTF-8 bytes.")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        return False
    try:
        return bcrypt.checkpw(password_bytes, password_hash.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError):
        return False


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    expiry_minutes = settings.jwt_access_token_expire_minutes
    if expiry_minutes <= 0:
        raise JWTConfigurationError("JWT access-token expiry must be greater than zero.")
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=expiry_minutes),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, object]:
    return jwt.decode(
        token,
        _get_jwt_secret(),
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "iat", "exp"]},
    )
