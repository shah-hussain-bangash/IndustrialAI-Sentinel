import { useEffect, useState } from "react";
import { ArrowRight, Bell, TriangleAlert, X } from "lucide-react";
import { api, date, type Episode } from "../api";

type AttentionMatch = { id: string; asset_tag: string; site: string; name: string;
  rule_version: number; signal_state: string; triggered_at: number };
type AttentionInbox = { items: AttentionMatch[]; total_matching: number };

export function AttentionPanel({ site, canReview, episodes, openConditions, openAsset, openMonitor, close }: {
  site: string; canReview: boolean; episodes: Episode[] | null;
  openConditions: () => void; openAsset: (id: string) => void; openMonitor: () => void; close: () => void;
}) {
  const [result, setResult] = useState<AttentionInbox | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(canReview);
  const [refresh, setRefresh] = useState(0);
  const [checkedAt, setCheckedAt] = useState<number | null>(null);
  useEffect(() => {
    let current = true;
    setResult(null); setError(""); setCheckedAt(null); setBusy(canReview);
    if (canReview) {
      const params = new URLSearchParams({ review_state: "unreviewed" });
      if (site) params.set("site", site);
      api<AttentionInbox>("/condition-rules/inbox?" + params.toString())
        .then(answer => { if (current) { setResult(answer); setCheckedAt(Date.now() / 1000); } })
        .catch(e => { if (current) setError((e as Error).message); })
        .finally(() => { if (current) setBusy(false); });
    }
    return () => { current = false; };
  }, [site, canReview, refresh]);
  const openEpisodes = (episodes || []).filter(episode => episode.state !== "resolved" && (!site || episode.site === site));
  return <section className="popover notification-popover attention-panel" aria-label="Workspace attention">
    <div className="attention-heading"><h4>Workspace attention</h4><button className="icon-btn" aria-label="Close workspace attention" onClick={close}><X size={16} /></button></div>
    <p className="attention-scope">{site || "All permitted sites"}</p>
    <p className="attention-note">Local review queue. Email and escalation are not enabled here.</p>
    <h5>Condition rules</h5>
    {!canReview ? <p>Rule review is available to engineers and administrators with site access.</p> : <>
      {busy && <p role="status">Checking unreviewed rule matches…</p>}
      {error && <p role="alert" className="form-error">Could not check rule matches. {error}</p>}
      {!busy && result && <>
        <p role="status"><strong>{result.total_matching}</strong> unreviewed rule matches</p>
        {result.total_matching === 0 && <p>No rule matches need initial review in this site scope.</p>}
        {result.items.slice(0, 4).map(match => <div className="attention-match" key={match.id}>
          <Bell size={15} /><span><strong>{match.asset_tag} · {match.name}</strong>
            <small>{match.site} · Revision {match.rule_version}</small>
            <small>Signal: {match.signal_state.replaceAll("_", " ")} · Triggered {date(match.triggered_at, true)} GST</small></span>
        </div>)}
        {result.total_matching > 4 && <p>Showing the four newest. Open the inbox for all matches.</p>}
        {checkedAt !== null && <p className="attention-note">Checked {date(checkedAt, true)} GST. Refresh to check again.</p>}
      </>}
      <div className="attention-actions"><button className="btn" disabled={busy} onClick={() => setRefresh(value => value + 1)}>Refresh rule matches</button>
        <button className="btn" onClick={openConditions}>Open Condition inbox <ArrowRight size={14} /></button></div>
    </>}
    <h5>Demonstration episodes</h5>
    <p>{episodes === null ? "Workspace episodes are not loaded. Refresh the workspace to check them." : `${openEpisodes.length} open demonstration episodes · separate from saved rule matches`}</p>
    {openEpisodes.slice(0, 4).map(episode => <button className="attention-episode" key={episode.id} onClick={() => openAsset(episode.asset_id)}>
      <TriangleAlert size={16} /><span><strong>{episode.asset_tag}</strong><small>{episode.title}</small></span>
    </button>)}
    <button onClick={openMonitor}>Open monitoring <ArrowRight size={14} /></button>
  </section>;
}
