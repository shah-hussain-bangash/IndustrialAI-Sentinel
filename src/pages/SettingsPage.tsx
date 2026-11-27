import { useState, type FormEvent } from "react";
import {
  Check,
  CircleHelp,
  Database,
  ExternalLink,
  RefreshCw,
  TriangleAlert,
  LockKeyhole,
} from "lucide-react";
import {
  api,
  post,
  human,
  type User,
  type Operations,
  type Preferences,
} from "../api";

import { initials, Badge, Button } from "../components/ui";
import type { Run } from "../types";
import { GatewayPanel } from "../components/GatewayPanel";
import { RecoveryPanel } from "../components/RecoveryPanel";
import { SiteDirectory } from "../components/SiteDirectory";
import { AdminMfaPanel } from "../components/AdminMfaPanel";
import { ConditionRulePreview } from "../components/ConditionRulePreview";
import { MaintenanceWindowDrafts } from "../components/MaintenanceWindowDrafts";
export function SettingsPage({
  user,
  operations,
  prefs,
  setPrefs,
  run,
  switchAccount,
  onPasswordChanged,
}: {
  user: User;
  operations: Operations;
  prefs: Preferences;
  setPrefs: (p: Preferences) => void;
  run: Run;
  switchAccount: () => void;
  onPasswordChanged: () => void;
}) {
  const [section, setSection] = useState("workspace");
  const sections = [
    ...(user.role==='admin'?[{id:'security',label:'Administrator MFA'}]:[]),
    { id: "workspace", label: "Workspace" },
    { id: "telemetry", label: "Telemetry access" },
    ...(["admin", "engineer"].includes(user.role) ? [{ id: "rules", label: "Condition rules" }] : []),
    ...(["admin", "engineer"].includes(user.role) ? [{ id: "windows", label: "Maintenance windows" }] : []),
    { id: "sites", label: "Site directory" },
    { id: "recovery", label: "Backup & recovery" },
    { id: "account", label: "Account & password" },
    { id: "system", label: "System status" },
  ];
  const [draft, setDraft] = useState(prefs);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  async function changePassword(event: FormEvent) {
    event.preventDefault();
    if (passwordBusy) return;
    setPasswordError("");
    if (newPassword !== confirmation) {
      setPasswordError("The new passwords do not match.");
      return;
    }
    setPasswordBusy(true);
    try {
      await post("/auth/password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmation("");
      onPasswordChanged();
    } catch (error) {
      setPasswordError((error as Error).message);
    } finally {
      setPasswordBusy(false);
    }
  }
  return (
    <div className="settings-layout">
      <nav className="settings-navigation" aria-label="Settings sections">
        {sections.map((item) => (
          <button
            key={item.id}
            type="button"
            className={section === item.id ? "active" : ""}
            aria-current={section === item.id ? "page" : undefined}
            onClick={() => setSection(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <div className="settings-context">
        <span>{sections.find((item) => item.id === section)?.label}</span>
        <span>
          Signed in as <strong>{human(user.role)}</strong> · {user.email}
        </span>
      </div>
      <div className="settings-grid">
        {section === "rules" && ["admin", "engineer"].includes(user.role) && <ConditionRulePreview isAdmin={user.role === "admin"} />}
        {section === "windows" && ["admin", "engineer"].includes(user.role) && <MaintenanceWindowDrafts key={user.id} />}
        {section==='security'&&user.role==='admin'&&<AdminMfaPanel onRemoved={onPasswordChanged}/>}
        <section
          className="panel settings-card"
          hidden={section !== "workspace"}
        >
          <h2>Your workspace profile</h2>
          <p>Identity and permissions are enforced by the backend.</p>
          <div className="profile-summary">
            <span className="avatar large">{initials(user.name)}</span>
            <div>
              <h3>{user.name}</h3>
              <p>{user.email}</p>
              <Badge value="healthy">{human(user.role)}</Badge>
            </div>
          </div>
          <dl>
            {user.sites.map((s) => (
              <div key={s}>
                <dt>Permitted site</dt>
                <dd>{s}</dd>
              </div>
            ))}
          </dl>
          <Button icon={RefreshCw} onClick={switchAccount}>
            Switch demo account
          </Button>
        </section>
        <section
          className="panel settings-card"
          hidden={section !== "workspace"}
        >
          <h2>Display preferences</h2>
          <p>
            Saved per account. Display times currently use Gulf Standard Time.
          </p>
          <label className="toggle-row">
            <span>
              <strong>Compact workspace</strong>
              <small>Reduce table and card spacing.</small>
            </span>
            <input
              type="checkbox"
              checked={draft.compact}
              onChange={(e) =>
                setDraft({ ...draft, compact: e.target.checked })
              }
            />
          </label>
          <div className="local-note">
            <CircleHelp size={16} />
            <span>
              No email notifications are sent by this local application.
            </span>
          </div>
          <Button
            className="primary"
            icon={Check}
            onClick={() =>
              run(async () => {
                const r = await api<Preferences>("/preferences", {
                  method: "PUT",
                  body: JSON.stringify(draft),
                });
                setPrefs(r);
              }, "Display preferences saved.")
            }
          >
            Save preferences
          </Button>
        </section>
        <div className="full-span" hidden={section !== "telemetry"}>
          <GatewayPanel isAdmin={user.role === "admin"} />
        </div>
        <div className="full-span" hidden={section !== "recovery"}>
          <RecoveryPanel isAdmin={user.role === "admin"} />
        </div>
        <div className="full-span" hidden={section !== "sites"}>
          <SiteDirectory userId={user.id} canEdit={user.role === "admin"} />
        </div>
        <section
          className="panel settings-card full-span password-settings"
          hidden={section !== "account"}
        >
          <div>
            <span className="password-settings-icon">
              <LockKeyhole size={22} />
            </span>
            <h2>Change your password</h2>
            <p>Choose a personal password for {user.email}.</p>
            <p id="password-guidance">
              Use 15–128 characters. A long, unique passphrase works well.
              Updating your password signs out all sessions for this account.
            </p>
            <div className="local-note">
              <CircleHelp size={16} />
              <span>
                After changing it, use email sign-in. Your account will leave
                the shared demo role list.
              </span>
            </div>
          </div>
          <form
            onSubmit={changePassword}
            aria-label="Change password"
            aria-describedby="password-guidance"
          >
            <label>
              Current password
              <input
                type="password"
                autoComplete="current-password"
                required
                maxLength={200}
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                disabled={passwordBusy}
              />
            </label>
            <label>
              New password
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={15}
                maxLength={128}
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                disabled={passwordBusy}
              />
            </label>
            <label>
              Confirm new password
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={15}
                maxLength={128}
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                disabled={passwordBusy}
              />
            </label>
            {passwordError && (
              <p className="form-error" role="alert">
                {passwordError}
              </p>
            )}
            <Button
              type="submit"
              className="primary"
              icon={LockKeyhole}
              disabled={passwordBusy}
            >
              {passwordBusy ? "Updating password…" : "Update password"}
            </Button>
          </form>
        </section>
        <section
          className="panel settings-card full-span"
          hidden={section !== "system"}
        >
          <div className="panel-header no-padding">
            <div>
              <h2>Local system status</h2>
              <p>Measured runtime state and explicit integration boundaries.</p>
            </div>
            <Badge value="healthy">API connected</Badge>
          </div>
          <div className="service-grid">
            {operations.services.map((s) => (
              <div key={s.name}>
                <span className={`service-icon ${s.status}`}>
                  <Database size={19} />
                </span>
                <h4>{s.name}</h4>
                <p>{s.detail}</p>
                <Badge
                  value={s.status === "operational" ? "healthy" : "simulation"}
                >
                  {s.status}
                </Badge>
              </div>
            ))}
          </div>
          <div className="runtime-metrics">
            <span>
              <strong>{operations.snapshots.toLocaleString()}</strong> stored
              snapshots
            </span>
            <span>
              <strong>{operations.api_p95_ms.toFixed(1)} ms</strong> recent API
              p95
            </span>
            <span>
              <strong>{operations.requests_measured}</strong> requests sampled
            </span>
          </div>
        </section>
        <section
          className="panel settings-card full-span"
          hidden={section !== "system"}
        >
          <h2>Implementation boundaries</h2>
          <p>
            This runnable reference application is the starting point for an
            enterprise pilot.
          </p>
          <div className="boundary-grid">
            {operations.limitations.map((l) => (
              <div key={l}>
                <TriangleAlert size={16} />
                {l}
              </div>
            ))}
          </div>
          <a
            className="text-link"
            href="/docs"
            target="_blank"
            rel="noreferrer"
          >
            Open live backend API documentation <ExternalLink size={14} />
          </a>
        </section>
      </div>
    </div>
  );
}
