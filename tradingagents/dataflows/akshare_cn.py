from datetime import datetime

import akshare as ak
import pandas as pd
from stockstats import wrap

from tradingagents.market_utils import get_market_info


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
    """Retrieve A-share OHLCV data from Akshare."""
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

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


def get_indicator(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
    """Calculate technical indicators from Akshare A-share historical data."""
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
            value = "N/A" if pd.isna(value) else value
        else:
            value = "N/A: Not a trading day (weekend or holiday)"
        rows.append(f"{cursor.strftime('%Y-%m-%d')}: {value}")
        cursor -= pd.Timedelta(days=1)

    return (
        f"## {indicator} values from {start_dt.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
        + "\n".join(rows)
    )
