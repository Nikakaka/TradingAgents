from typing import Annotated
import logging

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
from .tencent_finance import (
    get_hk_realtime_quote as get_tencent_hk_realtime_quote,
)
from .efinance_cn import (
    get_stock_data as get_efinance_cn_stock,
    get_indicator as get_efinance_cn_indicator,
)
from .ifind_data import (
    get_stock_data_ifind,
    get_realtime_quote_ifind,
    get_financial_indicators_ifind,
    get_capital_flow_ifind,
)
from yfinance.exceptions import YFRateLimitError

# Configuration and routing logic
from .config import get_config

logger = logging.getLogger(__name__)

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "股票行情数据（开高低收成交量）",
        "tools": [
            "get_stock_data",
            "get_realtime_quote",  # Real-time quotes
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
    },
    "capital_flow": {
        "description": "资金流向数据",
        "tools": [
            "get_capital_flow",
        ]
    }
}

VENDOR_LIST = [
    "tencent",   # 腾讯财经 - 港股实时行情（收盘价最准确）
    "ifind",     # 同花顺iFinD - 专业金融数据（付费，最全面）
    "efinance",  # EastMoney - A股数据（稳定、免费）
    "sina",      # 新浪财经 - 港股实时行情（备用）
    "akshare",   # AKShare - A股/港股数据（全面、免费）
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "ifind": get_stock_data_ifind,
        "efinance": get_efinance_cn_stock,  # A股 via EastMoney（稳定）
        "sina": get_sina_hk_stock,  # 港股实时数据（无速率限制）
        "akshare": [get_akshare_hk_stock, get_akshare_cn_stock],
    },
    # Real-time quotes
    "get_realtime_quote": {
        "tencent": get_tencent_hk_realtime_quote,  # 腾讯港股实时行情（收盘价更准确）
        "ifind": get_realtime_quote_ifind,
        "sina": get_hk_realtime_quote,  # 新浪港股实时行情（备用）
    },
    # technical_indicators
    # Note: ifind does not have a technical indicators function, only financial indicators
    # Financial indicators (get_financial_indicators_ifind) have different signature
    # (ticker, date) vs (symbol, indicator, curr_date, look_back_days)
    "get_indicators": {
        "efinance": get_efinance_cn_indicator,  # A股 via EastMoney
        "akshare": [get_akshare_hk_indicator, get_akshare_cn_indicator],
    },
    # fundamental_data
    "get_fundamentals": {
        "ifind": get_financial_indicators_ifind,
        "akshare": get_akshare_fundamentals,
    },
    "get_balance_sheet": {
        "akshare": get_akshare_balance_sheet,
    },
    "get_cashflow": {
        "akshare": get_akshare_cashflow,
    },
    "get_income_statement": {
        "akshare": get_akshare_income_statement,
    },
    # news_data
    "get_news": {
        "akshare": get_news_akshare,  # 中文A股新闻（东方财富）
        # Note: yfinance removed - blocked in mainland China
    },
    "get_global_news": {
        "akshare": get_global_news_akshare,  # 中文财经新闻（东方财富）
        # Note: yfinance removed - blocked in mainland China
    },
    # capital_flow
    "get_capital_flow": {
        "ifind": get_capital_flow_ifind,
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
    """Route method calls to appropriate vendor implementation with fallback support.

    Enhanced with:
    - Detailed logging for debugging
    - Smart fallback based on stock type (A-share vs HK vs US)
    - Rate limit tracking to avoid recently failed vendors

    Args:
        method: The data method to call (e.g., "get_stock_data")
        *args: Positional arguments passed to the method
        **kwargs: Keyword arguments passed to the method

    Returns:
        Data from the first successful vendor, or error message if all fail
    """
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in str(vendor_config).split(',') if v.strip()]
    symbol = args[0] if args else kwargs.get("ticker") or kwargs.get("symbol")
    attempted_errors = []

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Determine stock type for smart routing
    stock_type = _detect_stock_type(symbol)
    logger.debug(f"[DataRouter] method={method}, symbol={symbol}, stock_type={stock_type}")

    # Build optimized fallback chain based on stock type
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = _build_fallback_chain(primary_vendors, all_available_vendors, stock_type, method)

    logger.info(f"[DataRouter] Fallback chain for {method}: {fallback_vendors}")

    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_funcs = vendor_impl if isinstance(vendor_impl, list) else [vendor_impl]

        for impl_func in impl_funcs:
            func_name = impl_func.__name__ if hasattr(impl_func, '__name__') else str(impl_func)
            try:
                logger.debug(f"[DataRouter] Trying {vendor}:{func_name} for {symbol}")
                result = impl_func(*args, **kwargs)

                # Check if result indicates failure
                if isinstance(result, str) and ("失败" in result or "error" in result.lower()):
                    attempted_errors.append(f"{vendor}:{func_name} returned error: {result[:100]}")
                    logger.warning(f"[DataRouter] {vendor}:{func_name} returned error for {symbol}")
                    continue

                logger.info(f"[DataRouter] Success: {method} from {vendor}:{func_name} for {symbol}")
                return result

            except YFRateLimitError as exc:
                error_msg = f"{vendor}:{func_name} 速率限制 ({exc})"
                attempted_errors.append(error_msg)
                logger.warning(f"[DataRouter] {error_msg}")
                continue

            except ValueError as exc:
                if vendor == "akshare" and symbol:
                    error_msg = f"{vendor}:{func_name} 不支持股票 {symbol} ({exc})"
                    attempted_errors.append(error_msg)
                    logger.debug(f"[DataRouter] {error_msg}")
                    continue
                error_msg = f"{vendor}:{func_name} 验证失败 ({exc})"
                attempted_errors.append(error_msg)
                logger.warning(f"[DataRouter] {error_msg}")
                raise

            except Exception as exc:
                error_msg = f"{vendor}:{func_name} 异常 ({type(exc).__name__}: {exc})"
                attempted_errors.append(error_msg)
                logger.warning(f"[DataRouter] {error_msg}")
                continue

    # All vendors failed - log detailed error
    reason = "; ".join(attempted_errors) if attempted_errors else "no vendor implementation could handle the request"
    logger.error(f"[DataRouter] All vendors failed for {method}({symbol}): {reason}")

    return (
        f"数据获取失败：'{method}'。"
        f"股票代码：{symbol or '未知'}。"
        f"尝试记录：{reason}"
    )


