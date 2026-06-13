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


@pytest.mark.parametrize(
    ("text", "expected_span", "expected"),
    [
        (
            "聯絡王小明確認時間",
            PiiSpan(start=2, end=5, kind="PERSON"),
            "聯絡[PERSON_001]確認時間",
        ),
        (
            "提醒王小明明天開會",
            PiiSpan(start=2, end=5, kind="PERSON"),
            "提醒[PERSON_001]明天開會",
        ),
        (
            "聯絡\n王小明",
            PiiSpan(start=3, end=6, kind="PERSON"),
            "聯絡\n[PERSON_001]",
        ),
        (
            "提醒\N{FULLWIDTH COLON}王小明",
            PiiSpan(start=3, end=6, kind="PERSON"),
            "提醒\N{FULLWIDTH COLON}[PERSON_001]",
        ),
    ],
)
def test_masks_contextual_name_with_follow_on_or_separator(
    text: str,
    expected_span: PiiSpan,
    expected: str,
) -> None:
    detections = detect_pii(text)

    assert detections == [expected_span]
    assert mask_text(text, detections) == expected


@pytest.mark.parametrize(
    "text",
    [
        "找時間",
        "提醒事項",
        "聯絡客服",
        "告訴大家",
        "約三點",
    ],
)
def test_does_not_treat_contextual_common_phrases_as_people(text: str) -> None:
    assert all(span.kind != "PERSON" for span in detect_pii(text))


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
    "span",
    [
        PiiSpan(start=-1, end=2, kind="EMAIL"),
        PiiSpan(start=1, end=1, kind="EMAIL"),
        PiiSpan(start=4, end=2, kind="EMAIL"),
        PiiSpan(start=0, end=7, kind="EMAIL"),
    ],
)
def test_rejects_invalid_external_spans(span: PiiSpan) -> None:
    with pytest.raises(ValueError):
        mask_text("abcdef", [span])


@pytest.mark.parametrize(
    "text",
    [
        "912345678",
        "+8860912345678",
        "abc0912345678xyz",
        "abc_0912345678_xyz",
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


def test_email_suppresses_overlapping_phone() -> None:
    text = "寄到 0912345678@example.com"
    detections = detect_pii(text)

    assert [(span.kind, text[span.start : span.end]) for span in detections] == [
        ("EMAIL", "0912345678@example.com")
    ]
    assert mask_text(text, detections) == "寄到 [EMAIL_001]"


def test_detects_and_masks_standalone_tw_id_and_ip() -> None:
    text = "身分證 A123456789\N{FULLWIDTH COMMA}IP 192.168.1.1"
    detections = detect_pii(text)

    assert [(span.kind, text[span.start : span.end]) for span in detections] == [
        ("TW_ID", "A123456789"),
        ("IP", "192.168.1.1"),
    ]
    assert (
        mask_text(text, detections)
        == "身分證 [TW_ID_001]\N{FULLWIDTH COMMA}IP [IP_001]"
    )
