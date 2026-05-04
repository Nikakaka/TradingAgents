"""
Tencent Finance data source for HK stocks.
More accurate than Sina for closing prices.
"""
import os

# Disable ALL proxies
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

import httpx
from tradingagents.market_utils import get_market_info

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


def _normalize_hk_symbol(symbol: str) -> str:
    """Convert exchange-qualified HK tickers like 9988.HK into 5-digit code."""
    info = get_market_info(symbol)
    if info.market != "hk" or not info.akshare_symbol:
        raise ValueError(f"Tencent Finance only supports Hong Kong tickers, got: {symbol}")
    return info.akshare_symbol


def get_hk_realtime_quote(symbol: str) -> dict:
    """Get real-time quote for HK stock from Tencent Finance.
    
    Tencent HK stock data format (tilde-separated):
    [0] 未知
    [1] 名称
    [2] 代码
    [3] 当前价
    [4] 昨收盘
    [5] 今开盘
    [6] 成交量（手）
    [7] 成交额
    ...
    [32] 开盘价
    [33] 最高价
    [34] 最低价
    """
    code = _normalize_hk_symbol(symbol)
    tencent_symbol = f"r_hk{code}"

    response = httpx.get(
        f"https://web.sqt.gtimg.cn/q={tencent_symbol}",
        headers=_HEADERS,
        timeout=15
    )
    response.raise_for_status()

    text = response.text
    if 'v_r_hk' not in text:
        raise ValueError(f"No data found for {symbol}")

    # Parse response: v_r_hk09988="~阿里巴巴-W~09988~126.500~..."
    start = text.find('"') + 1
    end = text.rfind('"')
    data_str = text[start:end]
    
    if not data_str:
        raise ValueError(f"Empty data for {symbol}")

    parts = data_str.split('~')
    if len(parts) < 35:
        raise ValueError(f"Invalid data format for {symbol}: expected 35+ fields, got {len(parts)}")

    def safe_float(val, default=0.0):
        try:
            return float(val) if val and val.strip() else default
        except (ValueError, AttributeError):
            return default

    return {
        'name': parts[1].strip() if len(parts) > 1 else '',
        'code': parts[2].strip() if len(parts) > 2 else '',
        'close': safe_float(parts[3]),  # 当前价
        'prev_close': safe_float(parts[4]),  # 昨收
        'open': safe_float(parts[32]) if len(parts) > 32 else 0,  # 开盘
        'high': safe_float(parts[33]) if len(parts) > 33 else 0,  # 最高
        'low': safe_float(parts[34]) if len(parts) > 34 else 0,  # 最低
        'volume': safe_float(parts[6]) if len(parts) > 6 else 0,  # 成交量
        'amount': safe_float(parts[7]) if len(parts) > 7 else 0,  # 成交额
        'change': safe_float(parts[3]) - safe_float(parts[4]) if len(parts) > 4 else 0,
        'change_pct': ((safe_float(parts[3]) - safe_float(parts[4])) / safe_float(parts[4]) * 100) if safe_float(parts[4]) != 0 else 0,
    }
