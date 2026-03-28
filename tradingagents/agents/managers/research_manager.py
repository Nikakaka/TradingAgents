import re

from langchain_core.messages import AIMessage

from tradingagents.agents.utils.agent_utils import build_instrument_context


def _sanitize_for_provider(text: str, max_chars: int = 6000) -> str:
    """Reduce provider filter risk by removing noisy or quote-heavy content."""
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
        "bull analyst": "view A",
        "bear analyst": "view B",
        "supportive analyst": "view A",
        "risk analyst": "view B",
        "bull case": "positive case",
        "bear case": "risk case",
        "debate": "discussion",
        "bull": "positive",
        "bear": "risk",
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


def _summarize_history_for_provider(text: str, max_points: int = 8, max_chars: int = 1800) -> str:
    sanitized = _sanitize_for_provider(text, max_chars=max_chars)
    if not sanitized:
        return ""

    pieces = re.split(r"[\n\r]+", sanitized)
    selected: list[str] = []
    for piece in pieces:
        compact = re.sub(r"\s+", " ", piece).strip(" -:*")
        if not compact:
            continue
        if len(compact) < 20:
            continue
        selected.append(f"- {compact}")
        if len(selected) >= max_points:
            break
    return "\n".join(selected)


def _build_ultra_safe_prompt(instrument_context: str, history_summary: str) -> str:
    return f"""Provide a short, neutral trading note for the instrument below.

Return exactly these sections:
Recommendation: Buy, Sell, or Hold
Reasons:
- point 1
- point 2
Next step:
- point 1

Keep the tone calm and factual. Avoid debate language.

{instrument_context}

Notes:
{history_summary or "- Limited analyst notes available."}"""


def _build_deterministic_fallback(instrument_context: str, history: str) -> AIMessage:
    history_summary = _summarize_history_for_provider(history, max_points=4, max_chars=900)
    content = (
        "Recommendation: Hold\n"
        "Reasons:\n"
        "- The provider safety filter blocked automated synthesis of the analyst discussion.\n"
        f"{history_summary or '- The available notes need manual review before a directional trade.'}\n"
        "Next step:\n"
        "- Review the analyst reports manually and rerun with a more neutral prompt if needed.\n"
    )
    return AIMessage(content=f"{instrument_context}\n\n{content}".strip())


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
                history=_summarize_history_for_provider(history, max_points=10, max_chars=2500),
            )
            try:
                response = llm.invoke(fallback_prompt)
            except Exception as fallback_exc:
                fallback_error = str(fallback_exc)
                if "1301" not in fallback_error and "contentFilter" not in fallback_error:
                    raise

                ultra_safe_prompt = _build_ultra_safe_prompt(
                    instrument_context=instrument_context,
                    history_summary=_summarize_history_for_provider(history, max_points=6, max_chars=1200),
                )
                try:
                    response = llm.invoke(ultra_safe_prompt)
                except Exception as ultra_exc:
                    ultra_error = str(ultra_exc)
                    if "1301" not in ultra_error and "contentFilter" not in ultra_error:
                        raise
                    response = _build_deterministic_fallback(
                        instrument_context=instrument_context,
                        history=history,
                    )

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
