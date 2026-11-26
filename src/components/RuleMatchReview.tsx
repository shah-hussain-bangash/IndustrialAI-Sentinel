import { useEffect, useState, type FormEvent } from "react";
import { api, post } from "../api";
import { Button } from "./ui";
import { RuleMatchEvidence } from "./RuleMatchEvidence";
type Review = { state: string; version: number; reason: string | null; actor_name: string | null; created: number | null };
type History = { current: Review; signal_state: string; items: Review[] };

export function RuleMatchReview({ matchId, onBusy, onSaved }: {
  matchId: string; onBusy: (busy: boolean) => void; onSaved: () => Promise<void>;
}) {
  const [history, setHistory] = useState<History | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    let current = true;
    api<History>(`/condition-rules/matches/${matchId}/reviews`).then(data => { if (current) setHistory(data); })
      .catch(e => { if (current) setError((e as Error).message); });
    return () => { current = false; };
  }, [matchId]);
  async function refresh() { setHistory(await api<History>(`/condition-rules/matches/${matchId}/reviews`)); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!history || busy) return;
    const action = ((event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null)?.value;
    if (action !== "acknowledge" && action !== "resolve") return;
    setBusy(true); onBusy(true); setError(""); setMessage("");
    try {
      await post(`/condition-rules/matches/${matchId}/review`, { action, expected_version: history.current.version, reason });
      setReason(""); setMessage(action === "acknowledge" ? "Match acknowledged. Signal state and rule activation were not changed." : "Review resolved. This does not record physical maintenance completion.");
      try { await refresh(); await onSaved(); } catch { setError("Review saved; reload before another action."); }
    } catch (e) { setError((e as Error).message + " Reload review before retrying."); }
    finally { setBusy(false); onBusy(false); }
  }
  return <section style={{ marginTop: 20 }}>
    <RuleMatchEvidence key={matchId} matchId={matchId} />
    <h3>Match review</h3><p>Match: {matchId}</p>
    <p>Review notes describe your assessment. They do not confirm a fault, equipment repair or work-order completion.</p>
    <Button disabled={busy} onClick={async () => {
      setBusy(true); onBusy(true); setError("");
      try { await refresh(); await onSaved(); } catch (e) { setError((e as Error).message); }
      finally { setBusy(false); onBusy(false); }
    }}>Reload review</Button>
    {history && <p>Signal state: {history.signal_state.replaceAll("_", " ")}. Review: {history.current.state}. Review version: {history.current.version}.</p>}
    {history?.signal_state === "active" && <p>The signal is still active. You can acknowledge it; resolution requires it to end first.</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {history && history.current.state !== "resolved" && <form onSubmit={submit}>
      <fieldset disabled={busy} style={{ border: 0, padding: 0 }}>
        <label>Review note<textarea required minLength={5} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <Button type="submit" className="primary" value="acknowledge" disabled={history.current.state !== "unreviewed"}>Acknowledge match</Button>
        <Button type="submit" value="resolve" disabled={history.current.state !== "acknowledged" || history.signal_state === "active"}>Resolve review</Button>
      </fieldset>
    </form>}
    {!!history?.items.length && <div><h4>Review history</h4>{history.items.map(row => <div key={row.version} className="local-note" style={{ display: "block", marginTop: 8 }}>
      <strong>{row.state} · {row.actor_name}</strong>
      <p>{row.created ? new Date(row.created * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST" : "—"}</p><p>{row.reason}</p>
    </div>)}</div>}
  </section>;
}
