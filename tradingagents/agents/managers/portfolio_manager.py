import re
import logging
from tradingagents.agents.utils.agent_utils import build_instrument_context
from tradingagents.agents.utils.analysis_memory import (
    get_analysis_memory,
    get_calibration,
    record_analysis,
    CalibrationResult,
)

logger = logging.getLogger(__name__)


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
    text = re.sub(r'<think>[\s\S]*?</think>', '', text)
    text = re.sub(r'<think>[\s\S]*$', '', text)
    # Handle orphaned close tags
    text = text.replace('</think>', '')

    # Pattern 6: Extended thinking tags (Claude format)
    # These tags contain the LLM's internal reasoning that should not appear in reports
    open_tag = chr(60) + 'think' + chr(62)
    close_tag = chr(60) + '/think' + chr(62)
    pattern = re.escape(open_tag) + r'[\s\S]*?' + re.escape(close_tag)
    text = re.sub(pattern, '', text)
    # Handle unclosed extended thinking tags
    text = re.sub(re.escape(open_tag) + r'[\s\S]*$', '', text)
    # Handle orphaned close tags
    text = text.replace(close_tag, '')

    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _extract_signal_and_confidence(content: str) -> tuple:
    """Extract trading signal and confidence from portfolio manager response.

    Returns:
        Tuple of (signal, confidence) where signal is one of buy/hold/sell
        and confidence is a float between 0 and 1.
    """
    if not content:
        return "hold", 0.5

    content_lower = content.lower()

    # Extract signal from the response
    signal = "hold"
    if "**评级**：" in content or "评级：" in content:
        rating_line = ""
        for line in content.split("\n"):
            if "评级" in line:
                rating_line = line.lower()
                break

        if "买入" in rating_line:
            signal = "buy"
        elif "卖出" in rating_line:
            signal = "sell"
        elif "持有" in rating_line or "观望" in rating_line:
            signal = "hold"
        elif "超配" in rating_line:
            signal = "buy"  # Treat overweight as buy signal
        elif "低配" in rating_line:
            signal = "sell"  # Treat underweight as sell signal
    else:
        # Fallback: look for signal keywords anywhere
        if "买入" in content_lower:
            signal = "buy"
        elif "卖出" in content_lower:
            signal = "sell"

    # Extract or estimate confidence
    confidence = 0.5

    # Look for explicit confidence mentions
    import re
    conf_match = re.search(r'置信度[：:]\s*(\d+(?:\.\d+)?)\s*%', content)
    if conf_match:
        confidence = float(conf_match.group(1)) / 100
    else:
        # Estimate confidence based on language strength
        strong_words = ["强烈", "明确", "坚定", "确认"]
        weak_words = ["可能", "或许", "待观察", "谨慎", "不确定性"]

        strong_count = sum(1 for w in strong_words if w in content)
        weak_count = sum(1 for w in weak_words if w in content)

        if strong_count > weak_count:
            confidence = 0.7
        elif weak_count > strong_count:
            confidence = 0.4

    return signal, min(1.0, max(0.1, confidence))


def create_portfolio_manager(llm, memory):
    def portfolio_manager_node(state) -> dict:

        instrument_context = build_instrument_context(state["company_of_interest"])
        ticker = state["company_of_interest"]
        analysis_date = state.get("trade_date", "")

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        research_plan = state["investment_plan"]  # 研究经理的投资计划
        trader_plan = state["trader_investment_plan"]  # 交易员的交易提案

        # Get historical calibration for this ticker
        calibration = get_calibration(ticker=ticker)
        calibration_context = ""
        if calibration.calibrated:
            calibration_context = f"""
**历史校准信息**：
- 该股票历史分析准确率：{calibration.accuracy:.1%}
- 买入信号准确率：{calibration.buy_accuracy:.1%}
- 卖出信号准确率：{calibration.sell_accuracy:.1%}
- 持有信号准确率：{calibration.hold_accuracy:.1%}
- 样本数：{calibration.total_samples}次

请根据历史准确率调整您的置信度评估。
"""
            logger.info(f"Applied calibration for {ticker}: accuracy={calibration.accuracy:.1%}, factor={calibration.calibration_factor:.2f}")

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""作为投资组合经理，综合风险分析师的辩论并给出最终交易决策。

{instrument_context}

---

**评级标准**（仅使用其中一个）：
- **买入**：有强烈信心建仓或加仓
- **超配**：前景看好，逐步增加敞口
- **持有**：维持当前仓位，无需行动
- **低配**：减少敞口，部分获利了结
- **卖出**：清仓或避免入场

**背景：**
- 研究经理的投资计划：**{research_plan}**
- 交易员的交易提案：**{trader_plan}**
- 过往决策经验：**{past_memory_str}**
{calibration_context}
**必需的输出格式（严格按此格式）：**

**评级**：[选择：买入 / 超配 / 持有 / 低配 / 卖出]

**执行摘要**：[2-3句话说明入场策略、仓位大小、关键风险位和时间期限]

**投资逻辑**：[基于分析师辩论的详细论证]

---

**风险分析师辩论历史：**
{history}

---

**重要提示**：以评级行开头。不要在评级前添加任何开场白。

示例输出：
**评级**：持有
**执行摘要**：维持当前仓位，在关键支撑位设置紧止损。等待技术确认后再增加敞口。
**投资逻辑**：基本面增长逻辑依然成立，但近期技术弱势和内部人卖出值得警惕...
请使用中文撰写回复。
"""

        response = llm.invoke(prompt)

        # Clean pseudo tool calls from response
        cleaned_content = _clean_pseudo_tool_calls(response.content)

        # Extract signal and confidence for recording
        signal, confidence = _extract_signal_and_confidence(cleaned_content)

        # Apply calibration to confidence if available
        if calibration.calibrated:
            original_confidence = confidence
            confidence = min(1.0, max(0.1, confidence * calibration.calibration_factor))
            logger.info(f"Calibrated confidence: {original_confidence:.2f} -> {confidence:.2f}")

        # Record the analysis for future calibration
        try:
            analysis_memory = get_analysis_memory()
            analysis_memory.record_analysis(
                ticker=ticker,
                analysis_date=analysis_date,
                signal=signal,
                confidence=confidence,
                reasoning=cleaned_content[:500],
                agent_name="portfolio_manager",
            )
        except Exception as e:
            logger.warning(f"Failed to record analysis: {e}")

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
