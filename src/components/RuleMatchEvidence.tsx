import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Button } from "./ui";
import type { RuleSettings } from "./ConditionRuleDrafts";

type Evidence = {
  match_id: string; asset: { tag: string; name: string; site: string };
  rule: { version: number; name: string; settings: RuleSettings; actor_name: string; created: number; reason: string };
  match: { signal_state: string; started_at: number; triggered_at: number; ended_at: number | null };
  snapshot: { id: string; timestamp: number; quality: string; signals: { channel: string; unit: string; value: number | null }[] };
  boundary: string;
};
const stamp = (t: number | null) => t === null ? "—" : new Date(t * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST";

export function RuleMatchEvidence({ matchId }: { matchId: string }) {
  const [data, setData] = useState<Evidence | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  async function load() {
    const request = ++generation.current;
    setBusy(true); setError(""); setData(null);
    try {
      const result = await api<Evidence>(`/condition-rules/matches/${encodeURIComponent(matchId)}/evidence`);
      if (generation.current === request) setData(result);
    } catch (e) { if (generation.current === request) setError((e as Error).message); }
    finally { if (generation.current === request) setBusy(false); }
  }
  useEffect(() => { void load(); return () => { generation.current++; }; }, [matchId]);
  const settings = data?.rule.settings;
  const unit = data?.snapshot.signals.find(signal => signal.channel === settings?.channel)?.unit ?? "";
  return <section style={{ marginTop: 20 }} aria-label="Triggering evidence">
    <h3>Triggering evidence</h3>
    {busy && <p role="status">Loading historical evidence…</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    <Button disabled={busy} onClick={() => void load()}>Reload evidence</Button>
    {data && settings && <>
      <p><strong>{data.asset.tag} · {data.asset.name}</strong> · {data.asset.site}</p>
      <div className="local-note">{data.boundary}</div>
      <h4>{data.rule.name} · Matched revision {data.rule.version}</h4>
      <p>Signal: {settings.channel}. Trigger above {settings.threshold} {unit}. Clear at or below {Number((settings.threshold - settings.hysteresis).toFixed(8))} {unit}.</p>
      <p>Required time above limit: {settings.persistence_seconds} seconds. Maximum gap: {settings.maximum_gap_seconds} seconds.</p>
      <p>Revision saved by {data.rule.actor_name} · {stamp(data.rule.created)}. Reason: {data.rule.reason}</p>
      <p>Above-limit sequence started: {stamp(data.match.started_at)}. Triggered: {stamp(data.match.triggered_at)}. Ended: {stamp(data.match.ended_at)}.</p>
      <p>Recorded signal state: {data.match.signal_state.replaceAll("_", " ")}.</p>
      <h4>Trigger snapshot</h4>
      <p>Reading: {data.snapshot.id} · {stamp(data.snapshot.timestamp)} · Quality: {data.snapshot.quality}</p>
      <div className="table-scroll"><table className="data-table"><thead><tr><th>Signal</th><th>Recorded value</th><th>Role in this rule</th></tr></thead><tbody>
        {data.snapshot.signals.map(signal => <tr key={signal.channel}><td>{signal.channel}</td><td>{signal.value === null ? "Unavailable" : `${signal.value} ${signal.unit}`}</td><td>{signal.channel === settings.channel ? "Trigger signal" : "Context only"}</td></tr>)}
      </tbody></table></div>
    </>}
  </section>;
}
