import {
  ArrowRight,
  ArrowUpRight,
  Box,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  Gauge,
  ShieldCheck,
  Sparkles,
  Thermometer,
  TriangleAlert,
  Waves,
} from "lucide-react";
import { age, human } from "../api";

import {
  Badge,
  Button,
  Empty,
  Chart,
  EquipmentArt,
  colors,
} from "../components/ui";
import type { Data, Page } from "../types";
export function OverviewPage({
  data,
  openAsset,
  navigate,
  openInvestigation,
}: {
  data: Data;
  openAsset: (id: string) => void;
  navigate: (p: Page) => void;
  openInvestigation: (id: string) => void;
}) {
  const { stats } = data.overview;
  const unknownAssets = data.assets.filter((a) => a.health === null).length;
  const activeEpisodes = data.episodes.filter(
    (e) => e.state !== "resolved",
  ).length;
  const statsList = [
    {
      label: "Monitored assets",
      value: stats.assets,
      suffix: "",
      icon: Box,
      meta: `${stats.sensors} sensor channels`,
      tone: "teal",
    },
    {
      label: "Fleet condition index",
      value: stats.health ?? "—",
      suffix: "/100",
      icon: Gauge,
      meta: "Transparent condition score",
      tone: "blue",
    },
    {
      label: "Require attention",
      value: stats.attention,
      suffix: "",
      icon: TriangleAlert,
      meta: `${data.episodes.filter((e) => e.state !== "resolved").length} active condition episodes`,
      tone: "amber",
    },
    {
      label: "Open work orders",
      value: stats.open_orders,
      suffix: "",
      icon: ClipboardCheck,
      meta: `${stats.pending_reviews} recommendations to review`,
      tone: "violet",
    },
  ];
  const priority = [...data.assets]
    .sort((a, b) => (a.health ?? 100) - (b.health ?? 100))
    .slice(0, 3);
  const healthDist = [
    { label: "Healthy", value: stats.healthy, color: colors.teal },
    {
      label: "Watch",
      value: data.assets.filter((a) => a.status === "warning").length,
      color: colors.amber,
    },
    {
      label: "Critical",
      value: data.assets.filter((a) => a.status === "critical").length,
      color: colors.red,
    },
    {
      label: "Unknown",
      value: data.assets.filter((a) => a.health === null).length,
      color: "#c8c8c8",
    },
  ];
  const circumference = 2 * Math.PI * 64;
  let offset = 0;
  return (
    <>
      <section className="operations-brief" aria-label="Operations brief">
        <div className="brief-icon">
          <Waves size={24} />
        </div>
        <div className="brief-copy">
          <span className="brief-eyebrow">WORKSPACE PULSE</span>
          <h2>
            {unknownAssets
              ? "Bring your equipment into focus."
              : "Your next decision starts with a clearer view."}
          </h2>
          <p>
            {unknownAssets
              ? `${unknownAssets} assets await fresh readings. Run a demo replay in Live monitoring.`
              : `${activeEpisodes} active condition episodes · ${stats.pending_reviews} recommendations awaiting review.`}
          </p>
        </div>
        <Button onClick={() => navigate("monitor")} icon={ArrowUpRight}>
          Open monitoring
        </Button>
      </section>
      <div className="stats-grid">
        {statsList.map((s) => (
          <div className="stat-card" key={s.label}>
            <div className="stat-top">
              <span>{s.label}</span>
              <div className={`stat-icon ${s.tone}`}>
                <s.icon size={19} />
              </div>
            </div>
            <div className="stat-value">
              {s.value}
              <small>{s.suffix}</small>
            </div>
            <div className="stat-meta">
              <span className={`tiny-dot ${s.tone}`} />
              {s.meta}
            </div>
          </div>
        ))}
      </div>
      <div className="overview-main-grid">
        <section className="panel trend-panel">
          <div className="panel-header">
            <div>
              <h2>
                Equipment condition trend{" "}
                <span
                  className="info-mark"
                  title="The chart shows demonstration vibration readings, not failure probability."
                >
                  i
                </span>
              </h2>
              <p>
                Vibration RMS ·{" "}
                {data.overview.trend_asset || "No asset selected"}
              </p>
            </div>
            <button
              className="subtle-select"
              onClick={() => navigate("monitor")}
            >
              Last 7 hours <ChevronDown size={13} />
            </button>
          </div>
          <div className="trend-summary">
            <strong>
              {data.overview.trend.at(-1)?.vibration.toFixed(2) || "—"}
              <span>mm/s</span>
            </strong>
            <span className="trend-warning">
              <ArrowUpRight size={14} /> Review trend
            </span>
            <div className="chart-legend">
              <i />
              Vibration <i className="dashed" />
              Demo review limit
            </div>
          </div>
          <Chart data={data.overview.trend} threshold={4.5} />
          <div className="chart-caption">
            <span>
              <Clock3 size={12} /> GST · Synthetic sensor replay
            </span>
            <button onClick={() => navigate("monitor")}>
              Explore monitoring <ArrowRight size={13} />
            </button>
          </div>
        </section>
        <section className="panel fleet-panel">
          <div className="panel-header">
            <div>
              <h2>Fleet health</h2>
              <p>Condition across permitted assets</p>
            </div>
            <Gauge size={18} className="muted" />
          </div>
          <div className="donut">
            <svg viewBox="0 0 170 170">
              <circle
                cx="85"
                cy="85"
                r="64"
                fill="none"
                stroke="#f2f2f2"
                strokeWidth="17"
              />
              {healthDist
                .filter((x) => x.value)
                .map((s) => {
                  const length =
                    (s.value / (stats.assets || 1)) * circumference;
                  const before = offset;
                  offset += length;
                  return (
                    <circle
                      key={s.label}
                      cx="85"
                      cy="85"
                      r="64"
                      fill="none"
                      stroke={s.color}
                      strokeWidth="17"
                      strokeDasharray={`${Math.max(0, length - 5)} ${circumference}`}
                      strokeDashoffset={-before}
                      transform="rotate(-90 85 85)"
                    />
                  );
                })}
            </svg>
            <div>
              <strong>
                {unknownAssets === stats.assets
                  ? "—"
                  : stats.assets
                    ? Math.round((stats.healthy / stats.assets) * 100)
                    : 0}
                {unknownAssets !== stats.assets && <small>%</small>}
              </strong>
              <span>
                {unknownAssets === stats.assets
                  ? "awaiting fresh readings"
                  : "of all assets healthy"}
              </span>
            </div>
          </div>
          <div className="health-legend">
            {healthDist.map((h) => (
              <div key={h.label}>
                <i style={{ background: h.color }} />
                <span>{h.label}</span>
                <strong>{h.value}</strong>
              </div>
            ))}
          </div>
          <div className="fleet-note">
            <ShieldCheck size={15} />
            <span>Condition index, not failure probability.</span>
          </div>
        </section>
      </div>
      <div className="section-heading">
        <div>
          <h2>
            Equipment spotlight{" "}
            <span className="count-pill">{priority.length}</span>
          </h2>
          <p>Prioritized by current condition and equipment context.</p>
        </div>
        <button onClick={() => navigate("assets")}>
          View asset registry <ArrowRight size={15} />
        </button>
      </div>
      <div className="asset-cards">
        {priority.map((a) => (
          <button
            className="asset-card"
            key={a.id}
            onClick={() => openAsset(a.id)}
          >
            <div className="asset-card-top">
              <span className="asset-tag">
                <Box size={13} />
                {a.tag}
              </span>
              <Badge value={a.status} />
            </div>
            <div className="asset-visual">
              <EquipmentArt kind={a.kind} />
              <div className={`health-chip ${a.status}`}>
                <span>CONDITION</span>
                <strong>
                  {a.health ?? "—"}
                  <small>/100</small>
                </strong>
              </div>
            </div>
            <h3>{a.name}</h3>
            <p>{a.location}</p>
            <div className="asset-card-readings">
              <span>
                <Waves size={14} />
                {a.reading?.vibration.toFixed(2) ?? "—"} <small>mm/s</small>
              </span>
              <span>
                <Thermometer size={14} />
                {a.reading?.temperature.toFixed(1) ?? "—"} <small>°C</small>
              </span>
              <ChevronRight size={17} />
            </div>
          </button>
        ))}
      </div>
      <div className="overview-bottom-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Recent condition episodes</h2>
              <p>Signals that deserve a closer look</p>
            </div>
            <button className="text-link" onClick={() => navigate("monitor")}>
              View all <ArrowRight size={13} />
            </button>
          </div>
          <div className="episode-list">
            {data.episodes.slice(0, 3).map((e) => (
              <button
                key={e.id}
                className="episode-row"
                onClick={() => openAsset(e.asset_id)}
              >
                <span className={`episode-icon ${e.severity}`}>
                  <TriangleAlert size={17} />
                </span>
                <div>
                  <strong>{e.title}</strong>
                  <small>
                    {e.asset_tag} <i>·</i> {age(e.created)}
                  </small>
                </div>
                <Badge value={e.state === "resolved" ? "healthy" : e.severity}>
                  {e.state === "resolved" ? "Resolved" : human(e.severity)}
                </Badge>
                <ChevronRight size={15} />
              </button>
            ))}
            {!data.episodes.length && (
              <Empty
                title="No condition episodes"
                description="Monitoring will record new abnormalities here."
              />
            )}
          </div>
        </section>
        <section className="intelligence-card">
          <div className="ai-orb">
            <Sparkles size={23} />
          </div>
          <span className="eyebrow">EVIDENCE BEFORE ACTION</span>
          <h2>
            Your next investigation
            <br />
            starts with a signal.
          </h2>
          <p>
            Connect sensor observations with source procedures and a controlled
            review.
          </p>
          <div className="intelligence-card-bottom">
            <span>
              <span className="signal-dot" />
              {stats.pending_reviews} awaiting review
            </span>
            <Button
              onClick={() => {
                const inv = data.investigations.find(
                  (x) => x.state === "awaiting_review",
                );
                if (inv) openInvestigation(inv.id);
                else navigate("intelligence");
              }}
              icon={ArrowUpRight}
            >
              Open investigations
            </Button>
          </div>
        </section>
      </div>
    </>
  );
}
