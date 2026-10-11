from datetime import date
from uuid import uuid4

from app.fleet_command import command_metrics
from app.models import Branch, Driver, MaintenanceWorkOrder, Vehicle, VehicleDocument


def test_command_metrics_branch_isolation(db):
    first = Branch(code="AAA", name="Main Fleet")
    second = Branch(code="BBB", name="Other Fleet")
    db.add_all([first, second])
    db.flush()
    a = Vehicle(branch_id=first.id, registration_plate="AA100", make="Toyota",
                model="Hilux", vehicle_type="Truck", mechanical_condition="attention")
    b = Vehicle(branch_id=second.id, registration_plate="BB100", make="Toyota",
                model="Hilux", vehicle_type="Truck", mechanical_condition="operational")
    db.add_all([a, b])
    db.flush()
    db.add_all([
        Driver(branch_id=first.id, full_name="Driver A", license_number="DL-A",
               license_category="B", license_expiry=date(2026, 1, 1)),
        Driver(branch_id=second.id, full_name="Driver B", license_number="DL-B",
               license_category="B", license_expiry=date(2027, 1, 1)),
        MaintenanceWorkOrder(branch_id=first.id, vehicle_id=a.id, description="Brakes", status="open"),
        VehicleDocument(branch_id=first.id, vehicle_id=a.id, document_type="Insurance",
                        is_required=True, expiry_date=date(2026, 9, 1)),
        VehicleDocument(branch_id=second.id, vehicle_id=b.id, document_type="Insurance",
                        is_required=True, expiry_date=date(2027, 9, 1)),
    ])
    db.commit()
    report = command_metrics(db, first.id, today=date(2026, 10, 11))
    assert report["vehicles_active"] == 1
    assert report["drivers_active"] == 1
    assert report["vehicles_with_mechanical_attention"] == 1
    assert report["drivers_license_expired"] == 1
    assert report["expired_required_vehicle_documents"] == 1
    assert report["open_maintenance_work_orders"] == 1
    assert report["requires_attention"] == 4
    assert command_metrics(db, second.id, today=date(2026, 10, 11))["requires_attention"] == 0


def test_empty_branch_does_not_count_other_branches(db):
    branch = Branch(code="EMPTY", name="No Vehicles")
    db.add(branch)
    db.commit()
    report = command_metrics(db, branch.id, today=date(2026, 10, 11))
    assert report["vehicles_active"] == 0
    assert report["active_trips"] == 0
    assert report["requires_attention"] == 0
