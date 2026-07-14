from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import re
from typing import Iterable
from zoneinfo import ZoneInfo

from monitor.discovery import resolve_employer
from monitor.fingerprint import normalize_text
from monitor.match import classify_major, has_geology_signal, is_target_recruitment
from monitor.schema import Source, Unit


SHANGHAI = ZoneInfo("Asia/Shanghai")
TRUST_RANK = {"official": 0, "authoritative": 1, "clue": 2}


@dataclass(frozen=True)
class Candidate:
    id: str
    company: str
    parent: str
    batch: str
    published_at: str
    deadline: str | None
    deadline_label: str
    roles: tuple[str, ...]
    education: str
    majors: str
    locations: tuple[str, ...]
    priority: str
    match: str
    sector: str
    conditions: tuple[str, ...]
    assessment: str
    official_url: str
    mirror_urls: tuple[str, ...]
    source_type: str
    source_trust: str
    source_ids: tuple[str, ...]
    first_seen_at: str
    last_confirmed_at: str
    status: str
    evidence: str
    rule_id: str
    change_summary: str
    registry_scope: str
    employer_type: str
    major_category: str
    verification_status: str
    source_evidence: tuple[dict, ...]
    fallback_used: bool


def _date_match(text: str, labels: str) -> tuple[str, tuple[int, int] | None] | None:
    pattern = re.compile(
        rf"(?:{labels})\s*[：:]?\s*(\d{{4}})[年/.-](\d{{1,2}})[月/.-](\d{{1,2}})日?"
        rf"(?:\s*(\d{{1,2}})(?:[时:：](\d{{1,2}}))?分?)?"
    )
    match = pattern.search(text)
    if not match:
        return None
    year, month, day = (int(match.group(index)) for index in range(1, 4))
    date = f"{year:04d}-{month:02d}-{day:02d}"
    if not match.group(4):
        return date, None
    return date, (int(match.group(4)), int(match.group(5) or 0))


