import os
import urllib.request
from datetime import datetime
import httpx
import re

# Disable system proxy for akshare data fetching
# This fixes connection issues when Windows proxy settings point to a non-working proxy
# (e.g., Clash/V2Ray that is not running)
def _disable_system_proxy():
    """Disable system proxy settings that may interfere with data fetching."""
    # Clear environment variables
    for key in list(os.environ.keys()):
        if 'proxy' in key.lower() and key.upper() not in ['NO_PROXY']:
            del os.environ[key]

    # Install a proxy handler that bypasses all proxies for urllib
    no_proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(no_proxy_handler)
    urllib.request.install_opener(opener)

    # Also disable proxy for requests library (used by akshare internally)
    os.environ['NO_PROXY'] = '*'
    os.environ['no_proxy'] = '*'

    # Disable requests library from reading system proxy settings
    import requests
    requests.Session.trust_env = False


# Disable proxy on module load
_disable_system_proxy()

import akshare as ak
import pandas as pd
from stockstats import wrap

from tradingagents.market_utils import get_market_info

# Tencent Finance API as fallback for A-shares
_TENCENT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://gu.qq.com/',
}


def _get_cn_stock_data_tencent(symbol: str, start_date: str, end_date: str) -> str:
    """Fallback: Get A-share data from Tencent Finance API."""
    info = get_market_info(symbol)

    # Tencent uses different prefixes for Shanghai/Shenzhen
    if info.market == "cn_a":
        code = info.akshare_symbol or symbol.split('.')[0]
        if code.startswith('6'):
            tencent_symbol = f"sh{code}"
        else:
            tencent_symbol = f"sz{code}"
    else:
        raise ValueError(f"Tencent Finance only supports A-shares, got: {symbol}")

    # Tencent real-time quote API
    url = f"https://web.sqt.gtimg.cn/q={tencent_symbol}"

    try:
        response = httpx.get(url, headers=_TENCENT_HEADERS, timeout=15)
        response.raise_for_status()

        # Parse response: v_sh600519="1~贵州茅台~600519~1460.00~..."
        text = response.text
        if '~' not in text:
            return f"No data found for {symbol} from Tencent"

        # Extract data fields
        parts = text.split('~')
        if len(parts) < 35:
            return f"Invalid data format for {symbol} from Tencent"

        # Field mapping (Tencent format):
        # [0] prefix, [1] unknown, [2] name, [3] code, [4] price, [5] yesterday_close
        # [6] open, [7] volume, [8] turnover, [9] buy1, [10] sell1
        name = parts[1] if len(parts) > 1 else ''
        code = parts[2] if len(parts) > 2 else ''
        price = float(parts[3]) if len(parts) > 3 and parts[3] else 0
        prev_close = float(parts[4]) if len(parts) > 4 and parts[4] else 0
        open_price = float(parts[5]) if len(parts) > 5 and parts[5] else 0
        volume = float(parts[6]) if len(parts) > 6 and parts[6] else 0
        high = float(parts[33]) if len(parts) > 33 and parts[33] else price
        low = float(parts[34]) if len(parts) > 34 and parts[34] else price

        # Build CSV output
        today = datetime.now().strftime('%Y-%m-%d')
        lines = [
            "Date,Open,High,Low,Close,Volume",
            f"{today},{open_price},{high},{low},{price},{int(volume)}"
        ]

        csv_string = "\n".join(lines)
        header = f"# Real-time stock data for {symbol.upper()} (Tencent Finance)\n"
        header += f"# Note: Showing real-time quote (historical data unavailable)\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        return f"Failed to retrieve data for {symbol} from Tencent: {str(e)}"


_CN_RENAME_MAP = {
    "日期": "Date",
    "开盘": "Open",
    "收盘": "Close",
    "最高": "High",
    "最低": "Low",
    "成交量": "Volume",
    "成交额": "Turnover",
    "振幅": "Amplitude",
    "涨跌幅": "ChangePercent",
    "涨跌额": "ChangeAmount",
    "换手率": "TurnoverRate",
}


