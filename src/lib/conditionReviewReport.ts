import { investigationStatusLabel } from "./investigationStatus.ts";

type ReviewEntry = { state: string; version: number; actor_name: string | null; reason: string | null; created: number | null };
type OwnerEntry = { version: number; owner_name: string | null; actor_name: string | null; reason: string | null; created: number | null };
type History<T> = { current: T; history_newest_first: T[]; total_records: number; included_records: number; truncated: boolean };
export type ConditionReviewRecord = {
  format: string; format_version: number; generated_at: number; boundary: string;
  evidence: { match_id: string; asset: { tag: string; name: string; site: string };
    rule: { id: string; version: number; name: string; actor_name: string; created: number; reason: string;
      settings: { channel: string; threshold: number; hysteresis: number; persistence_seconds: number; maximum_gap_seconds: number } };
    match: { signal_state: string; started_at: number; triggered_at: number; ended_at: number | null };
    snapshot: { id: string; timestamp: number; quality: string; signals: { channel: string; unit: string; value: number | null }[] }; boundary: string };
  review: History<ReviewEntry>;
  ownership: History<OwnerEntry> & { owner_currently_eligible: boolean };
  linked_investigation: { id?: string; title?: string; state: string; version?: number; approval_current?: boolean; approved_until?: number | null } | null;
  scope: { excluded: string[] };
};

// Text is escaped even for known backend fields: notes and names are user content.
export const reportText = (value: unknown): string => String(value ?? "—").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!);
const time = (value: number | null): string => {
  if (value === null || !Number.isFinite(value) || !Number.isFinite(new Date(value * 1000).getTime())) return "Unavailable";
  return new Date(value * 1000).toLocaleString("en-GB", { timeZone: "Asia/Dubai" }) + " GST (UTC+4)";
};
const human = (value: string) => value.replaceAll("_", " ");

export function validateReviewRecord(report: ConditionReviewRecord, matchId: string): void {
  if (report?.format !== "sentinel.condition-review" || report.format_version !== 1 || report.evidence?.match_id !== matchId)
    throw new Error("The downloaded record did not match this page. Reload before retrying.");
  for (const section of [report.review, report.ownership]) {
    if (!section || !section.current || !Array.isArray(section.history_newest_first) || section.history_newest_first.length > 100 ||
        !Number.isInteger(section.total_records) || !Number.isInteger(section.included_records) ||
        section.included_records !== section.history_newest_first.length || section.total_records < section.included_records ||
        section.truncated !== (section.total_records > section.included_records)) throw new Error("The record's history information is incomplete. Reload before retrying.");
  }
  if (!report.evidence.asset || !report.evidence.rule?.settings || !report.evidence.match ||
      !Array.isArray(report.evidence.snapshot?.signals) || !Array.isArray(report.scope?.excluded))
    throw new Error("The review evidence is incomplete. Reload before retrying.");
}

