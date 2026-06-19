from warmai.config.model_config import PROMPT_VERSION
from warmai.contracts.common import PrimaryLanguage


def build_prompt(
    text: str,
    primary_language: PrimaryLanguage,
    validation_error: str | None = None,
) -> str:
    retry_note = (
        f"\nYour previous output failed validation: {validation_error}\n"
        if validation_error
        else ""
    )
    return f"""Prompt version: {PROMPT_VERSION}
/no_think
Analyze one WarmDock task.
- Preserve the input language and meaning.
- Only correct clear spelling, typo, or grammar errors.
- Return null when no correction is needed.
- Score task difficulty from 1 to 5 using time, steps, workload, and cognitive load.
- Give one reason in {primary_language.value}, 1 to 100 characters.
- Warnings are human-readable only.
- Return only the JSON object required by the provided schema.
{retry_note}
Task: {text}"""
