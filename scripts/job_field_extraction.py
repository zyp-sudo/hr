"""Conservative extraction of searchable job requirements from source text.

Only explicit education and RMB monthly/annual salary expressions are emitted.
Unknown or foreign-currency compensation remains null instead of being guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


EDUCATION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("博士", (r"博士(?:及以上)?(?:学历|学位)?", r"\bph\.?d\.?\b", r"\bdoctorate\b")),
    ("硕士", (r"硕士(?:及以上)?(?:学历|学位)?", r"研究生(?:及以上)?(?:学历|学位)?", r"\bmaster(?:'s)?\b", r"\bmsc\b", r"\bmba\b")),
    ("本科", (r"本科(?:及以上)?(?:学历|学位)?", r"学士(?:及以上)?(?:学历|学位)?", r"\bbachelor(?:'s)?\b", r"\bundergraduate\b")),
    ("大专", (r"大专(?:及以上)?(?:学历)?", r"专科(?:及以上)?(?:学历)?", r"\bassociate(?:'s)? degree\b")),
    ("高中", (r"高中(?:及以上)?(?:学历)?", r"中专(?:及以上)?(?:学历)?", r"\bhigh school\b")),
)

_EDUCATION_RANK = {"高中": 1, "大专": 2, "本科": 3, "硕士": 4, "博士": 5}


@dataclass(frozen=True)
class Salary:
    minimum: int
    maximum: int
    text: str


def extract_education(text: str | None) -> str | None:
    """Return the explicitly requested minimum education level, if present."""
    value = str(text or "")
    candidates: list[str] = []
    for label, patterns in EDUCATION_PATTERNS:
        for pattern in patterns:
            for match in re.finditer(pattern, value, flags=re.IGNORECASE):
                suffix = value[match.end() : match.end() + 8]
                # "博士优先" is a preference, not a minimum requirement. If an
                # actual lower requirement also exists, it remains a candidate.
                if re.match(r"\s*(?:者)?优先", suffix):
                    continue
                candidates.append(label)
    return min(candidates, key=_EDUCATION_RANK.__getitem__) if candidates else None


_MONTHLY_RANGE = re.compile(
    r"(?<![\d.])(?:月薪\s*|薪资\s*[:：]?\s*|人民币\s*|RMB\s*|[¥￥]\s*)?"
    r"(?P<low>\d{1,3}(?:\.\d+)?)\s*(?:k|K|千)?\s*[-~～—至到]\s*"
    r"(?P<high>\d{1,3}(?:\.\d+)?)\s*(?P<unit>k|K|千|万)?"
    r"\s*(?:元)?\s*(?:/\s*(?:月|month)|每月|月薪|·\s*\d{1,2}薪)",
    flags=re.IGNORECASE,
)

_ANNUAL_RANGE = re.compile(
    r"(?<![\d.])(?:年薪\s*|薪资\s*[:：]?\s*|人民币\s*|RMB\s*|[¥￥]\s*)?"
    r"(?P<low>\d{1,3}(?:\.\d+)?)\s*[-~～—至到]\s*"
    r"(?P<high>\d{1,3}(?:\.\d+)?)\s*(?P<unit>万|w|W|k|K|千)"
    r"\s*(?:元)?\s*(?:/\s*(?:年|year)|每年|年薪)",
    flags=re.IGNORECASE,
)


def _amount(value: str, unit: str | None) -> int:
    multiplier = {"万": 10_000, "w": 10_000, "k": 1_000, "千": 1_000}.get((unit or "").lower(), 1)
    return round(float(value) * multiplier)


def extract_salary(text: str | None) -> Salary | None:
    """Extract an explicit RMB salary and normalize it to monthly integer RMB.

    Bare ranges without a monthly/annual marker and foreign-currency expressions
    are intentionally unsupported because conversion would fabricate data.
    """
    value = str(text or "")
    candidates: list[tuple[int, re.Match[str], bool]] = []
    for pattern, annual in ((_MONTHLY_RANGE, False), (_ANNUAL_RANGE, True)):
        match = pattern.search(value)
        if match:
            candidates.append((match.start(), match, annual))
    if not candidates:
        return None
    _, match, annual = min(candidates, key=lambda item: item[0])
    unit = match.group("unit")
    # In common Chinese listings, 10-20K/月 puts the unit after the range.
    low = _amount(match.group("low"), unit)
    high = _amount(match.group("high"), unit)
    if annual:
        low, high = round(low / 12), round(high / 12)
    if low <= 0 or high < low or high > 1_000_000:
        return None
    return Salary(low, high, match.group(0).strip())
