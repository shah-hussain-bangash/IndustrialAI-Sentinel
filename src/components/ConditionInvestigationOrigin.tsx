import type { ConditionOrigin } from "../api";
const stamp = (t: number | null) => t === null ? "—" : new Date(t * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST";

export function ConditionInvestigationOrigin({ origin }: { origin: ConditionOrigin }) {
  return <section className="modal-section" aria-label="Condition match origin">
    <h3>Condition match origin</h3>
    <p>{origin.asset.tag} · {origin.rule.name} · Matched revision {origin.rule.version}</p>
    <p>Historical trigger: {stamp(origin.snapshot.timestamp)}. Analysis snapshot: {stamp(origin.analysis_snapshot.timestamp)}.</p>
    <p>Captured when this investigation was prepared. This evidence does not update as readings or rule drafts change.</p>
    <details><summary>Show captured condition evidence</summary>
      <p>Match: {origin.match_id} · Recorded state at preparation: {origin.match.signal_state.replaceAll("_", " ")}</p>
      <p>Investigation note: {origin.investigation_note}</p>
      <p>Rule channel: {origin.rule.settings.channel}. Trigger above {origin.rule.settings.threshold}; clear margin {origin.rule.settings.hysteresis}, in the matching signal's units. Persistence: {origin.rule.settings.persistence_seconds}s; maximum gap: {origin.rule.settings.maximum_gap_seconds}s.</p>
      <p>Matched revision saved by {origin.rule.actor_name} · {stamp(origin.rule.created)}. Reason: {origin.rule.reason}</p>
      <p>Sequence started: {stamp(origin.match.started_at)}. Triggered: {stamp(origin.match.triggered_at)}. Ended: {stamp(origin.match.ended_at)}.</p>
      {[{ label: "Historical trigger snapshot", snapshot: origin.snapshot }, { label: "Snapshot used for analysis", snapshot: origin.analysis_snapshot }].map(({ label, snapshot }) => {
        return <div key={label}><h4>{label}</h4><p>{snapshot.id} · {stamp(snapshot.timestamp)} · Quality: {snapshot.quality}</p>
          <div className="table-scroll"><table className="data-table"><thead><tr><th>Signal</th><th>Captured value</th></tr></thead><tbody>
            {snapshot.signals.map(signal => <tr key={signal.channel}><td>{signal.channel}</td><td>{signal.value === null ? "Unavailable" : `${signal.value} ${signal.unit}`}</td></tr>)}
          </tbody></table></div></div>;
      })}
      <p>{origin.boundary}</p>
    </details>
  </section>;
}
