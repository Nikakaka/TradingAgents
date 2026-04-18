from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_fundamentals(
    ticker: Annotated[str, "股票代码"],
    curr_date: Annotated[str, "当前交易日期，格式：yyyy-mm-dd"],
) -> str:
    """
    获取公司的全面基本面数据。
    适用于A股和港股的基本面分析。
    参数：
        ticker (str): 股票代码，如 600519.SH（贵州茅台）、0700.HK（腾讯控股）
        curr_date (str): 当前交易日期，格式：yyyy-mm-dd
    返回：
        str: 包含公司基本面数据的格式化报告，包括公司概况、财务指标、估值等
    """
    return route_to_vendor("get_fundamentals", ticker, curr_date)


@tool
def get_balance_sheet(
    ticker: Annotated[str, "股票代码"],
    freq: Annotated[str, "报告周期：annual（年报）/ quarterly（季报）"] = "quarterly",
    curr_date: Annotated[str, "当前交易日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """
    获取公司的资产负债表数据。
    适用于A股和港股的财务分析。
    参数：
        ticker (str): 股票代码
        freq (str): 报告周期：annual（年报）/ quarterly（季报），默认季报
        curr_date (str): 当前交易日期，格式：yyyy-mm-dd
    返回：
        str: 包含资产负债表数据的格式化报告
    """
    return route_to_vendor("get_balance_sheet", ticker, freq, curr_date)


@tool
def get_cashflow(
    ticker: Annotated[str, "股票代码"],
    freq: Annotated[str, "报告周期：annual（年报）/ quarterly（季报）"] = "quarterly",
    curr_date: Annotated[str, "当前交易日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """
    获取公司的现金流量表数据。
    适用于A股和港股的财务分析。
    参数：
        ticker (str): 股票代码
        freq (str): 报告周期：annual（年报）/ quarterly（季报），默认季报
        curr_date (str): 当前交易日期，格式：yyyy-mm-dd
    返回：
        str: 包含现金流量表数据的格式化报告
    """
    return route_to_vendor("get_cashflow", ticker, freq, curr_date)


@tool
def get_income_statement(
    ticker: Annotated[str, "股票代码"],
    freq: Annotated[str, "报告周期：annual（年报）/ quarterly（季报）"] = "quarterly",
    curr_date: Annotated[str, "当前交易日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """
    获取公司的利润表数据。
    适用于A股和港股的财务分析。
    参数：
        ticker (str): 股票代码
        freq (str): 报告周期：annual（年报）/ quarterly（季报），默认季报
        curr_date (str): 当前交易日期，格式：yyyy-mm-dd
    返回：
        str: 包含利润表数据的格式化报告
    """
    return route_to_vendor("get_income_statement", ticker, freq, curr_date)