from dataclasses import dataclass
import re


EXACT = (
    "地质学",
    "0709",
    "矿物学、岩石学、矿床学",
    "矿物学",
    "岩石学",
    "矿床学",
    "古生物学与地层学",
    "构造地质学",
    "第四纪地质学",
    "地球化学",
)
ENGINEERING_ONLY = (
    "地质工程",
    "资源勘查工程",
    "勘查技术与工程",
    "工程地质",
    "物探",
    "地球物理",
    "采矿工程",
)
RELATED_PATTERNS = (
    r"地质类",
    r"地学.{0,6}相关专业",
    r"地质.{0,6}相关专业",
    r"专业要求.{0,20}地质(?:[、,，/]|$)",
)


@dataclass(frozen=True)
class MatchDecision:
    level: str
    priority: str
    evidence: str
    rule_id: str


def classify_major(text: str) -> MatchDecision:
    exact = next((term for term in EXACT if term in text), None)
    if exact:
        return MatchDecision("完全匹配", "重点冲", exact, "major.exact")
    related = next((pattern for pattern in RELATED_PATTERNS if re.search(pattern, text)), None)
    if related:
        evidence = re.search(related, text).group(0)
        return MatchDecision("可能匹配", "保底", evidence, "major.related")
    engineering = [term for term in ENGINEERING_ONLY if term in text]
    if engineering:
        return MatchDecision(
            "需咨询",
            "专业匹配较弱",
            "、".join(dict.fromkeys(engineering)),
            "major.engineering_only",
        )
    return MatchDecision("需咨询", "专业匹配较弱", "未找到地质学专业原文", "major.unknown")


def has_geology_signal(text: str) -> bool:
    decision = classify_major(text)
    return decision.rule_id != "major.unknown"


def is_target_recruitment(text: str) -> bool:
    target_year = bool(re.search(r"2027\s*届|2027年(?:应届|毕业)", text))
    recruitment_context = bool(re.search(r"校园招聘|高校毕业生|应届|暑期实习|实习转正", text))
    social_only = "社会招聘" in text and not re.search(r"校园招聘|高校毕业生|应届|实习", text)
    return target_year and recruitment_context and not social_only
