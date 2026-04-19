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


def _calculate_sentiment_score(
    signal: str,
    confidence: float,
    risk_factors: dict = None,
    debate_context: str = None,
) -> int:
    """Calculate sentiment score (0-100) based on multiple dimensions.

    Multi-dimensional scoring system:
    1. Base score from signal type (40% weight)
    2. Confidence adjustment (20% weight)
    3. Risk factor penalties (25% weight)
    4. Debate sentiment analysis (15% weight)

    Scoring bands:
    - 80-100: Strong buy (all conditions met, high conviction)
    - 60-79: Buy (mostly positive, minor caveats)
    - 40-59: Hold (mixed signals, or risk present)
    - 20-39: Sell (negative trend + risk)
    - 0-19: Strong sell (major risk + bearish)

    Args:
        signal: Trading signal (buy/hold/sell)
        confidence: Confidence level (0-1)
        risk_factors: Optional dict with risk information
        debate_context: Optional debate history text for sentiment analysis

    Returns:
        Integer score between 0-100
    """
    # === 1. Base Score from Signal (40% weight) ===
    signal_scores = {
        "buy": 75,    # Base bullish score
        "hold": 50,   # Neutral
        "sell": 25,   # Base bearish score
    }
    base_score = signal_scores.get(signal, 50)

    # === 2. Confidence Adjustment (20% weight) ===
    # Confidence modulates the score towards extremes
    # High confidence pushes buy higher, sell lower
    if signal == "buy":
        confidence_adjustment = (confidence - 0.5) * 30  # -15 to +15
    elif signal == "sell":
        confidence_adjustment = -(confidence - 0.5) * 30  # -15 to +15 (inverse for sell)
    else:  # hold
        confidence_adjustment = (confidence - 0.5) * 10  # -5 to +5

    # === 3. Risk Factor Penalties (25% weight) ===
    risk_penalty = 0
    if risk_factors:
        # Severity-based penalties
        high_severity = risk_factors.get("high_severity_count", 0)
        medium_severity = risk_factors.get("medium_severity_count", 0)

        risk_penalty += min(high_severity * 12, 36)  # Cap at 36 points
        risk_penalty += min(medium_severity * 5, 20)   # Cap at 20 points

        # Specific risk types
        if risk_factors.get("cashflow_issue", False):
            risk_penalty += 8
        if risk_factors.get("inventory_risk", False):
            risk_penalty += 5
        if risk_factors.get("debt_risk", False):
            risk_penalty += 7
        if risk_factors.get("governance_issue", False):
            risk_penalty += 10

    # === 4. Debate Sentiment Analysis (15% weight) ===
    debate_adjustment = 0
    if debate_context:
        debate_adjustment = _analyze_debate_sentiment(debate_context)

    # === Final Score Calculation ===
    raw_score = base_score + confidence_adjustment - risk_penalty + debate_adjustment

    # Apply signal-specific bounds
    if signal == "buy":
        # Buy signals should stay in 50-95 range
        final_score = max(50, min(95, raw_score))
    elif signal == "sell":
        # Sell signals should stay in 5-50 range
        final_score = max(5, min(50, raw_score))
    else:  # hold
        # Hold signals should stay in 35-65 range
        final_score = max(35, min(65, raw_score))

    return int(final_score)


def _analyze_debate_sentiment(debate_text: str) -> int:
    """Analyze debate context for sentiment signals.

    Returns adjustment score from -15 to +15.
    """
    if not debate_text:
        return 0

    text_lower = debate_text.lower()
    adjustment = 0

    # Positive sentiment keywords (bullish)
    positive_keywords = [
        "增长强劲", "业绩超预期", "估值合理", "技术突破",
        "资金流入", "机构增持", "基本面改善", "行业景气",
        "利好", "上升趋势", "支撑强劲"
    ]

    # Negative sentiment keywords (bearish)
    negative_keywords = [
        "业绩下滑", "估值过高", "技术破位", "资金流出",
        "机构减持", "基本面恶化", "行业衰退", "利空",
        "下降趋势", "阻力强劲", "风险加大"
    ]

    # Count occurrences
    positive_count = sum(1 for kw in positive_keywords if kw in text_lower or kw in debate_text)
    negative_count = sum(1 for kw in negative_keywords if kw in text_lower or kw in debate_text)

    # Calculate adjustment
    sentiment_diff = positive_count - negative_count
    adjustment = min(max(sentiment_diff * 3, -15), 15)

    return adjustment


