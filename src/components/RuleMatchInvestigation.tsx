import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, post, type Investigation } from "../api";
import { Button } from "./ui";

type Status = { investigation: Investigation | null; ready: boolean; message: string };
export function RuleMatchInvestigation({ matchId, locked, onBusy, onSaved }: {
  matchId: string; locked: boolean; onBusy: (busy: boolean) => void; onSaved: () => Promise<void>;
}) {
  const [data, setData] = useState<Status | null>(null);
  const [title, setTitle] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const generation = useRef(0);
  const path = `/condition-rules/matches/${encodeURIComponent(matchId)}/investigation`;
  async function load() {
    const request = ++generation.current;
    const answer = await api<Status>(path);
    if (generation.current === request) setData(answer);
  }
  useEffect(() => {
    setBusy(true);
    load().catch(e => setError((e as Error).message)).finally(() => setBusy(false));
    return () => { generation.current++; };
  }, [matchId]);
  async function reload() {
    setBusy(true); onBusy(true); setError("");
    try { await load(); } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); onBusy(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || locked || !data?.ready || data.investigation) return;
    setBusy(true); onBusy(true); setError(""); setMessage("");
    try {
      const result = await post<{ investigation: Investigation; created: boolean }>(path, { title, reason });
      setData({ investigation: result.investigation, ready: false, message: "A linked investigation exists." });
      setReason("");
      setMessage(result.created ? "Draft investigation prepared with historical trigger evidence and a separate fresh analysis snapshot. Independent review is required before action." : "Opened the existing link; no duplicate investigation was created.");
      try { await onSaved(); } catch { setError("Investigation saved; reload status to see the current link."); }
    } catch (e) { setError((e as Error).message + " Reload investigation status before retrying."); }
    finally { setBusy(false); onBusy(false); }
  }
  return <section style={{ marginTop: 20 }} aria-label="Linked investigation">
    <h3>Linked investigation</h3>
    <p>Prepare one investigation for this match using fresh, good-quality readings. The original trigger and matched rule revision are attached for traceability. Existing review status and ownership stay unchanged.</p>
    <Button disabled={busy || locked} onClick={() => void reload()}>Reload investigation status</Button>
    {busy && <p role="status">Loading or preparing investigation…</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {data && <>
      <p>{data.message}</p>
      {data.investigation ? <div className="local-note" style={{ display: "block" }}>
        <strong>{data.investigation.title}</strong><p>State: {data.investigation.state.replaceAll("_", " ")} · Version {data.investigation.version}</p>
        <Button disabled={busy || locked} onClick={() => { window.location.hash = `intelligence/${data.investigation!.id}`; }}>Open linked investigation</Button>
      </div> : <form onSubmit={submit}><fieldset disabled={busy || locked || !data.ready} style={{ border: 0, padding: 0 }}>
        <label>Investigation title (optional)<input maxLength={200} value={title} onChange={e => setTitle(e.target.value)} /></label>
        <label>Investigation note<textarea required minLength={5} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <Button className="primary" type="submit">Prepare linked investigation</Button>
      </fieldset></form>}
    </>}
  </section>;
}
