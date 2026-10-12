from datetime import date, datetime, timezone
import pytest
from fastapi import HTTPException
from app.dispatch_guard import ensure_dispatch_eligible
from app.models import Branch, Vehicle, Driver, VehicleTypeLicenseRule, Assignment


def test_dispatch_requires_eligible_driver_and_vehicle(db):
    branch = Branch(code="HQ", name="Head Office")
    db.add(branch); db.flush()
    vehicle = Vehicle(branch_id=branch.id, registration_plate="A123", make="Toyota",
                      model="Hilux", vehicle_type="heavy", mechanical_condition="operational")
    driver = Driver(branch_id=branch.id, full_name="Driver One", license_number="D001",
                    license_category="B", license_expiry=date(2027, 1, 1))
    db.add_all([vehicle, driver]); db.flush()
    db.add(VehicleTypeLicenseRule(branch_id=branch.id, vehicle_type="heavy", license_category="C"))
    db.commit()
    args = dict(branch_id=branch.id, vehicle_id=vehicle.id, driver_id=driver.id,
                operation="assignment", at=datetime(2026, 10, 12, tzinfo=timezone.utc))
    with pytest.raises(HTTPException) as exc:
        ensure_dispatch_eligible(db, **args)
    assert exc.value.status_code == 409
    driver.license_category = "C"
    db.commit()
    ensure_dispatch_eligible(db, **args)
    db.add(Assignment(branch_id=branch.id, vehicle_id=vehicle.id, driver_id=driver.id,
                      start_at=args["at"], status="active"))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        ensure_dispatch_eligible(db, **args)
    assert exc.value.status_code == 409
    vehicle.mechanical_condition = "out_of_service"
    db.commit()
    with pytest.raises(HTTPException) as exc:
        ensure_dispatch_eligible(db, **args)
    assert "mechanically" in exc.value.detail


def test_dispatch_blocks_expired_licence(db):
    branch = Branch(code="B", name="Branch B")
    db.add(branch); db.flush()
    vehicle = Vehicle(branch_id=branch.id, registration_plate="B123", make="Toyota",
                      model="Hilux", vehicle_type="light")
    driver = Driver(branch_id=branch.id, full_name="Driver Two", license_number="D002",
                    license_category="B", license_expiry=date(2025, 1, 1))
    db.add_all([vehicle, driver]); db.commit()
    with pytest.raises(HTTPException) as exc:
        ensure_dispatch_eligible(db, branch_id=branch.id, vehicle_id=vehicle.id,
            driver_id=driver.id, operation="trip", at=datetime(2026, 10, 12, tzinfo=timezone.utc))
    assert exc.value.status_code == 409
