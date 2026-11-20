import { test } from "node:test";
import assert from "node:assert/strict";
import {
  alignmentWindow,
  duration,
  signalSource,
} from "../src/lib/alignment.ts";
import { sampleRecords } from "../src/lib/gatewaySample.ts";
const channels = ["vibration", "temperature", "pressure", "flow"];
const sensors = channels.map((channel) => ({
  channel,
  stale_after_seconds: 900,
}));
const frame = {
  ready: true,
  rows: channels.map((channel) => ({ channel, event: { observed_at: 1000 } })),
};
test("freshness window closes at the earliest configured channel limit", () => {
  const state = alignmentWindow(
    frame,
    sensors.map((s) => ({
      ...s,
      stale_after_seconds: s.channel === "flow" ? 60 : 900,
    })),
    1030,
  );
  assert.equal(state.expiresAt, 1060);
  assert.equal(state.remaining, 30);
  assert.equal(state.eligible, true);
  assert.equal(alignmentWindow(frame, sensors, 1900).eligible, false);
});
test("missing readings, missing configuration and server rejection cannot be published", () => {
  assert.equal(
    alignmentWindow({ ...frame, ready: false }, sensors, 1010).eligible,
    false,
  );
  assert.equal(
    alignmentWindow(
      {
        ...frame,
        rows: [...frame.rows.slice(0, 3), { channel: "flow", event: null }],
      },
      sensors,
      1010,
    ).eligible,
    false,
  );
  assert.equal(
    alignmentWindow(frame, sensors.slice(0, 3), 1010).eligible,
    false,
  );
  assert.equal(alignmentWindow(null, sensors, 1010).eligible, false);
});
test("timer and source labels remain clear without hiding original IDs", () => {
  assert.equal(duration(65), "1:05");
  assert.equal(duration(-20), "0:00");
  assert.equal(signalSource("gateway:example"), "Gateway sender");
  assert.equal(signalSource("manual-alignment-ui"), "Manual test frame");
});
const canonical = [
  { id: "v", channel: "vibration", unit: "mm/s" },
  { id: "t", channel: "temperature", unit: "degC" },
  { id: "p", channel: "pressure", unit: "bar" },
  { id: "f", channel: "flow", unit: "m3/h" },
];
test("gateway sample uses scoped identities, unique messages and one observed time", () => {
  const records = sampleRecords(canonical, "request-one", 1234);
  assert.equal(records.length, 4);
  assert.equal(new Set(records.map((r) => r.message_id)).size, 4);
  assert.equal(new Set(records.map((r) => r.observed_at)).size, 1);
  assert.deepEqual(
    records.map((r) => r.raw_value),
    [2, 70, 5, 120],
  );
  assert.deepEqual(
    records.map((r) => r.sensor_id),
    ["v", "t", "p", "f"],
  );
  assert.ok(records.every((r) => !("source" in r)));
  assert.deepEqual(sampleRecords(canonical, "request-one", 1234), records);
});
test("sample builder rejects changed units, duplicate channels and bad clocks", () => {
  assert.throws(() => sampleRecords(canonical.slice(0, 3), "x", 1234));
  assert.throws(() =>
    sampleRecords([...canonical.slice(0, 3), canonical[0]], "x", 1234),
  );
  assert.throws(() =>
    sampleRecords(
      canonical.map((r) => ({ ...r, unit: "wrong" })),
      "x",
      1234,
    ),
  );
  assert.throws(() => sampleRecords(canonical, "x", NaN));
});
