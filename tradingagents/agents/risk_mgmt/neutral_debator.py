import re


def _sanitize_report(text: str, max_chars: int = 2500) -> str:
    if not text:
        return ""
    sanitized = str(text)
    replacements = {
        "Aggressive Analyst:": "Growth-Focused View:",
        "Conservative Analyst:": "Risk-Control View:",
        "Neutral Analyst:": "Balanced View:",
        "FINAL TRANSACTION PROPOSAL": "FINAL RECOMMENDATION",
    }
    for src, dst in replacements.items():
        sanitized = sanitized.replace(src, dst)
    sanitized = re.sub(r"https?://\S+", "[link]", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized[:max_chars]


def _clean_pseudo_tool_calls(text: str) -> str:
    """Remove pseudo tool call patterns that LLMs sometimes hallucinate."""
    if not text:
        return text

    pattern1 = r'<tool_call>\w+\([^)]*\)(?:<tool_call>\w+\([^)]*\))*'
    text = re.sub(pattern1, '', text)
    pattern2 = r'<tool_call>\w+\([^)]*\)'
    text = re.sub(pattern2, '', text)
    pattern3 = r'\n\s*<tool_call>\w+\([^)]*\)\s*\n'
    text = re.sub(pattern3, '\n', text)
    pattern4 = r'<tool_call>\w+\([^)]*\)\s*'
    text = re.sub(pattern4, '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _fallback_argument(trader_decision: str) -> str:
    summary = _sanitize_report(trader_decision, max_chars=900) or "Research summary requires manual review."
    return (
        "Neutral Analyst: Recommendation review from a balanced perspective.\n"
        "- Weigh upside and downside before changing exposure materially.\n"
        f"- Current plan summary: {summary}\n"
        "- Prefer staged execution and confirmation from price action or fundamentals."
    )


def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        trader_decision = state["trader_investment_plan"]

        prompt = f"""You are the balanced risk reviewer.

Provide a short note from a neutral perspective. Focus on:
- where the constructive case is credible,
- where the downside case is still meaningful,
- a practical middle-ground execution plan.

Keep the tone factual and professional. Do not argue with other analysts.

Trader decision:
{_sanitize_report(trader_decision, max_chars=1400)}

Market research:
{_sanitize_report(market_research_report, max_chars=1000)}

Sentiment:
{_sanitize_report(sentiment_report, max_chars=800)}

News:
{_sanitize_report(news_report, max_chars=800)}

Fundamentals:
{_sanitize_report(fundamentals_report, max_chars=800)}

Prior discussion:
{_sanitize_report(history, max_chars=900)}

Other views:
- Growth-focused view: {_sanitize_report(current_aggressive_response, max_chars=500)}
- Risk-control view: {_sanitize_report(current_conservative_response, max_chars=500)}
"""

        try:
            response = llm.invoke(prompt)
            argument = f"Neutral Analyst: {_clean_pseudo_tool_calls(response.content)}"
        except Exception as exc:
            error_text = str(exc)
            if "1301" not in error_text and "contentFilter" not in error_text:
                raise
            argument = _fallback_argument(trader_decision)

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
