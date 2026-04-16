import datetime
import logging
import re
import time
from pathlib import Path
from typing import Optional

from tradingagents.llm_clients.factory import create_llm_client

logger = logging.getLogger(__name__)

# Translation retry configuration
_TRANSLATION_MAX_RETRIES = 3
_TRANSLATION_RETRY_DELAY = 5.0  # seconds
_TRANSLATION_CHUNK_SIZE = 15000  # characters per chunk for translation (larger chunks for efficiency)


def _clean_pseudo_tool_calls(text: str) -> str:
    """Remove pseudo tool call patterns and thinking blocks that LLMs sometimes output.

    Cleans:
    - Pseudo tool calls like "get_price_data(...)"
    - Thinking blocks (content between thinking tags)
    """
    if not text:
        return text

    # Pattern 1: Pseudo tool call blocks like "<tool_call>get_price_data("...")<tool_call>get_financial_data("...")"
    pattern1 = r'<tool_call>\w+\([^)]*\)(?:<tool_call>\w+\([^)]*\))*'
    text = re.sub(pattern1, '', text)

    # Pattern 2: Single pseudo tool calls like "<tool_call>get_price_data("ticker")"
    pattern2 = r'<tool_call>\w+\([^)]*\)'
    text = re.sub(pattern2, '', text)

    # Pattern 3: Trailing tool call remnants
    pattern3 = r'\n\s*<tool_call>\w+\([^)]*\)\s*\n'
    text = re.sub(pattern3, '\n', text)

    # Pattern 4: Tool calls followed by content without proper spacing
    pattern4 = r'<tool_call>\w+\([^)]*\)\s*'
    text = re.sub(pattern4, '', text)

    # Pattern 5: Remove thinking blocks (used by DeepSeek, GLM and other reasoning models)
    # Match content between thinking open and close tags (generic pattern for any "thinking" variant)
    text = re.sub(r'<(?:thinking|think|thought|reasoning)[^>]*>[\s\S]*?</(?:thinking|think|thought|reasoning)[^>]*>', '', text, flags=re.IGNORECASE)
    # Handle unclosed thinking tags - remove from open tag to end
    text = re.sub(r'<(?:thinking|think|thought|reasoning)[^>]*>[\s\S]*$', '', text, flags=re.IGNORECASE)
    # Handle orphaned close tags (left over after translation or partial processing)
    text = re.sub(r'</(?:thinking|think|thought|reasoning)[^>]*>', '', text, flags=re.IGNORECASE)

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

    # Clean up multiple consecutive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _extract_text_from_llm_response(response) -> str:
    """Best-effort extraction of text from varied LangChain/provider responses."""
    if response is None:
        return ""

    def _from_value(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, str):
                    text = item.strip()
                elif isinstance(item, dict):
                    block_type = str(item.get("type") or "").lower()
                    if block_type and block_type not in {"text", "output_text"}:
                        text = ""
                    else:
                        text = str(
                            item.get("text")
                            or item.get("output_text")
                            or item.get("content")
                            or item.get("reasoning")  # Some models (e.g., ollama reasoning models) return reasoning field
                            or ""
                        ).strip()
                else:
                    text = str(getattr(item, "text", "") or getattr(item, "content", "")).strip()
                if text:
                    parts.append(text)
            return "\n".join(parts).strip()
        if isinstance(value, dict):
            for key in ("text", "output_text", "content", "reasoning"):
                text = _from_value(value.get(key))
                if text:
                    return text
            return ""
        if hasattr(value, "text") or hasattr(value, "content") or hasattr(value, "output_text"):
            return str(
                getattr(value, "text", None)
                or getattr(value, "content", None)
                or getattr(value, "output_text", None)
                or ""
            ).strip()
        return ""

    for candidate in (
        getattr(response, "content", None),
        getattr(response, "text", None),
        getattr(response, "output_text", None),
        getattr(response, "additional_kwargs", None),
        response,
    ):
        text = _from_value(candidate)
        if text:
            return text
    return ""


