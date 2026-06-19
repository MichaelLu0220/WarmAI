import json


def repair_json_syntax(raw: str) -> str:
    """Apply only bounded, syntax-level repairs to a JSON string."""
    if _is_valid_json(raw):
        return raw

    repaired = _strip_surrounding_fence(raw)
    repaired = _remove_trailing_commas(repaired)
    if _is_valid_json(repaired):
        return repaired

    if _has_one_unclosed_root_object(repaired):
        completed = f"{repaired}}}"
        if _is_valid_json(completed):
            return completed

    return repaired


def _is_valid_json(value: str) -> bool:
    try:
        json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return False
    return True


def _strip_surrounding_fence(raw: str) -> str:
    stripped = raw.strip()
    first_newline = stripped.find("\n")
    if first_newline == -1 or not stripped.endswith("```"):
        return raw

    opening = stripped[:first_newline].strip().lower()
    if opening not in {"```", "```json"}:
        return raw

    return stripped[first_newline + 1 : -3].strip()


def _remove_trailing_commas(raw: str) -> str:
    repaired: list[str] = []
    in_string = False
    escaped = False
    index = 0

    while index < len(raw):
        character = raw[index]
        if in_string:
            repaired.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue

        if character == '"':
            in_string = True
            repaired.append(character)
        elif character == ",":
            next_index = index + 1
            while next_index < len(raw) and raw[next_index].isspace():
                next_index += 1
            if next_index >= len(raw) or raw[next_index] not in "}]":
                repaired.append(character)
        else:
            repaired.append(character)
        index += 1

    return "".join(repaired)


def _has_one_unclosed_root_object(raw: str) -> bool:
    stack: list[str] = []
    in_string = False
    escaped = False

    for character in raw:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
        elif character in "[{":
            stack.append(character)
        elif character in "]}":
            if not stack or not _closers_match(stack.pop(), character):
                return False

    return not in_string and stack == ["{"]


def _closers_match(opener: str, closer: str) -> bool:
    return (opener, closer) in {("[", "]"), ("{", "}")}
