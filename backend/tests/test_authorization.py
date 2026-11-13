from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import update

from app.core.security import JWT_ALGORITHM
from app.models import User
from tests.conftest import TEST_JWT_SECRET, TEST_PASSWORD

ROLE_PATHS = {
    "CUSTOMER": "/__test__/roles/customer",
    "OWNER": "/__test__/roles/owner",
    "DELIVERY_PARTNER": "/__test__/roles/delivery_partner",
}


@pytest.mark.parametrize("role", ["CUSTOMER", "OWNER", "DELIVERY_PARTNER"])
def test_each_role_can_access_its_allowed_route(client, role_users, role):
    login = client.post(
        "/auth/login",
        json={"email": role_users[role].email, "password": TEST_PASSWORD},
    )
    response = client.get(
        ROLE_PATHS[role],
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == role
    assert "password_hash" not in response.json()


@pytest.mark.parametrize(
    ("user_role", "required_role"),
    [
        ("CUSTOMER", "OWNER"),
        ("CUSTOMER", "DELIVERY_PARTNER"),
        ("OWNER", "CUSTOMER"),
        ("OWNER", "DELIVERY_PARTNER"),
        ("DELIVERY_PARTNER", "CUSTOMER"),
        ("DELIVERY_PARTNER", "OWNER"),
    ],
)
def test_disallowed_role_receives_403(client, role_users, user_role, required_role):
    login = client.post(
        "/auth/login",
        json={"email": role_users[user_role].email, "password": TEST_PASSWORD},
    )
    response = client.get(
        ROLE_PATHS[required_role],
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize("authorization", [None, "Bearer malformed.token.value", "Basic abc"])
def test_missing_or_malformed_token_receives_401(client, role_users, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}
    response = client.get(ROLE_PATHS["OWNER"], headers=headers)
    assert response.status_code == 401


def test_expired_token_receives_401_on_role_protected_route(client, role_users):
    expired_token = jwt.encode(
        {
            "sub": str(role_users["OWNER"].id),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    response = client.get(
        ROLE_PATHS["OWNER"],
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


def test_inactive_user_receives_401_on_role_protected_route(client, db_session, role_users):
    user = role_users["OWNER"]
    login = client.post(
        "/auth/login",
        json={"email": user.email, "password": TEST_PASSWORD},
    )
    user.is_active = False
    db_session.commit()

    response = client.get(
        ROLE_PATHS["OWNER"],
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 401


def test_database_role_change_after_token_issuance_controls_access(client, db_session, role_users):
    user = role_users["CUSTOMER"]
    login = client.post(
        "/auth/login",
        json={"email": user.email, "password": TEST_PASSWORD},
    )
    token = login.json()["access_token"]

    db_session.execute(
        update(User)
        .where(User.id == user.id)
        .values(role="OWNER"),
        execution_options={"synchronize_session": False},
    )
    db_session.commit()
    assert user.role == "CUSTOMER"  # The session still holds its stale identity-map value.

    headers = {"Authorization": f"Bearer {token}"}
    owner_access = client.get(ROLE_PATHS["OWNER"], headers=headers)
    customer_access = client.get(ROLE_PATHS["CUSTOMER"], headers=headers)

    assert owner_access.status_code == 200
    assert owner_access.json()["role"] == "OWNER"
    assert customer_access.status_code == 403


def test_token_role_claim_cannot_override_database_role(client, role_users):
    customer = role_users["CUSTOMER"]
    token_with_forged_role = jwt.encode(
        {
            "sub": str(customer.id),
            "role": "OWNER",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        TEST_JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    response = client.get(
        ROLE_PATHS["OWNER"],
        headers={"Authorization": f"Bearer {token_with_forged_role}"},
    )
    assert response.status_code == 403