def build_complete_report_markdown(final_state, ticker: str) -> str:
    """Build a consolidated Markdown report from the final graph state."""
    sections = []

    analyst_parts = []
    if final_state.get("market_report"):
        analyst_parts.append(("Market Analyst", final_state["market_report"]))
    if final_state.get("sentiment_report"):
        analyst_parts.append(("Social Analyst", final_state["sentiment_report"]))
    if final_state.get("news_report"):
        analyst_parts.append(("News Analyst", final_state["news_report"]))
    if final_state.get("fundamentals_report"):
        analyst_parts.append(("Fundamentals Analyst", final_state["fundamentals_report"]))
    if analyst_parts:
        content = "\n\n".join(f"### {name}\n{text}" for name, text in analyst_parts)
        sections.append(f"## I. Analyst Team Reports\n\n{content}")

    if final_state.get("investment_debate_state"):
        debate = final_state["investment_debate_state"]
        research_parts = []
        if debate.get("bull_history"):
            research_parts.append(("Bull Researcher", debate["bull_history"]))
        if debate.get("bear_history"):
            research_parts.append(("Bear Researcher", debate["bear_history"]))
        if debate.get("judge_decision"):
            research_parts.append(("Research Manager", debate["judge_decision"]))
        if research_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in research_parts)
            sections.append(f"## II. Research Team Decision\n\n{content}")

    if final_state.get("trader_investment_plan"):
        # Clean pseudo tool calls from trader output
        trader_plan = _clean_pseudo_tool_calls(final_state['trader_investment_plan'])
        sections.append(f"## III. Trading Team Plan\n\n### Trader\n{trader_plan}")

    if final_state.get("risk_debate_state"):
        risk = final_state["risk_debate_state"]
        risk_parts = []
        if risk.get("aggressive_history"):
            # Clean pseudo tool calls from risk analyst outputs
            aggressive_text = _clean_pseudo_tool_calls(risk["aggressive_history"])
            risk_parts.append(("Aggressive Analyst", aggressive_text))
        if risk.get("conservative_history"):
            conservative_text = _clean_pseudo_tool_calls(risk["conservative_history"])
            risk_parts.append(("Conservative Analyst", conservative_text))
        if risk.get("neutral_history"):
            neutral_text = _clean_pseudo_tool_calls(risk["neutral_history"])
            risk_parts.append(("Neutral Analyst", neutral_text))
        if risk_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in risk_parts)
            sections.append(f"## IV. Risk Management Team Decision\n\n{content}")

        if risk.get("judge_decision"):
            judge_decision = _clean_pseudo_tool_calls(risk['judge_decision'])
            sections.append(f"## V. Portfolio Manager Decision\n\n### Portfolio Manager\n{judge_decision}")

    header = f"# Trading Analysis Report: {ticker}\n\nGenerated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + "\n\n".join(sections)


def _split_report_for_translation(report_markdown: str, chunk_size: int = _TRANSLATION_CHUNK_SIZE) -> list[tuple[str, str]]:
    """Split a long report into chunks for translation.

    Returns a list of (section_header, content) tuples.
    Each chunk is designed to be translatable independently.
    """
    import re

    # Split by major sections (## headers)
    section_pattern = r'(^## .+)$'
    lines = report_markdown.split('\n')

    chunks = []
    current_header = ""
    current_content = []

    for line in lines:
        # Check if this is a major section header
        if re.match(section_pattern, line, re.MULTILINE):
            # Save current chunk if it has content
            if current_content or current_header:
                chunk_text = '\n'.join(current_content)
                if chunk_text.strip():
                    chunks.append((current_header, chunk_text))
            current_header = line
            current_content = []
        else:
            current_content.append(line)

            # Check if current chunk is getting too large (use larger threshold)
            if len('\n'.join(current_content)) > chunk_size and len(current_content) > 100:
                # Try to find a good breaking point (empty line or paragraph end)
                break_idx = -1
                for i in range(len(current_content) - 1, max(0, len(current_content) - 30), -1):
                    if current_content[i].strip() == "":
                        break_idx = i
                        break

                if break_idx > 0:
                    chunk_text = '\n'.join(current_content[:break_idx])
                    chunks.append((current_header, chunk_text))
                    current_content = current_content[break_idx + 1:]
                else:
                    # No good breaking point, just split at current size
                    chunk_text = '\n'.join(current_content)
                    chunks.append((current_header, chunk_text))
                    current_content = []

    # Save final chunk
    if current_content:
        chunk_text = '\n'.join(current_content)
        chunks.append((current_header, chunk_text))

    return chunks


