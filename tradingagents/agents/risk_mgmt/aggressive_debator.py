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
        "Aggressive Analyst: Recommendation review from a growth-focused perspective.\n"
        "- Maintain exposure only if upside catalysts remain credible.\n"
        f"- Current plan summary: {summary}\n"
        "- Use position sizing and stop-loss controls to manage higher-volatility scenarios."
    )


def create_aggressive_debator(llm):
    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        trader_decision = state["trader_investment_plan"]

        prompt = f"""You are the growth-focused risk reviewer.

Provide a short note from a higher-conviction perspective. Focus on:
- upside catalysts that could justify staying constructive,
- the main conditions required for the trade to work,
- practical guardrails such as entry discipline, sizing, or stops.

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
- Risk-control view: {_sanitize_report(current_conservative_response, max_chars=500)}
- Balanced view: {_sanitize_report(current_neutral_response, max_chars=500)}
"""

        try:
            response = llm.invoke(prompt)
            argument = f"Aggressive Analyst: {response.content}"
        except Exception as exc:
            error_text = str(exc)
            if "1301" not in error_text and "contentFilter" not in error_text:
                raise
            argument = _fallback_argument(trader_decision)

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
