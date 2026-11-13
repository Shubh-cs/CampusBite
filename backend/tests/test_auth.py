from datetime import datetime, timedelta, timezone

import jwt
import pytest
from pydantic import SecretStr
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import JWT_ALGORITHM, hash_password
from app.models import User
from tests.conftest import TEST_JWT_SECRET, TEST_PASSWORD


def test_customer_registration_normalizes_email_and_never_returns_hash(client, db_session):
    response = client.post(
        "/auth/register",
        json={
            "full_name": "  Ada Campus  ",
            "email": "  Ada@Example.Test ",
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "ada@example.test"
    assert body["user"]["full_name"] == "Ada Campus"
    assert body["user"]["role"] == "CUSTOMER"
    assert "password_hash" not in body
    assert "password" not in body

    user = db_session.query(User).filter_by(email="ada@example.test").one()
    assert user.role == "CUSTOMER"
    assert user.password_hash != TEST_PASSWORD


def test_registration_rejects_client_selected_role(client):
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Attempted Owner",
            "email": "attempt@example.test",
            "password": TEST_PASSWORD,
            "role": "OWNER",
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("email", ["bad-email", "   "])
def test_registration_rejects_invalid_email(client, email):
    response = client.post(
        "/auth/register",
        json={"full_name": "Test Person", "email": email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 422


def test_registration_rejects_password_over_bcrypt_limit(client):
    response = client.post(
        "/auth/register",
        json={"full_name": "Test Person", "email": "long@example.test", "password": "é" * 37},
    )
    assert response.status_code == 422


def test_registration_rejects_duplicate_email_case_insensitively(client):
    payload = {"full_name": "First User", "email": "same@example.test", "password": TEST_PASSWORD}
    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json={**payload, "email": "SAME@example.test"})

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.parametrize("role", ["CUSTOMER", "OWNER", "DELIVERY_PARTNER"])
def test_all_roles_can_login(client, role_users, role):
    response = client.post(
        "/auth/login",
        json={"email": role_users[role].email, "password": TEST_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == role
    assert "password_hash" not in body
    assert "password" not in body


def test_login_uses_generic_error_for_unknown_email_and_wrong_password(client, role_users):
    unknown = client.post(
        "/auth/login",
        json={"email": "absent@example.test", "password": TEST_PASSWORD},
    )
    wrong = client.post(
        "/auth/login",
        json={"email": role_users["CUSTOMER"].email, "password": "incorrect-password"},
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_inactive_user_cannot_login(client, db_session):
    user = User(
        full_name="Inactive User",
        email="inactive@example.test",
        password_hash=hash_password(TEST_PASSWORD),
        role="CUSTOMER",
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": TEST_PASSWORD},
    )

    assert response.status_code == 401


def test_login_fails_closed_when_jwt_secret_is_unconfigured(client, role_users, monkeypatch):
    monkeypatch.setattr(
        settings,
        "jwt_secret_key",
        SecretStr("replace-with-a-long-random-development-secret"),
    )

    response = client.post(
        "/auth/login",
        json={"email": role_users["CUSTOMER"].email, "password": TEST_PASSWORD},
    )

    assert response.status_code == 503
    assert "secure JWT_SECRET_KEY" in response.json()["detail"]


def test_me_requires_valid_token_and_returns_current_database_user(client, role_users):
    login = client.post(
        "/auth/login",
        json={"email": role_users["OWNER"].email, "password": TEST_PASSWORD},
    )
    token = login.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    missing_token = client.get("/auth/me")
    tampered_token = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.value"})

    assert response.status_code == 200
    assert response.json()["role"] == "OWNER"
    assert "password_hash" not in response.json()
    assert missing_token.status_code == 401
    assert tampered_token.status_code == 401


def test_expired_token_is_rejected(client, role_users):
    expired = jwt.encode(
        {
            "sub": str(role_users["CUSTOMER"].id),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_me_rejects_user_deactivated_after_token_was_issued(client, db_session, role_users):
    user = role_users["CUSTOMER"]
    login = client.post(
        "/auth/login",
        json={"email": user.email, "password": TEST_PASSWORD},
    )
    user.is_active = False
    db_session.commit()

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 401


def test_database_rejects_unrecognized_role(db_session):
    db_session.add(
        User(
            full_name="Invalid Role",
            email="invalid-role@example.test",
            password_hash=hash_password(TEST_PASSWORD),
            role="ADMIN",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
