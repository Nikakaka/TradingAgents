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
    
    **重要**: 分析港股时务必调用此函数获取当天实时价格，不要仅依赖历史数据。

    参数：
        ticker (str): 股票代码，如 600519.SH、0700.HK、9988.HK

    返回：
        str: 包含实时行情数据的格式化报告，包括：
            - 股票名称
            - 当前价格
            - 涨跌幅
            - 成交量
            - 52周高低
    """
    result = route_to_vendor("get_realtime_quote", ticker)
    
    # If result is a dict, format it nicely
    if isinstance(result, dict):
        name = result.get('name', '')
        name_en = result.get('name_en', '')
        close = result.get('close', 0)
        prev_close = result.get('prev_close', 0)
        change = result.get('change', 0)
        change_pct = result.get('change_pct', 0)
        open_p = result.get('open', 0)
        high = result.get('high', 0)
        low = result.get('low', 0)
        volume = result.get('volume', 0)
        high_52w = result.get('high_52w', 0)
        low_52w = result.get('low_52w', 0)
        
        return f"""# 实时行情：{ticker}

**股票名称**: {name} ({name_en})
**当前价格**: {close} {'HKD' if '.HK' in ticker.upper() else 'CNY'}
**昨收**: {prev_close}
**涨跌**: {change:+} ({change_pct:+}%)
**今日区间**: {low} - {high}
**开盘**: {open_p}
**成交量**: {int(volume):,}
**52周最高**: {high_52w}
**52周最低**: {low_52w}

> 此数据为实时行情，分析报告应基于此价格而非历史数据的最后一条记录。
"""
    
    return result
