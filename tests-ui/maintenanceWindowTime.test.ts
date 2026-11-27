import test from "node:test";
import assert from "node:assert/strict";
import { gstWindowInput, gstWindowTime, validWindowRange } from "../src/lib/maintenanceWindowTime.ts";
test("maintenance times use explicit GST independently of the browser timezone", () => {
  assert.equal(gstWindowTime("2026-11-27T12:00"), Date.parse("2026-11-27T08:00:00Z") / 1000);
  assert.equal(gstWindowInput(gstWindowTime("2026-11-27T12:00:45")!), "2026-11-27T12:00:45");
});
test("invalid calendar dates, missing values and out-of-range intervals cannot be submitted", () => {
  for (const value of ["", "2026-02-30T12:00", "2026-11-27T25:00", "2026-11-27", "1960-01-01T12:00", "2026-11-27T12:00Z"]) assert.equal(gstWindowTime(value), null, value);
  assert.equal(validWindowRange(null, 2), false); assert.equal(validWindowRange(100, 100), false);
  assert.equal(validWindowRange(100, 604900), true); assert.equal(validWindowRange(100, 604901), false);
});
