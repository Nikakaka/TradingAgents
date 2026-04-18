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

    # Pattern 1: Pseudo tool call blocks
    pattern1 = r'<tool_call>\w+\([^)]*\)(?:<tool_call>\w+\([^)]*\))*'
    text = re.sub(pattern1, '', text)

    # Pattern 2: Single pseudo tool calls
    pattern2 = r'<tool_call>\w+\([^)]*\)'
    text = re.sub(pattern2, '', text)

    # Pattern 3: Trailing tool call remnants
    pattern3 = r'\n\s*<tool_call>\w+\([^)]*\)\s*\n'
    text = re.sub(pattern3, '\n', text)

    # Pattern 4: Tool calls followed by content without proper spacing
    pattern4 = r'<tool_call>\w+\([^)]*\)\s*'
    text = re.sub(pattern4, '', text)

    # Clean up multiple consecutive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _fallback_argument(trader_decision: str) -> str:
    summary = _sanitize_report(trader_decision, max_chars=900) or "研究摘要需要人工审查。"
    return (
        "激进分析师：从成长型视角审查建议。\n"
        "- 仅在上行催化剂仍然可信时保持敞口。\n"
        f"- 当前计划摘要：{summary}\n"
        "- 使用仓位控制和止损来管理高波动情形。"
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

        prompt = f"""你是成长型风险评审员。

请从高确定性视角撰写一份简短说明。重点关注：
- 可能支持看涨立场的上行催化剂，
- 交易成功所需的主要条件，
- 实用的风险控制措施，如入场纪律、仓位控制或止损。

保持语气事实性和专业性。不要与其他分析师争论。

交易员决策：
{_sanitize_report(trader_decision, max_chars=1400)}

市场研究：
{_sanitize_report(market_research_report, max_chars=1000)}

情绪：
{_sanitize_report(sentiment_report, max_chars=800)}

新闻：
{_sanitize_report(news_report, max_chars=800)}

基本面：
{_sanitize_report(fundamentals_report, max_chars=800)}

先前讨论：
{_sanitize_report(history, max_chars=900)}

其他观点：
- 风险控制观点：{_sanitize_report(current_conservative_response, max_chars=500)}
- 平衡观点：{_sanitize_report(current_neutral_response, max_chars=500)}
请使用中文撰写回复。
"""

        try:
            response = llm.invoke(prompt)
            argument = f"激进分析师：{_clean_pseudo_tool_calls(response.content)}"
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
