import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, post } from "../api";
import { Button } from "./ui";

type Decision = { version: number; draft_version: number; state: "approved" | "rejected"; actor_name: string; reason: string; created: number };
type Status = {
  draft_version: number; review_version: number; current_decision: Decision["state"] | null;
  last_review: Decision | null; can_review: boolean;
  saved_revision: { version: number; name: string; starts_at: number; ends_at: number; actor_name: string; reason: string; created: number };
};
type History = Status & { items: Decision[]; next_before_version: number | null };
const stamp = (epoch: number) => new Date(epoch * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST";

export function MaintenanceWindowReview({ draftId, version, dirty, onBusy }: {
  draftId: string; version: number; dirty: boolean; onBusy: (busy: boolean) => void;
}) {
  const [data, setData] = useState<History | null>(null), [error, setError] = useState(""), [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true);
  const [decision, setDecision] = useState<Decision["state"]>("approved"), [reason, setReason] = useState(""), [confirmed, setConfirmed] = useState(false);
  const current = useRef(true);
  const path = `/maintenance-windows/drafts/${draftId}/reviews`;
  useEffect(() => { onBusy(busy); return () => { onBusy(false); }; }, [busy, onBusy]);
  async function load(older = false) {
    const answer = await api<History>(path + (older && data?.next_before_version ? `?before_version=${data.next_before_version}` : ""));
    if (answer.draft_version !== version) throw new Error("This window has a newer revision. Reload the window list and load that revision before reviewing.");
    if (current.current) {
      setData(old => ({ ...answer, items: older && old ? [...old.items, ...answer.items] : answer.items }));
      setConfirmed(false);
    }
  }
  useEffect(() => {
    current.current = true;
    void load().catch(e => { if (current.current) setError((e as Error).message); }).finally(() => { if (current.current) setLoading(false); });
    return () => { current.current = false; };
    // The parent keys this component by the selected draft and its saved version.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftId, version]);
  async function reload(older = false) {
    setBusy(true); setError(""); setMessage("");
    try { await load(older); } catch (e) { if (current.current) { setData(null); setError((e as Error).message); } }
    finally { if (current.current) setBusy(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!data || busy || dirty || !confirmed) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const answer = await post<Status>(path, { decision, reason, confirmed, expected_draft_version: version, expected_review_version: data.review_version });
      if (!current.current) return;
      setConfirmed(false); setReason("");
      setData(null);
      await load();
      if (current.current) setMessage(`Planning review saved: ${answer.current_decision}. This does not activate downtime or suppress signals.`);
    } catch (e) { if (current.current) { setData(null); setConfirmed(false); setError((e as Error).message + " Reload planning review before retrying."); } }
    finally { if (current.current) setBusy(false); }
  }
  return <section style={{ marginTop: 24 }}><h3>Independent planning review</h3>
    <p>Approval records an administrator’s decision about the exact saved revision. It does not authorize or schedule physical work, activate downtime or suppress signals.</p>
    {loading && <p role="status">Loading planning review…</p>}
    {error && <p className="form-error" role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <Button type="button" disabled={busy || loading} onClick={() => void reload()}>Reload planning review</Button>
    {data && <><div className="local-note"><strong>Saved revision {data.draft_version}: {data.saved_revision.name}</strong>
      <p>{stamp(data.saved_revision.starts_at)} to {stamp(data.saved_revision.ends_at)}</p>
      <p>Author: {data.saved_revision.actor_name} · Saved {stamp(data.saved_revision.created)}</p><p>{data.saved_revision.reason}</p>
      <strong>Current revision: {data.current_decision ? `${data.current_decision} for planning only` : "Awaiting planning review"}</strong>
      {data.last_review && data.last_review.draft_version !== version && <p>The last decision applies to revision {data.last_review.draft_version}. This revision needs a fresh review.</p>}
    </div>
    {dirty && <p role="status">Save or reload changes before planning review. The saved revision above excludes your unsaved edits.</p>}
    {data.can_review ? <form onSubmit={submit}><fieldset disabled={busy || dirty} style={{ border: 0, padding: 0 }}>
      <label>Planning decision<select value={decision} onChange={e => { setDecision(e.target.value as Decision["state"]); setConfirmed(false); }}><option value="approved">Approve saved plan</option><option value="rejected">Reject saved plan</option></select></label>
      <label>Review note<textarea required minLength={5} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <label className="checkbox-row"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I reviewed saved revision {version}, its equipment, interval and reason.</label>
      <Button className="primary" disabled={!confirmed || reason.trim().length < 5}>Save planning review</Button>
    </fieldset></form> : <p>A different administrator from the author of this saved revision must record the planning decision.</p>}
    <h4>Planning review history</h4>{!data.items.length && <p>No planning decisions have been recorded.</p>}
    {data.items.map(row => <details key={row.version}><summary>Review {row.version} · Revision {row.draft_version} · {row.state} · {row.actor_name}</summary><p>{stamp(row.created)}</p><p>{row.reason}</p></details>)}
    {data.next_before_version !== null && <Button type="button" disabled={busy} onClick={() => void reload(true)}>Older planning reviews</Button>}
    </>}
  </section>;
}
