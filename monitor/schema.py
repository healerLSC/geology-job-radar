from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Unit:
    unit_id: str
    name: str
    aliases: tuple[str, ...]
    parent_unit_id: str | None
    group: str
    sector: str
    level: str
    priority: str
    source_ids: tuple[str, ...]
    coverage: str


@dataclass(frozen=True)
class Source:
    source_id: str
    name: str
    url: str
    source_type: str
    trust: str
    unit_ids: tuple[str, ...]
    mode: str
    official_domains: tuple[str, ...]


def load_units(path: Path) -> list[Unit]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    units: list[Unit] = []
    for group in payload["groups"]:
        group_id = group["unit_id"]
        group_name = group["name"]
        group_sources = tuple(group.get("source_ids", ()))
        units.append(
            Unit(
                unit_id=group_id,
                name=group_name,
                aliases=tuple(group.get("aliases", ())),
                parent_unit_id=None,
                group=group_name,
                sector=group["sector"],
                level="集团/总局",
                priority=group.get("priority", "保底"),
                source_ids=group_sources,
                coverage="direct" if group_sources else "restricted",
            )
        )
        for member in group.get("members", ()):
            sources = tuple(member.get("source_ids", ()))
            units.append(
                Unit(
                    unit_id=member["unit_id"],
                    name=member["name"],
                    aliases=tuple(member.get("aliases", ())),
                    parent_unit_id=group_id,
                    group=group_name,
                    sector=member.get("sector", group["sector"]),
                    level=member.get("level", "二/三级单位"),
                    priority=member.get("priority", group.get("priority", "保底")),
                    source_ids=sources,
                    coverage="direct" if sources else member.get("coverage", "inherited"),
                )
            )
    return units


def load_sources(path: Path) -> list[Source]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [
        Source(
            source_id=row["source_id"],
            name=row["name"],
            url=row["url"],
            source_type=row["source_type"],
            trust=row["trust"],
            unit_ids=tuple(row.get("unit_ids", ())),
            mode=row["mode"],
            official_domains=tuple(row.get("official_domains", ())),
        )
        for row in rows
    ]


def validate_registry(units: list[Unit], sources: list[Source]) -> list[str]:
    errors: list[str] = []
    unit_ids = [unit.unit_id for unit in units]
    names = [unit.name for unit in units]
    unit_id_set = set(unit_ids)
    source_ids = [source.source_id for source in sources]
    source_id_set = set(source_ids)

    if len(unit_ids) != len(unit_id_set):
        errors.append("duplicate unit_id")
    if len(names) != len(set(names)):
        errors.append("duplicate unit name")
    if len(source_ids) != len(source_id_set):
        errors.append("duplicate source_id")

    for unit in units:
        if unit.parent_unit_id and unit.parent_unit_id not in unit_id_set:
            errors.append(f"{unit.unit_id}: missing parent {unit.parent_unit_id}")
        missing = set(unit.source_ids) - source_id_set
        if missing:
            errors.append(f"{unit.unit_id}: missing sources {sorted(missing)}")
        if not unit.source_ids and not unit.parent_unit_id:
            errors.append(f"{unit.unit_id}: no coverage path")

    for source in sources:
        parsed = urlparse(source.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{source.source_id}: invalid URL")
        missing_units = set(source.unit_ids) - unit_id_set
        if missing_units:
            errors.append(f"{source.source_id}: missing units {sorted(missing_units)}")
        if source.trust == "official" and not source.official_domains:
            errors.append(f"{source.source_id}: official source lacks domain allowlist")
    return errors