def _normalize_cn_symbol(symbol: str) -> str:
    info = get_market_info(symbol)
    if info.market != "cn_a" or not info.akshare_symbol:
        raise ValueError(f"Akshare A-share data source only supports China A-share tickers, got: {symbol}")
    return info.akshare_symbol


def _fetch_cn_hist_df(symbol: str) -> pd.DataFrame:
    cn_symbol = _normalize_cn_symbol(symbol)
    df = ak.stock_zh_a_hist(symbol=cn_symbol, period="daily", adjust="qfq")
    if df is None or df.empty:
        raise RuntimeError(f"No Akshare A-share data found for symbol '{symbol}'")
    return df.copy()


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = df.rename(columns=_CN_RENAME_MAP)
    required_columns = {"Date", "Open", "High", "Low", "Close", "Volume"}
    missing = required_columns - set(renamed.columns)
    if missing:
        raise RuntimeError(f"Unexpected Akshare A-share columns: missing {sorted(missing)}")
    return renamed


def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Retrieve A-share OHLCV data from Akshare with Tencent fallback."""
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    # Try Akshare first
    try:
        df = _rename_columns(_fetch_cn_hist_df(symbol))
        df["Date"] = pd.to_datetime(df["Date"])
        filtered = df[(df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))]

        if filtered.empty:
            return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

        csv_string = filtered.to_csv(index=False)
        header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
        header += f"# Total records: {len(filtered)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + csv_string

    except Exception as e:
        # Fallback to Tencent Finance for real-time data
        import warnings
        warnings.warn(f"Akshare failed for {symbol}: {e}. Falling back to Tencent Finance.")
        return _get_cn_stock_data_tencent(symbol, start_date, end_date)
    filtered = df[(df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))]

    if filtered.empty:
        return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

    csv_string = filtered.to_csv(index=False)
    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(filtered)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + csv_string


def get_indicator(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
    """Calculate technical indicators from Akshare A-share historical data.

    Note: If Akshare is unavailable, returns a message indicating limited functionality.
    """
    supported = {
        "close_50_sma",
        "close_200_sma",
        "close_10_ema",
        "macd",
        "macds",
        "macdh",
        "rsi",
        "boll",
        "boll_ub",
        "boll_lb",
        "atr",
        "vwma",
        "mfi",
    }
    if indicator not in supported:
        raise ValueError(f"Indicator {indicator} is not supported by Akshare fallback")

    try:
        curr_dt = pd.to_datetime(curr_date)
        start_dt = curr_dt - pd.Timedelta(days=look_back_days)

        df = _rename_columns(_fetch_cn_hist_df(symbol))
        df["Date"] = pd.to_datetime(df["Date"])
        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].copy().sort_values("Date")

        stats_df = wrap(df)
        stats_df["Date"] = pd.to_datetime(stats_df["Date"])
        stats_df[indicator]

        rows = []
        cursor = curr_dt
        while cursor >= start_dt:
            match = stats_df[stats_df["Date"] == cursor]
            if not match.empty:
                value = match.iloc[0][indicator]
                value = "N/A" if pd.isna(value) else f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
            else:
                value = "N/A: Not a trading day (weekend or holiday)"
            rows.append(f"{cursor.strftime('%Y-%m-%d')}: {value}")
            cursor -= pd.Timedelta(days=1)

        return (
            f"## {indicator} values from {start_dt.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
            + "\n".join(rows)
        )

    except Exception as e:
        # Fallback: return message about limited functionality
        return (
            f"## {indicator} values for {symbol}:\n\n"
            f"Technical indicator data is temporarily unavailable due to data source connectivity issues.\n"
            f"The primary data source (Akshare/EastMoney) is not responding, and the fallback (Tencent Finance) "
            f"only provides real-time quotes without historical data needed for indicator calculation.\n\n"
            f"Error: {str(e)}\n\n"
            f"Please try again later or use an alternative analysis approach."
        )
