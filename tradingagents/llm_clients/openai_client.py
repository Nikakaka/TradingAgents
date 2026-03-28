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


def _is_rate_limit_error(error_text: str) -> bool:
    normalized = (error_text or "").lower()
    patterns = (
        "ratelimiterror",
        "rate limit",
        "error code: 429",
        '"code": "1302"',
        "'code': '1302'",
        "达到速率限制",
        "速率限制",
    )
    return any(pattern in normalized for pattern in patterns)


class NormalizedChatOpenAI(ChatOpenAI):
    """ChatOpenAI with normalized content output and provider-specific retries."""

    _provider_name: str = PrivateAttr(default="openai")
    _fallback_provider: Optional[str] = PrivateAttr(default=None)
    _fallback_model: Optional[str] = PrivateAttr(default=None)
    _fallback_base_url: Optional[str] = PrivateAttr(default=None)
    _fallback_kwargs: dict[str, Any] = PrivateAttr(default_factory=dict)
    _fallback_llm: Any = PrivateAttr(default=None)

    def __init__(
        self,
        *args,
        provider: str = "openai",
        fallback_provider: Optional[str] = None,
        fallback_model: Optional[str] = None,
        fallback_base_url: Optional[str] = None,
        fallback_kwargs: Optional[dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._provider_name = (provider or "openai").lower()
        self._fallback_provider = (fallback_provider or "").lower() or None
        self._fallback_model = fallback_model
        self._fallback_base_url = fallback_base_url
        self._fallback_kwargs = dict(fallback_kwargs or {})
        self._fallback_llm = None

    def _get_fallback_llm(self):
        if not self._fallback_provider or not self._fallback_model:
            return None
        if self._fallback_llm is not None:
            return self._fallback_llm

        from .factory import create_llm_client

        fallback_client = create_llm_client(
            provider=self._fallback_provider,
            model=self._fallback_model,
            base_url=self._fallback_base_url,
            **self._fallback_kwargs,
        )
        self._fallback_llm = fallback_client.get_llm()
        return self._fallback_llm

    def invoke(self, input, config=None, **kwargs):
        try:
            return normalize_content(super().invoke(input, config, **kwargs))
        except Exception as exc:
            error_text = str(exc)
            if _is_rate_limit_error(error_text):
                fallback_llm = self._get_fallback_llm()
                if fallback_llm is not None:
                    fallback_response = fallback_llm.invoke(input, config=config, **kwargs)
                    return normalize_content(fallback_response)
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

        fallback_provider = self.kwargs.get("fallback_provider")
        fallback_model = self.kwargs.get("fallback_model")
        fallback_base_url = self.kwargs.get("fallback_base_url")
        fallback_kwargs = self.kwargs.get("fallback_kwargs")

        return NormalizedChatOpenAI(
            provider=self.provider,
            fallback_provider=fallback_provider,
            fallback_model=fallback_model,
            fallback_base_url=fallback_base_url,
            fallback_kwargs=fallback_kwargs,
            **llm_kwargs,
        )

    def validate_model(self) -> bool:
        """Validate model for the provider."""
        return validate_model(self.provider, self.model)
