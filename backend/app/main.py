from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.auth import router as auth_router
from app.routers.delivery_orders import router as delivery_orders_router
from app.routers.owner_menu import router as owner_menu_router
from app.routers.owner_orders import router as owner_orders_router
from app.routers.orders import router as orders_router
from app.routers.refunds import customer_router as customer_refunds_router
from app.routers.refunds import owner_router as owner_refunds_router
from app.routers.restaurants import router as restaurants_router
from app.routers.reviews import router as reviews_router

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)
app.include_router(restaurants_router)
app.include_router(owner_menu_router)
app.include_router(orders_router)
app.include_router(reviews_router)
app.include_router(customer_refunds_router)
app.include_router(owner_orders_router)
app.include_router(owner_refunds_router)
app.include_router(delivery_orders_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
