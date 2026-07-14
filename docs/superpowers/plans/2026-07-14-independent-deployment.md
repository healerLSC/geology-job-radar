# 地质招聘雷达独立部署 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有招聘看板迁移到公开 GitHub Pages，并用无需付费密钥的 GitHub Actions 每日核查完整单位名册、生成招聘数据和自动发布。

**Architecture:** 保留 React/Next 页面但改为 Next 静态导出；Python 监控程序读取版本化单位与来源 JSON，抓取公开页面、检测变化、执行专业规则并生成 `data/radar.json`。GitHub Actions 分别负责每日监控与 Pages 发布；抓取失败保留最后一次成功数据。

**Tech Stack:** Next.js 16、React 19、TypeScript 5、Python 3.12、requests、Beautiful Soup、pypdf、python-docx、openpyxl、GitHub Actions、GitHub Pages。

## Global Constraints

- GitHub 仓库名固定为 `geology-job-radar`，公开可读。
- 不使用 ChatGPT 任务、付费搜索 API、付费服务器、数据库或私密凭据。
- `monitor/units.json` 必须覆盖原文件中全部集团、子公司、矿区、研究院、技术中心、地勘单位、工程单位与事业单位。
- “地质工程、资源勘查工程、勘查技术与工程、工程地质、物探、采矿工程”不得自动判为地质学完全匹配。
- 搜索线索不是官方公告；只有官方或权威公开平台正文可进入有效岗位，其他结果标为线索。
- 单个来源失败时保留上次数据，构建失败时不得覆盖已发布网站。
- 网站基础路径固定为 `/geology-job-radar/`，本地测试可使用根路径。
- 监控运行时间为中国时间每日 19:00（GitHub cron 为 `0 11 * * *`，实际执行可能受平台排队影响）。

---

### Task 1: Next 静态导出与 GitHub Pages 基础路径

**Files:**
- Modify: `package.json`
- Modify: `next.config.ts`
- Delete: `vite.config.ts`
- Delete: `worker/index.ts`
- Modify: `tests/rendered-html.test.mjs`
- Create: `tests/static-export.test.mjs`

**Interfaces:**
- Consumes: 现有 `app/` React 页面。
- Produces: `npm run build` 生成 `out/index.html`；`SITE_BASE_PATH` 控制项目路径。

- [ ] **Step 1: 写静态导出失败测试**

```js
// tests/static-export.test.mjs
import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("Next build exports a GitHub Pages index", () => {
  assert.ok(fs.existsSync("out/index.html"));
});

test("exported assets use the repository base path", () => {
  const html = fs.readFileSync("out/index.html", "utf8");
  assert.match(html, /\/geology-job-radar\/_next\//);
});
```

- [ ] **Step 2: 运行测试并确认当前构建形态失败**

Run: `SITE_BASE_PATH=/geology-job-radar npm run build && node --test tests/static-export.test.mjs`

Expected: FAIL，当前构建不生成 `out/index.html`。

- [ ] **Step 3: 改为 Next 静态导出**

```ts
// next.config.ts
import type { NextConfig } from "next";

const basePath = process.env.SITE_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: "export",
  basePath,
  assetPrefix: basePath || undefined,
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
```

