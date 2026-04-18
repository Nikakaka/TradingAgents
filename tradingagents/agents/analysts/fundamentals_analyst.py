from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_insider_transactions,
)
from tradingagents.dataflows.config import get_config


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]

        system_message = (
            "你是一名基本面研究员，负责分析一家公司过去一周的基本面信息。请撰写一份全面的公司基本面报告，"
            "包括财务文件、公司概况、基本财务数据和公司财务历史，为交易员提供公司基本面的完整视角。"
            "请尽可能详细地提供具体、可操作的见解和支撑证据，帮助交易员做出明智的决策。"
            "请使用可用的工具：`get_fundamentals` 用于全面的公司分析，`get_balance_sheet`、`get_cashflow` 和 `get_income_statement` 用于具体的财务报表。"
            "请确保在报告末尾附上一个 Markdown 表格，整理报告中的关键要点，使其有条理且易于阅读。"
            "请使用中文撰写报告。"
        )

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
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
