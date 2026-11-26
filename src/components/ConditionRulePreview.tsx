import { useEffect, useState, type FormEvent } from "react";
import { api, post, type Asset } from "../api";
import { ConditionRuleDrafts, type RuleSettings } from "./ConditionRuleDrafts";

type Result = {
  asset_tag: string; sample_count: number; trigger_count: number;
  good_samples: number; invalid_samples: number; continuity_breaks: number;
  history_truncated: boolean; active_at_last_sample: boolean;
  first_observed_at: number | null; last_observed_at: number | null; boundary: string;
  windows: { started_at: number; triggered_at: number; ended_at: number | null; end_reason: string }[];
};
const channels = { vibration: "Vibration · mm/s", temperature: "Temperature · °C", pressure: "Pressure · bar", flow: "Flow · m³/h" };
const defaults = { vibration: "4.5", temperature: "85", pressure: "6", flow: "140" };
function stamp(value: number | null) {
  return value === null ? "—" : new Date(value * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST";
}

export function ConditionRulePreview() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [assetId, setAssetId] = useState("");
  const [channel, setChannel] = useState<keyof typeof channels>("vibration");
  const [threshold, setThreshold] = useState("4.5");
  const [hysteresis, setHysteresis] = useState("0.2");
  const [persistence, setPersistence] = useState("30");
  const [gap, setGap] = useState("300");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [draftBusy, setDraftBusy] = useState(false);
  const settings: RuleSettings = { asset_id: assetId, channel, threshold: Number(threshold), hysteresis: Number(hysteresis),
    persistence_seconds: Number(persistence), maximum_gap_seconds: Number(gap) };
  const valid = [threshold, hysteresis, persistence, gap].every(value => value.trim() !== "" && Number.isFinite(Number(value)));
  useEffect(() => {
    let active = true;
    api<Asset[]>("/assets").then(items => {
      if (active) { setAssets(items); setAssetId(items[0]?.id || ""); }
    }).catch(e => { if (active) setError((e as Error).message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  function changed() { setResult(null); setError(""); }
  async function preview(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError(""); setResult(null);
    try {
      const answer = await post<Result>("/condition-rules/preview", { asset_id: assetId, channel,
        threshold: Number(threshold), hysteresis: Number(hysteresis),
        persistence_seconds: Number(persistence), maximum_gap_seconds: Number(gap) });
      setResult(answer);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <section className="panel settings-card full-span">
    <h2>Condition rule preview</h2>
    <p>Try a high-limit rule against stored equipment snapshots before deciding how it should behave.</p>
    <div className="local-note">Preview does not save or activate a rule. Use Saved rule drafts below to retain settings. All saved drafts remain inactive.</div>
    {loading && <p role="status">Loading permitted equipment…</p>}
    <form onSubmit={preview}>
      <fieldset disabled={busy || loading || draftBusy} style={{ border: 0, padding: 0, margin: "16px 0" }}>
        <div className="settings-grid">
          <label>Equipment<select required value={assetId} onChange={e => { changed(); setAssetId(e.target.value); }}>
            {assets.map(a => <option key={a.id} value={a.id}>{a.tag} · {a.site}</option>)}
          </select></label>
          <label>Signal<select value={channel} onChange={e => { const next = e.target.value as keyof typeof channels; changed(); setChannel(next); setThreshold(defaults[next]); setHysteresis("0"); }}>
            {Object.entries(channels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></label>
          <label>Trigger above<input type="number" required step="any" min="-273.15" max="100000" value={threshold} onChange={e => { changed(); setThreshold(e.target.value); }} /></label>
          <label>Clear margin (same signal units)<input type="number" required step="any" min="0" max="100000" value={hysteresis} onChange={e => { changed(); setHysteresis(e.target.value); }} /></label>
          <label>Time above limit before triggering (seconds)<input type="number" required min="0" max="86400" step="1" value={persistence} onChange={e => { changed(); setPersistence(e.target.value); }} /></label>
          <label>Maximum gap between readings (seconds)<input type="number" required min="1" max="86400" step="1" value={gap} onChange={e => { changed(); setGap(e.target.value); }} /></label>
        </div>
      </fieldset>
      <p>Trigger when readings stay above the limit for the selected time. Clear at or below the limit minus the clear margin. Poor-quality readings and long gaps reset continuity.</p>
      <p>Suggested values are demonstration examples and need engineering review for real equipment.</p>
      {error && <p role="alert" className="form-error">{error}</p>}
      {!loading && !assets.length && <p>No permitted equipment is available.</p>}
      <button className="btn primary" disabled={busy || loading || draftBusy || !assetId}>{busy ? "Evaluating…" : "Preview rule"}</button>
    </form>
    {result && <div aria-live="polite" style={{ marginTop: 24 }}>
      <h3>{result.asset_tag}: {result.trigger_count} historical matches</h3>
      <p>{result.sample_count} snapshots · {result.good_samples} good · {result.invalid_samples} invalid · {result.continuity_breaks} continuity breaks</p>
      <p>History: {stamp(result.first_observed_at)} to {stamp(result.last_observed_at)}</p>
      {result.history_truncated && <p>Limited to the latest 500 snapshots. Earlier history was excluded.</p>}
      <div className="local-note">{result.boundary}</div>
      {result.active_at_last_sample && <p>The rule was active at the final historical sample. This does not establish the equipment’s current condition.</p>}
      {!result.sample_count && <p>No stored snapshots to evaluate. Independent sensor events require reviewed alignment before they appear here.</p>}
      {!!result.windows.length && <div className="table-scroll"><table className="data-table">
        <thead><tr><th>Above limit since</th><th>Triggered</th><th>Ended</th><th>Reason</th></tr></thead>
        <tbody>{result.windows.map((w, i) => <tr key={i}><td>{stamp(w.started_at)}</td><td>{stamp(w.triggered_at)}</td><td>{stamp(w.ended_at)}</td><td>{({ cleared: "Cleared", data_gap: "Data gap", invalid_sample: "Invalid sample", end_of_history: "End of available history" })[w.end_reason] || w.end_reason}</td></tr>)}</tbody>
      </table></div>}
    </div>}
    {assetId && <ConditionRuleDrafts key={assetId} settings={settings} valid={valid && !busy} locked={busy} onBusy={setDraftBusy} onLoad={value => {
      changed(); setChannel(value.channel); setThreshold(String(value.threshold)); setHysteresis(String(value.hysteresis));
      setPersistence(String(value.persistence_seconds)); setGap(String(value.maximum_gap_seconds));
    }} />}
  </section>;
}
