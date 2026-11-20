import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, date } from "../api";
import { Button, Empty, Spinner } from "./ui";

interface Item {
  id: string;
  raw_payload: Record<string, unknown>;
  validation_errors: string[];
  status: string;
  version: number;
  created: number;
  review_reason: string | null;
  corrected_event_id: string | null;
  corrected_payload: Record<string, unknown> | null;
  reviewed_at: number | null;
}
interface Queue {
  items: Item[];
  supported_units: string[];
  summary: { pending: number; replayed: number; dismissed: number };
  total_matching: number;
  page_cursor: string;
  next_cursor: string | null;
}
function localTime(timestamp: unknown) {
  const d =
    typeof timestamp === "number" ? new Date(timestamp * 1000) : new Date();
  if (!Number.isFinite(d.getTime())) return "";
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 19);
}
export function SensorDataReview({
  sensorId,
  canWrite,
  onBusyChange,
  onEventsSaved,
}: {
  sensorId: string;
  canWrite: boolean;
  onBusyChange: (busy: boolean) => void;
  onEventsSaved: () => void;
}) {
  const [data, setData] = useState<Queue | null>(null),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [filter, setFilter] = useState("pending"),
    [reload, setReload] = useState(0);
  const [reviewing, setReviewing] = useState<Item | null>(null),
    [value, setValue] = useState(""),
    [unit, setUnit] = useState(""),
    [observed, setObserved] = useState(""),
    [quality, setQuality] = useState("good"),
    [reason, setReason] = useState("");
  const [draftSearch, setDraftSearch] = useState(""),
    [search, setSearch] = useState(""),
    [pageSize, setPageSize] = useState(10),
    [page, setPage] = useState(0);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  function restart() {
    setReviewing(null);
    setCursors([null]);
    setPage(0);
    setError("");
    setReload((n) => n + 1);
  }
  const testAttempt = useRef<{ key: string; body: string } | null>(null);
  const requestAttempt = useRef<{
    key: string;
    path: string;
    body: string;
  } | null>(null);
  useEffect(() => {
    onBusyChange(busy);
  }, [busy, onBusyChange]);
  useEffect(() => {
    let stop = false;
    setLoading(true);
    setData(null);
    const params = new URLSearchParams({
      sensor_id: sensorId,
      status: filter,
      limit: String(pageSize),
      q: search,
    });
    if (cursors[page]) params.set("cursor", cursors[page]!);
    api<Queue>(`/sensor-quarantine?${params}`)
      .then((r) => {
        if (!stop) {
          setData(r);
          setCursors((previous) => {
            const next = [...previous];
            next[page] = r.page_cursor;
            return next;
          });
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
    // Cursor values are captured for this page; saving its returned token must not refetch it.
  }, [sensorId, filter, search, pageSize, page, reload]);
  async function test() {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (!testAttempt.current)
        testAttempt.current = {
          key: crypto.randomUUID(),
          body: JSON.stringify({
            raw_payload: {
              message_id: crypto.randomUUID(),
              observed_at: Date.now() / 1000 - 1,
              raw_value: 212,
              raw_unit: "invalid-unit-test",
              quality: "good",
              source: "manual-quarantine-test",
            },
          }),
        };
      const r = await api<{ outcome: string }>(`/sensor-intake/${sensorId}`, {
        method: "POST",
        headers: { "Idempotency-Key": testAttempt.current.key },
        body: testAttempt.current.body,
      });
      testAttempt.current = null;
      setNotice(
        r.outcome === "quarantined"
          ? "Intentional unit error captured. Review the original evidence below."
          : "Submission accepted.",
      );
      setFilter("pending");
      setDraftSearch("");
      setSearch("");
      restart();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function review(item: Item) {
    setReviewing(item);
    setError("");
    setNotice("");
    setReason("");
    requestAttempt.current = null;
    const raw = item.raw_payload;
    setValue(
      (typeof raw.raw_value === "number" ||
        typeof raw.raw_value === "string") &&
        Number.isFinite(Number(raw.raw_value))
        ? String(raw.raw_value)
        : "",
    );
    setUnit(
      typeof raw.raw_unit === "string" &&
        data?.supported_units.includes(raw.raw_unit)
        ? raw.raw_unit
        : "",
    );
    setObserved(localTime(raw.observed_at));
    setQuality(
      typeof raw.quality === "string" &&
        ["good", "suspect", "bad"].includes(raw.quality)
        ? raw.quality
        : "good",
    );
  }
  async function resolve(action: "replay" | "dismiss") {
    if (!reviewing || busy) return;
    if (reason.trim().length < 10) {
      setError("Explain your decision using at least 10 characters.");
      return;
    }
    if (action === "replay" && (!value.trim() || !unit || !observed)) {
      setError(
        "Complete value, verified unit and observation time before replaying.",
      );
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const path = `/sensor-quarantine/${reviewing.id}/${action}`;
      const body = JSON.stringify({
        expected_version: reviewing.version,
        reason: reason.trim(),
        ...(action === "replay"
          ? {
              raw_value: Number(value),
              raw_unit: unit,
              observed_at: new Date(observed).getTime() / 1000,
              quality,
            }
          : {}),
      });
      if (
        !requestAttempt.current ||
        requestAttempt.current.path !== path ||
        requestAttempt.current.body !== body
      )
        requestAttempt.current = { path, body, key: crypto.randomUUID() };
      const r = await api<{ event_id?: string }>(path, {
        method: "POST",
        headers: { "Idempotency-Key": requestAttempt.current.key },
        body,
      });
      setNotice(
        action === "replay"
          ? `Correction replayed · event ${r.event_id}. It still needs an eligible four-channel frame before snapshot publication.`
          : "Item dismissed with its original evidence retained.",
      );
      setReviewing(null);
      requestAttempt.current = null;
      setFilter("all");
      restart();
      if (action === "replay") onEventsSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    void resolve("replay");
  }
  return (
    <section className="data-review-panel">
      <div className="event-history-heading">
        <div>
          <h3>Rejected sensor data</h3>
          <p>Original evidence stays intact through review and replay.</p>
        </div>
        <Button disabled={busy || loading} onClick={restart}>
          Refresh queue
        </Button>
      </div>
      <p className="local-note">
        This queue receives submissions sent through the opt-in intake API.
        Existing batch requests keep their atomic rejection behavior. Replay
        creates an independent sensor event; publication remains a separate
        reviewed action.
      </p>
      <div className="review-toolbar">
        <label>
          Show
          <select
            value={filter}
            disabled={busy}
            onChange={(e) => {
              setFilter(e.target.value);
              restart();
            }}
          >
            <option value="pending">Pending review</option>
            <option value="replayed">Corrected & replayed</option>
            <option value="dismissed">Dismissed</option>
            <option value="all">All statuses</option>
          </select>
        </label>
        {canWrite && (
          <Button disabled={busy} onClick={test}>
            Create rejected-unit test
          </Button>
        )}
      </div>
      <form
        className="review-search"
        onSubmit={(e) => {
          e.preventDefault();
          setSearch(draftSearch.trim());
          restart();
        }}
      >
        <label>
          Search review items
          <input
            maxLength={100}
            disabled={busy}
            value={draftSearch}
            onChange={(e) => setDraftSearch(e.target.value)}
            placeholder="ID, message, source or review reason"
          />
        </label>
        <Button type="submit" disabled={busy}>
          Search
        </Button>
        <Button
          disabled={busy || (!search && !draftSearch)}
          onClick={() => {
            setDraftSearch("");
            setSearch("");
            restart();
          }}
        >
          Clear search
        </Button>
      </form>
      {data && (
        <div className="review-counts" aria-label="Matching statuses">
          <span>
            Pending <strong>{data.summary.pending}</strong>
          </span>
          <span>
            Corrected & replayed <strong>{data.summary.replayed}</strong>
          </span>
          <span>
            Dismissed <strong>{data.summary.dismissed}</strong>
          </span>
          <small>
            Counts include every status matching the search, within this
            browsing session.
          </small>
        </div>
      )}
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
      {reviewing && (
        <form className="event-entry" onSubmit={submit}>
          <h3>Review & resolve</h3>
          <p>
            Item {reviewing.id} · version {reviewing.version}. Use the verified
            observation time; do not make old data appear current.
          </p>
          <details open>
            <summary>Original submission & rejection reasons</summary>
            <pre className="raw-evidence">
              {JSON.stringify(reviewing.raw_payload, null, 2)}
            </pre>
            <ul className="alignment-reasons">
              {reviewing.validation_errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </details>
          <div className="form-grid">
            <label>
              Corrected value
              <input
                type="number"
                step="any"
                value={value}
                disabled={busy}
                onChange={(e) => setValue(e.target.value)}
              />
            </label>
            <label>
              Verified original unit
              <select
                value={unit}
                disabled={busy}
                onChange={(e) => setUnit(e.target.value)}
              >
                <option value="">Choose verified unit</option>
                {data?.supported_units.map((u) => (
                  <option key={u}>{u}</option>
                ))}
              </select>
            </label>
            <label>
              Observed time (computer timezone)
              <input
                type="datetime-local"
                step="1"
                value={observed}
                disabled={busy}
                onChange={(e) => setObserved(e.target.value)}
              />
            </label>
            <label>
              Corrected sample quality
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
          <label>
            Review reason
            <textarea
              required
              minLength={10}
              maxLength={1000}
              value={reason}
              disabled={busy}
              placeholder="Explain the evidence for your correction or dismissal."
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <div className="modal-actions">
            <Button disabled={busy} onClick={() => setReviewing(null)}>
              Cancel review
            </Button>
            <Button
              disabled={busy || reason.trim().length < 10}
              onClick={() => void resolve("dismiss")}
            >
              Dismiss with reason
            </Button>
            <Button
              className="primary"
              type="submit"
              disabled={busy || reason.trim().length < 10}
            >
              {busy ? "Working…" : "Validate correction & replay"}
            </Button>
          </div>
        </form>
      )}
      {loading ? (
        <Spinner />
      ) : !data?.items.length ? (
        <Empty
          title="No matching review items"
          description="Rejected readings from the intake API appear here. Use the labelled test action to try the workflow."
        />
      ) : (
        data.items.map((item) => (
          <article className="quarantine-card" key={item.id}>
            <div className="event-history-heading">
              <div>
                <strong>
                  {item.status === "pending"
                    ? "Pending review"
                    : item.status === "replayed"
                      ? "Corrected & replayed"
                      : "Dismissed"}
                </strong>
                <p>
                  {date(item.created, true)} GST · v{item.version}
                </p>
              </div>
              {canWrite && item.status === "pending" && (
                <Button disabled={busy} onClick={() => review(item)}>
                  Review item
                </Button>
              )}
            </div>
            <code>{item.id}</code>
            <ul className="alignment-reasons">
              {item.validation_errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
            <details>
              <summary>Evidence & decision history</summary>
              <pre className="raw-evidence">
                {JSON.stringify(item.raw_payload, null, 2)}
              </pre>
              {item.review_reason && <p>Review reason: {item.review_reason}</p>}
              {item.corrected_event_id && (
                <p>
                  Corrected event: <code>{item.corrected_event_id}</code>
                </p>
              )}
              {item.reviewed_at && (
                <p>Reviewed {date(item.reviewed_at, true)} GST</p>
              )}
              {item.corrected_payload && (
                <pre className="raw-evidence">
                  {JSON.stringify(item.corrected_payload, null, 2)}
                </pre>
              )}
            </details>
          </article>
        ))
      )}
      <nav className="review-pagination" aria-label="Review queue pages">
        <label>
          Items per page
          <select
            value={pageSize}
            disabled={busy || loading}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              restart();
            }}
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
          </select>
        </label>
        <span aria-live="polite">
          Page {page + 1}
          {data
            ? ` · ${data.items.length} shown · ${data.total_matching} matching`
            : ""}
        </span>
        <Button
          disabled={busy || loading || page === 0}
          onClick={() => {
            setReviewing(null);
            setError("");
            setPage((n) => n - 1);
          }}
        >
          Previous
        </Button>
        <Button
          disabled={busy || loading || !data?.next_cursor}
          onClick={() => {
            if (!data?.next_cursor) return;
            setReviewing(null);
            setError("");
            setCursors((previous) => [
              ...previous.slice(0, page + 1),
              data.next_cursor,
            ]);
            setPage((n) => n + 1);
          }}
        >
          Next
        </Button>
      </nav>
      <p className="lab-footnote">
        Refresh queue includes newer submissions and restarts browsing. Status
        changes are live. Navigation expires after 15 minutes or a server
        restart. Source labels are not authenticated device identities.
      </p>
    </section>
  );
}
