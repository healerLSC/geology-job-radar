import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const developmentPreviewMeta =
  /<meta(?=[^>]*\bname=["']codex-preview["'])(?=[^>]*\bcontent=["']development["'])[^>]*>/i;

test("renders development preview metadata", () => {
  const html = fs.readFileSync("out/index.html", "utf8");
  assert.match(html, developmentPreviewMeta);
});

test("renders the geology job radar content and verification language", () => {
  const html = fs.readFileSync("out/index.html", "utf8");
  assert.match(html, /<html lang="zh-CN">/);
  assert.match(html, /<title>地质招聘雷达｜2027届央国企招聘监控<\/title>/);
  assert.match(html, /地质招聘雷达/);
  assert.match(html, /广岩国际投资有限责任公司/);
  assert.match(html, /专业匹配依据/);
  assert.match(html, /独立自动监控/);
  assert.match(html, /349/);
  assert.match(html, /来源健康/);
  assert.match(html, /备用来源正常/);
  assert.match(html, /工程类限定/);
  assert.match(html, /扩展发现/);
  assert.match(html, /历史岗位/);
  assert.match(html, /最终以官方公告为准/);
});
