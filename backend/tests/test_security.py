from datetime import datetime, timezone

import jwt
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.core.security import (
    JWTConfigurationError,
    create_access_token,
    hash_password,
    verify_password,
)
from tests.conftest import TEST_JWT_SECRET


def test_password_hash_is_not_plaintext_and_verifies(monkeypatch):
    password = "sample-password-123"
    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$2")
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_password_hash_rejects_more_than_bcrypt_byte_limit():
    with pytest.raises(ValueError, match="72 UTF-8 bytes"):
        hash_password("é" * 37)


def test_access_token_has_subject_and_sixty_minute_expiry(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret_key", SecretStr(TEST_JWT_SECRET))
    monkeypatch.setattr(settings, "jwt_access_token_expire_minutes", 60)
    now = datetime.now(timezone.utc).timestamp()

    payload = jwt.decode(
        create_access_token(42),
        TEST_JWT_SECRET,
        algorithms=["HS256"],
    )

    assert payload["sub"] == "42"
    assert 3590 <= payload["exp"] - now <= 3600
    assert "role" not in payload


@pytest.mark.parametrize(
    "secret",
    [None, SecretStr("short"), SecretStr("replace-with-a-long-random-development-secret")],
)
def test_access_token_refuses_missing_weak_or_placeholder_secret(monkeypatch, secret):
    monkeypatch.setattr(settings, "jwt_secret_key", secret)
    with pytest.raises(JWTConfigurationError):
        create_access_token(1)
