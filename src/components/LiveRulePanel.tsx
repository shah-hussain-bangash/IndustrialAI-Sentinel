import { useEffect, useState, type FormEvent } from "react";
import { api, post } from "../api";
import { Button } from "./ui";
import type { RuleSettings } from "./ConditionRuleDrafts";
type Deployment = { state: string; version: number; rule_version: number | null; activated_at: number | null; last_evaluated_at: number | null; latest_rule_version: number };
type Match = { id: string; name: string; rule_version: number; state: string; started_at: number; triggered_at: number; ended_at: number | null; trigger_reading_id: string };
type Activity = { items: Match[]; truncated: boolean; boundary: string };
const stamp = (t: number | null) => t ? new Date(t * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST" : "—";

export function LiveRulePanel({ ruleId, draftVersion, draftSettings, assetId, isAdmin, onBusy }: {
  ruleId: string; draftVersion: number; draftSettings: RuleSettings; assetId: string; isAdmin: boolean; onBusy: (value: boolean) => void;
}) {
  const [deployment, setDeployment] = useState<Deployment | null>(null);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    let current = true;
    Promise.all([api<Deployment>(`/condition-rules/drafts/${ruleId}/deployment`), api<Activity>(`/condition-rules/activity?asset_id=${encodeURIComponent(assetId)}`)])
      .then(([state, events]) => { if (current) { setDeployment(state); setActivity(events); } })
      .catch(e => { if (current) setError((e as Error).message); });
    return () => { current = false; };
  }, [ruleId, assetId, draftVersion]);
  async function refresh() {
    const [state, events] = await Promise.all([api<Deployment>(`/condition-rules/drafts/${ruleId}/deployment`), api<Activity>(`/condition-rules/activity?asset_id=${encodeURIComponent(assetId)}`)]);
    setDeployment(state); setActivity(events);
  }
  async function control(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!deployment || busy || !confirmed) return;
    const action = ((event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null)?.value;
    if (action !== "activate" && action !== "pause") return;
    setBusy(true); onBusy(true); setError(""); setMessage("");
    try {
      await post(`/condition-rules/drafts/${ruleId}/control`, { action, expected_version: deployment.version,
        expected_rule_version: draftVersion, reason, confirmed });
      setMessage(action === "activate" ? `Saved revision ${draftVersion} is active for new snapshots. No notifications are sent.` : "Rule paused. New snapshots will not trigger this rule.");
      setReason(""); setConfirmed(false);
      try { await refresh(); } catch { setError("Change saved; reload status before continuing."); }
    } catch (e) { setError((e as Error).message + " Reload status before retrying."); }
    finally { setBusy(false); onBusy(false); }
  }
  return <section style={{ marginTop: 24 }}>
    <h3>Controlled activation</h3>
    <p>Activate the saved revision shown below. Unsaved edits above are excluded. New draft revisions do not replace an active revision automatically.</p>
    <p><strong>Saved revision {draftVersion} settings:</strong> {draftSettings.channel} · above {draftSettings.threshold} · clear margin {draftSettings.hysteresis} · persistence {draftSettings.persistence_seconds}s · maximum gap {draftSettings.maximum_gap_seconds}s. Signal units match the rule editor.</p>
    {deployment && <div className="local-note">State: {deployment.state}. Running revision: {deployment.rule_version ?? "none"}. Selected saved revision: {draftVersion}.
      <br />Last processed snapshot: {stamp(deployment.last_evaluated_at)}. Activation starts with new snapshots and does not replay old history.</div>}
    <Button disabled={busy} onClick={async () => {
      setBusy(true); onBusy(true); setError("");
      try { await refresh(); } catch (e) { setError((e as Error).message); }
      finally { setBusy(false); onBusy(false); }
    }}>Reload activation and matches</Button>
    {error && <p role="alert" className="form-error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {isAdmin && deployment ? <form onSubmit={control}>
      <fieldset disabled={busy} style={{ border: 0, padding: 0 }}>
        <label>Activation or pause reason<textarea required maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}><input style={{ width: "auto" }} type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I reviewed the saved revision and its signal settings for this equipment.</label>
        <Button className="primary" type="submit" value="activate" disabled={!confirmed || (deployment.state === "active" && deployment.rule_version === draftVersion)}>Activate saved revision {draftVersion}</Button>
        <Button type="submit" value="pause" disabled={!confirmed || deployment.state !== "active"}>Pause rule</Button>
      </fieldset>
    </form> : <p>Administrator access is required to activate or pause a rule.</p>}
    <h3>Recent rule matches for this equipment</h3>
    <p>{activity?.boundary || "Loading rule matches…"}</p>
    {activity?.truncated && <p>Showing the latest 100 matches.</p>}
    {activity && !activity.items.length && <p>No rule matches recorded.</p>}
    {!!activity?.items.length && <div className="table-scroll"><table className="data-table"><thead><tr><th>Rule / revision</th><th>State</th><th>Triggered</th><th>Ended</th></tr></thead><tbody>
      {activity.items.map(m => <tr key={m.id}><td>{m.name} · {m.rule_version}<small>Reading: {m.trigger_reading_id}</small></td><td>{m.state.replaceAll("_", " ")}</td><td>{stamp(m.triggered_at)}</td><td>{stamp(m.ended_at)}</td></tr>)}
    </tbody></table></div>}
  </section>;
}
