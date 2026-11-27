import { useEffect, useState } from "react";
import { api } from "../api";
export function MaintenanceStatusBanner({ assetId, refreshKey }: { assetId: string; refreshKey: number }) {
  const [status, setStatus] = useState<{server_time: number; items: {id: string; name: string; state: string}[]; scope: string} | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true; setStatus(null); setError("");
    api<NonNullable<typeof status>>("/maintenance-windows/status?asset_id=" + encodeURIComponent(assetId))
      .then(answer => { if (current) setStatus(answer); }).catch(() => { if (current) setError("Maintenance-window status is unavailable. Refresh before relying on trigger availability."); });
    return () => { current = false; };
  }, [assetId, refreshKey]);
  if (error) return <p className="form-error" role="alert">{error}</p>;
  if (!status) return <p role="status">Checking maintenance-window status…</p>;
  return <div className="local-note" style={{ display: "block" }}><strong>{status.items.some(row => row.state === "suppressing") ? "Maintenance window: new saved-rule matches suppressed" : "No currently suppressing maintenance window"}</strong>
    {status.items.map(row => <p key={row.id}>{row.name} · {row.state}</p>)}
    <p>Checked {new Date(status.server_time * 1000).toLocaleString("en-GB", {timeZone: "Asia/Dubai"})} GST. Refresh data for current status.</p>
    {!!status.items.length && <p>{status.scope}</p>}
  </div>;
}
