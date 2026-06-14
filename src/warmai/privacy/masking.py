from collections import defaultdict

from warmai.privacy.pii import PiiSpan


def mask_text(text: str, spans: list[PiiSpan]) -> str:
    counters: defaultdict[str, int] = defaultdict(int)
    ordered_spans = sorted(spans, key=lambda item: (item.start, item.end))
    replacements: list[tuple[PiiSpan, str]] = []
    for index, span in enumerate(ordered_spans):
        if not 0 <= span.start < span.end <= len(text):
            raise ValueError("PII spans must be within text bounds")
        if index > 0 and span.start < ordered_spans[index - 1].end:
            raise ValueError("PII spans must not overlap")
        counters[span.kind] += 1
        token = f"[{span.kind}_{counters[span.kind]:03d}]"
        replacements.append((span, token))

    result = text
    for span, token in reversed(replacements):
        result = result[: span.start] + token + result[span.end :]
    return result
