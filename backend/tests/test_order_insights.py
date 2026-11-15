import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.core.config import settings
from app.models import MenuItem, Order, OrderItem, PaymentLedgerEntry, Restaurant, User
from app.schemas.order_insights import OrderInsightsQuestion
from app.services.order_insights import _load_verified_facts, answer_customer_order_question
from tests.conftest import TEST_PASSWORD


def _login_headers(client, user):
    response = client.post("/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_order(
    db_session,
    customer,
    owner,
    *,
    status="DELIVERED",
    item_name="Campus Bowl",
    price="25.00",
    quantity=1,
    placed_at=None,
    payment_created_at=None,
):
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
        placed_at=placed_at or datetime(2026, 11, 14, 12, tzinfo=timezone.utc),
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
    payment_values = {
        "order_id": order.id,
        "entry_type": "PAYMENT",
        "status": "MOCK_PAID",
        "amount": order.total_amount,
    }
    if payment_created_at is not None:
        payment_values["created_at"] = payment_created_at
    db_session.add(PaymentLedgerEntry(**payment_values))
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
    assert body["verified_facts"]["weekly_payment_activity"]["net_payment_activity"] == "0.00"
    assert body["verified_facts"]["outstanding_orders"] == []
    assert body["answer"] is None
    assert "orders yet" in body["notice"].lower()


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