def translate_report_to_chinese(report_markdown: str, selections: dict, fallback_selections: dict = None) -> Optional[str]:
    """Translate the consolidated Markdown report into Simplified Chinese.

    Args:
        report_markdown: The markdown report to translate
        selections: Dict with llm_provider, deep_thinker/shallow_thinker, backend_url
        fallback_selections: Optional fallback provider config if primary fails

    Returns:
        Translated markdown string, or None if translation fails

    Raises:
        ValueError: If translation response is empty after all retries/fallbacks
    """
    provider = selections.get("llm_provider")
    model = selections.get("deep_thinker") or selections.get("shallow_thinker")
    if not provider or not model:
        return None

    # Check if report is too large and needs chunking
    if len(report_markdown) > _TRANSLATION_CHUNK_SIZE * 2:
        logger.info(f"Report is large ({len(report_markdown)} chars), splitting into chunks for translation")
        return _translate_large_report(report_markdown, selections, fallback_selections)

    return _translate_single_chunk(report_markdown, selections, fallback_selections)


def _translate_single_chunk(report_markdown: str, selections: dict, fallback_selections: dict = None, prompt: str = None) -> Optional[str]:
    """Translate a single chunk of markdown to Chinese.

    Args:
        report_markdown: The markdown content to translate (used if prompt is None)
        selections: Provider configuration
        fallback_selections: Fallback provider configuration
        prompt: Optional custom prompt (if None, uses default translation prompt)
    """
    provider = selections.get("llm_provider")
    model = selections.get("deep_thinker") or selections.get("shallow_thinker")

    if prompt is None:
        prompt = (
            "Translate the following financial analysis report into Simplified Chinese.\n"
            "Preserve the Markdown structure, headings, tables, lists, ticker symbols, dates, numbers, "
            "percentages, currencies, and inline code formatting exactly where possible.\n"
            "Do not omit any content. Translate ALL sections completely, including:\n"
            "- All analyst reports and debates\n"
            "- Trading Team Plan section\n"
            "- Risk Management Team Decision section\n"
            "- Portfolio Manager Decision section (including 'Final Determination' subsection)\n"
            "- All headings like '### Final Determination', '### Executive Summary', etc.\n"
            "Keep machine-relevant labels unchanged when they appear, especially "
            "`FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`, `Buy`, `Sell`, `Hold`, `Overweight`, and `Underweight`.\n"
            "Translate section headers consistently:\n"
            "- 'Final Determination' → '最终决定'\n"
            "- 'Executive Summary' → '执行摘要'\n"
            "- 'Investment Thesis' → '投资逻辑'\n"
            "- 'Action Plan' → '行动计划'\n"
            "Return only the translated Markdown.\n\n"
            f"{report_markdown}"
        )

    # Collect all providers to try (primary + fallback)
    provider_configs = [selections]
    if fallback_selections:
        provider_configs.append(fallback_selections)

    last_error = None
    attempted_providers = []

    for config in provider_configs:
        cfg_provider = config.get("llm_provider")
        cfg_model = config.get("deep_thinker") or config.get("shallow_thinker")
        cfg_backend_url = config.get("backend_url")

        if not cfg_provider or not cfg_model:
            continue

        # Check if this is a local provider (ollama) and if it's likely unavailable
        if cfg_provider.lower() == "ollama":
            cfg_backend_url = cfg_backend_url or "http://localhost:11434/v1"
            if "localhost" in cfg_backend_url or "127.0.0.1" in cfg_backend_url:
                # Try a quick connectivity check for local ollama
                try:
                    import urllib.request
                    import urllib.error
                    ollama_base = cfg_backend_url.replace("/v1", "")
                    req = urllib.request.Request(f"{ollama_base}/api/tags", method="GET")
                    req.add_header("Accept", "application/json")
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        if resp.status != 200:
                            raise ConnectionError(f"Ollama returned status {resp.status}")
                except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, Exception) as e:
                    logger.warning(
                        f"Skipping fallback to ollama - local service not available at {cfg_backend_url}: {e}"
                    )
                    attempted_providers.append(f"{cfg_provider}/{cfg_model} (skipped - unavailable)")
                    continue

        # Build client with translation-specific settings
        client_kwargs = {}
        if cfg_provider.lower() == "ollama":
            # Ollama needs larger num_predict for long translations
            client_kwargs["num_predict"] = 8192  # Allow longer output for translation
            client_kwargs["num_ctx"] = 32768  # Larger context window for long reports

        # Retry loop with exponential backoff
        for attempt in range(_TRANSLATION_MAX_RETRIES + 1):
            try:
                client = create_llm_client(cfg_provider, cfg_model, cfg_backend_url, **client_kwargs)
                llm = client.get_llm()
                response = llm.invoke(prompt)
                translated_text = _extract_text_from_llm_response(response)
                if translated_text:
                    # Clean any thinking tags that might have been introduced during translation
                    translated_text = _clean_pseudo_tool_calls(translated_text)
                    logger.info(f"Translation successful using {cfg_provider}/{cfg_model}")
                    return translated_text
                raise ValueError(f"Translation response was empty for provider='{cfg_provider}' model='{cfg_model}'.")
            except Exception as exc:
                last_error = exc
                error_str = str(exc).lower()

                # Check if it's a retryable error (5xx, timeout, rate limit)
                is_retryable = (
                    "503" in error_str
                    or "502" in error_str
                    or "504" in error_str
                    or "500" in error_str
                    or "timeout" in error_str
                    or "rate limit" in error_str
                    or "429" in error_str
                )

                if is_retryable and attempt < _TRANSLATION_MAX_RETRIES:
                    delay = _TRANSLATION_RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Translation failed (attempt {attempt + 1}/{_TRANSLATION_MAX_RETRIES + 1}), "
                        f"retrying in {delay:.0f}s: {exc}"
                    )
                    time.sleep(delay)
                elif is_retryable and attempt == _TRANSLATION_MAX_RETRIES:
                    # Exhausted retries for this provider, try fallback
                    logger.error(
                        f"Translation exhausted retries for {cfg_provider}/{cfg_model}: {exc}"
                    )
                    attempted_providers.append(f"{cfg_provider}/{cfg_model} (failed: {type(exc).__name__})")
                    break
                else:
                    # Non-retryable error, raise immediately
                    attempted_providers.append(f"{cfg_provider}/{cfg_model} (failed: {type(exc).__name__})")
                    raise

    # All providers and retries exhausted
    if last_error:
        # Include information about all attempted providers in the error
        providers_tried = ", ".join(attempted_providers) if attempted_providers else "none"
        raise ValueError(f"Translation failed after trying providers: {providers_tried}. Last error: {last_error}")
    return None


