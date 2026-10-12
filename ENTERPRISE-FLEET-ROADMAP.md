# Enterprise Fleet Management Roadmap

The existing NBros platform is the source of truth. External open-source fleet
projects are research references, **not dependencies or copied components**.

## Data model and operations

All operational records belong to a branch and are subject to server-side
branch authorisation. A single vehicle ID links maintenance, documents,
assignments, trips, fuel, inspections, and costs.

### Phase 1 — Central oversight (this PR)
- [x] Read-only command API aggregating branch-owned operational records.
- [x] New command dashboard for vehicles, drivers, trips, assignments, bookings,
  maintenance work, fuel records, expired documents and driver licence dates.
- [x] Tests proving isolation between branches.
- [ ] Verify CI on the PR and production deployment before claiming readiness.

### Phase 2 — Vehicle master data & operational safety
- Vehicle transfer history, acquisition/disposal approvals and deactivation.
- Odometer reading history with anti-rollback rules and corrections audit.
- Driver licence category matching before dispatch, duplicate scheduling
  prevention under concurrent transactions and return inspections.
- Inspection checklists and explicit lockout on critical safety defects.

### Phase 3 — Preventive maintenance
- Time, kilometres and engine-hours rules with idempotent work-order creation.
- Parts reservation, mechanic time, estimates, approvals, invoices and closeout.
- Equipment and tyre lifecycle, document expiration renewal workflow.

### Phase 4 — Finance, procurement & controls
- Immutable cost allocations by vehicle, branch, job and funding source.
- Fuel receipts, expected versus actual consumption and exception review.
- Budget approvals, vendor invoices, depreciation with accounting integration.
- TCO reporting with defined cost periods, correct currency and reconciliation.

### Phase 5 — Enterprise scale
- Efficient indexed paginated fleet APIs (avoid loading all vehicles for lists).
- Audit and permission review, query/performance tests and backup restoration.
- Optional GPS/telematics provider adapters with explicit consent and retention.
- Role-specific mobile workflows, alert notification delivery and accessibility.
- Service-level objectives, continuous integration and observability.

## Operational design principles

- **Availability is never inferred from one status field.** The existing
  readiness engine is authoritative; overlapping exceptions are not distinct
  vehicles.
- **No invented GPS coordinates.** Location is unknown until a real
  telemetry provider reports a validated observation.
- **Database transactions protect competing assignments.** UI checks alone
  are not sufficient for collision prevention.
- **Financial balances require posting and reconciliation.** Raw costs are not
  equivalent to accounting entries.
- **No credentials in repositories.** Keep bootstrap admin disabled in
  production and prefer central identity.
