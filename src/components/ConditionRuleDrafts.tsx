import { useEffect, useState, type FormEvent } from "react";
import { api, post } from "../api";
import { Button } from "./ui";
import { LiveRulePanel } from "./LiveRulePanel";

export type RuleSettings = { asset_id: string; channel: "vibration" | "temperature" | "pressure" | "flow";
  threshold: number; hysteresis: number; persistence_seconds: number; maximum_gap_seconds: number };
type Revision = { version: number; name: string; settings: RuleSettings; reason: string; actor_name: string; created: number };
type Draft = Revision & { id: string; active: false; state: "draft" };
type History = { items: Revision[]; next_before_version: number | null };
function date(value: number) { return new Date(value * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST"; }

export function ConditionRuleDrafts({ settings, valid, locked, isAdmin, onLoad, onBusy }: {
  settings: RuleSettings; valid: boolean; locked: boolean; isAdmin: boolean; onLoad: (settings: RuleSettings) => void; onBusy: (busy: boolean) => void;
}) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [selected, setSelected] = useState<Draft | null>(null);
  const [name, setName] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<History | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [loading, setLoading] = useState(true);
  // A key tied to asset_id in the parent resets selections when equipment changes.
  useEffect(() => {
    let current = true;
    api<{ items: Draft[]; truncated: boolean }>("/condition-rules/drafts?asset_id=" + encodeURIComponent(settings.asset_id))
      .then(data => { if (current) { setDrafts(data.items); setTruncated(data.truncated); } })
      .catch(e => { if (current) setError((e as Error).message); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [settings.asset_id]);
  async function refresh() {
    const data = await api<{ items: Draft[]; truncated: boolean }>("/condition-rules/drafts?asset_id=" + encodeURIComponent(settings.asset_id));
    setDrafts(data.items); setTruncated(data.truncated);
  }
  function load(draft: Draft) {
    setSelected(draft); setName(draft.name); setReason(""); setHistory(null); setError(""); setMessage(""); onLoad(draft.settings);
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || !valid) return;
    setBusy(true); onBusy(true); setError(""); setMessage("");
    try {
      const data = await post<Draft>(selected ? "/condition-rules/drafts/" + selected.id : "/condition-rules/drafts",
        { ...settings, name, reason, ...(selected ? { expected_version: selected.version } : {}) });
      setSelected(data); setReason(""); setHistory(null);
      setMessage(`Saved inactive draft, version ${data.version}. No alerts or notifications were activated.`);
      try { await refresh(); } catch { setError("Draft saved, but the list could not refresh. Reload drafts before continuing."); }
    } catch (e) { setError((e as Error).message + " Reload drafts if the record changed or delivery is uncertain."); }
    finally { setBusy(false); onBusy(false); }
  }
  async function viewHistory() {
    if (!selected) return;
    setBusy(true); onBusy(true); setError("");
    try {
      const suffix = history?.next_before_version ? "?before_version=" + history.next_before_version : "";
      const data = await api<History>("/condition-rules/drafts/" + selected.id + "/history" + suffix);
      setHistory(old => ({ ...data, items: [...(old?.items || []), ...data.items] }));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); onBusy(false); }
  }
  return <fieldset disabled={locked} style={{ border: 0, margin: 0, padding: 0 }}><section style={{ marginTop: 28, borderTop: "1px solid #dbe3ef", paddingTop: 20 }}>
    <h3>Saved rule drafts</h3>
    <p>Save the settings above as an inactive draft. Each revision keeps its author, date and reason.</p>
    {loading && <p role="status">Loading drafts…</p>}
    {truncated && <p>Showing the latest 100 drafts for this equipment.</p>}
    <div className="table-scroll"><table className="data-table">
      <thead><tr><th>Name</th><th>Version / state</th><th>Updated by</th><th>Action</th></tr></thead>
      <tbody>{drafts.map(draft => <tr key={draft.id}><td>{draft.name}</td><td>{draft.version} · Saved draft</td><td>{draft.actor_name}<small>{date(draft.created)}</small></td><td><Button type="button" disabled={busy} onClick={() => load(draft)}>Load draft</Button></td></tr>)}</tbody>
    </table></div>
    {!loading && !drafts.length && <p>No saved drafts for this equipment.</p>}
    <Button type="button" disabled={busy} onClick={async () => {
      setBusy(true); onBusy(true); setError("");
      try { await refresh(); setSelected(null); setName(""); setReason(""); setHistory(null); setMessage("Draft list refreshed. Load the current version before editing."); }
      catch (e) { setError((e as Error).message); }
      finally { setBusy(false); onBusy(false); }
    }}>Reload drafts</Button>
    <form onSubmit={save} style={{ marginTop: 16 }}>
      <fieldset disabled={busy || loading} style={{ border: 0, padding: 0 }}>
        <p>{selected ? `Editing ${selected.name}, version ${selected.version}. Saving creates the next revision.` : "Create a new draft from the settings above."}</p>
        <label>Rule name<input required maxLength={120} value={name} onChange={e => setName(e.target.value)} /></label>
        <label>Reason for saving<textarea required maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
        {error && <p role="alert" className="form-error">{error}</p>}
        {message && <p role="status">{message}</p>}
        <Button className="primary" disabled={!valid || busy || loading}>{selected ? "Save new revision" : "Save inactive draft"}</Button>
        {selected && <>
          <Button type="button" onClick={() => { setSelected(null); setName(""); setReason(""); setHistory(null); setMessage(""); }}>Start a separate draft</Button>
          {!history && <Button type="button" onClick={viewHistory}>View revision history</Button>}
        </>}
      </fieldset>
    </form>
    {history && <div><h3>Revision history</h3>
      {history.items.map(row => <details key={row.version}><summary>Version {row.version} · {row.name} · {row.actor_name} · {date(row.created)}</summary>
        <p>{row.reason}</p><p>{row.settings.channel}: above {row.settings.threshold}, clear margin {row.settings.hysteresis}, persistence {row.settings.persistence_seconds}s, maximum gap {row.settings.maximum_gap_seconds}s.</p>
      </details>)}
      {history.next_before_version !== null && <Button disabled={busy} onClick={viewHistory}>Older revisions</Button>}
    </div>}
    {selected && <LiveRulePanel key={selected.id + ":" + selected.version} ruleId={selected.id} draftVersion={selected.version} draftSettings={selected.settings} assetId={settings.asset_id} isAdmin={isAdmin} onBusy={value => { setBusy(value); onBusy(value); }} />}
  </section></fieldset>;
}