def _translate_large_report(report_markdown: str, selections: dict, fallback_selections: dict = None) -> Optional[str]:
    """Translate a large report by splitting it into chunks.

    This function handles reports that are too large for a single LLM call
    by splitting them into manageable chunks, translating each, and reassembling.
    """
    chunks = _split_report_for_translation(report_markdown)
    total_chunks = len(chunks)
    logger.info(f"Split report into {total_chunks} chunks for translation")

    translated_chunks = []
    for i, (header, content) in enumerate(chunks):
        chunk_num = i + 1
        logger.info(f"Translating chunk {chunk_num}/{total_chunks} ({len(content)} chars)")

        # Build a focused prompt for this chunk
        chunk_prompt = (
            f"Translate the following section of a financial analysis report into Simplified Chinese.\n"
            f"This is part {chunk_num} of {total_chunks}.\n"
            f"Preserve the Markdown structure, headings, tables, lists, ticker symbols, dates, numbers, "
            f"percentages, currencies, and inline code formatting exactly where possible.\n"
            f"Translate section headers consistently:\n"
            f"- 'Market Analyst' → '市场分析师'\n"
            f"- 'Social Analyst' → '社交分析师'\n"
            f"- 'News Analyst' → '新闻分析师'\n"
            f"- 'Fundamentals Analyst' → '基本面分析师'\n"
            f"- 'Bull Researcher' → '多头研究员'\n"
            f"- 'Bear Researcher' → '空头研究员'\n"
            f"- 'Research Manager' → '研究经理'\n"
            f"- 'Trader' → '交易员'\n"
            f"- 'Aggressive Analyst' → '激进分析师'\n"
            f"- 'Conservative Analyst' → '保守分析师'\n"
            f"- 'Neutral Analyst' → '中性分析师'\n"
            f"- 'Portfolio Manager' → '投资组合经理'\n"
            f"- 'Final Determination' → '最终决定'\n"
            f"- 'Executive Summary' → '执行摘要'\n"
            f"- 'Investment Thesis' → '投资逻辑'\n"
            f"- 'Action Plan' → '行动计划'\n"
            f"Return only the translated Markdown.\n\n"
            f"{header}\n\n{content}"
        )

        # Translate this chunk
        translated = _translate_single_chunk(
            chunk_prompt,
            selections,
            fallback_selections,
        )

        if translated:
            translated_chunks.append(translated)
        else:
            # If translation failed, keep original
            logger.warning(f"Chunk {chunk_num}/{total_chunks} translation failed, keeping original")
            translated_chunks.append(f"{header}\n\n{content}")

        # Small delay between chunks to avoid rate limits
        if i < total_chunks - 1:
            time.sleep(0.5)

    # Reassemble the translated report
    return "\n\n".join(translated_chunks)


