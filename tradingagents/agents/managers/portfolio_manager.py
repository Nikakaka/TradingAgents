import re

from tradingagents.agents.utils.agent_utils import build_instrument_context


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

    # Pattern 5: Remove thinking blocks (used by DeepSeek, GLM reasoning models)
    text = re.sub(r'[\s\S]*?', '', text)
    text = re.sub(r'[\s\S]*$', '', text)

    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def create_portfolio_manager(llm, memory):
    def portfolio_manager_node(state) -> dict:

        instrument_context = build_instrument_context(state["company_of_interest"])

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision.

{instrument_context}

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction to enter or add to position
- **Overweight**: Favorable outlook, gradually increase exposure
- **Hold**: Maintain current position, no action needed
- **Underweight**: Reduce exposure, take partial profits
- **Sell**: Exit position or avoid entry

**Context:**
- Trader's proposed plan: **{trader_plan}**
- Lessons from past decisions: **{past_memory_str}**

**Required Output Structure (STRICTLY follow this format):**

**Rating**: [One of: Buy / Overweight / Hold / Underweight / Sell]

**Executive Summary**: [2-3 sentences on entry strategy, position sizing, key risk levels, and time horizon]

**Investment Thesis**: [Detailed reasoning anchored in the analysts' debate]

---

**Risk Analysts Debate History:**
{history}

---

**IMPORTANT**: Start your response with the Rating line. Do not add introductory text before the Rating.

Example output:
**Rating**: Hold
**Executive Summary**: Maintain current position with tight stop-loss at key support. Wait for technical confirmation before adding exposure.
**Investment Thesis**: The fundamental growth story remains intact, but near-term technical weakness and insider selling warrant caution..."""

        response = llm.invoke(prompt)

        # Clean pseudo tool calls from response
        cleaned_content = _clean_pseudo_tool_calls(response.content)

        new_risk_debate_state = {
            "judge_decision": cleaned_content,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": cleaned_content,
        }

    return portfolio_manager_node
