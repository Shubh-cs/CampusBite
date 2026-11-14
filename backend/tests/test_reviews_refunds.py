from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from app.models import (
    MenuItem,
    Order,
    PaymentLedgerEntry,
    RefundRequest,
    Restaurant,
    Review,
    User,
)
from tests.conftest import TEST_PASSWORD


def _headers(client, user):
    response = client.post("/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_owner_restaurant(db_session, owner, name="Review Test Restaurant"):
    restaurant = Restaurant(owner_id=owner.id, name=name, address="Campus")
    db_session.add(restaurant)
    db_session.commit()
    return restaurant


def _make_delivered_order(client, db_session, customer, owner, *, delivered=True):
    restaurant = _make_owner_restaurant(db_session, owner)
    menu_item = MenuItem(
        restaurant_id=restaurant.id,
        name="Review Test Dish",
        category="Mains",
        price=Decimal("125.00"),
        is_available=True,
    )
    db_session.add(menu_item)
    db_session.commit()
    response = client.post(
        "/orders",
        headers=_headers(client, customer),
        json={"items": [{"menu_item_id": menu_item.id, "quantity": 2}], "delivery_address": "Campus Road"},
    )
    assert response.status_code == 201
    order = db_session.get(Order, response.json()["id"])
    if delivered:
        order.status = "DELIVERED"
        order.delivered_at = datetime.now(timezone.utc)
        db_session.commit()
    return order, restaurant


def _submit_review(client, order_id, headers, *, rating=5, comment="Good meal"):
    return client.post(f"/orders/{order_id}/review", headers=headers, json={"rating": rating, "comment": comment})


def _request_refund(client, order_id, headers, reason="Food arrived cold"):
    return client.post(f"/orders/{order_id}/refund-request", headers=headers, json={"reason": reason})


def test_customer_can_review_delivered_order_and_retrieve_it(client, db_session, role_users):
    order, _ = _make_delivered_order(client, db_session, role_users["CUSTOMER"], role_users["OWNER"])
    headers = _headers(client, role_users["CUSTOMER"])

    submitted = _submit_review(client, order.id, headers, rating=4, comment="  Good meal  ")
    assert submitted.status_code == 201
    assert submitted.json()["customer_id"] == role_users["CUSTOMER"].id
    assert submitted.json()["rating"] == 4
    assert submitted.json()["comment"] == "Good meal"
    assert "password_hash" not in submitted.json()
    assert client.get(f"/orders/{order.id}/review", headers=headers).json()["id"] == submitted.json()["id"]


def test_customer_cannot_review_undelivered_order_and_rating_is_validated(client, db_session, role_users):
    order, _ = _make_delivered_order(
        client, db_session, role_users["CUSTOMER"], role_users["OWNER"], delivered=False
    )
    headers = _headers(client, role_users["CUSTOMER"])
    assert _submit_review(client, order.id, headers).status_code == 409
    assert _submit_review(client, order.id, headers, rating=6).status_code == 422
    assert db_session.scalar(select(Review.id).where(Review.order_id == order.id)) is None


def test_review_is_unique_at_api_and_database_levels(client, db_session, role_users):
    order, _ = _make_delivered_order(client, db_session, role_users["CUSTOMER"], role_users["OWNER"])
    headers = _headers(client, role_users["CUSTOMER"])
    assert _submit_review(client, order.id, headers).status_code == 201
    assert _submit_review(client, order.id, headers).status_code == 409

    db_session.add(Review(order_id=order.id, customer_id=role_users["CUSTOMER"].id, rating=3))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_delivered_order_remains_reviewable_after_refund(client, db_session, role_users):
    order, _ = _make_delivered_order(client, db_session, role_users["CUSTOMER"], role_users["OWNER"])
    customer_headers = _headers(client, role_users["CUSTOMER"])
    owner_headers = _headers(client, role_users["OWNER"])
    request = _request_refund(client, order.id, customer_headers)
    assert request.status_code == 201
    approved = client.patch(
        f"/owner/refund-requests/{request.json()['id']}",
        headers=owner_headers,
        json={"status": "APPROVED"},
    )
    assert approved.status_code == 200
    db_session.refresh(order)
    assert order.status == "REFUNDED"
    assert order.delivered_at is not None
    review = _submit_review(client, order.id, customer_headers)
    assert review.status_code == 201


def test_refund_request_requires_delivered_order_and_nonblank_reason(client, db_session, role_users):
    delivered, _ = _make_delivered_order(client, db_session, role_users["CUSTOMER"], role_users["OWNER"])
    second_owner = User(
        full_name="Second Test Owner",
        email="reviews-second-owner@example.test",
        password_hash=role_users["OWNER"].password_hash,
        role="OWNER",
    )
    db_session.add(second_owner)
    db_session.commit()
    undelivered, _ = _make_delivered_order(
        client, db_session, role_users["CUSTOMER"], second_owner, delivered=False
    )
    headers = _headers(client, role_users["CUSTOMER"])

    assert client.post(f"/orders/{delivered.id}/refund-request", headers=headers, json={}).status_code == 422
    assert client.post(
        f"/orders/{delivered.id}/refund-request", headers=headers, json={"reason": "   "}
    ).status_code == 422
    assert _request_refund(client, undelivered.id, headers).status_code == 409
    assert db_session.scalar(select(RefundRequest.id).where(RefundRequest.order_id == undelivered.id)) is None


def test_refund_request_is_unique_at_api_and_database_levels(client, db_session, role_users):
    order, _ = _make_delivered_order(client, db_session, role_users["CUSTOMER"], role_users["OWNER"])
    headers = _headers(client, role_users["CUSTOMER"])
    first = _request_refund(client, order.id, headers)
    assert first.status_code == 201
    assert first.json()["status"] == "PENDING"
    assert client.get(f"/orders/{order.id}/refund-request", headers=headers).json()["id"] == first.json()["id"]
    assert _request_refund(client, order.id, headers, "Another reason").status_code == 409

    db_session.add(
        RefundRequest(order_id=order.id, customer_id=role_users["CUSTOMER"].id, reason="duplicate", status="PENDING")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_owner_lists_only_own_refund_requests_and_customer_is_isolated(client, db_session, role_users):
    order, _ = _make_delivered_order(client, db_session, role_users["CUSTOMER"], role_users["OWNER"])
    request = _request_refund(client, order.id, _headers(client, role_users["CUSTOMER"])).json()
    second_owner = User(
        full_name="Other Owner",
        email="reviews-other-owner@example.test",
        password_hash=role_users["OWNER"].password_hash,
        role="OWNER",
    )
    db_session.add(second_owner)
    db_session.commit()
    _make_owner_restaurant(db_session, second_owner, "Other Restaurant")

    owner_list = client.get("/owner/refund-requests", headers=_headers(client, role_users["OWNER"]))
    other_owner_list = client.get("/owner/refund-requests", headers=_headers(client, second_owner))
    assert owner_list.status_code == 200
    assert owner_list.json()["total"] == 1
    assert owner_list.json()["items"][0]["customer"]["email"] == role_users["CUSTOMER"].email
    assert owner_list.json()["items"][0]["order"]["id"] == order.id
    assert other_owner_list.status_code == 200 and other_owner_list.json()["total"] == 0
    assert client.patch(
        f"/owner/refund-requests/{request['id']}",
        headers=_headers(client, second_owner),
        json={"status": "APPROVED"},
    ).status_code == 404
    assert client.get("/owner/refund-requests", headers=_headers(client, role_users["CUSTOMER"])).status_code == 403


def test_customer_cannot_read_or_create_refund_request_for_another_customer(client, db_session, role_users):
    other_customer = User(
        full_name="Other Customer",
        email="reviews-other-customer@example.test",
        password_hash=role_users["CUSTOMER"].password_hash,
        role="CUSTOMER",
    )
    db_session.add(other_customer)
    db_session.commit()
    order, _ = _make_delivered_order(client, db_session, other_customer, role_users["OWNER"])
    owner_headers = _headers(client, role_users["OWNER"])
    request = _request_refund(client, order.id, _headers(client, other_customer)).json()
    customer_headers = _headers(client, role_users["CUSTOMER"])

    assert client.get(f"/orders/{order.id}/refund-request", headers=customer_headers).status_code == 404
    assert _request_refund(client, order.id, customer_headers).status_code == 404
    assert client.patch(
        f"/owner/refund-requests/{request['id']}", headers=owner_headers, json={"status": "APPROVED"}
    ).status_code == 200


def test_refund_approval_updates_order_and_ledger_without_changing_payment(client, db_session, role_users):
    order, _ = _make_delivered_order(client, db_session, role_users["CUSTOMER"], role_users["OWNER"])
    request = _request_refund(client, order.id, _headers(client, role_users["CUSTOMER"])).json()
    original = db_session.scalar(
        select(PaymentLedgerEntry).where(
            PaymentLedgerEntry.order_id == order.id,
            PaymentLedgerEntry.entry_type == "PAYMENT",
        )
    )
    original_values = (original.status, original.amount, original.created_at)

    response = client.patch(
        f"/owner/refund-requests/{request['id']}",
        headers=_headers(client, role_users["OWNER"]),
        json={"status": "APPROVED"},
    )
    assert response.status_code == 200 and response.json()["status"] == "APPROVED"
    db_session.refresh(order)
    db_session.refresh(original)
    entries = db_session.scalars(
        select(PaymentLedgerEntry).where(PaymentLedgerEntry.order_id == order.id).order_by(PaymentLedgerEntry.id)
    ).all()
    assert order.status == "REFUNDED" and order.payment_status == "REFUNDED"
    assert (original.status, original.amount, original.created_at) == original_values
    assert [(entry.entry_type, entry.status, entry.amount) for entry in entries] == [
        ("PAYMENT", "MOCK_PAID", Decimal("250.00")),
        ("REFUND", "REFUNDED", Decimal("250.00")),
    ]
    assert client.patch(
        f"/owner/refund-requests/{request['id']}",
        headers=_headers(client, role_users["OWNER"]),
        json={"status": "APPROVED"},
    ).status_code == 409


def test_refund_rejection_changes_only_request_and_cannot_be_repeated(client, db_session, role_users):
    order, _ = _make_delivered_order(client, db_session, role_users["CUSTOMER"], role_users["OWNER"])
    request = _request_refund(client, order.id, _headers(client, role_users["CUSTOMER"])).json()
    before = db_session.scalars(
        select(PaymentLedgerEntry).where(PaymentLedgerEntry.order_id == order.id)
    ).all()
    rejected = client.patch(
        f"/owner/refund-requests/{request['id']}",
        headers=_headers(client, role_users["OWNER"]),
        json={"status": "REJECTED"},
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "REJECTED"
    db_session.refresh(order)
    after = db_session.scalars(
        select(PaymentLedgerEntry).where(PaymentLedgerEntry.order_id == order.id)
    ).all()
    assert order.status == "DELIVERED" and order.payment_status == "MOCK_PAID"
    assert [(entry.id, entry.entry_type, entry.status, entry.amount) for entry in after] == [
        (entry.id, entry.entry_type, entry.status, entry.amount) for entry in before
    ]
    assert client.patch(
        f"/owner/refund-requests/{request['id']}",
        headers=_headers(client, role_users["OWNER"]),
        json={"status": "REJECTED"},
    ).status_code == 409


def test_refund_approval_is_atomic_when_commit_fails(client, db_session, role_users):
    order, _ = _make_delivered_order(client, db_session, role_users["CUSTOMER"], role_users["OWNER"])
    request = _request_refund(client, order.id, _headers(client, role_users["CUSTOMER"])).json()

    def fail_before_commit(_session):
        raise IntegrityError("injected test failure", {}, RuntimeError("failure"))

    event.listen(db_session, "before_commit", fail_before_commit)
    try:
        response = client.patch(
            f"/owner/refund-requests/{request['id']}",
            headers=_headers(client, role_users["OWNER"]),
            json={"status": "APPROVED"},
        )
    finally:
        event.remove(db_session, "before_commit", fail_before_commit)

    db_session.refresh(order)
    saved_request = db_session.get(RefundRequest, request["id"])
    entries = db_session.scalars(
        select(PaymentLedgerEntry).where(PaymentLedgerEntry.order_id == order.id)
    ).all()
    assert response.status_code == 409
    assert order.status == "DELIVERED" and order.payment_status == "MOCK_PAID"
    assert saved_request.status == "PENDING"
    assert [(entry.entry_type, entry.status, entry.amount) for entry in entries] == [
        ("PAYMENT", "MOCK_PAID", Decimal("250.00"))
    ]


def test_refund_decision_rejects_invalid_status_and_nonpending_request(client, db_session, role_users):
    order, _ = _make_delivered_order(client, db_session, role_users["CUSTOMER"], role_users["OWNER"])
    request = _request_refund(client, order.id, _headers(client, role_users["CUSTOMER"])).json()
    headers = _headers(client, role_users["OWNER"])

    assert client.patch(
        f"/owner/refund-requests/{request['id']}", headers=headers, json={"status": "PENDING"}
    ).status_code == 422
    assert client.patch(
        f"/owner/refund-requests/{request['id']}", headers=headers, json={"status": "REJECTED"}
    ).status_code == 200
    assert client.patch(
        f"/owner/refund-requests/{request['id']}", headers=headers, json={"status": "APPROVED"}
    ).status_code == 409

