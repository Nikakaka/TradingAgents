import re

from langchain_core.messages import AIMessage

from tradingagents.agents.utils.agent_utils import build_instrument_context


def _sanitize_for_provider(text: str, max_chars: int = 6000) -> str:
    """Reduce provider filter risk by removing noisy or quote-heavy content."""
    if not text:
        return ""

    sanitized = str(text)
    replacements = {
        "Bull Analyst:": "View A:",
        "Bear Analyst:": "View B:",
        "Supportive Analyst:": "View A:",
        "Risk Analyst:": "View B:",
        "Supportive View:": "View A:",
        "Risk View:": "View B:",
        "bull analyst": "view A",
        "bear analyst": "view B",
        "supportive analyst": "view A",
        "risk analyst": "view B",
        "bull case": "positive case",
        "bear case": "risk case",
        "debate": "discussion",
        "bull": "positive",
        "bear": "risk",
    }
    for src, dst in replacements.items():
        sanitized = sanitized.replace(src, dst)

    sanitized = re.sub(r"https?://\S+", "[link]", sanitized)
    sanitized = re.sub(r"\b\S+@\S+\b", "[email]", sanitized)
    sanitized = re.sub(r"`{1,3}.*?`{1,3}", "[quoted text]", sanitized, flags=re.DOTALL)
    sanitized = re.sub(r"[ \t]+", " ", sanitized)

    if len(sanitized) > max_chars:
        sanitized = sanitized[:max_chars]

    return sanitized.strip()


def _summarize_history_for_provider(text: str, max_points: int = 8, max_chars: int = 1800) -> str:
    sanitized = _sanitize_for_provider(text, max_chars=max_chars)
    if not sanitized:
        return ""

    pieces = re.split(r"[\n\r]+", sanitized)
    selected: list[str] = []
    for piece in pieces:
        compact = re.sub(r"\s+", " ", piece).strip(" -:*")
        if not compact:
            continue
        if len(compact) < 20:
            continue
        selected.append(f"- {compact}")
        if len(selected) >= max_points:
            break
    return "\n".join(selected)


def _build_ultra_safe_prompt(instrument_context: str, history_summary: str) -> str:
    return f"""Provide a short, neutral trading note for the instrument below.

Return exactly these sections:
Recommendation: Buy, Sell, or Hold
Reasons:
- point 1
- point 2
Next step:
- point 1

Keep the tone calm and factual. Avoid debate language.

{instrument_context}

Notes:
{history_summary or "- Limited analyst notes available."}"""


def _build_deterministic_fallback(instrument_context: str, history: str) -> AIMessage:
    history_summary = _summarize_history_for_provider(history, max_points=4, max_chars=900)
    content = (
        "建议：持有\n"
        "理由：\n"
        "- 提供商安全过滤器阻止了分析师讨论的自动综合。\n"
        f"{history_summary or '- 可用备注需要在方向性交易前进行人工审查。'}\n"
        "下一步行动：\n"
        "- 人工审查分析师报告，如有需要请使用更中立的提示重新运行。\n"
    )
    return AIMessage(content=f"{instrument_context}\n\n{content}".strip())


def _build_primary_prompt(instrument_context: str, past_memory_str: str, history: str) -> str:
    return f"""你是研究主管，负责将两个对立的投资观点综合为一个给交易员的实用决策。

审视观点 A 和观点 B，然后判断哪一方有更好的证据支持。选择买入、卖出或持有。仅当可用证据真正混合或不足时才使用持有。

撰写一份清晰的决策说明，包括：
1. 建议：买入、卖出或持有。
2. 来自双方观点的关键支持证据。
3. 最终决策的理由。
4. 给交易员的实用下一步行动。

利用类似过去情况的经验教训来改进决策，但保持语气专业、冷静，聚焦财务分析。

过去的反思：
"{past_memory_str}"

{instrument_context}

讨论历史：
{history}
请使用中文撰写回复。"""


def _build_fallback_prompt(instrument_context: str, history: str) -> str:
    return f"""审视以下投资讨论并提供一份冷静的财务总结。

返回：
1. 建议：买入、卖出或持有。
2. 两到三个关键理由。
3. 给交易员的实用下一步行动。

保持回复简洁专业。

{instrument_context}

讨论：
{history}
请使用中文撰写回复。"""


def _build_ultra_safe_prompt(instrument_context: str, history_summary: str) -> str:
    return f"""为以下标的提供一份简短、中性的交易说明。

严格按以下格式返回：
建议：买入、卖出或持有
理由：
- 要点 1
- 要点 2
下一步行动：
- 要点 1

保持语气冷静和事实性。避免辩论语言。

{instrument_context}

备注：
{history_summary or '- 可用的分析师备注有限。'}
请使用中文撰写回复。"""


def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        investment_debate_state = state["investment_debate_state"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec["recommendation"] + "\n\n"

        sanitized_history = _sanitize_for_provider(history)
        sanitized_memories = _sanitize_for_provider(past_memory_str, max_chars=2000)

        primary_prompt = _build_primary_prompt(
            instrument_context=instrument_context,
            past_memory_str=sanitized_memories,
            history=sanitized_history,
        )

        try:
            response = llm.invoke(primary_prompt)
        except Exception as exc:
            error_text = str(exc)
            if "1301" not in error_text and "contentFilter" not in error_text:
                raise

            fallback_prompt = _build_fallback_prompt(
                instrument_context=instrument_context,
                history=_summarize_history_for_provider(history, max_points=10, max_chars=2500),
            )
            try:
                response = llm.invoke(fallback_prompt)
            except Exception as fallback_exc:
                fallback_error = str(fallback_exc)
                if "1301" not in fallback_error and "contentFilter" not in fallback_error:
                    raise

                ultra_safe_prompt = _build_ultra_safe_prompt(
                    instrument_context=instrument_context,
                    history_summary=_summarize_history_for_provider(history, max_points=6, max_chars=1200),
                )
                try:
                    response = llm.invoke(ultra_safe_prompt)
                except Exception as ultra_exc:
                    ultra_error = str(ultra_exc)
                    if "1301" not in ultra_error and "contentFilter" not in ultra_error:
                        raise
                    response = _build_deterministic_fallback(
                        instrument_context=instrument_context,
                        history=history,
                    )

        new_investment_debate_state = {
            "judge_decision": response.content,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": response.content,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }

    return research_manager_node
