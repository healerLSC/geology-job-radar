import assert from "node:assert/strict";
import test from "node:test";

import { filterJobs, getDeadlineState } from "../app/job-filters.ts";
import { jobs } from "../app/jobs.ts";

test("组合筛选仅返回完全匹配的重点冲岗位", () => {
  const result = filterJobs(jobs, {
    query: "地质",
    priority: "重点冲",
    match: "完全匹配",
    sector: "全部",
  });

  assert.ok(result.length >= 1);
  assert.ok(result.every((job) => job.priority === "重点冲"));
  assert.ok(result.every((job) => job.match === "完全匹配"));
});

test("搜索会覆盖单位、集团、岗位、专业和地点", () => {
  assert.equal(filterJobs(jobs, { query: "中国铁建" }).length, 1);
  assert.equal(filterJobs(jobs, { query: "工程地质" }).length, 1);
  assert.equal(filterJobs(jobs, { query: "西二环" }).length, 1);
});

test("截止状态根据明确日期计算并保留未注明状态", () => {
  assert.equal(getDeadlineState(null, new Date("2026-07-14T00:00:00+08:00")), "未注明");
  assert.equal(getDeadlineState("2026-07-20T12:00:00+08:00", new Date("2026-07-14T00:00:00+08:00")), "临近截止");
  assert.equal(getDeadlineState("2026-07-13T23:59:00+08:00", new Date("2026-07-14T00:00:00+08:00")), "已截止");
});
