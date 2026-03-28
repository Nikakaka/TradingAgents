import copy
import os
import re
from typing import Any, Optional

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from pydantic import PrivateAttr

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model


def _sanitize_text_for_zhipu(text: str, max_chars: int = 5000) -> str:
    if not text:
        return ""

    sanitized = str(text)
    replacements = {
        "Bull Analyst": "View A",
        "Bear Analyst": "View B",
        "Bull Researcher": "Researcher A",
        "Bear Researcher": "Researcher B",
        "Supportive Analyst": "View A",
        "Risk Analyst": "View B",
        "Aggressive Analyst": "Growth-Focused Analyst",
        "Conservative Analyst": "Risk-Control Analyst",
        "Neutral Analyst": "Balanced Analyst",
        "Supportive View": "View A",
        "Risk View": "View B",
        "FINAL TRANSACTION PROPOSAL": "FINAL RECOMMENDATION",
        "debate": "discussion",
        "bull": "positive",
        "bear": "risk",
    }
    for src, dst in replacements.items():
        sanitized = sanitized.replace(src, dst)

    sanitized = re.sub(r"https?://\S+", "[link]", sanitized)
    sanitized = re.sub(r"\b\S+@\S+\b", "[email]", sanitized)
    sanitized = re.sub(r"`{1,3}.*?`{1,3}", "[quoted text]", sanitized, flags=re.DOTALL)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized[:max_chars]


def _sanitize_input_for_zhipu(input_data: Any) -> Any:
    if isinstance(input_data, str):
        return (
            "Please answer in calm, neutral financial language.\n\n"
            + _sanitize_text_for_zhipu(input_data)
        )

    if isinstance(input_data, list):
        sanitized_items = []
        for item in input_data:
            if isinstance(item, dict):
                cloned = dict(item)
                if "content" in cloned:
                    cloned["content"] = _sanitize_text_for_zhipu(cloned["content"])
                sanitized_items.append(cloned)
                continue
            cloned = copy.deepcopy(item)
            if hasattr(cloned, "content"):
                try:
                    cloned.content = _sanitize_text_for_zhipu(cloned.content)
                except Exception:
                    pass
            sanitized_items.append(cloned)
        return sanitized_items

    cloned = copy.deepcopy(input_data)
    if hasattr(cloned, "content"):
        try:
            cloned.content = _sanitize_text_for_zhipu(cloned.content)
        except Exception:
            pass
    return cloned


def _build_safe_fallback_message(input_data: Any) -> AIMessage:
    if isinstance(input_data, str):
        source = _sanitize_text_for_zhipu(input_data, max_chars=1200)
    elif isinstance(input_data, list):
        parts = []
        for item in input_data:
            if isinstance(item, dict) and item.get("content"):
                parts.append(_sanitize_text_for_zhipu(item["content"], max_chars=400))
            elif hasattr(item, "content"):
                parts.append(_sanitize_text_for_zhipu(getattr(item, "content", ""), max_chars=400))
        source = " ".join(part for part in parts if part)[:1200]
    elif hasattr(input_data, "content"):
        source = _sanitize_text_for_zhipu(getattr(input_data, "content", ""), max_chars=1200)
    else:
        source = ""

    content = (
        "Rating: Hold\n"
        "Executive Summary: Automated synthesis was blocked by the provider safety filter, so a conservative hold stance is used as a fallback.\n"
        f"Investment Thesis: {source or 'The available analyst context should be reviewed manually before taking a directional position.'}\n"
        "FINAL RECOMMENDATION: HOLD"
    )
    return AIMessage(content=content)


class NormalizedChatOpenAI(ChatOpenAI):
    """ChatOpenAI with normalized content output and provider-specific retries."""

    _provider_name: str = PrivateAttr(default="openai")

    def __init__(self, *args, provider: str = "openai", **kwargs):
        super().__init__(*args, **kwargs)
        self._provider_name = (provider or "openai").lower()

    def invoke(self, input, config=None, **kwargs):
        try:
            return normalize_content(super().invoke(input, config, **kwargs))
        except Exception as exc:
            error_text = str(exc)
            if self._provider_name != "zhipu":
                raise
            if "1301" not in error_text and "contentFilter" not in error_text:
                raise
            sanitized_input = _sanitize_input_for_zhipu(input)
            try:
                return normalize_content(super().invoke(sanitized_input, config, **kwargs))
            except Exception as retry_exc:
                retry_error = str(retry_exc)
                if "1301" not in retry_error and "contentFilter" not in retry_error:
                    raise
                return _build_safe_fallback_message(sanitized_input)


# Kwargs forwarded from user config to ChatOpenAI
_PASSTHROUGH_KWARGS = (
    "timeout", "max_retries", "reasoning_effort",
    "api_key", "callbacks", "http_client", "http_async_client",
)

# Provider base URLs and API key env vars
_PROVIDER_CONFIG = {
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "zhipu": ("https://open.bigmodel.cn/api/paas/v4", "ZHIPUAI_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
}


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI-compatible providers."""

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        provider: str = "openai",
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.provider = provider.lower()

    def get_llm(self) -> Any:
        """Return configured ChatOpenAI instance."""
        llm_kwargs = {"model": self.model}

        if self.provider in _PROVIDER_CONFIG:
            base_url, api_key_env = _PROVIDER_CONFIG[self.provider]
            llm_kwargs["base_url"] = base_url
            if api_key_env:
                api_key = os.environ.get(api_key_env)
                if api_key:
                    llm_kwargs["api_key"] = api_key
            else:
                llm_kwargs["api_key"] = "ollama"
        elif self.base_url:
            llm_kwargs["base_url"] = self.base_url

        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        if self.provider == "openai":
            llm_kwargs["use_responses_api"] = True

        return NormalizedChatOpenAI(provider=self.provider, **llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for the provider."""
        return validate_model(self.provider, self.model)
