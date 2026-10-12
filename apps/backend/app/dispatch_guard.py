"""Server-side operational eligibility and concurrency safeguards for dispatch."""
from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import Assignment, Driver, Trip, Vehicle, VehicleTypeLicenseRule
from .fleet_engine import evaluate_vehicle


def ensure_dispatch_eligible(db: Session, *, branch_id: uuid.UUID,
                             vehicle_id: uuid.UUID, driver_id: uuid.UUID,
                             operation: str, at: datetime | None = None) -> None:
    """Validate resources under row locks in the caller's write transaction.

    Assignments and trips have separate lifecycles, so duplicates are checked
    inside each lifecycle; an assignment may legitimately precede a trip.
    """
    if operation not in {"assignment", "trip"}:
        raise ValueError("unsupported dispatch operation")
    at = at or datetime.now(timezone.utc)
    vehicle = db.scalar(select(Vehicle).where(
        Vehicle.id == vehicle_id, Vehicle.branch_id == branch_id
    ).with_for_update())
    driver = db.scalar(select(Driver).where(
        Driver.id == driver_id, Driver.branch_id == branch_id
    ).with_for_update())
    if vehicle is None or not vehicle.is_active or vehicle.mechanical_condition != "operational":
        raise HTTPException(status_code=409, detail="vehicle is inactive or not mechanically operational")
    if driver is None or not driver.is_active or driver.license_expiry < at.date():
        raise HTTPException(status_code=409, detail="driver is inactive or licence has expired")
    allowed = list(db.scalars(select(VehicleTypeLicenseRule.license_category).where(
        VehicleTypeLicenseRule.branch_id == branch_id,
        VehicleTypeLicenseRule.vehicle_type == vehicle.vehicle_type,
    )))
    if allowed and driver.license_category not in allowed:
        raise HTTPException(status_code=409, detail="driver licence category not permitted for this vehicle type")
    # The existing deterministic engine is authoritative for compliance and
    # maintenance safety. Orange states remain warnings; red states block.
    snapshot = evaluate_vehicle(db, vehicle, at=at)
    safety_sections = ("documents", "service", "mechanical", "inspection")
    unsafe = [
        name for name in safety_sections
        if (snapshot[name]["overall"] if name == "documents" else snapshot[name])["level"] == "red"
    ]
    maintenance_open = any(
        item["label"] == "UNDER MAINTENANCE"
        for item in snapshot["availability"]["blockers"]
    )
    if maintenance_open:
        unsafe.append("maintenance")
    if unsafe:
        raise HTTPException(
            status_code=409,
            detail="vehicle safety or compliance blocks dispatch: " + ", ".join(unsafe),
        )
    model = Assignment if operation == "assignment" else Trip
    existing = db.scalar(select(model.id).where(
        model.branch_id == branch_id, model.status == "active",
        or_(model.vehicle_id == vehicle_id, model.driver_id == driver_id)
    ).limit(1))
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"active {operation} already uses this vehicle or driver")
