from datetime import datetime, date, timezone, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.fleet_reservation_guard import ensure_reservation_available
from app.models import Branch, Driver, Reservation, Vehicle


def test_overlapping_vehicle_and_driver_bookings_are_rejected(db):
    branch = Branch(code="MAIN", name="Main")
    db.add(branch); db.flush()
    vehicle = Vehicle(branch_id=branch.id, registration_plate="ABC100", make="Toyota",
                      model="Hilux", vehicle_type="truck")
    second = Vehicle(branch_id=branch.id, registration_plate="ABC200", make="Toyota",
                     model="Hilux", vehicle_type="truck")
    driver = Driver(branch_id=branch.id, full_name="Test Driver", license_number="LIC01",
                    license_category="B", license_expiry=date(2028, 1, 1))
    db.add_all([vehicle, second, driver]); db.flush()
    start = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
    end = start + timedelta(hours=4)
    db.add(Reservation(branch_id=branch.id, vehicle_id=vehicle.id,
                       driver_id=driver.id, start_at=start, end_at=end))
    db.commit()
    args = dict(branch_id=branch.id, vehicle_id=vehicle.id, driver_id=None,
                start_at=start + timedelta(hours=1), end_at=end)
    with pytest.raises(HTTPException) as error:
        ensure_reservation_available(db, **args)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        ensure_reservation_available(db, branch_id=branch.id, vehicle_id=second.id,
            driver_id=driver.id, start_at=start, end_at=end)
    assert error.value.status_code == 409
    ensure_reservation_available(db, branch_id=branch.id, vehicle_id=vehicle.id,
        driver_id=driver.id, start_at=end, end_at=end + timedelta(hours=2))


def test_reject_expired_driver_and_invalid_interval(db):
    branch = Branch(code="MAIN", name="Main")
    db.add(branch); db.flush()
    vehicle = Vehicle(branch_id=branch.id, registration_plate="ABC100", make="Toyota",
                      model="Hilux", vehicle_type="truck")
    driver = Driver(branch_id=branch.id, full_name="Expired Driver", license_number="LIC02",
                    license_category="B", license_expiry=date(2025, 1, 1))
    db.add_all([vehicle, driver]); db.commit()
    start = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
    with pytest.raises(HTTPException) as error:
        ensure_reservation_available(db, branch_id=branch.id, vehicle_id=vehicle.id,
            driver_id=driver.id, start_at=start, end_at=start+timedelta(hours=1))
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        ensure_reservation_available(db, branch_id=branch.id, vehicle_id=vehicle.id,
            driver_id=None, start_at=start, end_at=start)
    assert error.value.status_code == 422
