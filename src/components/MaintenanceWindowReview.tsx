import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, post } from "../api";
import { Button } from "./ui";

type Decision = { version: number; draft_version: number; state: "approved" | "rejected"; actor_name: string; reason: string; created: number };
type Status = {
  draft_version: number; review_version: number; current_decision: Decision["state"] | null;
  last_review: Decision | null; can_review: boolean; locked: boolean;
  saved_revision: { version: number; name: string; starts_at: number; ends_at: number; actor_name: string; reason: string; created: number };
};
type History = Status & { items: Decision[]; next_before_version: number | null };
type Control = {
  draft_version: number; review_version: number; control_version: number; state: string; server_time: number;
  can_activate: boolean; can_cancel: boolean; scope: string; suppressed_count: number; suppression_history_truncated: boolean;
  history: { version: number; action: string; draft_version: number; review_version: number; actor_name: string; reason: string; created: number }[];
  recent_suppressions: { rule_id: string; rule_version: number; reading_id: string; observed_at: number; created: number }[];
};
const stamp = (epoch: number) => new Date(epoch * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST";

export function MaintenanceWindowReview({ draftId, version, dirty, onBusy, onLocked }: {
  draftId: string; version: number; dirty: boolean; onBusy: (busy: boolean) => void; onLocked: (locked: boolean) => void;
}) {
  const [data, setData] = useState<History | null>(null), [error, setError] = useState(""), [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true);
  const [decision, setDecision] = useState<Decision["state"]>("approved"), [reason, setReason] = useState(""), [confirmed, setConfirmed] = useState(false);
  const [control, setControl] = useState<Control | null>(null), [controlReason, setControlReason] = useState(""), [controlConfirmed, setControlConfirmed] = useState(false);
  const current = useRef(true);
  const path = `/maintenance-windows/drafts/${draftId}/reviews`;
  useEffect(() => { onBusy(busy); return () => { onBusy(false); }; }, [busy, onBusy]);
  async function load(older = false) {
    const [answer, operational] = await Promise.all([
      api<History>(path + (older && data?.next_before_version ? `?before_version=${data.next_before_version}` : "")),
      api<Control>(`/maintenance-windows/drafts/${draftId}/control`),
    ]);
    if (answer.draft_version !== version) throw new Error("This window has a newer revision. Reload the window list and load that revision before reviewing.");
    if (operational.draft_version !== version || operational.review_version !== answer.review_version) throw new Error("The planning review changed while loading. Reload before continuing.");
    if (current.current) {
      setData(old => ({ ...answer, items: older && old ? [...old.items, ...answer.items] : answer.items }));
      setConfirmed(false);
      setControlConfirmed(false); setControl(operational); onLocked(operational.control_version > 0);
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
    try { await load(older); } catch (e) { if (current.current) { setData(null); setControl(null); setError((e as Error).message); } }
    finally { if (current.current) setBusy(false); }
  }
  async function controlWindow(event: FormEvent) {
    event.preventDefault(); if (!control || busy || dirty || !controlConfirmed) return;
    const action = control.can_cancel ? "cancel" : "activate";
    if (action === "activate" && !control.can_activate) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await post(`/maintenance-windows/drafts/${draftId}/control`, { action, expected_draft_version: version,
        expected_review_version: control.review_version, expected_control_version: control.control_version, reason: controlReason, confirmed: true });
      if (!current.current) return;
      setData(null); setControl(null); setControlReason(""); setControlConfirmed(false);
      await load();
      if (current.current) setMessage(action === "activate" ? "Window activated for the saved future interval. Its plan and review are now immutable. No physical work was dispatched." : "Window cancelled. New snapshots can trigger saved-rule matches again; persistence starts afresh after the effective window.");
    } catch (e) { if (current.current) { setData(null); setControl(null); setControlConfirmed(false); setError((e as Error).message + " Reload before retrying."); } }
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
    {data && <><div className="local-note" style={{ display: "block" }}><strong>Saved revision {data.draft_version}: {data.saved_revision.name}</strong>
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
    </fieldset></form> : <p>{data.locked ? "The activated revision and its planning decision are immutable." : "A different administrator from the author of this saved revision must record the planning decision."}</p>}
    <h4>Planning review history</h4>{!data.items.length && <p>No planning decisions have been recorded.</p>}
    {data.items.map(row => <details key={row.version}><summary>Review {row.version} · Revision {row.draft_version} · {row.state} · {row.actor_name}</summary><p>{stamp(row.created)}</p><p>{row.reason}</p></details>)}
    {data.next_before_version !== null && <Button type="button" disabled={busy} onClick={() => void reload(true)}>Older planning reviews</Button>}
    </>}
    {data && control && <section style={{ marginTop: 24 }}><h3>Window activation and cancellation</h3>
      <div className="local-note" style={{ display: "block" }}><strong>Window state: {control.state}</strong><p>Checked {stamp(control.server_time)}. Reload planning review to refresh this state.</p><p>{control.scope}</p>
      <p>One activation per plan. Once activated, use cancellation or create a separate plan; editing or reviewing its captured revision is blocked.</p></div>
      {control.can_activate || control.can_cancel ? <form onSubmit={controlWindow}><fieldset disabled={busy || dirty} style={{ border: 0, padding: 0 }}>
        <label>Reason for {control.can_cancel ? "cancellation" : "activation"}<textarea required minLength={5} maxLength={1000} value={controlReason} onChange={e => setControlReason(e.target.value)} /></label>
        <label className="checkbox-row"><input type="checkbox" checked={controlConfirmed} onChange={e => setControlConfirmed(e.target.checked)} />I reviewed this equipment, saved revision {version}, GST interval and the scope of {control.can_cancel ? "cancellation" : "new saved-rule trigger suppression"}.</label>
        <Button className="primary" disabled={!controlConfirmed || controlReason.trim().length < 5}>{control.can_cancel ? "Cancel activated window" : "Activate approved future window"}</Button>
      </fieldset></form> : <p>Activation requires an administrator, independent approval of this exact revision, a future start and a plan that has never been activated.</p>}
      <h4>Window control history</h4>{!control.history.length && <p>No activation or cancellation has been recorded.</p>}
      {control.history.map(row => <details key={row.version}><summary>Control {row.version} · {row.action} · {row.actor_name}</summary><p>Revision {row.draft_version}, planning review {row.review_version} · {stamp(row.created)}</p><p>{row.reason}</p></details>)}
      <h4>Suppressed high readings: {control.suppressed_count}</h4><p>These are good-quality readings above a saved rule’s limit where a new match was prevented; they do not prove a sustained condition. Existing active matches are excluded.</p>
      {control.suppression_history_truncated && <p>Showing the newest 50 records of {control.suppressed_count}; older evidence remains stored.</p>}
      {control.recent_suppressions.map(row => <details key={`${row.rule_id}:${row.reading_id}`}><summary>{stamp(row.observed_at)} · Rule revision {row.rule_version}</summary><p>Rule {row.rule_id} · Reading {row.reading_id}</p><p>Recorded {stamp(row.created)}</p></details>)}
    </section>}
  </section>;
}
