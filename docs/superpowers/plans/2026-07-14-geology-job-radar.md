# 地质招聘雷达 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建并发布一个可搜索、可筛选、严格区分地质学与地质工程的单页招聘雷达。

**Architecture:** 使用Vinext/React单页应用。招聘记录与筛选逻辑分别放在独立模块中，客户端看板只负责交互和展示；服务端页面负责元数据与页面入口。首版不引入数据库和登录，后续招聘核查结果可通过更新数据文件进入页面。

**Tech Stack:** React 19、Next/Vinext、TypeScript、Tailwind CSS 4、Node test、Sites hosting。

## Global Constraints

- 页面语言为简体中文，面向2027届地质学硕士。
- “地质工程、资源勘查工程、工程地质、物探”不得自动判为地质学完全匹配。
- 招聘单位必须按实际二三级用人单位单列。
- 官方来源与第三方镜像必须在视觉和文案上区分。
- 首版不增加登录、数据库、邮件订阅或伪实时爬取。
- 手机与桌面均需可用，360px宽度不得横向溢出。

---

### Task 1: 招聘数据模型与筛选逻辑

**Files:**
- Create: `app/jobs.ts`
- Create: `app/job-filters.ts`
- Create: `tests/job-filters.test.ts`

**Interfaces:**
- Produces: `JobPosting`, `jobs`, `filterJobs(jobs, filters)`、`getDeadlineState(deadline)`。
- Consumes: 无。

- [ ] **Step 1: 编写筛选逻辑测试**

```ts
import test from "node:test";
import assert from "node:assert/strict";
import { filterJobs } from "../app/job-filters.ts";
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
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --import tsx --test tests/job-filters.test.ts`

Expected: FAIL，提示 `app/job-filters.ts` 或 `app/jobs.ts` 不存在。

- [ ] **Step 3: 实现类型、三条种子数据和纯筛选函数**

`JobPosting`包含`id`、`company`、`parent`、`batch`、`publishedAt`、`deadline`、`deadlineLabel`、`roles`、`education`、`majors`、`locations`、`priority`、`match`、`sector`、`conditions`、`assessment`、`officialUrl`、`mirrorUrl`、`sourceType`。`filterJobs`对公司、集团、岗位、专业和地点执行不区分大小写的包含搜索，并与三个枚举筛选取交集。

- [ ] **Step 4: 运行测试并确认通过**

Run: `node --import tsx --test tests/job-filters.test.ts`

Expected: PASS。

### Task 2: 可交互招聘看板

**Files:**
- Create: `app/JobRadar.tsx`
- Create: `app/components/FilterBar.tsx`
- Create: `app/components/JobRow.tsx`
- Modify: `app/page.tsx`
- Modify: `app/globals.css`

**Interfaces:**
- Consumes: `jobs`、`filterJobs`和`JobPosting`。
- Produces: 默认导出的`JobRadar`客户端组件以及单页看板。

- [ ] **Step 1: 增加页面内容测试断言**

在`tests/rendered-html.test.mjs`中断言HTML包含“地质招聘雷达”“广岩国际投资有限责任公司”“专业匹配依据”和“最终以官方公告为准”。

- [ ] **Step 2: 运行生产测试并确认新增断言失败**

Run: `npm test`

Expected: 构建成功但页面内容断言失败。

- [ ] **Step 3: 实现页面和交互组件**

`JobRadar`使用`useMemo`计算结果；`FilterBar`提供搜索、优先级、匹配度和类别筛选；`JobRow`显示单位、截止、岗位、专业原文、限制条件、匹配判断和来源链接。无结果时显示清除筛选按钮。页面采用语义化`header`、`main`、`section`和`article`。

- [ ] **Step 4: 实现响应式视觉系统**

在`globals.css`定义墨色、矿物绿、浅灰和琥珀色令牌；桌面列表使用网格对齐，移动端折叠为单列；添加键盘焦点、悬停、`prefers-reduced-motion`和360px适配。

- [ ] **Step 5: 运行页面测试**

Run: `npm test`

Expected: PASS。

### Task 3: 元数据、可访问性与质量检查

**Files:**
- Modify: `app/layout.tsx`
- Modify: `tests/rendered-html.test.mjs`

**Interfaces:**
- Consumes: Task 2页面。
- Produces: 中文文档语言、招聘雷达标题与描述、稳定页面测试。

- [ ] **Step 1: 更新元数据和HTML语言**

将`lang`改为`zh-CN`，标题改为“地质招聘雷达｜2027届央国企招聘监控”，描述说明只展示核实后的地质相关招聘。

- [ ] **Step 2: 检查类型、样式和生产构建**

Run: `npm run lint && npm run build && npm run validate:artifact`

Expected: 三条命令均退出码0。

### Task 4: 浏览器验证与发布

**Files:**
- Modify only if QA finds defects.

**Interfaces:**
- Consumes: 完整页面。
- Produces: 已验证的在线检查点。

- [ ] **Step 1: 启动内部预览并检查桌面页面**

确认首屏出现标题、最后核查时间、4项摘要、筛选栏和第一条招聘；组合筛选后结果数量改变；清除筛选恢复全部记录；三个外部来源链接可点击。

- [ ] **Step 2: 检查移动页面**

在360px宽度检查无横向溢出，筛选控件和岗位字段保持可读。

- [ ] **Step 3: 修复QA问题并重新运行最终门禁**

Run: `npm run lint && npm test && npm run validate:artifact`

Expected: 全部通过。

- [ ] **Step 4: 创建并核验发布检查点**

发布后查询部署状态，只有状态确认可用时才向用户提供链接。

