import { useEffect, useState, type FormEvent } from 'react';
import { post, ApiError } from '../api';
import { Button } from './ui';

export function ForgotPassword({onBack}: {onBack:()=>void}) {
  const [email,setEmail]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  async function submit(e:FormEvent) {
    e.preventDefault();setBusy(true);setError('');
    try { const result=await post<{message:string}>('/accounts/forgot-password',{email});setMessage(result.message); }
    catch(e){setError((e as Error).message);}
    finally{setBusy(false);}
  }
  return <section aria-label="Password recovery"><h3>Forgot your password?</h3><p>Enter your account email to request a single-use password-reset link.</p>{message ? <p className="success-banner" role="status">{message}</p> : <form onSubmit={submit}><label>Email address<input type="email" required maxLength={200} autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/></label>{error&&<p className="form-error" role="alert">{error}</p>}<Button type="submit" className="primary full-width" disabled={busy}>{busy?'Requesting…':'Send reset link'}</Button></form>}<Button type="button" onClick={onBack} disabled={busy}>Back to sign in</Button></section>;
}

export function AccountLinkScreen({token,onDone}: {token:string;onDone:()=>void}) {
  const [info,setInfo]=useState<{purpose:string;expires:number}|null>(null);
  const [error,setError]=useState('');
  const [password,setPassword]=useState('');
  const [confirm,setConfirm]=useState('');
  const [busy,setBusy]=useState(false);
  const [complete,setComplete]=useState(false);
  useEffect(()=>{let active=true;post<{purpose:string;expires:number}>('/accounts/link-info',{token}).then(v=>{if(active)setInfo(v);}).catch(e=>{if(active)setError((e as Error).message);});return()=>{active=false;};},[token]);
  async function submit(e:FormEvent) {
    e.preventDefault();setError('');
    if(password!==confirm){setError('The passwords do not match. Enter the same new password in both fields.');return;}
    setBusy(true);
    try{await post('/accounts/set-password',{token,password});setPassword('');setConfirm('');setComplete(true);}
    catch(e){setError(e instanceof ApiError && e.fields.password ? e.fields.password+' Enter a new password.' : (e as Error).message);}
    finally{setBusy(false);}
  }
  return <div className="login-page account-link-page"><section className="login-story"><a className="brand" href="#"><img src="/sentinel.svg" alt=""/><span>sentinelAI</span></a><div className="account-link-story"><div className="eyebrow">YOUR SECURE OPERATIONS WORKSPACE</div><h1>A personal account.<br/>A clearer connection.</h1><p>Choose your own password to access the sites and workflows assigned to you.</p></div></section><section className="login-form-side"><div className="login-form-inner"><h2>{complete?'Your password is ready.':info?.purpose==='invite'?'Welcome to your team.':'Choose a new password.'}</h2><p>{complete?'Sign in with your email and new password. Existing account sessions have been revoked.':'Links expire and can be used once. Keep your password private.'}</p>{error&&<p className="form-error" role="alert">{error}</p>}{info&&!complete&&<form className="account-password-form" onSubmit={submit}><label>New password<input type="password" required minLength={15} maxLength={128} autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/><small>Use 15–128 characters. The shared demo password is not allowed.</small></label><label>Confirm new password<input type="password" required minLength={15} maxLength={128} autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} disabled={busy}/></label><Button type="submit" className="primary full-width" disabled={busy}>{busy?'Saving…':'Save my password'}</Button></form>}{!info&&!error&&<p role="status">Checking your secure link…</p>}<Button onClick={onDone} disabled={busy}>Return to sign in</Button>{!info&&error&&<p>For a reset, request another link from Forgot password. For an invitation, ask your administrator to resend it.</p>}</div></section></div>;
}