将 `package.json` 脚本改为：

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint . --ignore-pattern out --ignore-pattern .next",
    "test:unit": "node --import tsx --test tests/job-filters.test.ts tests/rendered-html.test.mjs tests/radar-data.test.ts",
    "test:static": "node --test tests/static-export.test.mjs",
    "test": "npm run test:unit && SITE_BASE_PATH=/geology-job-radar npm run build && npm run test:static",
    "monitor": "python -m monitor.run"
  }
}
```

删除 Cloudflare/Vinext 专用配置和依赖：`vinext`、`vite`、`wrangler`、`@cloudflare/vite-plugin`、`@vitejs/plugin-react`、`@vitejs/plugin-rsc`、`drizzle-orm`、`drizzle-kit`；保留 Next、React、TypeScript、ESLint 和 `tsx`。

- [ ] **Step 4: 更新 HTML 测试读取静态导出文件**

`tests/rendered-html.test.mjs` 固定读取 `out/index.html`，断言页面标题、三条种子岗位和专业匹配说明存在。

- [ ] **Step 5: 运行静态构建测试**

Run: `npm install && SITE_BASE_PATH=/geology-job-radar npm run build && node --test tests/static-export.test.mjs tests/rendered-html.test.mjs`

Expected: PASS，`out/index.html` 存在且资源路径包含 `/geology-job-radar/_next/`。

- [ ] **Step 6: 提交**

```bash
git add package.json package-lock.json next.config.ts tests vite.config.ts worker
git commit -m "build: support GitHub Pages static export"
```

### Task 2: 完整单位名册与来源模型

**Files:**
- Create: `monitor/__init__.py`
- Create: `monitor/units.json`
- Create: `monitor/sources.json`
- Create: `monitor/schema.py`
- Create: `monitor/tests/test_registry.py`
- Create: `monitor/requirements.txt`

**Interfaces:**
- Produces: `load_units(path) -> list[Unit]`、`load_sources(path) -> list[Source]`、`validate_registry(units, sources) -> list[str]`。
- Consumes: 独立部署设计中的完整单位范围。

- [ ] **Step 1: 写名册校验失败测试**

```python
# monitor/tests/test_registry.py
from pathlib import Path
from monitor.schema import load_sources, load_units, validate_registry

ROOT = Path(__file__).parents[2]

def test_complete_registry_is_valid():
    units = load_units(ROOT / "monitor/units.json")
    sources = load_sources(ROOT / "monitor/sources.json")
    assert validate_registry(units, sources) == []
    names = {unit.name for unit in units}
    required = {
        "塔里木油田", "西北油田分公司", "中海油研究总院",
        "神东煤炭集团", "中煤平朔集团", "中煤地质集团有限公司",
        "国冶一局集团", "中化地质矿山总局地质研究院",
        "五矿资源", "中国黄金集团地质有限公司", "中铝矿业",
        "山东黄金地质矿产勘查有限公司", "江西铜业集团地勘工程有限公司",
        "德兴铜矿", "普朗铜矿", "白云鄂博矿区", "镜铁山矿",
        "中铁上海设计院集团有限公司", "中国地质调查局",
    }
    assert required <= names

def test_every_unit_has_coverage_path():
    units = load_units(ROOT / "monitor/units.json")
    assert all(unit.source_ids or unit.parent_unit_id for unit in units)
```

- [ ] **Step 2: 运行测试并确认模块缺失**

Run: `python -m pytest monitor/tests -q`

Expected: FAIL with `ModuleNotFoundError: monitor.schema`。

- [ ] **Step 3: 实现不可变数据模型和校验**

```python
# monitor/schema.py
from dataclasses import dataclass
import json
from pathlib import Path

@dataclass(frozen=True)
class Unit:
    unit_id: str
    name: str
    aliases: tuple[str, ...]
    parent_unit_id: str | None
    group: str
    sector: str
    level: str
    priority: str
    source_ids: tuple[str, ...]
    coverage: str

@dataclass(frozen=True)
class Source:
    source_id: str
    name: str
    url: str
    source_type: str
    trust: str
    unit_ids: tuple[str, ...]
    mode: str
    official_domains: tuple[str, ...]

def load_units(path: Path) -> list[Unit]:
    return [Unit(**{**row, "aliases": tuple(row["aliases"]), "source_ids": tuple(row["source_ids"])})
            for row in json.loads(path.read_text(encoding="utf-8"))]

def load_sources(path: Path) -> list[Source]:
    return [Source(**{**row, "unit_ids": tuple(row["unit_ids"]),
                      "official_domains": tuple(row["official_domains"])})
            for row in json.loads(path.read_text(encoding="utf-8"))]

