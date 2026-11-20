import { useEffect, useState, type FormEvent } from "react";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Check,
  Download,
  FlaskConical,
  RefreshCw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  TriangleAlert,
} from "lucide-react";
import { api, post, date, human, type Asset, type Reading } from "../api";
import { Badge, Button, Empty, Modal, Spinner } from "../components/ui";

type Field = "vibration" | "temperature" | "pressure" | "flow";
const fields: Field[] = ["vibration", "temperature", "pressure", "flow"];
const units: Record<Field, string> = {
  vibration: "mm/s",
  temperature: "°C",
  pressure: "bar",
  flow: "m³/h",
};
const bounds: Record<Field, [number, number]> = {
  vibration: [0, 200],
  temperature: [-100, 500],
  pressure: [0, 1000],
  flow: [0, 100000],
};
const palette = ["#3478df", "#36a692", "#9b76cf"];
interface Triage {
  asset: Asset;
  score: number;
  components: Record<string, number>;
  band: string;
  needs_data_review: boolean;
  active_episodes: number;
  overdue_orders: number;
  samples: number;
  quality_percent: number | null;
  reasons: string[];
}
interface Fleet {
  generated_at: number;
  hours: number;
  method: string;
  limitation: string;
  summary: {
    assets: number;
    data_review: number;
    urgent: number;
    overdue_orders: number;
    samples: number;
  };
  items: Triage[];
}
interface Channel {
  min: number | null;
  max: number | null;
  mean: number | null;
  observed_change_per_hour: number | null;
  constant_last_12: boolean;
}
interface Series {
  asset: Asset;
  readings: Reading[];
  statistics: {
    samples: number;
    good_samples: number;
    channels: Record<Field, Channel>;
  };
}
interface ScenarioResult {
  asset_id: string;
  asset_tag: string;
  site: string;
  baseline: Reading;
  baseline_stale: boolean;
  inputs: Record<Field, number>;
  baseline_condition: { health: number; status: string };
  scenario_condition: {
    health: number;
    status: string;
    anomaly: boolean;
    anomaly_score: number;
    threshold_exceeded: boolean;
  };
  health_delta: number;
  model_version: string;
  method: string;
  calculated_at: number;
  limitation: string;
}
interface Saved {
  id: string;
  title: string;
  actor: string;
  created: number;
  result: ScenarioResult;
}

function ComparisonChart({
  series,
  field,
}: {
  series: Series[];
  field: Field;
}) {
  const good = series.map((s) =>
    s.readings.filter((r) => r.quality === "good"),
  );
  const all = good.flat();
  if (!all.length)
    return (
      <Empty
        title="No good-quality readings in this window"
        description="Choose another window or ingest valid telemetry."
      />
    );
  const times = all.map((r) => r.timestamp),
    values = all.map((r) => r[field]);
  const start = Math.min(...times),
    end = Math.max(...times);
  const low = Math.min(...values),
    high = Math.max(...values),
    span = high - low || 1;
  const min = low - span * 0.12,
    max = high + span * 0.12;
  const x = (t: number) => 55 + ((t - start) / (end - start || 1)) * 760;
  const y = (v: number) => 220 - ((v - min) / (max - min)) * 185;
  return (
    <div className="lab-comparison-chart">
      <svg
        viewBox="0 0 850 260"
        role="img"
        aria-label={`${human(field)} comparison in ${units[field]}, shared time and value axes`}
      >
        {[0, 1, 2, 3].map((i) => {
          const v = min + ((max - min) * i) / 3;
          return (
            <g key={i}>
              <line
                x1="55"
                x2="815"
                y1={y(v)}
                y2={y(v)}
                stroke="#e3eaf4"
                strokeDasharray="4 5"
              />
              <text
                x="44"
                y={y(v) + 4}
                textAnchor="end"
                fill="#7387a4"
                fontSize="12"
              >
                {v.toFixed(1)}
              </text>
            </g>
          );
        })}
        {good.map((samples, i) => (
          <g key={series[i].asset.id}>
            <path
              d={samples
                .map(
                  (r, j) => `${j ? "L" : "M"}${x(r.timestamp)},${y(r[field])}`,
                )
                .join(" ")}
              stroke={palette[i]}
              strokeWidth="2.4"
              fill="none"
              strokeLinejoin="round"
            />
            <circle
              cx={x(samples.at(-1)?.timestamp || start)}
              cy={y(samples.at(-1)?.[field] || 0)}
              r={samples.length ? 3 : 0}
              fill={palette[i]}
            />
          </g>
        ))}
        <text x="55" y="249" fill="#7387a4" fontSize="12">
          {date(start, true)}
        </text>
        <text x="815" y="249" textAnchor="end" fill="#7387a4" fontSize="12">
          {date(end, true)}
        </text>
      </svg>
      <div className="lab-chart-legend">
        {series.map((s, i) => (
          <span key={s.asset.id}>
            <i style={{ background: palette[i] }} />
            {s.asset.tag} · {s.statistics.good_samples} good samples
          </span>
        ))}
      </div>
    </div>
  );
}

