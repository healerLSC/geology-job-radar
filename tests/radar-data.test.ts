import assert from "node:assert/strict";
import test from "node:test";

import { radar } from "../app/jobs.ts";


test("radar exposes independent monitoring metadata", () => {
  assert.match(radar.lastCheckedAt, /^\d{4}-\d{2}-\d{2}T/);
  assert.ok(radar.coverage.totalUnits >= 300);
  assert.equal(
    radar.coverage.totalUnits,
    radar.coverage.direct + radar.coverage.inherited + radar.coverage.restricted,
  );
});


test("every job preserves matching evidence", () => {
  assert.ok(radar.jobs.every((job) => job.evidence && job.ruleId));
  assert.ok(radar.jobs.every((job) => Array.isArray(job.mirrorUrls)));
});
