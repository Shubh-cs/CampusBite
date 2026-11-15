import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.auth import router as auth_router
from app.routers.delivery_orders import router as delivery_orders_router
from app.routers.owner_menu import router as owner_menu_router
from app.routers.owner_orders import router as owner_orders_router
from app.routers.orders import router as orders_router
from app.routers.owner_reminders import router as owner_reminders_router
from app.routers.order_insights import router as order_insights_router
from app.routers.refunds import customer_router as customer_refunds_router
from app.routers.refunds import owner_router as owner_refunds_router
from app.routers.restaurants import router as restaurants_router
from app.routers.reviews import router as reviews_router
from app.services.reminders import reminder_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    task = asyncio.create_task(reminder_scheduler(stop_event), name="campusbite-owner-reminders")
    app.state.reminder_scheduler_task = task
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def log_request(request, call_next):
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "HTTP method=%s path=%s status=%d elapsed_ms=%.2f",
            request.method,
            request.url.path,
            500,
            elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "HTTP method=%s path=%s status=%d elapsed_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


app.include_router(auth_router)
app.include_router(restaurants_router)
app.include_router(owner_menu_router)
app.include_router(orders_router)
app.include_router(order_insights_router)
app.include_router(reviews_router)
app.include_router(customer_refunds_router)
app.include_router(owner_orders_router)
app.include_router(owner_reminders_router)
app.include_router(owner_refunds_router)
app.include_router(delivery_orders_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
