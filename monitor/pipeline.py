from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
from typing import Callable, Iterable, Mapping
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from monitor.fetch import FetchResult, create_session, fetch_source
from monitor.fingerprint import content_fingerprint
from monitor.parse import Candidate, dedupe_candidates, parse_candidate
from monitor.schema import Source, Unit


SHANGHAI = ZoneInfo("Asia/Shanghai")
PRIORITY_ORDER = {"必投": 0, "重点冲": 1, "保底": 2, "专业匹配较弱": 3}


@dataclass(frozen=True)
class RadarData:
    version: int
    generated_at: str
    last_checked_at: str
    jobs: tuple[Candidate, ...]
    history: tuple[Candidate, ...]
    sources: tuple[dict, ...]
    coverage: dict
    summary: dict


def _candidate_from_dict(row: dict) -> Candidate:
    return Candidate(
        id=row["id"],
        company=row["company"],
        parent=row["parent"],
        batch=row["batch"],
        published_at=row["publishedAt"],
        deadline=row.get("deadline"),
        deadline_label=row.get("deadlineLabel", "官方未注明"),
        roles=tuple(row.get("roles", ())),
        education=row.get("education", "官方未注明"),
        majors=row.get("majors", "官方未注明"),
        locations=tuple(row.get("locations", ())),
        priority=row["priority"],
        match=row["match"],
        sector=row["sector"],
        conditions=tuple(row.get("conditions", ())),
        assessment=row.get("assessment", ""),
        official_url=row["officialUrl"],
        mirror_urls=tuple(row.get("mirrorUrls", row.get("mirrorUrl") and [row["mirrorUrl"]] or ())),
        source_type=row.get("sourceType", "公开来源"),
        source_trust=row.get("sourceTrust", "authoritative"),
        source_ids=tuple(row.get("sourceIds", ())),
        first_seen_at=row.get("firstSeenAt", row.get("publishedAt", "")),
        last_confirmed_at=row.get("lastConfirmedAt", row.get("publishedAt", "")),
        status=row.get("status", "可投"),
        evidence=row.get("evidence", row.get("majors", "")),
        rule_id=row.get("ruleId", "major.manual_verified"),
        change_summary=row.get("changeSummary", "历史数据迁移"),
    )


def _candidate_to_dict(candidate: Candidate) -> dict:
    return {
        "id": candidate.id,
        "company": candidate.company,
        "parent": candidate.parent,
        "batch": candidate.batch,
        "publishedAt": candidate.published_at,
        "deadline": candidate.deadline,
        "deadlineLabel": candidate.deadline_label,
        "roles": list(candidate.roles),
        "education": candidate.education,
        "majors": candidate.majors,
        "locations": list(candidate.locations),
        "priority": candidate.priority,
        "match": candidate.match,
        "sector": candidate.sector,
        "conditions": list(candidate.conditions),
        "assessment": candidate.assessment,
        "officialUrl": candidate.official_url,
        "mirrorUrls": list(candidate.mirror_urls),
        "sourceType": candidate.source_type,
        "sourceTrust": candidate.source_trust,
        "sourceIds": list(candidate.source_ids),
        "firstSeenAt": candidate.first_seen_at,
        "lastConfirmedAt": candidate.last_confirmed_at,
        "status": candidate.status,
        "evidence": candidate.evidence,
        "ruleId": candidate.rule_id,
        "changeSummary": candidate.change_summary,
    }


def load_radar(path: Path) -> RadarData:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return RadarData(
        version=payload.get("version", 1),
        generated_at=payload["generatedAt"],
        last_checked_at=payload["lastCheckedAt"],
        jobs=tuple(_candidate_from_dict(row) for row in payload.get("jobs", ())),
        history=tuple(_candidate_from_dict(row) for row in payload.get("history", ())),
        sources=tuple(payload.get("sources", ())),
        coverage=dict(payload.get("coverage", {})),
        summary=dict(payload.get("summary", {})),
    )


