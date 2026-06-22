from dataclasses import FrozenInstanceError
from typing import Any, get_type_hints

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
    "is_task",
    "needs_review",
]


@pytest.mark.parametrize(
    ("language", "warning", "reason"),
    [
        (
            PrimaryLanguage.ZH_TW,
            "AI 分析暫時無法使用。",
            "目前使用預設分數。",
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
        is_task=True,
        needs_review=True,
    )


def test_partial_recovery_is_immutable() -> None:
    recovery = recover_partial({}, PrimaryLanguage.EN)

    assert isinstance(recovery, PartialRecovery)
    assert get_type_hints(PartialRecovery) == {
        "output": ModelOutput,
        "recovered_fields": list[str],
        "defaulted_fields": list[str],
    }
    assert isinstance(recovery.recovered_fields, list)
    assert isinstance(recovery.defaulted_fields, list)
    with pytest.raises(FrozenInstanceError):
        recovery.output = safe_default(PrimaryLanguage.EN)  # type: ignore[misc]


def test_returned_values_are_defensive_copies() -> None:
    recovery = recover_partial(
        {
            "warnings": ["Original warning."],
            "reason": "Original reason.",
        },
        PrimaryLanguage.EN,
    )

    output = recovery.output
    recovered_fields = recovery.recovered_fields
    defaulted_fields = recovery.defaulted_fields
    output.score = 5
    output.warnings.append("Mutated warning.")
    recovered_fields.clear()
    defaulted_fields.append("mutated")

    assert recovery.output.score == 3
    assert recovery.output.warnings == ["Original warning."]
    assert recovery.recovered_fields == ["warnings", "reason"]
    assert recovery.defaulted_fields == [
        "suggested_text",
        "score",
        "correction_confidence",
        "score_confidence",
        "is_task",
        "needs_review",
    ]


def test_each_field_is_validated_against_pristine_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_validate = ModelOutput.model_validate
    validation_call = 0

    def validate_with_cross_field_rule(
        cls: type[ModelOutput],
        /,
        candidate: object,
        *,
        strict: bool | None = None,
        **kwargs: Any,
    ) -> ModelOutput:
        nonlocal validation_call
        validation_call += 1
        if (
            validation_call == 2
            and isinstance(candidate, dict)
            and candidate["suggested_text"] is not None
            and candidate["score"] == 4
        ):
            original_validate({**candidate, "score": 87}, strict=True)
        return original_validate(candidate, strict=strict, **kwargs)

    monkeypatch.setattr(
        ModelOutput,
        "model_validate",
        classmethod(validate_with_cross_field_rule),
    )

    recovery = recover_partial(
        {
            "suggested_text": "Clean the desk.",
            "score": 4,
        },
        PrimaryLanguage.EN,
    )

    assert recovery.output.suggested_text == "Clean the desk."
    assert recovery.output.score == 4
    assert recovery.recovered_fields == ["suggested_text", "score"]


def test_recovers_each_valid_field_and_tracks_provenance_in_model_order() -> None:
    data = {
        "reason": "A valid reason.",
        "suggested_text": "Clean the desk.",
        "score_confidence": 0.8,
        "warnings": ["Check the deadline."],
        "score": 4,
        "correction_confidence": 0.9,
        "is_task": True,
        "needs_review": True,
    }

    recovery = recover_partial(data, PrimaryLanguage.EN)

    assert recovery.output == ModelOutput.model_validate(data, strict=True)
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
        is_task=True,
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
        "is_task",
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
