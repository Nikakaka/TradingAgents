import re


def _sanitize_report(text: str, max_chars: int = 3500) -> str:
    if not text:
        return ""
    sanitized = re.sub(r"https?://\S+", "[link]", str(text))
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized[:max_chars]


def create_bull_researcher(llm, memory):
    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

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

        prompt = f"""You are the Supportive Analyst for this investment review. Build a concise, evidence-based case for the more constructive interpretation of the stock, focusing on growth potential, competitive strengths, and favorable market signals.

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Risk Counterpoints: Critically analyze the risk view with specific data and sound reasoning, addressing concerns thoroughly and showing why the constructive perspective has merit.
- Output Style: Keep the response practical, neutral in tone, and easy for another analyst to summarize.

Resources available:
Market research report: {_sanitize_report(market_research_report)}
Social media sentiment report: {_sanitize_report(sentiment_report)}
Latest world affairs news: {_sanitize_report(news_report)}
Company fundamentals report: {_sanitize_report(fundamentals_report)}
Conversation history of the discussion: {_sanitize_report(history, max_chars=1500)}
Last risk view: {_sanitize_report(current_response, max_chars=1200)}
Reflections from similar situations and lessons learned: {past_memory_str}
Use this information to deliver a strong supportive view, address the main risks, and incorporate useful lessons from similar past situations.
"""

        response = llm.invoke(prompt)

        argument = f"Supportive View: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
