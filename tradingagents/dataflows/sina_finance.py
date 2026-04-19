"""
Sina Finance data source for HK stocks.
Free, no rate limit, supports real-time quotes.
Enhanced with akshare for historical data.
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

from datetime import datetime, timedelta
from typing import Annotated
import httpx
import pandas as pd

# Also disable requests library from reading system proxy settings
import requests
requests.Session.trust_env = False

from tradingagents.market_utils import get_market_info

# Try to import akshare for HK historical data
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

# Common headers to avoid being blocked
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://finance.sina.com.cn/',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


def _normalize_hk_symbol(symbol: str) -> str:
    """Convert exchange-qualified HK tickers like 9988.HK into 5-digit code."""
    info = get_market_info(symbol)
    if info.market != "hk" or not info.akshare_symbol:
        raise ValueError(f"Sina Finance only supports Hong Kong tickers, got: {symbol}")
    return info.akshare_symbol


def get_hk_realtime_quote(symbol: str) -> dict:
    """Get real-time quote for HK stock from Sina Finance.

    Sina HK stock data format (comma-separated):
    [0] 英文名称 (BABA-W)
    [1] 中文名称 (阿里巴巴)
    [2] 开盘价
    [3] 最高价
    [4] 最低价
    [5] 昨收盘价 (prev_close)
    [6] 当前价/今收盘价 (close)
    [7] 涨跌额
    [8] 涨跌幅
    [9] 买一价
    [10] 卖一价
    [11] 成交量 (股数)
    [12] 成交金额 (港元)
    [13-15] 其他
    [16] 52周最高
    [17] 52周最低
    [18] 日期
    [19] 时间

    Returns dict with: name, open, close, high, low, volume, etc.
    """
    code = _normalize_hk_symbol(symbol)
    sina_symbol = f"hk{code}"

    response = httpx.get(
        f"https://hq.sinajs.cn/list={sina_symbol}",
        headers=_HEADERS,
        timeout=15
    )
    response.raise_for_status()

    # Parse response: var hq_str_hk09988="BABA-W,阿里巴巴,121.000,122.700,121.000,117.500,118.500,..."
    text = response.text
    if 'var hq_str_' not in text:
        raise ValueError(f"No data found for {symbol}")

    # Extract the data string
    start = text.find('"') + 1
    end = text.rfind('"')
    data_str = text[start:end]

    if not data_str:
        raise ValueError(f"Empty data for {symbol}")

    parts = data_str.split(',')
    if len(parts) < 13:
        raise ValueError(f"Invalid data format for {symbol}")

    # Map fields according to Sina HK stock format
    def safe_float(val, default=0.0):
        try:
            return float(val) if val and val.strip() else default
        except (ValueError, AttributeError):
            return default

    return {
        'name': parts[1].strip() if len(parts) > 1 else '',
        'name_en': parts[0].strip() if len(parts) > 0 else '',
        'open': safe_float(parts[2]) if len(parts) > 2 else 0,
        'high': safe_float(parts[3]) if len(parts) > 3 else 0,
        'low': safe_float(parts[4]) if len(parts) > 4 else 0,
        'prev_close': safe_float(parts[5]) if len(parts) > 5 else 0,  # 昨收
        'close': safe_float(parts[6]) if len(parts) > 6 else 0,  # 当前价
        'change': safe_float(parts[7]) if len(parts) > 7 else 0,
        'change_pct': safe_float(parts[8]) if len(parts) > 8 else 0,
        'volume': safe_float(parts[11]) if len(parts) > 11 else 0,  # 成交量
        'amount': safe_float(parts[12]) if len(parts) > 12 else 0,  # 成交额
        'high_52w': safe_float(parts[16]) if len(parts) > 16 else 0,
        'low_52w': safe_float(parts[17]) if len(parts) > 17 else 0,
        'date': parts[18].strip() if len(parts) > 18 else '',
        'time': parts[19].strip() if len(parts) > 19 else '',
    }


def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Get HK stock historical data.

    Uses akshare for historical data, falls back to Sina real-time quotes.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    code = _normalize_hk_symbol(symbol)

    # Try akshare for historical data first
    if AKSHARE_AVAILABLE:
        try:
            return _get_hk_hist_akshare(code, symbol, start_date, end_date)
        except Exception as e:
            import warnings
            warnings.warn(f"akshare HK historical data failed for {symbol}: {e}. Falling back to real-time.")

    # Fallback to real-time quote
    return _get_hk_realtime_only(symbol, start_date, end_date)


def _get_hk_hist_akshare(code: str, symbol: str, start_date: str, end_date: str) -> str:
    """Get HK stock historical data from akshare."""
    # akshare uses 5-digit code with leading zeros
    ak_code = code.zfill(5)

    df = ak.stock_hk_daily(symbol=ak_code, adjust="qfq")

    if df is None or df.empty:
        return _get_hk_realtime_only(symbol, start_date, end_date)

    # Rename columns to standard format
    df = df.rename(columns={
        'date': 'Date',
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume',
        'amount': 'Amount'
    })

    # Ensure Date column is string
    df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')

    # Filter by date range
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    df['Date_dt'] = pd.to_datetime(df['Date'])
    df = df[(df['Date_dt'] >= start_dt) & (df['Date_dt'] <= end_dt)]
    df = df.drop(columns=['Date_dt'])

    # Sort by date ascending
    df = df.sort_values('Date')

    if df.empty:
        return _get_hk_realtime_only(symbol, start_date, end_date)

    # Select required columns
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    available_cols = [c for c in required_cols if c in df.columns]
    df = df[available_cols]

    # Build CSV output
    csv_string = df.to_csv(index=False)
    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Source: akshare (Sina Finance)\n"
    header += f"# Total records: {len(df)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    return header + csv_string


def _get_hk_realtime_only(symbol: str, start_date: str, end_date: str) -> str:
    """Fallback to real-time quote when historical data is unavailable."""
    try:
        quote = get_hk_realtime_quote(symbol)

        # Build CSV output with single row (real-time data)
        lines = [
            "Date,Open,High,Low,Close,Volume",
            f"{datetime.now().strftime('%Y-%m-%d')},{quote['open']},{quote['high']},{quote['low']},{quote['close']},{int(quote['volume'])}"
        ]

        csv_string = "\n".join(lines)
        header = f"# Real-time stock data for {symbol.upper()} (Sina Finance)\n"
        header += f"# Note: Historical data temporarily unavailable, showing real-time quote\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        return f"Failed to retrieve data for {symbol}: {str(e)}"


def get_indicator(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
    """Get technical indicator for HK stock."""
    supported = {
        "close_50_sma", "close_200_sma", "close_10_ema",
        "macd", "macds", "macdh",
        "rsi", "boll", "boll_ub", "boll_lb",
        "atr", "vwma", "mfi",
    }

    if indicator not in supported:
        return f"Indicator {indicator} is not supported. Supported: {sorted(supported)}"

    try:
        # Get historical data
        end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=look_back_days * 3)  # Extra buffer

        data_str = get_stock_data(
            symbol,
            start_dt.strftime("%Y-%m-%d"),
            end_dt.strftime("%Y-%m-%d")
        )

        # Check if we got historical data or just real-time
        if "Real-time" in data_str:
            return f"Technical indicator '{indicator}' for {symbol} requires historical data. Only real-time quote available."

        # Parse CSV data
        lines = data_str.strip().split('\n')
        data_lines = [l for l in lines if l and not l.startswith('#')]

        if len(data_lines) < 2:
            return f"Insufficient historical data for {symbol} to calculate {indicator}"

        # Skip header, parse data
        import io
        df = pd.read_csv(io.StringIO('\n'.join(data_lines)))

        if df.empty or len(df) < 5:
            return f"Insufficient data points for {symbol} to calculate {indicator}"

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
            return f"Cannot calculate {indicator} for {symbol}"

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
        return f"Failed to calculate {indicator} for {symbol}: {str(e)}"
