from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_indicators,
    get_stock_data,
    get_cross_market_listings,
    check_dual_listing,
    get_cross_market_comparison,
)
from tradingagents.agents.utils.capital_flow_tools import get_capital_flow, get_realtime_quote
from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.cross_market_mapping import has_cross_market_listing


def create_market_analyst(llm):
    config = get_config()
    provider = (config.get("llm_provider") or "").lower()

    full_system_message = (
        "你是一名专业的市场分析师。请按以下步骤进行分析：\n"
        "1. **首先调用 get_realtime_quote 获取当前实时行情**（这是当天的最新价格，不要仅依赖历史数据）\n"
        "2. **调用 check_dual_listing 检查该股票是否在多个市场上市**\n"
        "3. 如果股票跨市场上市，调用 get_cross_market_comparison 获取各市场行情对比\n"
        "4. 使用 get_stock_data 获取股价历史数据\n"
        "5. 使用 get_indicators 分析技术指标（趋势、动量、波动率）\n"
        "6. 调用 get_capital_flow 获取资金流向数据（主力资金、散户资金动向）\n\n"
        "**重要提示**：\n"
        "- 分析报告中的当前价格必须使用 get_realtime_quote 返回的实时价格，不要使用历史数据的最后一条记录\n"
        "- 如果是港股且今天正在交易中，历史数据可能不包含今天的记录，必须使用实时行情\n\n"
        "**跨市场分析要点：**\n"
        "- 对于A+H股：分析AH溢价率，判断两地市场估值差异\n"
        "- 对于港股+美股：关注ADR溢价/折价，美股对港股的开盘影响\n"
        "- 综合多个市场的价格走势、成交量、资金流向进行分析\n\n"
        "技术指标选择：从以下列表中选择最多6个指标，每次调用 get_indicators 只查询一个指标：\n"
        "close_50_sma, close_200_sma, close_10_ema, macd, macds, macdh, rsi, boll, boll_ub, boll_lb, atr, vwma, mfi\n\n"
        "报告要求：\n"
        "- 基于数据分析价格趋势、技术形态\n"
        "- 如果跨市场上市，必须包含跨市场价格对比分析\n"
        "- 结合资金流向判断主力动向和市场情绪\n"
        "- 明确支撑位、阻力位和关键价位\n"
        "- 给出看涨和看跌两种情形的分析\n"
        "- 在报告末尾附上 Markdown 表格汇总主要信号\n"
        "请使用中文撰写报告。"
    )

    local_system_message = (
        "你是一名市场分析师。\n"
        "1. **首先调用 check_dual_listing 检查该股票是否在多个市场上市**\n"
        "2. 如果跨市场上市，使用 get_cross_market_comparison 获取对比数据\n"
        "3. 然后调用 get_stock_data 获取股价数据\n"
        "4. 最后选择对当前走势最有用的指标，每次调用 get_indicators 只查询一个指标。"
        "最多选择 6 个指标，从以下列表中选择：close_50_sma, close_200_sma, close_10_ema, macd, macds, macdh, rsi, boll, boll_ub, boll_lb, atr, vwma。"
        "撰写一份简洁但基于证据的市场报告，涵盖价格趋势、动量、波动率、关键支撑阻力位以及交易启示。"
        "如果跨市场上市，必须包含跨市场分析内容。"
        "在报告末尾附上一个简短的 Markdown 表格，汇总主要信号。"
        "请使用中文撰写报告。"
    )

    system_message = local_system_message if provider == "ollama" else full_system_message

    def market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)

        # 检查是否跨市场上市，添加相关工具提示
        cross_market_hint = ""
        if has_cross_market_listing(ticker):
            cross_market_hint = f"\n注意：该股票在多个市场上市，请务必使用 check_dual_listing 和 get_cross_market_comparison 进行跨市场分析。"

        # 基础工具列表
        tool_list = [get_stock_data, get_indicators]

        # 添加跨市场分析工具
        tool_list.extend([get_cross_market_listings, check_dual_listing, get_cross_market_comparison])

        # 添加实时行情工具（支持港股和A股）
        tool_list.append(get_realtime_quote)

        try:
            import os
            if os.environ.get("IFIND_REFRESH_TOKEN") or os.environ.get("IFIND_USERNAME"):
                tool_list.append(get_capital_flow)
        except Exception:
            pass

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个有帮助的 AI 助手，与其他助手协作。"
                    " 使用提供的工具来推进问题的解答。"
                    " 如果你无法完全回答，没关系；其他具有不同工具的助手"
                    " 会接着你停下的地方继续。执行你能做的来推进进度。"
                    " 如果你或任何其他助手有最终交易建议：**买入/持有/卖出** 或可交付成果，"
                    " 请在回复前加上最终交易建议：**买入/持有/卖出**，以便团队知道停止。"
                    " 你可以使用以下工具：{tool_names}。\n{system_message}\n"
                    "供参考，当前日期是 {current_date}。{instrument_context}{cross_market_hint}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tool_list]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)
        prompt = prompt.partial(cross_market_hint=cross_market_hint)

        chain = prompt | llm.bind_tools(tool_list)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "market_report": report,
        }

    return market_analyst_node
