from copy import deepcopy


DEFAULT_PROVIDER = "jd"

PROVIDER_SPECS = {
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key_label": "OpenAI API Key",
        "api_key_placeholder": "输入 OPENAI_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的 OpenAI Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
        "models": {
            "quick": ["gpt-5-mini", "gpt-5-nano", "gpt-5.4", "gpt-4.1"],
            "deep": ["gpt-5.4", "gpt-5.2", "gpt-5-mini", "gpt-5.4-pro"],
        },
        "defaults": {
            "quick": "gpt-5-mini",
            "deep": "gpt-5.4",
        },
    },
    "google": {
        "label": "Google",
        "base_url": "https://generativelanguage.googleapis.com/v1",
        "api_key_label": "Google API Key",
        "api_key_placeholder": "输入 GOOGLE_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的 Google Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
        "models": {
            "quick": ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-3.1-flash-lite-preview", "gemini-2.5-flash-lite"],
            "deep": ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash"],
        },
        "defaults": {
            "quick": "gemini-3-flash-preview",
            "deep": "gemini-3.1-pro-preview",
        },
    },
    "anthropic": {
        "label": "Anthropic",
        "base_url": "https://api.anthropic.com/",
        "api_key_label": "Anthropic API Key",
        "api_key_placeholder": "输入 ANTHROPIC_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的 Anthropic Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
        "models": {
            "quick": ["claude-sonnet-4-6", "claude-haiku-4-5", "claude-sonnet-4-5"],
            "deep": ["claude-opus-4-6", "claude-opus-4-5", "claude-sonnet-4-6", "claude-sonnet-4-5"],
        },
        "defaults": {
            "quick": "claude-sonnet-4-6",
            "deep": "claude-opus-4-6",
        },
    },
    "xai": {
        "label": "xAI",
        "base_url": "https://api.x.ai/v1",
        "api_key_label": "xAI API Key",
        "api_key_placeholder": "输入 XAI_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的 xAI Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
        "models": {
            "quick": ["grok-4-1-fast-non-reasoning", "grok-4-fast-non-reasoning", "grok-4-1-fast-reasoning"],
            "deep": ["grok-4-0709", "grok-4-1-fast-reasoning", "grok-4-fast-reasoning", "grok-4-1-fast-non-reasoning"],
        },
        "defaults": {
            "quick": "grok-4-1-fast-non-reasoning",
            "deep": "grok-4-0709",
        },
    },
    "zhipu": {
        "label": "Zhipu GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_label": "智谱 API Key",
        "api_key_placeholder": "输入 ZHIPUAI_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的智谱 Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
        "models": {
            "quick": ["GLM-4.5-Air", "GLM-4.7"],
            "deep": ["GLM-4.7", "GLM-4.5", "GLM-4.5-Air"],
        },
        "defaults": {
            "quick": "GLM-4.5-Air",
            "deep": "GLM-4.7",
        },
        "valid_models": ["GLM-4.7", "GLM-4.5", "GLM-4.5-Air", "GLM-4-Air-250414"],
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_label": "OpenRouter API Key",
        "api_key_placeholder": "输入 OPENROUTER_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的 OpenRouter Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
        "models": {
            "quick": ["z-ai/glm-4.5-air:free", "nvidia/nemotron-3-nano-30b-a3b:free"],
            "deep": ["z-ai/glm-4.5-air:free", "nvidia/nemotron-3-nano-30b-a3b:free"],
        },
        "defaults": {
            "quick": "z-ai/glm-4.5-air:free",
            "deep": "z-ai/glm-4.5-air:free",
        },
    },
    "ollama": {
        "label": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "api_key_label": "Ollama 无需 API Key",
        "api_key_placeholder": "",
        "api_key_helper": "本地 Ollama 连接默认不需要 API Key。",
        "requires_api_key": False,
        "models": {
            "quick": ["glm-4.7-flash:latest", "gpt-oss:latest", "qwen3:latest"],
            "deep": ["glm-4.7-flash:latest", "gpt-oss:latest", "qwen3:latest"],
        },
        "defaults": {
            "quick": "glm-4.7-flash:latest",
            "deep": "glm-4.7-flash:latest",
        },
    },
    "jd": {
        "label": "jd",
        "base_url": "https://modelservice.jdcloud.com/coding/openai/v1",
        "api_key_label": "JD API Key",
        "api_key_placeholder": "输入 JD_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的 JD Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
        "models": {
            "quick": ["MiniMax-M2.5"],
            "deep": ["GLM-5"],
        },
        "defaults": {
            "quick": "MiniMax-M2.5",
            "deep": "GLM-5",
        },
    }
}


def list_provider_options() -> list[dict]:
    return [
        {
            "id": provider,
            "label": spec["label"],
            "base_url": spec["base_url"],
            "api_key_label": spec["api_key_label"],
            "api_key_placeholder": spec["api_key_placeholder"],
            "api_key_helper": spec["api_key_helper"],
            "requires_api_key": spec["requires_api_key"],
        }
        for provider, spec in PROVIDER_SPECS.items()
    ]


def get_model_options(provider: str | None = None) -> dict:
    if provider:
        spec = PROVIDER_SPECS[provider]
        return deepcopy(spec["models"])
    return {name: deepcopy(spec["models"]) for name, spec in PROVIDER_SPECS.items()}


def get_provider_defaults(provider: str | None = None) -> dict[str, str]:
    selected_provider = (provider or DEFAULT_PROVIDER).lower()
    spec = PROVIDER_SPECS[selected_provider]
    return {
        "provider": selected_provider,
        "quick_model": spec["defaults"]["quick"],
        "deep_model": spec["defaults"]["deep"],
        "backend_url": spec["base_url"],
    }


def get_valid_models() -> dict[str, list[str]]:
    valid: dict[str, list[str]] = {}
    for provider, spec in PROVIDER_SPECS.items():
        models = []
        for group in ("quick", "deep"):
            for model in spec["models"].get(group, []):
                if model not in models:
                    models.append(model)
        for model in spec.get("valid_models", []):
            if model not in models:
                models.append(model)
        valid[provider] = models
    return valid
