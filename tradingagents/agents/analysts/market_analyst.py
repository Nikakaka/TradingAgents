from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_indicators,
    get_stock_data,
)
from tradingagents.dataflows.config import get_config


def create_market_analyst(llm):
    config = get_config()
    provider = (config.get("llm_provider") or "").lower()

    full_system_message = (
        "You are a market analyst. First call get_stock_data, then use get_indicators to inspect the market setup in a disciplined way. "
        "Choose indicators deliberately across trend, momentum, volatility, and volume, and avoid redundant requests. "
        "Only use supported indicator names from this list: close_50_sma, close_200_sma, close_10_ema, macd, macds, macdh, rsi, boll, boll_ub, boll_lb, atr, vwma, mfi. "
        "Call get_indicators one indicator at a time. "
        "Build an evidence-based market report that covers the current price structure, trend strength, momentum shifts, volatility regime, support and resistance, and likely trading implications. "
        "Use the indicator evidence to explain both the constructive case and the risk case before reaching a balanced conclusion. "
        "Append a short Markdown table summarizing the main signals."
    )

    local_system_message = (
        "You are a market analyst. First call get_stock_data, then select only the most useful indicators for the current setup and call get_indicators one indicator at a time. "
        "Choose at most 6 indicators from this list: close_50_sma, close_200_sma, close_10_ema, macd, macds, macdh, rsi, boll, boll_ub, boll_lb, atr, vwma. "
        "Prefer diverse signals across trend, momentum, volatility, and volume. Avoid redundant choices. "
        "Write a concise but evidence-based market report covering price trend, momentum, volatility, key support/resistance, and trading implications. "
        "Append a short Markdown table summarizing the main signals."
    )

    system_message = local_system_message if provider == "ollama" else full_system_message

    def market_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_stock_data,
            get_indicators,
        ]

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}\n"
                    "For your reference, the current date is {current_date}. {instrument_context}",
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
            "market_report": report,
        }

    return market_analyst_node
