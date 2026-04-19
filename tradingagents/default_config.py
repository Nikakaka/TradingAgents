import os

from tradingagents.model_registry import get_provider_defaults

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

_MODEL_DEFAULTS = get_provider_defaults()
_FALLBACK_MODEL_DEFAULTS = get_provider_defaults("ollama")

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
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
    # OpenAI-compatible API timeout (for JD, OpenAI, xAI, etc.)
    "openai_timeout": 300,  # 5 minutes per request
    "openai_max_retries": 2,
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 800,  # Increased for depth=3 analysis with multiple stocks and complex debates
    # Data vendor configuration - optimized for China A-shares and Hong Kong stocks
    # Category-level configuration (default for all tools in category)
    # ifind: 同花顺iFinD (付费，数据最全面，支持资金流向)
    # efinance: EastMoney (best for China A-shares, stable and free)
    # sina: Free, no rate limit, HK real-time quotes
    # akshare: A-share/HK data (free, comprehensive)
    # Note: iFinD requires IFIND_REFRESH_TOKEN or IFIND_USERNAME/IFIND_PASSWORD env vars
    "data_vendors": {
        # 核心行情数据：ifind(付费) > efinance(A股) > sina(港股) > akshare > yfinance
        "core_stock_apis": "ifind,efinance,sina,akshare,yfinance",
        # 技术指标：efinance(A股) > akshare > yfinance
        # Note: ifind does not support technical indicators, only financial indicators
        "technical_indicators": "efinance,akshare,yfinance",
        # 基本面数据：ifind(付费) > akshare(最全面) > yfinance
        "fundamental_data": "ifind,akshare,yfinance",
        # 新闻数据：akshare(东方财富中文新闻) > yfinance
        "news_data": "akshare,yfinance",
        # 资金流向：仅ifind支持
        "capital_flow": "ifind",
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # 港股行情优先使用 sina（无速率限制）
        # "get_stock_data": "sina",  # Override for HK stocks
    },
}