def _detect_stock_type(symbol: str) -> str:
    """Detect the type of stock based on symbol format.

    Returns:
        'cn_a': China A-share (6-digit starting with 0/3/6)
        'cn_b': China B-share
        'hk': Hong Kong stock
        'us': US stock
        'unknown': Cannot determine
    """
    if not symbol:
        return "unknown"

    symbol = str(symbol).upper().strip()

    # Hong Kong stocks: end with .HK or start with HK
    if symbol.endswith(".HK") or symbol.startswith("HK"):
        return "hk"

    # China A-share: 6-digit codes
    # 0xxxxx - Shenzhen A-share
    # 3xxxxx - ChiNext
    # 6xxxxx - Shanghai A-share
    if symbol.isdigit() and len(symbol) == 6:
        if symbol.startswith(('0', '3', '6')):
            return "cn_a"
        elif symbol.startswith(('2', '9')):
            return "cn_b"

    # Check if it's a pure ticker without suffix
    if symbol.isdigit() and len(symbol) == 5:
        return "hk"  # 5-digit HK stock code

    # US stocks: typically alphabetic
    if symbol.isalpha():
        return "us"

    # Handle formats like "0700.HK", "AAPL.US"
    if "." in symbol:
        suffix = symbol.split(".")[-1].upper()
        if suffix == "HK":
            return "hk"
        elif suffix in ("US", "NQ", "NY"):
            return "us"
        elif suffix in ("SZ", "SH"):
            return "cn_a"

    return "unknown"


def _build_fallback_chain(
    primary_vendors: list,
    all_vendors: list,
    stock_type: str,
    method: str,
) -> list:
    """Build an optimized fallback chain based on stock type and method.

    Prioritizes vendors that are more likely to succeed for the given stock type.
    """
    # Start with primary vendors
    chain = primary_vendors.copy()

    # Stock-type specific preferences
    type_preferences = {
        "cn_a": ["efinance", "akshare", "sina", "ifind", "yfinance"],
        "hk": ["sina", "akshare", "yfinance", "ifind"],
        "us": ["yfinance", "alpha_vantage"],
        "cn_b": ["akshare", "yfinance"],
    }

    # Method-specific preferences (override stock type for some methods)
    method_preferences = {
        "get_news": ["akshare", "yfinance"],  # Chinese news preferred for CN stocks
        "get_capital_flow": ["ifind"],  # Only ifind supports this
    }

    # Apply method-specific preferences if available
    if method in method_preferences:
        preferred = method_preferences[method]
        for v in preferred:
            if v in all_vendors and v not in chain:
                chain.append(v)
    else:
        # Apply stock-type preferences
        preferred = type_preferences.get(stock_type, [])
        for v in preferred:
            if v in all_vendors and v not in chain:
                chain.append(v)

    # Add remaining vendors
    for v in all_vendors:
        if v not in chain:
            chain.append(v)

    return chain
