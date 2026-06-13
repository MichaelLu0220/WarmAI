import pytest

from warmai.text.language import LanguageClassificationError, classify_language


@pytest.mark.parametrize(
    ("text", "language", "primary"),
    [
        ("整理房間", "zh-TW", "zh-TW"),
        ("Clean the room", "en", "en"),
        ("整理 README file", "mixed", "zh-TW"),
        ("Update 文件", "mixed", "en"),
    ],
)
def test_classifies_supported_text(text: str, language: str, primary: str) -> None:
    result = classify_language(text)
    assert result.language.value == language
    assert result.primary_language.value == primary


@pytest.mark.parametrize(
    "text",
    ["?????", "👍👍👍", "123456", "これはテストです", "\ufffd\ufffd\ufffd"],
)
def test_rejects_unanalyzable_input(text: str) -> None:
    with pytest.raises(LanguageClassificationError):
        classify_language(text)
