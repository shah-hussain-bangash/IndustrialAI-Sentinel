import { useEffect, useState } from "react";
import { api } from "../api";
import { Button } from "./ui";
import { RuleMatchReview } from "./RuleMatchReview";

type Identity = { match_id: string; asset: { tag: string; name: string; site: string }; rule: { name: string; version: number } };

export function ConditionMatchDetail({ matchId, site }: { matchId: string; site: string }) {
  const [record, setRecord] = useState<Identity | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let current = true;
    setRecord(null); setError(""); setLoading(true);
    api<Identity>(`/condition-rules/matches/${encodeURIComponent(matchId)}/evidence`)
      .then(result => {
        if (!current) return;
        if (result.match_id !== matchId) { setError("The returned record does not match this link. Return to the inbox and select it again."); return; }
        if (site && result.asset.site !== site) { setError("This match is outside the selected site. Return to the inbox or select its permitted site."); return; }
        setRecord(result);
      })
      .catch(() => { if (current) setError("This match could not be opened. It may be unavailable, outside your access, or temporarily unreachable. Check your connection or return to the inbox."); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [matchId, site, attempt]);
  return <section className="panel settings-card" aria-label="Linked condition match">
    <div className="table-toolbar"><h2>Condition match</h2><Button disabled={saving} onClick={() => { window.location.hash = "conditions"; }}>Back to Condition inbox</Button></div>
    <p>This link opens one saved match independently of inbox review filters. Opening it does not change its review or signal state.</p>
    {loading && <p role="status">Opening linked match…</p>}
    {error && <><p role="alert" className="form-error">{error}</p><Button onClick={() => setAttempt(value => value + 1)}>Try opening match again</Button></>}
    {record && <>
      <h3>{record.asset.tag} · {record.rule.name} · Revision {record.rule.version}</h3>
      <p>{record.asset.name} · {record.asset.site}</p>
      <p className="local-note">You can bookmark this page. Anyone opening the link must sign in and have the required role and site access.</p>
      <RuleMatchReview key={matchId} matchId={matchId} onBusy={setSaving} onSaved={async () => {}} />
    </>}
  </section>;
}
