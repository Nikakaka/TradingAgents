from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor

@tool
def get_news(
    ticker: Annotated[str, "股票代码"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"],
) -> str:
    """
    获取与指定股票相关的新闻数据。
    适用于A股和港股的新闻分析。返回中文新闻为主。
    参数：
        ticker (str): 股票代码，如 600519.SH、0700.HK
        start_date (str): 开始日期，格式：yyyy-mm-dd
        end_date (str): 结束日期，格式：yyyy-mm-dd
    返回：
        str: 包含相关新闻数据的格式化报告
    """
    return route_to_vendor("get_news", ticker, start_date, end_date)

@tool
def get_global_news(
    curr_date: Annotated[str, "当前日期，格式：yyyy-mm-dd"],
    look_back_days: Annotated[int, "回看天数"] = 7,
    limit: Annotated[int, "返回文章数量上限"] = 5,
) -> str:
    """
    获取全球市场新闻数据。
    适用于A股和港股的宏观经济分析。返回中文财经新闻为主。
    参数：
        curr_date (str): 当前日期，格式：yyyy-mm-dd
        look_back_days (int): 回看天数，默认7天
        limit (int): 返回文章数量上限，默认5篇
    返回：
        str: 包含全球市场新闻数据的格式化报告
    """
    return route_to_vendor("get_global_news", curr_date, look_back_days, limit)

@tool
def get_insider_transactions(
    ticker: Annotated[str, "股票代码"],
) -> str:
    """
    获取公司内部人交易信息。
    注意：此功能对A股和港股支持有限，主要适用于美股。
    参数：
        ticker (str): 股票代码
    返回：
        str: 包含内部人交易数据的格式化报告
    """
    return route_to_vendor("get_insider_transactions", ticker)