function ScenarioSummary({ result }: { result: ScenarioResult }) {
  return (
    <>
      {result.baseline_stale && (
        <div className="local-note">
          <TriangleAlert size={17} />
          <span>
            Historical baseline: this reading is over one hour old. This is an
            exploratory comparison, not current equipment health.
          </span>
        </div>
      )}
      <div className="scenario-score-grid">
        <div>
          <small>Baseline condition</small>
          <strong>
            {result.baseline_condition.health}
            <em>/100</em>
          </strong>
          <Badge value={result.baseline_condition.status} />
        </div>
        <ArrowUpRight size={22} />
        <div>
          <small>What-if condition</small>
          <strong>
            {result.scenario_condition.health}
            <em>/100</em>
          </strong>
          <Badge value={result.scenario_condition.status} />
        </div>
      </div>
      <div className="scenario-facts">
        <span>
          Condition change{" "}
          <b>
            {result.health_delta > 0 ? "+" : ""}
            {result.health_delta} points
          </b>
        </span>
        <span>
          Demo vibration limit{" "}
          <b>
            {result.scenario_condition.threshold_exceeded
              ? "Exceeded"
              : "Within limit"}
          </b>
        </span>
        <span>
          Synthetic anomaly model{" "}
          <b>{result.scenario_condition.anomaly ? "Flagged" : "Not flagged"}</b>
        </span>
      </div>
      <p className="lab-footnote">
        Condition uses vibration and temperature penalties; pressure and flow
        also inform the synthetic anomaly model. This does not simulate physical
        degradation.
      </p>
    </>
  );
}

