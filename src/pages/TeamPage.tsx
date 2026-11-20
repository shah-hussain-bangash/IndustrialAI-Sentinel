import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Plus, RefreshCw, ShieldCheck, Users } from 'lucide-react';
import { api, post, ApiError, type User } from '../api';
import { Button, Spinner } from '../components/ui';

type Member = { id: string; name: string; email: string; role: string; active: boolean; site_ids: string[]; version: string };
type Directory = { items: Member[]; sites: {id: string; name: string}[]; current_user_id: string };
const roles: Record<string, string> = {observer:'Observer — view permitted site records', engineer:'Engineer — investigate and configure telemetry', approver:'Approver — review maintenance recommendations', planner:'Planner — plan and dispatch maintenance work', technician:'Technician — execute assigned maintenance work', admin:'Administrator — configure sites and workspace access', disabled:'Disabled — sign-in blocked'};

export function TeamPage({user}: {user: User}) {
  const [directory, setDirectory] = useState<Directory | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [edit, setEdit] = useState<Member | 'new' | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('observer');
  const [sites, setSites] = useState<string[]>([]);
  const [reviewed, setReviewed] = useState(false);
  const [passwordIssue, setPasswordIssue] = useState('');
  const passwordInput = useRef<HTMLInputElement>(null);
  const noticeBox = useRef<HTMLDivElement>(null);
  const errorBox = useRef<HTMLDivElement>(null);
  const formHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (edit) formHeading.current?.focus(); }, [edit]);
  useEffect(() => { if (notice) noticeBox.current?.focus(); }, [notice]);
  useEffect(() => { if (error && edit) { if (passwordIssue) passwordInput.current?.focus(); else errorBox.current?.focus(); } }, [error, passwordIssue, edit]);
  function checkPassword(value: string) {
    if (!value.trim()) return 'Enter a new password. Use 15–128 characters; the shared demo password is not allowed.';
    if (value.length < 15) return 'This password is too short. Enter a new password with at least 15 characters.';
    if (value.length > 128) return 'This password is too long. Use no more than 128 characters.';
    return '';
  }
  async function load() {
    setLoading(true); setError('');
    try { setDirectory(await api<Directory>('/team')); }
    catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  function open(member: Member | 'new') {
    setEdit(member); setName(member === 'new' ? '' : member.name);
    setEmail(member === 'new' ? '' : member.email); setPassword('');
    setRole(member === 'new' ? 'observer' : member.role);
    setSites(member === 'new' ? [] : member.site_ids); setReviewed(false); setError(''); setNotice(''); setPasswordIssue('');
  }
  async function save(e: FormEvent) {
    e.preventDefault(); if (!edit || !reviewed) return;
    if (edit === 'new') {
      const message = checkPassword(password);
      if (message) { setPasswordIssue(message); setError(message); passwordInput.current?.focus(); return; }
    }
    setBusy(true); setError('');
    try {
      const body = {name, role, site_ids: sites};
      if (edit === 'new') await post('/team', {...body, email, password});
      else await api(`/team/${edit.id}`, {method:'PUT', body: JSON.stringify({...body, expected_version:edit.version})});
      setPassword(''); setEdit(null);
      setNotice(edit === 'new' ? 'Account created. Share its credentials privately; no email was sent.' : 'Access saved. Existing sessions for this person were revoked.');
      await load();
    } catch (e) {
      const passwordError = e instanceof ApiError ? e.fields.password : undefined;
      if (passwordError) setPasswordIssue(passwordError + ' Enter a new password and try again.');
      setError(passwordError ? 'Account not created. Enter a new password in the highlighted field.' : (e as Error).message);
    }
    finally { setBusy(false); }
  }
  if (user.role !== 'admin') return <div className="panel team-panel"><ShieldCheck/><h2>Administrator access required</h2><p>Ask a company administrator to manage team roles and site access.</p></div>;
  if (loading && !directory) return <Spinner/>;
  const visible = directory?.items.filter(m => `${m.name} ${m.email} ${m.role}`.toLowerCase().includes(search.toLowerCase())) || [];
  return <div className="team-workspace">
    {error && !edit && <div className="error-banner" role="alert">{error}</div>}
    {notice && <div className="success-banner" role="status" ref={noticeBox} tabIndex={-1}>{notice}</div>}
    {!directory ? <Button onClick={load}>Retry</Button> : <>
      <div className="team-metrics">
        <div className="panel"><Users/><strong>{directory.items.filter(m=>m.active).length}</strong><span>Active team members</span></div>
        <div className="panel"><ShieldCheck/><strong>{directory.items.filter(m=>m.role==='admin').length}</strong><span>Administrators</span></div>
        <div className="panel"><strong>{directory.sites.length}</strong><span>Company sites</span></div>
      </div>
      <section className="panel team-panel">
        <div className="team-toolbar"><div><h2>People and permissions</h2><p>Manage company-wide roles and explicit site access.</p></div><div><Button icon={RefreshCw} onClick={load} disabled={busy || loading}>Refresh</Button> <Button className="primary" icon={Plus} onClick={()=>open('new')} disabled={busy}>Add team member</Button></div></div>
        <label className="team-search">Find a team member<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search name, email or role"/></label>
        <p className="team-explanation">A role applies across the selected sites. Team administration requires access to every company site. Your own account is protected.</p>
        <div className="team-table"><table><thead><tr><th>Team member</th><th>Role / status</th><th>Permitted sites</th><th>Action</th></tr></thead><tbody>{visible.map(m=><tr key={m.id}><td><strong>{m.name}</strong><small>{m.email}</small></td><td><span className={m.active?'team-active':'team-disabled'}>{m.active ? m.role : 'Disabled'}</span></td><td>{m.site_ids.map(id=>directory.sites.find(s=>s.id===id)?.name || 'Unavailable site').join(', ') || 'No sites'}</td><td>{m.id===directory.current_user_id ? <span>Your account</span> : <Button onClick={()=>open(m)} disabled={busy}>Manage access</Button>}</td></tr>)}</tbody></table>{!visible.length && <p>No team members match your search.</p>}</div>
      </section>
      {edit && <section className="panel team-panel" aria-labelledby="team-form-title">
        <h2 id="team-form-title" ref={formHeading} tabIndex={-1}>{edit==='new'?'Create a team account':`Manage ${edit.name}`}</h2>
        <p>{edit==='new'?'Create an email sign-in account. No invitation email will be sent.':'Saving these changes signs this person out. Disabling blocks new sign-ins; records and history remain available.'}</p>
        <form onSubmit={save}>
          <div className="team-form-grid">
            <label>Full name<input required maxLength={100} value={name} onChange={e=>setName(e.target.value)} disabled={busy}/></label>
            <label>Email address<input type="email" required value={email} onChange={e=>setEmail(e.target.value)} readOnly={edit!=='new'} disabled={busy} maxLength={200}/></label>
            <label>Role<select value={role} onChange={e=>{setRole(e.target.value);setReviewed(false);}} disabled={busy}>{Object.entries(roles).filter(([key])=>edit!=='new'||key!=='disabled').map(([key,title])=><option key={key} value={key}>{title}</option>)}</select></label>
            {edit==='new' && <label>Initial password<input ref={passwordInput} type="password" required minLength={15} maxLength={128} autoComplete="new-password" value={password} aria-invalid={!!passwordIssue} aria-describedby="team-password-help team-password-error" onBlur={()=>{const message=checkPassword(password);if(message)setPasswordIssue(message);}} onInvalid={()=>setPasswordIssue(checkPassword(password))} onChange={e=>{setPassword(e.target.value);setPasswordIssue('');setError('');}} disabled={busy}/><small id="team-password-help">Use a new password of 15–128 characters. The shared demo password cannot be used. Share privately and ask the user to change it in Account settings.</small><small id="team-password-error" className="team-field-error" role="alert">{passwordIssue}</small></label>}
          </div>
          <fieldset className="team-sites" disabled={busy}><legend>Permitted sites — select at least one</legend>{directory.sites.map(site=><label key={site.id}><input type="checkbox" checked={sites.includes(site.id)} onChange={e=>{setSites(e.target.checked?[...sites,site.id]:sites.filter(id=>id!==site.id));setReviewed(false);}}/>{site.name}</label>)}</fieldset>
          {role==='admin' && <p className="team-explanation">Administrators assigned to every site can manage the entire team and company profile.</p>}
          <label className="team-confirm"><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)} disabled={busy}/>I have reviewed the role and selected sites{role==='disabled'?' and want to disable this account':''}.</label>
          {error && <div className="error-banner" ref={errorBox} role="alert" tabIndex={-1}>{error}</div>}
          <div className="team-actions"><Button type="button" onClick={()=>{setEdit(null);setPassword('');}} disabled={busy}>Cancel</Button><Button className="primary" type="submit" disabled={busy || !reviewed || !sites.length}>{busy?'Saving…':edit==='new'?'Create account':'Save access'}</Button></div>
        </form>
      </section>}
    </>}
  </div>;
}
