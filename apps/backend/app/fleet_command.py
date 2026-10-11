"""Branch-scoped fleet command overview.

Aggregation only: it reads the authoritative fleet tables and does not create
duplicate counts or mutate operational records.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from .auth import current_claims
from .db import SessionLocal
from .fleet import _profile, _require_branch
from .models import (
    Assignment, Driver, FuelRecord, MaintenanceWorkOrder, Reservation,
    Trip, Vehicle, VehicleDocument,
)

router = APIRouter(prefix="/api/v1/fleet", tags=["fleet-command"])


def command_metrics(db, branch_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any]:
    """Calculate fleet-wide operational counts for a single authorised branch."""
    today = today or datetime.now(timezone.utc).date()

    def total(model, *filters):
        return int(db.scalar(select(func.count()).select_from(model).where(
            model.branch_id == branch_id, *filters
        )) or 0)

    vehicles = total(Vehicle, Vehicle.is_active.is_(True))
    drivers = total(Driver, Driver.is_active.is_(True))
    unavailable = total(
        Vehicle, Vehicle.is_active.is_(True),
        Vehicle.mechanical_condition != "operational"
    )
    overdue_licenses = total(
        Driver, Driver.is_active.is_(True), Driver.license_expiry < today
    )
    expiring_licenses = total(
        Driver, Driver.is_active.is_(True),
        Driver.license_expiry >= today,
        Driver.license_expiry <= date.fromordinal(today.toordinal() + 30)
    )
    expired_docs = total(
        VehicleDocument,
        VehicleDocument.is_required.is_(True),
        VehicleDocument.expiry_date.is_not(None),
        VehicleDocument.expiry_date < today,
    )
    open_work_orders = total(
        MaintenanceWorkOrder,
        MaintenanceWorkOrder.status.in_(["open", "in_progress"])
    )
    active_trips = total(Trip, Trip.status == "active")
    active_assignments = total(Assignment, Assignment.status == "active")
    active_reservations = total(Reservation, Reservation.status == "active")
    fuel_entries = total(FuelRecord)

    # Fleet counts are not summed into a fictitious "available" count: vehicles
    # can have multiple simultaneous blocking reasons. The existing decision
    # engine remains the authority for dispatch readiness.
    return {
        "as_of": today.isoformat(),
        "vehicles_active": vehicles,
        "drivers_active": drivers,
        "vehicles_with_mechanical_attention": unavailable,
        "drivers_license_expired": overdue_licenses,
        "drivers_license_expiring_30_days": expiring_licenses,
        "expired_required_vehicle_documents": expired_docs,
        "open_maintenance_work_orders": open_work_orders,
        "active_trips": active_trips,
        "active_assignments": active_assignments,
        "active_reservations": active_reservations,
        "fuel_records": fuel_entries,
        "requires_attention": (
            unavailable + overdue_licenses + expired_docs + open_work_orders
        ),
        "attention_count_note": "Issue categories can overlap; this is not a distinct vehicle count.",
    }


@router.get("/command")
def fleet_command(
    branch_id: uuid.UUID = Query(...),
    claims: dict = Depends(current_claims),
) -> dict[str, Any]:
    with SessionLocal() as db:
        profile = _profile(db, claims)
        branch = _require_branch(db, profile, branch_id)
        return {
            "branch": {"id": str(branch.id), "name": branch.name, "code": branch.code},
            "metrics": command_metrics(db, branch_id),
        }