def save_report_to_disk(final_state, ticker: str, save_path: Path, translated_report: Optional[str] = None):
    """Save complete analysis report to disk with organized subfolders."""
    save_path.mkdir(parents=True, exist_ok=True)

    analysts_dir = save_path / "1_analysts"
    if final_state.get("market_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "market.md").write_text(final_state["market_report"], encoding="utf-8")
    if final_state.get("sentiment_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "sentiment.md").write_text(final_state["sentiment_report"], encoding="utf-8")
    if final_state.get("news_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "news.md").write_text(final_state["news_report"], encoding="utf-8")
    if final_state.get("fundamentals_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "fundamentals.md").write_text(final_state["fundamentals_report"], encoding="utf-8")

    if final_state.get("investment_debate_state"):
        research_dir = save_path / "2_research"
        debate = final_state["investment_debate_state"]
        if debate.get("bull_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bull.md").write_text(debate["bull_history"], encoding="utf-8")
        if debate.get("bear_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bear.md").write_text(debate["bear_history"], encoding="utf-8")
        if debate.get("judge_decision"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "manager.md").write_text(debate["judge_decision"], encoding="utf-8")

    if final_state.get("trader_investment_plan"):
        trading_dir = save_path / "3_trading"
        trading_dir.mkdir(exist_ok=True)
        (trading_dir / "trader.md").write_text(final_state["trader_investment_plan"], encoding="utf-8")

    if final_state.get("risk_debate_state"):
        risk_dir = save_path / "4_risk"
        risk = final_state["risk_debate_state"]
        if risk.get("aggressive_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "aggressive.md").write_text(risk["aggressive_history"], encoding="utf-8")
        if risk.get("conservative_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "conservative.md").write_text(risk["conservative_history"], encoding="utf-8")
        if risk.get("neutral_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "neutral.md").write_text(risk["neutral_history"], encoding="utf-8")
        if risk.get("judge_decision"):
            portfolio_dir = save_path / "5_portfolio"
            portfolio_dir.mkdir(exist_ok=True)
            (portfolio_dir / "decision.md").write_text(risk["judge_decision"], encoding="utf-8")

    report_file = save_path / "complete_report.md"
    report_file.write_text(build_complete_report_markdown(final_state, ticker), encoding="utf-8")
    if translated_report:
        (save_path / "complete_report_zh.md").write_text(translated_report, encoding="utf-8")
    return report_file


def translate_saved_report_to_chinese(
    report_dir: Path,
    selections: dict,
    overwrite: bool = False,
    fallback_selections: dict = None,
) -> Path:
    """Generate `complete_report_zh.md` for an existing saved report directory.

    Args:
        report_dir: Directory containing the report
        selections: Primary LLM provider config
        overwrite: Overwrite existing translation
        fallback_selections: Optional fallback provider config if primary fails
    """
    report_dir = Path(report_dir)
    source_path = report_dir / "complete_report.md"
    target_path = report_dir / "complete_report_zh.md"

    if not source_path.exists():
        raise FileNotFoundError(f"Source report not found: {source_path}")

    if target_path.exists() and not overwrite:
        return target_path

    report_markdown = source_path.read_text(encoding="utf-8")
    translated_report = translate_report_to_chinese(report_markdown, selections, fallback_selections)
    target_path.write_text(translated_report, encoding="utf-8")
    return target_path