export function printableReviewReport(report: ConditionReviewRecord, matchId: string): string {
  validateReviewRecord(report, matchId);
  const e = report.evidence, config = e.rule.settings;
  const table = (headings: string[], rows: unknown[][]) => `<table><thead><tr>${headings.map(value => `<th scope="col">${reportText(value)}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(value => `<td>${reportText(value)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  const facts = (rows: unknown[][]) => table(["Field", "Recorded value"], rows);
  const historyNotice = (section: History<ReviewEntry> | History<OwnerEntry>) => `<p class="${section.truncated ? "warning" : "note"}">${section.truncated ? "Older history omitted. " : ""}${section.included_records} of ${section.total_records} records included, newest first. Maximum 100 per section.</p>`;
  const linked = report.linked_investigation;
  const investigation = linked === null ? "<p>No linked investigation.</p>" : facts([
    ["Status", investigationStatusLabel(linked.state, linked.approval_current)],
    ...(linked.state === "unavailable" ? [] : [["Title", linked.title], ["Investigation ID", linked.id], ["Version", linked.version],
      ...(linked.state === "approved" ? [["Approval until", time(linked.approved_until ?? null)]] : [])]),
  ]);
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>${reportText(e.asset.tag)} · Condition review record</title>
<style>
*{box-sizing:border-box}body{font:15px/1.55 system-ui,Arial,sans-serif;color:#16283f;background:#edf1f5;margin:0;padding:32px}main{max-width:1020px;margin:auto;padding:40px;background:white;border:1px solid #d4dce6;border-radius:12px}header{border-bottom:4px solid #cfaa30;padding-bottom:20px}h1{font-size:30px;margin:8px 0}h2{font-size:21px;margin:32px 0 12px}h3{font-size:17px}.eyebrow{letter-spacing:.12em;font-size:12px;color:#715812}p{margin:10px 0}.note,.warning{padding:12px 16px;background:#f1f5fb;border:1px solid #d4dfed;border-radius:6px}.warning{background:#fff7df;border-color:#dac074;font-weight:600}table{width:100%;border-collapse:collapse;margin:14px 0;font-size:13px}th,td{text-align:left;vertical-align:top;border:1px solid #d4dce6;padding:10px;overflow-wrap:anywhere;white-space:pre-wrap}th{background:#eef3f9}section{margin-top:20px}footer{margin-top:32px;border-top:1px solid #d4dce6;font-size:12px;padding-top:16px;color:#48586b}li{overflow-wrap:anywhere}.instructions{font-size:13px;color:#48586b}@page{size:A4;margin:14mm}@media print{body{background:white;padding:0;font-size:10pt}main{padding:0;border:0;border-radius:0;max-width:none}h1{font-size:21pt}h2{font-size:15pt;break-after:avoid}thead{display:table-header-group}tr{break-inside:avoid}th{background:#eef3f9!important;print-color-adjust:exact}.instructions{display:none}table{font-size:9pt}footer{font-size:9pt}}
</style></head><body><main>
<header><p class="eyebrow">INDUSTRIALAI SENTINEL · LOCAL REVIEW RECORD</p><h1>${reportText(e.asset.tag)} · Condition review</h1>
<p>${reportText(e.asset.name)} · ${reportText(e.asset.site)}</p><p>Generated: ${reportText(time(report.generated_at))}</p></header>
<p class="instructions">Open this file in a browser. Use Print (Ctrl+P on Windows) to print or choose Save as PDF. No internet connection is needed to read this file.</p>
<p class="warning">Downloaded readout only. A review or paused signal does not confirm a physical fault, repair or maintenance completion.</p>
<section><h2>Record identity and current review</h2>${facts([["Match ID", e.match_id], ["Signal state", human(e.match.signal_state)], ["Review state", human(report.review.current.state)], ["Review version", report.review.current.version], ["Owner", report.ownership.current.owner_name ?? "Unassigned"], ["Owner currently eligible", report.ownership.owner_currently_eligible ? "Yes" : "No / unassigned"]])}</section>
<section><h2>Matched rule revision</h2>${facts([["Rule", e.rule.name], ["Rule ID", e.rule.id], ["Matched revision", e.rule.version], ["Signal", config.channel], ["Trigger above", config.threshold], ["Clear margin", config.hysteresis], ["Time above limit (seconds)", config.persistence_seconds], ["Maximum gap (seconds)", config.maximum_gap_seconds], ["Saved by", e.rule.actor_name], ["Saved at", time(e.rule.created)], ["Revision reason", e.rule.reason]])}<p>Threshold and margin use the trigger signal's units shown below.</p></section>
<section><h2>Historical trigger evidence</h2><p class="note">${reportText(e.boundary)}</p>${facts([["Above-limit sequence started", time(e.match.started_at)], ["Triggered", time(e.match.triggered_at)], ["Ended", e.match.ended_at === null ? "Not ended at export" : time(e.match.ended_at)], ["Reading ID", e.snapshot.id], ["Reading time", time(e.snapshot.timestamp)], ["Quality", e.snapshot.quality]])}
${table(["Signal", "Recorded value", "Units", "Role"], e.snapshot.signals.map(signal => [signal.channel, signal.value ?? "Unavailable", signal.unit, signal.channel === config.channel ? "Trigger signal" : "Context only"]))}</section>
<section><h2>Review history</h2>${historyNotice(report.review)}${report.review.history_newest_first.length ? table(["Version", "State", "Reviewer", "Recorded at", "Note"], report.review.history_newest_first.map(row => [row.version, human(row.state), row.actor_name, time(row.created), row.reason])) : "<p>No review decisions recorded.</p>"}</section>
<section><h2>Ownership history</h2>${historyNotice(report.ownership)}${report.ownership.history_newest_first.length ? table(["Version", "Owner", "Changed by", "Recorded at", "Reason"], report.ownership.history_newest_first.map(row => [row.version, row.owner_name ?? "Unassigned", row.actor_name, time(row.created), row.reason])) : "<p>No ownership changes recorded.</p>"}</section>
<section><h2>Linked investigation summary</h2>${investigation}<p>Full recommendation contents, approval decisions and work-order execution are outside this report.</p></section>
<section><h2>Scope and limits</h2><p>${reportText(report.boundary)}</p><h3>Excluded</h3><ul>${report.scope.excluded.map(value => `<li>${reportText(value)}</li>`).join("")}</ul></section>
<footer>Format: ${reportText(report.format)} · Version ${reportText(report.format_version)}. This file contains local review notes and names. Protect it separately; portal access changes cannot revoke downloaded copies. No scripts, remote assets or tracking are included.</footer>
</main></body></html>`;
}
