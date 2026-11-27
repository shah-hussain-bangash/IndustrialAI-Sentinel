import test from "node:test";
import assert from "node:assert/strict";
import { printableReviewReport, type ConditionReviewRecord } from "../src/lib/conditionReviewReport.ts";

const mid = "038c5d49-3bdf-4bd1-9469-20319d8336f7";
function fixture(): ConditionReviewRecord {
  return { format: "sentinel.condition-review", format_version: 1, generated_at: 0, boundary: "Local readout; not a signed certificate or system backup.",
    evidence: { match_id: mid, asset: { tag: "TEST-101", name: "Fixture pump", site: "Fixture site" },
      rule: { id: "rule-fixture", name: "Saved vibration rule", version: 2, actor_name: "Fixture reviewer", created: 0, reason: "Synthetic fixture",
        settings: { channel: "vibration", threshold: 4.5, hysteresis: .2, persistence_seconds: 60, maximum_gap_seconds: 300 } },
      match: { signal_state: "paused", started_at: 0, triggered_at: 60, ended_at: 120 },
      snapshot: { id: "reading-fixture", timestamp: 60, quality: "good", signals: [{ channel: "vibration", value: 0, unit: "mm/s" }, { channel: "temperature", value: null, unit: "°C" }] },
      boundary: "Historical trigger only; persistence sequence is outside this snapshot." },
    review: { current: { state: "resolved", version: 1, actor_name: "Reviewer", reason: "Synthetic assessment", created: 120 }, history_newest_first: [], total_records: 0, included_records: 0, truncated: false },
    ownership: { current: { version: 0, owner_name: null, actor_name: null, reason: null, created: null }, history_newest_first: [], total_records: 0, included_records: 0, truncated: false, owner_currently_eligible: false },
    linked_investigation: null, scope: { excluded: ["Physical maintenance evidence", "Credentials"] } };
}
test("printable report preserves identity, units, zero/null distinctions and GST without mutating the source", () => {
  const record = fixture(), before = JSON.stringify(record), html = printableReviewReport(record, mid);
  for (const text of [mid, "TEST-101", "Matched revision", "reading-fixture", "mm/s", "Unavailable", "04:00:00 GST (UTC+4)", "No linked investigation", "not a signed certificate", "@media print", 'scope="col"']) assert.ok(html.includes(text), text);
  assert.ok(html.includes("<td>vibration</td><td>0</td>"));
  assert.equal(JSON.stringify(record), before);
});
test("printable report treats notes, names, titles and exclusions as text and contains no active or remote content", () => {
  const record = fixture();
  const attack = '</td><script>alert("x")</script><img src="https://untrusted.invalid/track">';
  record.evidence.rule.reason = attack; record.evidence.asset.name = attack;
  record.scope.excluded.push(attack);
  const html = printableReviewReport(record, mid);
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(!/<script\b|<img\b|<iframe\b|<link\b|<form\b|\son\w+=/i.test(html));
  assert.ok(html.includes("default-src 'none'"));
  assert.ok(!/\b(?:src|href)=["']/i.test(html));
});
test("omitted history and expired approvals remain explicit; unavailable investigation identity stays hidden", () => {
  const record = fixture();
  record.review.history_newest_first = [{ ...record.review.current, reason: "A reviewed note" }];
  record.review.included_records = 1; record.review.total_records = 3; record.review.truncated = true;
  record.linked_investigation = { state: "approved", title: "Test recommendation", approval_current: false };
  let html = printableReviewReport(record, mid);
  assert.ok(html.includes("Older history omitted. 1 of 3 records included, newest first."));
  assert.ok(html.includes("Approval needs review"));
  record.linked_investigation = { state: "unavailable", title: "HIDDEN LINK TITLE", id: "HIDDEN-ID" };
  html = printableReviewReport(record, mid);
  assert.ok(html.includes("Link unavailable")); assert.ok(!html.includes("HIDDEN"));
});
test("mismatched records and incomplete or misleading history metadata cannot produce a report", () => {
  assert.throws(() => printableReviewReport(fixture(), "another-match"), /did not match/);
  const incomplete = fixture(); incomplete.review.total_records = 1;
  assert.throws(() => printableReviewReport(incomplete, mid), /history information is incomplete/);
  const malformed = fixture(); malformed.evidence.snapshot.signals = undefined as never;
  assert.throws(() => printableReviewReport(malformed, mid), /evidence is incomplete/);
});