def _field(text: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    boundary = (
        r"(?=\n\s*(?:发布日期|发布时间|报名截止时间|截止时间|招聘岗位|岗位名称|"
        r"学历要求|学历|专业要求|专业|工作地点|地点|岗位详情|岗位职责|工作职责|"
        r"任职要求|任职资格|应聘条件)\s*[：:]|\Z)"
    )
    match = re.search(rf"(?:{label_pattern})\s*[：:]\s*(.+?){boundary}", text, flags=re.S)
    return normalize_text(match.group(1)) if match else ""


def _batch(text: str) -> str:
    first_line = next((normalize_text(line) for line in text.splitlines() if line.strip()), "")
    match = re.search(r"2027\s*届.{0,28}?(?:校园招聘|高校毕业生招聘|暑期实习|实习生招聘)", first_line)
    return match.group(0) if match else "2027届高校毕业生招聘"


def _split_values(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in re.split(r"[、,，;/；]", value) if part.strip())


def parse_candidate(
    text: str,
    source: Source,
    discovered_at: datetime,
    units: list[Unit],
) -> Candidate | None:
    if not is_target_recruitment(text) or not has_geology_signal(text):
        return None
    resolved = resolve_employer(text, units, source)
    if resolved is None:
        return None
    unit = resolved.unit

    decision = classify_major(text)
    published = _date_match(text, "发布日期|发布时间|公告日期")
    published_at = published[0] if published else discovered_at.astimezone(SHANGHAI).date().isoformat()
    deadline_value = _date_match(text, "报名截止时间|网申截止时间|截止时间|报名截止|截止日期")
    deadline: str | None = None
    deadline_label = "官方未注明"
    if deadline_value:
        deadline_date, time_value = deadline_value
        if time_value:
            hour, minute = time_value
            deadline = datetime.fromisoformat(f"{deadline_date}T{hour:02d}:{minute:02d}:00").replace(tzinfo=SHANGHAI).isoformat()
            deadline_label = f"{deadline_date} {hour:02d}:{minute:02d}"
        else:
            deadline = datetime.fromisoformat(f"{deadline_date}T23:59:00").replace(tzinfo=SHANGHAI).isoformat()
            deadline_label = deadline_date

    unit_by_id = {item.unit_id: item for item in units}
    parent = unit_by_id.get(unit.parent_unit_id) if unit.parent_unit_id else None
    parent_name = (
        resolved.employer_type
        if resolved.registry_scope == "discovered"
        else parent.name if parent else unit.group
    )
    batch = _batch(text)
    stable_key = normalize_text(f"{unit.name}|{batch}|{published_at}")
    candidate_id = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:16]
    roles_value = _field(text, ("招聘岗位", "岗位名称", "地质相关岗位"))
    majors = _field(text, ("专业要求", "需求专业", "专业")) or decision.evidence
    education = _field(text, ("学历要求", "学历")) or "官方正文未解析"
    locations_value = _field(text, ("工作地点", "地点"))
    timestamp = discovered_at.astimezone(SHANGHAI).isoformat()
    major_category = {
        "major.exact": "geology",
        "major.related": "broad-geoscience",
        "major.engineering_only": "engineering-only",
    }.get(decision.rule_id, "consult")
    verification_status = {
        "l1": "official",
        "l2": "authoritative",
        "l3": "lead",
    }.get(source.tier, "lead")

    return Candidate(
        id=candidate_id,
        company=unit.name,
        parent=parent_name,
        batch=batch,
        published_at=published_at,
        deadline=deadline,
        deadline_label=deadline_label,
        roles=_split_values(roles_value) or ("地质相关岗位（以公告原文为准）",),
        education=education,
        majors=majors,
        locations=_split_values(locations_value) or ("官方未注明",),
        priority=decision.priority if decision.level != "完全匹配" else unit.priority,
        match=decision.level,
        sector=unit.sector,
        conditions=(),
        assessment=f"命中“{decision.evidence}”；按规则 {decision.rule_id} 判定。",
        official_url=source.url,
        mirror_urls=(),
        source_type=source.source_type,
        source_trust=source.trust,
        source_ids=(source.source_id,),
        first_seen_at=timestamp,
        last_confirmed_at=timestamp,
        status="待核验线索" if verification_status == "lead" else "可投",
        evidence=decision.evidence,
        rule_id=decision.rule_id,
        change_summary="首次发现",
        registry_scope=resolved.registry_scope,
        employer_type=resolved.employer_type,
        major_category=major_category,
        verification_status=verification_status,
        source_evidence=(
            {
                "sourceId": source.source_id,
                "name": source.name,
                "url": source.url,
                "tier": source.tier,
                "trust": source.trust,
                "discoveredAt": timestamp,
            },
        ),
        fallback_used=source.tier == "l2",
    )


def dedupe_candidates(candidates: Iterable[Candidate | None]) -> list[Candidate]:
    grouped: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        if candidate is not None:
            grouped.setdefault(candidate.id, []).append(candidate)

    merged: list[Candidate] = []
    for items in grouped.values():
        ordered = sorted(items, key=lambda item: TRUST_RANK.get(item.source_trust, 9))
        primary = ordered[0]
        mirrors = tuple(
            dict.fromkeys(
                url
                for item in ordered
                for url in (*item.mirror_urls, item.official_url)
                if url != primary.official_url
            )
        )
        source_ids = tuple(dict.fromkeys(source_id for item in ordered for source_id in item.source_ids))
        evidence: list[dict] = []
        seen_evidence: set[tuple[str, str]] = set()
        for item in ordered:
            for row in item.source_evidence:
                key = (str(row.get("sourceId", "")), str(row.get("url", "")))
                if key in seen_evidence:
                    continue
                seen_evidence.add(key)
                evidence.append(row)
        merged.append(
            replace(
                primary,
                mirror_urls=mirrors,
                source_ids=source_ids,
                source_evidence=tuple(evidence),
            )
        )
    return sorted(merged, key=lambda item: (item.published_at, item.company), reverse=True)
