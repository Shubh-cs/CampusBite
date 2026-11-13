from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.menu_item import MenuItem
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.menu_item import MenuItemCreate, MenuItemPublic, MenuItemUpdate, PaginatedMenuItems
from app.schemas.restaurant import RestaurantPublic, RestaurantUpdate

router = APIRouter(prefix="/owner", tags=["restaurant owner"])
owner_only = require_roles("OWNER")


def _owned_restaurant(db: Session, owner_id: int) -> Restaurant:
    restaurant = db.scalar(select(Restaurant).where(Restaurant.owner_id == owner_id))
    if restaurant is None:
        raise HTTPException(status_code=404, detail="No restaurant is associated with this owner.")
    return restaurant


@router.get("/restaurant", response_model=RestaurantPublic)
def read_owner_restaurant(
    db: Session = Depends(get_db), owner: User = Depends(owner_only)
) -> Restaurant:
    return _owned_restaurant(db, owner.id)


@router.patch("/restaurant", response_model=RestaurantPublic)
def update_owner_restaurant(
    payload: RestaurantUpdate,
    db: Session = Depends(get_db),
    owner: User = Depends(owner_only),
) -> Restaurant:
    restaurant = _owned_restaurant(db, owner.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(restaurant, field, value)
    db.commit()
    db.refresh(restaurant)
    return restaurant


@router.get("/menu-items", response_model=PaginatedMenuItems)
def list_owner_menu(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    owner: User = Depends(owner_only),
) -> dict:
    restaurant = _owned_restaurant(db, owner.id)
    total = db.scalar(
        select(func.count()).select_from(MenuItem).where(MenuItem.restaurant_id == restaurant.id)
    ) or 0
    items = db.scalars(
        select(MenuItem)
        .where(MenuItem.restaurant_id == restaurant.id)
        .order_by(MenuItem.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("/menu-items", response_model=MenuItemPublic, status_code=status.HTTP_201_CREATED)
def create_menu_item(
    payload: MenuItemCreate,
    db: Session = Depends(get_db),
    owner: User = Depends(owner_only),
) -> MenuItem:
    restaurant = _owned_restaurant(db, owner.id)
    item = MenuItem(
        restaurant_id=restaurant.id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        price=payload.price,
        image_url=str(payload.image_url) if payload.image_url else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/menu-items/{menu_item_id}", response_model=MenuItemPublic)
def update_menu_item(
    menu_item_id: int,
    payload: MenuItemUpdate,
    db: Session = Depends(get_db),
    owner: User = Depends(owner_only),
) -> MenuItem:
    restaurant = _owned_restaurant(db, owner.id)
    item = db.scalar(
        select(MenuItem).where(
            MenuItem.id == menu_item_id,
            MenuItem.restaurant_id == restaurant.id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Menu item not found.")
    changes = payload.model_dump(exclude_unset=True)
    if "image_url" in changes and changes["image_url"] is not None:
        changes["image_url"] = str(changes["image_url"])
    for field, value in changes.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item
