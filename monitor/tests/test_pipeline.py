from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from monitor.fetch import FetchResult
from monitor.pipeline import (
    RadarData,
    calculate_unit_health,
    load_radar,
    merge_results,
    radar_to_dict,
    run_pipeline,
)
from monitor.schema import Source, Unit
from monitor.run import write_json_atomic


NOW = datetime(2026, 7, 21, 19, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
PREVIOUS = Path("monitor/tests/fixtures/previous-radar.json")


def test_failed_source_preserves_last_verified_job():
    previous = load_radar(PREVIOUS)
    merged = merge_results(previous, [], {"official-a": "failed", "official-b": "success"}, NOW)
    retained = next(job for job in merged.jobs if job.id == "no-deadline-job")
    assert retained.status == "来源检查失败"
    assert retained.company == "塔里木油田"


def test_expired_job_moves_to_history():
    previous = load_radar(PREVIOUS)
    merged = merge_results(previous, [], {"official-a": "success", "official-b": "success"}, NOW)
    assert all(job.id != "expired-job" for job in merged.jobs)
    expired = next(job for job in merged.history if job.id == "expired-job")
    assert expired.status == "已截止"


def test_cross_source_versions_of_same_opportunity_are_merged():
    fixture = load_radar(PREVIOUS)
    curated = next(job for job in fixture.jobs if job.company == "广岩国际投资有限责任公司")
    curated = replace(
        curated,
        id="curated-opportunity",
        deadline="2026-09-30T23:59:00+08:00",
        source_evidence=(
            {"sourceId": "official-b", "url": curated.official_url, "tier": "l2"},
        ),
    )
    api_version = replace(
        curated,
        id="api-opportunity",
        batch="2027届校园招聘",
        published_at="2026-07-11",
        roles=("业务和研究类岗位(实习)",),
        match="大类可能匹配",
        official_url="https://authority.example/job/208522992576103181",
        source_ids=("authority-api",),
        source_evidence=(
            {
                "sourceId": "authority-api",
                "url": "https://authority.example/job/208522992576103181",
                "tier": "l2",
            },
        ),
        fallback_used=True,
    )
    previous = RadarData(
        1,
        fixture.generated_at,
        fixture.last_checked_at,
        (curated, replace(api_version, change_summary="上次接口发现")),
        (),
        (),
        {},
        {},
    )

    merged = merge_results(
        previous,
        [api_version],
        {"official-b": "failed", "authority-api": "success"},
        datetime(2026, 7, 14, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    assert len(merged.jobs) == 1
    assert merged.jobs[0].id == "curated-opportunity"
    assert set(merged.jobs[0].source_ids) == {"official-b", "authority-api"}
    assert "https://authority.example/job/208522992576103181" in merged.jobs[0].mirror_urls


def test_serialized_radar_has_stable_public_contract():
    previous = load_radar(PREVIOUS)
    merged = merge_results(previous, [], {"official-a": "success", "official-b": "success"}, NOW)
    payload = radar_to_dict(merged)
    assert payload["version"] == 1
    assert payload["lastCheckedAt"] == "2026-07-21T19:00:00+08:00"
    assert set(payload) == {
        "version", "generatedAt", "lastCheckedAt", "jobs", "history", "sources", "coverage", "summary"
    }
    assert payload["summary"]["active"] == len(payload["jobs"])


def test_run_pipeline_discovers_candidate_and_records_fingerprint():
    empty = RadarData(1, NOW.isoformat(), NOW.isoformat(), (), (), (), {}, {})
    units = [
        Unit("cnpc", "中国石油", (), None, "中国石油", "油气", "集团/总局", "必投", ("official-a",), "direct"),
        Unit("cnpc-tarim", "塔里木油田", (), "cnpc", "中国石油", "油气", "二/三级单位", "必投", (), "inherited"),
    ]
    sources = [
        Source("official-a", "官方招聘", "https://example.com/jobs", "集团招聘平台", "official", ("cnpc",), "html", ("example.com",))
    ]
    text = """
    中国石油塔里木油田2027届高校毕业生校园招聘
    发布日期：2026-07-13
    专业要求：地质学
    学历要求：硕士研究生
    """

    def fake_fetcher(source, session):
        return FetchResult(source.source_id, "success", source.url, text, (), "text/html")

    radar, state = run_pipeline(units, sources, empty, {}, NOW, fetcher=fake_fetcher)
    assert radar.jobs[0].company == "塔里木油田"
    assert radar.sources[0]["status"] == "success"
    assert radar.coverage["totalSources"] == 1
    assert radar.coverage["checkedSources"] == 1
    assert state["sources"]["official-a"]["fingerprint"]


def test_run_pipeline_follows_recruitment_detail_link():
    empty = RadarData(1, NOW.isoformat(), NOW.isoformat(), (), (), (), {}, {})
    units = [
        Unit("cnpc", "中国石油", (), None, "中国石油", "油气", "集团/总局", "必投", ("official-a",), "direct"),
        Unit("cnpc-tarim", "塔里木油田", (), "cnpc", "中国石油", "油气", "二/三级单位", "必投", (), "inherited"),
    ]
    sources = [
        Source("official-a", "官方招聘", "https://example.com/careers", "集团招聘平台", "official", ("cnpc",), "html", ("example.com",))
    ]
    detail_text = "塔里木油田2027届高校毕业生校园招聘\n专业要求：地质学\n学历要求：硕士研究生"

    def fake_fetcher(source, session):
        if source.url.endswith("/careers"):
            return FetchResult(
                source.source_id,
                "success",
                source.url,
                "招聘公告列表",
                ("https://example.com/notice/2027-campus.html",),
                "text/html",
            )
        return FetchResult(source.source_id, "success", source.url, detail_text, (), "text/html")

    radar, _ = run_pipeline(units, sources, empty, {}, NOW, fetcher=fake_fetcher)
    assert radar.jobs[0].official_url == "https://example.com/notice/2027-campus.html"


def test_run_pipeline_parses_separate_api_documents_as_discovered_employers():
    empty = RadarData(1, NOW.isoformat(), NOW.isoformat(), (), (), (), {}, {})
    units = [
        Unit("cnpc", "中国石油", (), None, "中国石油", "油气", "集团/总局", "必投", (), "direct"),
    ]
    source = Source(
        "authority-api",
        "权威招聘平台",
        "https://authority.example/jobs",
        "权威招聘平台",
        "authoritative",
        (),
        "iguopin-api",
        ("authority.example",),
        tier="l2",
        role="discovery",
        query_terms=("地质工程",),
    )
    document = """星海矿业有限公司2027届校园招聘
发布日期：2026-07-14
招聘岗位：矿山地质岗
学历要求：硕士
专业要求：地质工程、资源勘查工程
工作地点：青海-西宁
岗位详情：负责矿山地质技术工作"""

    def fake_fetcher(source, session):
        return FetchResult(
            source.source_id,
            "success",
            source.url,
            "权威平台结构化岗位接口",
            (),
            "application/json",
            documents=(("https://authority.example/job/2027-job", document),),
        )

    radar, _ = run_pipeline(units, [source], empty, {}, NOW, fetcher=fake_fetcher)
    assert len(radar.jobs) == 1
    assert radar.jobs[0].company == "星海矿业有限公司"
    assert radar.jobs[0].registry_scope == "discovered"
    assert radar.jobs[0].match == "工程类限定"
    assert radar.jobs[0].locations == ("青海-西宁",)
    assert radar.jobs[0].official_url == "https://authority.example/job/2027-job"


def test_atomic_json_writer_replaces_target(tmp_path):
    target = tmp_path / "radar.json"
    target.write_text('{"old": true}', encoding="utf-8")
    write_json_atomic(target, {"version": 1, "jobs": []})
    assert target.read_text(encoding="utf-8").startswith("{\n")
    assert not (tmp_path / "radar.json.tmp").exists()


def test_failed_primary_with_successful_l2_is_fallback_healthy():
    units = [
        Unit("cnpc", "中国石油", (), None, "中国石油", "油气", "集团/总局", "必投", ("official-a",), "direct"),
        Unit("cnpc-tarim", "塔里木油田", (), "cnpc", "中国石油", "油气", "二/三级单位", "必投", (), "inherited"),
    ]
    sources = [
        Source("official-a", "官方招聘", "https://official.example/jobs", "集团官网", "official", ("cnpc",), "html", ("official.example",)),
        Source(
            "authority-a",
            "权威平台",
            "https://authority.example/jobs",
            "权威招聘平台",
            "authoritative",
            ("cnpc",),
            "html",
            ("authority.example",),
            tier="l2",
            role="fallback",
            follow_domains=("authority.example",),
        ),
    ]
    health = calculate_unit_health(
        units,
        sources,
        {"official-a": "failed", "authority-a": "success"},
    )
    assert health["cnpc"] == "fallback"
    assert health["cnpc-tarim"] == "fallback"


def test_run_pipeline_reports_unit_health_counts():
    empty = RadarData(1, NOW.isoformat(), NOW.isoformat(), (), (), (), {}, {})
    units = [
        Unit("cnpc", "中国石油", (), None, "中国石油", "油气", "集团/总局", "必投", ("official-a",), "direct"),
    ]
    sources = [
        Source("official-a", "官方招聘", "https://example.com/jobs", "集团官网", "official", ("cnpc",), "html", ("example.com",)),
    ]

    def fake_fetcher(source, session):
        return FetchResult(source.source_id, "success", source.url, "没有新增招聘", (), "text/html")

    radar, _ = run_pipeline(units, sources, empty, {}, NOW, fetcher=fake_fetcher)
    assert radar.coverage["unitHealth"] == {
        "primary": 1,
        "fallback": 0,
        "leads": 0,
        "unavailable": 0,
    }
