from dataclasses import FrozenInstanceError, fields
from typing import get_type_hints

import pytest
from pydantic import ValidationError

from warmai.contracts.common import PrimaryLanguage
from warmai.contracts.task_analysis import ModelOutput
from warmai.recovery.partial import PartialRecovery, recover_partial, safe_default

FIELD_ORDER = [
    "suggested_text",
    "score",
    "correction_confidence",
    "score_confidence",
    "warnings",
    "reason",
    "needs_review",
]


@pytest.mark.parametrize(
    ("language", "warning", "reason"),
    [
        (
            PrimaryLanguage.ZH_TW,
            "模型輸出不完整。已套用安全預設值。",
            "無法完整分析。請人工確認。",
        ),
        (
            PrimaryLanguage.EN,
            "AI analysis unavailable.",
            "A default score was used.",
        ),
    ],
)
def test_safe_default_is_localized_and_contract_valid(
    language: PrimaryLanguage,
    warning: str,
    reason: str,
) -> None:
    output = safe_default(language)

    assert output == ModelOutput(
        suggested_text=None,
        score=3,
        correction_confidence=0.0,
        score_confidence=0.0,
        warnings=[warning],
        reason=reason,
        needs_review=True,
    )


def test_partial_recovery_is_immutable() -> None:
    recovery = recover_partial({}, PrimaryLanguage.EN)

    assert isinstance(recovery, PartialRecovery)
    assert [field.name for field in fields(recovery)] == [
        "output",
        "recovered_fields",
        "defaulted_fields",
    ]
    assert get_type_hints(PartialRecovery) == {
        "output": ModelOutput,
        "recovered_fields": list[str],
        "defaulted_fields": list[str],
    }
    assert isinstance(recovery.recovered_fields, list)
    assert isinstance(recovery.defaulted_fields, list)
    with pytest.raises(FrozenInstanceError):
        recovery.output = safe_default(PrimaryLanguage.EN)


def test_recovers_each_valid_field_and_tracks_provenance_in_model_order() -> None:
    data = {
        "reason": "A valid reason.",
        "suggested_text": "Clean the desk.",
        "score_confidence": 0.8,
        "warnings": ["Check the deadline."],
        "score": 4,
        "correction_confidence": 0.9,
        "needs_review": True,
    }

    recovery = recover_partial(data, PrimaryLanguage.EN)

    assert recovery.output == ModelOutput(**data)
    assert recovery.recovered_fields == FIELD_ORDER
    assert recovery.defaulted_fields == []


def test_invalid_and_missing_fields_use_defaults_without_affecting_valid_fields() -> None:
    recovery = recover_partial(
        {
            "suggested_text": "整理桌面",
            "score": 87,
            "correction_confidence": 0.7,
            "score_confidence": "0.8",
            "warnings": ["請確認期限"],
            "reason": "",
        },
        PrimaryLanguage.ZH_TW,
    )
    defaults = safe_default(PrimaryLanguage.ZH_TW)

    assert recovery.output == ModelOutput(
        suggested_text="整理桌面",
        score=defaults.score,
        correction_confidence=0.7,
        score_confidence=defaults.score_confidence,
        warnings=["請確認期限"],
        reason=defaults.reason,
        needs_review=True,
    )
    assert recovery.recovered_fields == [
        "suggested_text",
        "correction_confidence",
        "warnings",
    ]
    assert recovery.defaulted_fields == [
        "score",
        "score_confidence",
        "reason",
        "needs_review",
    ]


def test_strict_contract_types_are_not_coerced() -> None:
    recovery = recover_partial(
        {
            "suggested_text": 123,
            "score": "4",
            "correction_confidence": 1,
            "score_confidence": 0,
            "warnings": ("tuple warning",),
            "reason": True,
            "needs_review": 1,
        },
        PrimaryLanguage.EN,
    )

    assert recovery.recovered_fields == []
    assert recovery.defaulted_fields == FIELD_ORDER
    assert recovery.output == safe_default(PrimaryLanguage.EN)


def test_unknown_input_keys_do_not_enter_output_or_provenance() -> None:
    recovery = recover_partial(
        {
            "score": 5,
            "unknown": "must be ignored",
        },
        PrimaryLanguage.EN,
    )

    assert recovery.output.score == 5
    assert "unknown" not in recovery.output.model_dump()
    assert "unknown" not in recovery.recovered_fields
    assert "unknown" not in recovery.defaulted_fields


def test_false_needs_review_is_recovered_before_policy_forces_output_true() -> None:
    recovery = recover_partial(
        {
            "needs_review": False,
        },
        PrimaryLanguage.EN,
    )

    assert recovery.output.needs_review is True
    assert recovery.recovered_fields == ["needs_review"]
    assert recovery.defaulted_fields == FIELD_ORDER[:-1]


def test_partial_recovery_output_remains_contract_valid() -> None:
    recovery = recover_partial({}, PrimaryLanguage.EN)

    with pytest.raises(ValidationError):
        ModelOutput.model_validate(
            {
                **recovery.output.model_dump(),
                "score": 87,
            },
            strict=True,
        )
