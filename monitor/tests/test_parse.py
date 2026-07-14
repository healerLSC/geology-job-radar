from datetime import datetime
from zoneinfo import ZoneInfo

from monitor.parse import dedupe_candidates, parse_candidate
from monitor.schema import Source, Unit


NOW = datetime(2026, 7, 14, 19, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def unit(unit_id, name, parent=None, group="中国石油"):
    return Unit(
        unit_id=unit_id,
        name=name,
        aliases=(),
        parent_unit_id=parent,
        group=group,
        sector="油气",
        level="二/三级单位" if parent else "集团/总局",
        priority="必投",
        source_ids=("official",) if not parent else (),
        coverage="direct" if not parent else "inherited",
    )


def source(source_id="official", trust="official", url="https://example.com/jobs/2027"):
    return Source(
        source_id=source_id,
        name="官方招聘",
        url=url,
        source_type="集团招聘平台",
        trust=trust,
        unit_ids=("cnpc",),
        mode="html",
        official_domains=("example.com",),
    )


TEXT = """
中国石油塔里木油田2027届高校毕业生校园招聘
发布日期：2026-07-13
报名截止时间：2026年7月20日12:00
招聘岗位：油气地质研究岗
学历要求：硕士研究生及以上
专业要求：地质学、矿物学、构造地质学
工作地点：新疆库尔勒
"""


def test_parse_candidate_extracts_core_fields_and_unit():
    units = [unit("cnpc", "中国石油"), unit("cnpc-tarim", "塔里木油田", "cnpc")]
    candidate = parse_candidate(TEXT, source(), NOW, units)
    assert candidate is not None
    assert candidate.company == "塔里木油田"
    assert candidate.parent == "中国石油"
    assert candidate.published_at == "2026-07-13"
    assert candidate.deadline == "2026-07-20T12:00:00+08:00"
    assert candidate.match == "完全匹配"
    assert candidate.education == "硕士研究生及以上"
    assert candidate.locations == ("新疆库尔勒",)
    assert candidate.registry_scope == "base"
    assert candidate.employer_type == "央企/中央单位"
    assert candidate.major_category == "geology"
    assert candidate.verification_status == "official"
    assert candidate.source_evidence[0]["url"] == "https://example.com/jobs/2027"
    assert candidate.fallback_used is False


def test_discovery_source_collects_unknown_engineering_employer():
    discovery_source = Source(
        source_id="global",
        name="权威招聘平台",
        url="https://example.com/jobs/unknown",
        source_type="权威招聘平台",
        trust="authoritative",
        unit_ids=(),
        mode="html",
        official_domains=("example.com",),
        tier="l2",
        role="discovery",
        follow_domains=("example.com",),
    )
    text = """
星海矿业有限公司2027届校园招聘
发布日期：2026-07-14
招聘岗位：矿山地质岗
学历要求：硕士研究生
专业要求：地质工程、资源勘查工程
工作地点：青海
"""
    candidate = parse_candidate(text, discovery_source, NOW, [])
    assert candidate is not None
    assert candidate.company == "星海矿业有限公司"
    assert candidate.match == "工程类限定"
    assert candidate.registry_scope == "discovered"
    assert candidate.employer_type == "其他企业"
    assert candidate.major_category == "engineering-only"
    assert candidate.verification_status == "authoritative"
    assert candidate.fallback_used is True


def test_non_target_or_non_geology_text_is_rejected():
    units = [unit("cnpc", "中国石油")]
    assert parse_candidate("2026届校园招聘 地质学", source(), NOW, units) is None
    assert parse_candidate("2027届校园招聘 会计学", source(), NOW, units) is None


def test_duplicates_merge_sources_and_prefer_official():
    units = [unit("cnpc", "中国石油"), unit("cnpc-tarim", "塔里木油田", "cnpc")]
    official = parse_candidate(TEXT, source(), NOW, units)
    mirror = parse_candidate(
        TEXT,
        source("mirror", "authoritative", "https://jobs.example.edu/mirror"),
        NOW,
        units,
    )
    merged = dedupe_candidates([mirror, official])
    assert len(merged) == 1
    assert merged[0].official_url == "https://example.com/jobs/2027"
    assert merged[0].mirror_urls == ("https://jobs.example.edu/mirror",)
    assert len(merged[0].source_evidence) == 2
    assert merged[0].verification_status == "official"
    assert merged[0].fallback_used is False


def test_authoritative_confirmation_promotes_same_l3_lead():
    units = [unit("cnpc", "中国石油"), unit("cnpc-tarim", "塔里木油田", "cnpc")]
    lead_source = Source(
        source_id="lead",
        name="高校就业网转载",
        url="https://career.example.edu/notice",
        source_type="高校就业网转载",
        trust="clue",
        unit_ids=("cnpc",),
        mode="html",
        official_domains=("career.example.edu",),
        tier="l3",
        role="fallback",
        follow_domains=("career.example.edu",),
    )
    authority_source = Source(
        source_id="authority",
        name="国家就业平台",
        url="https://jobs.gov.example/notice",
        source_type="权威招聘平台",
        trust="authoritative",
        unit_ids=("cnpc",),
        mode="html",
        official_domains=("jobs.gov.example",),
        tier="l2",
        role="fallback",
        follow_domains=("jobs.gov.example",),
    )
    lead = parse_candidate(TEXT, lead_source, NOW, units)
    authority = parse_candidate(TEXT, authority_source, NOW, units)
    assert lead is not None and lead.status == "待核验线索"
    merged = dedupe_candidates([lead, authority])
    assert len(merged) == 1
    assert merged[0].status == "可投"
    assert merged[0].verification_status == "authoritative"
    assert merged[0].fallback_used is True
    assert len(merged[0].source_evidence) == 2
