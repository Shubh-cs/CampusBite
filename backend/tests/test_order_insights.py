import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.models import MenuItem, Order, OrderItem, PaymentLedgerEntry, Restaurant, User
from tests.conftest import TEST_PASSWORD


def _login_headers(client, user):
    response = client.post("/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_order(db_session, customer, owner, *, status="DELIVERED", item_name="Campus Bowl", price="25.00", quantity=1):
    restaurant = db_session.query(Restaurant).filter_by(owner_id=owner.id).one_or_none()
    if restaurant is None:
        restaurant = Restaurant(owner_id=owner.id, name="Insights Cafe", address="Campus")
        db_session.add(restaurant)
        db_session.flush()
    menu = MenuItem(
        restaurant_id=restaurant.id,
        name=item_name,
        category="Mains",
        price=Decimal(price),
        is_available=True,
    )
    db_session.add(menu)
    db_session.flush()
    order = Order(
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        status=status,
        payment_status={"CANCELLED": "VOIDED", "REFUNDED": "REFUNDED"}.get(status, "MOCK_PAID"),
        delivery_address="Private address not sent to AI",
        total_amount=Decimal(price) * quantity,
        placed_at=datetime(2026, 11, 14, 12, tzinfo=timezone.utc),
    )
    order.items.append(
        OrderItem(
            menu_item_id=menu.id,
            item_name=item_name,
            unit_price=Decimal(price),
            quantity=quantity,
        )
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        PaymentLedgerEntry(
            order_id=order.id,
            entry_type="PAYMENT",
            status="MOCK_PAID",
            amount=order.total_amount,
        )
    )
    db_session.commit()
    # The current catalog value can change; insights must use the order snapshot.
    menu.price = Decimal("999.00")
    db_session.commit()
    return order


def _install_mock_openai(monkeypatch, *, answer="Here is your order summary.", failure=None):
    calls = []

    class ProviderError(Exception):
        pass

    class RateLimitError(ProviderError):
        pass

    class APITimeoutError(ProviderError):
        pass

    class APIConnectionError(ProviderError):
        pass

    class APIError(ProviderError):
        pass

    exceptions = {
        "rate_limit": RateLimitError,
        "timeout": APITimeoutError,
        "connection": APIConnectionError,
        "api": APIError,
    }
    if isinstance(failure, str):
        failure = exceptions[failure]("do not expose this provider detail or key")

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            if failure is not None:
                raise failure
            return SimpleNamespace(output_text=answer)

    class FakeClient:
        def __init__(self, **kwargs):
            calls.append({"client_options": kwargs})
            self.responses = FakeResponses()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-key-not-real"))
    monkeypatch.setattr(settings, "openai_model", "test-model")
    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(
            OpenAI=FakeClient,
            APIConnectionError=APIConnectionError,
            APIError=APIError,
            APITimeoutError=APITimeoutError,
            RateLimitError=RateLimitError,
        ),
    )
    return calls, exceptions


def test_insights_requires_customer_auth_and_rejects_other_roles(client, role_users):
    assert client.post("/insights/orders", json={"question": "Summarize"}).status_code == 401
    assert client.post(
        "/insights/orders", headers=_login_headers(client, role_users["OWNER"]), json={"question": "Summarize"}
    ).status_code == 403


