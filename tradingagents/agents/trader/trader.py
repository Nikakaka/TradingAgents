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


def _build_primary_messages(
    company_name: str,
    instrument_context: str,
    investment_plan: str,
    past_memories: str,
):
    context = {
        "role": "user",
        "content": (
            f"Provide a practical trading recommendation for {company_name}. "
            f"{instrument_context}\n\n"
            f"Decision note from the research lead:\n{investment_plan}\n\n"
            "Return a concise recommendation with rationale and a clear final line in the form "
            "'FINAL RECOMMENDATION: BUY', 'FINAL RECOMMENDATION: HOLD', or "
            "'FINAL RECOMMENDATION: SELL'."
        ),
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are a trading agent making a practical investment decision from prior analyst work. "
                "Keep the tone calm, factual, and action-oriented. Recommend Buy, Hold, or Sell. "
                "Use the past lessons only as brief context.\n\n"
                f"Past lessons:\n{past_memories or '- No past lessons available.'}"
            ),
        },
        context,
    ]
    return messages


def _build_fallback_prompt(company_name: str, instrument_context: str, investment_plan: str) -> str:
    return (
        f"Provide a short trading recommendation for {company_name}.\n\n"
        "Return exactly:\n"
        "Recommendation: Buy, Hold, or Sell\n"
        "Reasons:\n"
        "- point 1\n"
        "- point 2\n"
        "Next step:\n"
        "- point 1\n"
        "Final line:\n"
        "FINAL RECOMMENDATION: BUY/HOLD/SELL\n\n"
        "Keep it neutral and concise.\n\n"
        f"{instrument_context}\n\n"
        f"Decision note:\n{investment_plan}"
    )


def _build_deterministic_fallback(instrument_context: str, investment_plan: str) -> AIMessage:
    summary = _sanitize_for_provider(investment_plan, max_chars=900) or "The research summary needs manual review."
    content = (
        "Recommendation: Hold\n"
        "Reasons:\n"
        "- The provider safety filter blocked automated trading synthesis.\n"
        f"- Research summary: {summary}\n"
        "Next step:\n"
        "- Review the research summary manually before placing a directional trade.\n"
        "FINAL RECOMMENDATION: HOLD"
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

        return {
            "messages": [result],
            "trader_investment_plan": result.content,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