def _is_expired(candidate: Candidate, now: datetime) -> bool:
    if not candidate.deadline:
        return False
    return datetime.fromisoformat(candidate.deadline).astimezone(SHANGHAI) < now.astimezone(SHANGHAI)


def _summary(jobs: Iterable[Candidate], now: datetime) -> dict:
    active = list(jobs)
    near_deadline = 0
    for job in active:
        if job.deadline:
            deadline = datetime.fromisoformat(job.deadline).astimezone(SHANGHAI)
            if now <= deadline <= now + timedelta(days=7):
                near_deadline += 1
    today = now.astimezone(SHANGHAI).date()
    return {
        "active": len(active),
        "nearDeadline": near_deadline,
        "exactMatch": sum(job.match == "完全匹配" for job in active),
        "newToday": sum(
            bool(job.first_seen_at) and datetime.fromisoformat(job.first_seen_at).astimezone(SHANGHAI).date() == today
            for job in active
        ),
    }


def _sort_jobs(jobs: Iterable[Candidate]) -> tuple[Candidate, ...]:
    return tuple(
        sorted(
            jobs,
            key=lambda job: (
                PRIORITY_ORDER.get(job.priority, 9),
                -int(job.published_at.replace("-", "") or 0),
                job.company,
            ),
        )
    )


def merge_results(
    previous: RadarData,
    current_candidates: Iterable[Candidate | None],
    source_statuses: Mapping[str, str],
    now: datetime,
    *,
    coverage: dict | None = None,
    sources: Iterable[dict] | None = None,
) -> RadarData:
    now = now.astimezone(SHANGHAI)
    timestamp = now.isoformat()
    previous_active = {job.id: job for job in previous.jobs}
    active: dict[str, Candidate] = {}
    newly_expired: list[Candidate] = []

    for candidate in dedupe_candidates(current_candidates):
        prior = previous_active.get(candidate.id)
        if prior:
            candidate = replace(
                candidate,
                first_seen_at=prior.first_seen_at,
                change_summary="条件或来源已更新" if candidate != prior else prior.change_summary,
            )
        candidate = replace(candidate, last_confirmed_at=timestamp, status="可投")
        if _is_expired(candidate, now):
            newly_expired.append(replace(candidate, status="已截止"))
        else:
            active[candidate.id] = candidate

    for old in previous.jobs:
        if old.id in active or any(item.id == old.id for item in newly_expired):
            continue
        if _is_expired(old, now):
            newly_expired.append(replace(old, status="已截止", change_summary="报名截止"))
            continue
        statuses = [source_statuses.get(source_id, "unknown") for source_id in old.source_ids]
        if statuses and all(status in {"failed", "restricted"} for status in statuses):
            active[old.id] = replace(old, status="来源检查失败", change_summary="来源暂时无法核查")
        else:
            active[old.id] = replace(old, status="可投", last_confirmed_at=timestamp)

    history_by_id = {job.id: job for job in previous.history}
    for job in newly_expired:
        history_by_id[job.id] = job

    active_jobs = _sort_jobs(active.values())
    history_jobs = tuple(sorted(history_by_id.values(), key=lambda job: (job.published_at, job.company), reverse=True))
    source_rows = tuple(sources) if sources is not None else tuple(
        {"sourceId": source_id, "status": status} for source_id, status in sorted(source_statuses.items())
    )
    return RadarData(
        version=1,
        generated_at=timestamp,
        last_checked_at=timestamp,
        jobs=active_jobs,
        history=history_jobs,
        sources=source_rows,
        coverage=dict(coverage if coverage is not None else previous.coverage),
        summary=_summary(active_jobs, now),
    )


def _coverage(units: list[Unit], sources: list[Source], checked_sources: int) -> dict:
    return {
        "totalUnits": len(units),
        "direct": sum(unit.coverage == "direct" for unit in units),
        "inherited": sum(unit.coverage == "inherited" for unit in units),
        "restricted": sum(unit.coverage == "restricted" for unit in units),
        "totalSources": len(sources),
        "checkedSources": checked_sources,
    }


