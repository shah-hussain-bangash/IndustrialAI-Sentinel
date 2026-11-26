import test from "node:test";
import assert from "node:assert/strict";
import { conditionMatchHash, conditionMatchIdFromHash } from "../src/lib/conditionMatchRoute.ts";

const id = "038c5d49-3bdf-4bd1-9469-20319d8336f7";
test("condition links retain one exact match across bookmarking and uppercase input", () => {
  assert.equal(conditionMatchIdFromHash(conditionMatchHash(id)), id);
  assert.equal(conditionMatchIdFromHash(`#conditions/${id.toUpperCase()}`), id);
  assert.equal(conditionMatchHash(id.toUpperCase()), `#conditions/${id}`);
});
test("malformed condition links and unrelated routes never select a match", () => {
  for (const hash of ["#conditions", "#conditions/", `#intelligence/${id}`, `#conditions/${id}/extra`, `#conditions/${id}?site=other`, `#conditions/${id}%2fextra`, "#conditions/undefined", "#conditions/<script>"]) {
    assert.equal(conditionMatchIdFromHash(hash), null, hash);
  }
  assert.equal(conditionMatchHash("../other"), "#conditions");
});
