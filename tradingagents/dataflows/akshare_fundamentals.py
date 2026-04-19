from __future__ import annotations

import os
import urllib.request
from datetime import datetime

# Disable system proxy for akshare data fetching
# This fixes connection issues when Windows proxy settings point to a non-working proxy
def _disable_system_proxy():
    """Disable system proxy settings that may interfere with data fetching."""
    for key in list(os.environ.keys()):
        if 'proxy' in key.lower() and key.upper() not in ['NO_PROXY']:
            del os.environ[key]
    no_proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(no_proxy_handler)
    urllib.request.install_opener(opener)
    os.environ['NO_PROXY'] = '*'
    os.environ['no_proxy'] = '*'

    # Also disable requests library from reading system proxy settings
    import requests
    requests.Session.trust_env = False

_disable_system_proxy()

import akshare as ak
import pandas as pd

from tradingagents.market_utils import get_market_info


def _require_cn_a(ticker: str) -> str:
    info = get_market_info(ticker)
    if info.market != "cn_a" or not info.akshare_symbol:
        raise ValueError(f"Akshare A-share fundamentals only support China A-share tickers, got: {ticker}")
    return info.akshare_symbol


def _require_hk(ticker: str) -> str:
    info = get_market_info(ticker)
    if info.market != "hk" or not info.akshare_symbol:
        raise ValueError(f"Akshare HK fundamentals only support Hong Kong tickers, got: {ticker}")
    return info.akshare_symbol


def _header(title: str) -> str:
    return f"# {title}\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"


def _compact_table(df: pd.DataFrame, rows: int = 5) -> str:
    trimmed = df.head(rows).copy()
    return trimmed.to_csv(index=False)


def _latest_hk_report_table(df: pd.DataFrame, report_name: str) -> str:
    if df is None or df.empty:
        return f"No {report_name} data found"

    working = df.copy()
    working["REPORT_DATE"] = pd.to_datetime(working["REPORT_DATE"])
    latest_date = working["REPORT_DATE"].max()
    latest = working[working["REPORT_DATE"] == latest_date][["STD_ITEM_NAME", "AMOUNT"]].copy()
    latest = latest.rename(columns={"STD_ITEM_NAME": "Item", "AMOUNT": "Amount"})
    return (
        f"Latest report date: {latest_date.strftime('%Y-%m-%d')}\n\n"
        + latest.to_csv(index=False)
    )


def _safe_numeric_value(value) -> str:
    if pd.isna(value):
        return "N/A"
    return str(value)


def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    info = get_market_info(ticker)

    if info.market == "cn_a":
        symbol = _require_cn_a(ticker)
        profile = ak.stock_individual_info_em(symbol=symbol)
        metrics = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")

        lines = []
        if profile is not None and not profile.empty:
            for _, row in profile.iterrows():
                lines.append(f"{row['item']}: {row['value']}")

        if metrics is not None and not metrics.empty:
            latest = metrics.iloc[-1]
            lines.append("")
            lines.append("Latest key financial metrics:")
            for col in [
                "报告期",
                "净利润",
                "净利润同比增长率",
                "扣非净利润",
                "营业总收入",
                "营业总收入同比增长率",
                "基本每股收益",
                "每股净资产",
                "每股经营现金流",
                "销售净利率",
                "销售毛利率",
                "净资产收益率",
                "资产负债率",
            ]:
                if col in latest.index:
                    lines.append(f"{col}: {_safe_numeric_value(latest[col])}")

            lines.append("")
            lines.append("Recent financial abstract:")
            lines.append(_compact_table(metrics.iloc[::-1], rows=4))

        if not lines:
            return f"No fundamentals data found for symbol '{info.canonical_ticker}'"

        return _header(f"Company Fundamentals for {info.canonical_ticker}") + "\n".join(lines)

    if info.market == "hk":
        symbol = _require_hk(ticker)
        profile = ak.stock_hk_company_profile_em(symbol=symbol)
        metrics = ak.stock_hk_financial_indicator_em(symbol=symbol)

        lines = []
        if profile is not None and not profile.empty:
            row = profile.iloc[0]
            for col in profile.columns:
                lines.append(f"{col}: {row[col]}")

        if metrics is not None and not metrics.empty:
            row = metrics.iloc[0]
            lines.append("")
            lines.append("Latest key financial metrics:")
            for col in metrics.columns:
                lines.append(f"{col}: {row[col]}")

        if not lines:
            return f"No fundamentals data found for symbol '{info.canonical_ticker}'"

        return _header(f"Company Fundamentals for {info.canonical_ticker}") + "\n".join(lines)

    raise ValueError(f"Akshare fundamentals not supported for ticker '{ticker}'")


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    info = get_market_info(ticker)

    if info.market == "cn_a":
        stock = f"{info.canonical_ticker[-2:].lower()}{info.akshare_symbol}"
        df = ak.stock_financial_report_sina(stock=stock, symbol="资产负债表")
        if df is None or df.empty:
            return f"No balance sheet data found for symbol '{info.canonical_ticker}'"
        return _header(f"Balance Sheet data for {info.canonical_ticker} ({freq})") + _compact_table(df, rows=4)

    if info.market == "hk":
        df = ak.stock_financial_hk_report_em(stock=info.akshare_symbol, symbol="资产负债表", indicator="报告期")
        return _header(f"Balance Sheet data for {info.canonical_ticker} ({freq})") + _latest_hk_report_table(df, "balance sheet")

    raise ValueError(f"Akshare balance sheet not supported for ticker '{ticker}'")


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    info = get_market_info(ticker)

    if info.market == "cn_a":
        stock = f"{info.canonical_ticker[-2:].lower()}{info.akshare_symbol}"
        df = ak.stock_financial_report_sina(stock=stock, symbol="现金流量表")
        if df is None or df.empty:
            return f"No cash flow data found for symbol '{info.canonical_ticker}'"
        return _header(f"Cash Flow data for {info.canonical_ticker} ({freq})") + _compact_table(df, rows=4)

    if info.market == "hk":
        df = ak.stock_financial_hk_report_em(stock=info.akshare_symbol, symbol="现金流量表", indicator="报告期")
        return _header(f"Cash Flow data for {info.canonical_ticker} ({freq})") + _latest_hk_report_table(df, "cash flow")

    raise ValueError(f"Akshare cash flow not supported for ticker '{ticker}'")


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    info = get_market_info(ticker)

    if info.market == "cn_a":
        stock = f"{info.canonical_ticker[-2:].lower()}{info.akshare_symbol}"
        df = ak.stock_financial_report_sina(stock=stock, symbol="利润表")
        if df is None or df.empty:
            return f"No income statement data found for symbol '{info.canonical_ticker}'"
        return _header(f"Income Statement data for {info.canonical_ticker} ({freq})") + _compact_table(df, rows=4)

    if info.market == "hk":
        df = ak.stock_financial_hk_report_em(stock=info.akshare_symbol, symbol="利润表", indicator="报告期")
        return _header(f"Income Statement data for {info.canonical_ticker} ({freq})") + _latest_hk_report_table(df, "income statement")

    raise ValueError(f"Akshare income statement not supported for ticker '{ticker}'")
