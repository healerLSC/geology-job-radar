import radarJson from "../data/radar.json";

export const priorityOptions = ["必投", "重点冲", "保底", "专业匹配较弱"] as const;
export const matchOptions = ["完全匹配", "大类可能匹配", "工程类限定", "需咨询"] as const;
export const registryScopeOptions = ["base", "discovered"] as const;

export type Priority = (typeof priorityOptions)[number];
export type MatchLevel = (typeof matchOptions)[number];
export type RegistryScope = (typeof registryScopeOptions)[number];
export type Sector = string;
export type SourceTrust = "official" | "authoritative" | "clue";
export type JobStatus = "可投" | "待核验线索" | "来源检查失败" | "已截止";
export type VerificationStatus = "official" | "authoritative" | "lead";
export type MajorCategory = "geology" | "broad-geoscience" | "engineering-only" | "consult";

export type SourceEvidence = {
  sourceId: string;
  name: string;
  url: string;
  tier: "l1" | "l2" | "l3";
  trust: SourceTrust;
  discoveredAt: string;
};

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
  registryScope: RegistryScope;
  employerType: string;
  majorCategory: MajorCategory;
  verificationStatus: VerificationStatus;
  sourceEvidence: SourceEvidence[];
  fallbackUsed: boolean;
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
  tier?: "l1" | "l2" | "l3";
  role?: "primary" | "fallback" | "discovery";
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
    unitHealth: {
      primary: number;
      fallback: number;
      leads: number;
      unavailable: number;
    };
  };
  summary: {
    active: number;
    nearDeadline: number;
    exactMatch: number;
    newToday: number;
  };
};

type LegacyJobPosting = Omit<Partial<JobPosting>, "match"> & {
  match?: MatchLevel | "可能匹配";
};

const rawRadar = radarJson as unknown as Omit<RadarData, "jobs" | "history"> & {
  jobs: LegacyJobPosting[];
  history: LegacyJobPosting[];
};

const normalizeJob = (row: LegacyJobPosting): JobPosting => {
  const ruleId = row.ruleId ?? "major.manual_verified";
  const match = row.match === "可能匹配"
    ? "大类可能匹配"
    : row.match === "需咨询" && ruleId === "major.engineering_only"
      ? "工程类限定"
      : (row.match ?? "需咨询");
  const verificationStatus = row.verificationStatus
    ?? (row.sourceTrust === "official" ? "official" : row.sourceTrust === "clue" ? "lead" : "authoritative");
  const majorCategory = row.majorCategory
    ?? (ruleId === "major.exact" ? "geology"
      : ruleId === "major.related" ? "broad-geoscience"
        : ruleId === "major.engineering_only" ? "engineering-only" : "consult");
  return {
    ...row,
    match,
    ruleId,
    registryScope: row.registryScope ?? "base",
    employerType: row.employerType ?? "基础名册单位",
    majorCategory,
    verificationStatus,
    sourceEvidence: row.sourceEvidence ?? [],
    fallbackUsed: row.fallbackUsed ?? verificationStatus === "authoritative",
  } as JobPosting;
};

const defaultUnitHealth = {
  primary: 0,
  fallback: 0,
  leads: 0,
  unavailable: rawRadar.coverage.totalUnits,
};

export const radar: RadarData = {
  ...rawRadar,
  jobs: rawRadar.jobs.map(normalizeJob),
  history: rawRadar.history.map(normalizeJob),
  coverage: {
    ...rawRadar.coverage,
    unitHealth: rawRadar.coverage.unitHealth ?? defaultUnitHealth,
  },
};
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
