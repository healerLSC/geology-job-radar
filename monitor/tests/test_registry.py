from pathlib import Path

from monitor.schema import load_sources, load_units, validate_registry


ROOT = Path(__file__).parents[2]


def test_complete_registry_is_valid():
    units = load_units(ROOT / "monitor/units.json")
    sources = load_sources(ROOT / "monitor/sources.json")
    assert validate_registry(units, sources) == []
    names = {unit.name for unit in units}
    required = {
        "塔里木油田",
        "西北油田分公司",
        "中海油研究总院",
        "神东煤炭集团",
        "中煤平朔集团",
        "中煤地质集团有限公司",
        "国冶一局集团",
        "中化地质矿山总局地质研究院",
        "五矿资源",
        "中国黄金集团地质有限公司",
        "中铝矿业",
        "山东黄金地质矿产勘查有限公司",
        "江西铜业集团地勘工程有限公司",
        "德兴铜矿",
        "普朗铜矿",
        "白云鄂博矿区",
        "镜铁山矿",
        "中铁上海设计院集团有限公司",
        "中国地质调查局",
    }
    assert required <= names


def test_every_unit_has_coverage_path():
    units = load_units(ROOT / "monitor/units.json")
    assert all(unit.source_ids or unit.parent_unit_id for unit in units)


def test_combined_names_are_split_into_independent_units():
    units = load_units(ROOT / "monitor/units.json")
    names = {unit.name for unit in units}
    assert {"华北油田", "冀东油田", "吉林油田"} <= names
    assert {"江苏油田", "河南油田"} <= names
    assert {"乌海能源", "平庄煤业", "包头能源"} <= names
    assert {"焦家金矿", "三山岛金矿", "新城金矿"} <= names
    assert {"玲珑金矿", "夏甸金矿", "大尹格庄金矿"} <= names
