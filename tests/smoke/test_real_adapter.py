import os

import pytest

from warmai.inference.adapters.llama_cpp import LlamaCppAdapter


@pytest.mark.skipif(
    os.getenv("WARMAI_RUN_REAL_MODEL_SMOKE") != "1",
    reason="real llama.cpp smoke test is opt-in",
)
@pytest.mark.asyncio
async def test_llama_cpp_model_is_loaded() -> None:
    adapter = LlamaCppAdapter(
        base_url=os.environ["WARMAI_LLAMA_CPP_BASE_URL"],
        model=os.environ["WARMAI_LLAMA_CPP_MODEL"],
    )

    assert await adapter.healthcheck()
