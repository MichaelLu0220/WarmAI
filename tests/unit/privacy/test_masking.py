import pytest

from warmai.privacy.masking import mask_text
from warmai.privacy.pii import PiiSpan, detect_pii


def test_masks_email_phone_and_contextual_chinese_name() -> None:
    text = "提醒王小明寄信到 user@example.com\N{FULLWIDTH COMMA}電話 0912-345-678"
    detections = detect_pii(text)
    masked = mask_text(text, detections)

    assert [(span.kind, text[span.start : span.end]) for span in detections] == [
        ("PERSON", "王小明"),
        ("EMAIL", "user@example.com"),
        ("PHONE", "0912-345-678"),
    ]
    assert (
        masked
        == "提醒[PERSON_001]寄信到 [EMAIL_001]\N{FULLWIDTH COMMA}電話 [PHONE_001]"
    )


def test_normal_task_is_training_eligible() -> None:
    assert detect_pii("整理房間") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("聯絡王小明", "聯絡[PERSON_001]"),
        ("寄給王小明", "寄給[PERSON_001]"),
        ("打給王小明", "打給[PERSON_001]"),
        ("告訴王小明", "告訴[PERSON_001]"),
        ("找王小明", "找[PERSON_001]"),
        ("約王小明", "約[PERSON_001]"),
        ("提醒 王小明", "提醒 [PERSON_001]"),
    ],
)
def test_masks_contextual_chinese_names(text: str, expected: str) -> None:
    assert mask_text(text, detect_pii(text)) == expected


def test_email_suppresses_overlapping_tw_id() -> None:
    text = "寄到 A123456789@example.com"
    detections = detect_pii(text)

    assert [(span.kind, text[span.start : span.end]) for span in detections] == [
        ("EMAIL", "A123456789@example.com")
    ]
    assert mask_text(text, detections) == "寄到 [EMAIL_001]"


def test_rejects_overlapping_external_spans() -> None:
    spans = [
        PiiSpan(start=0, end=4, kind="EMAIL"),
        PiiSpan(start=2, end=6, kind="PHONE"),
    ]

    with pytest.raises(ValueError):
        mask_text("abcdef", spans)


@pytest.mark.parametrize(
    "text",
    [
        "912345678",
        "+8860912345678",
        "abc0912345678xyz",
    ],
)
def test_rejects_invalid_phone_forms(text: str) -> None:
    assert all(span.kind != "PHONE" for span in detect_pii(text))


@pytest.mark.parametrize(
    "phone",
    [
        "0912-345-678",
        "+886 912-345-678",
    ],
)
def test_detects_valid_phone_forms(phone: str) -> None:
    assert [(span.kind, phone[span.start : span.end]) for span in detect_pii(phone)] == [
        ("PHONE", phone)
    ]


def test_numbers_same_kind_tokens_left_to_right() -> None:
    text = "first@example.com second@example.com"

    assert mask_text(text, detect_pii(text)) == "[EMAIL_001] [EMAIL_002]"
