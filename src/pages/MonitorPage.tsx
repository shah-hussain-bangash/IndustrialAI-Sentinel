import { useState, useEffect } from "react";
import {
  ArrowRight,
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
    <>
      <div className="simulation-banner">
        <div>
          <Radio size={22} />
          <span>
            <strong>Sensor simulation studio</strong>
            <small>
              Generate readings and test condition changes. No plant equipment
              is connected.
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
      <div className="monitor-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Operating signals</h2>
              <p>Four-channel snapshots · GST</p>
            </div>
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
          </div>
          <div className="signal-tabs">
            {(["vibration", "temperature", "pressure", "flow"] as const).map(
              (f) => (
                <button
                  key={f}
                  className={field === f ? "active" : ""}
                  onClick={() => setField(f)}
                >
                  <span>{human(f)}</span>
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
                </button>
              ),
            )}
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
              View asset context <ArrowRight size={13} />
            </button>
          </div>
        </section>
        <section className="panel signal-quality">
          <div className="panel-header">
            <div>
              <h2>Signal quality</h2>
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
                ? "Inspect freshness and operating context before a maintenance decision."
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
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Condition episode queue</h2>
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
    </>
  );
}
