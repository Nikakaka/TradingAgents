from typing import Annotated

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .akshare_fundamentals import (
    get_fundamentals as get_akshare_fundamentals,
    get_balance_sheet as get_akshare_balance_sheet,
    get_cashflow as get_akshare_cashflow,
    get_income_statement as get_akshare_income_statement,
)
from .akshare_news import get_news_akshare, get_global_news_akshare
from .akshare_hk import (
    get_stock_data as get_akshare_hk_stock,
    get_indicator as get_akshare_hk_indicator,
)
from .akshare_cn import (
    get_stock_data as get_akshare_cn_stock,
    get_indicator as get_akshare_cn_indicator,
)
from .sina_finance import (
    get_stock_data as get_sina_hk_stock,
    get_hk_realtime_quote,
)
from .efinance_cn import (
    get_stock_data as get_efinance_cn_stock,
    get_indicator as get_efinance_cn_indicator,
)
from yfinance.exceptions import YFRateLimitError

# Configuration and routing logic
from .config import get_config

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "股票行情数据（开高低收成交量）",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "技术分析指标",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "公司基本面数据",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "新闻和内部人交易数据",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    }
}

VENDOR_LIST = [
    "efinance",  # EastMoney - A股数据（稳定、免费）
    "sina",      # 新浪财经 - 港股实时行情（无速率限制）
    "akshare",   # AKShare - A股/港股数据（全面、免费）
    "yfinance",  # Yahoo Finance - 通用数据（有速率限制）
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "efinance": get_efinance_cn_stock,  # A股 via EastMoney（稳定）
        "sina": get_sina_hk_stock,  # 港股实时数据（无速率限制）
        "akshare": [get_akshare_hk_stock, get_akshare_cn_stock],
        "yfinance": get_YFin_data_online,
    },
    # technical_indicators
    "get_indicators": {
        "efinance": get_efinance_cn_indicator,  # A股 via EastMoney
        "akshare": [get_akshare_hk_indicator, get_akshare_cn_indicator],
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "akshare": get_akshare_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "akshare": get_akshare_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "akshare": get_akshare_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "akshare": get_akshare_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "akshare": get_news_akshare,  # 中文A股新闻（东方财富）
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "akshare": get_global_news_akshare,  # 中文财经新闻（东方财富）
        "yfinance": get_global_news_yfinance,
    },
    "get_insider_transactions": {
        "yfinance": get_yfinance_insider_transactions,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in str(vendor_config).split(',') if v.strip()]
    symbol = args[0] if args else kwargs.get("ticker") or kwargs.get("symbol")
    attempted_errors = []

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Build fallback chain: primary vendors first, then remaining available vendors
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_funcs = vendor_impl if isinstance(vendor_impl, list) else [vendor_impl]

        for impl_func in impl_funcs:
            try:
                return impl_func(*args, **kwargs)
            except YFRateLimitError as exc:
                attempted_errors.append(f"{vendor}:{impl_func.__name__} 速率限制 ({exc})")
                continue
            except ValueError as exc:
                if vendor == "akshare" and symbol:
                    attempted_errors.append(f"{vendor}:{impl_func.__name__} 不支持股票 {symbol} ({exc})")
                    continue
                attempted_errors.append(f"{vendor}:{impl_func.__name__} 失败 ({exc})")
                raise
            except Exception as exc:
                attempted_errors.append(f"{vendor}:{impl_func.__name__} 失败 ({exc})")
                continue

    reason = "; ".join(attempted_errors) if attempted_errors else "no vendor implementation could handle the request"
    return (
        f"数据获取失败：'{method}'。"
        f"股票代码：{symbol or '未知'}。"
        f"尝试记录：{reason}"
    )
