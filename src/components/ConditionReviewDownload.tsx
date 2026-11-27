import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Button } from "./ui";
import { printableReviewReport, validateReviewRecord, type ConditionReviewRecord } from "../lib/conditionReviewReport";

export function ConditionReviewDownload({ matchId, locked }: { matchId: string; locked: boolean }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, [matchId]);
  async function download(printable = false) {
    setBusy(true); setError("");
    try {
      const report = await api<ConditionReviewRecord>(`/condition-rules/matches/${encodeURIComponent(matchId)}/export`);
      if (!mounted.current) return;
      validateReviewRecord(report, matchId);
      const content = printable ? printableReviewReport(report, matchId) : JSON.stringify(report, null, 2);
      const url = URL.createObjectURL(new Blob([content], { type: printable ? "text/html;charset=utf-8" : "application/json" }));
      const link = document.createElement("a");
      link.href = url; link.download = `sentinel-condition-${matchId}.${printable ? "html" : "json"}`;
      document.body.appendChild(link); link.click(); link.remove();
      // Allow the browser to begin the file transfer before releasing its URL.
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { if (mounted.current) setError((e as Error).message); }
    finally { if (mounted.current) setBusy(false); }
  }
  return <section aria-label="Download condition review" className="local-note" style={{ display: "block" }}>
    <div className="attention-actions"><Button disabled={busy || locked} onClick={() => void download(true)}>Download printable report</Button>
      <Button disabled={busy || locked} onClick={() => void download()}>Download review record (JSON)</Button></div>
    {busy && <p role="status">Preparing review record…</p>}
    <p>Open the printable HTML file in a browser, then use Print to print or save as PDF.</p>
    <p>Includes the saved trigger evidence, review and ownership history, and a linked-investigation summary. Each history section includes up to 100 newest entries and states whether older entries were omitted. Keep downloaded notes private.</p>
    {error && <p role="alert" className="form-error">{error}</p>}
  </section>;
}
