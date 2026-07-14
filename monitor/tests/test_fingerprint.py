from monitor.fingerprint import content_fingerprint, normalize_text


def test_dynamic_whitespace_does_not_change_fingerprint():
    first = "2027届 校园招聘\n地质学 硕士"
    second = " 2027届   校园招聘 地质学\t硕士 "
    assert normalize_text(first) == normalize_text(second)
    assert content_fingerprint(first) == content_fingerprint(second)


def test_unicode_width_is_normalized():
    assert normalize_text("２０２７届　地质学") == "2027届 地质学"
