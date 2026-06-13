from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ResponseStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"


class FallbackStage(StrEnum):
    NONE = "none"
    JSON_REPAIR = "json_repair"
    RETRY = "retry"
    PARTIAL = "partial"
    SAFE_DEFAULT = "safe_default"


class Language(StrEnum):
    ZH_TW = "zh-TW"
    EN = "en"
    MIXED = "mixed"


class PrimaryLanguage(StrEnum):
    ZH_TW = "zh-TW"
    EN = "en"
