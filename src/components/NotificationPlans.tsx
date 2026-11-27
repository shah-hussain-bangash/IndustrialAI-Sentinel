import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, post, type Asset } from "../api";
import { Button } from "./ui";
import { NotificationPlanReview } from "./NotificationPlanReview";

type Person = { id: string; name: string; role?: string };
type Plan = { version: number; rule_version: number; name: string; recipients: Person[]; actor_name: string; reason: string; created: number };
type Info = { latest_rule_version: number; rule_name: string; asset_tag: string; current: Plan | null; recipients: Person[]; recipients_truncated: boolean;
  recent_matches: {id: string; rule_version: number; state: string; triggered_at: number}[]; matches_truncated: boolean; boundary: string };
type History = {items: Plan[]; next_before_version: number | null};
type Preview = {plan: Plan; plan_rule_is_current: boolean; subject: string; match_id: string; match_route: string; boundary: string; eligible_configured_count: number;
  recipients: (Person & {currently_eligible: boolean; email_address_configured: boolean})[]; review: {state: string};
  evidence: {rule: {version: number; name: string}; match: {signal_state: string; triggered_at: number}; snapshot: {timestamp: number; quality: string; signals: {channel: string; value: number | null; unit: string}[]}} };
const stamp = (epoch: number) => new Date(epoch * 1000).toLocaleString("en-GB", {timeZone:"Asia/Dubai"}) + " GST";

export function NotificationPlans() {
  const [assets,setAssets]=useState<Asset[]>([]), [assetId,setAssetId]=useState(""), [error,setError]=useState(""), [loading,setLoading]=useState(true), [busy,setBusy]=useState(false);
  useEffect(()=>{ let current=true; api<Asset[]>("/assets").then(rows=>{if(current){setAssets(rows);setAssetId(rows[0]?.id||"");}}).catch(e=>{if(current)setError((e as Error).message);}).finally(()=>{if(current)setLoading(false);});return()=>{current=false;};},[]);
  return <section className="panel settings-card full-span"><h2>Notification plan drafts</h2>
    <div className="local-note" style={{display:"block"}}><strong>Email delivery is off.</strong><p>Prepare recipients for a saved rule revision and inspect a historical message preview. Saving and previewing do not send or queue email, activate routing, change site access or dispatch work.</p></div>
    {loading&&<p role="status">Loading permitted equipment…</p>}{error&&<p className="form-error" role="alert">{error}</p>}
    <label>Equipment for notification planning<select disabled={loading||busy} value={assetId} onChange={e=>setAssetId(e.target.value)}>{assets.map(a=><option key={a.id} value={a.id}>{a.tag} · {a.site}</option>)}</select></label>
    {!loading&&!error&&!assets.length&&<p>No permitted equipment is available.</p>}
    {assetId&&<RulePicker key={assetId} assetId={assetId} onBusy={setBusy}/>}
  </section>;
}

function RulePicker({assetId,onBusy}:{assetId:string;onBusy:(busy:boolean)=>void}) {
  const [rules,setRules]=useState<{id:string;name:string;version:number}[]>([]),[ruleId,setRuleId]=useState("");
  const [loading,setLoading]=useState(true),[editorBusy,setEditorBusy]=useState(false),[error,setError]=useState(""),[truncated,setTruncated]=useState(false);
  useEffect(()=>{onBusy(loading||editorBusy);return()=>onBusy(false);},[loading,editorBusy,onBusy]);
  useEffect(()=>{let current=true;api<{items:typeof rules;truncated:boolean}>("/condition-rules/drafts?asset_id="+encodeURIComponent(assetId))
    .then(answer=>{if(current){setRules(answer.items);setRuleId(answer.items[0]?.id||"");setTruncated(answer.truncated);}}).catch(e=>{if(current)setError((e as Error).message);}).finally(()=>{if(current)setLoading(false);});return()=>{current=false;};},[assetId]);
  return <><label>Saved rule<select disabled={loading||editorBusy} value={ruleId} onChange={e=>setRuleId(e.target.value)}>{rules.map(r=><option key={r.id} value={r.id}>{r.name} · revision {r.version}</option>)}</select></label>
    {loading&&<p role="status">Loading saved rules…</p>}{error&&<p role="alert" className="form-error">{error}</p>}
    {truncated&&<p>Showing the newest 100 saved rules for this equipment.</p>}
    {!loading&&!error&&!rules.length&&<p>Save a rule in Condition rules before preparing its notification plan.</p>}
    {ruleId&&<PlanEditor key={ruleId} ruleId={ruleId} onBusy={setEditorBusy}/>}</>;
}

