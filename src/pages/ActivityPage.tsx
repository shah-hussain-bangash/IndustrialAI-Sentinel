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
  const filtered = events.filter((e) =>
    `${e.action} ${e.actor} ${e.target}`
      .toLowerCase()
      .includes(query.toLowerCase()),
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
                {e.details && (
                  <>
                    {" "}
                    <i>·</i> {e.details}
                  </>
                )}
              </small>
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