def test_empty_order_history_returns_zero_verified_facts_without_provider_call(client, role_users, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", None)
    response = client.post(
        "/insights/orders",
        headers=_login_headers(client, role_users["CUSTOMER"]),
        json={"question": "Summarize my orders"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verified_facts"]["order_count"] == 0
    assert body["verified_facts"]["gross_successful_payments"] == "0.00"
    assert body["verified_facts"]["voided_amounts"] == "0.00"
    assert body["verified_facts"]["refunded_amounts"] == "0.00"
    assert body["verified_facts"]["net_spending"] == "0.00"
    assert "orders yet" in body["answer"].lower()


def test_facts_separate_paid_voided_and_refunded_amounts_without_double_counting(
    client, db_session, role_users, monkeypatch
):
    customer = role_users["CUSTOMER"]
    owner = role_users["OWNER"]
    _make_order(db_session, customer, owner, item_name="Snapshot Soup", price="100.00", quantity=1)
    _make_order(db_session, customer, owner, status="CANCELLED", item_name="Cancelled Rice", price="40.00")
    refunded = _make_order(db_session, customer, owner, status="REFUNDED", item_name="Refunded Wrap", price="60.00")
    db_session.add_all([
        PaymentLedgerEntry(order_id=db_session.query(Order).filter_by(status="CANCELLED").one().id,
                           entry_type="VOIDED", status="VOIDED", amount=Decimal("40.00")),
        PaymentLedgerEntry(order_id=refunded.id, entry_type="REFUND", status="REFUNDED", amount=Decimal("60.00")),
    ])
    db_session.commit()
    _install_mock_openai(monkeypatch)

    response = client.post(
        "/insights/orders",
        headers=_login_headers(client, customer),
        json={"question": "Summarize my spending"},
    )

    assert response.status_code == 200
    facts = response.json()["verified_facts"]
    assert facts["order_count"] == 3
    assert facts["order_counts_by_status"] == {"CANCELLED": 1, "DELIVERED": 1, "REFUNDED": 1}
    assert facts["gross_successful_payments"] == "200.00"
    assert facts["voided_amounts"] == "40.00"
    assert facts["refunded_amounts"] == "60.00"
    assert facts["net_spending"] == "100.00"
    assert facts["currency"] == "INR"
    assert facts["timezone"] == "Asia/Kolkata"
    soup = next(item for item in facts["most_ordered_items"] if item["item_name"] == "Snapshot Soup")
    assert soup["snapshot_spend"] == "100.00"
    assert soup["snapshot_spend"] != "999.00"


def test_verified_facts_are_passed_to_ai_without_other_customer_or_address_data(
    client, db_session, role_users, monkeypatch
):
    _make_order(db_session, role_users["CUSTOMER"], role_users["OWNER"], item_name="Customer A Dish")
    other = User(
        full_name="Customer B",
        email="insights-customer-b@example.test",
        password_hash=role_users["CUSTOMER"].password_hash,
        role="CUSTOMER",
    )
    db_session.add(other)
    db_session.commit()
    _make_order(db_session, other, role_users["OWNER"], item_name="Customer B Secret Dish")
    calls, _ = _install_mock_openai(monkeypatch)

    response = client.post(
        "/insights/orders",
        headers=_login_headers(client, role_users["CUSTOMER"]),
        json={"question": "What did I order?"},
    )

    assert response.status_code == 200
    provider_input = json.loads(calls[1]["input"])
    serialized = json.dumps(provider_input)
    assert "Customer A Dish" in serialized
    assert "Customer B Secret Dish" not in serialized
    assert "Private address" not in serialized
    assert provider_input["verified_facts"]["order_count"] == 1
    assert response.json()["answer"] == "Here is your order summary."


@pytest.mark.parametrize("question", ["", "   ", "x" * 501])
def test_question_validation_rejects_blank_or_excessive_input(client, role_users, question):
    response = client.post(
        "/insights/orders",
        headers=_login_headers(client, role_users["CUSTOMER"]),
        json={"question": question},
    )
    assert response.status_code == 422


def test_missing_openai_configuration_returns_safe_message(client, db_session, role_users, monkeypatch):
    _make_order(db_session, role_users["CUSTOMER"], role_users["OWNER"])
    monkeypatch.setattr(settings, "openai_api_key", None)
    response = client.post(
        "/insights/orders", headers=_login_headers(client, role_users["CUSTOMER"]), json={"question": "Summarize"}
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "AI order insights are not configured. Please try again later."


@pytest.mark.parametrize(
    ("failure_kind", "expected_status", "expected_text"),
    [
        ("rate_limit", 429, "busy"),
        ("timeout", 504, "too long"),
        ("connection", 503, "temporarily unavailable"),
        ("api", 502, "could not be generated"),
    ],
)
def test_provider_failures_have_safe_user_messages(
    client, db_session, role_users, monkeypatch, failure_kind, expected_status, expected_text
):
    _make_order(db_session, role_users["CUSTOMER"], role_users["OWNER"])
    _install_mock_openai(monkeypatch, failure=failure_kind)

    response = client.post(
        "/insights/orders", headers=_login_headers(client, role_users["CUSTOMER"]), json={"question": "Summarize"}
    )

    assert response.status_code == expected_status
    assert expected_text in response.json()["detail"]
    assert "provider detail" not in response.json()["detail"]
    assert "test-key-not-real" not in response.text


def test_ai_answer_and_verified_facts_are_returned_separately(client, db_session, role_users, monkeypatch):
    _make_order(db_session, role_users["CUSTOMER"], role_users["OWNER"], price="15.50", quantity=2)
    _install_mock_openai(monkeypatch, answer="You have one order in your history.")

    response = client.post(
        "/insights/orders", headers=_login_headers(client, role_users["CUSTOMER"]), json={"question": "How many orders?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "You have one order in your history."
    assert body["verified_facts"]["order_count"] == 1
    assert body["verified_facts"]["gross_successful_payments"] == "31.00"
    assert body["verified_facts"]["net_spending"] == "31.00"


def test_empty_provider_response_returns_safe_error(client, db_session, role_users, monkeypatch):
    _make_order(db_session, role_users["CUSTOMER"], role_users["OWNER"])
    _install_mock_openai(monkeypatch, answer="   ")

    response = client.post(
        "/insights/orders", headers=_login_headers(client, role_users["CUSTOMER"]), json={"question": "Summarize"}
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "The AI service returned an unusable response. Please retry."
