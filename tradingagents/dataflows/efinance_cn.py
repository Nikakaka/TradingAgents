"""
Sina Finance data source for China A-shares.
Uses Sina Finance API for stable A-share real-time and historical data.

More reliable than EastMoney/efinance when network restrictions exist.
"""
import os
import sys

# Disable ALL proxies before importing any network libraries
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['ALL_PROXY'] = ''
os.environ['all_proxy'] = ''

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

import httpx
import pandas as pd
from datetime import datetime, timedelta
from typing import Annotated

from tradingagents.market_utils import get_market_info

# Common headers to avoid being blocked
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://finance.sina.com.cn/',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


def _normalize_cn_symbol(symbol: str) -> tuple[str, str]:
    """Convert exchange-qualified tickers to Sina format.

    Args:
        symbol: Stock ticker (e.g., "600519.SH", "300750.SZ")

    Returns:
        Tuple of (sina_symbol, market) where sina_symbol is like "sh600519" or "sz300750"
    """
    info = get_market_info(symbol)
    if info.market not in ("cn_a", "hk"):
        raise ValueError(f"Sina Finance only supports China A-shares and HK stocks, got: {symbol}")

    code = info.akshare_symbol or symbol.split('.')[0]

    # Shanghai stocks: sh prefix
    # Shenzhen stocks: sz prefix
    if info.market == "hk":
        # For HK stocks, use sina_hk format
        return f"hk{code}", "hk"
    elif code.startswith('6'):
        return f"sh{code}", "sh"
    else:
        return f"sz{code}", "sz"


def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Get A-share OHLCV data from Sina Finance.

    Args:
        symbol: Stock ticker (e.g., "600519.SH", "300750.SZ", "9988.HK")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        CSV string with Date, Open, High, Low, Close, Volume columns
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    info = get_market_info(symbol)
    code = info.akshare_symbol or symbol.split('.')[0]

    # For HK stocks, delegate to sina_finance which uses akshare for historical data
    if info.market == "hk":
        from .sina_finance import get_stock_data as get_hk_stock_data
        return get_hk_stock_data(symbol, start_date, end_date)

    try:
        # A-share stocks use Sina Finance API
        sina_symbol = f"sh{code}" if code.startswith('6') else f"sz{code}"

        # Calculate data length needed
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end_dt - start_dt).days + 1
        # Request more days to account for non-trading days
        datalen = min(max(days * 2, 30), 500)

        # Sina historical data API
        url = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
        params = {
            "symbol": sina_symbol,
            "scale": "240",  # Daily (240 minutes)
            "ma": "no",
            "datalen": str(datalen)
        }

        response = httpx.get(url, params=params, headers=_HEADERS, timeout=15)

        if response.status_code != 200:
            return _fallback_to_realtime(symbol, start_date, end_date)

        # Parse JSON response
        data = response.json()

        if not data or not isinstance(data, list):
            return _fallback_to_realtime(symbol, start_date, end_date)

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Rename columns
        df = df.rename(columns={
            'day': 'Date',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })

        # Select required columns
        required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        df = df[required_cols]

        # Filter by date range
        df['Date_dt'] = pd.to_datetime(df['Date'])
        df = df[(df['Date_dt'] >= start_dt) & (df['Date_dt'] <= end_dt)]
        df = df.drop(columns=['Date_dt'])

        # Sort by date ascending
        df = df.sort_values('Date')

        if df.empty:
            return _fallback_to_realtime(symbol, start_date, end_date)

        # Build CSV output
        csv_string = df.to_csv(index=False)
        header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
        header += f"# Source: Sina Finance\n"
        header += f"# Total records: {len(df)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        import warnings
        warnings.warn(f"Sina historical data failed for {symbol}: {e}. Falling back to real-time.")
        return _fallback_to_realtime(symbol, start_date, end_date)


