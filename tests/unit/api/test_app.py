from pydantic import SecretStr

from warmai.api.app import build_adapter
from warmai.config.settings import Settings
from warmai.inference.adapters.llama_cpp import LlamaCppAdapter
from warmai.inference.adapters.mock import MockAdapter


def test_build_adapter_selects_mock() -> None:
    settings = Settings(api_key=SecretStr("secret"), adapter_kind="mock")

    assert isinstance(build_adapter(settings), MockAdapter)


def test_build_adapter_selects_llama_cpp() -> None:
    settings = Settings(
        api_key=SecretStr("secret"),
        adapter_kind="llama_cpp",
        llama_cpp_base_url="http://llama/",
        llama_cpp_model="model-1",
    )

    adapter = build_adapter(settings)

    assert isinstance(adapter, LlamaCppAdapter)
    assert adapter.base_url == "http://llama"
    assert adapter.model == "model-1"
