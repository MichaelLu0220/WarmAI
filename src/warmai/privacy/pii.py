import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PiiSpan:
    start: int
    end: int
    kind: str


PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    (
        "PHONE",
        re.compile(
            r"(?<![A-Za-z0-9_])"
            r"(?:09\d{2}[- ]?\d{3}[- ]?\d{3}|\+886[- ]?9\d{2}[- ]?\d{3}[- ]?\d{3})"
            r"(?![A-Za-z0-9_])"
        ),
    ),
    ("TW_ID", re.compile(r"\b[A-Z][12]\d{8}\b", re.I)),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
)
NON_PERSON_PHRASES = frozenset({"時間", "事項", "客服", "大家", "三點"})
CONTEXTUAL_NAME = re.compile(
    r"(?:提醒|聯絡|寄給|打給|告訴|找|約)[ \t]*"
    r"(?:(?::|\N{FULLWIDTH COLON})[ \t]*|\r?\n[ \t]*)?"
    r"([\u4e00-\u9fff]{2,4}?)(?=寄信|確認|明天|"
    r"[\s\N{FULLWIDTH COMMA},\N{IDEOGRAPHIC FULL STOP}.!"
    r"\N{FULLWIDTH EXCLAMATION MARK}\N{FULLWIDTH QUESTION MARK}?:"
    r"\N{FULLWIDTH COLON}]|$)"
)
REMINDER_TASK_NAME = re.compile(r"提醒([\u4e00-\u9fff]{2,4})(?=整理|打掃)")


def _is_likely_name(value: str) -> bool:
    return value not in NON_PERSON_PHRASES


def detect_pii(text: str) -> list[PiiSpan]:
    spans: list[PiiSpan] = []
    for kind, pattern in PATTERNS:
        spans.extend(PiiSpan(match.start(), match.end(), kind) for match in pattern.finditer(text))
    for match in CONTEXTUAL_NAME.finditer(text):
        if _is_likely_name(match.group(1)):
            spans.append(PiiSpan(match.start(1), match.end(1), "PERSON"))
    for match in REMINDER_TASK_NAME.finditer(text):
        if _is_likely_name(match.group(1)):
            spans.append(PiiSpan(match.start(1), match.end(1), "PERSON"))

    preferred = sorted(
        set(spans),
        key=lambda item: (-(item.end - item.start), item.start, item.end, item.kind),
    )
    resolved: list[PiiSpan] = []
    for span in preferred:
        if not any(span.start < item.end and item.start < span.end for item in resolved):
            resolved.append(span)
    return sorted(resolved, key=lambda item: (item.start, item.end))
