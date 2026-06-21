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
- Only correct clear spelling, typo, grammar, or encoding errors.
- suggested_text must be null when the input is already clear and understandable.
- Do not rewrite clear text just to make it prettier, more formal, or more specific.
- Score task difficulty from 1 to 5 using time, steps, workload, and cognitive load.
- Score 1: trivial, one clear step, usually under 5 minutes.
- Score 2: easy task with low effort, usually 5 to 15 minutes.
- Score 3: normal chore or personal task with multiple steps, usually 15 to 45 minutes.
- Score 4: substantial task needing planning, sustained effort, or high cognitive load.
- Score 5: large, risky, multi-session, or highly complex task.
- Do not default to score 1 just because the wording is short.
- Give one reason in {primary_language.value}, 1 to 100 characters.
- Warnings are human-readable only.
- Return only the JSON object required by the provided schema.
{retry_note}
Task: {text}"""
