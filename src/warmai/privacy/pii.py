import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PiiSpan:
    start: int
    end: int
    kind: str


PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?886[- ]?)?0?9\d{2}[- ]?\d{3}[- ]?\d{3}(?!\d)")),
    ("TW_ID", re.compile(r"\b[A-Z][12]\d{8}\b", re.I)),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
)
CONTEXTUAL_NAME = re.compile(r"(?:提醒|聯絡|寄給|打給|告訴|找|約)([\u4e00-\u9fff]{2,4})")


def detect_pii(text: str) -> list[PiiSpan]:
    spans: list[PiiSpan] = []
    for kind, pattern in PATTERNS:
        spans.extend(PiiSpan(match.start(), match.end(), kind) for match in pattern.finditer(text))
    for match in CONTEXTUAL_NAME.finditer(text):
        spans.append(PiiSpan(match.start(1), match.end(1), "PERSON"))
    return sorted(spans, key=lambda item: (item.start, item.end))
