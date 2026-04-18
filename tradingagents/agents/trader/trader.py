import functools
import re

from langchain_core.messages import AIMessage

from tradingagents.agents.utils.agent_utils import build_instrument_context


def _sanitize_for_provider(text: str, max_chars: int = 5000) -> str:
    if not text:
        return ""

    sanitized = str(text)
    replacements = {
        "Bull Analyst:": "View A:",
        "Bear Analyst:": "View B:",
        "Supportive Analyst:": "View A:",
        "Risk Analyst:": "View B:",
        "Supportive View:": "View A:",
        "Risk View:": "View B:",
        "FINAL TRANSACTION PROPOSAL": "FINAL RECOMMENDATION",
        "bull": "positive",
        "bear": "risk",
        "debate": "discussion",
    }
    for src, dst in replacements.items():
        sanitized = sanitized.replace(src, dst)

    sanitized = re.sub(r"https?://\S+", "[link]", sanitized)
    sanitized = re.sub(r"\b\S+@\S+\b", "[email]", sanitized)
    sanitized = re.sub(r"`{1,3}.*?`{1,3}", "[quoted text]", sanitized, flags=re.DOTALL)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized[:max_chars]


def _clean_pseudo_tool_calls(text: str) -> str:
    """Remove pseudo tool call patterns that LLMs sometimes hallucinate.

    Some models output text like:
    - "<tool_call>get_price_data("ticker")<tool_call>get_financial_data("ticker")"
    - "<tool_call>get_price_data("ticker")1080"

    These are not real tool calls but model hallucinations that should be cleaned.
    """
    if not text:
        return text

    # Pattern 1: Pseudo tool call blocks
    pattern1 = r'<tool_call>\w+\([^)]*\)(?:<tool_call>\w+\([^)]*\))*'
    text = re.sub(pattern1, '', text)

    # Pattern 2: Single pseudo tool calls
    pattern2 = r'<tool_call>\w+\([^)]*\)'
    text = re.sub(pattern2, '', text)

    # Pattern 3: Trailing tool call remnants
    pattern3 = r'\n\s*<tool_call>\w+\([^)]*\)\s*\n'
    text = re.sub(pattern3, '\n', text)

    # Pattern 4: Tool calls followed by content without proper spacing
    pattern4 = r'<tool_call>\w+\([^)]*\)\s*'
    text = re.sub(pattern4, '', text)

    # Clean up multiple consecutive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _build_primary_messages(
    company_name: str,
    instrument_context: str,
    investment_plan: str,
    past_memories: str,
):
    context = {
        "role": "user",
        "content": (
            f"请为 {company_name} 提供一个实用的交易建议。"
            f"{instrument_context}\n\n"
            f"研究主管的决策说明：\n{investment_plan}\n\n"
            "返回一份简洁的建议，包含理由和清晰的最后一行，格式为"
            "'最终建议：买入'、'最终建议：持有' 或 '最终建议：卖出'。"
            "请使用中文撰写。"
        ),
    }

    messages = [
        {
            "role": "system",
            "content": (
                "你是一名交易员，根据之前的分析师工作做出实际的投资决策。"
                "保持语气冷静、事实性、以行动为导向。建议买入、持有或卖出。"
                "仅将过去的经验教训作为简短背景。\n\n"
                f"过去的经验教训：\n{past_memories or '- 无可用经验教训。'}"
            ),
        },
        context,
    ]
    return messages


def _build_fallback_prompt(company_name: str, instrument_context: str, investment_plan: str) -> str:
    return (
        f"请为 {company_name} 提供一个简短的交易建议。\n\n"
        "严格按以下格式返回：\n"
        "建议：买入、持有或卖出\n"
        "理由：\n"
        "- 要点 1\n"
        "- 要点 2\n"
        "下一步行动：\n"
        "- 要点 1\n"
        "最后一行：\n"
        "最终建议：买入/持有/卖出\n\n"
        "保持中立简洁。\n\n"
        f"{instrument_context}\n\n"
        f"决策说明：\n{investment_plan}"
        "请使用中文撰写。"
    )


def _build_deterministic_fallback(instrument_context: str, investment_plan: str) -> AIMessage:
    summary = _sanitize_for_provider(investment_plan, max_chars=900) or "研究摘要需要人工审查。"
    content = (
        "建议：持有\n"
        "理由：\n"
        "- 提供商安全过滤器阻止了自动交易综合。\n"
        f"- 研究摘要：{summary}\n"
        "下一步行动：\n"
        "- 在进行方向性交易前人工审查研究摘要。\n"
        "最终建议：持有"
    )
    return AIMessage(content=f"{instrument_context}\n\n{content}".strip())


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for rec in past_memories:
                past_memory_str += rec["recommendation"] + "\n\n"

        sanitized_plan = _sanitize_for_provider(investment_plan, max_chars=2500)
        sanitized_memories = _sanitize_for_provider(past_memory_str, max_chars=1500)

        messages = _build_primary_messages(
            company_name=company_name,
            instrument_context=instrument_context,
            investment_plan=sanitized_plan,
            past_memories=sanitized_memories,
        )

        try:
            result = llm.invoke(messages)
        except Exception as exc:
            error_text = str(exc)
            if "1301" not in error_text and "contentFilter" not in error_text:
                raise
            fallback_prompt = _build_fallback_prompt(
                company_name=company_name,
                instrument_context=instrument_context,
                investment_plan=sanitized_plan[:1200],
            )
            try:
                result = llm.invoke(fallback_prompt)
            except Exception as fallback_exc:
                fallback_error = str(fallback_exc)
                if "1301" not in fallback_error and "contentFilter" not in fallback_error:
                    raise
                result = _build_deterministic_fallback(
                    instrument_context=instrument_context,
                    investment_plan=sanitized_plan,
                )

        # Clean any pseudo tool calls from the response
        cleaned_content = _clean_pseudo_tool_calls(_extract_content(result))

        return {
            "messages": [AIMessage(content=cleaned_content)],
            "trader_investment_plan": cleaned_content,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")


def _extract_content(result) -> str:
    """Extract text content from LLM response."""
    if hasattr(result, "content"):
        return result.content
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("content", result.get("text", str(result)))
    return str(result)
