import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": "zhipu",
    "deep_think_llm": "GLM-4.7",
    "quick_think_llm": "GLM-4.7",
    "backend_url": "https://open.bigmodel.cn/api/paas/v4",
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        # Prefer yfinance for broader exchange coverage (including HK suffixes),
        # then fall back to Alpha Vantage when configured.
        "core_stock_apis": "akshare,yfinance,alpha_vantage",
        "technical_indicators": "akshare,yfinance,alpha_vantage",
        "fundamental_data": "akshare,yfinance,alpha_vantage",
        "news_data": "yfinance,alpha_vantage",
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
}