function PlanEditor({ruleId,onBusy}:{ruleId:string;onBusy:(busy:boolean)=>void}) {
  const [data,setData]=useState<Info|null>(null),[name,setName]=useState(""),[reason,setReason]=useState(""),[ids,setIds]=useState<string[]>([]),[names,setNames]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(""),[message,setMessage]=useState("");
  const [reviewBusy,setReviewBusy]=useState(false);
  const [search,setSearch]=useState(""),[matchId,setMatchId]=useState(""),[preview,setPreview]=useState<Preview|null>(null),[history,setHistory]=useState<History|null>(null);
  const current=useRef(true),path="/notification-plans/rules/"+ruleId;
  useEffect(()=>{onBusy(busy||loading||reviewBusy);return()=>onBusy(false);},[busy,loading,reviewBusy,onBusy]);
  async function load() {
    const answer=await api<Info>(path);
    if(!current.current)return;
    setData(answer);setName(answer.current?.name||"");setIds(answer.current?.recipients.map(p=>p.id)||[]);
    setNames(Object.fromEntries([...answer.recipients,...(answer.current?.recipients||[])].map(p=>[p.id,p.name])));
    setReason("");setSearch("");setPreview(null);setHistory(null);setMatchId(answer.recent_matches[0]?.id||"");
  }
  useEffect(()=>{current.current=true;void load().catch(e=>{if(current.current)setError((e as Error).message);}).finally(()=>{if(current.current)setLoading(false);});return()=>{current.current=false;};},[ruleId]);
  async function reload() {setBusy(true);setError("");setMessage("");try{await load();}catch(e){if(current.current){setData(null);setError((e as Error).message);}}finally{if(current.current)setBusy(false);}}
  async function searchPeople() {
    if(!data)return;setBusy(true);setError("");
    try{const answer=await api<Info>(path+"?recipient_name="+encodeURIComponent(search));
      if(!current.current)return;
      if(answer.latest_rule_version!==data.latest_rule_version||(answer.current?.version||0)!==(data.current?.version||0))throw new Error("The rule or plan changed. Reload the saved plan before continuing.");
      setData(old=>old?{...old,recipients:answer.recipients,recipients_truncated:answer.recipients_truncated}:old);
      setNames(old=>({...old,...Object.fromEntries(answer.recipients.map(p=>[p.id,p.name]))}));
    }catch(e){if(current.current)setError((e as Error).message);}finally{if(current.current)setBusy(false);}
  }
  function toggle(id:string) {setPreview(null);setIds(old=>old.includes(id)?old.filter(v=>v!==id):[...old,id]);}
  async function save(event:FormEvent) {
    event.preventDefault();if(!data||busy||!ids.length||ids.length>10)return;setBusy(true);setError("");setMessage("");setPreview(null);
    try{await post(path,{expected_version:data.current?.version||0,expected_rule_version:data.latest_rule_version,name,recipient_ids:ids,reason});if(!current.current)return;await load();if(current.current)setMessage("Inactive notification plan saved. No email was queued or sent.");}
    catch(e){if(current.current){setData(null);setError((e as Error).message+" Reload the saved plan before retrying.");}}
    finally{if(current.current)setBusy(false);}
  }
  const dirty=!!data?.current&&(name!==data.current.name||JSON.stringify(ids)!==JSON.stringify(data.current.recipients.map(p=>p.id))||!!reason.trim());
  async function previewMatch() {
    if(!data?.current||!matchId||busy||dirty)return;setBusy(true);setError("");setPreview(null);
    try{const answer=await post<Preview>(path+"/preview",{expected_plan_version:data.current.version,match_id:matchId});if(current.current)setPreview(answer);}
    catch(e){if(current.current)setError((e as Error).message);}finally{if(current.current)setBusy(false);}
  }
  async function historyPage() {
    setBusy(true);setError("");try{const answer=await api<History>(path+"/history"+(history?.next_before_version?"?before_version="+history.next_before_version:""));if(current.current)setHistory(old=>({...answer,items:[...(old?.items||[]),...answer.items]}));}
    catch(e){if(current.current)setError((e as Error).message);}finally{if(current.current)setBusy(false);}
  }
  return <div style={{marginTop:20}}>
    {loading&&<p role="status">Loading notification planning…</p>}{error&&<p role="alert" className="form-error">{error}</p>}{message&&<p role="status">{message}</p>}
    <Button type="button" disabled={busy||loading||reviewBusy} onClick={()=>void reload()}>Reload saved notification plan</Button>
    {data&&<fieldset disabled={busy||loading} style={{border:0,padding:0}}><fieldset disabled={reviewBusy} style={{border:0,padding:0}}><h3>{data.asset_tag} · {data.rule_name}</h3><p>Current saved rule revision: {data.latest_rule_version}. Event: new saved-rule match. Planned channel: email.</p>
      {data.current&&<div className="local-note" style={{display:"block"}}><strong>Saved plan revision {data.current.version}: {data.current.name}</strong><p>Bound to rule revision {data.current.rule_version} · {data.current.actor_name} · {stamp(data.current.created)}</p><p>Recipients: {data.current.recipients.map(p=>p.name).join(", ")}</p><p>{data.current.reason}</p></div>}
      {data.current&&data.current.rule_version!==data.latest_rule_version&&<p className="form-error">The saved rule has changed. Save a new notification-plan revision to bind it to the current rule. Historical previews still use the saved plan’s exact revision.</p>}
      <label>Find a planned recipient by name<input maxLength={100} value={search} onChange={e=>setSearch(e.target.value)}/></label><Button type="button" onClick={()=>void searchPeople()}>Find eligible recipients</Button>
      {data.recipients_truncated&&<p>Showing the first 100 matching eligible accounts. Search by name to narrow the list.</p>}
      <form onSubmit={save}><label>Notification plan name<input required maxLength={120} value={name} onChange={e=>{setName(e.target.value);setPreview(null);}}/></label>
      <fieldset><legend>Planned recipients — select one to ten</legend><p>Engineers and administrators with current access to this equipment site. No email addresses are displayed or changed here.</p>
        {!data.recipients.length&&<p>No matching eligible accounts.</p>}{data.recipients.map(p=><label className="checkbox-row" key={p.id}><input type="checkbox" checked={ids.includes(p.id)} disabled={!ids.includes(p.id)&&ids.length>=10} onChange={()=>toggle(p.id)}/>{p.name} · {p.role}</label>)}
      </fieldset>
      <p>Selected: {ids.length}/10</p>{ids.map(id=><div key={id}>{names[id]||"Saved account"} <Button type="button" onClick={()=>toggle(id)}>Remove planned recipient</Button></div>)}
      <label>Reason for this plan revision<textarea required minLength={5} maxLength={1000} value={reason} onChange={e=>{setReason(e.target.value);setPreview(null);}}/></label>
      <Button className="primary" disabled={!ids.length||ids.length>10}>Save inactive notification plan</Button></form>
      {data.current&&<><h3>Historical message preview</h3><p>Uses the saved plan and an existing match from its exact rule revision. It does not simulate delivery or create a notification event.</p>
        {dirty&&<p>Save or reload changes before previewing the saved plan.</p>}
        <label>Saved match to preview<select value={matchId} onChange={e=>{setMatchId(e.target.value);setPreview(null);}}>{data.recent_matches.map(m=><option key={m.id} value={m.id}>{stamp(m.triggered_at)} · revision {m.rule_version} · {m.state}</option>)}</select></label>
        {data.matches_truncated&&<p>Showing the newest 20 matches for this saved plan’s rule revision.</p>}{!data.recent_matches.length&&<p>No stored matches for this exact rule revision. A preview becomes available after a match exists.</p>}
        <Button type="button" disabled={dirty||!matchId} onClick={()=>void previewMatch()}>Preview saved notification plan</Button>
        {!history&&<Button type="button" onClick={()=>void historyPage()}>View notification plan history</Button>}
      </>}
      {preview&&<section className="local-note" style={{display:"block",marginTop:20}}><h3>Preview only — email delivery off</h3><strong>{preview.subject}</strong><p>Plan revision {preview.plan.version} · Rule revision {preview.evidence.rule.version}</p>
        <p>Historical match: {preview.evidence.match.signal_state} · Review: {preview.review.state} · Triggered {stamp(preview.evidence.match.triggered_at)}</p>
        <p>Captured snapshot: {stamp(preview.evidence.snapshot.timestamp)} · {preview.evidence.snapshot.quality}</p>
        <p>{preview.evidence.snapshot.signals.map(s=>`${s.channel}: ${s.value??"unavailable"} ${s.unit}`).join(" · ")}</p>
        {!preview.plan_rule_is_current&&<p>This plan references an older rule revision.</p>}
        <h4>Current recipient checks</h4>{preview.recipients.map(p=><p key={p.id}>{p.name}: {!p.currently_eligible?"No longer eligible for this equipment site":p.email_address_configured?"Eligible; account email configured (delivery not verified)":"Eligible; demonstration or unsupported email address"}</p>)}
        <p>{preview.eligible_configured_count} eligible accounts with a configured email address. Delivery remains disabled for every recipient.</p>
        <a href={preview.match_route}>Open captured match evidence</a><p>{preview.boundary}</p>
      </section>}
      {history&&<section><h3>Notification plan revision history</h3>{history.items.map(p=><details key={p.version}><summary>Plan revision {p.version} · Rule revision {p.rule_version} · {p.actor_name}</summary><p>{p.name} · {stamp(p.created)}</p><p>Recipients: {p.recipients.map(r=>r.name).join(", ")}</p><p>{p.reason}</p></details>)}{history.next_before_version!==null&&<Button type="button" onClick={()=>void historyPage()}>Older notification plan revisions</Button>}</section>}
    </fieldset>
      {data.current&&<NotificationPlanReview key={`${ruleId}:${data.current.version}`} ruleId={ruleId} version={data.current.version} dirty={dirty} onBusy={setReviewBusy}/>}
    </fieldset>}
  </div>;
}
