import type { MatchLevel, Priority, RegistryScope, Sector } from "../jobs";
import { matchOptions, priorityOptions, sectorOptions } from "../jobs";

type FilterBarProps = {
  query: string;
  priority: Priority | "全部";
  match: MatchLevel | "全部";
  sector: Sector | "全部";
  registryScope: RegistryScope | "全部";
  hasFilters: boolean;
  onQueryChange: (value: string) => void;
  onPriorityChange: (value: Priority | "全部") => void;
  onMatchChange: (value: MatchLevel | "全部") => void;
  onSectorChange: (value: Sector | "全部") => void;
  onRegistryScopeChange: (value: RegistryScope | "全部") => void;
  onReset: () => void;
};

const SearchIcon = () => (
  <svg aria-hidden="true" viewBox="0 0 24 24" fill="none">
    <circle cx="11" cy="11" r="6.75" />
    <path d="m16 16 4 4" />
  </svg>
);

export function FilterBar({
  query,
  priority,
  match,
  sector,
  registryScope,
  hasFilters,
  onQueryChange,
  onPriorityChange,
  onMatchChange,
  onSectorChange,
  onRegistryScopeChange,
  onReset,
}: FilterBarProps) {
  return (
    <div className="filter-bar" aria-label="招聘筛选工具">
      <label className="search-field">
        <span className="sr-only">搜索单位、岗位、专业或地点</span>
        <SearchIcon />
        <input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="搜索单位、岗位、专业或地点"
        />
      </label>

      <label className="select-field">
        <span>投递级别</span>
        <select
          value={priority}
          onChange={(event) => onPriorityChange(event.target.value as Priority | "全部")}
        >
          <option value="全部">全部级别</option>
          {priorityOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>

      <label className="select-field">
        <span>专业判断</span>
        <select
          value={match}
          onChange={(event) => onMatchChange(event.target.value as MatchLevel | "全部")}
        >
          <option value="全部">全部判断</option>
          {matchOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>

      <label className="select-field">
        <span>名单范围</span>
        <select
          value={registryScope}
          onChange={(event) => onRegistryScopeChange(event.target.value as RegistryScope | "全部")}
        >
          <option value="全部">全部范围</option>
          <option value="base">基础名册</option>
          <option value="discovered">扩展发现</option>
        </select>
      </label>

      <label className="select-field">
        <span>单位类别</span>
        <select
          value={sector}
          onChange={(event) => onSectorChange(event.target.value as Sector | "全部")}
        >
          <option value="全部">全部类别</option>
          {sectorOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>

      <button className="reset-button" type="button" onClick={onReset} disabled={!hasFilters}>
        清除筛选
      </button>
    </div>
  );
}
