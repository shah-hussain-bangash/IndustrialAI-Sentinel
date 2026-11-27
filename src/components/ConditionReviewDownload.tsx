import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Button } from "./ui";

export function ConditionReviewDownload({ matchId, locked }: { matchId: string; locked: boolean }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, [matchId]);
  async function download() {
    setBusy(true); setError("");
    try {
      const report = await api<{ format: string; format_version: number; evidence: { match_id: string } }>(`/condition-rules/matches/${encodeURIComponent(matchId)}/export`);
      if (!mounted.current) return;
      if (report.format !== "sentinel.condition-review" || report.format_version !== 1 || report.evidence.match_id !== matchId) throw new Error("The downloaded record did not match this page. Reload before retrying.");
      const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url; link.download = `sentinel-condition-${matchId}.json`;
      document.body.appendChild(link); link.click(); link.remove();
      // Allow the browser to begin the file transfer before releasing its URL.
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { if (mounted.current) setError((e as Error).message); }
    finally { if (mounted.current) setBusy(false); }
  }
  return <section aria-label="Download condition review" className="local-note" style={{ display: "block" }}>
    <Button disabled={busy || locked} onClick={() => void download()}>{busy ? "Preparing review record…" : "Download review record (JSON)"}</Button>
    <p>Includes the saved trigger evidence, review and ownership history, and a linked-investigation summary. Each history section includes up to 100 newest entries and states whether older entries were omitted. Keep downloaded notes private.</p>
    {error && <p role="alert" className="form-error">{error}</p>}
  </section>;
}
