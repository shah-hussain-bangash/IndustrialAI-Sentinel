import { useEffect,useRef,useState,type FormEvent } from "react";
import { api,post } from "../api";
import { Button } from "./ui";
type Run={id:string;version:number;state:string;attempts:number;next_attempt_at:number|null;created:number;plan_version:number;review_version:number;match_id:string;recipients:{id:string;name:string}[];actor_name:string;reason:string};
type Info={plan:{version:number;rule_version:number;name:string}|null;latest_rule_version:number;review_version:number;server_time:number;can_enqueue:boolean;gate_reasons:string[];
  items:Run[];next_before_id:string|null;matches:{id:string;triggered_at:number;state:string}[];matches_truncated:boolean;boundary:string};
type Detail=Run&{can_control:boolean;attempt_due:boolean;server_time:number;gate_reasons:string[];source_plan:{name:string;rule_version:number};source_match:{triggered_at:number;state:string};boundary:string;
  history:{version:number;action:string;attempt_number:number;check_reasons:string[];actor_name:string;reason:string;created:number}[]};
const stamp=(value:number|null)=>value===null?"No further attempt scheduled":new Date(value*1000).toLocaleString("en-GB",{timeZone:"Asia/Dubai"})+" GST";
const words=(value:string)=>value.replaceAll("_"," ");
const checkStyle={display:"flex",flexDirection:"row",justifyContent:"flex-start",alignItems:"center",gap:8} as const;

