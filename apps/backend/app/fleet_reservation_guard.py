"""Transactional protection for fleet vehicle and driver reservations."""
from datetime import datetime
import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import Driver, Reservation, Vehicle


def ensure_reservation_available(
    db: Session, *, branch_id: uuid.UUID, vehicle_id: uuid.UUID,
    driver_id: uuid.UUID | None, start_at: datetime, end_at: datetime,
) -> None:
    """Lock fleet resources then reject overlapping active reservations.

    In PostgreSQL, row-level locks serialize reservations for the same vehicle
    and driver across concurrent requests. Endpoints must call this before
    inserting and commit in the same transaction.
    """
    if end_at <= start_at:
        raise HTTPException(status_code=422, detail="reservation end must be after start")

    vehicle = db.scalar(select(Vehicle).where(
        Vehicle.id == vehicle_id, Vehicle.branch_id == branch_id,
        Vehicle.is_active.is_(True),
    ).with_for_update())
    if vehicle is None:
        raise HTTPException(status_code=409, detail="vehicle is unavailable")

    if driver_id is not None:
        driver = db.scalar(select(Driver).where(
            Driver.id == driver_id, Driver.branch_id == branch_id,
            Driver.is_active.is_(True),
        ).with_for_update())
        if driver is None or driver.license_expiry < start_at.date():
            raise HTTPException(status_code=409, detail="driver is unavailable or licence expired")
    overlap = (
        Reservation.branch_id == branch_id,
        Reservation.status == "active",
        Reservation.start_at < end_at,
        Reservation.end_at > start_at,
    )
    vehicle_conflict = db.scalar(select(Reservation.id).where(
        *overlap, Reservation.vehicle_id == vehicle_id,
    ).limit(1))
    if vehicle_conflict is not None:
        raise HTTPException(status_code=409, detail="vehicle already reserved for this period")
    if driver_id is not None:
        driver_conflict = db.scalar(select(Reservation.id).where(
            *overlap, Reservation.driver_id == driver_id,
        ).limit(1))
        if driver_conflict is not None:
            raise HTTPException(status_code=409, detail="driver already reserved for this period")
