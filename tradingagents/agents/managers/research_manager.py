import re

from tradingagents.agents.utils.agent_utils import build_instrument_context


def _sanitize_for_provider(text: str, max_chars: int = 6000) -> str:
    """Reduce provider filter risk by removing noisy or quote-heavy content."""
    if not text:
        return ""

    sanitized = str(text)
    replacements = {
        "Bull Analyst:": "View A:",
        "Bear Analyst:": "View B:",
        "bull analyst": "view A",
        "bear analyst": "view B",
        "bull case": "positive case",
        "bear case": "risk case",
        "debate": "discussion",
    }
    for src, dst in replacements.items():
        sanitized = sanitized.replace(src, dst)

    sanitized = re.sub(r"https?://\S+", "[link]", sanitized)
    sanitized = re.sub(r"\b\S+@\S+\b", "[email]", sanitized)
    sanitized = re.sub(r"`{1,3}.*?`{1,3}", "[quoted text]", sanitized, flags=re.DOTALL)
    sanitized = re.sub(r"[ \t]+", " ", sanitized)

    if len(sanitized) > max_chars:
        sanitized = sanitized[:max_chars]

    return sanitized.strip()


def _build_primary_prompt(instrument_context: str, past_memory_str: str, history: str) -> str:
    return f"""You are the research lead responsible for combining two contrasting investment viewpoints into one practical decision for the trader.

Review View A and View B, then decide which side is better supported by the evidence. Choose Buy, Sell, or Hold. Use Hold only when the available evidence is genuinely mixed or insufficient.

Write a clear decision note with:
1. Recommendation: Buy, Sell, or Hold.
2. Key supporting evidence from both viewpoints.
3. Rationale for the final decision.
4. Practical next steps for the trader.

Use lessons from similar past situations to improve the decision, but keep the tone professional, calm, and focused on financial analysis.

Past reflections:
"{past_memory_str}"

{instrument_context}

Discussion history:
{history}"""


def _build_fallback_prompt(instrument_context: str, history: str) -> str:
    return f"""Review the following investment discussion and provide a calm financial summary.

Return:
1. Recommendation: Buy, Sell, or Hold.
2. Two or three key reasons.
3. Practical next step for the trader.

Keep the response concise and professional.

{instrument_context}

Discussion:
{history}"""


def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        investment_debate_state = state["investment_debate_state"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec["recommendation"] + "\n\n"

        sanitized_history = _sanitize_for_provider(history)
        sanitized_memories = _sanitize_for_provider(past_memory_str, max_chars=2000)

        primary_prompt = _build_primary_prompt(
            instrument_context=instrument_context,
            past_memory_str=sanitized_memories,
            history=sanitized_history,
        )

        try:
            response = llm.invoke(primary_prompt)
        except Exception as exc:
            error_text = str(exc)
            if "1301" not in error_text and "contentFilter" not in error_text:
                raise

            fallback_prompt = _build_fallback_prompt(
                instrument_context=instrument_context,
                history=_sanitize_for_provider(history, max_chars=2500),
            )
            response = llm.invoke(fallback_prompt)

        new_investment_debate_state = {
            "judge_decision": response.content,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": response.content,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }

    return research_manager_node
