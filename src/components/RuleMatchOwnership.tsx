import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, post } from "../api";
import { Button } from "./ui";

type Assignment = { version: number; owner_id: string | null; owner_name: string | null; actor_name: string | null; reason: string | null; created: number | null };
type Ownership = { current: Assignment; owner_eligible: boolean; review_state: string;
  reviewers: { id: string; name: string; role: string }[]; reviewers_truncated: boolean;
  items: Assignment[]; next_before_version: number | null };
const stamp = (t: number | null) => t === null ? "—" : new Date(t * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST";

export function RuleMatchOwnership({ matchId, reviewState, locked, onBusy, onSaved }: {
  matchId: string; reviewState?: string; locked: boolean; onBusy: (busy: boolean) => void; onSaved: () => Promise<void>;
}) {
  const [data, setData] = useState<Ownership | null>(null);
  const [owner, setOwner] = useState("");
  const [query, setQuery] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const generation = useRef(0);
  async function load(mode: "reload" | "search" | "older" = "reload") {
    const request = ++generation.current;
    const params = new URLSearchParams({ reviewer_name: query });
    if (mode === "older" && data?.next_before_version) params.set("before_version", String(data.next_before_version));
    const result = await api<Ownership>(`/condition-rules/matches/${encodeURIComponent(matchId)}/ownership?${params}`);
    if (generation.current !== request) return;
    if (mode === "search") setData(old => old ? { ...old, reviewers: result.reviewers, reviewers_truncated: result.reviewers_truncated } : result);
    else if (mode === "older") setData(old => old ? { ...old, items: [...old.items, ...result.items], next_before_version: result.next_before_version } : result);
    else { setData(result); setOwner(result.current.owner_id ?? ""); }
  }
  useEffect(() => {
    setBusy(true);
    load().catch(e => setError((e as Error).message)).finally(() => setBusy(false));
    return () => { generation.current++; };
  }, [matchId]);
  async function run(mode: "reload" | "search" | "older") {
    setBusy(true); onBusy(true); setError("");
    try { await load(mode); } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); onBusy(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!data || busy || locked) return;
    setBusy(true); onBusy(true); setError(""); setMessage("");
    try {
      await post(`/condition-rules/matches/${encodeURIComponent(matchId)}/ownership`, {
        owner_id: owner || null, expected_version: data.current.version, reason,
      });
      setReason(""); setMessage("Ownership saved. No access permissions were changed and no notification was sent.");
      try { await load(); await onSaved(); } catch { setError("Ownership saved; reload ownership to see the current record."); }
    } catch (e) { setError((e as Error).message + " Reload ownership before retrying."); }
    finally { setBusy(false); onBusy(false); }
  }
  const resolved = reviewState === "resolved" || data?.review_state === "resolved";
  return <section style={{ marginTop: 20 }} aria-label="Review ownership">
    <h3>Review ownership</h3>
    <p>Assign responsibility to an engineer or administrator who already has this site's access. Assignment does not grant access or dispatch maintenance.</p>
    <Button disabled={busy || locked} onClick={() => void run("reload")}>Reload ownership</Button>
    {busy && <p role="status">Loading or saving ownership…</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {data && <>
      <p>Owner: <strong>{data.current.owner_name || "Unassigned"}</strong>. Assignment version: {data.current.version}.</p>
      {data.current.owner_id && !data.owner_eligible && <p role="status">The recorded owner no longer has an eligible role or this site's access. Reassign an open review to an eligible reviewer.</p>}
      {resolved ? <p>This review is resolved. Its ownership history is retained.</p> : <>
        <div className="table-toolbar"><label>Find reviewer by name<input maxLength={100} disabled={busy || locked} value={query} onChange={e => setQuery(e.target.value)} /></label>
          <Button disabled={busy || locked} onClick={() => void run("search")}>Find reviewers</Button></div>
        {data.reviewers_truncated && <p>Showing the first 100 matching reviewers. Refine the name to find another reviewer.</p>}
        <form onSubmit={submit}><fieldset disabled={busy || locked} style={{ border: 0, padding: 0 }}>
          <label>Review owner<select value={owner} onChange={e => setOwner(e.target.value)}><option value="">Unassigned</option>
            {data.current.owner_id && !data.reviewers.some(person => person.id === data.current.owner_id) && <option value={data.current.owner_id} disabled>Current: {data.current.owner_name}</option>}
            {data.reviewers.map(person => <option key={person.id} value={person.id}>{person.name} · {person.role}</option>)}
          </select></label>
          <label>Assignment note<textarea required minLength={5} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
          <Button className="primary" type="submit" disabled={(owner || null) === data.current.owner_id}>Save ownership</Button>
        </fieldset></form>
      </>}
      {!!data.items.length && <div><h4>Ownership history</h4>{data.items.map(row => <div key={row.version} className="local-note" style={{ display: "block", marginTop: 8 }}>
        <strong>{row.owner_name || "Unassigned"} · Version {row.version}</strong><p>{row.actor_name} · {stamp(row.created)}</p><p>{row.reason}</p>
      </div>)}</div>}
      {data.next_before_version && <Button disabled={busy || locked} onClick={() => void run("older")}>Older ownership history</Button>}
    </>}
  </section>;
}
