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
