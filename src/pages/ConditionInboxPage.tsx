import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Button } from "../components/ui";
import { RuleMatchReview } from "../components/RuleMatchReview";
type Cursor = { before_created: number; before_id: string };
type Match = { id: string; name: string; rule_version: number; asset_tag: string; asset_name: string; site: string;
  signal_state: string; triggered_at: number; ended_at: number | null; review: { state: string } };
type Inbox = { items: Match[]; total_matching: number; next_cursor: Cursor | null; boundary: string };
const stamp = (t: number | null) => t === null ? "—" : new Date(t * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST";

export function ConditionInboxPage({ site, refreshKey, canReview }: { site: string; refreshKey: number; canReview: boolean }) {
  const [filter, setFilter] = useState("unreviewed");
  const [data, setData] = useState<Inbox | null>(null);
  const [selected, setSelected] = useState<Match | null>(null);
  const [busy, setBusy] = useState(false);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [page, setPage] = useState(1);
  const generation = useRef(0);
  const scope = `${site}\u0000${filter}\u0000${canReview}`;
  const currentScope = useRef(scope);
  const loadedScope = useRef<string | null>(null);
  currentScope.current = scope;
  async function load(cursor: Cursor | null = null) {
    if (currentScope.current !== scope) return;
    const request = ++generation.current;
    if (!canReview) return;
    setBusy(true); setError("");
    const params = new URLSearchParams({ review_state: filter });
    if (site) params.set("site", site);
    if (cursor) { params.set("before_created", String(cursor.before_created)); params.set("before_id", cursor.before_id); }
    try {
      const answer = await api<Inbox>("/condition-rules/inbox?" + params.toString());
      if (generation.current === request && currentScope.current === scope) { setData(answer); setPage(old => cursor ? old + 1 : 1); }
    } catch (e) { if (generation.current === request) setError((e as Error).message); }
    finally { if (generation.current === request) setBusy(false); }
  }
  useEffect(() => {
    // Refreshing data must not erase an open review or its unsaved note.
    if (loadedScope.current !== scope) {
      setSelected(null); setData(null); setMessage(""); loadedScope.current = scope;
    }
    if (!reviewBusy) void load();
    return () => { generation.current++; };
  }, [site, filter, refreshKey, canReview, reviewBusy]);
  if (!canReview) return <section className="panel settings-card"><h2>Engineer or administrator access required</h2><p>Ask your administrator for the appropriate equipment-review role and site access.</p></section>;
  return <section className="panel settings-card">
    <h2>Condition inbox</h2><p>Review local rule matches across your permitted equipment. Signal state and review progress are shown separately.</p>
    <div className="table-toolbar">
      <label>Review status<select disabled={busy || reviewBusy} value={filter} onChange={e => setFilter(e.target.value)}>
        <option value="unreviewed">Unreviewed</option><option value="acknowledged">Acknowledged</option>
        <option value="resolved">Resolved</option><option value="all">All reviews</option>
      </select></label>
      <Button disabled={busy || reviewBusy} onClick={() => { setMessage(""); void load(); }}>Refresh inbox</Button>
    </div>
    {busy && <p role="status">Loading matches…</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {data && <>
      <p>{data.total_matching} matching records · Page {page} · {data.items.length} shown</p>
      <div className="local-note">{data.boundary}</div>
      {!data.items.length && <p>No matches for this review status and site selection.</p>}
      {!!data.items.length && <div className="table-scroll"><table className="data-table"><thead><tr><th>Equipment / site</th><th>Rule / revision</th><th>Signal / review</th><th>Triggered / ended</th><th>Action</th></tr></thead><tbody>
        {data.items.map(match => <tr key={match.id}><td>{match.asset_tag} · {match.asset_name}<small>{match.site}</small></td>
          <td>{match.name} · {match.rule_version}</td><td>{match.signal_state.replaceAll("_", " ")}<small>{match.review.state}</small></td>
          <td>{stamp(match.triggered_at)}<small>Ended: {stamp(match.ended_at)}</small></td><td><Button disabled={busy || reviewBusy} onClick={() => { setSelected(match); setMessage(""); }}>Review match</Button></td></tr>)}
      </tbody></table></div>}
      <div className="toolbar-right"><Button disabled={busy || reviewBusy || page === 1} onClick={() => void load()}>Newest matches</Button>
        <Button disabled={busy || reviewBusy || !data.next_cursor} onClick={() => { if (data.next_cursor) void load(data.next_cursor); }}>Older matches</Button></div>
    </>}
    {selected && <section style={{ marginTop: 24 }}><h3>{selected.asset_tag} · {selected.name} · Revision {selected.rule_version}</h3><p>{selected.site}</p>
      <RuleMatchReview key={selected.id} matchId={selected.id} onBusy={setReviewBusy} onSaved={async () => {
        await load(); if (currentScope.current === scope) setMessage("Review saved. The inbox was refreshed; its status filter may move the record out of this list.");
      }} />
    </section>}
  </section>;
}
