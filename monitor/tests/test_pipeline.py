from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from monitor.fetch import FetchResult
from monitor.pipeline import RadarData, load_radar, merge_results, radar_to_dict, run_pipeline
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


def test_atomic_json_writer_replaces_target(tmp_path):
    target = tmp_path / "radar.json"
    target.write_text('{"old": true}', encoding="utf-8")
    write_json_atomic(target, {"version": 1, "jobs": []})
    assert target.read_text(encoding="utf-8").startswith("{\n")
    assert not (tmp_path / "radar.json.tmp").exists()
