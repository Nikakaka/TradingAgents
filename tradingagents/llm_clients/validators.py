"""Model name validators for each provider.

Only validates model names - does NOT enforce limits.
Let LLM providers use their own defaults for unspecified params.
"""

from tradingagents.model_registry import get_valid_models


VALID_MODELS = get_valid_models()


def validate_model(provider: str, model: str) -> bool:
    """Check if model name is valid for the given provider.

    For ollama, openrouter - any model is accepted.
    """
    provider_lower = provider.lower()

    if provider_lower in ("ollama", "openrouter"):
        return True

    if provider_lower not in VALID_MODELS:
        return True

    return model in VALID_MODELS[provider_lower]
