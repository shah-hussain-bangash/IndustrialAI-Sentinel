import test from "node:test";
import assert from "node:assert/strict";
import { investigationIdFromHash } from "../src/lib/investigationRoute.ts";

test("investigation links preserve an explicit record identity", () => {
  const id = "038c5d49-3bdf-4bd1-9469-20319d8336f7";
  assert.equal(investigationIdFromHash(`#intelligence/${id}`), id);
});

test("unrelated routes, malformed identifiers and extra path or query content do not open a record", () => {
  for (const hash of ["#intelligence", "#settings", "#account-link=private", "#intelligence/../../settings", "#intelligence/not-a-record", "#intelligence/038c5d49-3bdf-4bd1-9469-20319d8336f7/extra", "#intelligence/038c5d49-3bdf-4bd1-9469-20319d8336f7?site=other"])
    assert.equal(investigationIdFromHash(hash), null);
});
