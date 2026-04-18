from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_news
from tradingagents.dataflows.config import get_config


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_news,
        ]

        system_message = (
            "你是一名社交媒体和公司新闻研究员/分析师，负责分析过去一周关于特定公司的社交媒体帖子、最新公司新闻和公众情绪。"
            "你将获得一家公司的名称，你的目标是撰写一份全面的长篇报告，详细说明你对这家公司当前状态的分析、见解以及对交易员和投资者的启示，"
            "包括查看社交媒体上人们对该公司的评论、分析每日情绪数据以及查看最新的公司新闻。"
            "使用 get_news(query, start_date, end_date) 工具搜索公司特定新闻和社交媒体讨论。"
            "对于中国 A 股和港股，如有需要，请同时尝试基于代码的查询和基于公司名称的查询。"
            "请尽量查看所有可能的信息来源，从社交媒体到情绪再到新闻。"
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
            "sentiment_report": report,
        }

    return social_media_analyst_node