def _extract_risk_factors(history: str) -> dict:
    """Extract risk factors from debate history for score adjustment.

    Note: Each risk keyword is counted at most once to avoid over-penalization.
    """
    risk_factors = {
        "high_severity_count": 0,
        "medium_severity_count": 0,
        "cashflow_issue": False,
        "inventory_risk": False,
        "debt_risk": False,
        "governance_issue": False,
    }

    if not history:
        return risk_factors

    history_lower = history.lower()

    # Count severity mentions (each keyword at most once)
    high_keywords = ["高风险", "重大风险", "严重", "critical", "重大隐患", "重大利空"]
    medium_keywords = ["中等风险", "需关注", "风险提示", "谨慎", "不确定性"]

    # Count unique occurrences of each severity level
    for kw in high_keywords:
        if kw in history_lower or kw in history:
            risk_factors["high_severity_count"] += 1
            break  # Only count once per severity level

    for kw in medium_keywords:
        if kw in history_lower or kw in history:
            risk_factors["medium_severity_count"] += 1
            break  # Only count once per severity level

    # Check for specific risk types (boolean flags)
    if any(kw in history for kw in ["现金流", "经营现金流", "资金链", "流动性风险"]):
        risk_factors["cashflow_issue"] = True

    if any(kw in history for kw in ["存货", "库存", "存货周转", "库存积压"]):
        risk_factors["inventory_risk"] = True

    if any(kw in history for kw in ["债务", "负债率", "偿债能力", "财务杠杆"]):
        risk_factors["debt_risk"] = True

    if any(kw in history for kw in ["治理", "内控", "违规", "处罚", "诉讼"]):
        risk_factors["governance_issue"] = True

    return risk_factors


def _get_score_label(score: int) -> str:
    """Get a descriptive label for the sentiment score."""
    if score >= 80:
        return "强烈看好"
    elif score >= 60:
        return "偏多"
    elif score >= 40:
        return "中性"
    elif score >= 20:
        return "偏空"
    else:
        return "强烈看空"


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

    # Look for explicit confidence mentions (multiple patterns)
    conf_patterns = [
        r'置信度[：:]\s*(\d+(?:\.\d+)?)\s*%',  # 置信度：70%
        r'信心[：:]\s*(\d+(?:\.\d+)?)\s*%',    # 信心：70%
        r'确定性[：:]\s*(\d+(?:\.\d+)?)\s*%',  # 确定性：70%
        r'把握[：:]\s*(\d+(?:\.\d+)?)\s*%',    # 把握：70%
    ]

    for pattern in conf_patterns:
        conf_match = re.search(pattern, content)
        if conf_match:
            confidence = float(conf_match.group(1)) / 100
            break
    else:
        # Estimate confidence based on multiple factors
        confidence = _estimate_confidence_from_content(content, signal)

    return signal, min(1.0, max(0.1, confidence))


