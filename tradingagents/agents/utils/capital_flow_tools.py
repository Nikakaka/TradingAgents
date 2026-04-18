"""
资金流向数据工具

提供主力资金、散户资金流向分析功能。
数据来源：同花顺iFinD（付费数据源）
"""

from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_capital_flow(
    ticker: Annotated[str, "股票代码"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"],
) -> str:
    """
    获取股票的资金流向数据，包括主力资金、散户资金的流入流出情况。
    这是分析机构动向和市场情绪的重要指标。
    注意：此功能需要同花顺iFinD账号支持。

    参数：
        ticker (str): 股票代码，如 600519.SH、0700.HK
        start_date (str): 开始日期，格式：yyyy-mm-dd
        end_date (str): 结束日期，格式：yyyy-mm-dd

    返回：
        str: 包含资金流向数据的格式化报告，包括：
            - 主力资金流入/流出
            - 散户资金流入/流出
            - 净流入金额
    """
    return route_to_vendor("get_capital_flow", ticker, start_date, end_date)


@tool
def get_realtime_quote(
    ticker: Annotated[str, "股票代码"],
) -> str:
    """
    获取股票的实时行情数据，包括最新价、涨跌幅、成交量等。
    支持A股和港股的实时行情查询。

    参数：
        ticker (str): 股票代码，如 600519.SH、0700.HK

    返回：
        str: 包含实时行情数据的格式化报告
    """
    return route_to_vendor("get_realtime_quote", ticker)
