import os

from tradingagents.model_registry import get_provider_defaults


_MODEL_DEFAULTS = get_provider_defaults()
_FALLBACK_MODEL_DEFAULTS = get_provider_defaults("ollama")

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": _MODEL_DEFAULTS["provider"],
    "deep_think_llm": _MODEL_DEFAULTS["deep_model"],
    "quick_think_llm": _MODEL_DEFAULTS["quick_model"],
    "backend_url": _MODEL_DEFAULTS["backend_url"],
    "rate_limit_fallback_enabled": True,
    "rate_limit_fallback_provider": _FALLBACK_MODEL_DEFAULTS["provider"],
    "rate_limit_fallback_quick_think_llm": _FALLBACK_MODEL_DEFAULTS["quick_model"],
    "rate_limit_fallback_deep_think_llm": _FALLBACK_MODEL_DEFAULTS["deep_model"],
    "rate_limit_fallback_backend_url": _FALLBACK_MODEL_DEFAULTS["backend_url"],
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    "ollama_timeout": 900,
    "ollama_connect_timeout": 15,
    "ollama_max_retries": 2,
    "ollama_retry_backoff": 2,
    "ollama_num_ctx": 8192,
    "ollama_num_predict": 900,
    "ollama_temperature": 0.2,
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 800,  # Increased for depth=3 analysis with multiple stocks and complex debates
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    # efinance: EastMoney (best for China A-shares, stable and free)
    # sina: Free, no rate limit, HK real-time quotes
    # yfinance: Broader coverage but rate limited
    # akshare: A-share data via baostock (free, but can be unstable)
    # alpha_vantage: US stocks only, requires API key
    "data_vendors": {
        "core_stock_apis": "efinance,sina,akshare,yfinance,alpha_vantage",
        "technical_indicators": "efinance,akshare,yfinance,alpha_vantage",
        "fundamental_data": "akshare,yfinance,alpha_vantage",
        "news_data": "akshare,yfinance,alpha_vantage",  # akshare first for Chinese A-shares
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Use sina for HK stocks (no rate limit)
        # "get_stock_data": "sina",  # Override for HK stocks
    },
}
