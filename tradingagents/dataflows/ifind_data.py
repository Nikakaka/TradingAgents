"""
同花顺iFinD数据源模块

提供A股、港股的专业金融数据获取功能。
支持HTTP API和本地SDK两种调用方式。

主要功能:
- 行情数据: 日K线、分钟K线、实时行情
- 财务数据: 资产负债表、利润表、现金流量表
- 估值指标: PE、PB、PS、市值等
- 资金流向: 主力资金、散户资金、板块资金
- 问财选股: 自然语言条件选股
"""

from __future__ import annotations

import os
import json
import time
from datetime import datetime, timedelta
from typing import Any, Optional
import requests
import pandas as pd

from tradingagents.market_utils import get_market_info, MarketInfo


class IFindClient:
    """同花顺iFinD数据客户端"""

    # HTTP API endpoints
    BASE_URL = "https://quantapi.51ifind.com/api/v1"

    # 常用指标代码映射
    INDICATORS = {
        # 行情指标
        "close": "ths_close_price_stock",      # 收盘价
        "open": "ths_open_price_stock",        # 开盘价
        "high": "ths_high_price_stock",        # 最高价
        "low": "ths_low_price_stock",          # 最低价
        "volume": "ths_vol_stock",             # 成交量
        "amount": "ths_amount_stock",          # 成交额
        "turnover": "ths_turnover_ratio_stock", # 换手率

        # 估值指标
        "pe": "ths_pe_stock",                  # 市盈率
        "pe_ttm": "ths_pe_ttm_stock",          # 市盈率TTM
        "pb": "ths_pb_stock",                  # 市净率
        "ps": "ths_ps_stock",                  # 市销率
        "pcf": "ths_pcf_stock",                # 市现率

        # 市值指标
        "market_cap": "ths_market_value_stock",      # 总市值
        "circulating_cap": "ths_circulating_market_value_stock",  # 流通市值

        # 财务指标
        "roe": "ths_roe_stock",                # 净资产收益率
        "roa": "ths_roa_stock",                # 总资产收益率
        "gross_margin": "ths_gross_profit_ratio_stock",  # 毛利率
        "net_margin": "ths_net_profit_ratio_stock",      # 净利率
        "debt_ratio": "ths_debt_asset_ratio_stock",      # 资产负债率

        # 现金流指标
        "ocf": "ths_operate_cash_flow_ps_stock",  # 每股经营现金流
        "fcf": "ths_free_cash_flow_stock",         # 自由现金流

        # 成长指标
        "revenue_growth": "ths_incm_ps_growth_ratio_stock",  # 营收增长率
        "profit_growth": "ths_np_growth_ratio_stock",        # 净利润增长率
    }

    def __init__(self, refresh_token: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None):
        """
        初始化iFinD客户端

        Args:
            refresh_token: 长期刷新令牌（HTTP API用）
            username: 用户名（SDK用）
            password: 密码（SDK用）
        """
        self.refresh_token = refresh_token or os.environ.get("IFIND_REFRESH_TOKEN", "")
        self.username = username or os.environ.get("IFIND_USERNAME", "")
        self.password = password or os.environ.get("IFIND_PASSWORD", "")
        self.access_token: Optional[str] = None
        self._sdk_available = False
        self._last_request_time = 0

        # 检查SDK可用性
        self._check_sdk()

    def _check_sdk(self) -> bool:
        """检查本地SDK是否可用"""
        try:
            from iFinDPy import THS_iFinDLogin, THS_BD, THS_DS, THS_HQ
            self._sdk_available = True
            return True
        except ImportError:
            self._sdk_available = False
            return False

    def _get_access_token(self) -> str:
        """获取访问令牌"""
        if not self.refresh_token:
            raise ValueError("未配置IFIND_REFRESH_TOKEN，请在环境变量中设置或传入refresh_token参数")

        url = f"{self.BASE_URL}/get_access_token"
        headers = {
            "Content-Type": "application/json",
            "refresh_token": self.refresh_token
        }

        response = requests.post(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        self.access_token = data.get("access_token", "")
        return self.access_token

    def _rate_limit(self):
        """简单的频率限制，避免超过API限制"""
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.1:  # 限制10次/秒
            time.sleep(0.1 - elapsed)
        self._last_request_time = time.time()

    def _http_request(self, endpoint: str, params: dict) -> dict:
        """发送HTTP请求"""
        self._rate_limit()

        if not self.access_token:
            self._get_access_token()

        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "access_token": self.access_token
        }

        response = requests.post(url, headers=headers, json=params, timeout=30)

        if response.status_code == 401:
            # Token过期，重新获取
            self._get_access_token()
            headers["access_token"] = self.access_token
            response = requests.post(url, headers=headers, json=params, timeout=30)

        response.raise_for_status()
        return response.json()

    def _sdk_login(self) -> bool:
        """SDK登录"""
        if not self._sdk_available:
            return False

        from iFinDPy import THS_iFinDLogin
        result = THS_iFinDLogin(self.username, self.password)
        return result == 0 or result == -201  # 0=成功, -201=重复登录

    def _convert_symbol_to_ifind(self, ticker: str) -> str:
        """将统一代码格式转换为iFinD格式"""
        info = get_market_info(ticker)

        # iFinD使用 SH/SZ 后缀
        if info.market == "cn_a":
            code = info.akshare_symbol or ticker.split('.')[0]
            if ticker.endswith('.SH'):
                return f"{code}.SH"
            elif ticker.endswith('.SZ'):
                return f"{code}.SZ"
            elif ticker.endswith('.BJ'):
                return f"{code}.BJ"  # 北交所
            return f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
        elif info.market == "hk":
            code = ticker.split('.')[0]
            return f"{code}.HK"  # iFinD港股格式
        else:
            return ticker  # 美股保持原样

    def get_realtime_quote(self, ticker: str) -> dict:
        """
        获取实时行情

        Args:
            ticker: 股票代码

        Returns:
            包含实时行情数据的字典
        """
        symbol = self._convert_symbol_to_ifind(ticker)

        if self._sdk_available and self._sdk_login():
            from iFinDPy import THS_RT
            data = THS_RT(symbol, "last;open;high;low;volume;amount;change;changeRatio")
            return self._parse_sdk_response(data)
        else:
            # HTTP API
            params = {
                "codes": symbol,
                "indipara": [
                    {"indicator": "ths_close_price_stock"},
                    {"indicator": "ths_open_price_stock"},
                    {"indicator": "ths_high_price_stock"},
                    {"indicator": "ths_low_price_stock"},
                    {"indicator": "ths_vol_stock"},
                    {"indicator": "ths_turnover_ratio_stock"},
                ]
            }
            return self._http_request("basic_data_service", params)

    def get_kline_daily(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取日K线数据

        Args:
            ticker: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            K线数据DataFrame
        """
        symbol = self._convert_symbol_to_ifind(ticker)

        if self._sdk_available and self._sdk_login():
            from iFinDPy import THS_HQ
            data = THS_HQ(
                symbol,
                "open;high;low;close;volume;amount;turnoverRatio",
                "CPS:1",  # 前复权
                start_date,
                end_date
            )
            return self._parse_sdk_dataframe(data)
        else:
            # HTTP API - 使用日期序列接口
            params = {
                "codes": symbol,
                "indicators": ["open", "high", "low", "close", "volume", "amount", "turnoverRatio"],
                "startTime": start_date,
                "endTime": end_date,
                "frequency": "day"
            }
            result = self._http_request("high_frequency", params)
            return pd.DataFrame(result.get("data", []))

    def get_financial_indicators(self, ticker: str, date: Optional[str] = None) -> dict:
        """
        获取财务指标

        Args:
            ticker: 股票代码
            date: 查询日期 (YYYY-MM-DD)，默认最新

        Returns:
            财务指标字典
        """
        symbol = self._convert_symbol_to_ifind(ticker)
        date_param = date or datetime.now().strftime("%Y-%m-%d")

        indicators = [
            "ths_pe_stock",          # 市盈率
            "ths_pb_stock",          # 市净率
            "ths_ps_stock",          # 市销率
            "ths_roe_stock",         # ROE
            "ths_roa_stock",         # ROA
            "ths_gross_profit_ratio_stock",  # 毛利率
            "ths_net_profit_ratio_stock",    # 净利率
            "ths_debt_asset_ratio_stock",    # 资产负债率
            "ths_market_value_stock",        # 总市值
            "ths_circulating_market_value_stock",  # 流通市值
        ]

        if self._sdk_available and self._sdk_login():
            from iFinDPy import THS_BD
            data = THS_BD(symbol, ";".join(indicators), date_param)
            return self._parse_sdk_response(data)
        else:
            params = {
                "codes": symbol,
                "indipara": [{"indicator": ind, "param": date_param} for ind in indicators]
            }
            return self._http_request("basic_data_service", params)

    def get_capital_flow(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取资金流向数据

        Args:
            ticker: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            资金流向DataFrame
        """
        symbol = self._convert_symbol_to_ifind(ticker)

        # iFinD资金流向指标
        indicators = [
            "ths_main_in_fund_stock",      # 主力流入
            "ths_main_out_fund_stock",     # 主力流出
            "ths_main_net_in_fund_stock",  # 主力净流入
            "ths_retail_in_fund_stock",    # 散户流入
            "ths_retail_out_fund_stock",   # 散户流出
            "ths_retail_net_in_fund_stock", # 散户净流入
        ]

        if self._sdk_available and self._sdk_login():
            from iFinDPy import THS_DS
            data = THS_DS(
                symbol,
                ";".join(indicators),
                f"{start_date}:{end_date}",
                "date:Y"
            )
            return self._parse_sdk_dataframe(data)
        else:
            # HTTP API可能不支持此功能
            raise NotImplementedError("资金流向数据目前仅支持SDK方式获取")

    def wencai_query(self, query: str) -> list:
        """
        问财自然语言选股

        Args:
            query: 自然语言查询条件

        Returns:
            符合条件的股票列表
        """
        if self._sdk_available and self._sdk_login():
            from iFinDPy import THS_WC
            data = THS_WC(query, "stock")
            return self._parse_sdk_response(data)
        else:
            raise NotImplementedError("问财选股目前仅支持SDK方式获取")

    def _parse_sdk_response(self, data: Any) -> dict:
        """解析SDK返回数据"""
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        if hasattr(data, 'to_dict'):
            return data.to_dict()
        return {"data": data}

    def _parse_sdk_dataframe(self, data: Any) -> pd.DataFrame:
        """解析SDK返回为DataFrame"""
        if data is None:
            return pd.DataFrame()
        if isinstance(data, pd.DataFrame):
            return data
        if hasattr(data, 'tables') and data.tables:
            return pd.DataFrame(data.tables[0].data)
        return pd.DataFrame(data)


# 全局客户端实例
_client: Optional[IFindClient] = None


def get_ifind_client() -> IFindClient:
    """获取全局iFinD客户端实例"""
    global _client
    if _client is None:
        _client = IFindClient()
    return _client


def get_stock_data_ifind(ticker: str, start_date: str, end_date: str) -> str:
    """
    获取股票历史行情数据（用于数据路由）

    Args:
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        格式化的股票数据字符串
    """
    try:
        client = get_ifind_client()
        df = client.get_kline_daily(ticker, start_date, end_date)

        if df.empty:
            return f"未找到股票 {ticker} 在 {start_date} 至 {end_date} 的数据"

        # 格式化输出
        info = get_market_info(ticker)
        header = f"# 股票历史行情数据: {info.canonical_ticker}\n"
        header += f"# 市场: {info.region_label}\n"
        header += f"# 数据期间: {start_date} 至 {end_date}\n"
        header += f"# 数据来源: 同花顺iFinD\n"
        header += f"# 获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + df.to_csv(index=True)

    except Exception as e:
        return f"iFinD数据获取失败: {ticker} - {str(e)}"


def get_realtime_quote_ifind(ticker: str) -> str:
    """
    获取实时行情（用于数据路由）

    Args:
        ticker: 股票代码

    Returns:
        格式化的实时行情字符串
    """
    try:
        client = get_ifind_client()
        data = client.get_realtime_quote(ticker)

        info = get_market_info(ticker)
        header = f"# 实时行情: {info.canonical_ticker}\n"
        header += f"# 市场: {info.region_label}\n"
        header += f"# 数据来源: 同花顺iFinD\n\n"

        # 格式化输出
        lines = []
        for key, value in data.items():
            if isinstance(value, (int, float)):
                lines.append(f"{key}: {value}")
            else:
                lines.append(f"{key}: {value}")

        return header + "\n".join(lines)

    except Exception as e:
        return f"iFinD实时行情获取失败: {ticker} - {str(e)}"


def get_financial_indicators_ifind(ticker: str, date: Optional[str] = None) -> str:
    """
    获取财务指标（用于数据路由）

    Args:
        ticker: 股票代码
        date: 查询日期

    Returns:
        格式化的财务指标字符串
    """
    try:
        client = get_ifind_client()
        data = client.get_financial_indicators(ticker, date)

        info = get_market_info(ticker)
        header = f"# 财务指标: {info.canonical_ticker}\n"
        header += f"# 市场: {info.region_label}\n"
        header += f"# 查询日期: {date or '最新'}\n"
        header += f"# 数据来源: 同花顺iFinD\n\n"

        # 格式化输出
        lines = []
        for key, value in data.items():
            lines.append(f"{key}: {value}")

        return header + "\n".join(lines)

    except Exception as e:
        return f"iFinD财务指标获取失败: {ticker} - {str(e)}"


def get_capital_flow_ifind(ticker: str, start_date: str, end_date: str) -> str:
    """
    获取资金流向（用于数据路由）

    Args:
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        格式化的资金流向字符串
    """
    try:
        client = get_ifind_client()
        df = client.get_capital_flow(ticker, start_date, end_date)

        if df.empty:
            return f"未找到股票 {ticker} 的资金流向数据"

        info = get_market_info(ticker)
        header = f"# 资金流向数据: {info.canonical_ticker}\n"
        header += f"# 市场: {info.region_label}\n"
        header += f"# 数据期间: {start_date} 至 {end_date}\n"
        header += f"# 数据来源: 同花顺iFinD\n\n"

        return header + df.to_csv(index=True)

    except Exception as e:
        return f"iFinD资金流向获取失败: {ticker} - {str(e)}"
