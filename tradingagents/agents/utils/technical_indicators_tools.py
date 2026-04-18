from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor

INDICATOR_ALIASES = {
    "sma": "close_50_sma",
    "ma": "close_50_sma",
    "50sma": "close_50_sma",
    "200sma": "close_200_sma",
    "ema": "close_10_ema",
    "10ema": "close_10_ema",
    "bollinger": "boll",
    "bollinger_bands": "boll",
    "boll_upper": "boll_ub",
    "boll_lower": "boll_lb",
    "macd_signal": "macds",
    "macd_hist": "macdh",
    "histogram": "macdh",
    "volume_weighted_ma": "vwma",
    "obv": "vwma",
    "on_balance_volume": "vwma",
}


def normalize_indicator_name(indicator: str) -> str:
    normalized = (indicator or "").strip().lower()
    return INDICATOR_ALIASES.get(normalized, normalized)


@tool
def get_indicators(
    symbol: Annotated[str, "股票代码"],
    indicator: Annotated[str, "技术指标名称"],
    curr_date: Annotated[str, "当前交易日期，格式：yyyy-mm-dd"],
    look_back_days: Annotated[int, "回看天数"] = 30,
) -> str:
    """
    获取股票的单一技术指标数据。
    适用于A股和港股的技术分析。
    参数：
        symbol (str): 股票代码，如 600519.SH、0700.HK
        indicator (str): 单个技术指标名称，如 'rsi'、'macd'、'boll'。每次调用只查询一个指标。
        curr_date (str): 当前交易日期，格式：yyyy-mm-dd
        look_back_days (int): 回看天数，默认30天
    返回：
        str: 包含指定技术指标数据的格式化报告

    支持的技术指标列表：
    - close_50_sma: 50日简单移动平均线
    - close_200_sma: 200日简单移动平均线
    - close_10_ema: 10日指数移动平均线
    - macd: MACD指标
    - macds: MACD信号线
    - macdh: MACD柱状图
    - rsi: 相对强弱指数
    - boll: 布林带中轨
    - boll_ub: 布林带上轨
    - boll_lb: 布林带下轨
    - atr: 平均真实波幅
    - vwma: 成交量加权移动平均线
    - mfi: 资金流量指标
    """
    # LLMs sometimes pass multiple indicators as a comma-separated string;
    # split and process each individually.
    indicators = [normalize_indicator_name(i) for i in indicator.split(",") if i.strip()]
    if len(indicators) > 1:
        results = []
        for ind in indicators:
            results.append(route_to_vendor("get_indicators", symbol, ind, curr_date, look_back_days))
        return "\n\n".join(results)
    return route_to_vendor("get_indicators", symbol, normalize_indicator_name(indicator), curr_date, look_back_days)
