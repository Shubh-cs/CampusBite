from decimal import Decimal

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from app.models import MenuItem, Order, OrderItem, PaymentLedgerEntry, Restaurant, User
from tests.conftest import TEST_PASSWORD


def _token(client, user):
    response = client.post("/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def _make_restaurant(db_session, owner, name="Test Restaurant"):
    restaurant = Restaurant(owner_id=owner.id, name=name, address="Test address")
    db_session.add(restaurant)
    db_session.commit()
    return restaurant


def _make_item(db_session, restaurant, name="Test Dish", price="10.00", available=True):
    item = MenuItem(
        restaurant_id=restaurant.id,
        name=name,
        category="Mains",
        description=f"{name} description",
        price=Decimal(price),
        is_available=available,
    )
    db_session.add(item)
    db_session.commit()
    return item


def _checkout(client, customer, lines, address="123 Campus Road"):
    return client.post(
        "/orders",
        headers={"Authorization": f"Bearer {_token(client, customer)}"},
        json={"items": lines, "delivery_address": address},
    )


def _owner_headers(client, owner):
    return {"Authorization": f"Bearer {_token(client, owner)}"}


def _partner_headers(client, partner):
    return {"Authorization": f"Bearer {_token(client, partner)}"}


def test_checkout_uses_database_prices_and_creates_order_items_and_payment_ledger(
    client, db_session, role_users
):
    restaurant = _make_restaurant(db_session, role_users["OWNER"])
    first = _make_item(db_session, restaurant, "Soup", "125.50")
    second = _make_item(db_session, restaurant, "Rice", "80.00")

    response = _checkout(
        client,
        role_users["CUSTOMER"],
        [
            {"menu_item_id": first.id, "quantity": 2, "expected_unit_price": "125.50"},
            {"menu_item_id": second.id, "quantity": 1, "expected_unit_price": "80.00"},
        ],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PLACED"
    assert body["payment_status"] == "MOCK_PAID"
    assert body["total_amount"] == "331.00"
    assert body["delivery_address"] == "123 Campus Road"
    assert {item["item_name"] for item in body["items"]} == {"Soup", "Rice"}
    order = db_session.get(Order, body["id"])
    assert order.customer_id == role_users["CUSTOMER"].id
    assert order.restaurant_id == restaurant.id
    snapshots = db_session.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    assert {(item.item_name, item.unit_price, item.quantity) for item in snapshots} == {
        ("Soup", Decimal("125.50"), 2),
        ("Rice", Decimal("80.00"), 1),
    }
    ledger = db_session.scalars(
        select(PaymentLedgerEntry).where(PaymentLedgerEntry.order_id == order.id)
    ).all()
    assert [(entry.entry_type, entry.status, entry.amount) for entry in ledger] == [
        ("PAYMENT", "MOCK_PAID", Decimal("331.00"))
    ]


def test_order_endpoints_enforce_their_required_roles(client, role_users):
    owner_headers = _owner_headers(client, role_users["OWNER"])
    customer_headers = {"Authorization": f"Bearer {_token(client, role_users['CUSTOMER'])}"}
    partner_headers = _partner_headers(client, role_users["DELIVERY_PARTNER"])

    checkout_payload = {"items": [{"menu_item_id": 1, "quantity": 1}], "delivery_address": "Campus"}
    assert client.post("/orders", headers=owner_headers, json=checkout_payload).status_code == 403
    assert client.post("/orders", headers=partner_headers, json=checkout_payload).status_code == 403
    assert client.get("/owner/orders", headers=customer_headers).status_code == 403
    assert client.get("/delivery/orders", headers=customer_headers).status_code == 403


@pytest.mark.parametrize(
    "items",
    [[], [{"menu_item_id": 1, "quantity": 0}], [{"menu_item_id": 1, "quantity": -1}]],
)
def test_checkout_rejects_empty_cart_and_invalid_quantities(client, role_users, items):
    response = _checkout(client, role_users["CUSTOMER"], items)
    assert response.status_code == 422


def test_checkout_rejects_mixed_restaurants_and_unavailable_items_without_records(
    client, db_session, role_users
):
    first_restaurant = _make_restaurant(db_session, role_users["OWNER"])
    second_owner = User(
        full_name="Second Owner",
        email="orders-second-owner@example.test",
        password_hash=role_users["OWNER"].password_hash,
        role="OWNER",
    )
    db_session.add(second_owner)
    db_session.commit()
    second_restaurant = _make_restaurant(db_session, second_owner, "Second Restaurant")
    available = _make_item(db_session, first_restaurant, "Available")
    other_restaurant_item = _make_item(db_session, second_restaurant, "Other Restaurant")
    unavailable = _make_item(db_session, first_restaurant, "Unavailable", available=False)

    mixed = _checkout(
        client,
        role_users["CUSTOMER"],
        [{"menu_item_id": available.id, "quantity": 1}, {"menu_item_id": other_restaurant_item.id, "quantity": 1}],
    )
    unavailable_response = _checkout(
        client, role_users["CUSTOMER"], [{"menu_item_id": unavailable.id, "quantity": 1}]
    )

    assert mixed.status_code == 422
    assert unavailable_response.status_code == 409
    assert db_session.scalar(select(func.count()).select_from(Order)) == 0
    assert db_session.scalar(select(func.count()).select_from(PaymentLedgerEntry)) == 0


def test_changed_expected_price_returns_current_price_and_creates_nothing(client, db_session, role_users):
    restaurant = _make_restaurant(db_session, role_users["OWNER"])
    item = _make_item(db_session, restaurant, price="12.00")

    response = _checkout(
        client,
        role_users["CUSTOMER"],
        [{"menu_item_id": item.id, "quantity": 2, "expected_unit_price": "10.00"}],
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "PRICE_CHANGED"
    assert detail["items"][0]["current_unit_price"] == "12.00"
    assert db_session.scalar(select(func.count()).select_from(Order)) == 0
    assert db_session.scalar(select(func.count()).select_from(PaymentLedgerEntry)) == 0


def test_checkout_rolls_back_order_and_items_if_ledger_commit_fails(client, db_session, role_users):
    restaurant = _make_restaurant(db_session, role_users["OWNER"])
    item = _make_item(db_session, restaurant)

    def fail_before_commit(_session):
        raise IntegrityError("test commit failure", {}, RuntimeError("injected"))

    event.listen(db_session, "before_commit", fail_before_commit)
    try:
        response = _checkout(client, role_users["CUSTOMER"], [{"menu_item_id": item.id, "quantity": 1}])
    finally:
        event.remove(db_session, "before_commit", fail_before_commit)

    assert response.status_code == 409
    assert db_session.scalar(select(func.count()).select_from(Order)) == 0
    assert db_session.scalar(select(func.count()).select_from(OrderItem)) == 0
    assert db_session.scalar(select(func.count()).select_from(PaymentLedgerEntry)) == 0


def test_customer_history_is_private_and_cancellation_voids_mock_payment(client, db_session, role_users):
    restaurant = _make_restaurant(db_session, role_users["OWNER"])
    item = _make_item(db_session, restaurant)
    placed = _checkout(client, role_users["CUSTOMER"], [{"menu_item_id": item.id, "quantity": 1}])
    order_id = placed.json()["id"]
    other_customer = User(
        full_name="Other Customer",
        email="orders-other-customer@example.test",
        password_hash=role_users["CUSTOMER"].password_hash,
        role="CUSTOMER",
    )
    db_session.add(other_customer)
    db_session.commit()
    other_headers = {"Authorization": f"Bearer {_token(client, other_customer)}"}

    assert client.get(f"/orders/{order_id}", headers=other_headers).status_code == 404
    assert client.post(f"/orders/{order_id}/cancel", headers=other_headers).status_code == 404
    history = client.get("/orders", headers={"Authorization": f"Bearer {_token(client, role_users['CUSTOMER'])}"})
    assert history.status_code == 200
    assert [entry["id"] for entry in history.json()["items"]] == [order_id]

    cancelled = client.post(
        f"/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {_token(client, role_users['CUSTOMER'])}"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["payment_status"] == "VOIDED"
    entries = db_session.scalars(
        select(PaymentLedgerEntry).where(PaymentLedgerEntry.order_id == order_id).order_by(PaymentLedgerEntry.id)
    ).all()
    assert [(entry.entry_type, entry.status) for entry in entries] == [
        ("PAYMENT", "MOCK_PAID"),
        ("VOIDED", "VOIDED"),
    ]
    assert client.post(
        f"/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {_token(client, role_users['CUSTOMER'])}"},
    ).status_code == 409


def test_owner_lifecycle_enforces_restaurant_ownership_and_transitions(client, db_session, role_users):
    restaurant = _make_restaurant(db_session, role_users["OWNER"])
    item = _make_item(db_session, restaurant)
    order_id = _checkout(client, role_users["CUSTOMER"], [{"menu_item_id": item.id, "quantity": 1}]).json()["id"]
    owner_headers = _owner_headers(client, role_users["OWNER"])

    second_owner = User(
        full_name="Second Owner",
        email="orders-isolated-owner@example.test",
        password_hash=role_users["OWNER"].password_hash,
        role="OWNER",
    )
    db_session.add(second_owner)
    db_session.commit()
    second_owner_headers = _owner_headers(client, second_owner)

    assert client.post(f"/owner/orders/{order_id}/accept", headers=second_owner_headers).status_code == 404
    assert client.post(f"/owner/orders/{order_id}/assign-delivery", headers=owner_headers, json={"delivery_partner_id": role_users["DELIVERY_PARTNER"].id}).status_code == 409
    accepted = client.post(f"/owner/orders/{order_id}/accept", headers=owner_headers)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"
    invalid_skip = client.patch(
        f"/owner/orders/{order_id}/status", headers=owner_headers, json={"status": "READY"}
    )
    assert invalid_skip.status_code == 409
    assert client.patch(
        f"/owner/orders/{order_id}/status", headers=owner_headers, json={"status": "PREPARING"}
    ).json()["status"] == "PREPARING"
    ready = client.patch(f"/owner/orders/{order_id}/status", headers=owner_headers, json={"status": "READY"})
    assert ready.status_code == 200
    assert ready.json()["status"] == "READY"
    invalid_partner = client.post(
        f"/owner/orders/{order_id}/assign-delivery",
        headers=owner_headers,
        json={"delivery_partner_id": role_users["CUSTOMER"].id},
    )
    assert invalid_partner.status_code == 404
    assigned = client.post(
        f"/owner/orders/{order_id}/assign-delivery",
        headers=owner_headers,
        json={"delivery_partner_id": role_users["DELIVERY_PARTNER"].id},
    )
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "ASSIGNED"
    assert assigned.json()["delivery_partner_id"] == role_users["DELIVERY_PARTNER"].id


def test_delivery_partner_only_sees_and_updates_assigned_orders(client, db_session, role_users):
    restaurant = _make_restaurant(db_session, role_users["OWNER"])
    item = _make_item(db_session, restaurant)
    order_id = _checkout(client, role_users["CUSTOMER"], [{"menu_item_id": item.id, "quantity": 1}]).json()["id"]
    owner_headers = _owner_headers(client, role_users["OWNER"])
    client.post(f"/owner/orders/{order_id}/accept", headers=owner_headers)
    client.patch(f"/owner/orders/{order_id}/status", headers=owner_headers, json={"status": "PREPARING"})
    client.patch(f"/owner/orders/{order_id}/status", headers=owner_headers, json={"status": "READY"})
    client.post(
        f"/owner/orders/{order_id}/assign-delivery",
        headers=owner_headers,
        json={"delivery_partner_id": role_users["DELIVERY_PARTNER"].id},
    )

    other_partner = User(
        full_name="Other Delivery Partner",
        email="orders-other-delivery@example.test",
        password_hash=role_users["DELIVERY_PARTNER"].password_hash,
        role="DELIVERY_PARTNER",
    )
    db_session.add(other_partner)
    db_session.commit()
    other_headers = _partner_headers(client, other_partner)
    assigned_headers = _partner_headers(client, role_users["DELIVERY_PARTNER"])

    assert client.get("/delivery/orders", headers=other_headers).json()["items"] == []
    assert client.get(f"/delivery/orders/{order_id}", headers=other_headers).status_code == 404
    assert client.patch(
        f"/delivery/orders/{order_id}/status", headers=other_headers, json={"status": "OUT_FOR_DELIVERY"}
    ).status_code == 404
    out_for_delivery = client.patch(
        f"/delivery/orders/{order_id}/status", headers=assigned_headers, json={"status": "OUT_FOR_DELIVERY"}
    )
    assert out_for_delivery.status_code == 200
    assert out_for_delivery.json()["status"] == "OUT_FOR_DELIVERY"
    delivered = client.patch(
        f"/delivery/orders/{order_id}/status", headers=assigned_headers, json={"status": "DELIVERED"}
    )
    assert delivered.status_code == 200
    assert delivered.json()["status"] == "DELIVERED"
    assert delivered.json()["delivered_at"] is not None
    assert client.patch(
        f"/delivery/orders/{order_id}/status", headers=assigned_headers, json={"status": "DELIVERED"}
    ).status_code == 409
