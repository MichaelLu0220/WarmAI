import unicodedata
from dataclasses import dataclass

from warmai.contracts.common import Language, PrimaryLanguage


class LanguageClassificationError(ValueError):
    pass


@dataclass(frozen=True)
class LanguageResult:
    language: Language
    primary_language: PrimaryLanguage


def _is_han(char: str) -> bool:
    codepoint = ord(char)
    return 0x3400 <= codepoint <= 0x4DBF or 0x4E00 <= codepoint <= 0x9FFF


def _is_latin(char: str) -> bool:
    return char.isalpha() and "LATIN" in unicodedata.name(char, "")


def _is_unsupported_letter(char: str) -> bool:
    return char.isalpha() and not _is_han(char) and not _is_latin(char)


def classify_language(text: str) -> LanguageResult:
    normalized = unicodedata.normalize("NFKC", text).strip()
    if not normalized:
        raise LanguageClassificationError("input is blank")

    han_count = sum(_is_han(char) for char in normalized)
    latin_count = sum(_is_latin(char) for char in normalized)
    unsupported_count = sum(_is_unsupported_letter(char) for char in normalized)

    if unsupported_count or (han_count == 0 and latin_count == 0):
        raise LanguageClassificationError("input language is unsupported or unanalyzable")

    if han_count and latin_count:
        first_is_han = next(
            _is_han(char)
            for char in normalized
            if _is_han(char) or _is_latin(char)
        )
        primary = PrimaryLanguage.ZH_TW if first_is_han else PrimaryLanguage.EN
        return LanguageResult(Language.MIXED, primary)
    if han_count:
        return LanguageResult(Language.ZH_TW, PrimaryLanguage.ZH_TW)
    return LanguageResult(Language.EN, PrimaryLanguage.EN)
