import { useState } from "react";
import {
  Activity,
  ClipboardCheck,
  Filter,
  GitBranch,
  Search,
  ShieldCheck,
} from "lucide-react";
import { date, type AuditEvent } from "../api";

import { Empty } from "../components/ui";

export function ActivityPage({ events }: { events: AuditEvent[] }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All activity");
  const matches = (action: string) =>
    category === "All activity" ||
    (category === "Telemetry"
      ? /sensor|gateway|snapshot/i
      : category === "Maintenance"
        ? /order|approv|investigation|recommendation/i
        : /document/i
    ).test(action);
  const filtered = events.filter(
    (e) =>
      `${e.action} ${e.actor} ${e.target} ${e.details || ""}`
        .toLowerCase()
        .includes(query.toLowerCase()) && matches(e.action),
  );
  return (
    <section className="panel">
      <div className="table-toolbar">
        <div>
          <h2>Workspace activity</h2>
          <p className="muted small-text">
            Latest 200 permitted audit records · GST
          </p>
        </div>
        <div className="inline-search">
          <Search size={15} />
          <input
            placeholder="Filter activity…"
            aria-label="Filter activity"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>
      <div className="activity-filters" aria-label="Activity categories">
        {["All activity", "Telemetry", "Maintenance", "Documents"].map(
          (label) => (
            <button
              key={label}
              aria-pressed={category === label}
              className={category === label ? "active" : ""}
              onClick={() => setCategory(label)}
            >
              {label}
            </button>
          ),
        )}
        <span>{filtered.length} matching records</span>
      </div>
      <div className="activity-timeline">
        {filtered.map((e) => (
          <div key={e.id} className="activity-event">
            <div className="timeline-icon">
              {e.action.toLowerCase().includes("approv") ? (
                <ShieldCheck size={18} />
              ) : e.action.toLowerCase().includes("order") ? (
                <ClipboardCheck size={18} />
              ) : (
                <Activity size={18} />
              )}
            </div>
            <div>
              <div>
                <strong>{e.action}</strong>
                <time>{date(e.created, true)}</time>
              </div>
              <p>{e.target}</p>
              <small>
                {e.actor} <i>·</i> {e.site}
              </small>
              {e.details && (
                <details className="audit-evidence">
                  <summary>Evidence & record IDs</summary>
                  <p>{e.details}</p>
                </details>
              )}
            </div>
          </div>
        ))}
      </div>
      {!filtered.length && (
        <Empty
          icon={GitBranch}
          title="No matching activity"
          description="Actions you take in this workspace will be recorded here."
        />
      )}
    </section>
  );
}
