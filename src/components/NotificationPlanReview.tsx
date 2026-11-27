import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, post } from "../api";
import { Button } from "./ui";
type Event = {version:number;plan_version:number;rule_version:number;plan_name:string;state:"approved"|"rejected";actor_name:string;reason:string;created:number};
type Status = {saved_plan:{version:number;rule_version:number;name:string;actor_name:string;reason:string;created:number;recipients:{id:string;name:string}[]};
  latest_rule_version:number;plan_rule_is_current:boolean;review_version:number;current_decision:Event["state"]|null;last_review:Event|null;can_review:boolean;can_approve:boolean;
  recipient_checks:{id:string;name:string;currently_eligible:boolean;email_address_configured:boolean}[];boundary:string;items:Event[];next_before_version:number|null};
const stamp=(epoch:number)=>new Date(epoch*1000).toLocaleString("en-GB",{timeZone:"Asia/Dubai"})+" GST";

export function NotificationPlanReview({ruleId,version,dirty,onBusy}:{ruleId:string;version:number;dirty:boolean;onBusy:(busy:boolean)=>void}) {
  const [data,setData]=useState<Status|null>(null),[error,setError]=useState(""),[message,setMessage]=useState("");
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[decision,setDecision]=useState<Event["state"]>("approved"),[reason,setReason]=useState(""),[confirmed,setConfirmed]=useState(false);
  const current=useRef(true),path=`/notification-plans/rules/${ruleId}/reviews`;
  useEffect(()=>{onBusy(busy||loading);return()=>onBusy(false);},[busy,loading,onBusy]);
  async function load(older=false) {
    const answer=await api<Status>(path+(older&&data?.next_before_version?`?before_version=${data.next_before_version}`:""));
    if(answer.saved_plan.version!==version)throw new Error("The notification plan has a newer revision. Reload the saved plan before reviewing it.");
    if(current.current){setData(old=>({...answer,items:older&&old?[...old.items,...answer.items]:answer.items}));setConfirmed(false);setDecision(answer.can_approve?"approved":"rejected");}
  }
  useEffect(()=>{current.current=true;void load().catch(e=>{if(current.current)setError((e as Error).message);}).finally(()=>{if(current.current)setLoading(false);});return()=>{current.current=false;};},[ruleId,version]);
  async function reload(older=false) {
    setBusy(true);setError("");setMessage("");try{await load(older);}catch(e){if(current.current){setData(null);setError((e as Error).message);}}finally{if(current.current)setBusy(false);}
  }
  async function submit(event:FormEvent) {
    event.preventDefault();if(!data||busy||dirty||!confirmed||!data.can_review||(decision==="approved"&&!data.can_approve))return;
    setBusy(true);setError("");setMessage("");
    try{await post(path,{decision,expected_plan_version:version,expected_rule_version:data.latest_rule_version,expected_review_version:data.review_version,reason,confirmed:true});
      if(!current.current)return;setData(null);setReason("");setConfirmed(false);await load();if(current.current)setMessage("Planning review saved. Email addresses and delivery are not authorized by this decision.");}
    catch(e){if(current.current){setData(null);setConfirmed(false);setError((e as Error).message+" Reload planning review before retrying.");}}
    finally{if(current.current)setBusy(false);}
  }
  return <section style={{marginTop:24}}><h3>Independent notification plan review</h3>
    <p>An administrator other than the author can approve or reject the exact saved plan for planning only. This does not approve email addresses or enable message delivery.</p>
    {loading&&<p role="status">Loading notification planning review…</p>}{error&&<p className="form-error" role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    <Button type="button" disabled={busy||loading} onClick={()=>void reload()}>Reload notification planning review</Button>
    {data&&<><div className="local-note" style={{display:"block"}}><strong>Saved plan revision {version}: {data.saved_plan.name}</strong>
      <p>Bound rule revision {data.saved_plan.rule_version} · Author: {data.saved_plan.actor_name} · {stamp(data.saved_plan.created)}</p>
      <p>Planned account identities: {data.saved_plan.recipients.map(p=>p.name).join(", ")}</p><p>{data.saved_plan.reason}</p>
      <strong>Current decision: {data.current_decision?`${data.current_decision} for planning only`:"Awaiting independent planning review"}</strong>
      {data.last_review&&data.last_review.plan_version!==version&&<p>The last decision applies to plan revision {data.last_review.plan_version}. This revision needs its own review.</p>}
      <p>{data.boundary}</p></div>
      {!data.plan_rule_is_current&&<p className="form-error">This plan references an older rule revision. Save a new plan revision before requesting planning approval of the current rule.</p>}
      <h4>Current recipient checks — separate from the saved decision</h4>
      {data.recipient_checks.map(p=><p key={p.id}>{p.name}: {p.currently_eligible?"Current site access eligible":"Current site access ineligible"}; {p.email_address_configured?"account email configured, delivery not verified":"demonstration or unsupported email address"}.</p>)}
      {dirty&&<p role="status">Save or reload your unsaved edits before reviewing the saved notification plan.</p>}
      {data.can_review?<form onSubmit={submit}><fieldset disabled={busy||dirty} style={{border:0,padding:0}}>
        {!data.can_approve&&<p>Planning approval is blocked until the plan uses the current rule revision and all selected reviewers have current site access. A rejection may still be recorded.</p>}
        <label>Notification planning decision<select value={decision} onChange={e=>{setDecision(e.target.value as Event["state"]);setConfirmed(false);}}><option value="approved" disabled={!data.can_approve}>Approve saved plan for planning</option><option value="rejected">Reject saved plan</option></select></label>
        <label>Notification planning review note<textarea required minLength={5} maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
        <label className="checkbox-row" style={{display:"flex",flexDirection:"row",justifyContent:"flex-start",alignItems:"center",gap:8}}><input type="checkbox" style={{width:"auto",flexShrink:0,margin:0}} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I reviewed saved plan revision {version}, its rule revision and planned account identities. This is a planning decision only.</label>
        <Button className="primary" disabled={!confirmed||reason.trim().length<5}>Save notification planning review</Button>
      </fieldset></form>:<p>A different administrator from this saved plan’s author must record the planning decision.</p>}
      <h4>Notification planning review history</h4>{!data.items.length&&<p>No notification planning decisions have been recorded.</p>}
      {data.items.map(row=><details key={row.version}><summary>Review {row.version} · Plan revision {row.plan_version} · {row.state} · {row.actor_name}</summary><p>{row.plan_name} · Rule revision {row.rule_version} · {stamp(row.created)}</p><p>{row.reason}</p></details>)}
      {data.next_before_version!==null&&<Button type="button" disabled={busy} onClick={()=>void reload(true)}>Older notification planning reviews</Button>}
    </>}
  </section>;
}
