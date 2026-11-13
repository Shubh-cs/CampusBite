"""Explicit, conservative seed for local CampusBite demonstration data.

Run with ``python -m app.seed_demo`` from the backend directory. This module is
never called during application startup. Demo accounts and passwords are for
local development only and must not be reused outside a local demo.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.database import SessionLocal
from app.models.menu_item import MenuItem
from app.models.restaurant import Restaurant
from app.models.user import User


class SeedConflict(RuntimeError):
    """Existing data differs from the expected local demo seed."""


@dataclass(frozen=True)
class DemoUser:
    full_name: str
    email: str
    role: str
    password: str


@dataclass(frozen=True)
class DemoRestaurant:
    owner_email: str
    name: str
    description: str
    address: str
    dishes: tuple[tuple[str, str, str, Decimal], ...]


DEMO_PASSWORD = "CampusBite-Local-Demo-2026!"
DEMO_USERS = (
    DemoUser("Demo Owner One", "owner1@campusbite.local", "OWNER", DEMO_PASSWORD),
    DemoUser("Demo Owner Two", "owner2@campusbite.local", "OWNER", DEMO_PASSWORD),
    DemoUser("Demo Owner Three", "owner3@campusbite.local", "OWNER", DEMO_PASSWORD),
    DemoUser("Demo Delivery One", "delivery1@campusbite.local", "DELIVERY_PARTNER", DEMO_PASSWORD),
    DemoUser("Demo Delivery Two", "delivery2@campusbite.local", "DELIVERY_PARTNER", DEMO_PASSWORD),
)
DEMO_RESTAURANTS = (
    DemoRestaurant(
        "owner1@campusbite.local",
        "Maple & Millet",
        "Fictional local demo kitchen serving comforting bowls.",
        "CampusBite Demo District, Building A",
        (
            ("Millet Veg Bowl", "Millet", "Warm millet with seasonal vegetables.", Decimal("145.00")),
            ("Paneer Rice Bowl", "Rice Bowls", "Paneer and rice with a mild house sauce.", Decimal("175.00")),
            ("Masala Corn Cup", "Snacks", "Sweet corn with a light spice blend.", Decimal("75.00")),
            ("Lemon Rice", "Rice Bowls", "Tangy lemon rice with roasted peanuts.", Decimal("110.00")),
            ("Cocoa Banana Shake", "Drinks", "Banana blended with cocoa and milk.", Decimal("95.00")),
        ),
    ),
    DemoRestaurant(
        "owner2@campusbite.local",
        "Copper Kettle Kitchen",
        "Fictional local demo kitchen with simple cafe meals.",
        "CampusBite Demo District, Building B",
        (
            ("Garden Grilled Sandwich", "Sandwiches", "Grilled vegetables with herbs.", Decimal("130.00")),
            ("Tomato Basil Pasta", "Pasta", "Pasta tossed in tomato and basil sauce.", Decimal("190.00")),
            ("Herbed Potato Wedges", "Sides", "Oven-style potato wedges with herbs.", Decimal("90.00")),
            ("Classic Veg Wrap", "Wraps", "Vegetables wrapped with a yogurt dressing.", Decimal("125.00")),
            ("Iced Lemon Tea", "Drinks", "Chilled tea with lemon.", Decimal("70.00")),
        ),
    ),
    DemoRestaurant(
        "owner3@campusbite.local",
        "Little Lotus Canteen",
        "Fictional local demo kitchen for everyday vegetarian meals.",
        "CampusBite Demo District, Building C",
        (
            ("Idli Sambar Set", "South Indian", "Steamed idli served with sambar.", Decimal("100.00")),
            ("Vegetable Upma", "Breakfast", "Savory semolina with vegetables.", Decimal("85.00")),
            ("Chole Kulcha", "North Indian", "Chickpeas served with soft kulcha.", Decimal("155.00")),
            ("Curd Rice", "Rice Bowls", "Cooling curd rice with a mild tempering.", Decimal("105.00")),
            ("Jaggery Rice Pudding", "Desserts", "Rice pudding sweetened with jaggery.", Decimal("80.00")),
        ),
    ),
)


def _dish_values(dish: tuple[str, str, str, Decimal]) -> tuple[str, str, str, Decimal, None, bool]:
    name, category, description, price = dish
    return name, category, description, price, None, True


def _actual_dish_values(item: MenuItem) -> tuple[str, str, str, Decimal, str | None, bool]:
    return item.name, item.category, item.description or "", item.price, item.image_url, item.is_available


def seed_demo_data(db: Session) -> dict[str, int]:
    """Validate existing demo records, then insert only missing records.

    The caller owns the transaction and must commit on success or roll back on
    failure. All existing records are validated before any new record is added.
    """
    existing_users: dict[str, User | None] = {}
    for expected in DEMO_USERS:
        matches = db.scalars(select(User).where(func.lower(User.email) == expected.email.lower())).all()
        if len(matches) > 1:
            raise SeedConflict(f"Multiple existing accounts conflict with demo account: {expected.email}")
        user = matches[0] if matches else None
        if user is not None and (
            user.email != expected.email
            or user.full_name != expected.full_name
            or user.role != expected.role
            or not user.is_active
            or not verify_password(expected.password, user.password_hash)
        ):
            raise SeedConflict(f"Existing demo account conflicts: {expected.email}")
        existing_users[expected.email] = user

    restaurant_states: list[tuple[DemoRestaurant, User | None, Restaurant | None, list[MenuItem]]] = []
    for expected in DEMO_RESTAURANTS:
        owner = existing_users[expected.owner_email]
        if owner is None:
            restaurant_states.append((expected, None, None, []))
            continue
        restaurant = db.scalar(select(Restaurant).where(Restaurant.owner_id == owner.id))
        items = [] if restaurant is None else db.scalars(
            select(MenuItem).where(MenuItem.restaurant_id == restaurant.id).order_by(MenuItem.id)
        ).all()
        if restaurant is not None:
            if (restaurant.name, restaurant.description, restaurant.address) != (
                expected.name,
                expected.description,
                expected.address,
            ):
                raise SeedConflict(f"Existing demo restaurant conflicts: {expected.name}")
            actual = sorted((_actual_dish_values(item) for item in items), key=lambda row: row[0])
            wanted = sorted((_dish_values(dish) for dish in expected.dishes), key=lambda row: row[0])
            if actual != wanted:
                raise SeedConflict(f"Existing demo menu conflicts: {expected.name}")
        restaurant_states.append((expected, owner, restaurant, items))

    new_users = 0
    for expected in DEMO_USERS:
        if existing_users[expected.email] is None:
            user = User(
                full_name=expected.full_name,
                email=expected.email,
                password_hash=hash_password(expected.password),
                role=expected.role,
            )
            db.add(user)
            existing_users[expected.email] = user
            new_users += 1
    db.flush()

    new_restaurants = 0
    new_menu_items = 0
    for expected, owner, restaurant, items in restaurant_states:
        if owner is None:
            owner = existing_users[expected.owner_email]
        assert owner is not None
        if restaurant is None:
            restaurant = Restaurant(
                owner_id=owner.id,
                name=expected.name,
                description=expected.description,
                address=expected.address,
            )
            db.add(restaurant)
            db.flush()
            new_restaurants += 1
        if not items:
            for dish in expected.dishes:
                name, category, description, price = dish
                db.add(
                    MenuItem(
                        restaurant_id=restaurant.id,
                        name=name,
                        category=category,
                        description=description,
                        price=price,
                        is_available=True,
                    )
                )
                new_menu_items += 1
    db.flush()
    return {"users": new_users, "restaurants": new_restaurants, "menu_items": new_menu_items}


def main() -> int:
    db = SessionLocal()
    try:
        counts = seed_demo_data(db)
        db.commit()
    except (SeedConflict, IntegrityError):
        db.rollback()
        print("Demo seed stopped: existing records conflict with the local demo data; no changes were committed.")
        return 1
    finally:
        db.close()

    print(
        "Local demo seed complete: "
        f"{counts['users']} accounts, {counts['restaurants']} restaurants, "
        f"{counts['menu_items']} menu items added. Existing exact records were left unchanged."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
