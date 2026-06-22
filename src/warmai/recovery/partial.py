from collections.abc import Mapping
from copy import deepcopy
from dataclasses import FrozenInstanceError

from pydantic import ValidationError

from warmai.contracts.common import PrimaryLanguage
from warmai.contracts.task_analysis import ModelOutput

FieldName = str


class PartialRecovery:
    __slots__ = (
        "_defaulted_fields_snapshot",
        "_output_snapshot",
        "_recovered_fields_snapshot",
    )

    _output_snapshot: ModelOutput
    _recovered_fields_snapshot: tuple[str, ...]
    _defaulted_fields_snapshot: tuple[str, ...]

    def __init__(
        self,
        output: ModelOutput,
        recovered_fields: list[str],
        defaulted_fields: list[str],
    ) -> None:
        object.__setattr__(self, "_output_snapshot", output.model_copy(deep=True))
        object.__setattr__(self, "_recovered_fields_snapshot", tuple(recovered_fields))
        object.__setattr__(self, "_defaulted_fields_snapshot", tuple(defaulted_fields))

    def __setattr__(self, name: str, value: object) -> None:
        raise FrozenInstanceError(f"cannot assign to field {name!r}")

    @property
    def output(self) -> ModelOutput:
        return self._output_snapshot.model_copy(deep=True)

    @property
    def recovered_fields(self) -> list[str]:
        return list(self._recovered_fields_snapshot)

    @property
    def defaulted_fields(self) -> list[str]:
        return list(self._defaulted_fields_snapshot)


PartialRecovery.__annotations__ = {
    "output": ModelOutput,
    "recovered_fields": list[str],
    "defaulted_fields": list[str],
}


def safe_default(language: PrimaryLanguage) -> ModelOutput:
    if language is PrimaryLanguage.ZH_TW:
        warning = "AI 分析暫時無法使用。"
        reason = "目前使用預設分數。"
    else:
        warning = "AI analysis unavailable."
        reason = "A default score was used."

    return ModelOutput(
        suggested_text=None,
        score=3,
        correction_confidence=0.0,
        score_confidence=0.0,
        warnings=[warning],
        reason=reason,
        is_task=True,
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

        if not _has_exact_contract_type(field_name, data[field_name]):
            defaulted.append(field_name)
            continue

        candidate = deepcopy(defaults.model_dump())
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
        recovered_fields=recovered,
        defaulted_fields=defaulted,
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
    if field_name in {"is_task", "needs_review"}:
        return type(value) is bool
    return False
