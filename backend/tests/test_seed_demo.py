import pytest
from sqlalchemy import delete, func, select

from app.core.security import hash_password
from app.models import MenuItem, Restaurant, User
from app.seed_demo import DEMO_PASSWORD, DEMO_RESTAURANTS, DEMO_USERS, SeedConflict, seed_demo_data


def test_demo_seed_creates_expected_records_and_is_safe_to_rerun(db_session):
    first = seed_demo_data(db_session)
    db_session.commit()
    second = seed_demo_data(db_session)
    db_session.commit()

    assert first == {"users": 5, "restaurants": 3, "menu_items": 15}
    assert second == {"users": 0, "restaurants": 0, "menu_items": 0}
    assert db_session.scalar(select(func.count()).select_from(User)) == 5
    assert db_session.scalar(select(func.count()).select_from(Restaurant)) == 3
    assert db_session.scalar(select(func.count()).select_from(MenuItem)) == 15
    assert len(DEMO_USERS) == 5
    assert len(DEMO_RESTAURANTS) == 3
    assert all(len(restaurant.dishes) == 5 for restaurant in DEMO_RESTAURANTS)


def test_demo_seed_fails_safely_when_existing_menu_has_been_edited(db_session):
    seed_demo_data(db_session)
    db_session.commit()
    item = db_session.scalar(select(MenuItem).order_by(MenuItem.id))
    item.name = "Owner Edited Name"
    db_session.commit()
    before_count = db_session.scalar(select(func.count()).select_from(MenuItem))

    with pytest.raises(SeedConflict, match="Existing demo menu conflicts"):
        seed_demo_data(db_session)

    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(MenuItem)) == before_count
    assert db_session.get(MenuItem, item.id).name == "Owner Edited Name"


def test_demo_seed_fails_on_conflicting_account_without_partial_inserts(db_session):
    expected = DEMO_USERS[0]
    db_session.add(
        User(
            full_name="Unrelated Existing Account",
            email=expected.email,
            password_hash="not-a-demo-password-hash",
            role="CUSTOMER",
        )
    )
    db_session.commit()

    with pytest.raises(SeedConflict, match="Existing demo account conflicts"):
        seed_demo_data(db_session)

    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(User)) == 1
    assert db_session.scalar(select(func.count()).select_from(Restaurant)) == 0


def test_demo_seed_fails_when_an_existing_demo_account_is_inactive(db_session):
    expected = DEMO_USERS[0]
    db_session.add(
        User(
            full_name=expected.full_name,
            email=expected.email,
            password_hash=hash_password(DEMO_PASSWORD),
            role=expected.role,
            is_active=False,
        )
    )
    db_session.commit()

    with pytest.raises(SeedConflict, match="Existing demo account conflicts"):
        seed_demo_data(db_session)

    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(User)) == 1
    assert db_session.scalar(select(func.count()).select_from(Restaurant)) == 0


def test_demo_seed_does_not_repopulate_an_existing_empty_menu(db_session):
    seed_demo_data(db_session)
    db_session.commit()
    db_session.execute(delete(MenuItem))
    db_session.commit()

    with pytest.raises(SeedConflict, match="Existing demo menu conflicts"):
        seed_demo_data(db_session)

    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(MenuItem)) == 0
