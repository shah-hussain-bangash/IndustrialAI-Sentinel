import { useEffect, useState, type FormEvent } from "react";
import { Activity, Check, RefreshCw } from "lucide-react";
import { SensorDataReview } from "./SensorDataReview";
import { SnapshotAlignment } from "./SnapshotAlignment";
import { api, date } from "../api";
import { Button, Empty, Modal, Spinner } from "./ui";

interface EventRow {
  id: string;
  message_id: string;
  observed_at: number;
  received_at: number;
  raw_value: number;
  raw_unit: string;
  value: number;
  unit: string;
  quality: string;
  source: string;
  conversion: string;
}
interface History {
  items: EventRow[];
  supported_units: string[];
  canonical_unit: string;
  bounds: number[];
  scope: string;
}
const localTime = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 19);
};

export function SensorEvents({
  sensor,
  canWrite,
  onClose,
}: {
  sensor: { id: string; asset_id: string; asset_tag: string; label: string };
  canWrite: boolean;
  onClose: () => void;
}) {
  const [tab, setTab] = useState("events");
  const [data, setData] = useState<History | null>(null),
    [loading, setLoading] = useState(true);
  const [error, setError] = useState(""),
    [receipt, setReceipt] = useState("");
  const [value, setValue] = useState(""),
    [unit, setUnit] = useState("");
  const [observed, setObserved] = useState(localTime),
    [quality, setQuality] = useState("good");
  const [message, setMessage] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false),
    [reload, setReload] = useState(0);
  useEffect(() => {
    let stop = false;
    setLoading(true);
    api<History>(
      `/sensor-events?sensor_id=${encodeURIComponent(sensor.id)}&limit=50`,
    )
      .then((r) => {
        if (!stop) {
          setData(r);
          setUnit((u) => u || r.canonical_unit);
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
  }, [sensor.id, reload]);
  async function save(e: FormEvent) {
    e.preventDefault();
    if (busy || !value.trim()) return;
    setBusy(true);
    setError("");
    setReceipt("");
    try {
      const r = await api<{
        inserted: number;
        duplicates: number;
        event_ids: string[];
      }>("/sensor-events/batches", {
        method: "POST",
        body: JSON.stringify({
          records: [
            {
              sensor_id: sensor.id,
              message_id: message,
              observed_at: new Date(observed).getTime() / 1000,
              raw_value: Number(value),
              raw_unit: unit,
              quality,
              source: "manual-ui",
            },
          ],
        }),
      });
      setReceipt(
        `${r.inserted ? "Event saved" : "Duplicate confirmed"} · ${r.event_ids[0]}`,
      );
      setMessage(crypto.randomUUID());
      setValue("");
      setObserved(localTime());
      setReload((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      wide
      title="Sensor event inspector"
      description={`${sensor.asset_tag} · ${sensor.label}`}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <div className="event-intro">
        <Activity size={22} />
        <div>
          <strong>One reading. Full traceability.</strong>
          <p>Inspect original measurements and verified unit conversions.</p>
        </div>
      </div>
      <div className="tabs alignment-tabs" aria-label="Inspector views">
        <button
          type="button"
          className={tab === "events" ? "active" : ""}
          disabled={busy}
          onClick={() => setTab("events")}
        >
          Sensor events
        </button>
        <button
          type="button"
          className={tab === "alignment" ? "active" : ""}
          disabled={busy}
          onClick={() => setTab("alignment")}
        >
          Equipment alignment
        </button>
        <button
          type="button"
          className={tab === "review" ? "active" : ""}
          disabled={busy}
          onClick={() => setTab("review")}
        >
          Data review
        </button>
      </div>
      <div hidden={tab !== "events"}>
        <div className="sensor-identity">
          <small>PERMANENT SENSOR ID</small>
          <code>{sensor.id}</code>
        </div>
        <p className="local-note">
          Independent events are stored separately. Use Equipment snapshot
          alignment below to review and publish a complete frame for analytics.
        </p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {receipt && (
          <p className="event-receipt" role="status">
            <Check size={16} />
            {receipt}
          </p>
        )}
        {canWrite && data && (
          <form onSubmit={save} className="event-entry">
            <h3>Add a manual test reading</h3>
            <p>
              Source: manual-ui. This form does not connect industrial
              equipment.
            </p>
            <div className="form-grid">
              <label>
                Original value
                <input
                  required
                  type="number"
                  step="any"
                  value={value}
                  disabled={busy}
                  onChange={(e) => setValue(e.target.value)}
                />
              </label>
              <label>
                Original unit
                <select
                  value={unit}
                  disabled={busy}
                  onChange={(e) => setUnit(e.target.value)}
                >
                  {data.supported_units.map((u) => (
                    <option key={u}>{u}</option>
                  ))}
                </select>
              </label>
              <label>
                Observed time (your computer’s timezone)
                <input
                  required
                  type="datetime-local"
                  step="1"
                  value={observed}
                  disabled={busy}
                  onChange={(e) => setObserved(e.target.value)}
                />
              </label>
              <label>
                Sample quality
                <select
                  value={quality}
                  disabled={busy}
                  onChange={(e) => setQuality(e.target.value)}
                >
                  <option value="good">Good</option>
                  <option value="suspect">Suspect</option>
                  <option value="bad">Bad</option>
                </select>
              </label>
            </div>
            <p className="lab-footnote">
              Accepted canonical range: {data.bounds.join(" to ")}{" "}
              {data.canonical_unit}. Message ID: {message}
            </p>
            <Button
              type="submit"
              className="primary"
              disabled={busy || !value.trim()}
            >
              {busy ? "Saving…" : "Validate & save event"}
            </Button>
          </form>
        )}
        <div className="event-history-heading">
          <h3>Latest 50 events</h3>
          <Button
            icon={RefreshCw}
            disabled={busy || loading}
            onClick={() => {
              setError("");
              setReload((n) => n + 1);
            }}
          >
            Refresh
          </Button>
        </div>
        {loading ? (
          <Spinner />
        ) : !data?.items.length ? (
          <Empty
            title="No independent events yet"
            description="Your existing equipment snapshots are preserved in Live monitoring. Submit a manual test or use the batch API to begin this stream."
          />
        ) : (
          <div className="table-scroll">
            <table className="data-table event-table">
              <thead>
                <tr>
                  <th>Observed / received · GST</th>
                  <th>Original → canonical</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <strong>{date(r.observed_at, true)}</strong>
                      <small>Received {date(r.received_at, true)}</small>
                    </td>
                    <td>
                      <strong>
                        {r.raw_value} {r.raw_unit} →{" "}
                        {Number(r.value.toPrecision(8))} {r.unit}
                      </strong>
                      <small>
                        {r.conversion} · {r.quality}
                      </small>
                    </td>
                    <td>
                      <strong>{r.source}</strong>
                      <code title={r.message_id}>{r.message_id}</code>
                      <small title={r.id}>Event {r.id}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {tab === "alignment" && (
        <SnapshotAlignment
          onBusyChange={setBusy}
          assetId={sensor.asset_id}
          canWrite={canWrite}
          onEventsSaved={() => setReload((n) => n + 1)}
        />
      )}
      {tab === "review" && (
        <SensorDataReview
          sensorId={sensor.id}
          canWrite={canWrite}
          onBusyChange={setBusy}
          onEventsSaved={() => setReload((n) => n + 1)}
        />
      )}
    </Modal>
  );
}
