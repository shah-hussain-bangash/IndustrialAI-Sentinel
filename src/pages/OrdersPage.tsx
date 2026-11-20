import { useState } from "react";
import {
  ArrowUpRight,
  Box,
  CalendarDays,
  CheckCheck,
  ClipboardCheck,
  Filter,
  LayoutDashboard,
  ListFilter,
  Search,
  ShieldCheck,
} from "lucide-react";
import { date, type WorkOrder } from "../api";

import { initials, Badge, Button, Empty, colors } from "../components/ui";
import type { Page } from "../types";
export function OrdersPage({
  orders,
  open,
  navigate,
}: {
  orders: WorkOrder[];
  open: (id: string) => void;
  navigate: (p: Page) => void;
}) {
  const [view, setView] = useState("board"),
    [query, setQuery] = useState("");
  const filtered = orders.filter((o) =>
    `${o.reference} ${o.title} ${o.asset_tag}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const cols = [
    { key: "planned", label: "Planned", color: "#879bca" },
    { key: "in_progress", label: "In progress", color: colors.teal },
    { key: "reconciling", label: "Needs reconciliation", color: colors.amber },
    { key: "completed", label: "Completed", color: "#9a9a9a" },
  ];
  return (
    <>
      <div className="order-summary">
        <div>
          <ClipboardCheck size={20} />
          <span>
            <strong>
              {
                orders.filter(
                  (o) => !["completed", "cancelled"].includes(o.status),
                ).length
              }
            </strong>{" "}
            open work orders
          </span>
        </div>
        <span>
          <ShieldCheck size={15} />
          Created from version-bound approvals
        </span>
        <Badge value="simulation">Local CMMS simulator</Badge>
      </div>
      <section
        className={`panel order-panel ${view === "board" ? "transparent" : ""}`}
      >
        <div className="table-toolbar">
          <div className="view-switch">
            <button
              className={view === "board" ? "active" : ""}
              onClick={() => setView("board")}
            >
              <LayoutDashboard size={15} />
              Board
            </button>
            <button
              className={view === "list" ? "active" : ""}
              onClick={() => setView("list")}
            >
              <ListFilter size={15} />
              List
            </button>
          </div>
          <div className="inline-search">
            <Search size={15} />
            <input
              aria-label="Filter work orders"
              placeholder="Search work orders…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
        {view === "board" ? (
          <div className="kanban">
            {cols.map((col) => (
              <div className="kanban-column" key={col.key}>
                <div className="kanban-title">
                  <i style={{ background: col.color }} />
                  <h3>{col.label}</h3>
                  <span>
                    {filtered.filter((o) => o.status === col.key).length}
                  </span>
                </div>
                {filtered
                  .filter((o) => o.status === col.key)
                  .map((o) => (
                    <button
                      className="order-card"
                      key={o.id}
                      onClick={() => open(o.id)}
                    >
                      <div className="order-card-top">
                        <span>{o.reference}</span>
                        <Badge
                          value={o.priority === "High" ? "warning" : "neutral"}
                        >
                          {o.priority}
                        </Badge>
                      </div>
                      <h3>{o.title}</h3>
                      <p>
                        <Box size={13} />
                        {o.asset_tag} · {o.asset_name}
                      </p>
                      <div className="order-card-date">
                        <CalendarDays size={13} />
                        {new Date(o.due_date + "T12:00:00Z").toLocaleDateString(
                          "en-GB",
                          { day: "numeric", month: "short", timeZone: "UTC" },
                        )}
                        {o.external_ref && (
                          <span>
                            <CheckCheck size={13} />
                            Synced
                          </span>
                        )}
                      </div>
                      <div className="order-card-bottom">
                        <span className="avatar tiny">
                          {o.assignee === "Unassigned"
                            ? "+"
                            : initials(o.assignee)}
                        </span>
                        <span>{o.assignee}</span>
                        <ArrowUpRight size={15} />
                      </div>
                    </button>
                  ))}
                {!filtered.some((o) => o.status === col.key) && (
                  <div className="kanban-empty">
                    <ClipboardCheck size={22} />
                    <p>
                      {col.key === "reconciling"
                        ? "No uncertain submissions"
                        : "No work orders here"}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Work order</th>
                  <th>Equipment</th>
                  <th>Status</th>
                  <th>Assignee</th>
                  <th>Due date</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filtered.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <button className="text-link" onClick={() => open(o.id)}>
                        {o.reference}
                      </button>
                      <small>{o.title}</small>
                    </td>
                    <td>{o.asset_tag}</td>
                    <td>
                      <Badge value={o.status} />
                    </td>
                    <td>{o.assignee}</td>
                    <td>{o.due_date}</td>
                    <td>
                      <button
                        className="icon-btn"
                        aria-label={`Open ${o.reference}`}
                        onClick={() => open(o.id)}
                      >
                        <ArrowUpRight size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {orders.some((o) => o.status === "cancelled") && (
        <div className="muted small-text">
          Cancelled orders are retained in List view and the audit history.
        </div>
      )}
      {!orders.length && (
        <Empty
          title="No maintenance work yet"
          description="Review an investigation, approve its current version and plan a work order."
          action={
            <Button onClick={() => navigate("intelligence")}>
              Open investigations
            </Button>
          }
        />
      )}
    </>
  );
}
