"""Opt-in backend integration checks against an isolated PostgreSQL DB.

Set TEST_DATABASE_URL explicitly to the disposable Stage 2D database on
127.0.0.1:55432. This module never reads DATABASE_URL or loads settings from
.env to choose its database, and it never runs migrations or creates tables.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from typing import Any
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import JWT_ALGORITHM, hash_password
from app.database import get_db
from app.models import MenuItem, Order, PaymentLedgerEntry, Restaurant, User
from tests.conftest import TEST_JWT_SECRET, TEST_PASSWORD, auth_test_app


EXPECTED_REVISION = "0002_user_role_check"
TEST_DATABASE_PORT = 55432
TEST_DATABASE_NAME = "campusbite_stage2d"
ROLE_PATHS = {
    "CUSTOMER": "/__test__/roles/customer",
    "OWNER": "/__test__/roles/owner",
    "DELIVERY_PARTNER": "/__test__/roles/delivery_partner",
}

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to opt in to isolated PostgreSQL integration tests.",
)


def _require(condition: bool, message: str) -> None:
    """Fail with a fixed message so response credentials are never shown."""
    if not condition:
        pytest.fail(message, pytrace=False)


@pytest.fixture(scope="session")
def postgres_test_run_id() -> str:
    run_id = uuid4().hex
    print(f"PostgreSQL integration test run id: {run_id}")
    return run_id


def _test_email(run_id: str, label: str) -> str:
    return f"stage2d-{run_id}-{label}@example.test"


@pytest.fixture
def postgres_session():
    # Deliberately read only this explicit process environment variable. Do not
    # fall back to application settings, DATABASE_URL, or a dotenv file.
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to opt in to isolated PostgreSQL integration tests.")

    try:
        parsed_url = make_url(database_url)
    except Exception:
        pytest.fail("TEST_DATABASE_URL is not a valid SQLAlchemy URL.", pytrace=False)

    if (
        parsed_url.get_backend_name() != "postgresql"
        or parsed_url.username != "campusbite_test"
        or parsed_url.host not in {"127.0.0.1", "localhost"}
        or parsed_url.port != TEST_DATABASE_PORT
        or parsed_url.database != TEST_DATABASE_NAME
    ):
        pytest.fail(
            "TEST_DATABASE_URL must target the isolated campusbite_stage2d PostgreSQL "
            "database on loopback port 55432.",
            pytrace=False,
        )

    engine = create_engine(database_url, pool_pre_ping=True)
    connection = None
    transaction = None
    session = None
    try:
        try:
            connection = engine.connect()
        except SQLAlchemyError as exc:
            pytest.fail(
                f"Could not connect to TEST_DATABASE_URL ({type(exc).__name__}); "
                "connection details were suppressed.",
                pytrace=False,
            )

        transaction = connection.begin()
        try:
            revisions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        except SQLAlchemyError as exc:
            pytest.fail(
                f"Could not verify the PostgreSQL Alembic revision ({type(exc).__name__}); "
                "connection details were suppressed.",
                pytrace=False,
            )

        _require(
            revisions == [EXPECTED_REVISION],
            "The PostgreSQL test database must already be at Alembic revision "
            "0002_user_role_check. Tests do not apply migrations.",
        )

        session = Session(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        yield session
    finally:
        if session is not None:
            session.close()
        if transaction is not None and transaction.is_active:
            transaction.rollback()
        if connection is not None:
            connection.close()
        engine.dispose()


@pytest.fixture
def postgres_client(postgres_session, monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret_key", SecretStr(TEST_JWT_SECRET))

    def override_get_db():
        yield postgres_session

    auth_test_app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(auth_test_app) as test_client:
            yield test_client
    finally:
        auth_test_app.dependency_overrides.clear()


@pytest.fixture
def postgres_role_users(postgres_session, postgres_test_run_id):
    users = {}
    for role in ("CUSTOMER", "OWNER", "DELIVERY_PARTNER"):
        user = User(
            full_name=f"Stage 2D {role.title()}",
            email=_test_email(postgres_test_run_id, role.lower()),
            password_hash=hash_password(TEST_PASSWORD),
            role=role,
        )
        postgres_session.add(user)
        users[role] = user
    postgres_session.commit()
    return users


def _response_json(response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        pytest.fail("The authentication API returned a non-JSON response.", pytrace=False)
    _require(isinstance(payload, dict), "The authentication API returned an unexpected response shape.")
    return payload


def _login(client: TestClient, email: str) -> tuple[dict[str, Any], str]:
    response = client.post("/auth/login", json={"email": email, "password": TEST_PASSWORD})
    _require(response.status_code == 200, "PostgreSQL-backed login did not succeed.")
    payload = _response_json(response)
    token = payload.get("access_token")
    _require(isinstance(token, str) and bool(token), "Login did not return an access token.")
    _require("password_hash" not in payload and "password" not in payload, "Login exposed a password field.")
    return payload, token


@pytest.mark.usefixtures("postgres_role_users")
def test_postgres_registration_login_and_me_do_not_expose_password_hash(
    postgres_client, postgres_test_run_id
):
    registration_email = _test_email(postgres_test_run_id, "registration")
    registration = postgres_client.post(
        "/auth/register",
        json={
            "full_name": "Postgres Integration Customer",
            "email": registration_email,
            "password": TEST_PASSWORD,
        },
    )
    _require(registration.status_code == 201, "PostgreSQL-backed customer registration failed.")
    registration_payload = _response_json(registration)
    registered_user = registration_payload.get("user", {})
    _require(registered_user.get("role") == "CUSTOMER", "Registration did not create a CUSTOMER account.")
    _require(
        "password_hash" not in registration_payload and "password" not in registration_payload,
        "Registration exposed a password field.",
    )

    login_payload, token = _login(postgres_client, registration_email)
    _require(login_payload.get("user", {}).get("role") == "CUSTOMER", "Customer login returned the wrong role.")

    me_response = postgres_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    _require(me_response.status_code == 200, "PostgreSQL-backed /auth/me rejected a valid token.")
    me_payload = _response_json(me_response)
    _require(me_payload.get("role") == "CUSTOMER", "/auth/me returned the wrong current database role.")
    _require(
        "password_hash" not in me_payload and "password" not in me_payload,
        "/auth/me exposed a password field.",
    )


def test_postgres_registration_rejects_client_selected_privileged_role(
    postgres_client, postgres_test_run_id
):
    response = postgres_client.post(
        "/auth/register",
        json={
            "full_name": "Stage 2D Role Escalation Attempt",
            "email": _test_email(postgres_test_run_id, "role-escalation"),
            "password": TEST_PASSWORD,
            "role": "OWNER",
        },
    )
    _require(response.status_code == 422, "Registration accepted a client-selected privileged role.")


@pytest.mark.parametrize("role", ["CUSTOMER", "OWNER", "DELIVERY_PARTNER"])
def test_postgres_login_and_allowed_role_route(postgres_client, postgres_role_users, role):
    payload, token = _login(postgres_client, postgres_role_users[role].email)
    _require(payload.get("user", {}).get("role") == role, "Login returned the wrong database role.")

    response = postgres_client.get(
        ROLE_PATHS[role],
        headers={"Authorization": f"Bearer {token}"},
    )
    _require(response.status_code == 200, "An allowed PostgreSQL-backed role was denied access.")
    route_payload = _response_json(response)
    _require(route_payload.get("role") == role, "The protected route returned the wrong database role.")
    _require("password_hash" not in route_payload, "A protected route exposed a password hash.")


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
def test_postgres_disallowed_roles_receive_forbidden(
    postgres_client, postgres_role_users, user_role, required_role
):
    _, token = _login(postgres_client, postgres_role_users[user_role].email)
    response = postgres_client.get(
        ROLE_PATHS[required_role],
        headers={"Authorization": f"Bearer {token}"},
    )
    _require(response.status_code == 403, "A disallowed PostgreSQL-backed role was not denied.")


def test_postgres_missing_invalid_expired_and_inactive_tokens_are_rejected(
    postgres_client, postgres_session, postgres_role_users
):
    missing = postgres_client.get("/auth/me")
    malformed = postgres_client.get("/auth/me", headers={"Authorization": "Bearer malformed.token.value"})
    _require(missing.status_code == 401, "A missing bearer token was not rejected with 401.")
    _require(malformed.status_code == 401, "A malformed bearer token was not rejected with 401.")

    expired_token = jwt.encode(
        {
            "sub": str(postgres_role_users["CUSTOMER"].id),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    expired = postgres_client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    _require(expired.status_code == 401, "An expired bearer token was not rejected with 401.")

    _, active_token = _login(postgres_client, postgres_role_users["CUSTOMER"].email)
    postgres_role_users["CUSTOMER"].is_active = False
    postgres_session.commit()
    inactive = postgres_client.get("/auth/me", headers={"Authorization": f"Bearer {active_token}"})
    _require(inactive.status_code == 401, "An inactive PostgreSQL user was not rejected with 401.")


def test_postgres_authorization_uses_current_database_role(postgres_client, postgres_session, postgres_role_users):
    customer = postgres_role_users["CUSTOMER"]
    _, token = _login(postgres_client, customer.email)
    postgres_session.execute(update(User).where(User.id == customer.id).values(role="OWNER"))
    postgres_session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    owner_route = postgres_client.get(ROLE_PATHS["OWNER"], headers=headers)
    customer_route = postgres_client.get(ROLE_PATHS["CUSTOMER"], headers=headers)
    _require(owner_route.status_code == 200, "Authorization did not use the user's current PostgreSQL role.")
    _require(customer_route.status_code == 403, "Authorization trusted a stale role after a database role change.")


def test_postgres_role_check_rejects_unsupported_role(postgres_session, postgres_test_run_id):
    postgres_session.add(
        User(
            full_name="Unsupported Role Fixture",
            email=_test_email(postgres_test_run_id, "invalid-role"),
            password_hash="non-credential-test-value",
            role="ADMIN",
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.flush()
    postgres_session.rollback()


def test_postgres_restaurant_and_menu_api_filters_availability(postgres_client, postgres_session, postgres_role_users):
    owner = postgres_role_users["OWNER"]
    restaurant = Restaurant(
        owner_id=owner.id,
        name="PostgreSQL Menu Fixture",
        description="Fixture",
        address="Test address",
    )
    postgres_session.add(restaurant)
    postgres_session.flush()
    postgres_session.add_all(
        [
            MenuItem(
                restaurant_id=restaurant.id,
                name="Available PostgreSQL Dish",
                description="Available fixture item",
                category="Mains",
                price=Decimal("125.00"),
                is_available=True,
            ),
            MenuItem(
                restaurant_id=restaurant.id,
                name="Unavailable PostgreSQL Dish",
                description="Unavailable fixture item",
                category="Mains",
                price=Decimal("150.00"),
                is_available=False,
            ),
        ]
    )
    postgres_session.flush()
    _, token = _login(postgres_client, owner.email)

    public_response = postgres_client.get(f"/restaurants/{restaurant.id}/menu-items")
    owner_response = postgres_client.get(
        "/owner/menu-items", headers={"Authorization": f"Bearer {token}"}
    )
    _require(public_response.status_code == 200, "PostgreSQL public menu request failed.")
    _require(owner_response.status_code == 200, "PostgreSQL owner menu request failed.")
    _require(
        [item["name"] for item in _response_json(public_response)["items"]]
        == ["Available PostgreSQL Dish"],
        "PostgreSQL public menu included an unavailable dish.",
    )
    _require(
        len(_response_json(owner_response)["items"]) == 2,
        "PostgreSQL owner menu did not include all availability states.",
    )


def test_postgres_order_checkout_owner_assignment_and_delivery_lifecycle(
    postgres_client, postgres_session, postgres_role_users, postgres_test_run_id
):
    owner = postgres_role_users["OWNER"]
    customer = postgres_role_users["CUSTOMER"]
    partner = postgres_role_users["DELIVERY_PARTNER"]
    restaurant = Restaurant(
        owner_id=owner.id,
        name=f"Stage 3B {postgres_test_run_id[:12]}",
        description="Order lifecycle integration fixture",
        address="Test campus address",
    )
    postgres_session.add(restaurant)
    postgres_session.flush()
    menu_item = MenuItem(
        restaurant_id=restaurant.id,
        name="Lifecycle Integration Dish",
        description="PostgreSQL lifecycle fixture",
        category="Mains",
        price=Decimal("125.50"),
        is_available=True,
    )
    postgres_session.add(menu_item)
    postgres_session.flush()

    _, customer_token = _login(postgres_client, customer.email)
    checkout = postgres_client.post(
        "/orders",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={
            "items": [{"menu_item_id": menu_item.id, "quantity": 2, "expected_unit_price": "125.50"}],
            "delivery_address": "123 Integration Road, Campus",
        },
    )
    _require(checkout.status_code == 201, "PostgreSQL-backed order checkout failed.")
    order_payload = _response_json(checkout)
    _require(order_payload.get("total_amount") == "251.00", "Checkout did not use the PostgreSQL menu price.")
    order_id = order_payload.get("id")
    _require(isinstance(order_id, int), "Checkout did not return an order identifier.")

    _, owner_token = _login(postgres_client, owner.email)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    accept = postgres_client.post(f"/owner/orders/{order_id}/accept", headers=owner_headers)
    prepare = postgres_client.patch(
        f"/owner/orders/{order_id}/status", headers=owner_headers, json={"status": "PREPARING"}
    )
    ready = postgres_client.patch(
        f"/owner/orders/{order_id}/status", headers=owner_headers, json={"status": "READY"}
    )
    _require(accept.status_code == 200 and accept.json().get("status") == "ACCEPTED", "Owner could not accept the order.")
    _require(prepare.status_code == 200 and prepare.json().get("status") == "PREPARING", "Owner preparation transition failed.")
    _require(ready.status_code == 200 and ready.json().get("status") == "READY", "Owner could not mark the order READY.")

    assignment = postgres_client.post(
        f"/owner/orders/{order_id}/assign-delivery",
        headers=owner_headers,
        json={"delivery_partner_id": partner.id},
    )
    _require(assignment.status_code == 200 and assignment.json().get("status") == "ASSIGNED", "Owner delivery assignment failed.")

    _, partner_token = _login(postgres_client, partner.email)
    partner_headers = {"Authorization": f"Bearer {partner_token}"}
    out_for_delivery = postgres_client.patch(
        f"/delivery/orders/{order_id}/status",
        headers=partner_headers,
        json={"status": "OUT_FOR_DELIVERY"},
    )
    delivered = postgres_client.patch(
        f"/delivery/orders/{order_id}/status",
        headers=partner_headers,
        json={"status": "DELIVERED"},
    )
    _require(
        out_for_delivery.status_code == 200 and out_for_delivery.json().get("status") == "OUT_FOR_DELIVERY",
        "Delivery partner could not start delivery.",
    )
    _require(delivered.status_code == 200 and delivered.json().get("status") == "DELIVERED", "Delivery partner could not complete delivery.")
    _require(delivered.json().get("delivered_at") is not None, "Delivery completion did not set delivered_at.")

    order = postgres_session.get(Order, order_id)
    _require(order is not None and order.status == "DELIVERED", "Final PostgreSQL order state was not persisted.")
    entries = postgres_session.query(PaymentLedgerEntry).filter_by(order_id=order_id).all()
    _require(
        len(entries) == 1
        and entries[0].entry_type == "PAYMENT"
        and entries[0].status == "MOCK_PAID"
        and entries[0].amount == Decimal("251.00"),
        "PostgreSQL checkout did not create the expected mock payment ledger entry.",
    )


def test_postgres_refund_approval_preserves_payment_and_allows_post_refund_review(
    postgres_client, postgres_session, postgres_role_users, postgres_test_run_id
):
    owner = postgres_role_users["OWNER"]
    customer = postgres_role_users["CUSTOMER"]
    restaurant = Restaurant(
        owner_id=owner.id,
        name=f"Review Refund {postgres_test_run_id[:12]}",
        description="Review/refund PostgreSQL fixture",
        address="Test campus address",
    )
    postgres_session.add(restaurant)
    postgres_session.flush()
    menu_item = MenuItem(
        restaurant_id=restaurant.id,
        name="Review Refund Integration Dish",
        category="Mains",
        price=Decimal("125.50"),
        is_available=True,
    )
    postgres_session.add(menu_item)
    postgres_session.flush()

    _, customer_token = _login(postgres_client, customer.email)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    checkout = postgres_client.post(
        "/orders",
        headers=customer_headers,
        json={
            "items": [{"menu_item_id": menu_item.id, "quantity": 2}],
            "delivery_address": "Review refund test address",
        },
    )
    _require(checkout.status_code == 201, "PostgreSQL review/refund fixture checkout failed.")
    order_id = _response_json(checkout).get("id")
    order = postgres_session.get(Order, order_id)
    order.status = "DELIVERED"
    order.delivered_at = datetime.now(timezone.utc)
    postgres_session.commit()

    _, owner_token = _login(postgres_client, owner.email)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    request_response = postgres_client.post(
        f"/orders/{order_id}/refund-request",
        headers=customer_headers,
        json={"reason": "PostgreSQL integration refund reason"},
    )
    _require(request_response.status_code == 201, "PostgreSQL refund request creation failed.")
    request_id = _response_json(request_response).get("id")
    owner_list = postgres_client.get("/owner/refund-requests", headers=owner_headers)
    _require(owner_list.status_code == 200, "Owner could not list PostgreSQL refund requests.")
    owner_item = _response_json(owner_list).get("items", [{}])[0]
    _require(
        owner_item.get("id") == request_id and owner_item.get("customer", {}).get("email") == customer.email,
        "PostgreSQL owner refund response did not include its scoped order/customer data.",
    )

    original = postgres_session.scalar(
        select(PaymentLedgerEntry).where(
            PaymentLedgerEntry.order_id == order_id,
            PaymentLedgerEntry.entry_type == "PAYMENT",
        )
    )
    original_values = (original.status, original.amount, original.created_at)
    approved = postgres_client.patch(
        f"/owner/refund-requests/{request_id}",
        headers=owner_headers,
        json={"status": "APPROVED"},
    )
    _require(approved.status_code == 200 and approved.json().get("status") == "APPROVED", "PostgreSQL refund approval failed.")
    postgres_session.refresh(order)
    postgres_session.refresh(original)
    entries = postgres_session.scalars(
        select(PaymentLedgerEntry)
        .where(PaymentLedgerEntry.order_id == order_id)
        .order_by(PaymentLedgerEntry.id)
    ).all()
    _require(
        order.status == "REFUNDED" and order.payment_status == "REFUNDED",
        "PostgreSQL refund approval did not update order/payment status.",
    )
    _require(
        (original.status, original.amount, original.created_at) == original_values,
        "PostgreSQL refund approval changed the original payment entry.",
    )
    _require(
        len(entries) == 2
        and entries[1].entry_type == "REFUND"
        and entries[1].status == "REFUNDED"
        and entries[1].amount == Decimal("251.00"),
        "PostgreSQL refund ledger entry did not record the full original payment.",
    )

    review = postgres_client.post(
        f"/orders/{order_id}/review",
        headers=customer_headers,
        json={"rating": 5, "comment": "Still reviewable after refund"},
    )
    _require(review.status_code == 201, "A delivered PostgreSQL order could not be reviewed after refund.")
    _require(
        postgres_client.get(f"/orders/{order_id}/review", headers=customer_headers).status_code == 200,
        "PostgreSQL customer review retrieval failed.",
    )


def test_postgres_refund_rejection_leaves_order_and_payment_unchanged(
    postgres_client, postgres_session, postgres_role_users, postgres_test_run_id
):
    owner = postgres_role_users["OWNER"]
    customer = postgres_role_users["CUSTOMER"]
    restaurant = Restaurant(
        owner_id=owner.id,
        name=f"Refund Rejection {postgres_test_run_id[:12]}",
        description="Refund rejection PostgreSQL fixture",
        address="Test campus address",
    )
    postgres_session.add(restaurant)
    postgres_session.flush()
    menu_item = MenuItem(
        restaurant_id=restaurant.id,
        name="Refund Rejection Integration Dish",
        category="Mains",
        price=Decimal("70.00"),
        is_available=True,
    )
    postgres_session.add(menu_item)
    postgres_session.flush()
    _, customer_token = _login(postgres_client, customer.email)
    _, owner_token = _login(postgres_client, owner.email)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    checkout = postgres_client.post(
        "/orders",
        headers=customer_headers,
        json={"items": [{"menu_item_id": menu_item.id, "quantity": 1}], "delivery_address": "Rejection test address"},
    )
    _require(checkout.status_code == 201, "PostgreSQL rejection fixture checkout failed.")
    order_id = _response_json(checkout).get("id")
    order = postgres_session.get(Order, order_id)
    order.status = "DELIVERED"
    order.delivered_at = datetime.now(timezone.utc)
    postgres_session.commit()
    request_response = postgres_client.post(
        f"/orders/{order_id}/refund-request",
        headers=customer_headers,
        json={"reason": "Reject this PostgreSQL test request"},
    )
    _require(request_response.status_code == 201, "PostgreSQL refund rejection fixture request failed.")
    request_id = _response_json(request_response).get("id")
    rejected = postgres_client.patch(
        f"/owner/refund-requests/{request_id}", headers=owner_headers, json={"status": "REJECTED"}
    )
    _require(rejected.status_code == 200 and rejected.json().get("status") == "REJECTED", "PostgreSQL refund rejection failed.")
    postgres_session.refresh(order)
    entries = postgres_session.scalars(
        select(PaymentLedgerEntry).where(PaymentLedgerEntry.order_id == order_id)
    ).all()
    _require(
        order.status == "DELIVERED"
        and order.payment_status == "MOCK_PAID"
        and len(entries) == 1
        and entries[0].entry_type == "PAYMENT"
        and entries[0].amount == Decimal("70.00"),
        "PostgreSQL rejection changed the order/payment or created a refund ledger entry.",
    )
