from doc_agent.config import Settings, get_settings, normalize_llm_provider
from doc_agent.llm.base import BaseLLMClient
from doc_agent.llm.local_relay_client import LocalRelayLLMClient
from doc_agent.llm.mock_client import MockLLMClient
from doc_agent.llm.nga_client import NGAClient
from doc_agent.llm.openai_client import OpenAICompatibleLLMClient


def get_llm_client(settings: Settings | None = None) -> BaseLLMClient:
    active_settings = settings or get_settings()
    provider = normalize_llm_provider(active_settings.llm_provider)
    if provider == "stub":
        return MockLLMClient()
    if provider == "nga":
        return NGAClient(active_settings)
    if provider == "local_relay":
        return LocalRelayLLMClient(active_settings)
    if provider == "openai_compatible":
        return OpenAICompatibleLLMClient(active_settings)
    raise ValueError(
        f"Unsupported LLM_PROVIDER: {active_settings.llm_provider}. "
        "Use stub, local_relay, or nga after the internal adapter is implemented."
    )


__all__ = [
    "BaseLLMClient",
    "LocalRelayLLMClient",
    "MockLLMClient",
    "NGAClient",
    "OpenAICompatibleLLMClient",
    "get_llm_client",
]
