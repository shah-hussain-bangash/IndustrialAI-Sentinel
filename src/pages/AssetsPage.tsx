import { useState } from "react";
import {
  ArrowUpRight,
  Box,
  Filter,
  ListFilter,
  Search,
  ShieldCheck,
} from "lucide-react";
import { type Asset } from "../api";

import {
  Badge,
  Empty,
  MiniSpark,
  EquipmentArt,
  colors,
} from "../components/ui";

export function AssetsPage({
  assets,
  openAsset,
}: {
  assets: Asset[];
  openAsset: (id: string) => void;
}) {
  const [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [view, setView] = useState("table");
  const filtered = assets.filter(
    (a) =>
      `${a.tag} ${a.name} ${a.kind}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (filter === "all" || a.status === filter),
  );
  return (
    <section className="panel registry">
      <div className="table-toolbar">
        <div className="tabs">
          {[
            ["all", "All assets"],
            ["healthy", "Healthy"],
            ["warning", "Watch"],
            ["critical", "Critical"],
          ].map(([id, label]) => (
            <button
              key={id}
              className={filter === id ? "active" : ""}
              onClick={() => setFilter(id)}
            >
              {label}
              <span>
                {id === "all"
                  ? assets.length
                  : assets.filter((a) => a.status === id).length}
              </span>
            </button>
          ))}
        </div>
        <div className="toolbar-right">
          <div className="inline-search">
            <Search size={15} />
            <input
              aria-label="Filter equipment"
              placeholder="Filter equipment…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <button
            className="icon-btn bordered"
            aria-label={
              view === "table" ? "Switch to card view" : "Switch to table view"
            }
            onClick={() => setView(view === "table" ? "cards" : "table")}
          >
            {view === "table" ? <Box size={16} /> : <ListFilter size={16} />}
          </button>
        </div>
      </div>
      {view === "table" ? (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Equipment</th>
                <th>Site / location</th>
                <th>Condition</th>
                <th>Vibration</th>
                <th>Criticality</th>
                <th>Trend</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((a, i) => (
                <tr key={a.id} onClick={() => openAsset(a.id)}>
                  <td>
                    <div className="equipment-cell">
                      <span className="equipment-square">
                        <Box size={19} />
                      </span>
                      <div>
                        <strong>
                          {a.tag} <em>{a.kind}</em>
                        </strong>
                        <small>{a.name}</small>
                      </div>
                    </div>
                  </td>
                  <td>
                    <strong className="normal-weight">
                      {a.site.split(" ").slice(0, 2).join(" ")}
                    </strong>
                    <small>{a.location}</small>
                  </td>
                  <td>
                    <div className="inline-health">
                      <strong className={a.status}>{a.health ?? "—"}</strong>
                      <div>
                        <Badge value={a.status} />
                        <div className="health-bar">
                          <i
                            style={{
                              width: `${a.health || 0}%`,
                              background:
                                a.status === "critical"
                                  ? colors.red
                                  : a.status === "warning"
                                    ? colors.amber
                                    : colors.teal,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <strong className="numeric">
                      {a.reading?.vibration.toFixed(2) ?? "—"}{" "}
                      <small>mm/s</small>
                    </strong>
                  </td>
                  <td>
                    <span className="criticality">
                      <span className={a.criticality.toLowerCase()} />
                      {a.criticality}
                    </span>
                  </td>
                  <td>
                    <MiniSpark
                      values={a.vibration_trend}
                      decorative={false}
                      critical={a.status !== "healthy"}
                    />
                    <span className="sr-only">Recorded vibration trend</span>
                  </td>
                  <td>
                    <button
                      className="icon-btn"
                      aria-label={`Open ${a.tag}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        openAsset(a.id);
                      }}
                    >
                      <ArrowUpRight size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="asset-cards registry-cards">
          {filtered.map((a) => (
            <button
              key={a.id}
              className="asset-card"
              onClick={() => openAsset(a.id)}
            >
              <div className="asset-card-top">
                <span className="asset-tag">{a.tag}</span>
                <Badge value={a.status} />
              </div>
              <EquipmentArt kind={a.kind} />
              <h3>{a.name}</h3>
              <p>{a.location}</p>
              <div className="asset-card-readings">
                <span>Condition index</span>
                <strong>{a.health ?? "—"}/100</strong>
                <ArrowUpRight size={17} />
              </div>
            </button>
          ))}
        </div>
      )}
      {!filtered.length && (
        <Empty
          title="No matching equipment"
          description="Try another status or search term, or register your first asset."
        />
      )}
      <div className="table-footer">
        <span>
          Showing {filtered.length} of {assets.length} permitted assets
        </span>
        <span>
          <ShieldCheck size={13} />
          Site access enforced
        </span>
      </div>
    </section>
  );
}
