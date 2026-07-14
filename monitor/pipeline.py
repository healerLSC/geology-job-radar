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
MATCH_ORDER = {"完全匹配": 0, "大类可能匹配": 1, "工程类限定": 2, "需咨询": 3}
TRUST_ORDER = {"official": 0, "authoritative": 1, "clue": 2}
ROLE_MARKERS = (
    "地质", "勘察", "勘探", "物探", "资源", "矿山", "油气", "业务", "研究", "实习",
)


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
    rule_id = row.get("ruleId", "major.manual_verified")
    match = row["match"]
    if match == "可能匹配":
        match = "大类可能匹配"
    if match == "需咨询" and rule_id == "major.engineering_only":
        match = "工程类限定"
    major_category = row.get("majorCategory") or {
        "major.exact": "geology",
        "major.related": "broad-geoscience",
        "major.engineering_only": "engineering-only",
    }.get(rule_id, "consult")
    verification_status = row.get("verificationStatus") or {
        "official": "official",
        "authoritative": "authoritative",
        "clue": "lead",
    }.get(row.get("sourceTrust", "authoritative"), "lead")
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
        match=match,
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
        rule_id=rule_id,
        change_summary=row.get("changeSummary", "历史数据迁移"),
        registry_scope=row.get("registryScope", "base"),
        employer_type=row.get("employerType", "基础名册单位"),
        major_category=major_category,
        verification_status=verification_status,
        source_evidence=tuple(row.get("sourceEvidence", ())),
        fallback_used=bool(row.get("fallbackUsed", verification_status == "authoritative")),
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
        "registryScope": candidate.registry_scope,
        "employerType": candidate.employer_type,
        "majorCategory": candidate.major_category,
        "verificationStatus": candidate.verification_status,
        "sourceEvidence": list(candidate.source_evidence),
        "fallbackUsed": candidate.fallback_used,
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
    active = [job for job in jobs if job.status != "待核验线索"]
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


def _same_cross_source_opportunity(current: Candidate, prior: Candidate) -> bool:
    if current.company != prior.company:
        return False
    try:
        day_gap = abs(
            (datetime.fromisoformat(current.published_at) - datetime.fromisoformat(prior.published_at)).days
        )
    except ValueError:
        return False
    if day_gap > 14:
        return False
    current_text = " ".join((current.batch, *current.roles))
    prior_text = " ".join((prior.batch, *prior.roles))
    shared_markers = {
        marker for marker in ROLE_MARKERS if marker in current_text and marker in prior_text
    }
    return len(shared_markers) >= 2