def run_pipeline(
    units: list[Unit],
    sources: list[Source],
    previous: RadarData,
    state: dict,
    now: datetime,
    *,
    fetcher: Callable[[Source, object], FetchResult] = fetch_source,
) -> tuple[RadarData, dict]:
    now = now.astimezone(SHANGHAI)
    timestamp = now.isoformat()
    previous_source_state = state.get("sources", {})

    def candidate_links(source: Source, result: FetchResult) -> list[str]:
        selected: list[str] = []
        for link in result.links:
            parsed = urlparse(link)
            allowed = any(
                parsed.netloc == domain or parsed.netloc.endswith(f".{domain}")
                for domain in source.official_domains
            )
            if not allowed:
                continue
            if not re.search(r"(?:job|recruit|career|zhaopin|notice|campus|content|art|zp|\.pdf$|\.docx?$|\.xlsx?$)", link, re.I):
                continue
            if link != source.url and link not in selected:
                selected.append(link)
            if len(selected) >= 12:
                break
        return selected

    def process(source: Source) -> tuple[Source, FetchResult, list[tuple[Source, FetchResult]]]:
        session = create_session()
        try:
            root_result = fetcher(source, session)
            details: list[tuple[Source, FetchResult]] = []
            if root_result.status == "success":
                for link in candidate_links(source, root_result):
                    detail_source = replace(source, url=link)
                    details.append((detail_source, fetcher(detail_source, session)))
            return source, root_result, details
        finally:
            session.close()

    workers = min(6, max(1, len(sources)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        processed = list(executor.map(process, sources))

    candidates: list[Candidate | None] = []
    source_rows: list[dict] = []
    next_source_state: dict[str, dict] = {}
    statuses: dict[str, str] = {}
    for source, result, detail_results in processed:
        statuses[source.source_id] = result.status
        old_state = previous_source_state.get(source.source_id, {})
        combined_text = "\n".join(
            item.text for item in (result, *(detail for _, detail in detail_results)) if item.status == "success"
        )
        fingerprint = content_fingerprint(combined_text) if result.status == "success" else old_state.get("fingerprint", "")
        changed = bool(result.status == "success" and fingerprint != old_state.get("fingerprint"))
        last_success_at = timestamp if result.status == "success" else old_state.get("lastSuccessAt")
        failure_count = 0 if result.status == "success" else int(old_state.get("failureCount", 0)) + 1
        next_source_state[source.source_id] = {
            "fingerprint": fingerprint,
            "status": result.status,
            "lastCheckedAt": timestamp,
            "lastSuccessAt": last_success_at,
            "failureCount": failure_count,
            "error": result.error,
        }
        source_rows.append(
            {
                "sourceId": source.source_id,
                "name": source.name,
                "url": source.url,
                "trust": source.trust,
                "status": result.status,
                "lastCheckedAt": timestamp,
                "lastSuccessAt": last_success_at,
                "failureCount": failure_count,
                "changed": changed,
                "error": result.error,
            }
        )
        if result.status == "success":
            candidates.append(parse_candidate(result.text, source, now, units))
            for detail_source, detail_result in detail_results:
                if detail_result.status == "success":
                    candidates.append(parse_candidate(detail_result.text, detail_source, now, units))

    radar = merge_results(
        previous,
        candidates,
        statuses,
        now,
        coverage=_coverage(units, sources, len(source_rows)),
        sources=source_rows,
    )
    return radar, {"version": 1, "lastRunAt": timestamp, "sources": next_source_state}


def radar_to_dict(radar: RadarData) -> dict:
    return {
        "version": radar.version,
        "generatedAt": radar.generated_at,
        "lastCheckedAt": radar.last_checked_at,
        "jobs": [_candidate_to_dict(job) for job in radar.jobs],
        "history": [_candidate_to_dict(job) for job in radar.history],
        "sources": list(radar.sources),
        "coverage": radar.coverage,
        "summary": radar.summary,
    }
