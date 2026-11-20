import { useState, useEffect } from "react";
import {
  Activity,
  Waves,
  Thermometer,
  Gauge,
  Droplets,
  CheckCircle2,
  Circle,
  Plus,
  Radio,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import {
  api,
  post,
  date,
  age,
  human,
  type Asset,
  type Reading,
  type Episode,
} from "../api";

import { Badge, Button, Empty, Chart } from "../components/ui";
import type { Run } from "../types";
export function MonitorPage({
  assets,
  episodes,
  live,
  setLive,
  scenario,
  setScenario,
  canOperate,
  refreshKey,
  openAsset,
  run,
}: {
  assets: Asset[];
  episodes: Episode[];
  live: boolean;
  setLive: (b: boolean) => void;
  scenario: string;
  setScenario: (s: string) => void;
  canOperate: boolean;
  refreshKey: number;
  openAsset: (id: string) => void;
  run: Run;
}) {
  const [selected, setSelected] = useState(assets[0]?.id || ""),
    [detail, setDetail] = useState<{
      asset: Asset;
      readings: Reading[];
    } | null>(null),
    [field, setField] = useState<
      "vibration" | "temperature" | "pressure" | "flow"
    >("vibration");
  const id = assets.some((a) => a.id === selected) ? selected : assets[0]?.id;
  useEffect(() => {
    if (id) {
      let stop = false;
      api<{ asset: Asset; readings: Reading[] }>("/assets/" + id).then((r) => {
        if (!stop) setDetail(r);
      });
      return () => {
        stop = true;
      };
    }
  }, [id, refreshKey]);
  return (
    <div className="monitor-experience">
      <section className="monitor-command monitor-photo-command">
        <img
          className="monitor-command-photo"
          src="/assets/photos/compressor-room.jpg"
          alt=""
        />
        <div className="monitor-command-copy">
          <span className="monitor-eyebrow">
            <Activity size={16} /> EQUIPMENT SIGNALS
          </span>
          <h2>Every reading. A clearer picture.</h2>
          <p>
            Select equipment, follow its signals and review the conditions that
            need attention.
          </p>
          <div className="monitor-command-meta">
            <span>{assets.length} assets in scope</span>
            <span>
              {episodes.filter((e) => e.state !== "resolved").length} open
              condition episodes
            </span>
            <span>{live ? "Demo replay running" : "Demo replay paused"}</span>
          </div>
        </div>
        <label className="monitor-equipment-picker">
          Equipment to monitor
          <select
            aria-label="Monitored equipment"
            value={id || ""}
            onChange={(e) => setSelected(e.target.value)}
          >
            {assets.map((a) => (
              <option key={a.id} value={a.id}>
                {a.tag} · {a.name}
              </option>
            ))}
          </select>
          <small>
            {assets.find((a) => a.id === id)?.site || "No equipment available"}
          </small>
          <span className="monitor-photo-note">
            Industrial installation · Illustrative photograph
          </span>
        </label>
      </section>
      <div className="simulation-banner">
        <div>
          <Radio size={22} />
          <span>
            <strong>Demo replay controls</strong>
            <small>
              Generate fresh simulated readings across the workspace. No plant
              equipment is connected.
            </small>
          </span>
        </div>
        <div>
          <select
            aria-label="Simulation scenario"
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
            disabled={!canOperate}
          >
            <option value="normal">Steady operation</option>
            <option value="bearing_trend">Rising vibration · P-101</option>
            <option value="recovery">Recovery trend · P-101</option>
          </select>
          <Button
            className={live ? "" : "primary"}
            icon={live ? Circle : Radio}
            disabled={!canOperate}
            onClick={() => setLive(!live)}
          >
            {live ? "Pause simulation" : "Start live demo"}
          </Button>
          <Button
            icon={Plus}
            disabled={!canOperate || live}
            onClick={() =>
              run(
                () => post("/simulation/tick", { scenario }),
                "New sensor snapshots generated.",
              )
            }
          >
            Step once
          </Button>
        </div>
      </div>
      <div className="signal-tabs" aria-label="Choose a signal to chart">
        {(["vibration", "temperature", "pressure", "flow"] as const).map(
          (f) => (
            <button
              key={f}
              aria-pressed={field === f}
              className={field === f ? "active" : ""}
              onClick={() => setField(f)}
            >
              <span className="monitor-signal-label">
                {(() => {
                  const Icon = {
                    vibration: Waves,
                    temperature: Thermometer,
                    pressure: Gauge,
                    flow: Droplets,
                  }[f];
                  return <Icon size={20} />;
                })()}
                {human(f)}
              </span>
              <strong>
                {detail?.asset.reading?.[f].toFixed(2) ?? "—"}{" "}
                <small>
                  {
                    {
                      vibration: "mm/s",
                      temperature: "°C",
                      pressure: "bar",
                      flow: "m³/h",
                    }[f]
                  }
                </small>
              </strong>
              <span className="monitor-signal-foot">
                {field === f ? "Viewing trend" : "View trend"}
              </span>
            </button>
          ),
        )}
      </div>
      <div className="monitor-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Signal history</h2>
              <p>Latest equipment snapshots · Times in GST</p>
            </div>
            <span className="monitor-chart-label">{human(field)} trend</span>
          </div>
          <Chart
            data={detail?.readings || []}
            field={field}
            large
            threshold={
              field === "vibration" ? detail?.asset.threshold : undefined
            }
          />
          <div className="chart-caption">
            <span>
              <span className={live ? "pulse-dot" : "signal-dot"} />
              {live ? "Updating every 5 seconds" : "Simulation paused"}
            </span>
            <button onClick={() => id && openAsset(id)}>
              Equipment details
            </button>
          </div>
        </section>
        <section
          className="panel signal-quality"
          data-state={
            !detail?.asset.reading
              ? "missing"
              : (detail.asset.freshness_seconds ?? Infinity) > 3600
                ? "stale"
                : detail.asset.reading.quality === "good"
                  ? "fresh"
                  : "review"
          }
        >
          <div className="panel-header">
            <div>
              <h2>Reading status</h2>
              <p>Latest snapshot</p>
            </div>
            <ShieldCheck size={19} />
          </div>
          <div className="quality-ring">
            {detail?.asset.reading?.quality === "good" &&
            (detail.asset.freshness_seconds ?? Infinity) <= 3600 ? (
              <CheckCircle2 size={42} />
            ) : (
              <TriangleAlert size={42} />
            )}
            <strong>
              {detail?.asset.reading?.quality === "good"
                ? (detail.asset.freshness_seconds ?? Infinity) > 3600
                  ? "Good sample · stale"
                  : "Good sample · fresh"
                : detail?.asset.reading
                  ? "Review quality"
                  : "No readings"}
            </strong>
            <p>
              {detail?.asset.reading
                ? (detail.asset.freshness_seconds ?? Infinity) > 3600
                  ? "This snapshot is over an hour old. Start the demo replay for fresh simulated readings, or review a new sensor frame in Sensor registry."
                  : "Recent equipment snapshot available. Review quality and operating context before deciding on maintenance."
                : "Ingest a snapshot to begin."}
            </p>
          </div>
          <dl>
            <div>
              <dt>Last reading</dt>
              <dd>
                {detail?.asset.reading
                  ? date(detail.asset.reading.timestamp, true) + " GST"
                  : "—"}
              </dd>
            </div>
            <div>
              <dt>Equipment freshness</dt>
              <dd>
                {!detail?.asset.reading
                  ? "Missing"
                  : (detail.asset.freshness_seconds ?? Infinity) > 3600
                    ? "Stale (over 1 hour)"
                    : "Within 1 hour"}
              </dd>
            </div>
            <div>
              <dt>Reading age</dt>
              <dd>
                {detail?.asset.freshness_seconds === null ||
                detail?.asset.freshness_seconds === undefined
                  ? "—"
                  : `${Math.floor(detail.asset.freshness_seconds / 60)} min`}
              </dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>
                {detail?.asset.source === "aligned_sensor_events"
                  ? "Aligned sensor events"
                  : "Snapshot / demo replay"}
              </dd>
            </div>
            <div>
              <dt>Schema</dt>
              <dd>Snapshot v1</dd>
            </div>
            <div>
              <dt>Channels</dt>
              <dd>4 per asset</dd>
            </div>
          </dl>
        </section>
      </div>
      <section className="panel monitor-episodes">
        <div className="panel-header">
          <div>
            <h2>Conditions to review</h2>
            <p>Acknowledge a signal, then investigate its context.</p>
          </div>
          <Badge value="warning">
            {episodes.filter((e) => e.state !== "resolved").length} open
          </Badge>
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Signal</th>
                <th>Equipment</th>
                <th>Severity</th>
                <th>State</th>
                <th>Detected</th>
                <th>Next action</th>
              </tr>
            </thead>
            <tbody>
              {episodes.map((e) => (
                <tr key={e.id}>
                  <td>
                    <strong>{e.title}</strong>
                  </td>
                  <td>
                    <button
                      className="text-link"
                      onClick={() => openAsset(e.asset_id)}
                    >
                      {e.asset_tag}
                    </button>
                  </td>
                  <td>
                    <Badge value={e.severity} />
                  </td>
                  <td>
                    <Badge value={e.state} />
                  </td>
                  <td>{age(e.created)}</td>
                  <td>
                    {e.state !== "resolved" && (
                      <Button
                        disabled={!canOperate}
                        onClick={() =>
                          run(
                            () =>
                              post(`/episodes/${e.id}/transition`, {
                                expected_version: e.version,
                                state:
                                  e.state === "active"
                                    ? "acknowledged"
                                    : e.state === "acknowledged"
                                      ? "under_review"
                                      : "resolved",
                              }),
                            "Condition episode updated.",
                          )
                        }
                      >
                        {e.state === "active"
                          ? "Acknowledge"
                          : e.state === "acknowledged"
                            ? "Review"
                            : "Resolve"}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!episodes.length && (
          <Empty
            title="No condition episodes"
            description="New abnormalities will appear as readings are evaluated."
          />
        )}
      </section>
    </div>
  );
}
