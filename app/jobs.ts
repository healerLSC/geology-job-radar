import radarJson from "../data/radar.json";

export const priorityOptions = ["必投", "重点冲", "保底", "专业匹配较弱"] as const;
export const matchOptions = ["完全匹配", "可能匹配", "需咨询"] as const;

export type Priority = (typeof priorityOptions)[number];
export type MatchLevel = (typeof matchOptions)[number];
export type Sector = string;
export type SourceTrust = "official" | "authoritative" | "clue";
export type JobStatus = "可投" | "来源检查失败" | "已截止";

export type JobPosting = {
  id: string;
  company: string;
  parent: string;
  batch: string;
  publishedAt: string;
  deadline: string | null;
  deadlineLabel: string;
  roles: string[];
  education: string;
  majors: string;
  locations: string[];
  priority: Priority;
  match: MatchLevel;
  sector: Sector;
  conditions: string[];
  assessment: string;
  officialUrl: string;
  mirrorUrls: string[];
  sourceType: string;
  sourceTrust: SourceTrust;
  sourceIds: string[];
  firstSeenAt: string;
  lastConfirmedAt: string;
  status: JobStatus;
  evidence: string;
  ruleId: string;
  changeSummary: string;
};

export type SourceHealth = {
  sourceId: string;
  name: string;
  url: string;
  trust: SourceTrust;
  status: "success" | "failed" | "restricted";
  lastCheckedAt: string;
  lastSuccessAt: string | null;
  failureCount: number;
  changed: boolean;
  error: string | null;
};

export type RadarData = {
  version: number;
  generatedAt: string;
  lastCheckedAt: string;
  jobs: JobPosting[];
  history: JobPosting[];
  sources: SourceHealth[];
  coverage: {
    totalUnits: number;
    direct: number;
    inherited: number;
    restricted: number;
    totalSources?: number;
    checkedSources?: number;
  };
  summary: {
    active: number;
    nearDeadline: number;
    exactMatch: number;
    newToday: number;
  };
};

export const radar = radarJson as unknown as RadarData;
export const jobs = radar.jobs;
export const historyJobs = radar.history;
export const sectorOptions = Array.from(
  new Set([...radar.jobs, ...radar.history].map((job) => job.sector)),
).sort((left, right) => left.localeCompare(right, "zh-CN"));

export const lastCheckedAt = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
}).format(new Date(radar.lastCheckedAt));
