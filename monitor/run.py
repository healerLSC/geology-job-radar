import argparse
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from monitor.fetch import FetchResult, html_links, html_to_text
from monitor.pipeline import RadarData, load_radar, radar_to_dict, run_pipeline
from monitor.schema import Source, load_sources, load_units, validate_registry


ROOT = Path(__file__).parents[1]
SHANGHAI = ZoneInfo("Asia/Shanghai")


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _empty_radar(now: datetime) -> RadarData:
    timestamp = now.astimezone(SHANGHAI).isoformat()
    return RadarData(1, timestamp, timestamp, (), (), (), {}, {})


def _fixture_fetcher(directory: Path):
    def fetch(source: Source, session: object) -> FetchResult:
        if source.mode == "restricted":
            return FetchResult(source.source_id, "restricted", source.url, "", (), "", "来源配置为受限")
        fixture = directory / f"{source.source_id}.html"
        if not fixture.exists():
            return FetchResult(source.source_id, "failed", source.url, "", (), "", "离线样例缺失")
        html = fixture.read_text(encoding="utf-8")
        return FetchResult(
            source.source_id,
            "success",
            source.url,
            html_to_text(html),
            html_links(html, source.url),
            "text/html",
        )

    return fetch


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the independent geology recruitment monitor")
    parser.add_argument("--now", help="ISO-8601 time used for deterministic runs")
    parser.add_argument("--offline-fixtures", type=Path, help="Read <source_id>.html fixtures instead of the network")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(SHANGHAI)
    if now.tzinfo is None:
        now = now.replace(tzinfo=SHANGHAI)
    units = load_units(ROOT / "monitor/units.json")
    sources = load_sources(ROOT / "monitor/sources.json")
    errors = validate_registry(units, sources)
    if errors:
        raise SystemExit("监控名册校验失败：\n" + "\n".join(errors))

    radar_path = ROOT / "data/radar.json"
    state_path = ROOT / "monitor/state.json"
    previous = load_radar(radar_path) if radar_path.exists() else _empty_radar(now)
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    options = {}
    if args.offline_fixtures:
        options["fetcher"] = _fixture_fetcher(args.offline_fixtures)
    radar, next_state = run_pipeline(units, sources, previous, state, now, **options)
    write_json_atomic(radar_path, radar_to_dict(radar))
    write_json_atomic(state_path, next_state)
    print(
        f"checked={len(sources)} active={radar.summary['active']} "
        f"history={len(radar.history)} failed={sum(row['status'] != 'success' for row in radar.sources)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