export function NotificationRehearsals({ruleId,planVersion,dirty,onBusy}:{ruleId:string;planVersion:number;dirty:boolean;onBusy:(busy:boolean)=>void}) {
  const [data,setData]=useState<Info|null>(null),[detail,setDetail]=useState<Detail|null>(null),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true);
  const [error,setError]=useState(""),[message,setMessage]=useState(""),[matchId,setMatchId]=useState(""),[reason,setReason]=useState(""),[confirmed,setConfirmed]=useState(false);
  const [action,setAction]=useState("simulate_success"),[controlReason,setControlReason]=useState(""),[controlConfirmed,setControlConfirmed]=useState(false);
  const current=useRef(true),path=`/notification-plans/rules/${ruleId}/rehearsals`;
  useEffect(()=>{onBusy(busy||loading);return()=>onBusy(false);},[busy,loading,onBusy]);
  async function load(older=false) {
    const answer=await api<Info>(path+(older&&data?.next_before_id?`?before_id=${data.next_before_id}`:""));
    if(answer.plan?.version!==planVersion)throw new Error("The saved notification plan changed. Reload the saved plan before rehearsing it.");
    if(current.current){setData(old=>({...answer,items:older&&old?[...old.items,...answer.items]:answer.items}));setMatchId(old=>answer.matches.some(m=>m.id===old)?old:answer.matches[0]?.id||"");setConfirmed(false);}
  }
  useEffect(()=>{current.current=true;void load().catch(e=>{if(current.current)setError((e as Error).message);}).finally(()=>{if(current.current)setLoading(false);});return()=>{current.current=false;};},[ruleId,planVersion]);
  async function reload(older=false) {
    setBusy(true);setError("");setMessage("");try{await load(older);if(detail){const answer=await api<Detail>(path+"/"+detail.id);if(current.current){setDetail(answer);setControlConfirmed(false);}}}
    catch(e){if(current.current){setData(null);setDetail(null);setError((e as Error).message);}}finally{if(current.current)setBusy(false);}
  }
  async function open(id:string) {
    setBusy(true);setError("");try{const answer=await api<Detail>(path+"/"+id);if(current.current){setDetail(answer);setControlReason("");setControlConfirmed(false);setAction("simulate_success");}}
    catch(e){if(current.current){setDetail(null);setError((e as Error).message);}}finally{if(current.current)setBusy(false);}
  }
  async function enqueue(event:FormEvent) {
    event.preventDefault();if(!data?.can_enqueue||busy||dirty||!confirmed||!matchId)return;
    setBusy(true);setError("");setMessage("");
    try{const answer=await post<Detail>(path,{expected_plan_version:planVersion,expected_rule_version:data.latest_rule_version,expected_review_version:data.review_version,match_id:matchId,reason,confirmed:true});
      if(!current.current)return;setDetail(answer);setReason("");setConfirmed(false);setControlConfirmed(false);await load();if(current.current)setMessage("Queued for manual simulation only. No email was queued or sent.");}
    catch(e){if(current.current){setData(null);setDetail(null);setError((e as Error).message+" Reload rehearsals before retrying.");}}finally{if(current.current)setBusy(false);}
  }
  async function control(event:FormEvent) {
    event.preventDefault();if(!detail||busy||dirty||!controlConfirmed)return;setBusy(true);setError("");setMessage("");
    try{const answer=await post<Detail>(path+"/"+detail.id+"/control",{expected_version:detail.version,action,reason:controlReason,confirmed:true});
      if(!current.current)return;setDetail(answer);setControlReason("");setControlConfirmed(false);await load();if(current.current)setMessage(`Rehearsal state: ${words(answer.state)}. This is a simulated outcome, not mailbox delivery.`);}
    catch(e){if(current.current){setDetail(null);setError((e as Error).message+" Reload the rehearsal before retrying.");}}finally{if(current.current)setBusy(false);}
  }
  return <section style={{marginTop:24}}><h3>Local delivery rehearsal</h3>
    <p>Exercise a durable local simulation record, retry timing and cancellation for an independently approved plan. Nothing connects to Gmail or sends a message.</p>
    {loading&&<p role="status">Loading delivery rehearsals…</p>}{error&&<p role="alert" className="form-error">{error}</p>}{message&&<p role="status">{message}</p>}
    <Button type="button" disabled={busy||loading} onClick={()=>void reload()}>Reload delivery rehearsals</Button>
    {data&&<fieldset disabled={busy||loading} style={{border:0,padding:0}}><div className="local-note" style={{display:"block"}}><strong>Simulation only — email delivery off</strong><p>{data.boundary}</p><p>Checked {stamp(data.server_time)}. Reload after planning-review or account changes and before the next due attempt.</p></div>
      {data.gate_reasons.map(note=><p key={note}>{note}</p>)}{dirty&&<p>Save or reload unsaved plan edits before taking a rehearsal action.</p>}
      {data.can_enqueue?<form onSubmit={enqueue}><fieldset disabled={dirty} style={{border:0,padding:0}}>
        <label>Historical match for a simulated rehearsal<select value={matchId} onChange={e=>{setMatchId(e.target.value);setConfirmed(false);}}>{data.matches.map(m=><option key={m.id} value={m.id}>{stamp(m.triggered_at)} · {m.state}</option>)}</select></label>
        {data.matches_truncated&&<p>Showing the newest 20 matches for this exact rule revision.</p>}{!data.matches.length&&<p>No matching historical rule matches are available.</p>}
        <label>Reason for this simulation<textarea required minLength={5} maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
        <label style={checkStyle}><input type="checkbox" style={{width:"auto",flexShrink:0,margin:0}} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I reviewed this exact plan, its independent review and captured match. Queue a manual simulation only.</label>
        <Button className="primary" disabled={!confirmed||!matchId||reason.trim().length<5}>Queue simulated rehearsal</Button>
      </fieldset></form>:<p>Only an administrator can queue a rehearsal after the current exact plan has independent planning approval and eligible recipients.</p>}
      <h4>Saved rehearsal records</h4>{!data.items.length&&<p>No delivery rehearsals have been queued.</p>}
      {data.items.map(row=><div key={row.id}><p>{words(row.state)} · Plan revision {row.plan_version} · Review {row.review_version} · Attempts {row.attempts}/3 · {stamp(row.created)}</p><Button type="button" onClick={()=>void open(row.id)}>Open simulated rehearsal</Button></div>)}
      {data.next_before_id&&<Button type="button" onClick={()=>void reload(true)}>Older rehearsal records</Button>}
      {detail&&<section style={{marginTop:20}}><h4>Selected rehearsal — {words(detail.state)}</h4><p>{detail.source_plan.name} · Plan revision {detail.plan_version}, rule revision {detail.source_plan.rule_version}, review {detail.review_version}</p>
        <p>Captured historical match: {stamp(detail.source_match.triggered_at)} · {detail.source_match.state} · <a href={"#conditions/"+detail.match_id}>Open captured match evidence</a></p><p>Planned account identities: {detail.recipients.map(p=>p.name).join(", ")}</p>
        <p>Queued by {detail.actor_name} · {stamp(detail.created)} · {detail.reason}</p><p>Attempts recorded: {detail.attempts}/3. Next: {stamp(detail.next_attempt_at)}</p>
        <p>Checked {stamp(detail.server_time)}. Retryable failures wait 30 seconds, then 60 seconds; a third failed attempt exhausts the rehearsal. There is no automatic retry worker.</p>
        {detail.gate_reasons.map(note=><p key={note}>{note}</p>)}
        {detail.can_control&&<form onSubmit={control}><fieldset disabled={dirty} style={{border:0,padding:0}}>
          <label>Simulated outcome or cancellation<select value={action} onChange={e=>{setAction(e.target.value);setControlConfirmed(false);}}>
            <option value="simulate_success">Simulate success</option><option value="simulate_retryable_failure">Simulate retryable failure</option><option value="simulate_permanent_failure">Simulate permanent failure</option><option value="cancel">Cancel this simulation</option></select></label>
          {!!detail.gate_reasons.length&&action!=="cancel"&&<p>Current checks failed. This action will record a blocked rehearsal instead of simulating an attempt.</p>}
          {!detail.attempt_due&&action!=="cancel"&&!detail.gate_reasons.length&&<p>The next simulated attempt is not due. Reload after its scheduled time.</p>}
          <label>Reason for the rehearsal action<textarea required minLength={5} maxLength={1000} value={controlReason} onChange={e=>setControlReason(e.target.value)}/></label>
          <label style={checkStyle}><input type="checkbox" style={{width:"auto",flexShrink:0,margin:0}} checked={controlConfirmed} onChange={e=>setControlConfirmed(e.target.checked)}/>Record this simulation-only action; no message delivery is authorized.</label>
          <Button className="primary" disabled={!controlConfirmed||controlReason.trim().length<5||(!detail.attempt_due&&action!=="cancel"&&!detail.gate_reasons.length)}>Record rehearsal action</Button>
        </fieldset></form>}
        <h4>Complete simulation history</h4>{detail.history.map(event=><details key={event.version}><summary>Version {event.version} · {words(event.action)} · Attempts recorded {event.attempt_number}</summary><p>{event.actor_name} · {stamp(event.created)}</p><p>{event.reason}</p>{event.check_reasons.map(note=><p key={note}>Check at action: {note}</p>)}</details>)}
      </section>}
    </fieldset>}
  </section>;
}
