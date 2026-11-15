import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import threading

import pytest
from sqlalchemy import func, select, update

from app.models import Order, ReminderLog, Restaurant, User
from app.services.reminders import _select_candidate_orders, create_due_reminders, reminder_scheduler
from tests.conftest import TEST_PASSWORD

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def _headers(client, user):
    response = client.post("/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _restaurant(db_session, owner, name="Reminder Restaurant"):
    restaurant = Restaurant(owner_id=owner.id, name=name, address="Campus")
    db_session.add(restaurant)
    db_session.commit()
    return restaurant


def _order(db_session, customer, restaurant, *, status="PLACED", updated_at=None, total="25.00"):
    updated = updated_at or NOW - timedelta(minutes=20)
    order = Order(
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        status=status,
        payment_status="MOCK_PAID",
        delivery_address="Private delivery address",
        total_amount=Decimal(total),
        placed_at=updated - timedelta(minutes=3),
        updated_at=updated,
    )
    db_session.add(order)
    db_session.commit()
    return order


def _count_reminders(db_session):
    return db_session.scalar(select(func.count()).select_from(ReminderLog))


def test_placed_and_accepted_orders_older_than_15_minutes_qualify(db_session, role_users):
    restaurant = _restaurant(db_session, role_users["OWNER"])
    placed = _order(db_session, role_users["CUSTOMER"], restaurant, status="PLACED")
    accepted = _order(db_session, role_users["CUSTOMER"], restaurant, status="ACCEPTED")

    created = create_due_reminders(db_session, now=NOW)

    assert created == 2
    reminders = db_session.scalars(select(ReminderLog).order_by(ReminderLog.order_id)).all()
    assert [reminder.order_id for reminder in reminders] == [placed.id, accepted.id]


def test_exact_boundary_newer_and_other_statuses_do_not_qualify(db_session, role_users):
    restaurant = _restaurant(db_session, role_users["OWNER"])
    boundary = _order(
        db_session,
        role_users["CUSTOMER"],
        restaurant,
        status="PLACED",
        updated_at=NOW - timedelta(minutes=15),
    )
    newer = _order(
        db_session,
        role_users["CUSTOMER"],
        restaurant,
        status="ACCEPTED",
        updated_at=NOW - timedelta(minutes=14),
    )
    preparing = _order(
        db_session,
        role_users["CUSTOMER"],
        restaurant,
        status="PREPARING",
        updated_at=NOW - timedelta(hours=1),
    )

    assert create_due_reminders(db_session, now=NOW) == 0
    assert _count_reminders(db_session) == 0
    assert [boundary.status, newer.status, preparing.status] == ["PLACED", "ACCEPTED", "PREPARING"]


def test_owner_and_restaurant_are_derived_and_orders_are_not_modified(db_session, role_users):
    restaurant = _restaurant(db_session, role_users["OWNER"])
    order = _order(db_session, role_users["CUSTOMER"], restaurant)
    original_updated_at = order.updated_at
    original_status = order.status

    assert create_due_reminders(db_session, now=NOW) == 1

    reminder = db_session.scalar(select(ReminderLog).where(ReminderLog.order_id == order.id))
    db_session.refresh(order)
    assert reminder.restaurant_id == restaurant.id
    assert reminder.owner_id == role_users["OWNER"].id
    refreshed_updated_at = order.updated_at
    if refreshed_updated_at.tzinfo is None:
        refreshed_updated_at = refreshed_updated_at.replace(tzinfo=timezone.utc)
    assert refreshed_updated_at == original_updated_at
    assert order.status == original_status


def test_repeated_checks_are_idempotent_and_other_orders_continue(db_session, role_users):
    restaurant = _restaurant(db_session, role_users["OWNER"])
    first = _order(db_session, role_users["CUSTOMER"], restaurant)
    second = _order(db_session, role_users["CUSTOMER"], restaurant, status="ACCEPTED")
    _order(
        db_session,
        role_users["CUSTOMER"],
        restaurant,
        status="READY",
        updated_at=NOW - timedelta(hours=1),
    )

    assert create_due_reminders(db_session, now=NOW) == 2
    assert create_due_reminders(db_session, now=NOW + timedelta(minutes=1)) == 0
    assert _count_reminders(db_session) == 2
    assert set(db_session.scalars(select(ReminderLog.order_id)).all()) == {first.id, second.id}


@pytest.mark.parametrize(
    ("new_status", "new_updated_at"),
    [
        ("PREPARING", NOW - timedelta(minutes=20)),
        ("PLACED", NOW - timedelta(minutes=5)),
    ],
    ids=["status-changed", "became-too-recent"],
)
def test_rechecks_candidate_after_concurrent_order_change(
    db_session, role_users, monkeypatch, new_status, new_updated_at
):
    restaurant = _restaurant(db_session, role_users["OWNER"])
    order = _order(db_session, role_users["CUSTOMER"], restaurant)
    original_select_candidates = _select_candidate_orders

    def select_then_change_order(session, cutoff, existing_reminder):
        candidates = original_select_candidates(session, cutoff, existing_reminder)
        assert any(candidate_id == order.id for candidate_id, _ in candidates)
        # Simulate a lifecycle endpoint committing after candidate selection but
        # before the reminder service locks and re-reads the order.
        session.execute(
            update(Order)
            .where(Order.id == order.id)
            .values(status=new_status, updated_at=new_updated_at)
        )
        session.commit()
        return candidates

    monkeypatch.setattr("app.services.reminders._select_candidate_orders", select_then_change_order)

    assert create_due_reminders(db_session, now=NOW) == 0
    assert _count_reminders(db_session) == 0


def test_owner_reminders_are_scoped_authorized_and_paginated(client, db_session, role_users):
    owner = role_users["OWNER"]
    restaurant = _restaurant(db_session, owner)
    own_orders = [_order(db_session, role_users["CUSTOMER"], restaurant) for _ in range(12)]

    other_owner = User(
        full_name="Other Owner",
        email="reminders-other-owner@example.test",
        password_hash=owner.password_hash,
        role="OWNER",
    )
    db_session.add(other_owner)
    db_session.commit()
    other_restaurant = _restaurant(db_session, other_owner, "Other Reminder Restaurant")
    other_order = _order(db_session, role_users["CUSTOMER"], other_restaurant)
    assert create_due_reminders(db_session, now=NOW) == 13
    inconsistent_order = _order(
        db_session,
        role_users["CUSTOMER"],
        other_restaurant,
        status="PLACED",
        updated_at=NOW - timedelta(minutes=2),
    )
    db_session.add(
        ReminderLog(
            order_id=inconsistent_order.id,
            restaurant_id=restaurant.id,
            owner_id=owner.id,
        )
    )
    db_session.commit()

    owner_headers = _headers(client, owner)
    first_page = client.get("/owner/reminders", headers=owner_headers)
    assert first_page.status_code == 200
    body = first_page.json()
    assert body["page"] == 1 and body["page_size"] == 10 and body["total"] == 12
    assert len(body["items"]) == 10
    assert all(item["order"]["customer"]["full_name"] == role_users["CUSTOMER"].full_name for item in body["items"])
    assert "delivery_address" not in body["items"][0]["order"]
    assert "email" not in body["items"][0]["order"]["customer"]

    second_page = client.get("/owner/reminders?page=2", headers=owner_headers)
    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 2
    assert {item["order_id"] for item in second_page.json()["items"]} <= {order.id for order in own_orders}

    other_page = client.get("/owner/reminders", headers=_headers(client, other_owner))
    assert other_page.status_code == 200
    assert other_page.json()["total"] == 1
    assert other_page.json()["items"][0]["order_id"] == other_order.id
    assert client.get("/owner/reminders", headers=_headers(client, role_users["CUSTOMER"])).status_code == 403
    assert client.get("/owner/reminders", headers=_headers(client, role_users["DELIVERY_PARTNER"])).status_code == 403
    assert client.get("/owner/reminders").status_code == 401


def test_owner_reminders_validate_pagination(client, role_users):
    headers = _headers(client, role_users["OWNER"])
    assert client.get("/owner/reminders?page=0", headers=headers).status_code == 422
    assert client.get("/owner/reminders?page_size=101", headers=headers).status_code == 422


def test_scheduler_runs_immediately_and_repeats_every_60_seconds(monkeypatch):
    async def scenario():
        stop_event = asyncio.Event()
        calls = []
        intervals = []

        def check():
            calls.append("checked")

        async def fake_wait(event, interval):
            intervals.append(interval)
            if len(intervals) == 2:
                event.set()

        monkeypatch.setattr("app.services.reminders._wait_for_next_check", fake_wait)
        await reminder_scheduler(stop_event, check=check)
        assert calls == ["checked", "checked"]
        assert intervals == [60, 60]

    asyncio.run(scenario())


def test_scheduler_logs_a_failed_check_and_keeps_running(monkeypatch, caplog):
    async def scenario():
        stop_event = asyncio.Event()
        calls = []

        def check():
            calls.append("checked")
            if len(calls) == 1:
                raise RuntimeError("details must not be logged")

        async def fake_wait(event, _interval):
            if len(calls) == 2:
                event.set()

        monkeypatch.setattr("app.services.reminders._wait_for_next_check", fake_wait)
        await reminder_scheduler(stop_event, check=check)

    asyncio.run(scenario())
    failures = [record for record in caplog.records if "Reminder check failed" in record.message]
    assert len(failures) == 1
    assert "details must not be logged" not in failures[0].message


def test_scheduler_shutdown_waits_for_inflight_database_check():
    async def scenario():
        stop_event = asyncio.Event()
        started = threading.Event()
        finish = threading.Event()

        def blocking_check():
            started.set()
            finish.wait()

        task = asyncio.create_task(reminder_scheduler(stop_event, check=blocking_check))
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        assert not task.done()
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.done()

    asyncio.run(scenario())


def test_fastapi_lifespan_cancels_scheduler_cleanly(monkeypatch):
    from app import main

    async def scenario():
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def fake_scheduler(stop_event):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        monkeypatch.setattr(main, "reminder_scheduler", fake_scheduler)
        async with main.lifespan(main.app):
            task = main.app.state.reminder_scheduler_task
            await started.wait()
            assert not task.done()
        assert stopped.is_set()
        assert task.done()

    asyncio.run(scenario())