def _fallback_to_realtime(symbol: str, start_date: str, end_date: str) -> str:
    """Fallback to real-time quote when historical data is unavailable."""
    info = get_market_info(symbol)
    code = info.akshare_symbol or symbol.split('.')[0]

    # Determine market prefix
    if info.market == "hk":
        sina_symbol = f"hk{code}"
    elif code.startswith('6'):
        sina_symbol = f"sh{code}"
    else:
        sina_symbol = f"sz{code}"

    # Sina real-time quote API
    url = f"https://hq.sinajs.cn/list={sina_symbol}"

    try:
        response = httpx.get(url, headers=_HEADERS, timeout=15)
        response.raise_for_status()

        text = response.text
        if 'var hq_str_' not in text:
            return f"No data found for {symbol} from Sina Finance"

        # Parse the data string
        start = text.find('"') + 1
        end = text.rfind('"')
        data_str = text[start:end]

        if not data_str:
            return f"Empty data for {symbol}"

        parts = data_str.split(',')
        if len(parts) < 6:
            return f"Invalid data format for {symbol}"

        # A-share format: name, open, prev_close, close, high, low, ...
        # Different from HK format!
        if info.market == "hk":
            # HK format: name_en, name_cn, open, high, low, prev_close, close, ...
            name = parts[1].strip() if len(parts) > 1 else ''
            open_price = float(parts[2]) if len(parts) > 2 and parts[2] else 0
            high = float(parts[3]) if len(parts) > 3 and parts[3] else 0
            low = float(parts[4]) if len(parts) > 4 and parts[4] else 0
            prev_close = float(parts[5]) if len(parts) > 5 and parts[5] else 0
            close = float(parts[6]) if len(parts) > 6 and parts[6] else 0
            volume = float(parts[11]) if len(parts) > 11 and parts[11] else 0
        else:
            # A-share format: name, open, prev_close, close, high, low, volume, ...
            name = parts[0].strip() if len(parts) > 0 else ''
            open_price = float(parts[1]) if len(parts) > 1 and parts[1] else 0
            prev_close = float(parts[2]) if len(parts) > 2 and parts[2] else 0
            close = float(parts[3]) if len(parts) > 3 and parts[3] else 0
            high = float(parts[4]) if len(parts) > 4 and parts[4] else 0
            low = float(parts[5]) if len(parts) > 5 and parts[5] else 0
            volume = float(parts[8]) if len(parts) > 8 and parts[8] else 0

        today = datetime.now().strftime('%Y-%m-%d')
        lines = [
            "Date,Open,High,Low,Close,Volume",
            f"{today},{open_price},{high},{low},{close},{int(volume)}"
        ]

        csv_string = "\n".join(lines)
        header = f"# Real-time stock data for {symbol.upper()} (Sina Finance fallback)\n"
        header += f"# Note: Only real-time quote available (historical data request failed)\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        return f"Failed to retrieve data for {symbol}: {str(e)}"


def get_indicator(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
    """Calculate technical indicators from Sina historical data.

    Args:
        symbol: Stock ticker
        indicator: Indicator name (rsi, macd, sma, etc.)
        curr_date: Current date for indicator calculation
        look_back_days: Days to look back for calculation

    Returns:
        Formatted string with indicator values
    """
    supported = {
        "close_50_sma", "close_200_sma", "close_10_ema",
        "macd", "macds", "macdh",
        "rsi", "boll", "boll_ub", "boll_lb",
        "atr", "vwma", "mfi",
    }

    if indicator not in supported:
        return f"Indicator {indicator} is not supported. Supported: {sorted(supported)}"

    # For HK stocks, delegate to sina_finance which uses akshare for historical data
    info = get_market_info(symbol)
    if info.market == "hk":
        from .sina_finance import get_indicator as get_hk_indicator
        return get_hk_indicator(symbol, indicator, curr_date, look_back_days)

    try:
        # Get historical data
        end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=look_back_days * 3)  # Extra buffer

        data_str = get_stock_data(
            symbol,
            start_dt.strftime("%Y-%m-%d"),
            end_dt.strftime("%Y-%m-%d")
        )

        # Parse CSV data
        lines = data_str.strip().split('\n')
        data_lines = [l for l in lines if l and not l.startswith('#')]

        if len(data_lines) < 2:
            return _indicator_unavailable_message(symbol, indicator, "Insufficient historical data")

        # Skip header, parse data
        import io
        df = pd.read_csv(io.StringIO('\n'.join(data_lines)))

        if df.empty or len(df) < 5:
            return _indicator_unavailable_message(symbol, indicator, "Insufficient data points")

        # Ensure correct column types
        df['Date'] = pd.to_datetime(df['Date'])
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df.sort_values('Date')

        # Use stockstats for indicator calculation
        from stockstats import wrap
        stats_df = wrap(df)

        try:
            stats_df[indicator]
        except Exception:
            return _indicator_unavailable_message(symbol, indicator, f"Cannot calculate {indicator}")

        # Build output
        curr_dt = pd.to_datetime(curr_date)
        start_dt = curr_dt - timedelta(days=look_back_days)

        rows = []
        cursor = curr_dt
        while cursor >= start_dt:
            match = stats_df[stats_df['Date'] == cursor]
            if not match.empty:
                value = match.iloc[0][indicator]
                value_str = "N/A" if pd.isna(value) else f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
            else:
                value_str = "N/A: Not a trading day"
            rows.append(f"{cursor.strftime('%Y-%m-%d')}: {value_str}")
            cursor -= timedelta(days=1)

        return (
            f"## {indicator} values for {symbol}:\n\n"
            f"## {indicator} values from {start_dt.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
            + "\n".join(rows)
        )

    except Exception as e:
        return _indicator_unavailable_message(symbol, indicator, str(e))


def _indicator_unavailable_message(symbol: str, indicator: str, error: str = "") -> str:
    """Return message when indicator calculation is unavailable."""
    msg = f"## {indicator} values for {symbol}:\n\n"
    msg += "Technical indicator data is temporarily unavailable.\n\n"
    msg += f"Reason: {error or 'Data source connectivity issues'}\n\n"
    msg += "The primary data source (Sina Finance) may be temporarily unavailable.\n"
    msg += "Please try again later or use an alternative analysis approach.\n"
    return msg