def validate_registry(units: list[Unit], sources: list[Source]) -> list[str]:
    errors: list[str] = []
    unit_ids = [unit.unit_id for unit in units]
    source_ids = {source.source_id for source in sources}
    if len(unit_ids) != len(set(unit_ids)):
        errors.append("duplicate unit_id")
    for unit in units:
        if unit.parent_unit_id and unit.parent_unit_id not in unit_ids:
            errors.append(f"{unit.unit_id}: missing parent {unit.parent_unit_id}")
        missing = set(unit.source_ids) - source_ids
        if missing:
            errors.append(f"{unit.unit_id}: missing sources {sorted(missing)}")
        if not unit.source_ids and not unit.parent_unit_id:
            errors.append(f"{unit.unit_id}: no coverage path")
    return errors
```

`monitor/requirements.txt` 固定为：

```text
requests>=2.32,<3
beautifulsoup4>=4.12,<5
pypdf>=5,<7
python-docx>=1.1,<2
openpyxl>=3.1,<4
pytest>=8,<10
```

- [ ] **Step 4: 写入完整单位和来源登记表**

`monitor/units.json` 将已批准设计中的 17 类监控范围逐项拆分。集团记录直接绑定来源；子公司、矿区和基层单位绑定自己的官方来源，或通过 `parent_unit_id` 继承集团入口并用自身名称与别名匹配。不得把斜杠、顿号或“及”连接的多个实际单位保留为一条记录。

`monitor/sources.json` 至少登记三桶油、国家能源、中煤、中国煤炭地质总局、中国冶金地质总局、中化地质矿山总局、五矿、中国黄金、中铝、中国有色、国家管网、九大煤炭省属集团、主要黄金有色集团、工程央企、中国地质调查局、国资委、人社部、国聘和国家大学生就业服务平台的公开入口。每个 URL 在写入前必须实际请求验证；无法稳定公开访问的来源使用 `mode: "restricted"`，不得伪造成功 URL。

- [ ] **Step 5: 运行名册测试**

Run: `python -m pytest monitor/tests -q`

Expected: PASS，且 `validate_registry` 返回空列表。

- [ ] **Step 6: 提交**

```bash
git add monitor
git commit -m "feat: add complete monitored unit registry"
```

### Task 3: 页面抓取、附件文本与变化指纹

**Files:**
- Create: `monitor/fetch.py`
- Create: `monitor/fingerprint.py`
- Create: `monitor/tests/fixtures/recruitment.html`
- Create: `monitor/tests/test_fetch.py`
- Create: `monitor/tests/test_fingerprint.py`

**Interfaces:**
- Produces: `fetch_source(source, session) -> FetchResult`、`extract_document_text(content, content_type, url) -> str`、`normalize_text(text) -> str`、`content_fingerprint(text) -> str`。
- Consumes: `Source` from Task 2。

- [ ] **Step 1: 写正文与指纹失败测试**

```python
# monitor/tests/test_fingerprint.py
from monitor.fingerprint import content_fingerprint, normalize_text

def test_dynamic_whitespace_does_not_change_fingerprint():
    a = "2027届 校园招聘\n地质学 硕士"
    b = " 2027届   校园招聘 地质学\t硕士 "
    assert normalize_text(a) == normalize_text(b)
    assert content_fingerprint(a) == content_fingerprint(b)

# monitor/tests/test_fetch.py
from pathlib import Path
from monitor.fetch import html_to_text

def test_html_to_text_drops_navigation_and_scripts():
    html = Path("monitor/tests/fixtures/recruitment.html").read_text(encoding="utf-8")
    text = html_to_text(html)
    assert "地质学" in text
    assert "window.__STATE__" not in text
    assert "网站导航" not in text
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest monitor/tests/test_fetch.py monitor/tests/test_fingerprint.py -q`

Expected: FAIL，抓取与指纹模块不存在。

- [ ] **Step 3: 实现标准化与 SHA-256 指纹**

```python
# monitor/fingerprint.py
import hashlib
import re
import unicodedata

def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()

