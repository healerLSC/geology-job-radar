from monitor.discovery import resolve_employer
from monitor.schema import Source, Unit


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


def source(role="discovery"):
    return Source(
        source_id="global",
        name="权威招聘平台",
        url="https://example.com/jobs",
        source_type="权威招聘平台",
        trust="authoritative",
        unit_ids=(),
        mode="html",
        official_domains=("example.com",),
        tier="l2",
        role=role,
        follow_domains=("example.com",),
    )


def test_known_unit_stays_in_base_registry():
    units = [unit("cnpc", "中国石油"), unit("cnpc-tarim", "塔里木油田", "cnpc")]
    resolved = resolve_employer("塔里木油田2027届招聘", units, source())
    assert resolved is not None
    assert resolved.registry_scope == "base"
    assert resolved.unit.name == "塔里木油田"


def test_unknown_geology_employer_is_discovered():
    resolved = resolve_employer(
        "星海矿业有限公司2027届校园招聘\n专业要求：地质工程",
        [],
        source(),
    )
    assert resolved is not None
    assert resolved.registry_scope == "discovered"
    assert resolved.unit.name == "星海矿业有限公司"
    assert resolved.employer_type == "其他企业"


def test_generic_listing_title_does_not_create_fake_employer():
    resolved = resolve_employer("2027届高校毕业生招聘信息汇总", [], source())
    assert resolved is None


def test_unknown_employer_requires_discovery_source():
    resolved = resolve_employer(
        "星海矿业有限公司2027届校园招聘\n专业要求：地质工程",
        [],
        source(role="fallback"),
    )
    assert resolved is None
