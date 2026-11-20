import { useEffect, useState, type FormEvent } from "react";
import {
  Activity,
  Check,
  Clock3,
  Radio,
  RefreshCw,
  Settings2,
  ShieldCheck,
} from "lucide-react";
import { SensorEvents } from "../components/SensorEvents";
import { api, date, human } from "../api";
import { Badge, Button, Empty, Modal, Spinner } from "../components/ui";

interface Sensor {
  id: string;
  asset_id: string;
  asset_tag: string;
  asset_name: string;
  site: string;
  channel: string;
  unit: string;
  label: string;
  expected_interval_seconds: number;
  stale_after_seconds: number;
  version: number;
  latest_value: number | null;
  latest_timestamp: number | null;
  age_seconds: number | null;
  quality: string;
  freshness: string;
  status: string;
  mapping: string;
}
interface Registry {
  items: Sensor[];
  summary: {
    sensors: number;
    fresh_good: number;
    stale: number;
    missing: number;
    quality_review: number;
  };
  mapping: string;
}
const displayUnit = (unit: string) =>
  ({ degC: "°C", "m3/h": "m³/h" })[unit] || unit;

export function SensorsPage({
  site,
  refreshKey,
  canConfigure,
  openAsset,
}: {
  site: string;
  refreshKey: number;
  canConfigure: boolean;
  openAsset: (id: string) => void;
}) {
  const [registry, setRegistry] = useState<Registry | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [reload, setReload] = useState(0),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all");
  const [inspecting, setInspecting] = useState<Sensor | null>(null);
  useEffect(() => {
    setInspecting(null);
  }, [site]);
  const [editing, setEditing] = useState<Sensor | null>(null),
    [label, setLabel] = useState(""),
    [interval, setInterval] = useState(300),
    [freshness, setFreshness] = useState(900),
    [busy, setBusy] = useState(false),
    [formError, setFormError] = useState(""),
    [message, setMessage] = useState("");
  useEffect(() => {
    let stop = false;
    setRegistry(null);
    setLoading(true);
    setError("");
    api<Registry>(
      "/sensors" + (site ? `?site=${encodeURIComponent(site)}` : ""),
    )
      .then((r) => {
        if (!stop) setRegistry(r);
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
  }, [site, refreshKey, reload]);
  function edit(sensor: Sensor) {
    setEditing(sensor);
    setLabel(sensor.label);
    setInterval(sensor.expected_interval_seconds);
    setFreshness(sensor.stale_after_seconds);
    setFormError("");
    setMessage("");
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!editing || busy) return;
    if (freshness < interval) {
      setFormError(
        "Freshness limit must be at least the expected reporting interval.",
      );
      return;
    }
    setBusy(true);
    setFormError("");
    try {
      await api<Sensor>(`/sensors/${editing.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_version: editing.version,
          label,
          expected_interval_seconds: interval,
          stale_after_seconds: freshness,
        }),
      });
      setEditing(null);
      setMessage("Sensor configuration saved and recorded in the audit trail.");
      setReload((x) => x + 1);
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const items =
    registry?.items.filter(
      (s) =>
        `${s.asset_tag} ${s.asset_name} ${s.label} ${s.id}`
          .toLowerCase()
          .includes(query.toLowerCase()) &&
        (filter === "all" ||
          (filter === "review" && s.status !== "healthy") ||
          (filter === "fresh" && s.status === "healthy")),
    ) || [];
  return (
    <div className="sensor-registry">
      <section className="lab-intro">
        <span className="lab-intro-icon">
          <Radio size={26} />
        </span>
        <div>
          <span className="brief-eyebrow">PHASE 3 · DATA FOUNDATION</span>
          <h2>Every channel has a stable identity.</h2>
          <p>
            Canonical units, versioned configuration and explicit data
            freshness.
          </p>
        </div>
        <span className="lab-method-tag">
          <ShieldCheck size={15} /> Existing telemetry preserved
        </span>
      </section>
      <div className="lab-metrics">
        {[
          ["Registered sensors", registry?.summary.sensors, Radio],
          ["Fresh & good quality", registry?.summary.fresh_good, Check],
          ["Stale channels", registry?.summary.stale, Clock3],
          ["Missing readings", registry?.summary.missing, Activity],
        ].map(([name, value, Icon]) => {
          const I = Icon as typeof Radio;
          return (
            <div key={String(name)}>
              <span>
                <I size={14} /> {String(name)}
              </span>
              <strong>{loading ? "—" : String(value ?? "—")}</strong>
              <small>
                {name === "Fresh & good quality"
                  ? "Uses each sensor’s configured limit"
                  : "Within your permitted sites"}
              </small>
            </div>
          );
        })}
      </div>
      {message && (
        <div className="local-note" role="status">
          <Check size={17} />
          {message}
        </div>
      )}
      {error && (
        <div className="error-banner" role="alert">
          {error}
          <Button onClick={() => setReload((x) => x + 1)}>Retry</Button>
        </div>
      )}
      <section className="panel sensor-panel">
        <div className="panel-header">
          <div>
            <h2>Sensor registry</h2>
            <p>
              Quality describes the sample. Freshness describes its age. Both
              matter.
            </p>
          </div>
          <Button icon={RefreshCw} onClick={() => setReload((x) => x + 1)}>
            Refresh sensors
          </Button>
        </div>
        <div className="table-toolbar">
          <div className="tabs">
            {[
              ["all", "All sensors"],
              ["review", "Needs review"],
              ["fresh", "Fresh & good"],
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
            aria-label="Search sensors"
            value={query}
            placeholder="Search tag, label or sensor ID…"
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {loading ? (
          <Spinner />
        ) : !items.length ? (
          <Empty
            title="No matching sensors"
            description="Try another filter or register equipment to create its channel identities."
          />
        ) : (
          <div className="table-scroll">
            <table className="data-table sensor-table">
              <thead>
                <tr>
                  <th>Sensor / equipment</th>
                  <th>Channel & unit</th>
                  <th>Latest snapshot value</th>
                  <th>Sample quality</th>
                  <th>Freshness</th>
                  <th>Configuration</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <strong>{s.label}</strong>
                      <button
                        className="lab-asset-link"
                        onClick={() => openAsset(s.asset_id)}
                      >
                        {s.asset_tag} · {s.asset_name}
                      </button>
                      <code title={s.id}>
                        {s.id.slice(0, 8)}…{s.id.slice(-4)}
                      </code>
                    </td>
                    <td>
                      <strong>{human(s.channel)}</strong>
                      <small>{displayUnit(s.unit)}</small>
                    </td>
                    <td>
                      <strong className="numeric">
                        {s.latest_value?.toFixed(2) ?? "—"}
                      </strong>
                      <small>
                        {s.latest_timestamp
                          ? date(s.latest_timestamp, true) + " GST"
                          : "No snapshot"}
                      </small>
                    </td>
                    <td>
                      <Badge
                        value={
                          s.quality === "good"
                            ? "healthy"
                            : s.quality === "unknown"
                              ? "unknown"
                              : "warning"
                        }
                      >
                        {human(s.quality)}
                      </Badge>
                    </td>
                    <td>
                      <Badge
                        value={
                          s.freshness === "fresh"
                            ? "healthy"
                            : s.freshness === "missing"
                              ? "unknown"
                              : "warning"
                        }
                      >
                        {human(s.freshness)}
                      </Badge>
                      <small>
                        {s.age_seconds === null
                          ? "Awaiting telemetry"
                          : `${Math.floor(s.age_seconds / 60)} min old`}
                      </small>
                    </td>
                    <td>
                      <strong className="normal-weight">
                        Every {s.expected_interval_seconds}s
                      </strong>
                      <small>
                        Stale after {s.stale_after_seconds}s · v{s.version}
                      </small>
                    </td>
                    <td>
                      <Button
                        onClick={() => setInspecting(s)}
                        aria-label={`Inspect events ${s.asset_tag} ${s.channel}`}
                      >
                        Inspect events
                      </Button>
                      <button
                        className="btn"
                        onClick={() => edit(s)}
                        disabled={!canConfigure}
                        aria-label={`Configure ${s.asset_tag} ${s.channel}`}
                      >
                        <Settings2 size={14} /> Configure
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="lab-method-note">
          <ShieldCheck size={17} />
          <span>
            {registry?.mapping ||
              "The registry maps four canonical channels to each equipment snapshot."}{" "}
            Independent readings and unit conversions are available through
            Inspect events. Site boundaries are inherited from the linked
            equipment.
          </span>
        </div>
      </section>
      {inspecting && (
        <SensorEvents
          key={inspecting.id}
          sensor={inspecting}
          canWrite={canConfigure}
          onClose={() => setInspecting(null)}
        />
      )}
      {editing && (
        <Modal
          title="Configure sensor"
          description={`${editing.asset_tag} · ${human(editing.channel)} · ${displayUnit(editing.unit)}`}
          onClose={() => {
            if (!busy) setEditing(null);
          }}
        >
          <div className="sensor-identity">
            <small>PERMANENT SENSOR ID</small>
            <code>{editing.id}</code>
            <span>
              Mapping: {editing.mapping} · configuration version{" "}
              {editing.version}
            </span>
          </div>
          <form onSubmit={save}>
            <label>
              Sensor label
              <input
                required
                minLength={1}
                maxLength={100}
                value={label}
                disabled={busy}
                onChange={(e) => setLabel(e.target.value)}
              />
            </label>
            <div className="form-grid">
              <label>
                Expected reporting interval (seconds)
                <input
                  type="number"
                  required
                  min={1}
                  max={86400}
                  step={1}
                  value={interval}
                  disabled={busy}
                  onChange={(e) => setInterval(Number(e.target.value))}
                />
              </label>
              <label>
                Stale after (seconds)
                <input
                  type="number"
                  required
                  min={interval}
                  max={604800}
                  step={1}
                  value={freshness}
                  disabled={busy}
                  onChange={(e) => setFreshness(Number(e.target.value))}
                />
              </label>
            </div>
            <p className="lab-footnote">
              Changing this configuration does not change units, stored values,
              equipment thresholds or the current one-hour equipment-condition
              rule.
            </p>
            {formError && (
              <p className="form-error" role="alert">
                {formError}
              </p>
            )}
            <div className="modal-actions">
              <Button disabled={busy} onClick={() => setEditing(null)}>
                Cancel
              </Button>
              <Button
                className="primary"
                type="submit"
                disabled={busy}
                icon={Check}
              >
                {busy ? "Saving…" : "Save configuration"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
