from importlib import resources

from warmai.config.model_config import PROMPT_VERSION
from warmai.contracts.common import PrimaryLanguage


def _load_template(prompt_version: str) -> str:
    template = resources.files("warmai.inference.prompts").joinpath(f"{prompt_version}.txt")
    if not template.is_file():
        raise ValueError(f"Unknown prompt template version: {prompt_version}")
    return template.read_text(encoding="utf-8")


def build_prompt(
    text: str,
    primary_language: PrimaryLanguage,
    validation_error: str | None = None,
    prompt_version: str | None = None,
) -> str:
    resolved_version = prompt_version or PROMPT_VERSION
    retry_note = (
        f"\nYour previous output failed validation: {validation_error}\n"
        if validation_error
        else ""
    )
    return _load_template(resolved_version).format(
        prompt_version=resolved_version,
        primary_language=primary_language.value,
        retry_note=retry_note,
        text=text,
    ).rstrip("\n")
