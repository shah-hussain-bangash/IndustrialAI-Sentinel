import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, date } from "../api";
import { Button, Empty, Spinner } from "./ui";
import { CheckCircle2, Copy, KeyRound, Radio, ShieldCheck } from "lucide-react";
import { sampleRecords } from "../lib/gatewaySample";

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
  const [sampleBusy, setSampleBusy] = useState(false),
    [sampleDone, setSampleDone] = useState(false);
  const sampleAttempt = useRef<{ key: string; body: string } | null>(null);
  const credentialInput = useRef<HTMLInputElement>(null);
  const locked = busy || sampleBusy;
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
    if (locked) return;
    setBusy(true);
    setError("");
    setNotice("");
    setCredential("");
    setSampleDone(false);
    sampleAttempt.current = null;
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
      setNotice(
        `Copied gateway key (${credential.length} characters). Paste it directly into the sender without copying another command.`,
      );
    } catch {
      setReveal(true);
      credentialInput.current?.focus();
      credentialInput.current?.select();
      setError(
        "Clipboard access was unavailable. The key is selected: press Ctrl+C, then paste directly into the sender. Or use Send test sample below.",
      );
    }
  }
  async function sendSample() {
    if (locked || !credential || sampleDone) return;
    setSampleBusy(true);
    setError("");
    setNotice("");
    async function gatewayRequest<T>(
      path: string,
      body?: string,
      key?: string,
    ): Promise<T> {
      const response = await fetch(`/api${path}`, {
        method: body ? "POST" : "GET",
        credentials: "omit",
        redirect: "error",
        signal: AbortSignal.timeout(20000),
        headers: {
          Authorization: `Bearer ${credential}`,
          ...(body
            ? { "Content-Type": "application/json", "Idempotency-Key": key! }
            : {}),
        },
        body,
      });
      if (!response.ok)
        throw new Error(
          response.status === 401
            ? "This gateway key is expired or no longer active. Rotate its credential and try again."
            : `Gateway rejected this sample (HTTP ${response.status}). Check its scope and refresh before retrying.`,
        );
      return response.json() as Promise<T>;
    }
    try {
      if (!sampleAttempt.current) {
        const identity = await gatewayRequest<{
          sensors: { id: string; channel: string; unit: string }[];
        }>("/gateway-identity");
        const key = crypto.randomUUID();
        sampleAttempt.current = {
          key,
          body: JSON.stringify({
            records: sampleRecords(
              identity.sensors,
              key,
              Date.now() / 1000 - 1,
            ),
          }),
        };
      }
      const result = await gatewayRequest<{
        inserted: number;
        duplicates: number;
      }>(
        "/gateway-events/batches",
        sampleAttempt.current.body,
        sampleAttempt.current.key,
      );
      setSampleDone(true);
      sampleAttempt.current = null;
      setNotice(
        `Gateway sample accepted: ${result.inserted} saved, ${result.duplicates} duplicates. Open Sensor registry to review the four readings and publish while fresh.`,
      );
      setReload((value) => value + 1);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "The sample could not be confirmed. Retry sends the same batch safely.",
      );
    } finally {
      setSampleBusy(false);
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
            disabled={locked || loading}
            onClick={() => {
              setError("");
              setReload((n) => n + 1);
            }}
          >
            Refresh gateways
          </Button>
        )}
      </div>
      <div className="gateway-guide" aria-label="Gateway setup guide">
        <div>
          <KeyRound size={20} />
          <strong>Create access</strong>
          <p>Choose one asset and issue its private sender key.</p>
        </div>
        <div>
          <Radio size={20} />
          <strong>Send a sample</strong>
          <p>
            Test here in your browser, or copy the key to an external sender.
          </p>
        </div>
        <div>
          <ShieldCheck size={20} />
          <strong>Review the readings</strong>
          <p>Open Sensor registry, check alignment and publish after review.</p>
        </div>
      </div>
      <p className="local-note">
        Demonstration telemetry only. No plant equipment is connected. Saving
        events and publishing equipment snapshots remain separate actions.
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
                This private key appears only once. You can test it below
                without copying it. Leave this section only after saving it
                privately if you need an external sender.
              </p>
              <label>
                New gateway credential
                <input
                  ref={credentialInput}
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
                <Button icon={Copy} onClick={copy}>
                  Copy credential
                </Button>
                <Button
                  disabled={locked}
                  onClick={() => {
                    setCredential("");
                    setReveal(false);
                  }}
                >
                  Clear displayed credential
                </Button>
              </div>
              <div className="gateway-browser-test">
                <div>
                  <strong>
                    {sampleDone
                      ? "Sample received"
                      : "Test this gateway in your browser"}
                  </strong>
                  <p>
                    One simulated batch: 2 mm/s · 70 °C · 5 bar · 120 m³/h. Uses
                    this gateway key; no account session is sent with the
                    sample.
                  </p>
                </div>
                <Button
                  className="primary"
                  icon={sampleDone ? CheckCircle2 : Radio}
                  disabled={locked || sampleDone}
                  onClick={sendSample}
                >
                  {sampleBusy
                    ? "Sending…"
                    : sampleDone
                      ? "Four-channel sample sent"
                      : sampleAttempt.current
                        ? "Retry test sample"
                        : "Send test sample"}
                </Button>
                {sampleDone && (
                  <a className="btn" href="#sensors">
                    Open sensor registry
                  </a>
                )}
              </div>
            </div>
          )}
          <div className="gateway-tools">
            <Button
              className="primary"
              disabled={locked || loading || !data?.assets.length}
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
                    disabled={locked}
                    placeholder="Local C-202 sender"
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                <label>
                  Equipment
                  <select
                    value={asset}
                    required
                    disabled={locked}
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
                    disabled={locked}
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
                disabled={locked || !name.trim() || !asset}
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
                        <span className={`gateway-state ${g.status}`}>
                          {g.status}
                        </span>
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
                            disabled={locked || g.status === "revoked"}
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
                            disabled={locked || g.status === "revoked"}
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
