import json

import pytest

from warmai.recovery.json_repair import repair_json_syntax


def test_strips_surrounding_markdown_json_fence() -> None:
    raw = '```json\n{"score": 3}\n```'

    assert repair_json_syntax(raw) == '{"score": 3}'


def test_strips_surrounding_unlabelled_markdown_fence() -> None:
    raw = '```\n[{"score": 3}]\n```'

    assert repair_json_syntax(raw) == '[{"score": 3}]'


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"score": 3,}', '{"score": 3}'),
        ('{"warnings": ["first", "second",],}', '{"warnings": ["first", "second"]}'),
        ("[1, 2,]", "[1, 2]"),
    ],
)
def test_removes_trailing_commas_before_object_and_array_closers(
    raw: str,
    expected: str,
) -> None:
    assert repair_json_syntax(raw) == expected


def test_does_not_change_commas_braces_or_escaped_quotes_inside_strings() -> None:
    raw = r'{"reason":"Keep comma, brace } and quote \" unchanged",}'

    repaired = repair_json_syntax(raw)

    assert repaired == r'{"reason":"Keep comma, brace } and quote \" unchanged"}'
    assert json.loads(repaired)["reason"] == 'Keep comma, brace } and quote " unchanged'


def test_adds_one_missing_final_root_object_closer_when_result_is_valid_json() -> None:
    raw = '{"score": 3, "warnings": ["brace } in text"]'

    assert repair_json_syntax(raw) == '{"score": 3, "warnings": ["brace } in text"]}'


def test_leaves_already_valid_json_unchanged() -> None:
    raw = ' { "score": 3, "warnings": ["already valid"] } '

    assert repair_json_syntax(raw) == raw


def test_does_not_change_invalid_scalar_values() -> None:
    raw = '{"score": 87}'

    assert repair_json_syntax(raw) == raw


@pytest.mark.parametrize(
    "raw",
    [
        '{"outer": {"score": 3',
        '{"score": 3 "reason": "missing comma"',
        '{"reason": "unterminated string}',
        '[{"score": 3}',
    ],
)
def test_leaves_unsupported_corruption_invalid_instead_of_guessing(raw: str) -> None:
    repaired = repair_json_syntax(raw)

    with pytest.raises(json.JSONDecodeError):
        json.loads(repaired)
