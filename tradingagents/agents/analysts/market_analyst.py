from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_indicators,
    get_stock_data,
)
from tradingagents.agents.utils.capital_flow_tools import get_capital_flow, get_realtime_quote
from tradingagents.dataflows.config import get_config


def create_market_analyst(llm):
    config = get_config()
    provider = (config.get("llm_provider") or "").lower()

    full_system_message = (
        "你是一名专业的市场分析师。请按以下步骤进行分析：\n"
        "1. 首先调用 get_stock_data 获取股价历史数据\n"
        "2. 使用 get_indicators 分析技术指标（趋势、动量、波动率）\n"
        "3. 调用 get_capital_flow 获取资金流向数据（主力资金、散户资金动向）\n"
        "4. 如果需要，调用 get_realtime_quote 获取实时行情\n\n"
        "技术指标选择：从以下列表中选择最多6个指标，每次调用 get_indicators 只查询一个指标：\n"
        "close_50_sma, close_200_sma, close_10_ema, macd, macds, macdh, rsi, boll, boll_ub, boll_lb, atr, vwma, mfi\n\n"
        "报告要求：\n"
        "- 基于数据分析价格趋势、技术形态\n"
        "- 结合资金流向判断主力动向和市场情绪\n"
        "- 明确支撑位、阻力位和关键价位\n"
        "- 给出看涨和看跌两种情形的分析\n"
        "- 在报告末尾附上 Markdown 表格汇总主要信号\n"
        "请使用中文撰写报告。"
    )

    local_system_message = (
        "你是一名市场分析师。首先调用 get_stock_data 获取股价数据，然后仅选择对当前走势最有用的指标，每次调用 get_indicators 只查询一个指标。"
        "最多选择 6 个指标，从以下列表中选择：close_50_sma, close_200_sma, close_10_ema, macd, macds, macdh, rsi, boll, boll_ub, boll_lb, atr, vwma。"
        "优先选择趋势、动量、波动率和成交量方面的多样化信号，避免冗余选择。"
        "撰写一份简洁但基于证据的市场报告，涵盖价格趋势、动量、波动率、关键支撑阻力位以及交易启示。"
        "在报告末尾附上一个简短的 Markdown 表格，汇总主要信号。"
        "请使用中文撰写报告。"
    )

    system_message = local_system_message if provider == "ollama" else full_system_message

    def market_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        # 检查是否配置了iFinD（资金流向数据需要）
        tool_list = [get_stock_data, get_indicators]
        try:
            import os
            if os.environ.get("IFIND_REFRESH_TOKEN") or os.environ.get("IFIND_USERNAME"):
                tool_list.extend([get_capital_flow, get_realtime_quote])
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
                    "供参考，当前日期是 {current_date}。{instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tool_list]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

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
