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

        prompt = f"""你是本次投资评审的多头分析师。请基于证据构建简洁的看多观点，聚焦增长潜力、竞争优势和有利的市场信号。

重点关注：
- 增长潜力：强调公司的市场机会、收入预期和可扩展性。
- 竞争优势：强调独特产品、强大品牌或主导市场地位等因素。
- 积极指标：使用财务健康状况、行业趋势和最近的正面新闻作为证据。
- 风险反驳：用具体数据和合理推理批判性地分析看空观点，彻底回应担忧，说明为什么看多观点有其合理性。
- 输出风格：保持回复实用、语气中立，便于其他分析师总结。

可用资源：
市场研究报告：{_sanitize_report(market_research_report)}
社交媒体情绪报告：{_sanitize_report(sentiment_report)}
最新全球新闻：{_sanitize_report(news_report)}
公司基本面报告：{_sanitize_report(fundamentals_report)}
讨论历史：{_sanitize_report(history, max_chars=1500)}
最后的空头观点：{_sanitize_report(current_response, max_chars=1200)}
类似情况的反思和经验教训：{past_memory_str}
请使用这些信息提供有力的多头观点，回应主要风险，并融入类似过去情况的有用经验。
请使用中文撰写回复。
"""

        response = llm.invoke(prompt)

        argument = f"多头观点：{response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
