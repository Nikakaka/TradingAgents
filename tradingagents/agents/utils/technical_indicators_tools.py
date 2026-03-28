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
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    """
    Retrieve a single technical indicator for a given ticker symbol.
    Uses the configured technical_indicators vendor.
    Args:
        symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
        indicator (str): A single technical indicator name, e.g. 'rsi', 'macd'. Call this tool once per indicator.
        curr_date (str): The current trading date you are trading on, YYYY-mm-dd
        look_back_days (int): How many days to look back, default is 30
    Returns:
        str: A formatted dataframe containing the technical indicators for the specified ticker symbol and indicator.
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
