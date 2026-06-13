from collections import defaultdict

from warmai.privacy.pii import PiiSpan


def mask_text(text: str, spans: list[PiiSpan]) -> str:
    counters: defaultdict[str, int] = defaultdict(int)
    result = text
    for span in sorted(spans, key=lambda item: item.start, reverse=True):
        counters[span.kind] += 1
        token = f"[{span.kind}_{counters[span.kind]:03d}]"
        result = result[: span.start] + token + result[span.end :]
    return result
