from dataclasses import dataclass
import hashlib
import re

from monitor.schema import Source, Unit


CENTRAL_GROUPS = {
    "cnpc",
    "sinopec",
    "cnooc",
    "chn-energy",
    "chinacoal",
    "ccgc",
    "cmgb",
    "ccgmb",
    "minmetals",
    "china-gold",
    "chinalco",
    "cnmc",
    "pipechina",
    "powerchina",
    "energy-china",
    "crec",
    "crcc",
    "cccc",
    "cscec",
    "china-aneng",
}
PROVINCIAL_GROUPS = {
    "shandong-energy",
    "shccig",
    "jinneng",
    "shanxi-coking",
    "huaihe-energy",
    "jizhong-energy",
    "kailuan",
    "henan-energy",
    "longmay",
    "shandong-gold",
    "jiangxi-copper",
    "yunnan-copper",
    "yunnan-tin",
    "baogang",
    "steel-mining",
    "jiugang",
    "zhaojin",
}
EMPLOYER_PATTERN = re.compile(
    r"(?P<name>[\u4e00-\u9fffA-Za-z0-9（）()·]{2,60}?(?:有限责任公司|股份有限公司|"
    r"有限公司|集团|研究总院|研究院|勘查院|地质队|事业单位))"
    r"(?:2027\s*届|2027年).{0,30}?(?:招聘|校招|实习)"
)
GENERIC_NAMES = {
    "高校毕业生招聘信息汇总",
    "中央企业招聘信息汇总",
    "事业单位",
}


@dataclass(frozen=True)
class ResolvedEmployer:
    unit: Unit
    registry_scope: str
    employer_type: str


def _root_unit(unit: Unit, units: list[Unit]) -> Unit:
    by_id = {item.unit_id: item for item in units}
    current = unit
    while current.parent_unit_id and current.parent_unit_id in by_id:
        current = by_id[current.parent_unit_id]
    return current


def _known_employer_type(unit: Unit, units: list[Unit]) -> str:
    root = _root_unit(unit, units)
    if root.unit_id == "cgs":
        return "事业单位"
    if root.unit_id in CENTRAL_GROUPS:
        return "央企/中央单位"
    if root.unit_id in PROVINCIAL_GROUPS:
        return "省属国企"
    return "基础名册单位"


def _discovered_employer_type(name: str, text: str) -> str:
    if "事业单位" in text:
        return "事业单位"
    if "央企" in text or "中央企业" in text:
        return "央企/中央单位"
    if re.search(r"省属|市属|国有企业|国企", text):
        return "地方国企"
    if name.endswith(("研究总院", "研究院", "勘查院", "地质队")):
        return "科研院所/地勘单位"
    return "其他企业"


def resolve_employer(text: str, units: list[Unit], source: Source) -> ResolvedEmployer | None:
    eligible = [
        unit
        for unit in units
        if unit.name in text or any(alias in text for alias in unit.aliases)
    ]
    if eligible:
        unit = max(
            eligible,
            key=lambda item: max([len(item.name), *(len(alias) for alias in item.aliases)]),
        )
        return ResolvedEmployer(unit, "base", _known_employer_type(unit, units))

    source_units = [unit for unit in units if unit.unit_id in set(source.unit_ids)]
    if len(source_units) == 1 and source.role != "discovery":
        unit = source_units[0]
        return ResolvedEmployer(unit, "base", _known_employer_type(unit, units))

    if source.role != "discovery":
        return None
    match = EMPLOYER_PATTERN.search(text.replace(" ", ""))
    if not match:
        return None
    name = match.group("name").strip("：:，,。；;")
    if name in GENERIC_NAMES or "招聘信息汇总" in name:
        return None
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
    unit = Unit(
        unit_id=f"discovered-{digest}",
        name=name,
        aliases=(),
        parent_unit_id=None,
        group=name,
        sector="扩展发现",
        level="扩展发现",
        priority="保底",
        source_ids=(source.source_id,),
        coverage="direct",
    )
    return ResolvedEmployer(unit, "discovered", _discovered_employer_type(name, text))
