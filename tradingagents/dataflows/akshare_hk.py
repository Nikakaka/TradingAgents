import os
from datetime import datetime

import httpx
import pandas as pd
from stockstats import wrap

from tradingagents.market_utils import get_market_info


# Proxy configuration for HK data
# Set to None to disable proxy (useful when proxy is not working)
_PROXY_URL = os.environ.get("AKSHARE_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")

# Check if proxy is working, if not disable it
if _PROXY_URL and _PROXY_URL.startswith("http://127.0.0.1"):
    # Local proxy may not be stable, try without proxy
    try:
        import urllib.request
        urllib.request.urlopen("https://www.baidu.com", timeout=5)
        # Direct connection works, no need for proxy
        _PROXY_URL = None
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
    except:
        pass  # Keep proxy if direct connection fails


_HK_RENAME_MAP = {
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


def _normalize_hk_symbol(symbol: str) -> str:
    """Convert exchange-qualified HK tickers like 9988.HK into Akshare format."""
    info = get_market_info(symbol)
    if info.market != "hk" or not info.akshare_symbol:
        raise ValueError(f"Akshare HK data source only supports Hong Kong tickers, got: {symbol}")
    return info.akshare_symbol


def _fetch_hk_hist_eastmoney(symbol: str, days: int = 1000) -> pd.DataFrame:
    """Fetch HK stock historical data directly from Eastmoney API via proxy.

    This bypasses akshare's SSL issues with certain proxies.
    """
    hk_symbol = _normalize_hk_symbol(symbol)
    # Eastmoney uses 116 for HK market, symbol without leading zeros but with 5 digits
    secid = f"116.{hk_symbol}"

    try:
        with httpx.Client(proxy=_PROXY_URL, timeout=30) as client:
            response = client.get(
                "http://push2his.eastmoney.com/api/qt/stock/kline/get",
                params={
                    "secid": secid,
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                    "klt": "101",  # daily
                    "fqt": "1",    # qfq (前复权)
                    "end": "20500000",
                    "lmt": str(days)
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("data", {}).get("klines"):
                raise RuntimeError(f"No data from Eastmoney for symbol '{symbol}'")

            # Parse klines: "date,open,close,high,low,volume,turnover,amplitude,change_pct,change_amt,turnover_rate"
            klines = data["data"]["klines"]
            records = []
            for kline in klines:
                parts = kline.split(",")
                if len(parts) >= 6:
                    records.append({
                        "日期": parts[0],
                        "开盘": float(parts[1]),
                        "收盘": float(parts[2]),
                        "最高": float(parts[3]),
                        "最低": float(parts[4]),
                        "成交量": float(parts[5]),
                    })

            df = pd.DataFrame(records)
            return df

    except Exception as e:
        raise RuntimeError(f"Eastmoney API failed for {symbol}: {e}")


def _fetch_hk_hist_df(symbol: str) -> pd.DataFrame:
    """Fetch HK stock historical data, with fallback to direct Eastmoney API."""
    # Try akshare first
    try:
        import akshare as ak
        hk_symbol = _normalize_hk_symbol(symbol)
        df = ak.stock_hk_hist(symbol=hk_symbol, period="daily", adjust="qfq")
        if df is not None and not df.empty:
            return df.copy()
    except Exception:
        pass  # Fall back to direct Eastmoney API

    # Fallback to direct Eastmoney API
    return _fetch_hk_hist_eastmoney(symbol)


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = df.rename(columns=_HK_RENAME_MAP)
    required_columns = {"Date", "Open", "High", "Low", "Close", "Volume"}
    missing = required_columns - set(renamed.columns)
    if missing:
        raise RuntimeError(f"Unexpected Akshare HK columns: missing {sorted(missing)}")
    return renamed


def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Retrieve HK stock OHLCV data from Akshare."""
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    df = _rename_columns(_fetch_hk_hist_df(symbol))
    df["Date"] = pd.to_datetime(df["Date"])
    filtered = df[(df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))]

    if filtered.empty:
        return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

    csv_string = filtered.to_csv(index=False)
    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(filtered)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + csv_string


def get_indicator(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
    """Calculate technical indicators from Akshare HK historical data via stockstats."""
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

    curr_dt = pd.to_datetime(curr_date)
    start_dt = curr_dt - pd.Timedelta(days=look_back_days)

    df = _rename_columns(_fetch_hk_hist_df(symbol))
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
            value = "N/A" if pd.isna(value) else value
        else:
            value = "N/A: Not a trading day (weekend or holiday)"
        rows.append(f"{cursor.strftime('%Y-%m-%d')}: {value}")
        cursor -= pd.Timedelta(days=1)

    return (
        f"## {indicator} values from {start_dt.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
        + "\n".join(rows)
    )
