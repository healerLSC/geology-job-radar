import type { JobPosting, MatchLevel, Priority, Sector } from "./jobs";

export type JobFilters = {
  query?: string;
  priority?: Priority | "全部";
  match?: MatchLevel | "全部";
  sector?: Sector | "全部";
};

export type DeadlineState = "临近截止" | "进行中" | "已截止" | "未注明";

const searchableText = (job: JobPosting) =>
  [
    job.company,
    job.parent,
    job.batch,
    job.roles.join(" "),
    job.majors,
    job.locations.join(" "),
    job.assessment,
  ]
    .join(" ")
    .toLocaleLowerCase("zh-CN");

export function filterJobs(list: JobPosting[], filters: JobFilters = {}) {
  const query = filters.query?.trim().toLocaleLowerCase("zh-CN") ?? "";

  return list.filter((job) => {
    if (query && !searchableText(job).includes(query)) return false;
    if (filters.priority && filters.priority !== "全部" && job.priority !== filters.priority) {
      return false;
    }
    if (filters.match && filters.match !== "全部" && job.match !== filters.match) return false;
    if (filters.sector && filters.sector !== "全部" && job.sector !== filters.sector) return false;
    return true;
  });
}

export function getDeadlineState(
  deadline: string | null,
  now = new Date(),
): DeadlineState {
  if (!deadline) return "未注明";

  const remaining = new Date(deadline).getTime() - now.getTime();
  if (remaining < 0) return "已截止";
  if (remaining <= 7 * 24 * 60 * 60 * 1000) return "临近截止";
  return "进行中";
}
