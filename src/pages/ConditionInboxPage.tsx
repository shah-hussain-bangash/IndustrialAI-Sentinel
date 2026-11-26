import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Button } from "../components/ui";
import { ConditionMatchDetail } from "../components/ConditionMatchDetail";
import { investigationStatusLabel } from "../lib/investigationStatus";
import { conditionMatchHash } from "../lib/conditionMatchRoute";
type Cursor = { before_created: number; before_id: string };
type Match = { id: string; name: string; rule_version: number; asset_tag: string; asset_name: string; site: string;
  signal_state: string; triggered_at: number; ended_at: number | null; review: { state: string };
  ownership: { owner_name: string | null; owner_id: string | null; eligible: boolean };
  investigation: { id?: string; title?: string; state: string; version?: number; approved_until?: number | null; approval_current?: boolean } | null };
type Inbox = { items: Match[]; total_matching: number; next_cursor: Cursor | null; boundary: string };
const stamp = (t: number | null) => t === null ? "—" : new Date(t * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST";

export function ConditionInboxPage({ site, refreshKey, canReview, matchId = null }: { site: string; refreshKey: number; canReview: boolean; matchId?: string | null }) {
  if (!canReview) return <section className="panel settings-card"><h2>Engineer or administrator access required</h2><p>Ask your administrator for the appropriate equipment-review role and site access.</p></section>;
  return matchId ? <ConditionMatchDetail key={`${matchId}:${site}`} matchId={matchId} site={site} /> : <ConditionInboxList site={site} refreshKey={refreshKey} />;
}

function ConditionInboxList({ site, refreshKey }: { site: string; refreshKey: number }) {
  const [filter, setFilter] = useState("unreviewed");
  const [ownership, setOwnership] = useState("all");
  const [investigationState, setInvestigationState] = useState("all");
  const [data, setData] = useState<Inbox | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const generation = useRef(0);
  const scope = `${site}\u0000${filter}\u0000${ownership}\u0000${investigationState}`;
  const currentScope = useRef(scope);
  const loadedScope = useRef<string | null>(null);
  currentScope.current = scope;
  async function load(cursor: Cursor | null = null) {
    if (currentScope.current !== scope) return;
    const request = ++generation.current;
    setBusy(true); setError("");
    const params = new URLSearchParams({ review_state: filter, ownership, investigation_state: investigationState });
    if (site) params.set("site", site);
    if (cursor) { params.set("before_created", String(cursor.before_created)); params.set("before_id", cursor.before_id); }
    try {
      const answer = await api<Inbox>("/condition-rules/inbox?" + params.toString());
      if (generation.current === request && currentScope.current === scope) { setData(answer); setPage(old => cursor ? old + 1 : 1); }
    } catch (e) { if (generation.current === request) setError((e as Error).message); }
    finally { if (generation.current === request) setBusy(false); }
  }
  useEffect(() => {
    // Keep pagination and data tied to the current list filters.
    if (loadedScope.current !== scope) {
      setData(null); loadedScope.current = scope;
    }
    void load();
    return () => { generation.current++; };
  }, [site, filter, ownership, investigationState, refreshKey]);
  return <section className="panel settings-card">
    <h2>Condition inbox</h2><p>Review local rule matches across your permitted equipment. Signal state and review progress are shown separately.</p>
    <div className="table-toolbar" style={{ flexWrap: "wrap", alignItems: "end" }}>
      <label>Review status<select disabled={busy} value={filter} onChange={e => setFilter(e.target.value)}>
        <option value="unreviewed">Unreviewed</option><option value="acknowledged">Acknowledged</option>
        <option value="resolved">Resolved</option><option value="all">All reviews</option>
      </select></label>
      <label>Ownership<select disabled={busy} value={ownership} onChange={e => setOwnership(e.target.value)}>
        <option value="all">All owners</option><option value="mine">Assigned to me</option><option value="unassigned">Unassigned</option>
      </select></label>
      <label>Investigation status<select disabled={busy} value={investigationState} onChange={e => setInvestigationState(e.target.value)}>
        <option value="all">All investigations</option><option value="not_started">Not started</option>
        <option value="awaiting_review">Awaiting review</option><option value="approved">Approved · current</option>
        <option value="approval_needed">Approval needs review</option><option value="rejected">Returned for revision</option>
        <option value="dispatched">Work order planned</option><option value="unavailable">Link unavailable</option>
      </select></label>
      <Button disabled={busy} onClick={() => { void load(); }}>Refresh inbox</Button>
    </div>
    {busy && <p role="status">Loading matches…</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {data && <>
      <p>{data.total_matching} matching records · Page {page} · {data.items.length} shown</p>
      <div className="local-note">{data.boundary}</div>
      {!data.items.length && <p>No matches for these review, ownership, investigation and site filters.</p>}
      {!!data.items.length && <div className="table-scroll"><table className="data-table"><thead><tr><th>Equipment / site</th><th>Rule / revision</th><th>Signal / review</th><th>Owner</th><th>Investigation</th><th>Triggered / ended</th><th>Action</th></tr></thead><tbody>
        {data.items.map(match => <tr key={match.id}><td>{match.asset_tag} · {match.asset_name}<small>{match.site}</small></td>
          <td>{match.name} · {match.rule_version}</td><td>{match.signal_state.replaceAll("_", " ")}<small>{match.review.state}</small></td>
          <td>{match.ownership.owner_name || "Unassigned"}{match.ownership.owner_id && !match.ownership.eligible && <small>{match.review.state === "resolved" ? "Owner access changed" : "Reassignment needed"}</small>}</td>
          <td>{match.investigation ? <>{investigationStatusLabel(match.investigation.state, match.investigation.approval_current)}
            {match.investigation.id && <><small>{match.investigation.title} · Version {match.investigation.version}</small>
              {match.investigation.state === "approved" && <small>Approval until: {stamp(match.investigation.approved_until ?? null)}</small>}
              <Button disabled={busy} onClick={() => { window.location.hash = `intelligence/${match.investigation!.id}`; }}>Open investigation</Button></>}
            {match.investigation.state === "unavailable" && <small>Ask an administrator to check the link.</small>}</> : "Not started"}</td>
          <td>{stamp(match.triggered_at)}<small>Ended: {stamp(match.ended_at)}</small></td><td><a className="btn" href={conditionMatchHash(match.id)}>Review match</a></td></tr>)}
      </tbody></table></div>}
      <div className="toolbar-right"><Button disabled={busy || page === 1} onClick={() => void load()}>Newest matches</Button>
        <Button disabled={busy || !data.next_cursor} onClick={() => { if (data.next_cursor) void load(data.next_cursor); }}>Older matches</Button></div>
    </>}
  </section>;
}
