import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, date } from "../api";
import { Button, Empty, Spinner } from "./ui";

interface Gateway {
  id: string;
  name: string;
  asset_tag: string;
  asset_id: string;
  site: string;
  version: number;
  status: string;
  expires: number;
  last_used: number | null;
  accepted_batches: number;
  credential_hint: string;
}
interface Directory {
  items: Gateway[];
  assets: { id: string; tag: string; name: string; site: string }[];
  scope: string;
}
interface Issued {
  gateway: Gateway;
  credential?: string | null;
  credential_notice?: string;
}
export function GatewayPanel({ isAdmin }: { isAdmin: boolean }) {
  const [data, setData] = useState<Directory | null>(null),
    [loading, setLoading] = useState(isAdmin),
    [busy, setBusy] = useState(false),
    [reload, setReload] = useState(0);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [name, setName] = useState(""),
    [asset, setAsset] = useState(""),
    [days, setDays] = useState(7),
    [creating, setCreating] = useState(false);
  const [credential, setCredential] = useState(""),
    [reveal, setReveal] = useState(false),
    [issuedName, setIssuedName] = useState("");
  const attempt = useRef<{ key: string; path: string; body: string } | null>(
    null,
  );
  useEffect(() => {
    if (!isAdmin) return;
    let stop = false;
    setLoading(true);
    api<Directory>("/gateways")
      .then((r) => {
        if (!stop) {
          setData(r);
          setAsset((a) => a || r.assets[0]?.id || "");
        }
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
  }, [isAdmin, reload]);
  async function request(path: string, body: unknown) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    setCredential("");
    setReveal(false);
    try {
      const encoded = JSON.stringify(body);
      if (
        !attempt.current ||
        attempt.current.path !== path ||
        attempt.current.body !== encoded
      )
        attempt.current = { path, body: encoded, key: crypto.randomUUID() };
      const r = await api<Issued>(path, {
        method: "POST",
        headers: { "Idempotency-Key": attempt.current.key },
        body: encoded,
      });
      attempt.current = null;
      setCredential(r.credential || "");
      setIssuedName(r.gateway.name);
      setNotice(
        r.credential_notice ||
          "Credential revoked. The sender can no longer authenticate.",
      );
      setCreating(false);
      setReload((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function create(e: FormEvent) {
    e.preventDefault();
    void request("/gateways", { name, asset_id: asset, lifetime_days: days });
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(credential);
      setNotice("Credential copied. It is not stored by this interface.");
    } catch {
      setNotice("Copy unavailable. Use Show credential and copy it manually.");
    }
  }
  return (
    <section className="panel gateway-panel">
      <div className="panel-header">
        <div>
          <h2>Telemetry gateway access</h2>
          <p>
            Issue a sender credential for one asset’s independent sensor events.
          </p>
        </div>
        {isAdmin && (
          <Button
            disabled={busy || loading}
            onClick={() => {
              setError("");
              setReload((n) => n + 1);
            }}
          >
            Refresh gateways
          </Button>
        )}
      </div>
      <p className="local-note">
        HTTP event ingestion only. No physical device, MQTT broker, PLC controls
        or maintenance approvals are connected by this feature. Publication
        still needs a reviewed, aligned frame.
      </p>
      {!isAdmin ? (
        <p className="lab-footnote">
          An Admin with access to the selected asset’s site can create, rotate
          or revoke its sender credential.
        </p>
      ) : (
        <>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {notice && (
            <p className="event-receipt" role="status">
              {notice}
            </p>
          )}
          {!!credential && (
            <div className="gateway-secret">
              <strong>New credential · {issuedName}</strong>
              <p>
                Displayed once. Copy it for the local sender. The server stores
                only a hash.
              </p>
              <label>
                New gateway credential
                <input
                  type={reveal ? "text" : "password"}
                  value={credential}
                  readOnly
                  autoComplete="off"
                  spellCheck={false}
                />
              </label>
              <div className="modal-actions">
                <Button onClick={() => setReveal((v) => !v)}>
                  {reveal ? "Hide value" : "Show credential"}
                </Button>
                <Button onClick={copy}>Copy credential</Button>
                <Button
                  onClick={() => {
                    setCredential("");
                    setReveal(false);
                  }}
                >
                  Clear displayed credential
                </Button>
              </div>
            </div>
          )}
          <div className="gateway-tools">
            <Button
              className="primary"
              disabled={busy || loading || !data?.assets.length}
              onClick={() => {
                setCreating((v) => !v);
                setCredential("");
                setError("");
              }}
            >
              {creating ? "Cancel creation" : "Create gateway"}
            </Button>
            <span className="lab-footnote">
              Latest 100 gateways within your permitted sites.
            </span>
          </div>
          {creating && (
            <form className="event-entry" onSubmit={create}>
              <h3>Create asset-scoped sender</h3>
              <div className="form-grid">
                <label>
                  Gateway name
                  <input
                    required
                    minLength={1}
                    maxLength={100}
                    value={name}
                    disabled={busy}
                    placeholder="Local C-202 sender"
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                <label>
                  Equipment
                  <select
                    value={asset}
                    required
                    disabled={busy}
                    onChange={(e) => setAsset(e.target.value)}
                  >
                    {data?.assets.map((a) => (
                      <option value={a.id} key={a.id}>
                        {a.tag} · {a.name} · {a.site}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Credential lifetime (days)
                  <input
                    required
                    type="number"
                    min={1}
                    max={90}
                    value={days}
                    disabled={busy}
                    onChange={(e) => setDays(Number(e.target.value))}
                  />
                </label>
              </div>
              <p className="lab-footnote">
                Rotations below use this selected lifetime. Revoked gateways
                cannot be reactivated; create a new record if needed.
              </p>
              <Button
                type="submit"
                className="primary"
                disabled={busy || !name.trim() || !asset}
              >
                {busy ? "Issuing…" : "Issue scoped credential"}
              </Button>
            </form>
          )}
          {loading && !data ? (
            <Spinner />
          ) : !data?.items.length ? (
            <Empty
              title="No telemetry gateways yet"
              description="Create a gateway for one asset, then use its credential with the local sample sender."
            />
          ) : (
            <div className="table-scroll">
              <table className="data-table gateway-table">
                <thead>
                  <tr>
                    <th>Sender / scope</th>
                    <th>Status / expiry · GST</th>
                    <th>Accepted batches</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((g) => (
                    <tr key={g.id}>
                      <td>
                        <strong>{g.name}</strong>
                        <small>
                          {g.asset_tag} · {g.site}
                        </small>
                        <code>{g.credential_hint}</code>
                      </td>
                      <td>
                        <strong>{g.status}</strong>
                        <small>
                          {date(g.expires, true)} · v{g.version}
                        </small>
                      </td>
                      <td>
                        <strong>{g.accepted_batches}</strong>
                        <small>
                          {g.last_used
                            ? date(g.last_used, true) + " GST"
                            : "No accepted batches"}
                        </small>
                      </td>
                      <td>
                        <div className="gateway-row-actions">
                          <Button
                            disabled={busy || g.status === "revoked"}
                            onClick={() =>
                              void request(`/gateways/${g.id}/rotate`, {
                                expected_version: g.version,
                                lifetime_days: days,
                              })
                            }
                          >
                            Rotate credential
                          </Button>
                          <Button
                            disabled={busy || g.status === "revoked"}
                            onClick={() =>
                              void request(`/gateways/${g.id}/revoke`, {
                                expected_version: g.version,
                              })
                            }
                          >
                            Revoke
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="lab-footnote">
            Use scripts/send_gateway_sample.py to submit one four-channel test
            batch. The script prompts for the credential without echoing it. A
            source label alone is not proof of an authenticated device; inspect
            the gateway audit history.
          </p>
        </>
      )}
    </section>
  );
}
