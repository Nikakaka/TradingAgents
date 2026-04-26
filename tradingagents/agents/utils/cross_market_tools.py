"""
Cross-market stock data tools for LangGraph agents.

This module provides tools for agents to fetch data from multiple markets
for stocks that are dual-listed (e.g., A+H shares, HK+US ADRs).
"""

from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.cross_market_mapping import (
    get_cross_market_tickers,
    get_cross_market_summary,
    has_cross_market_listing,
)
from tradingagents.dataflows.interface import route_to_vendor
import logging

logger = logging.getLogger(__name__)


@tool
def get_cross_market_listings(
    symbol: Annotated[str, "股票代码"],
) -> str:
    """
    获取股票在多个市场的上市情况。

    对于跨市场上市的股票，返回其在A股、港股、美股的对应代码。
    例如：阿里巴巴在港股代码为09988.HK，美股代码为BABA。

    参数：
        symbol (str): 股票代码，如 600519.SH、0700.HK、BABA

    返回：
        str: 跨市场上市信息，包含各市场对应的股票代码
    """
    return get_cross_market_summary(symbol)


@tool
def check_dual_listing(
    symbol: Annotated[str, "股票代码"],
) -> str:
    """
    检查股票是否在多个市场上市。

    参数：
        symbol (str): 股票代码

    返回：
        str: 是否跨市场上市的说明
    """
    tickers = get_cross_market_tickers(symbol)
    markets = []
    if tickers.get("cn_a"):
        markets.append(f"A股({tickers['cn_a']})")
    if tickers.get("hk"):
        markets.append(f"港股({tickers['hk']})")
    if tickers.get("us"):
        markets.append(f"美股({tickers['us']})")

    if len(markets) > 1:
        return f"股票 {symbol} 在多个市场上市: {'、'.join(markets)}。建议获取其他市场的行情数据进行综合分析。"
    else:
        return f"股票 {symbol} 仅在单一市场上市，无需跨市场分析。"


@tool
def get_cross_market_stock_data(
    symbol: Annotated[str, "股票代码"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"],
) -> str:
    """
    获取跨市场上市股票在所有市场的行情数据。

    如果股票在多个市场上市（如A+H股、港股+美股），则同时获取
    各市场的历史行情数据，以便进行综合分析。

    参数：
        symbol (str): 股票代码，如 600519.SH、0700.HK、BABA
        start_date (str): 开始日期
        end_date (str): 结束日期

    返回：
        str: 所有市场的行情数据报告
    """
    tickers = get_cross_market_tickers(symbol)
    results = []
    company_name = tickers.get("name") or symbol

    # Header with cross-market info
    results.append(f"=== {company_name} 跨市场行情数据 ===")
    results.append("")

    markets_to_fetch = []
    if tickers.get("hk"):
        markets_to_fetch.append(("港股", tickers["hk"]))
    if tickers.get("cn_a"):
        markets_to_fetch.append(("A股", tickers["cn_a"]))
    if tickers.get("us"):
        markets_to_fetch.append(("美股", tickers["us"]))

    if len(markets_to_fetch) <= 1:
        # Single market - just fetch the data normally
        return route_to_vendor("get_stock_data", symbol, start_date, end_date)

    # Fetch data from all markets
    for market_name, ticker in markets_to_fetch:
        results.append(f"--- {market_name} ({ticker}) ---")
        try:
            data = route_to_vendor("get_stock_data", ticker, start_date, end_date)
            if isinstance(data, str) and ("失败" in data or "error" in data.lower()):
                results.append(f"数据获取失败: {data[:200]}")
            else:
                results.append(str(data))
        except Exception as e:
            results.append(f"获取{market_name}数据时出错: {e}")
        results.append("")

    return "\n".join(results)


@tool
def get_cross_market_comparison(
    symbol: Annotated[str, "股票代码"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"],
) -> str:
    """
    获取跨市场上市股票的价格对比分析。

    对于在多个市场上市的股票，获取各市场的行情数据并进行对比分析，
    包括价格差异、折溢价情况、交易活跃度对比等。

    参数：
        symbol (str): 股票代码
        start_date (str): 开始日期
        end_date (str): 结束日期

    返回：
        str: 跨市场价格对比分析报告
    """
    tickers = get_cross_market_tickers(symbol)
    results = []
    company_name = tickers.get("name") or symbol

    results.append(f"=== {company_name} 跨市场对比分析 ===")
    results.append("")

    # Check if dual-listed
    markets = []
    if tickers.get("hk"):
        markets.append(("港股", tickers["hk"]))
    if tickers.get("cn_a"):
        markets.append(("A股", tickers["cn_a"]))
    if tickers.get("us"):
        markets.append(("美股", tickers["us"]))

    if len(markets) <= 1:
        return f"股票 {symbol} 仅在单一市场上市，无法进行跨市场对比分析。"

    # List all markets
    results.append("上市市场:")
    for market_name, ticker in markets:
        results.append(f"  - {market_name}: {ticker}")
    results.append("")

    # Fetch and compare data
    market_data = {}
    for market_name, ticker in markets:
        try:
            data = route_to_vendor("get_stock_data", ticker, start_date, end_date)
            market_data[market_name] = data
        except Exception as e:
            logger.warning(f"Failed to fetch {market_name} data: {e}")

    # Compare section
    results.append("=== 数据获取结果 ===")
    for market_name, ticker in markets:
        if market_name in market_data:
            data = market_data[market_name]
            if isinstance(data, str) and ("失败" not in data and "error" not in data.lower()):
                results.append(f"✓ {market_name} ({ticker}): 数据获取成功")
            else:
                results.append(f"✗ {market_name} ({ticker}): 数据获取失败")
        else:
            results.append(f"✗ {market_name} ({ticker}): 数据未获取")

    results.append("")
    results.append("=== 分析建议 ===")
    results.append("请结合上述各市场的行情数据进行综合分析：")

    if tickers.get("cn_a") and tickers.get("hk"):
        results.append("1. A股与港股价格对比：关注AH股溢价率，分析两地市场估值差异")
        results.append("2. 资金流向分析：观察北向资金/南向资金的流向变化")
        results.append("3. 交易时段差异：A股与港股交易时间部分重叠，注意价格传导效应")

    if tickers.get("hk") and tickers.get("us"):
        results.append("1. 港股与美股价格对比：关注ADR溢价/折价情况")
        results.append("2. 时差影响：美股收盘后对港股次日开盘的影响")
        results.append("3. 交易量对比：分析不同市场的投资者偏好")

    results.append("")
    results.append("=== 详细数据 ===")
    for market_name, ticker in markets:
        results.append(f"\n--- {market_name} ({ticker}) ---")
        if market_name in market_data:
            results.append(str(market_data[market_name]))
        else:
            results.append("数据获取失败")

    return "\n".join(results)
