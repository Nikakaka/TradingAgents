from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_global_news,
    get_news,
)
from tradingagents.dataflows.config import get_config


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_news,
            get_global_news,
        ]

        system_message = (
            "你是一名新闻研究员，负责分析过去一周的新闻和趋势。请撰写一份与交易和宏观经济相关的当前全球形势的全面报告。"
            "使用可用工具：get_news(query, start_date, end_date) 用于公司特定或定向新闻搜索，get_global_news(curr_date, look_back_days, limit) 用于更广泛的宏观经济新闻。"
            "对于中国 A 股和港股，当信息较少时，请同时使用交易所标准代码和公司名称进行搜索。"
            "请提供具体、可操作的见解和支撑证据，帮助交易员做出明智的决策。"
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
            "news_report": report,
        }

    return news_analyst_node
