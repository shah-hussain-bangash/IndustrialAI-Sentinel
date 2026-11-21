import { useState,type FormEvent } from 'react';
import { api,type User } from '../api';
import { Button } from './ui';
export function MfaSignIn({csrf,onLogin,onCancel}:{csrf:string;onLogin:(user:User,csrf:string)=>void;onCancel:()=>void}) {
  const [code,setCode]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  async function submit(e:FormEvent){e.preventDefault();setBusy(true);setError('');try{const result=await api<{user:User;csrf:string}>('/auth/mfa/verify',{method:'POST',headers:{'X-MFA-CSRF':csrf},body:JSON.stringify({code})});setCode('');onLogin(result.user,result.csrf);}catch(e){setCode('');setError((e as Error).message);}finally{setBusy(false);}}
  return <section className="mfa-signin"><h3>Verify administrator sign-in</h3><p>Enter a fresh six-digit code from your authenticator app, or an unused backup code. Verification expires after five minutes.</p><form onSubmit={submit}><label>Authenticator or backup code<input type="password" autoComplete="one-time-code" required maxLength={64} value={code} onChange={e=>setCode(e.target.value)} disabled={busy}/></label>{error&&<p className="form-error" role="alert">{error}</p>}<Button className="primary full-width" type="submit" disabled={busy}>{busy?'Verifying…':'Verify and sign in'}</Button><Button type="button" disabled={busy} onClick={onCancel}>Start sign-in again</Button></form></section>;
}
