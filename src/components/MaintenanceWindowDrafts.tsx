import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, post, type Asset } from "../api";
import { Button } from "./ui";
import { gstWindowTime, gstWindowInput, validWindowRange } from "../lib/maintenanceWindowTime";
import { MaintenanceWindowReview } from "./MaintenanceWindowReview";

type Revision = { version: number; name: string; starts_at: number; ends_at: number; reason: string; actor_name: string; created: number };
type Draft = Revision & { id: string; asset_id: string; state: "draft"; active: false };
type History = { items: Revision[]; next_before_version: number | null };
const stamp = (epoch: number) => new Date(epoch * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST";

export function MaintenanceWindowDrafts() {
  const [assets, setAssets] = useState<Asset[]>([]), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [assetId, setAssetId] = useState("");
  const [editorBusy, setEditorBusy] = useState(false);
  useEffect(() => {
    let current = true;
    api<Asset[]>("/assets").then(items => { if (current) { setAssets(items); setAssetId(items[0]?.id || ""); } })
      .catch(e => { if (current) setError((e as Error).message); }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, []);
  return <section className="panel settings-card full-span"><h2>Maintenance-window drafts</h2>
    <p>Prepare planned downtime for review. Every saved revision records its author, time and reason.</p>
    <div className="local-note">Planning only. These drafts do not suppress signals, pause rules, resolve reviews or dispatch work. Operational activation is a later development step.</div>
    {loading && <p role="status">Loading permitted equipment…</p>}{error && <p role="alert" className="form-error">{error}</p>}
    {!loading && !assets.length && <p>No permitted equipment is available.</p>}
    <label>Equipment across your permitted sites<select disabled={loading || editorBusy} value={assetId} onChange={e => setAssetId(e.target.value)}>
      {assets.map(asset => <option value={asset.id} key={asset.id}>{asset.tag} · {asset.site}</option>)}</select></label>
    {assetId && <WindowEditor key={assetId} assetId={assetId} onBusy={setEditorBusy} />}
  </section>;
}

function WindowEditor({ assetId, onBusy }: { assetId: string; onBusy: (busy: boolean) => void }) {
  const [items, setItems] = useState<Draft[]>([]), [selected, setSelected] = useState<Draft | null>(null);
  const [name, setName] = useState(""), [start, setStart] = useState(""), [end, setEnd] = useState(""), [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState(""), [message, setMessage] = useState("");
  const [history, setHistory] = useState<History | null>(null), [truncated, setTruncated] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [reviewBusy, setReviewBusy] = useState(false);
  const current = useRef(true);
  useEffect(() => { onBusy(busy || loading || reviewBusy); }, [busy, loading, reviewBusy, onBusy]);
  async function refresh() {
    const answer = await api<{items: Draft[]; truncated: boolean}>("/maintenance-windows/drafts?asset_id=" + encodeURIComponent(assetId));
    if (current.current) { setItems(answer.items); setTruncated(answer.truncated); setLoaded(true); }
  }
  useEffect(() => { current.current = true; void refresh().catch(e => { if (current.current) setError((e as Error).message); }).finally(() => { if (current.current) setLoading(false); }); return () => { current.current = false; }; }, [assetId]);
  function load(draft: Draft) {
    setSelected(draft); setName(draft.name); setStart(gstWindowInput(draft.starts_at)); setEnd(gstWindowInput(draft.ends_at)); setReason(""); setHistory(null); setError(""); setMessage("");
  }
  function separate() { setSelected(null); setName(""); setStart(""); setEnd(""); setReason(""); setHistory(null); setError(""); setMessage(""); }
  async function save(event: FormEvent) {
    event.preventDefault(); const startsAt = gstWindowTime(start), endsAt = gstWindowTime(end);
    if (busy || !validWindowRange(startsAt, endsAt)) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const answer = await post<Draft>("/maintenance-windows/drafts" + (selected ? "/" + selected.id : ""), { asset_id: assetId, name, starts_at: startsAt, ends_at: endsAt, reason, ...(selected ? { expected_version: selected.version } : {}) });
      if (!current.current) return;
      setSelected(answer); setReason(""); setHistory(null); setMessage(`Saved inactive window draft, version ${answer.version}. Rule evaluation is unchanged.`);
      try { await refresh(); } catch { if (current.current) setError("Draft saved, but its list could not refresh. Reload the list before continuing."); }
    } catch (e) { if (current.current) setError((e as Error).message + " Reload the list and load the current version if delivery is uncertain or the draft changed."); }
    finally { if (current.current) setBusy(false); }
  }
  async function viewHistory() {
    if (!selected || busy) return;
    setBusy(true); setError("");
    try {
      const answer = await api<History>(`/maintenance-windows/drafts/${selected.id}/history` + (history?.next_before_version ? `?before_version=${history.next_before_version}` : ""));
      if (current.current) setHistory(old => ({ ...answer, items: [...(old?.items || []), ...answer.items] }));
    } catch (e) { if (current.current) setError((e as Error).message); }
    finally { if (current.current) setBusy(false); }
  }
  return <><fieldset disabled={busy || loading || reviewBusy} style={{ border: 0, padding: 0, marginTop: 20 }}>
    {loading && <p role="status">Loading saved windows…</p>}
    {truncated && <p>Showing the newest 100 drafts for this equipment.</p>}
    {items.length > 0 && <div className="table-scroll"><table className="data-table"><thead><tr><th>Draft / version</th><th>Planned interval (GST)</th><th>Saved by</th><th>Action</th></tr></thead><tbody>
      {items.map(item => <tr key={item.id}><td>{item.name}<small>Version {item.version} · Inactive draft</small></td><td>{stamp(item.starts_at)}<small>to {stamp(item.ends_at)}</small></td><td>{item.actor_name}<small>{stamp(item.created)}</small></td><td><Button type="button" onClick={() => load(item)}>Load window draft</Button></td></tr>)}
    </tbody></table></div>}
    {loaded && !loading && !items.length && <p>No saved maintenance-window drafts for this equipment.</p>}
    <Button type="button" onClick={async () => { setBusy(true); setError(""); try { await refresh(); } catch (e) { if (current.current) setError((e as Error).message); } finally { if (current.current) setBusy(false); } }}>Reload window list</Button>
    <form onSubmit={save} style={{ marginTop: 20 }}><p>{selected ? `Editing ${selected.name}, version ${selected.version}. Saving creates the next revision.` : "Create a new inactive window draft."}</p>
      <div className="settings-grid"><label>Window name<input required maxLength={120} value={name} onChange={e => setName(e.target.value)} /></label>
      <label>Start in GST (UTC+4)<input type="datetime-local" step="1" required value={start} onChange={e => setStart(e.target.value)} /></label>
      <label>End in GST (UTC+4)<input type="datetime-local" step="1" required value={end} onChange={e => setEnd(e.target.value)} /></label></div>
      <p>End must follow start by no more than seven days. Past intervals may be kept as drafts; saving never applies a suppression window.</p>
      {!!start && !!end && !validWindowRange(gstWindowTime(start), gstWindowTime(end)) && <p className="form-error">Choose a valid interval of up to seven days.</p>}
      <label>Reason for this revision<textarea required minLength={5} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <Button className="primary" disabled={!loaded || !validWindowRange(gstWindowTime(start), gstWindowTime(end))}>{selected ? "Save window revision" : "Save inactive window draft"}</Button>
      {selected && <><Button type="button" onClick={separate}>Start a separate window</Button>{!history && <Button type="button" onClick={() => void viewHistory()}>View window history</Button>}</>}
    </form>
    {error && <p role="alert" className="form-error">{error}</p>}{message && <p role="status">{message}</p>}
    {history && <section><h3>Window revision history</h3>{history.items.map(row => <details key={row.version}><summary>Version {row.version} · {row.name} · {row.actor_name}</summary><p>{stamp(row.starts_at)} to {stamp(row.ends_at)}</p><p>Saved {stamp(row.created)}</p><p>{row.reason}</p></details>)}
      {history.next_before_version !== null && <Button type="button" onClick={() => void viewHistory()}>Older window revisions</Button>}</section>}
  </fieldset>
    {selected && <fieldset disabled={busy || loading} style={{ border: 0, padding: 0 }}><MaintenanceWindowReview
      key={`${selected.id}:${selected.version}`} draftId={selected.id} version={selected.version} onBusy={setReviewBusy}
      dirty={name !== selected.name || gstWindowTime(start) !== selected.starts_at || gstWindowTime(end) !== selected.ends_at || !!reason.trim()} /></fieldset>}
  </>;
}
