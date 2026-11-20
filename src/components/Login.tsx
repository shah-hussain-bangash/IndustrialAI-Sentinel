import { useState, useEffect, type FormEvent } from "react";
import {
  ArrowRight,
  UserCheck,
  Wrench,
  CalendarDays,
  Settings2,
  ClipboardCheck,
  Loader2,
  Radio,
  ShieldCheck,
  Sparkles,
  Waves,
  Eye,
  EyeOff,
  LockKeyhole,
} from "lucide-react";
import { api, post, human, type User } from "../api";

import { Button, MiniSpark, EquipmentArt } from "./ui";
const roleIcons = {
  admin: Settings2,
  approver: UserCheck,
  engineer: Wrench,
  planner: CalendarDays,
  technician: ClipboardCheck,
};
export function LoginChoices({
  onLogin,
  showHeading = false,
}: {
  onLogin: (u: User, csrf: string) => void;
  showHeading?: boolean;
}) {
  const [demo, setDemo] = useState<{
      enabled: boolean;
      password: string;
      accounts: User[];
    } | null>(null),
    [busy, setBusy] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    api<{ enabled: boolean; password: string; accounts: User[] }>("/auth/demo")
      .then(setDemo)
      .catch(() =>
        setError(
          "Unable to connect to Sentinel. Check that your application server is running, then refresh this page.",
        ),
      );
  }, []);
  async function select(u: User) {
    setBusy(u.id);
    setError("");
    try {
      const r = await post<{ user: User; csrf: string }>("/auth/login", {
        email: u.email,
        password: demo!.password,
      });
      onLogin(r.user, r.csrf);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  return (
    <section
      className={showHeading ? "demo-login-options" : "login-role-picker"}
      aria-label="Demo role access"
    >
      {showHeading && demo?.enabled && (
        <>
          <div className="demo-section-heading">
            <h3>Explore a demo workspace</h3>
            <span>DEMO ACCESS</span>
          </div>
          <p className="demo-intro">
            Choose your role. Step into the workspace.
          </p>
        </>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="demo-accounts">
        {demo?.enabled &&
          demo.accounts
            .filter((a) => a.role !== "observer")
            .map((u) => {
              const RoleIcon =
                roleIcons[u.role as keyof typeof roleIcons] || ShieldCheck;
              return (
                <button
                  key={u.id}
                  className={`role-card role-${u.role}`}
                  disabled={!!busy}
                  onClick={() => select(u)}
                >
                  <span className="role-card-icon">
                    <RoleIcon size={19} />
                  </span>
                  <div>
                    <strong>{human(u.role)}</strong>
                    <small>{u.name}</small>
                  </div>
                  {busy === u.id ? (
                    <Loader2 className="spin" size={16} />
                  ) : (
                    <ArrowRight size={16} />
                  )}
                </button>
              );
            })}
      </div>
      {demo?.enabled && (
        <p className="login-demo-note">
          <ShieldCheck size={13} />
          <span>
            Local demonstration · simulated equipment. Accounts with personal
            passwords use email sign-in.
          </span>
        </p>
      )}
    </section>
  );
}
export function LoginScreen({
  onLogin,
}: {
  onLogin: (u: User, csrf: string) => void;
}) {
  const [email, setEmail] = useState("engineer@sentinel.local"),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [showPassword, setShowPassword] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await post<{ user: User; csrf: string }>("/auth/login", {
        email,
        password,
      });
      onLogin(r.user, r.csrf);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <section className="login-story">
        <a className="brand" href="#">
          <img src="/sentinel.svg" alt="" />
          <div>
            <strong>
              sentinel<span>AI</span>
            </strong>
            <small>INDUSTRIAL INTELLIGENCE</small>
          </div>
        </a>
        <div className="login-story-content">
          <span className="login-tag">
            <span className="signal-dot" />
            ENERGY & INDUSTRIAL OPERATIONS
          </span>
          <h1>
            Industrial intelligence.
            <br />
            Operational confidence.
          </h1>
          <p>
            See the signals. Understand the evidence. Give your team a clearer
            path from equipment insight to approved action.
          </p>
          <div className="login-plant">
            <div className="plant-caption">
              <span>
                <Radio size={12} /> CONNECTED EQUIPMENT
              </span>
              <span>Illustrative view</span>
            </div>
            <EquipmentArt kind="Pump" size="large" />
            <div className="floating-signal">
              <Waves size={17} />
              <span>Equipment intelligence</span>
              <MiniSpark />
            </div>
            <div className="floating-approval">
              <ShieldCheck size={17} />
              Human review built in
            </div>
          </div>
          <div className="login-workflow" aria-label="Workflow preview">
            <span className="login-preview-label">ONE CONNECTED WORKFLOW</span>
            <div>
              <span>
                <b>01</b> Monitor signals
              </span>
              <ArrowRight size={15} />
              <span>
                <b>02</b> Review evidence
              </span>
              <ArrowRight size={15} />
              <span>
                <b>03</b> Approve action
              </span>
            </div>
          </div>
          <div className="login-capabilities">
            <span>
              <Radio size={16} />
              Sensor monitoring
            </span>
            <span>
              <Sparkles size={16} />
              Evidence workflows
            </span>
            <span>
              <ClipboardCheck size={16} />
              Maintenance planning
            </span>
          </div>
        </div>
        <div className="login-story-footer">
          <span>IndustrialAI Sentinel · Reference application</span>
          <span>
            Local environment <i className="signal-dot" />
          </span>
        </div>
      </section>
      <section className="login-form-side">
        <div className="login-form-inner">
          <div className="login-lock">
            <LockKeyhole size={24} />
          </div>
          <div className="eyebrow">YOUR OPERATIONS WORKSPACE</div>
          <h2>Welcome back.</h2>
          <p>Sign in to your IndustrialAI Sentinel workspace.</p>
          <div className="manual-login">
            <form onSubmit={submit}>
              <label>
                Email address
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                  required
                />
              </label>
              <label>
                Password
                <span className="password-field">
                  <input
                    type={showPassword ? "text" : "password"}
                    aria-label="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    required
                    placeholder="Enter your password"
                  />
                  <button
                    type="button"
                    aria-label={
                      showPassword ? "Hide password" : "Show password"
                    }
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </span>
              </label>
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
              <Button
                type="submit"
                className="primary full-width"
                disabled={busy}
              >
                {busy ? "Signing in…" : "Sign in to workspace"}
                <ArrowRight size={16} />
              </Button>
            </form>
          </div>
          <LoginChoices onLogin={onLogin} showHeading />
          <div className="login-footnote">
            <ShieldCheck size={16} />
            <p>
              This demo uses simulated equipment and procedures. No industrial
              controls are connected.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
