from decimal import Decimal

import pytest

from app.core.security import hash_password
from app.models import MenuItem, Restaurant, User
from tests.conftest import TEST_PASSWORD


def _token(client, user):
    response = client.post("/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def _restaurant(db_session, owner, name="Test Kitchen"):
    restaurant = Restaurant(owner_id=owner.id, name=name, description="Test", address="Test address")
    db_session.add(restaurant)
    db_session.commit()
    return restaurant


def _menu_item(db_session, restaurant, name, price="100.00", available=True):
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


def test_public_restaurants_are_paginated_and_menu_filters_available_dishes(client, db_session, role_users):
    first = _restaurant(db_session, role_users["OWNER"], "First Kitchen")
    other_owner = User(
        full_name="Second Owner", email="second-owner@example.test", password_hash="unused", role="OWNER"
    )
    db_session.add(other_owner)
    db_session.commit()
    second = _restaurant(db_session, other_owner, "Second Kitchen")
    _menu_item(db_session, first, "Herb Pasta", "120.00")
    _menu_item(db_session, first, "Veg Bowl", "180.00")
    _menu_item(db_session, first, "Hidden Soup", "90.00", available=False)

    restaurants = client.get("/restaurants?page=1&page_size=1")
    assert restaurants.status_code == 200
    assert restaurants.json() == {
        "items": [{"id": first.id, "name": "First Kitchen", "description": "Test", "address": "Test address"}],
        "page": 1,
        "page_size": 1,
        "total": 2,
    }
    assert client.get("/restaurants?page=0").status_code == 422

    filtered = client.get(
        f"/restaurants/{first.id}/menu-items",
        params={"search": "pAsTa", "min_price": "100", "max_price": "120"},
    )
    assert filtered.status_code == 200
    assert [item["name"] for item in filtered.json()["items"]] == ["Herb Pasta"]
    assert filtered.json()["total"] == 1
    assert client.get(f"/restaurants/{first.id}/menu-items", params={"min_price": 200, "max_price": 100}).status_code == 422
    public_menu = client.get(f"/restaurants/{first.id}/menu-items").json()
    assert {item["name"] for item in public_menu["items"]} == {"Herb Pasta", "Veg Bowl"}
    assert client.get(f"/restaurants/{second.id}/menu-items").json()["items"] == []
    assert client.get("/restaurants/9999/menu-items").status_code == 404


def test_owner_can_read_update_restaurant_and_manage_menu_without_changing_ownership(client, db_session, role_users):
    restaurant = _restaurant(db_session, role_users["OWNER"])
    item = _menu_item(db_session, restaurant, "Soup", available=False)
    token = _token(client, role_users["OWNER"])
    headers = {"Authorization": f"Bearer {token}"}

    own_restaurant = client.get("/owner/restaurant", headers=headers)
    assert own_restaurant.status_code == 200
    assert own_restaurant.json()["id"] == restaurant.id
    update_restaurant = client.patch("/owner/restaurant", headers=headers, json={"name": "Updated Kitchen"})
    assert update_restaurant.status_code == 200
    assert update_restaurant.json()["name"] == "Updated Kitchen"
    assert client.patch("/owner/restaurant", headers=headers, json={"owner_id": 999}).status_code == 422

    owner_menu = client.get("/owner/menu-items", headers=headers)
    assert owner_menu.status_code == 200
    assert len(owner_menu.json()["items"]) == 1
    assert owner_menu.json()["items"][0]["is_available"] is False

    created = client.post(
        "/owner/menu-items",
        headers=headers,
        json={"name": "New Dish", "category": "Mains", "price": "12.50", "description": "Fresh"},
    )
    assert created.status_code == 201
    assert created.json()["price"] == "12.50"
    assert "restaurant_id" not in created.json()
    assert client.patch(
        f"/owner/menu-items/{item.id}", headers=headers, json={"is_available": True, "name": "Renamed Soup"}
    ).json()["name"] == "Renamed Soup"
    assert client.delete(f"/owner/menu-items/{item.id}", headers=headers).status_code == 405


def test_owner_authorization_and_cross_owner_item_access_are_enforced(client, db_session, role_users):
    restaurant = _restaurant(db_session, role_users["OWNER"])
    item = _menu_item(db_session, restaurant, "Private Item")
    customer_token = _token(client, role_users["CUSTOMER"])

    assert client.get("/owner/restaurant").status_code == 401
    assert client.get("/owner/menu-items", headers={"Authorization": f"Bearer {customer_token}"}).status_code == 403
    assert client.post("/owner/menu-items", json={}).status_code == 401

    second_owner = User(
        full_name="Another Owner",
        email="another-owner@example.test",
        password_hash=hash_password(TEST_PASSWORD),
        role="OWNER",
    )
    db_session.add(second_owner)
    db_session.commit()
    second_token = _token(client, second_owner)
    assert client.patch(
        f"/owner/menu-items/{item.id}", headers={"Authorization": f"Bearer {second_token}"}, json={"name": "Stolen"}
    ).status_code == 404
    assert client.get("/owner/restaurant", headers={"Authorization": f"Bearer {second_token}"}).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   ", "category": "Mains", "price": "10.00"},
        {"name": "Dish", "category": "Mains", "price": "0"},
        {"name": "Dish", "category": "Mains", "price": "1.001"},
        {"name": "Dish", "category": "Mains", "price": "10.00", "restaurant_id": 1},
    ],
)
def test_owner_menu_create_validation(client, role_users, db_session, payload):
    _restaurant(db_session, role_users["OWNER"])
    token = _token(client, role_users["OWNER"])
    response = client.post("/owner/menu-items", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert response.status_code == 422


def test_owner_update_requires_a_change_and_missing_owner_restaurant_is_clear(client, role_users):
    token = _token(client, role_users["OWNER"])
    headers = {"Authorization": f"Bearer {token}"}
    assert client.patch("/owner/restaurant", headers=headers, json={}).status_code == 422
    assert client.get("/owner/restaurant", headers=headers).json()["detail"] == "No restaurant is associated with this owner."