def _merge_cross_source_opportunity(current: Candidate, prior: Candidate) -> Candidate:
    primary = min(
        (current, prior),
        key=lambda item: (
            MATCH_ORDER.get(item.match, 9),
            TRUST_ORDER.get(item.source_trust, 9),
        ),
    )
    source_ids = tuple(dict.fromkeys((*prior.source_ids, *current.source_ids)))
    evidence: list[dict] = []
    evidence_keys: set[tuple[str, str]] = set()
    for row in (*prior.source_evidence, *current.source_evidence):
        key = (str(row.get("sourceId", "")), str(row.get("url", "")))
        if key not in evidence_keys:
            evidence_keys.add(key)
            evidence.append(row)
    mirror_urls = tuple(
        dict.fromkeys(
            url
            for url in (
                *prior.mirror_urls,
                prior.official_url,
                *current.mirror_urls,
                current.official_url,
            )
            if url != primary.official_url
        )
    )
    return replace(
        primary,
        id=prior.id,
        first_seen_at=prior.first_seen_at,
        source_ids=source_ids,
        source_evidence=tuple(evidence),
        mirror_urls=mirror_urls,
        fallback_used=prior.fallback_used or current.fallback_used,
        change_summary="新增权威来源佐证",
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
    consumed_previous_ids: set[str] = set()

    for candidate in dedupe_candidates(current_candidates):
        prior = previous_active.get(candidate.id)
        cross_source_prior = next(
            (
                item
                for item in previous_active.values()
                if item.id != candidate.id and _same_cross_source_opportunity(candidate, item)
            ),
            None,
        )
        if cross_source_prior is not None:
            if prior is not None:
                consumed_previous_ids.add(prior.id)
            prior = cross_source_prior
            candidate = _merge_cross_source_opportunity(candidate, prior)
        if prior:
            candidate = replace(
                candidate,
                first_seen_at=prior.first_seen_at,
                change_summary="条件或来源已更新" if candidate != prior else prior.change_summary,
            )
        candidate = replace(
            candidate,
            last_confirmed_at=timestamp,
            status="待核验线索" if candidate.verification_status == "lead" else "可投",
        )
        if _is_expired(candidate, now):
            newly_expired.append(replace(candidate, status="已截止"))
        else:
            active[candidate.id] = candidate

    for old in previous.jobs:
        if old.id in active or old.id in consumed_previous_ids or any(item.id == old.id for item in newly_expired):
            continue
        if _is_expired(old, now):
            newly_expired.append(replace(old, status="已截止", change_summary="报名截止"))
            continue
        statuses = [source_statuses.get(source_id, "unknown") for source_id in old.source_ids]
        if statuses and all(status in {"failed", "restricted"} for status in statuses):
            active[old.id] = replace(old, status="来源检查失败", change_summary="来源暂时无法核查")
        else:
            status = "待核验线索" if old.verification_status == "lead" else "可投"
            active[old.id] = replace(old, status=status, last_confirmed_at=timestamp)

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


def calculate_unit_health(
    units: list[Unit],
    sources: list[Source],
    source_statuses: Mapping[str, str],
) -> dict[str, str]:
    units_by_id = {unit.unit_id: unit for unit in units}
    sources_by_id = {source.source_id: source for source in sources}
    health: dict[str, str] = {}

    for unit in units:
        lineage: list[Unit] = [unit]
        current = unit
        while current.parent_unit_id and current.parent_unit_id in units_by_id:
            current = units_by_id[current.parent_unit_id]
            lineage.append(current)
        lineage_ids = {item.unit_id for item in lineage}
        source_ids = {source_id for item in lineage for source_id in item.source_ids}
        for source in sources:
            if lineage_ids.intersection(source.unit_ids):
                source_ids.add(source.source_id)

        available_tiers = {
            sources_by_id[source_id].tier
            for source_id in source_ids
            if source_id in sources_by_id and source_statuses.get(source_id) == "success"
        }
        if "l1" in available_tiers:
            health[unit.unit_id] = "primary"
        elif "l2" in available_tiers:
            health[unit.unit_id] = "fallback"
        elif "l3" in available_tiers:
            health[unit.unit_id] = "leads"
        else:
            health[unit.unit_id] = "unavailable"
    return health


def _coverage(
    units: list[Unit],
    sources: list[Source],
    checked_sources: int,
    source_statuses: Mapping[str, str],
) -> dict:
    unit_health = calculate_unit_health(units, sources, source_statuses)
    return {
        "totalUnits": len(units),
        "direct": sum(unit.coverage == "direct" for unit in units),
        "inherited": sum(unit.coverage == "inherited" for unit in units),
        "restricted": sum(unit.coverage == "restricted" for unit in units),
        "totalSources": len(sources),
        "checkedSources": checked_sources,
        "unitHealth": {
            status: sum(value == status for value in unit_health.values())
            for status in ("primary", "fallback", "leads", "unavailable")
        },
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
        follow_domains = source.follow_domains or source.official_domains
        for link in result.links:
            parsed = urlparse(link)
            allowed = any(
                parsed.netloc == domain or parsed.netloc.endswith(f".{domain}")
                for domain in follow_domains
            )
            if not allowed:
                continue
            is_public_account = parsed.netloc == "mp.weixin.qq.com" and parsed.path.startswith("/s")
            if not is_public_account and not re.search(
                r"(?:job|recruit|career|zhaopin|notice|campus|content|art|zp|\.pdf$|\.docx?$|\.xlsx?$)",
                link,
                re.I,
            ):
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
            (
                *(item.text for item in (result, *(detail for _, detail in detail_results)) if item.status == "success"),
                *(text for _, text in result.documents),
            )
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
                "tier": source.tier,
                "role": source.role,
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
            for document_url, document_text in result.documents:
                candidates.append(parse_candidate(document_text, replace(source, url=document_url), now, units))
            for detail_source, detail_result in detail_results:
                if detail_result.status == "success":
                    candidates.append(parse_candidate(detail_result.text, detail_source, now, units))

    radar = merge_results(
        previous,
        candidates,
        statuses,
        now,
        coverage=_coverage(units, sources, len(source_rows), statuses),
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
