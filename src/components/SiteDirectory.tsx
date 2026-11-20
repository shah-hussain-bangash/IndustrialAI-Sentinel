import { useEffect, useState, type FormEvent } from "react";
import {
  Building2,
  Check,
  MapPin,
  RefreshCw,
  Settings2,
  ShieldCheck,
} from "lucide-react";
import { api } from "../api";
import { Badge, Button, Empty, Modal, Spinner } from "./ui";

interface Site {
  id: string;
  name: string;
  display_name: string;
  timezone: string;
  version: number;
  assets: number;
  sensors: number;
  documents: number;
}
export function SiteDirectory({
  userId,
  canEdit,
}: {
  userId: string;
  canEdit: boolean;
}) {
  const [directory, setDirectory] = useState<{
      items: Site[];
      database: string;
    } | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [reload, setReload] = useState(0),
    [editing, setEditing] = useState<Site | null>(null),
    [display, setDisplay] = useState(""),
    [busy, setBusy] = useState(false),
    [formError, setFormError] = useState(""),
    [message, setMessage] = useState("");
  useEffect(() => {
    let stop = false;
    setLoading(true);
    setError("");
    api<{ items: Site[]; database: string }>("/sites")
      .then((r) => {
        if (!stop) setDirectory(r);
      })
      .catch((e) => {
        if (!stop) setError(e.message);
      })
      .finally(() => {
        if (!stop) setLoading(false);
      });
    return () => {
      stop = true;
    };
  }, [userId, reload]);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!editing || busy) return;
    setBusy(true);
    setFormError("");
    try {
      await api<Site>("/sites/" + editing.id, {
        method: "PATCH",
        body: JSON.stringify({
          expected_version: editing.version,
          display_name: display,
        }),
      });
      setEditing(null);
      setMessage(
        "Site display updated. Identity and permissions are unchanged.",
      );
      setReload((x) => x + 1);
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel settings-card full-span site-directory">
      <div className="panel-header no-padding">
        <div>
          <h2>
            <Building2 size={18} /> Site directory
          </h2>
          <p>
            Permanent site identities connect equipment, documents and audit
            records.
          </p>
        </div>
        <Button icon={RefreshCw} onClick={() => setReload((x) => x + 1)}>
          Refresh sites
        </Button>
      </div>
      {message && (
        <div className="local-note" role="status">
          <Check size={16} />
          {message}
        </div>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <Spinner />
      ) : !directory?.items.length ? (
        <Empty
          title="No assigned sites"
          description="Your account has no canonical site memberships."
        />
      ) : (
        <div className="site-identity-grid">
          {directory.items.map((site) => (
            <article className="site-identity-card" key={site.id}>
              <div className="site-identity-heading">
                <span className="role-card-icon">
                  <MapPin size={19} />
                </span>
                <div>
                  <h3>{site.display_name}</h3>
                  <small>
                    {site.timezone} · metadata v{site.version}
                  </small>
                </div>
              </div>
              <div className="site-permanent-id">
                <small>PERMANENT SITE ID</small>
                <code>{site.id}</code>
              </div>
              <p className="site-canonical-name">
                Compatible site name: <strong>{site.name}</strong>
              </p>
              <div className="site-counts">
                <span>
                  <b>{site.assets}</b> assets
                </span>
                <span>
                  <b>{site.sensors}</b> sensors
                </span>
                <span>
                  <b>{site.documents}</b> documents
                </span>
              </div>
              <Button
                icon={Settings2}
                disabled={!canEdit}
                onClick={() => {
                  setEditing(site);
                  setDisplay(site.display_name);
                  setFormError("");
                  setMessage("");
                }}
                aria-label={`Edit display for ${site.name}`}
              >
                Edit display name
              </Button>
            </article>
          ))}
        </div>
      )}
      <div className="site-directory-note">
        <ShieldCheck size={17} />
        <p>
          Access follows your canonical site memberships. Display-name changes
          preserve IDs, equipment links and permissions. Runtime database:{" "}
          <Badge value="neutral">{directory?.database || "Checking"}</Badge>
        </p>
      </div>
      {editing && (
        <Modal
          title="Update site display"
          description={editing.name}
          onClose={() => {
            if (!busy) setEditing(null);
          }}
        >
          <div className="sensor-identity">
            <small>PERMANENT SITE ID</small>
            <code>{editing.id}</code>
          </div>
          <form onSubmit={save}>
            <label>
              Display name
              <input
                required
                minLength={1}
                maxLength={100}
                value={display}
                disabled={busy}
                onChange={(e) => setDisplay(e.target.value)}
              />
            </label>
            <p className="lab-footnote">
              This updates the directory label only. The canonical name, site
              ID, memberships and linked records remain unchanged.
            </p>
            {formError && (
              <p className="form-error" role="alert">
                {formError}
              </p>
            )}
            <div className="modal-actions">
              <Button disabled={busy} onClick={() => setEditing(null)}>
                Cancel
              </Button>
              <Button
                className="primary"
                type="submit"
                icon={Check}
                disabled={busy}
              >
                {busy ? "Saving…" : "Save display name"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