def test_weekly_payment_activity_uses_monday_kolkata_boundary_and_excludes_current_time(
    db_session, role_users
):
    customer = role_users["CUSTOMER"]
    owner = role_users["OWNER"]
    as_of = datetime(2026, 11, 18, 4, 0, tzinfo=timezone.utc)
    local_monday_start_utc = datetime(2026, 11, 15, 18, 30, tzinfo=timezone.utc)

    _make_order(
        db_session,
        customer,
        owner,
        item_name="Before week",
        price="20.00",
        payment_created_at=local_monday_start_utc - timedelta(seconds=1),
    )
    _make_order(
        db_session,
        customer,
        owner,
        item_name="At week start",
        price="30.00",
        payment_created_at=local_monday_start_utc,
    )
    _make_order(
        db_session,
        customer,
        owner,
        item_name="At current time",
        price="40.00",
        payment_created_at=as_of,
    )

    facts = _load_verified_facts(db_session, customer.id, now=as_of)
    weekly = facts.weekly_payment_activity

    assert weekly.period_start == datetime(2026, 11, 16, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert weekly.period_end == datetime(2026, 11, 18, 9, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert weekly.gross_successful_payments == Decimal("30.00")
    assert weekly.voided_amounts == Decimal("0.00")
    assert weekly.refunded_amounts == Decimal("0.00")
    assert weekly.net_payment_activity == Decimal("30.00")
    assert facts.gross_successful_payments == Decimal("90.00")


def test_weekly_refunds_and_voids_reduce_the_week_the_ledger_entries_were_posted(
    db_session, role_users
):
    customer = role_users["CUSTOMER"]
    owner = role_users["OWNER"]
    as_of = datetime(2026, 11, 18, 4, 0, tzinfo=timezone.utc)
    posted_this_week = datetime(2026, 11, 17, 5, 0, tzinfo=timezone.utc)
    posted_last_week = datetime(2026, 11, 14, 5, 0, tzinfo=timezone.utc)

    _make_order(
        db_session,
        customer,
        owner,
        item_name="Paid this week",
        price="100.00",
        payment_created_at=posted_this_week,
    )
    cancelled = _make_order(
        db_session,
        customer,
        owner,
        status="CANCELLED",
        item_name="Voided this week",
        price="40.00",
        payment_created_at=posted_this_week,
    )
    refunded = _make_order(
        db_session,
        customer,
        owner,
        status="REFUNDED",
        item_name="Refund posted this week",
        price="60.00",
        payment_created_at=posted_last_week,
    )
    db_session.add_all(
        [
            PaymentLedgerEntry(
                order_id=cancelled.id,
                entry_type="VOIDED",
                status="VOIDED",
                amount=Decimal("40.00"),
                created_at=posted_this_week,
            ),
            PaymentLedgerEntry(
                order_id=refunded.id,
                entry_type="REFUND",
                status="REFUNDED",
                amount=Decimal("60.00"),
                created_at=posted_this_week,
            ),
        ]
    )
    db_session.commit()

    facts = _load_verified_facts(db_session, customer.id, now=as_of)
    weekly = facts.weekly_payment_activity

    assert weekly.gross_successful_payments == Decimal("140.00")
    assert weekly.voided_amounts == Decimal("40.00")
    assert weekly.refunded_amounts == Decimal("60.00")
    assert weekly.net_payment_activity == Decimal("40.00")
    assert facts.gross_successful_payments == Decimal("200.00")
    assert facts.voided_amounts == Decimal("40.00")
    assert facts.refunded_amounts == Decimal("60.00")
    assert facts.net_spending == Decimal("100.00")
    assert "week their ledger entries are posted" in weekly.accounting_note


def test_outstanding_orders_include_older_active_orders_exclude_terminal_and_other_customer_orders(
    db_session, role_users
):
    customer = role_users["CUSTOMER"]
    owner = role_users["OWNER"]
    as_of = datetime(2026, 11, 18, 4, 0, tzinfo=timezone.utc)
    active_statuses = [
        "PLACED",
        "ACCEPTED",
        "PREPARING",
        "READY",
        "ASSIGNED",
        "OUT_FOR_DELIVERY",
    ]
    active_orders = []
    for index, order_status in enumerate(active_statuses):
        active_orders.append(
            _make_order(
                db_session,
                customer,
                owner,
                status=order_status,
                item_name=f"Active {order_status}",
                placed_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
                if index == 0
                else datetime(2026, 11, 1, index, tzinfo=timezone.utc),
            )
        )

    for index in range(20):
        _make_order(
            db_session,
            customer,
            owner,
            item_name=f"Recent delivered {index}",
            placed_at=datetime(2026, 11, 14, 12, index, tzinfo=timezone.utc),
        )

    cancelled = _make_order(
        db_session,
        customer,
        owner,
        status="CANCELLED",
        item_name="Terminal cancelled",
        placed_at=datetime(2026, 11, 15, 12, tzinfo=timezone.utc),
    )
    refunded = _make_order(
        db_session,
        customer,
        owner,
        status="REFUNDED",
        item_name="Terminal refunded",
        placed_at=datetime(2026, 11, 15, 13, tzinfo=timezone.utc),
    )
    other_customer = User(
        full_name="Other Insights Customer",
        email="other-insights-customer@example.test",
        password_hash="test-only-unused-hash",
        role="CUSTOMER",
    )
    db_session.add(other_customer)
    db_session.flush()
    other_order = _make_order(
        db_session,
        other_customer,
        owner,
        status="PLACED",
        item_name="Another customer's order",
        placed_at=datetime(2026, 11, 16, 12, tzinfo=timezone.utc),
    )

    facts = _load_verified_facts(db_session, customer.id, now=as_of)
    outstanding_ids = {order.order_id for order in facts.outstanding_orders}
    recent_ids = {order.order_id for order in facts.recent_orders}

    assert outstanding_ids == {order.id for order in active_orders}
    assert active_orders[0].id not in recent_ids
    assert cancelled.id not in outstanding_ids
    assert refunded.id not in outstanding_ids
    assert other_order.id not in outstanding_ids


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


def test_missing_openai_configuration_returns_facts_and_safe_notice(client, db_session, role_users, monkeypatch):
    _make_order(db_session, role_users["CUSTOMER"], role_users["OWNER"])
    monkeypatch.setattr(settings, "openai_api_key", None)
    response = client.post(
        "/insights/orders", headers=_login_headers(client, role_users["CUSTOMER"]), json={"question": "Summarize"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] is None
    assert "not configured" in body["notice"].lower()
    assert body["verified_facts"]["order_count"] == 1


@pytest.mark.parametrize(
    "failure_kind",
    [
        "rate_limit",
        "timeout",
        "connection",
        "api",
    ],
)
def test_provider_failures_have_safe_user_messages(
    client, db_session, role_users, monkeypatch, failure_kind
):
    _make_order(db_session, role_users["CUSTOMER"], role_users["OWNER"])
    _install_mock_openai(monkeypatch, failure=failure_kind)

    response = client.post(
        "/insights/orders", headers=_login_headers(client, role_users["CUSTOMER"]), json={"question": "Summarize"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] is None
    assert "temporarily unavailable" in body["notice"].lower()
    assert body["verified_facts"]["order_count"] == 1
    assert "provider detail" not in body["notice"]
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
    assert body["notice"] is None
    assert body["verified_facts"]["order_count"] == 1
    assert body["verified_facts"]["gross_successful_payments"] == "31.00"
    assert body["verified_facts"]["net_spending"] == "31.00"


def test_empty_provider_response_returns_facts_and_safe_notice(client, db_session, role_users, monkeypatch):
    _make_order(db_session, role_users["CUSTOMER"], role_users["OWNER"])
    _install_mock_openai(monkeypatch, answer="   ")

    response = client.post(
        "/insights/orders", headers=_login_headers(client, role_users["CUSTOMER"]), json={"question": "Summarize"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] is None
    assert "temporarily unavailable" in body["notice"].lower()
    assert body["verified_facts"]["order_count"] == 1


def test_unrelated_http_exception_from_generation_propagates(db_session, role_users, monkeypatch):
    customer = role_users["CUSTOMER"]
    _make_order(db_session, customer, role_users["OWNER"])
    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-key-not-real"))
    monkeypatch.setattr(settings, "openai_model", "test-model")

    def raise_http_error(*_args):
        raise HTTPException(status_code=418, detail="unrelated application error")

    monkeypatch.setattr("app.services.order_insights._generate_explanation", raise_http_error)
    with pytest.raises(HTTPException) as error:
        answer_customer_order_question(
            db_session, customer.id, OrderInsightsQuestion(question="Summarize")
        )
    assert error.value.status_code == 418
    assert error.value.detail == "unrelated application error"


def test_unexpected_exception_from_generation_propagates(db_session, role_users, monkeypatch):
    customer = role_users["CUSTOMER"]
    _make_order(db_session, customer, role_users["OWNER"])
    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-key-not-real"))
    monkeypatch.setattr(settings, "openai_model", "test-model")

    def raise_unexpected_error(*_args):
        raise RuntimeError("unexpected application failure")

    monkeypatch.setattr("app.services.order_insights._generate_explanation", raise_unexpected_error)
    with pytest.raises(RuntimeError, match="unexpected application failure"):
        answer_customer_order_question(
            db_session, customer.id, OrderInsightsQuestion(question="Summarize")
        )
