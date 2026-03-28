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


def _fallback_argument(trader_decision: str) -> str:
    summary = _sanitize_report(trader_decision, max_chars=900) or "Research summary requires manual review."
    return (
        "Conservative Analyst: Recommendation review from a capital-protection perspective.\n"
        "- Focus on downside containment and avoid oversized conviction.\n"
        f"- Current plan summary: {summary}\n"
        "- Prefer smaller sizing or waiting for stronger confirmation before increasing exposure."
    )


def create_conservative_debator(llm):
    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        trader_decision = state["trader_investment_plan"]

        prompt = f"""You are the capital-protection risk reviewer.

Provide a short note from a conservative perspective. Focus on:
- downside risks that could break the trade,
- balance-sheet or macro risks that deserve caution,
- practical controls such as smaller size, tighter risk limits, or waiting for confirmation.

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
- Balanced view: {_sanitize_report(current_neutral_response, max_chars=500)}
"""

        try:
            response = llm.invoke(prompt)
            argument = f"Conservative Analyst: {response.content}"
        except Exception as exc:
            error_text = str(exc)
            if "1301" not in error_text and "contentFilter" not in error_text:
                raise
            argument = _fallback_argument(trader_decision)

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
