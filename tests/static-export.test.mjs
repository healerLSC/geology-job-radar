import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("Next build exports a GitHub Pages index", () => {
  assert.ok(fs.existsSync("out/index.html"));
});

test("exported assets use the repository base path", () => {
  const html = fs.readFileSync("out/index.html", "utf8");
  assert.match(html, /\/geology-job-radar\/_next\//);
  assert.match(html, /href="\/geology-job-radar\/favicon\.svg"/);
});

test("repository includes independent monitor and Pages workflows", () => {
  const monitor = fs.readFileSync(".github/workflows/monitor.yml", "utf8");
  const deploy = fs.readFileSync(".github/workflows/deploy.yml", "utf8");

  assert.match(monitor, /schedule:/);
  assert.match(monitor, /python -m monitor\.run/);
  assert.match(deploy, /deploy-pages/);
  assert.match(deploy, /npm run build:pages/);
});
