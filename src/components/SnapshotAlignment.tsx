import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, date } from "../api";
import { Button, Spinner } from "./ui";
import { CheckCircle2, Clock3, RefreshCw, ShieldCheck } from "lucide-react";
import {
  alignmentWindow,
  duration,
  signalSource,
  type SensorWindow,
} from "../lib/alignment";

interface Frame {
  ready: boolean;
  reasons: string[];
  policy: string;
  preview_signature: string;
  skew_seconds: number | null;
  snapshot_timestamp: number | null;
  rows: {
    channel: string;
    event: null | {
      id: string;
      value: number;
      unit: string;
      quality: string;
      observed_at: number;
      source: string;
    };
  }[];
}
interface Projection {
  reading_id: string;
  created: number;
  policy: string;
  event_ids: Record<string, string>;
}
const channels = ["vibration", "temperature", "pressure", "flow"] as const;
const units = {
  vibration: "mm/s",
  temperature: "degC",
  pressure: "bar",
  flow: "m3/h",
};

export function SnapshotAlignment({
  assetId,
  canWrite,
  onEventsSaved,
  onBusyChange,
}: {
  assetId: string;
  canWrite: boolean;
  onEventsSaved: () => void;
  onBusyChange: (busy: boolean) => void;
}) {
  const [sensors, setSensors] = useState<SensorWindow[]>([]);
  const [clock, setClock] = useState(() => Date.now() / 1000);
  const [reviewed, setReviewed] = useState(false);
  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now() / 1000), 1000);
    return () => clearInterval(timer);
  }, []);
  const [frame, setFrame] = useState<Frame | null>(null),
    [history, setHistory] = useState<Projection[]>([]);
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0),
    [showTest, setShowTest] = useState(false);
  const [values, setValues] = useState({
    vibration: "2",
    temperature: "70",
    pressure: "5",
    flow: "120",
  });
  useEffect(() => {
    onBusyChange(busy);
  }, [busy, onBusyChange]);
  const attempt = useRef<{ body: string; key: string } | null>(null);
  useEffect(() => {
    let stop = false;
    setLoading(true);
    setFrame(null);
    setReviewed(false);
    Promise.all([
      api<Frame>(
        `/snapshot-projections/preview?asset_id=${encodeURIComponent(assetId)}`,
      ),
      api<{ items: Projection[] }>(
        `/snapshot-projections/history?asset_id=${encodeURIComponent(assetId)}`,
      ),
      api<{ items: SensorWindow[] }>(
        `/sensors?asset_id=${encodeURIComponent(assetId)}`,
      ),
    ])
      .then(([f, h, registry]) => {
        if (!stop) {
          setFrame(f);
          setHistory(h.items);
          setSensors(registry.items);
          setClock(Date.now() / 1000);
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
  }, [assetId, reload]);
  async function publish() {
    if (!frame || !windowState.eligible || !reviewed || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const r = await api<{ reading_id: string }>("/snapshot-projections", {
        method: "POST",
        headers: { "Idempotency-Key": frame.preview_signature },
        body: JSON.stringify({
          asset_id: assetId,
          preview_signature: frame.preview_signature,
        }),
      });
      setNotice(
        `Snapshot published · ${r.reading_id}. Refresh Live monitoring to inspect the equipment condition.`,
      );
      setReload((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
      setReviewed(false);
      setFrame(null);
      setReload((n) => n + 1);
    } finally {
      setBusy(false);
    }
  }
  async function saveTest(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (!attempt.current) {
        const registry = await api<{
          items: { id: string; channel: string }[];
        }>(`/sensors?asset_id=${encodeURIComponent(assetId)}`);
        const batch = crypto.randomUUID(),
          time = Date.now() / 1000 - 1;
        const records = channels.map((channel) => {
          const sensor = registry.items.find((s) => s.channel === channel);
          if (!sensor) throw new Error(`Missing ${channel} sensor.`);
          return {
            sensor_id: sensor.id,
            message_id: `frame-${batch}-${channel}`,
            observed_at: time,
            raw_value: Number(values[channel]),
            raw_unit: units[channel],
            quality: "good",
            source: "manual-alignment-ui",
          };
        });
        attempt.current = { key: batch, body: JSON.stringify({ records }) };
      }
      await api("/sensor-events/batches", {
        method: "POST",
        headers: { "Idempotency-Key": attempt.current.key },
        body: attempt.current.body,
      });
      attempt.current = null;
      setNotice(
        "Four manual test events saved. Review the alignment result before publishing.",
      );
      setShowTest(false);
      setReload((n) => n + 1);
      onEventsSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const windowState = alignmentWindow(frame, sensors, clock);
  const published = notice.startsWith("Snapshot published");
  return (
    <section className="alignment-panel">
      <div className="event-history-heading">
        <div>
          <h3>Equipment snapshot alignment</h3>
          <p>Four channels · maximum 5-second spread · good quality only</p>
        </div>
        <Button
          disabled={busy || loading}
          onClick={() => {
            setError("");
            setReload((n) => n + 1);
          }}
        >
          <RefreshCw size={15} /> Check alignment
        </Button>
      </div>
      <p className="local-note">
        Review four fresh readings, confirm their values, then publish. Keep
        simulation paused while testing. Publication never happens
        automatically.
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="event-receipt" role="status">
          {notice}
        </p>
      )}
      {loading ? (
        <Spinner />
      ) : (
        frame && (
          <>
            <div
              className={`alignment-status ${published ? "published" : windowState.eligible ? "ready" : "blocked"}`}
              role="status"
            >
              <div className="alignment-status-heading">
                {published ? (
                  <CheckCircle2 size={22} />
                ) : windowState.eligible ? (
                  <ShieldCheck size={22} />
                ) : (
                  <Clock3 size={22} />
                )}
                <div>
                  <strong>
                    {published
                      ? "Snapshot published"
                      : windowState.eligible
                        ? "Fresh readings · ready to review"
                        : "Fresh readings needed"}
                  </strong>
                  <span>
                    {published
                      ? "A new frame is required before the next publication."
                      : frame.ready && !windowState.eligible
                        ? "These readings have expired. Send a new sample or create a fresh test frame below."
                        : frame.skew_seconds === null
                          ? "All four channels are required."
                          : `Time spread: ${frame.skew_seconds.toFixed(3)} seconds · maximum 5 seconds`}
                  </span>
                </div>
              </div>
              {windowState.eligible && (
                <span className="freshness-timer">
                  <Clock3 size={16} /> Review window:{" "}
                  {duration(windowState.remaining)} remaining{" "}
                  <small>Server checks freshness again on publication.</small>
                </span>
              )}
            </div>
            {!published && !!frame.reasons.length && (
              <ul className="alignment-reasons">
                {frame.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
            {canWrite && (
              <div className="alignment-review-bar">
                <label className="review-confirmation">
                  <input
                    type="checkbox"
                    checked={reviewed}
                    disabled={busy || !windowState.eligible}
                    onChange={(e) => setReviewed(e.target.checked)}
                  />
                  <span>I reviewed all four readings</span>
                </label>
                <div className="alignment-actions">
                  <Button
                    disabled={busy}
                    onClick={() => setShowTest((value) => !value)}
                  >
                    {showTest ? "Hide test form" : "Create aligned test frame"}
                  </Button>
                  <Button
                    className="primary"
                    disabled={busy || !windowState.eligible || !reviewed}
                    onClick={publish}
                  >
                    {busy ? "Publishing…" : "Publish reviewed snapshot"}
                  </Button>
                </div>
              </div>
            )}
            <div className="alignment-reading-summary">
              {frame.rows.map((row) => (
                <div key={row.channel}>
                  <span>{row.channel}</span>
                  <strong>
                    {row.event
                      ? `${row.event.value} ${row.event.unit}`
                      : "Missing"}
                  </strong>
                </div>
              ))}
            </div>
            <div className="table-scroll">
              <table className="data-table event-table">
                <thead>
                  <tr>
                    <th>Channel</th>
                    <th>Canonical value / quality</th>
                    <th>Observed · GST / source</th>
                  </tr>
                </thead>
                <tbody>
                  {frame.rows.map((r) => (
                    <tr key={r.channel}>
                      <td>{r.channel}</td>
                      <td>
                        {r.event ? (
                          <>
                            <strong>
                              {r.event.value} {r.event.unit}
                            </strong>
                            <small>{r.event.quality}</small>
                          </>
                        ) : (
                          "Missing"
                        )}
                      </td>
                      <td>
                        {r.event ? (
                          <>
                            <strong>{date(r.event.observed_at, true)}</strong>
                            <small>{signalSource(r.event.source)}</small>
                            <details className="evidence-disclosure">
                              <summary>View traceability</summary>
                              <code>{r.event.source}</code>
                              <code>{r.event.id}</code>
                            </details>
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )
      )}
      {showTest && canWrite && (
        <form onSubmit={saveTest} className="event-entry">
          <h3>Create fresh demonstration readings</h3>
          <p>
            Creates four simulated measurements with one observation time.
            Source: manual-alignment-ui. Review values before saving; this does
            not connect equipment.
          </p>
          <div className="form-grid">
            {channels.map((c) => (
              <label key={c}>
                {c} ({units[c]})
                <input
                  required
                  type="number"
                  step="any"
                  value={values[c]}
                  disabled={busy}
                  onChange={(e) => {
                    attempt.current = null;
                    setValues((v) => ({ ...v, [c]: e.target.value }));
                  }}
                />
              </label>
            ))}
          </div>
          <p className="test-frame-tip">
            After saving, review the new values above, check the review box and
            publish before the countdown expires.
          </p>
          <Button className="primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save four test events"}
          </Button>
        </form>
      )}
      <h3>Published snapshots · latest 20</h3>
      {!history.length ? (
        <p className="lab-footnote">
          No aligned snapshot has been published for this equipment.
        </p>
      ) : (
        history.map((p) => (
          <details className="projection-record" key={p.reading_id}>
            <summary>
              {date(p.created, true)} GST · {p.reading_id}
            </summary>
            <p>{p.policy}</p>
            {Object.entries(p.event_ids).map(([c, id]) => (
              <p key={c}>
                {c}: <code>{id}</code>
              </p>
            ))}
          </details>
        ))
      )}
    </section>
  );
}