def _estimate_confidence_from_content(content: str, signal: str) -> float:
    """Estimate confidence from content analysis.

    Uses multiple signals:
    1. Language strength (strong/weak words)
    2. Evidence quality (data points, percentages mentioned)
    3. Certainty expressions
    4. Risk acknowledgment balance
    """
    content_lower = content.lower()

    # Base confidence
    base_confidence = 0.5

    # Factor 1: Language strength
    strong_words = ["强烈", "明确", "坚定", "确认", "确信", "无疑", "必然"]
    weak_words = ["可能", "或许", "待观察", "谨慎", "不确定性", "或许", "似乎"]

    strong_count = sum(1 for w in strong_words if w in content)
    weak_count = sum(1 for w in weak_words if w in content)

    # Factor 2: Evidence quality (numbers, percentages, data points)
    number_patterns = [
        r'\d+(?:\.\d+)?%',  # Percentages
        r'\d+(?:\.\d+)?(?:亿|万|元|港元|美元)',  # Amounts
        r'(?:PE|PB|ROE|RSI|MACD)[：:]\s*\d+',  # Indicators
    ]
    evidence_count = 0
    for pattern in number_patterns:
        evidence_count += len(re.findall(pattern, content))

    # Factor 3: Certainty expressions
    certainty_high = ["建议", "推荐", "应当", "必须", "需要"]
    certainty_low = ["考虑", "观望", "等待", "如果"]

    high_certainty_count = sum(1 for w in certainty_high if w in content)
    low_certainty_count = sum(1 for w in certainty_low if w in content)

    # Factor 4: Risk acknowledgment balance
    risk_words = ["风险", "警惕", "注意", "止损"]
    risk_count = sum(1 for w in risk_words if w in content)

    # Calculate confidence adjustment
    adjustment = 0.0

    # Language strength contribution (max ±0.15)
    if strong_count > weak_count:
        adjustment += min(0.15, (strong_count - weak_count) * 0.05)
    elif weak_count > strong_count:
        adjustment -= min(0.15, (weak_count - strong_count) * 0.05)

    # Evidence quality contribution (max +0.15)
    if evidence_count >= 5:
        adjustment += 0.15
    elif evidence_count >= 3:
        adjustment += 0.10
    elif evidence_count >= 1:
        adjustment += 0.05

    # Certainty expression contribution (max ±0.10)
    if high_certainty_count > low_certainty_count:
        adjustment += min(0.10, (high_certainty_count - low_certainty_count) * 0.03)
    elif low_certainty_count > high_certainty_count:
        adjustment -= min(0.10, (low_certainty_count - high_certainty_count) * 0.03)

    # Risk acknowledgment reduces confidence slightly (max -0.10)
    if risk_count > 3:
        adjustment -= 0.10
    elif risk_count > 1:
        adjustment -= 0.05

    # Calculate final confidence
    final_confidence = base_confidence + adjustment

    # Clamp to reasonable range
    return max(0.3, min(0.9, final_confidence))


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

**置信度**：[XX%，范围30%-95%]

**执行摘要**：[2-3句话说明入场策略、仓位大小、关键风险位和时间期限]

**投资逻辑**：[基于分析师辩论的详细论证]

---

**风险分析师辩论历史：**
{history}

---

**重要提示**：以评级行开头。不要在评级前添加任何开场白。

示例输出：
**评级**：持有
**置信度**：55%
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

        # Extract risk factors and calculate sentiment score
        risk_factors = _extract_risk_factors(history)
        sentiment_score = _calculate_sentiment_score(
            signal=signal,
            confidence=confidence,
            risk_factors=risk_factors,
            debate_context=history,
        )
        score_label = _get_score_label(sentiment_score)

        logger.info(f"Sentiment score: {sentiment_score} ({score_label}) for {ticker}")

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

        # Add score information to the decision output
        # Determine risk level summary
        risk_summary = []
        if risk_factors.get("high_severity_count", 0) > 0:
            risk_summary.append(f"高风险×{risk_factors['high_severity_count']}")
        if risk_factors.get("medium_severity_count", 0) > 0:
            risk_summary.append(f"中风险×{risk_factors['medium_severity_count']}")
        if risk_factors.get("cashflow_issue", False):
            risk_summary.append("现金流风险")
        if risk_factors.get("inventory_risk", False):
            risk_summary.append("库存风险")
        if risk_factors.get("debt_risk", False):
            risk_summary.append("债务风险")
        if risk_factors.get("governance_issue", False):
            risk_summary.append("治理风险")

        risk_text = "、".join(risk_summary) if risk_summary else "无明显风险"

        score_section = f"""

---

## 综合评分

| 指标 | 数值 |
|------|------|
| **情绪评分** | {sentiment_score}/100 |
| **评分解读** | {score_label} |
| **信号类型** | {signal.upper()} |
| **置信度** | {confidence:.0%} |
| **风险因素** | {risk_text} |

**评分维度**：
- 信号基准分（40%权重）：基于评级类型确定初始分数
- 置信度调整（20%权重）：高置信度强化信号方向
- 风险惩罚（25%权重）：根据风险类型和严重程度扣分
- 辩论情绪（15%权重）：分析辩论内容的多空倾向

**评分说明**：
- 80-100分：强烈看好，建议积极配置
- 60-79分：偏多，可考虑适度配置
- 40-59分：中性，建议观望或轻仓
- 20-39分：偏空，建议减仓或回避
- 0-19分：强烈看空，建议清仓
"""

        # Append score section to the decision
        final_decision = cleaned_content + score_section

        new_risk_debate_state = {
            "judge_decision": final_decision,  # Include score section in judge_decision
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
            "final_trade_decision": final_decision,
            "sentiment_score": sentiment_score,
            "signal": signal,
            "confidence": confidence,
        }

    return portfolio_manager_node
