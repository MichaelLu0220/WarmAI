from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import ValidationError

from warmai.contracts.common import PrimaryLanguage
from warmai.contracts.task_analysis import ModelOutput

FieldName = str


@dataclass(frozen=True)
class PartialRecovery:
    output: ModelOutput
    recovered: tuple[FieldName, ...]
    defaulted: tuple[FieldName, ...]


def safe_default(language: PrimaryLanguage) -> ModelOutput:
    if language is PrimaryLanguage.ZH_TW:
        warning = "模型輸出不完整。已套用安全預設值。"
        reason = "無法完整分析。請人工確認。"
    else:
        warning = "Model output was incomplete; safe defaults were applied."
        reason = "The analysis was incomplete and requires human review."

    return ModelOutput(
        suggested_text=None,
        score=3,
        correction_confidence=0.0,
        score_confidence=0.0,
        warnings=[warning],
        reason=reason,
        needs_review=True,
    )


def recover_partial(
    data: Mapping[str, object],
    language: PrimaryLanguage,
) -> PartialRecovery:
    defaults = safe_default(language)
    values = defaults.model_dump()
    recovered: list[FieldName] = []
    defaulted: list[FieldName] = []

    for field_name in ModelOutput.model_fields:
        if field_name not in data:
            defaulted.append(field_name)
            continue

        if field_name == "needs_review":
            if data[field_name] is True:
                recovered.append(field_name)
            else:
                defaulted.append(field_name)
            continue

        if not _has_exact_contract_type(field_name, data[field_name]):
            defaulted.append(field_name)
            continue

        candidate = values.copy()
        candidate[field_name] = data[field_name]
        try:
            validated = ModelOutput.model_validate(candidate, strict=True)
        except ValidationError:
            defaulted.append(field_name)
        else:
            values[field_name] = getattr(validated, field_name)
            recovered.append(field_name)

    values["needs_review"] = True
    return PartialRecovery(
        output=ModelOutput.model_validate(values, strict=True),
        recovered=tuple(recovered),
        defaulted=tuple(defaulted),
    )


def _has_exact_contract_type(field_name: FieldName, value: object) -> bool:
    if field_name == "suggested_text":
        return value is None or type(value) is str
    if field_name == "score":
        return type(value) is int
    if field_name in {"correction_confidence", "score_confidence"}:
        return type(value) is float
    if field_name == "warnings":
        return type(value) is list and all(type(item) is str for item in value)
    if field_name == "reason":
        return type(value) is str
    return False
