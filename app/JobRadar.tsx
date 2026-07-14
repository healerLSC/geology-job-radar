"use client";

import { useDeferredValue, useMemo, useState } from "react";

import { CoveragePanel } from "./components/CoveragePanel";
import { FilterBar } from "./components/FilterBar";
import { JobRow } from "./components/JobRow";
import { filterJobs } from "./job-filters";
import {
  historyJobs,
  jobs,
  lastCheckedAt,
  radar,
  type MatchLevel,
  type Priority,
  type RegistryScope,
  type Sector,
} from "./jobs";

const RadarMark = () => (
  <svg aria-hidden="true" viewBox="0 0 40 40" fill="none">
    <circle cx="20" cy="20" r="15" />
    <circle cx="20" cy="20" r="8" />
    <circle cx="20" cy="20" r="2.5" />
    <path d="M20 20 31 9" />
    <path d="M4 20h4M32 20h4M20 4v4M20 32v4" />
  </svg>
);

const summaryItems = [
  { label: "有效机会", value: radar.summary.active, unit: "条" },
  { label: "7日内截止", value: radar.summary.nearDeadline, unit: "条" },
  { label: "专业完全匹配", value: radar.summary.exactMatch, unit: "条" },
  { label: "监控覆盖", value: radar.coverage.totalUnits, unit: "个单位" },
];

export default function JobRadar() {
  const [view, setView] = useState<"active" | "history">("active");
  const [query, setQuery] = useState("");
  const [priority, setPriority] = useState<Priority | "全部">("全部");
  const [match, setMatch] = useState<MatchLevel | "全部">("全部");
  const [sector, setSector] = useState<Sector | "全部">("全部");
  const [registryScope, setRegistryScope] = useState<RegistryScope | "全部">("全部");
  const deferredQuery = useDeferredValue(query);
  const visibleJobs = view === "active" ? jobs : historyJobs;

  const filteredJobs = useMemo(
    () => filterJobs(visibleJobs, { query: deferredQuery, priority, match, sector, registryScope }),
    [visibleJobs, deferredQuery, priority, match, sector, registryScope],
  );

  const hasFilters = Boolean(
    query || priority !== "全部" || match !== "全部" || sector !== "全部" || registryScope !== "全部",
  );

  const resetFilters = () => {
    setQuery("");
    setPriority("全部");
    setMatch("全部");
    setSector("全部");
    setRegistryScope("全部");
  };

  return (
    <main>
      <header className="site-header">
        <div className="page-shell site-header__inner">
          <a className="brand" href="#top" aria-label="返回招聘雷达顶部">
            <span className="brand__mark">
              <RadarMark />
            </span>
            <span>
              <strong>地质招聘雷达</strong>
              <small>2027届 · 地质学硕士</small>
            </span>
          </a>
          <div className="check-status" aria-label={`最后核查时间：${lastCheckedAt}`}>
            <span className="status-pulse" aria-hidden="true" />
            <span>
              <small>最后核查</small>
              <strong>{lastCheckedAt}</strong>
            </span>
          </div>
        </div>
      </header>

      <div id="top" className="page-shell page-content">
        <section className="intro" aria-labelledby="page-title">
          <div>
            <p className="intro__eyebrow">基础名册＋扩展发现</p>
            <h1 id="page-title">今天只看值得投的</h1>
            <p className="intro__copy">
              汇总公开可访问的招聘渠道，优先标出新增、临近截止和真正接受
              <strong>地质学</strong>专业的机会；工程类岗位照常收集并单独标注。
              每家子公司、研究院和矿区分别核查，名单外单位也持续发现。
            </p>
          </div>
          <div className="intro__note">
            <span>本轮结论</span>
            <p>
              发现 <strong>{radar.summary.active}条</strong> 有效信息，其中
              <strong>{radar.summary.exactMatch}条</strong> 专业完全匹配、
              <strong>{radar.summary.nearDeadline}条</strong> 将于7日内截止。
            </p>
          </div>
        </section>

        <section className="summary-strip" aria-label="招聘雷达摘要">
          {summaryItems.map((item) => (
            <div className="summary-item" key={item.label}>
              <p>{item.label}</p>
              <strong>
                {item.value}
                <small>{item.unit}</small>
              </strong>
            </div>
          ))}
        </section>

        <CoveragePanel radar={radar} />

        <section className="radar-section" aria-labelledby="opportunities-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">机会清单</p>
              <h2 id="opportunities-title">
                {view === "active" ? "已核实的招聘更新" : "已截止或下线的历史岗位"}
              </h2>
            </div>
            <p>
              当前显示 <strong>{filteredJobs.length}</strong> / {visibleJobs.length} 条
            </p>
          </div>

          <div className="view-tabs" role="tablist" aria-label="岗位状态">
            <button
              type="button"
              role="tab"
              aria-selected={view === "active"}
              className={view === "active" ? "is-active" : ""}
              onClick={() => setView("active")}
            >
              当前机会 <span>{jobs.length}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === "history"}
              className={view === "history" ? "is-active" : ""}
              onClick={() => setView("history")}
            >
              历史岗位 <span>{historyJobs.length}</span>
            </button>
          </div>

          <FilterBar
            query={query}
            priority={priority}
            match={match}
            sector={sector}
            registryScope={registryScope}
            hasFilters={hasFilters}
            onQueryChange={setQuery}
            onPriorityChange={setPriority}
            onMatchChange={setMatch}
            onSectorChange={setSector}
            onRegistryScopeChange={setRegistryScope}
            onReset={resetFilters}
          />

          <div className="job-list" aria-live="polite">
            {filteredJobs.length ? (
              filteredJobs.map((job) => <JobRow key={job.id} job={job} />)
            ) : (
              <div className="empty-state">
                <RadarMark />
                <h3>{visibleJobs.length ? "没有符合当前条件的岗位" : "这里暂时没有岗位"}</h3>
                <p>
                  {visibleJobs.length
                    ? "可以换一个关键词，或清除筛选查看全部已核实信息。"
                    : view === "history"
                      ? "岗位截止或确认下线后会自动归档到这里。"
                      : "下一轮发现符合条件的新公告后会自动显示。"}
                </p>
                <button type="button" onClick={resetFilters}>
                  清除筛选
                </button>
              </div>
            )}
          </div>
        </section>

        <section className="method-note" aria-labelledby="method-title">
          <div>
            <p className="section-kicker">判定口径</p>
            <h2 id="method-title">岗位名称带“地质”，不等于专业匹配</h2>
          </div>
          <div className="method-grid">
            <p>
              <strong>完全匹配</strong>
              公告原文明确包含“地质学”或专业代码0709。
            </p>
            <p>
              <strong>大类可能匹配</strong>
              公告使用“地质类、相关专业”等宽口径，但没有完整专业目录。
            </p>
            <p>
              <strong>工程类限定</strong>
              仅列出地质工程、资源勘查工程、工程地质或物探；仍然收集，但地质学投递前必须确认。
            </p>
            <p>
              <strong>扩展发现</strong>
              原始349家之外的企业、科研院所和事业单位，只要招聘地质相关专业也会进入雷达。
            </p>
          </div>
        </section>

        <footer className="site-footer">
          <p>招聘雷达用于提高信息检索效率，专业目录、报名资格及截止时间最终以官方公告为准。</p>
          <a href="#top">回到顶部</a>
        </footer>
      </div>
    </main>
  );
}
