import re


def _sanitize_report(text: str, max_chars: int = 3500) -> str:
    if not text:
        return ""
    sanitized = re.sub(r"https?://\S+", "[link]", str(text))
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized[:max_chars]


def create_bear_researcher(llm, memory):
    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""You are the Risk Analyst for this investment review. Present a concise, evidence-based risk case for the stock, focusing on downside drivers, execution challenges, and weak market signals.

Key points to focus on:

- Risks and Challenges: Highlight factors like market saturation, financial instability, or macroeconomic threats that could hinder the stock's performance.
- Competitive Weaknesses: Emphasize vulnerabilities such as weaker market positioning, declining innovation, or threats from competitors.
- Negative Indicators: Use evidence from financial data, market trends, or recent adverse news to support your position.
- Supportive Counterpoints: Critically analyze the supportive view with specific data and sound reasoning, exposing weak assumptions or over-optimistic interpretations.
- Output Style: Keep the response practical, neutral in tone, and easy for another analyst to summarize.

Resources available:

Market research report: {_sanitize_report(market_research_report)}
Social media sentiment report: {_sanitize_report(sentiment_report)}
Latest world affairs news: {_sanitize_report(news_report)}
Company fundamentals report: {_sanitize_report(fundamentals_report)}
Conversation history of the discussion: {_sanitize_report(history, max_chars=1500)}
Last supportive view: {_sanitize_report(current_response, max_chars=1200)}
Reflections from similar situations and lessons learned: {past_memory_str}
Use this information to deliver a strong risk view, address the constructive case, and incorporate useful lessons from similar past situations.
"""

        response = llm.invoke(prompt)

        argument = f"Risk View: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