export function ReliabilityPage({
  assets,
  site,
  refreshKey,
  canSave,
  openAsset,
}: {
  assets: Asset[];
  site: string;
  refreshKey: number;
  canSave: boolean;
  openAsset: (id: string) => void;
}) {
  const [tab, setTab] = useState("triage"),
    [hours, setHours] = useState(168),
    [fleet, setFleet] = useState<Fleet | null>(null),
    [history, setHistory] = useState<Saved[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [reload, setReload] = useState(0);
  const [filter, setFilter] = useState("all"),
    [query, setQuery] = useState(""),
    [expanded, setExpanded] = useState("");
  const [selected, setSelected] = useState<string[]>(
      assets.slice(0, 2).map((a) => a.id),
    ),
    [comparison, setComparison] = useState<{
      series: Series[];
      note: string;
    } | null>(null),
    [compareError, setCompareError] = useState(""),
    [field, setField] = useState<Field>("vibration");
  const [scenarioAsset, setScenarioAsset] = useState(assets[0]?.id || ""),
    [inputs, setInputs] = useState<Record<Field, number>>({
      vibration: 0,
      temperature: 0,
      pressure: 0,
      flow: 0,
    }),
    [result, setResult] = useState<ScenarioResult | null>(null),
    [scenarioError, setScenarioError] = useState(""),
    [scenarioBusy, setScenarioBusy] = useState(false),
    [title, setTitle] = useState("Operating condition review"),
    [saveMessage, setSaveMessage] = useState(""),
    [saved, setSaved] = useState<Saved | null>(null);
  const selectedIds = selected
    .filter((id) => assets.some((a) => a.id === id))
    .join(",");
  const asset = assets.find((a) => a.id === scenarioAsset) || assets[0];
  const baselineTimestamp = asset?.reading?.timestamp;
  const scope = `hours=${hours}${site ? `&site=${encodeURIComponent(site)}` : ""}`;
  useEffect(() => {
    let stop = false;
    setLoading(true);
    setError("");
    setFleet(null);
    setHistory([]);
    Promise.all([
      api<Fleet>("/lab/fleet?" + scope),
      api<Saved[]>(
        "/lab/scenarios" + (site ? `?site=${encodeURIComponent(site)}` : ""),
      ),
    ])
      .then(([f, h]) => {
        if (!stop) {
          setFleet(f);
          setHistory(h);
        }
      })
      .catch((e) => {
        if (!stop) setError(e.message);
      })
      .finally(() => {
        if (!stop) setLoading(false);
      });
    return () => {
      stop = true;
    };
  }, [scope, refreshKey, reload]);
  useEffect(() => {
    let stop = false;
    setComparison(null);
    setCompareError("");
    if (tab !== "compare" || !selectedIds) return;
    const params = new URLSearchParams({ hours: String(hours) });
    selectedIds.split(",").forEach((id) => params.append("ids", id));
    api<{ series: Series[]; note: string }>("/lab/compare?" + params)
      .then((r) => {
        if (!stop) setComparison(r);
      })
      .catch((e) => {
        if (!stop) setCompareError(e.message);
      });
    return () => {
      stop = true;
    };
  }, [tab, selectedIds, hours, refreshKey]);
  useEffect(() => {
    setResult(null);
    setScenarioError("");
    setSaveMessage("");
    setInputs({
      vibration: asset?.reading?.vibration || 0,
      temperature: asset?.reading?.temperature || 0,
      pressure: asset?.reading?.pressure || 0,
      flow: asset?.reading?.flow || 0,
    });
  }, [asset?.id, baselineTimestamp]);
  async function simulate(event: FormEvent) {
    event.preventDefault();
    if (!asset || !baselineTimestamp || scenarioBusy) return;
    setScenarioBusy(true);
    setScenarioError("");
    setSaveMessage("");
    setResult(null);
    try {
      setResult(
        await post<ScenarioResult>("/lab/simulate", {
          asset_id: asset.id,
          baseline_timestamp: baselineTimestamp,
          baseline_signature: asset.reading?.fingerprint,
          ...inputs,
        }),
      );
    } catch (e) {
      setScenarioError((e as Error).message);
    } finally {
      setScenarioBusy(false);
    }
  }
  async function save() {
    if (!result || !asset || scenarioBusy) return;
    setScenarioBusy(true);
    setScenarioError("");
    try {
      await post<Saved>("/lab/scenarios", {
        asset_id: asset.id,
        baseline_timestamp: result.baseline.timestamp,
        baseline_signature: result.baseline.fingerprint,
        ...result.inputs,
        title: title.trim(),
      });
      setSaveMessage("Scenario saved to the audit trail.");
      setReload((x) => x + 1);
    } catch (e) {
      setScenarioError((e as Error).message);
    } finally {
      setScenarioBusy(false);
    }
  }
  const items =
    fleet?.items.filter(
      (i) =>
        (filter === "all" ||
          (filter === "data" && i.needs_data_review) ||
          (filter === "urgent" && i.band === "Urgent")) &&
        `${i.asset.tag} ${i.asset.name}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    ) || [];
  return (
    <div className="reliability-lab">
      <section className="lab-intro">
        <div className="lab-intro-icon">
          <FlaskConical size={27} />
        </div>
        <div>
          <span className="brief-eyebrow">ANALYZE · COMPARE · EXPLORE</span>
          <h2>Turn operating data into a clearer next step.</h2>
          <p>
            Explainable priorities, shared-axis trends and auditable what-if
            scenarios.
          </p>
        </div>
        <span className="lab-method-tag">
          <ShieldCheck size={14} /> Human decisions remain in control
        </span>
      </section>
      <div className="lab-navigation">
        <div role="tablist" aria-label="Reliability tools">
          {[
            ["triage", "Fleet triage", Activity],
            ["compare", "Compare assets", BarChart3],
            ["scenario", "Scenario lab", SlidersHorizontal],
          ].map(([id, label, Icon]) => {
            const I = Icon as typeof Activity;
            return (
              <button
                key={String(id)}
                role="tab"
                aria-selected={tab === id}
                onClick={() => setTab(String(id))}
              >
                <I size={17} />
                {String(label)}
              </button>
            );
          })}
        </div>
        <div className="lab-window">
          <label>
            Data window
            <select
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
            >
              <option value={24}>Last 24 hours</option>
              <option value={168}>Last 7 days</option>
              <option value={720}>Last 30 days</option>
            </select>
          </label>
          <button
            className="icon-btn"
            aria-label="Refresh reliability data"
            onClick={() => setReload((x) => x + 1)}
          >
            <RefreshCw size={17} />
          </button>
        </div>
      </div>
      {error && (
        <div className="error-banner" role="alert">
          <TriangleAlert size={18} />
          {error}
          <Button onClick={() => setReload((x) => x + 1)}>Retry</Button>
        </div>
      )}
      {tab === "triage" && (
        <>
          <div className="lab-metrics">
            {[
              ["Assets in scope", fleet?.summary.assets, "Equipment registry"],
              [
                "Need data review",
                fleet?.summary.data_review,
                "Freshness & quality",
              ],
              ["Urgent triage", fleet?.summary.urgent, "Heuristic score ≥65"],
              [
                "Overdue work",
                fleet?.summary.overdue_orders,
                "Open orders past due in GST",
              ],
            ].map(([label, value, caption]) => (
              <div key={String(label)}>
                <span>{label}</span>
                <strong>{loading ? "—" : (value ?? "—")}</strong>
                <small>{caption}</small>
              </div>
            ))}
          </div>
          <section className="panel lab-triage-panel">
            <div className="panel-header">
              <div>
                <h2>Maintenance priority queue</h2>
                <p>
                  Missing condition data appears first. Scores rank the
                  remaining operational context.
                </p>
              </div>
              <a className="btn" href={"/api/lab/export.csv?" + scope}>
                <Download size={15} /> Export brief
              </a>
            </div>
            <div className="table-toolbar">
              <div className="tabs">
                {[
                  ["all", "All assets"],
                  ["data", "Data review"],
                  ["urgent", "Urgent"],
                ].map(([v, l]) => (
                  <button
                    key={v}
                    className={filter === v ? "active" : ""}
                    onClick={() => setFilter(v)}
                  >
                    {l}
                  </button>
                ))}
              </div>
              <input
                aria-label="Filter triage assets"
                placeholder="Search tag or equipment…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            {loading ? (
              <Spinner />
            ) : !items.length ? (
              <Empty
                title="No assets match this queue"
                description="Change the filter or choose another permitted site."
              />
            ) : (
              items.map((i) => (
                <div className="lab-triage-row" key={i.asset.id}>
                  <div className="lab-triage-main">
                    <div>
                      <button
                        className="lab-asset-link"
                        onClick={() => openAsset(i.asset.id)}
                      >
                        {i.asset.tag}
                        <ArrowUpRight size={14} />
                      </button>
                      <h3>{i.asset.name}</h3>
                      <small>
                        {i.asset.site} · {i.asset.criticality} criticality
                      </small>
                    </div>
                    <div className="lab-triage-score">
                      <strong>
                        {i.score}
                        <small>/100</small>
                      </strong>
                      <span>{i.band}</span>
                      <div className="lab-score-bar">
                        {Object.entries(i.components).map(([k, v], n) => (
                          <i
                            key={k}
                            style={{
                              width: `${v}%`,
                              background: [
                                "#3478df",
                                "#8f79cf",
                                "#dea954",
                                "#d78092",
                              ][n],
                            }}
                            title={`${human(k)}: ${v}`}
                          />
                        ))}
                      </div>
                    </div>
                    <div className="lab-data-cell">
                      <span>Good-quality samples</span>
                      <b>
                        {i.quality_percent === null
                          ? "No samples"
                          : `${i.quality_percent}%`}
                      </b>
                      <small>
                        {i.samples} samples in window ·{" "}
                        {i.asset.freshness_seconds === null
                          ? "No latest reading"
                          : `${Math.floor(i.asset.freshness_seconds / 60)} min since latest`}
                      </small>
                    </div>
                    <button
                      className="text-link"
                      aria-expanded={expanded === i.asset.id}
                      onClick={() =>
                        setExpanded(expanded === i.asset.id ? "" : i.asset.id)
                      }
                    >
                      Explain score
                    </button>
                  </div>
                  {expanded === i.asset.id && (
                    <ul className="lab-score-reasons">
                      {i.reasons.map((r) => (
                        <li key={r}>
                          <Check size={13} />
                          {r}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))
            )}
            <div className="lab-method-note">
              <ShieldCheck size={17} />
              <span>
                <b>Transparent scoring:</b> condition 0–40 + criticality 0–20 +
                active episodes 0–20 + overdue work 0–20. Missing condition is
                marked for data review, never treated as healthy. Method:{" "}
                {fleet?.method || "triage-v1"}.
              </span>
            </div>
          </section>
        </>
      )}
      {tab === "compare" && (
        <section className="panel lab-compare-panel">
          <div className="panel-header">
            <div>
              <h2>Compare equipment on shared axes</h2>
              <p>
                Select up to three assets. Every plotted point comes from
                recorded telemetry.
              </p>
            </div>
          </div>
          <div className="lab-asset-selectors">
            {assets.map((a) => (
              <label key={a.id}>
                <input
                  type="checkbox"
                  checked={selectedIds.split(",").includes(a.id)}
                  disabled={
                    !selectedIds.split(",").includes(a.id) &&
                    selectedIds.split(",").filter(Boolean).length >= 3
                  }
                  onChange={(e) =>
                    setSelected(
                      e.target.checked
                        ? [
                            ...selected.filter((id) =>
                              assets.some((x) => x.id === id),
                            ),
                            a.id,
                          ]
                        : selected.filter((id) => id !== a.id),
                    )
                  }
                />
                <span>
                  {a.tag}
                  <small>{a.kind}</small>
                </span>
              </label>
            ))}
          </div>
          <div className="tabs lab-signal-tabs">
            {fields.map((f) => (
              <button
                key={f}
                className={field === f ? "active" : ""}
                onClick={() => setField(f)}
              >
                {human(f)} <small>{units[f]}</small>
              </button>
            ))}
          </div>
          {compareError ? (
            <p className="form-error" role="alert">
              {compareError}
            </p>
          ) : !selectedIds ? (
            <Empty
              title="Choose equipment to compare"
              description="Select one to three assets above."
            />
          ) : !comparison ? (
            <Spinner />
          ) : (
            <>
              <ComparisonChart series={comparison.series} field={field} />
              <div className="lab-comparison-stats">
                {comparison.series.map((s, i) => {
                  const c = s.statistics.channels[field];
                  return (
                    <div
                      key={s.asset.id}
                      style={{ borderTopColor: palette[i] }}
                    >
                      <h3>
                        {s.asset.tag} <Badge value={s.asset.status} />
                      </h3>
                      <p>{s.asset.name}</p>
                      <dl>
                        <div>
                          <dt>Window mean</dt>
                          <dd>
                            {c.mean?.toFixed(2) ?? "—"} {units[field]}
                          </dd>
                        </div>
                        <div>
                          <dt>Observed drift / hour</dt>
                          <dd>
                            {c.observed_change_per_hour?.toFixed(3) ?? "—"}
                          </dd>
                        </div>
                        <div>
                          <dt>Good / sampled</dt>
                          <dd>
                            {s.statistics.good_samples} / {s.statistics.samples}
                          </dd>
                        </div>
                      </dl>
                      {c.constant_last_12 && (
                        <p className="lab-constant-note">
                          Last 12 good values are constant. Inspect sensor
                          behavior and operating context.
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
              <p className="lab-footnote">
                {comparison.note} Lines connect retained samples; missing
                intervals are not interpolated as measurements.
              </p>
            </>
          )}
        </section>
      )}
      {tab === "scenario" && (
        <>
          <div className="lab-scenario-layout">
            <section className="panel lab-scenario-inputs">
              <div className="panel-header">
                <div>
                  <h2>Explore an operating scenario</h2>
                  <p>
                    Adjust hypothetical inputs. No telemetry or equipment
                    settings are changed.
                  </p>
                </div>
              </div>
              {!asset ? (
                <Empty
                  title="No equipment available"
                  description="Choose a permitted site with registered assets."
                />
              ) : (
                <form onSubmit={simulate}>
                  <label>
                    Equipment
                    <select
                      value={asset.id}
                      disabled={scenarioBusy}
                      onChange={(e) => setScenarioAsset(e.target.value)}
                    >
                      {assets.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.tag} · {a.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <p className="lab-footnote">
                    Baseline:{" "}
                    {baselineTimestamp
                      ? date(baselineTimestamp, true) + " GST"
                      : "No reading"}
                    . Comparison uses this exact recorded snapshot.
                  </p>
                  <div className="lab-input-grid">
                    {fields.map((f) => (
                      <label key={f}>
                        {human(f)} ({units[f]})
                        <input
                          type="number"
                          required
                          step="any"
                          min={bounds[f][0]}
                          max={bounds[f][1]}
                          value={inputs[f]}
                          disabled={scenarioBusy}
                          onChange={(e) => {
                            setInputs({
                              ...inputs,
                              [f]: Number(e.target.value),
                            });
                            setResult(null);
                            setSaveMessage("");
                          }}
                        />
                      </label>
                    ))}
                  </div>
                  <Button
                    className="primary"
                    type="submit"
                    icon={FlaskConical}
                    disabled={scenarioBusy || !baselineTimestamp}
                  >
                    {scenarioBusy ? "Calculating…" : "Run what-if scenario"}
                  </Button>
                </form>
              )}
            </section>
            <section className="panel lab-scenario-results">
              <div className="panel-header">
                <div>
                  <h2>Scenario assessment</h2>
                  <p>Computed comparison against your recorded baseline.</p>
                </div>
                <Badge value="simulation">What-if</Badge>
              </div>
              {scenarioError && (
                <p className="form-error" role="alert">
                  {scenarioError}
                </p>
              )}
              {result ? (
                <>
                  <ScenarioSummary result={result} />
                  <div className="lab-save-scenario">
                    <label>
                      Scenario name
                      <input
                        value={title}
                        minLength={3}
                        maxLength={120}
                        disabled={scenarioBusy}
                        onChange={(e) => {
                          setTitle(e.target.value);
                          setSaveMessage("");
                        }}
                      />
                    </label>
                    <Button
                      icon={Save}
                      disabled={
                        !canSave ||
                        scenarioBusy ||
                        title.trim().length < 3 ||
                        !!saveMessage
                      }
                      onClick={save}
                    >
                      Save to audit trail
                    </Button>
                    {!canSave && (
                      <p className="lab-footnote">
                        Saving requires Engineer or Admin. You can still explore
                        scenarios.
                      </p>
                    )}
                    {saveMessage && (
                      <p className="lab-save-success" role="status">
                        <Check size={15} />
                        {saveMessage}
                      </p>
                    )}
                  </div>
                </>
              ) : (
                <Empty
                  title="Start with a what-if"
                  description="Choose an asset, adjust the values and run the assessment."
                />
              )}
            </section>
          </div>
          <section className="panel lab-history">
            <div className="panel-header">
              <div>
                <h2>Saved scenario history</h2>
                <p>
                  Latest 25 records for permitted sites. Each preserves its
                  inputs, baseline and method.
                </p>
              </div>
            </div>
            {!history.length ? (
              <Empty
                title="No saved scenarios yet"
                description="Save a scenario after reviewing its result."
              />
            ) : (
              history.map((h) => (
                <button
                  className="lab-history-row"
                  key={h.id}
                  onClick={() => setSaved(h)}
                >
                  <span className="role-card-icon">
                    <FlaskConical size={19} />
                  </span>
                  <span>
                    <strong>{h.title}</strong>
                    <small>
                      {h.result.asset_tag} · {h.actor} · {date(h.created, true)}{" "}
                      GST
                    </small>
                  </span>
                  <span>
                    {h.result.health_delta > 0 ? "+" : ""}
                    {h.result.health_delta} points
                  </span>
                  <ArrowUpRight size={17} />
                </button>
              ))
            )}
          </section>
        </>
      )}
      <div className="lab-boundary">
        <ShieldCheck size={17} />
        <p>
          Decision support only. These heuristics and the synthetic anomaly
          model do not establish failure probability, remaining useful life or
          validated physical simulation.
        </p>
      </div>
      {saved && (
        <Modal
          title={saved.title}
          description={`${saved.result.asset_tag} · ${saved.actor} · ${date(saved.created, true)} GST`}
          onClose={() => setSaved(null)}
        >
          <ScenarioSummary result={saved.result} />
          <h3>Preserved scenario inputs</h3>
          <dl>
            {fields.map((f) => (
              <div key={f}>
                <dt>{human(f)}</dt>
                <dd>
                  {saved.result.inputs[f]} {units[f]}
                </dd>
              </div>
            ))}
          </dl>
          <p className="lab-footnote">
            Baseline: {date(saved.result.baseline.timestamp, true)} GST ·{" "}
            {saved.result.method} · {saved.result.model_version}
          </p>
        </Modal>
      )}
    </div>
  );
}
