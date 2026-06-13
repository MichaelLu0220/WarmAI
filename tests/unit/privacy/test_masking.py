from warmai.privacy.masking import mask_text
from warmai.privacy.pii import detect_pii


def test_masks_email_phone_and_contextual_chinese_name() -> None:
    text = "提醒王小明寄信到 user@example.com，電話 0912-345-678"
    detections = detect_pii(text)
    masked = mask_text(text, detections)

    assert "[PERSON_001]" in masked
    assert "[EMAIL_001]" in masked
    assert "[PHONE_001]" in masked
    assert "王小明" not in masked
    assert "user@example.com" not in masked


def test_normal_task_is_training_eligible() -> None:
    assert detect_pii("整理房間") == []
