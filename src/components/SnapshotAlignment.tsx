import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, date } from "../api";
import { Button, Spinner } from "./ui";

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
    Promise.all([
      api<Frame>(
        `/snapshot-projections/preview?asset_id=${encodeURIComponent(assetId)}`,
      ),
      api<{ items: Projection[] }>(
        `/snapshot-projections/history?asset_id=${encodeURIComponent(assetId)}`,
      ),
    ])
      .then(([f, h]) => {
        if (!stop) {
          setFrame(f);
          setHistory(h.items);
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
    if (!frame?.ready || busy) return;
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
          Check alignment
        </Button>
      </div>
      <p className="local-note">
        Independent events affect equipment analytics only after an eligible
        frame is explicitly published. Pause Live monitoring simulation before
        testing. The oldest channel time becomes the snapshot time.
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
              className={`alignment-status ${frame.ready ? "ready" : "blocked"}`}
            >
              <strong>
                {frame.ready
                  ? "Ready for review & publication"
                  : "Publication blocked"}
              </strong>
              <span>
                {frame.skew_seconds === null
                  ? "Awaiting all four channels"
                  : `Observed-time spread: ${frame.skew_seconds.toFixed(3)} seconds`}
              </span>
            </div>
            {!!frame.reasons.length && (
              <ul className="alignment-reasons">
                {frame.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
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
                            <small>{r.event.source}</small>
                            <code title={r.event.id}>{r.event.id}</code>
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
            {canWrite && (
              <div className="modal-actions">
                <Button disabled={busy} onClick={() => setShowTest((s) => !s)}>
                  {showTest ? "Hide test form" : "Create aligned test frame"}
                </Button>
                <Button
                  className="primary"
                  disabled={busy || !frame.ready}
                  onClick={publish}
                >
                  {busy ? "Working…" : "Publish reviewed snapshot"}
                </Button>
              </div>
            )}
          </>
        )
      )}
      {showTest && canWrite && (
        <form onSubmit={saveTest} className="event-entry">
          <h3>Manual four-channel test frame</h3>
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
