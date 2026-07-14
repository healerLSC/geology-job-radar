from monitor.match import classify_major, is_target_recruitment


def test_geology_is_exact_match():
    decision = classify_major("专业要求：地质学、矿物学，硕士研究生")
    assert decision.level == "完全匹配"
    assert "地质学" in decision.evidence
    assert decision.rule_id == "major.exact"


def test_geological_engineering_only_requires_consultation():
    decision = classify_major("专业要求：地质工程、资源勘查工程、采矿工程")
    assert decision.level == "需咨询"
    assert decision.priority == "专业匹配较弱"


def test_broad_geology_category_is_only_possible_match():
    decision = classify_major("地质类、地学相关专业均可报名")
    assert decision.level == "可能匹配"


def test_target_graduation_batch():
    assert is_target_recruitment("面向2027届高校毕业生校园招聘")
    assert is_target_recruitment("2027届暑期实习，优秀者可转正")
    assert not is_target_recruitment("2025届社会招聘")
    assert not is_target_recruitment("2027年度社会招聘成熟人才")
