import test from "node:test";
import assert from "node:assert/strict";
import { investigationStatusLabel } from "../src/lib/investigationStatus.ts";

test("approval summaries distinguish current approval from expiry or invalidation", () => {
  assert.equal(investigationStatusLabel("approved", true), "Approved · current");
  assert.equal(investigationStatusLabel("approved", false), "Approval needs review");
  assert.equal(investigationStatusLabel("approved"), "Approval needs review");
});

test("workflow summaries distinguish planning from dispatch and return-for-revision from resolution", () => {
  assert.equal(investigationStatusLabel("dispatched"), "Work order planned");
  assert.equal(investigationStatusLabel("rejected"), "Returned for revision");
  assert.equal(investigationStatusLabel("awaiting_review"), "Awaiting review");
  assert.equal(investigationStatusLabel("unavailable"), "Link unavailable");
  assert.equal(investigationStatusLabel("unexpected"), "Status unavailable");
});
