import { useEffect, useRef, useState } from "react";
import { Database, ShieldCheck } from "lucide-react";
import { api, date } from "../api";
import { Button, Spinner } from "./ui";

interface Report {
  job_id: string;
  status: string;
  started: number;
  duration_seconds: number;
  reason?: string;
  bytes?: number;
  integrity?: string;
  foreign_keys?: string;
  checksum_match?: boolean;
  schema_match?: boolean;
  table_content_match?: boolean;
  table_counts?: Record<string, number>;
  revisions?: string[];
  original_files_verified?: number;
  documents_without_original?: number;
}
interface Recovery {
  supported: boolean;
  items: Report[];
  scope: string;
  storage: string;
  limits: string;
}
export function RecoveryPanel({ isAdmin }: { isAdmin: boolean }) {
  const [data, setData] = useState<Recovery | null>(null),
    [loading, setLoading] = useState(isAdmin),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [reload, setReload] = useState(0),
    [result, setResult] = useState<Report | null>(null);
  const attempt = useRef<string | null>(null);
  useEffect(() => {
    if (!isAdmin) return;
    let stop = false;
    setLoading(true);
    api<Recovery>("/recovery")
      .then((r) => {
        if (!stop) setData(r);
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
  async function verify() {
    if (busy) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      attempt.current ||= crypto.randomUUID();
      const r = await api<Report>("/recovery/verify", {
        method: "POST",
        headers: { "Idempotency-Key": attempt.current },
        body: JSON.stringify({}),
      });
      setResult(r);
      attempt.current = null;
      setReload((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel recovery-panel">
      <div className="panel-header">
        <div>
          <h2>
            <ShieldCheck size={18} /> Backup & recovery verification
          </h2>
          <p>Check a database backup by restoring it into a separate folder.</p>
        </div>
        {isAdmin && (
          <Button
            disabled={busy || loading}
            onClick={() => {
              setError("");
              attempt.current = null;
              setReload((n) => n + 1);
            }}
          >
            Refresh checks
          </Button>
        )}
      </div>
      <p className="local-note">
        The live database is never replaced. This checks stored records and
        extracted document text and retained original files. Earlier documents
        can lack originals. Configuration, external systems and application
        startup are outside this drill.
      </p>
      {!isAdmin ? (
        <p className="lab-footnote">
          Sign in as an administrator with access to every site to run this
          database-wide check.
        </p>
      ) : (
        <>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {loading && !data ? (
            <Spinner />
          ) : (
            data && (
              <>
                <div className="recovery-action">
                  <div>
                    <strong>Local SQLite recovery drill</strong>
                    <p>
                      {data.supported
                        ? "Creates a consistent snapshot, verifies its checksum, and compares schema and every table after an isolated restoration."
                        : "This runtime uses another database engine. A separate recovery procedure is required."}
                    </p>
                    <small>
                      Backup files remain on this computer under
                      data/recovery/runs. They contain database authentication
                      and session records; no download endpoint is provided.
                    </small>
                  </div>
                  <Button
                    className="primary"
                    icon={Database}
                    disabled={busy || !data.supported}
                    onClick={verify}
                  >
                    {busy ? "Checking recovery…" : "Run recovery check"}
                  </Button>
                </div>
                <p className="lab-footnote">{data.limits}</p>
              </>
            )
          )}
          {result && (
            <div
              className={`recovery-result ${result.status === "passed" ? "passed" : "failed"}`}
              role="status"
            >
              <strong>
                {result.status === "passed"
                  ? "Recovery verification passed"
                  : "Recovery verification failed"}
              </strong>
              <p>
                {result.status === "passed"
                  ? "Backup and isolated restored data match. The live database was not restored."
                  : result.reason}
              </p>
              <code>{result.job_id}</code>
            </div>
          )}
          <h3>Recent checks · latest 20</h3>
          {!data?.items.length && !loading ? (
            <p className="lab-footnote">No completed checks yet.</p>
          ) : (
            data?.items.map((r) => (
              <details className="recovery-record" key={r.job_id}>
                <summary>
                  <span className={`recovery-status ${r.status}`}>
                    {r.status === "passed" ? "Passed" : "Failed"}
                  </span>{" "}
                  {date(r.started, true)} GST · {r.duration_seconds}s
                </summary>
                <code>{r.job_id}</code>
                {r.status === "passed" ? (
                  <>
                    <div className="recovery-proof">
                      <span>Integrity: {r.integrity}</span>
                      <span>Foreign keys: {r.foreign_keys}</span>
                      <span>
                        Checksum: {r.checksum_match ? "Match" : "Mismatch"}
                      </span>
                      <span>
                        Schema: {r.schema_match ? "Match" : "Mismatch"}
                      </span>
                      <span>
                        Table contents:{" "}
                        {r.table_content_match ? "Match" : "Mismatch"}
                      </span>
                      <span>
                        Backup: {((r.bytes || 0) / 1048576).toFixed(2)} MiB
                      </span>
                    </div>
                    <p className="local-note">
                      {r.original_files_verified !== undefined
                        ? `Original files verified: ${r.original_files_verified}. Documents without an original: ${r.documents_without_original ?? 0}.`
                        : "Earlier database-only report: original-file coverage was not measured."}
                    </p>
                    <p className="lab-footnote">
                      Migration history:{" "}
                      {r.revisions?.join(", ") || "Unversioned schema"}. This
                      duration is a measured local check, not a recovery-time
                      guarantee.
                    </p>
                    <div className="table-scroll">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Restored table</th>
                            <th>Rows verified</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(r.table_counts || {}).map(
                            ([name, count]) => (
                              <tr key={name}>
                                <td>{name}</td>
                                <td>{count}</td>
                              </tr>
                            ),
                          )}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <p className="form-error">{r.reason}</p>
                )}
              </details>
            ))
          )}
        </>
      )}
    </section>
  );
}
