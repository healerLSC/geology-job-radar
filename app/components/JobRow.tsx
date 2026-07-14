import { getDeadlineState } from "../job-filters";
import type { JobPosting } from "../jobs";

const ExternalIcon = () => (
  <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
    <path d="M8 4H4.75A1.75 1.75 0 0 0 3 5.75v9.5C3 16.216 3.784 17 4.75 17h9.5A1.75 1.75 0 0 0 16 15.25V12" />
    <path d="M11 3h6v6M17 3l-7.25 7.25" />
  </svg>
);

const CalendarIcon = () => (
  <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
    <rect x="2.75" y="4.25" width="14.5" height="13" rx="2" />
    <path d="M6 2.5v3.25M14 2.5v3.25M2.75 8h14.5" />
  </svg>
);

const PinIcon = () => (
  <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
    <path d="M16 8.3c0 4.2-6 9.2-6 9.2s-6-5-6-9.2a6 6 0 1 1 12 0Z" />
    <circle cx="10" cy="8.25" r="2" />
  </svg>
);

const publishedLabel = (date: string) => {
  const [, month, day] = date.split("-");
  return `${Number(month)}月${Number(day)}日发布`;
};

const checkedLabel = (date: string) =>
  new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "numeric",
    day: "numeric",
  }).format(new Date(date));

const officialLabel = (job: JobPosting) => {
  if (job.sourceTrust === "official") return "官方公告";
  if (job.sourceTrust === "authoritative") return "权威平台公告";
  return "公开线索（待复核）";
};

export function JobRow({ job }: { job: JobPosting }) {
  const deadlineState = getDeadlineState(job.deadline);

  return (
    <article className="job-row">
      <div className="job-row__topline">
        <div className="badge-group" aria-label={`投递级别：${job.priority}；专业判断：${job.match}`}>
          <span className={`badge priority priority--${job.priority}`}>{job.priority}</span>
          <span className={`badge match match--${job.match}`}>{job.match}</span>
          {job.status !== "可投" ? (
            <span className={`badge status-badge status-badge--${job.status}`}>{job.status}</span>
          ) : null}
        </div>
        <div className={`deadline deadline--${deadlineState}`}>
          <CalendarIcon />
          <span>{job.deadlineLabel}</span>
          <small>{deadlineState}</small>
        </div>
      </div>

      <div className="job-heading">
        <div>
          <p className="parent-name">{job.parent}</p>
          <h3>{job.company}</h3>
        </div>
        <div className="job-meta">
          <span>{job.batch}</span>
          <span>{publishedLabel(job.publishedAt)}</span>
          <span>{job.sector}</span>
        </div>
      </div>

      <div className="job-facts">
        <div className="fact">
          <p className="fact__label">地质相关岗位</p>
          <p className="fact__value">{job.roles.join(" · ")}</p>
        </div>
        <div className="fact">
          <p className="fact__label">学历与专业原文</p>
          <p className="fact__value">{job.education}</p>
          <p className="fact__support">{job.majors}</p>
        </div>
        <div className="fact">
          <p className="fact__label">工作地点</p>
          <p className="fact__value location-line">
            <PinIcon />
            <span>{job.locations.join("、")}</span>
          </p>
        </div>
      </div>

      <div className="match-note">
        <div className="match-note__heading">
          <span className="match-dot" aria-hidden="true" />
          <p>专业匹配依据</p>
        </div>
        <div>
          <p>{job.assessment}</p>
          <p className="match-note__evidence">
            识别依据：{job.evidence} · 规则 {job.ruleId}
          </p>
        </div>
      </div>

      <div className="job-row__footer">
        <div>
          <ul className="conditions" aria-label="额外招聘条件">
            {job.conditions.map((condition) => (
              <li key={condition}>{condition}</li>
            ))}
          </ul>
          <p className="verification-meta">
            {job.changeSummary} · 首次发现 {checkedLabel(job.firstSeenAt)} · 最近核实 {checkedLabel(job.lastConfirmedAt)}
          </p>
        </div>
        <div className="source-actions">
          <a href={job.officialUrl} target="_blank" rel="noreferrer">
            {officialLabel(job)}
            <ExternalIcon />
          </a>
          {job.mirrorUrls.slice(0, 2).map((url, index) => (
            <a className="secondary-link" href={url} target="_blank" rel="noreferrer" key={url}>
              {index ? `补充来源 ${index + 1}` : "补充来源"}
              <ExternalIcon />
            </a>
          ))}
        </div>
      </div>
    </article>
  );
}
