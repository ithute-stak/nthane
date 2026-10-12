import Link from "next/link";
import { redirect } from "next/navigation";
import { ApiError, nbrosApi } from "@/lib/backend";

type Branch = { id: string; name: string; code: string };
type Metrics = {
  as_of: string;
  vehicles_active: number;
  drivers_active: number;
  vehicles_with_mechanical_attention: number;
  drivers_license_expired: number;
  drivers_license_expiring_30_days: number;
  expired_required_vehicle_documents: number;
  open_maintenance_work_orders: number;
  active_trips: number;
  active_assignments: number;
  active_reservations: number;
  fuel_records: number;
  requires_attention: number;
  attention_count_note: string;
};
type Overview = { branch: Branch; metrics: Metrics };

export default async function FleetCommandPage({
  searchParams,
}: { searchParams: Promise<{ branch?: string }> }) {
  const { branch } = await searchParams;
  if (!branch) redirect("/fleet");
  let overview: Overview;
  try {
    overview = await nbrosApi<Overview>(`/api/v1/fleet/command?branch_id=${encodeURIComponent(branch)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/api/auth/login");
    throw error;
  }
  const { metrics: m } = overview;
  const tiles = [
    { label: "Active vehicles", value: m.vehicles_active, context: "Registered and active" },
    { label: "Active drivers", value: m.drivers_active, context: "Current driver records" },
    { label: "Active trips", value: m.active_trips, context: "In progress" },
    { label: "Vehicle assignments", value: m.active_assignments, context: "Current assignments" },
    { label: "Open work orders", value: m.open_maintenance_work_orders, context: "Open or in progress" },
    { label: "Mechanical attention", value: m.vehicles_with_mechanical_attention, context: "Not marked operational" },
    { label: "Expired driver licences", value: m.drivers_license_expired, context: "Active drivers" },
    { label: "Licences expiring soon", value: m.drivers_license_expiring_30_days, context: "Next 30 days" },
    { label: "Expired required documents", value: m.expired_required_vehicle_documents, context: "Vehicle document records" },
    { label: "Active reservations", value: m.active_reservations, context: "Current booking records" },
    { label: "Fuel records", value: m.fuel_records, context: "Total logged records" },
  ];
  const query = `branch=${encodeURIComponent(branch)}`;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand"><span className="mini-mark">NB</span><strong>NBros</strong></div>
        <nav><span className="nav-section">Fleet oversight</span>
          <Link className="nav-item active" href={`/fleet/command?${query}`}>Command overview</Link>
          <Link className="nav-item" href={`/fleet?${query}`}>Vehicles & readiness</Link>
          <Link className="nav-item" href={`/fleet/drivers?${query}`}>Drivers</Link>
          <Link className="nav-item" href={`/fleet/operations?${query}`}>Trips & operations</Link>
          <Link className="nav-item" href={`/fleet/reports?${query}`}>Reports</Link>
          <Link className="nav-item" href={`/operations/workshop?${query}`}>Workshop</Link>
        </nav>
      </aside>
      <main className="workspace">
        <header className="workspace-header">
          <div><span className="eyebrow">Enterprise fleet management</span>
            <h1>Fleet command overview</h1>
            <p className="muted">{overview.branch.name} · {overview.branch.code} · As of {m.as_of}</p>
          </div>
          <Link className="ghost-button" href={`/fleet?${query}`}>Vehicle readiness</Link>
        </header>
        <section className="panel">
          <span className="eyebrow">Exceptions requiring action</span>
          <h2>{m.requires_attention} recorded issues</h2>
          <p className="muted">{m.attention_count_note} This count includes only the four issue categories shown below, not every fleet alert.</p>
          <div className="quick-links">
            <Link href={`/fleet/operations?${query}`}>Maintenance · {m.open_maintenance_work_orders}</Link>
            <Link href={`/fleet/drivers?${query}`}>Expired licences · {m.drivers_license_expired}</Link>
            <Link href={`/fleet?${query}`}>Mechanical attention · {m.vehicles_with_mechanical_attention}</Link>
            <Link href={`/fleet?${query}`}>Expired documents · {m.expired_required_vehicle_documents}</Link>
          </div>
        </section>
        <section className="metric-grid" aria-label="Fleet operational metrics">
          {tiles.map((tile) => <article className="metric-card" key={tile.label}>
            <span>{tile.label}</span><strong>{tile.value.toLocaleString("en-LS")}</strong><small>{tile.context}</small>
          </article>)}
        </section>
        <section className="panel">
          <h2>Operational governance</h2>
          <p className="muted">Metrics are calculated from existing, branch-owned records. Vehicle dispatch readiness is determined separately by the fleet decision engine, including documentation, maintenance, inspection, mechanical and availability checks.</p>
          <div className="quick-links">
            <Link href={`/fleet/requests?${query}`}>Vehicle requests</Link>
            <Link href={`/fleet/inventory?${query}`}>Parts inventory</Link>
            <Link href={`/operations/finance?${query}`}>Fleet costs</Link>
            <Link href={`/operations/governance?${query}`}>Audit & governance</Link>
          </div>
        </section>
      </main>
    </div>
  );
}