def content_fingerprint(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()
```

- [ ] **Step 4: 实现限速抓取与多格式正文提取**

`fetch.py` 使用 `requests.Session`，连接和读取超时分别为 10 秒与 30 秒，最多重试 2 次，`User-Agent` 明确写为 `GeologyJobRadar/1.0 (+public GitHub repository)`。HTML 使用 Beautiful Soup 去除 `script/style/nav/footer`；PDF 使用 pypdf；DOCX 使用 python-docx；XLSX 使用 openpyxl。无法解析或被 robots/访问控制禁止时返回 `status="restricted"` 或 `status="failed"`，不抛出导致全批次终止的异常。

- [ ] **Step 5: 运行抓取单元测试**

Run: `python -m pytest monitor/tests/test_fetch.py monitor/tests/test_fingerprint.py -q`

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add monitor/fetch.py monitor/fingerprint.py monitor/tests monitor/requirements.txt
git commit -m "feat: fetch and fingerprint public recruitment pages"
```

### Task 4: 招聘解析、专业判定与去重

**Files:**
- Create: `monitor/match.py`
- Create: `monitor/parse.py`
- Create: `monitor/tests/test_match.py`
- Create: `monitor/tests/test_parse.py`

**Interfaces:**
- Produces: `classify_major(text) -> MatchDecision`、`is_target_recruitment(text) -> bool`、`parse_candidate(text, source, discovered_at) -> Candidate | None`、`dedupe_candidates(candidates) -> list[Candidate]`。
- Consumes: Task 2 `Source`，Task 3 标准化正文。

- [ ] **Step 1: 写专业规则失败测试**

```python
# monitor/tests/test_match.py
from monitor.match import classify_major, is_target_recruitment

def test_geology_is_exact_match():
    decision = classify_major("专业要求：地质学、矿物学，硕士研究生")
    assert decision.level == "完全匹配"
    assert "地质学" in decision.evidence

def test_geological_engineering_only_requires_consultation():
    decision = classify_major("专业要求：地质工程、资源勘查工程、采矿工程")
    assert decision.level == "需咨询"

def test_target_graduation_batch():
    assert is_target_recruitment("面向2027届高校毕业生校园招聘")
    assert not is_target_recruitment("2025届社会招聘")
```

- [ ] **Step 2: 运行规则测试并确认失败**

Run: `python -m pytest monitor/tests/test_match.py monitor/tests/test_parse.py -q`

Expected: FAIL，匹配模块不存在。

- [ ] **Step 3: 实现可解释专业规则**

```python
# monitor/match.py
from dataclasses import dataclass
import re

EXACT = ("地质学", "0709", "矿物学、岩石学、矿床学", "古生物学与地层学", "构造地质学")
ENGINEERING_ONLY = ("地质工程", "资源勘查工程", "勘查技术与工程", "工程地质", "物探", "采矿工程")

@dataclass(frozen=True)
class MatchDecision:
    level: str
    priority: str
    evidence: str
    rule_id: str

def classify_major(text: str) -> MatchDecision:
    exact = next((term for term in EXACT if term in text), None)
    if exact:
        return MatchDecision("完全匹配", "重点冲", exact, "major.exact")
    if "地质类" in text or re.search(r"地学.{0,6}相关专业", text):
        return MatchDecision("可能匹配", "保底", "地质类/地学相关专业", "major.related")
    engineering = [term for term in ENGINEERING_ONLY if term in text]
    if engineering:
        return MatchDecision("需咨询", "专业匹配较弱", "、".join(engineering), "major.engineering_only")
    return MatchDecision("需咨询", "专业匹配较弱", "未找到地质学专业原文", "major.unknown")

def is_target_recruitment(text: str) -> bool:
    return bool(re.search(r"2027\s*届|2027年(?:毕业|应届)", text)) and "社会招聘" not in text[:80]
```

- [ ] **Step 4: 实现候选字段解析与稳定去重键**

`parse.py` 定义 `Candidate` 数据类，字段包括 `id/company/parent/batch/publishedAt/deadline/deadlineLabel/roles/education/majors/locations/priority/match/conditions/assessment/officialUrl/mirrorUrls/sourceTrust/firstSeenAt/lastConfirmedAt/status/evidence/ruleId`。`id` 使用标准化后的“实际单位 + 批次 + 官方 URL”生成 SHA-256 前 16 位；去重时同一 `id` 合并来源与最后确认时间。

- [ ] **Step 5: 运行解析测试**

Run: `python -m pytest monitor/tests/test_match.py monitor/tests/test_parse.py -q`

Expected: PASS，包含“地质工程”而无“地质学”的样例为“需咨询”。

- [ ] **Step 6: 提交**

```bash
git add monitor/match.py monitor/parse.py monitor/tests
git commit -m "feat: classify geology recruitment candidates"
```

### Task 5: 增量监控管线与失败保留

**Files:**
- Create: `monitor/pipeline.py`
- Create: `monitor/run.py`
- Create: `monitor/state.json`
- Create: `data/radar.json`
- Create: `monitor/tests/test_pipeline.py`
- Create: `monitor/tests/fixtures/previous-radar.json`

**Interfaces:**
- Produces: `load_radar(path) -> RadarData`、`run_pipeline(units, sources, previous, state, now) -> RadarData`；CLI `python -m monitor.run --now ISO8601 --offline-fixtures DIR`。
- Consumes: Tasks 2–4。

- [ ] **Step 1: 写失败保留与截止归档测试**

```python
# monitor/tests/test_pipeline.py
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from monitor.pipeline import load_radar, merge_results

NOW = datetime(2026, 7, 21, 19, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
PREVIOUS = Path("monitor/tests/fixtures/previous-radar.json")

def test_failed_source_preserves_last_verified_job():
    previous_radar = load_radar(PREVIOUS)
    merged = merge_results(previous_radar, [], {"official-a": "failed"}, NOW)
    assert merged.jobs[0].status == "来源检查失败"
    assert merged.jobs[0].company == previous_radar.jobs[0].company

def test_expired_job_moves_to_history():
    previous_radar = load_radar(PREVIOUS)
    merged = merge_results(previous_radar, [], {"official-a": "success"}, NOW)
    assert merged.jobs == []
    assert merged.history[0].status == "已截止"
```

- [ ] **Step 2: 运行管线测试并确认失败**

Run: `python -m pytest monitor/tests/test_pipeline.py -q`

Expected: FAIL，管线模块不存在。

- [ ] **Step 3: 实现顺序稳定、失败安全的增量管线**

`pipeline.py` 并发抓取来源，但最终按 `priority、publishedAt、company` 稳定排序。只有成功抓取且公告明确失效时才删除有效记录；抓取失败、受限或字段解析失败时保留旧记录并更新来源健康状态。过期记录进入 `history`，相同 ID 不可同时出现在有效和历史数组。

- [ ] **Step 4: 实现 CLI 与原子写入**

`run.py` 使用临时文件写入后 `Path.replace()` 原子替换 `data/radar.json` 和 `monitor/state.json`；`--offline-fixtures` 禁止网络并用于 CI 测试。输出 JSON 顶层固定包含 `version/generatedAt/lastCheckedAt/jobs/history/sources/coverage/summary`。

- [ ] **Step 5: 迁移现有三条种子招聘**

将 `app/jobs.ts` 中三条记录写入 `data/radar.json`，保留原官方/镜像链接、专业原文、匹配结论和截止时间。截止日期相对运行时间动态进入历史，不手工伪造有效状态。

- [ ] **Step 6: 运行全部 Python 测试和离线管线**

Run: `python -m pytest monitor/tests -q && python -m monitor.run --now 2026-07-14T19:00:00+08:00 --offline-fixtures monitor/tests/fixtures`

Expected: PASS；`data/radar.json` 符合固定顶层结构。

- [ ] **Step 7: 提交**

```bash
git add monitor data
git commit -m "feat: generate radar data with failure-safe monitoring"
```

### Task 6: 网站读取独立数据并展示监控健康度

**Files:**
- Modify: `app/jobs.ts`
- Modify: `app/JobRadar.tsx`
- Modify: `app/components/FilterBar.tsx`
- Modify: `app/components/JobRow.tsx`
- Create: `app/components/CoveragePanel.tsx`
- Modify: `app/job-filters.ts`
- Modify: `app/globals.css`
- Create: `tests/radar-data.test.ts`
- Modify: `tests/job-filters.test.ts`

**Interfaces:**
- Consumes: `data/radar.json` from Task 5。
- Produces: 静态页面展示有效岗位、历史状态、来源健康和完整覆盖统计。

- [ ] **Step 1: 写数据契约和健康面板失败测试**

```ts
// tests/radar-data.test.ts
import assert from "node:assert/strict";
import test from "node:test";
import { radar } from "../app/jobs.ts";

test("radar exposes independent monitoring metadata", () => {
  assert.match(radar.lastCheckedAt, /^\d{4}-\d{2}-\d{2}T/);
  assert.ok(radar.coverage.totalUnits > 0);
  assert.equal(
    radar.coverage.totalUnits,
    radar.coverage.direct + radar.coverage.inherited + radar.coverage.restricted,
  );
});

test("every job preserves matching evidence", () => {
  assert.ok(radar.jobs.every((job) => job.evidence && job.ruleId));
});
```

- [ ] **Step 2: 运行前端单元测试并确认失败**

Run: `node --import tsx --test tests/radar-data.test.ts`

Expected: FAIL，当前数据模型没有 `radar.coverage`。

- [ ] **Step 3: 将 JSON 映射为严格 TypeScript 数据契约**

`app/jobs.ts` 导入 `../data/radar.json`，导出 `RadarData`、`JobPosting`、`SourceHealth` 类型和经过只读断言的 `radar`。删除硬编码 `lastCheckedAt` 和硬编码 `jobs` 数组。

- [ ] **Step 4: 更新看板和列表**

页面顶部显示最近核查时间、有效岗位、临近截止、今日新增、监控单位数；`CoveragePanel` 显示成功、失败、受限来源及单位覆盖方式。列表增加首次发现、最后确认、变化摘要和来源可信度。默认展示有效岗位，提供历史岗位切换；失败来源保留岗位时显示“来源检查失败”，不得显示成已确认最新。

- [ ] **Step 5: 更新样式和可访问性**

在 360px 下保持单列且无横向滚动；来源健康不能只靠颜色，状态文本和图标均有可读标签；键盘焦点、`aria-live` 结果计数和 reduced-motion 保持有效。

- [ ] **Step 6: 运行前端测试与静态构建**

Run: `npm test`

Expected: TypeScript、筛选、HTML 和 GitHub Pages 静态导出测试全部 PASS。

- [ ] **Step 7: 提交**

```bash
git add app data tests
git commit -m "feat: show independent monitoring coverage and history"
```

### Task 7: GitHub Actions 监控与 Pages 发布

**Files:**
- Create: `.github/workflows/monitor.yml`
- Create: `.github/workflows/deploy.yml`
- Create: `.github/dependabot.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `python -m monitor.run`、`npm test`、Next `out/`。
- Produces: 每日数据提交和 GitHub Pages 部署。

- [ ] **Step 1: 写工作流静态检查**

在 `tests/static-export.test.mjs` 增加：

```js
test("daily monitor and Pages workflows exist", () => {
  const monitor = fs.readFileSync(".github/workflows/monitor.yml", "utf8");
  const deploy = fs.readFileSync(".github/workflows/deploy.yml", "utf8");
  assert.match(monitor, /cron: ['"]0 11 \* \* \*['"]/);
  assert.match(monitor, /python -m monitor\.run/);
  assert.match(deploy, /actions\/deploy-pages/);
});
```

- [ ] **Step 2: 运行测试并确认工作流缺失**

Run: `node --test tests/static-export.test.mjs`

Expected: FAIL with `ENOENT: .github/workflows/monitor.yml`。

- [ ] **Step 3: 创建每日监控工作流**

`monitor.yml` 使用 `schedule: 0 11 * * *` 和 `workflow_dispatch`，权限仅为 `contents: write`。步骤依次 checkout、Python 3.12、安装 `monitor/requirements.txt`、运行全部 Python 测试、运行监控、仅在 diff 存在时以 `github-actions[bot]` 提交并推送。无论是否发现岗位，`lastCheckedAt` 和来源健康状态都会更新，因此每次成功运行产生可追溯记录。

- [ ] **Step 4: 创建 Pages 发布工作流**

`deploy.yml` 响应 `push` 到 `main`、手动触发和 `monitor.yml` 的 `workflow_run: completed`。仅在监控成功时部署；权限为 `contents: read`、`pages: write`、`id-token: write`。构建时设置 `SITE_BASE_PATH=/geology-job-radar`，上传 `out/`，使用 `actions/deploy-pages@v4` 发布。

- [ ] **Step 5: 更新 README**

README 说明公开网址、每日运行时间、专业判定口径、免费抓取限制、手动运行方式、来源失败含义和不收集个人数据。不得保留 Sites、Cloudflare Worker、D1 或 ChatGPT 登录说明。

- [ ] **Step 6: 运行工作流静态测试和完整门禁**

Run: `python -m pytest monitor/tests -q && npm run lint && npm test`

Expected: 全部 PASS。

- [ ] **Step 7: 提交**

```bash
git add .github README.md tests
git commit -m "ci: automate daily monitoring and Pages deployment"
```

### Task 8: 创建公开仓库、启用 Pages 并验证首次运行

**Files:**
- No source changes unless remote validation exposes a defect.

**Interfaces:**
- Consumes: Tasks 1–7 的已验证主分支。
- Produces: GitHub 公开仓库、成功 Actions 运行和公开 Pages URL。

- [ ] **Step 1: 最终本地验证**

Run: `python -m pytest monitor/tests -q && npm run lint && npm test && git status --short`

Expected: 所有测试通过，工作树为空。

- [ ] **Step 2: 创建公开 GitHub 仓库**

在已连接账号下创建 `geology-job-radar` 公共仓库，默认分支 `main`，不自动生成 README、许可证或 `.gitignore`，避免覆盖本地历史。

- [ ] **Step 3: 推送经过验证的主分支**

保留现有 Sites 远端作为备份，新增名为 `github` 的远端并推送：

```bash
git remote add github https://github.com/healerLSC/geology-job-radar.git
git push -u github main
```

推送目标固定为已连接账号 `healerLSC`；不得把邮箱、令牌或内部远端地址写入仓库。

- [ ] **Step 4: 启用 GitHub Pages 的 GitHub Actions 来源**

将仓库 Pages 发布来源设为 GitHub Actions。若连接器不提供该设置，首次 `deploy-pages` 工作流会创建 Pages 环境；只有在平台明确要求时才由用户在仓库 Settings → Pages 选择 GitHub Actions。

- [ ] **Step 5: 手动触发首次监控并核验 Actions**

触发 `monitor.yml`，等待测试、抓取和提交完成；随后确认 `deploy.yml` 成功。若某些来源失败，确认网站展示失败状态且旧招聘记录未被清空。

- [ ] **Step 6: 浏览器验收公开网站**

打开 `https://healerlsc.github.io/geology-job-radar/`，验证首页、搜索、专业筛选、历史切换、来源健康、官方链接、移动端和静态资源。确认页面最后核查时间来自独立监控输出。

- [ ] **Step 7: 完成交付**

向用户提供独立网址和公开仓库链接，说明无需打开或续费 ChatGPT。保留原 ChatGPT Sites 网站作为临时备份；待用户确认独立版连续运行正常后再决定是否停用原 ChatGPT 自动任务。
