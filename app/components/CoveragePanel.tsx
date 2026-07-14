import type { RadarData } from "../jobs";

const healthLabel = {
  success: "正常",
  restricted: "访问受限",
  failed: "检查失败",
} as const;

export function CoveragePanel({ radar }: { radar: RadarData }) {
  const health = radar.sources.reduce(
    (counts, source) => {
      counts[source.status] += 1;
      return counts;
    },
    { success: 0, restricted: 0, failed: 0 },
  );
  const totalSources = radar.coverage.totalSources ?? radar.sources.length;
  const checkedSources = radar.coverage.checkedSources ?? radar.sources.length;

  return (
    <section className="coverage-panel" aria-labelledby="coverage-title">
      <div className="coverage-panel__intro">
        <p className="section-kicker">独立自动监控</p>
        <h2 id="coverage-title">覆盖范围与来源健康</h2>
        <p>
          名单内 <strong>{radar.coverage.totalUnits}</strong> 个集团、子公司、矿区、研究院和地勘单位均保留监控；
          集团入口发布的岗位会继续识别实际用人单位。
        </p>
      </div>

      <div className="coverage-stats" aria-label="监控覆盖统计">
        <div>
          <span>直接来源覆盖</span>
          <strong>{radar.coverage.direct}</strong>
        </div>
        <div>
          <span>继承集团来源</span>
          <strong>{radar.coverage.inherited}</strong>
        </div>
        <div>
          <span>已检查来源</span>
          <strong>{checkedSources}<small> / {totalSources}</small></strong>
        </div>
      </div>

      <div className="source-health" aria-label="来源健康">
        <div className="source-health__heading">
          <strong>来源健康</strong>
          <span>{checkedSources ? "最近一轮独立核查" : "等待首次独立核查"}</span>
        </div>
        <div className="source-health__counts">
          {(Object.keys(healthLabel) as Array<keyof typeof healthLabel>).map((status) => (
            <span className={`health-count health-count--${status}`} key={status}>
              {healthLabel[status]} <strong>{health[status]}</strong>
            </span>
          ))}
        </div>
        <p>
          来源失败或受限时，网站保留上次核实结果并明确标记，不把抓取失败误当作岗位下线。
        </p>
      </div>
    </section>
  );
}
