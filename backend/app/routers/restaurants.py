from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.menu_item import MenuItem
from app.models.restaurant import Restaurant
from app.schemas.menu_item import PaginatedMenuItems
from app.schemas.restaurant import PaginatedRestaurants, RestaurantPublic

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


@router.get("", response_model=PaginatedRestaurants)
def list_restaurants(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    total = db.scalar(select(func.count()).select_from(Restaurant)) or 0
    restaurants = db.scalars(
        select(Restaurant).order_by(Restaurant.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [RestaurantPublic.model_validate(item) for item in restaurants],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/{restaurant_id}/menu-items", response_model=PaginatedMenuItems)
def list_restaurant_menu(
    restaurant_id: int,
    search: str | None = Query(default=None, max_length=160),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    if db.get(Restaurant, restaurant_id) is None:
        raise HTTPException(status_code=404, detail="Restaurant not found.")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail="min_price must not exceed max_price.")

    filters = [MenuItem.restaurant_id == restaurant_id, MenuItem.is_available.is_(True)]
    if search and search.strip():
        filters.append(MenuItem.name.ilike(f"%{search.strip()}%"))
    if min_price is not None:
        filters.append(MenuItem.price >= min_price)
    if max_price is not None:
        filters.append(MenuItem.price <= max_price)

    total = db.scalar(select(func.count()).select_from(MenuItem).where(*filters)) or 0
    items = db.scalars(
        select(MenuItem)
        .where(*filters)
        .order_by(MenuItem.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"items": items, "page": page, "page_size": page_size, "total": total}
