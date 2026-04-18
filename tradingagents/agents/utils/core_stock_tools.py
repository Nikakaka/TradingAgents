from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_stock_data(
    symbol: Annotated[str, "股票代码"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"],
) -> str:
    """
    获取股票的历史行情数据（开盘价、最高价、最低价、收盘价、成交量）。
    适用于A股和港股分析。
    参数：
        symbol (str): 股票代码，如 600519.SH（贵州茅台）、0700.HK（腾讯控股）
        start_date (str): 开始日期，格式：yyyy-mm-dd
        end_date (str): 结束日期，格式：yyyy-mm-dd
    返回：
        str: 包含指定日期范围内股票行情数据的格式化报告
    """
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)
