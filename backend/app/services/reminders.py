import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models.order import Order
from app.models.reminder_log import ReminderLog
from app.models.restaurant import Restaurant

logger = logging.getLogger(__name__)
REMINDER_AGE = timedelta(minutes=15)


def create_due_reminders(db: Session, *, now: datetime | None = None) -> int:
    """Create one owner reminder for each overdue PLACED/ACCEPTED order."""
    checked_at = now or datetime.now(timezone.utc)
    cutoff = checked_at - REMINDER_AGE
    existing_reminder = exists(select(ReminderLog.id).where(ReminderLog.order_id == Order.id))
    candidates = _select_candidate_orders(db, cutoff, existing_reminder)

    created = 0
    try:
        for order_id, expected_restaurant_id in candidates:
            try:
                # Lifecycle endpoints also lock the order row. Refreshing it while
                # holding that lock prevents a stale candidate from qualifying.
                with db.begin_nested():
                    order = db.scalar(
                        select(Order)
                        .options(joinedload(Order.restaurant))
                        .where(
                            Order.id == order_id,
                            Order.restaurant_id == expected_restaurant_id,
                            Order.status.in_(("PLACED", "ACCEPTED")),
                            Order.updated_at < cutoff,
                        )
                        .with_for_update(of=Order)
                        .execution_options(populate_existing=True)
                    )
                    if order is None or order.restaurant is None:
                        continue

                    db.add(
                        ReminderLog(
                            order_id=order.id,
                            restaurant_id=order.restaurant.id,
                            owner_id=order.restaurant.owner_id,
                        )
                    )
                    db.flush()
            except IntegrityError:
                # A concurrent scheduler may have inserted the unique order reminder.
                # Only treat it as an expected race when the winning row now exists.
                if db.scalar(select(ReminderLog.id).where(ReminderLog.order_id == order_id)) is not None:
                    continue
                raise
            created += 1
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return created


def _select_candidate_orders(db: Session, cutoff: datetime, existing_reminder):
    """Select possible due orders; each is revalidated under its row lock later."""
    return db.execute(
        select(Order.id, Order.restaurant_id)
        .join(Restaurant, Restaurant.id == Order.restaurant_id)
        .where(
            Order.status.in_(("PLACED", "ACCEPTED")),
            Order.updated_at < cutoff,
            ~existing_reminder,
        )
        .order_by(Order.id)
    ).all()


def run_reminder_check() -> int:
    """Run one check with its own short-lived database session."""
    db = SessionLocal()
    try:
        return create_due_reminders(db)
    finally:
        db.close()


async def _wait_for_next_check(stop_event: asyncio.Event, interval_seconds: int) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
    except asyncio.TimeoutError:
        pass


async def _run_check_in_thread(check) -> None:
    worker = asyncio.create_task(asyncio.to_thread(check))
    try:
        await asyncio.shield(worker)
    except asyncio.CancelledError:
        # Cancelling asyncio.to_thread does not stop its worker thread. Wait for the
        # current database check to finish before allowing application shutdown.
        try:
            await worker
        except Exception as exc:
            logger.error("Reminder check failed during shutdown (%s).", type(exc).__name__)
        raise


async def reminder_scheduler(
    stop_event: asyncio.Event,
    *,
    check=None,
    interval_seconds: int = 60,
) -> None:
    run_check = check or run_reminder_check
    while not stop_event.is_set():
        try:
            await _run_check_in_thread(run_check)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Error type only: database/provider exceptions can contain sensitive
            # connection details. The scheduler remains alive and retries next tick.
            logger.error("Reminder check failed (%s); it will retry.", type(exc).__name__)
        await _wait_for_next_check(stop_event, interval_seconds)
