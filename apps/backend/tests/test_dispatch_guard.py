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


def test_dispatch_blocks_expired_required_document_and_overdue_service(db):
    from app.models import (
        DocumentRequirement, VehicleDocument, ServiceRecord, Inspection
    )
    branch = Branch(code="COMP", name="Compliance branch")
    db.add(branch); db.flush()
    vehicle = Vehicle(branch_id=branch.id, registration_plate="COMP100",
                      make="Toyota", model="Hilux", vehicle_type="light")
    driver = Driver(branch_id=branch.id, full_name="Driver Three",
                    license_number="D003", license_category="B",
                    license_expiry=date(2028, 1, 1))
    db.add_all([vehicle, driver]); db.flush()
    db.add(DocumentRequirement(branch_id=branch.id, document_type="Insurance",
                               is_required=True))
    db.add(VehicleDocument(branch_id=branch.id, vehicle_id=vehicle.id,
                           document_type="Insurance", expiry_date=date(2026, 1, 1)))
    db.add(ServiceRecord(branch_id=branch.id, vehicle_id=vehicle.id,
                         service_date=date(2026, 1, 1), mileage=1000,
                         service_type="Annual", next_service_date=date(2026, 9, 1)))
    db.add(Inspection(branch_id=branch.id, vehicle_id=vehicle.id,
                      inspection_date=date(2026, 10, 1), status="passed",
                      next_inspection_date=date(2027, 10, 1)))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        ensure_dispatch_eligible(db, branch_id=branch.id, vehicle_id=vehicle.id,
             driver_id=driver.id, operation="trip",
             at=datetime(2026, 10, 12, tzinfo=timezone.utc))
    assert exc.value.status_code == 409
    assert "documents" in exc.value.detail
    assert "service" in exc.value.detail


def test_dispatch_blocks_failed_inspection_and_open_work_order(db):
    from app.models import Inspection, MaintenanceWorkOrder
    branch = Branch(code="SAFE", name="Safety branch")
    db.add(branch); db.flush()
    vehicle = Vehicle(branch_id=branch.id, registration_plate="SAFE100",
                      make="Toyota", model="Hilux", vehicle_type="light")
    driver = Driver(branch_id=branch.id, full_name="Driver Four",
                    license_number="D004", license_category="B",
                    license_expiry=date(2028, 1, 1))
    db.add_all([vehicle, driver]); db.flush()
    db.add(Inspection(branch_id=branch.id, vehicle_id=vehicle.id,
                      inspection_date=date(2026, 10, 1), status="failed"))
    db.add(MaintenanceWorkOrder(branch_id=branch.id, vehicle_id=vehicle.id,
                                description="Repair brakes", status="open"))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        ensure_dispatch_eligible(db, branch_id=branch.id, vehicle_id=vehicle.id,
             driver_id=driver.id, operation="assignment",
             at=datetime(2026, 10, 12, tzinfo=timezone.utc))
    assert exc.value.status_code == 409
    assert "inspection" in exc.value.detail
    assert "maintenance" in exc.value.detail
