import html
import json
import os
import re
import threading
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from cli.stats_handler import StatsCallbackHandler
from cli.utils import get_installed_ollama_models
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.market_utils import load_symbol_index, resolve_ticker_input, search_symbol_candidates
from tradingagents.reporting import (
    build_complete_report_markdown,
    save_report_to_disk,
    translate_report_to_chinese,
    translate_saved_report_to_chinese,
)

APP_DIR = Path(__file__).resolve().parent
ASSET_DIR = APP_DIR / "web_assets"
REPORTS_DIR = Path.cwd() / "reports"
SYMBOL_INDEX = None
API_KEY_ENV_LOCK = threading.Lock()

ANALYST_OPTIONS = [
    {"id": "market", "label": "Market Analyst"},
    {"id": "social", "label": "Social Analyst"},
    {"id": "news", "label": "News Analyst"},
    {"id": "fundamentals", "label": "Fundamentals Analyst"},
]

PROVIDER_OPTIONS = [
    {
        "id": "openai",
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key_label": "OpenAI API Key",
        "api_key_placeholder": "输入 OPENAI_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的 OpenAI Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
    },
    {
        "id": "google",
        "label": "Google",
        "base_url": "https://generativelanguage.googleapis.com/v1",
        "api_key_label": "Google API Key",
        "api_key_placeholder": "输入 GOOGLE_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的 Google Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
    },
    {
        "id": "anthropic",
        "label": "Anthropic",
        "base_url": "https://api.anthropic.com/",
        "api_key_label": "Anthropic API Key",
        "api_key_placeholder": "输入 ANTHROPIC_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的 Anthropic Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
    },
    {
        "id": "xai",
        "label": "xAI",
        "base_url": "https://api.x.ai/v1",
        "api_key_label": "xAI API Key",
        "api_key_placeholder": "输入 XAI_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的 xAI Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
    },
    {
        "id": "zhipu",
        "label": "Zhipu GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_label": "智谱 API Key",
        "api_key_placeholder": "输入 ZHIPUAI_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的智谱 Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
    },
    {
        "id": "openrouter",
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_label": "OpenRouter API Key",
        "api_key_placeholder": "输入 OPENROUTER_API_KEY",
        "api_key_helper": "可直接覆盖当前分析任务使用的 OpenRouter Key；留空时沿用本机已有环境变量。",
        "requires_api_key": True,
    },
    {
        "id": "ollama",
        "label": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "api_key_label": "Ollama 无需 API Key",
        "api_key_placeholder": "",
        "api_key_helper": "本地 Ollama 连接默认不需要 API Key。",
        "requires_api_key": False,
    },
]

MODEL_OPTIONS = {
    "openai": {
        "quick": ["gpt-5-mini", "gpt-5-nano", "gpt-5.4", "gpt-4.1"],
        "deep": ["gpt-5.4", "gpt-5.2", "gpt-5-mini", "gpt-5.4-pro"],
    },
    "anthropic": {
        "quick": ["claude-sonnet-4-6", "claude-haiku-4-5", "claude-sonnet-4-5"],
        "deep": ["claude-opus-4-6", "claude-opus-4-5", "claude-sonnet-4-6", "claude-sonnet-4-5"],
    },
    "google": {
        "quick": ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-3.1-flash-lite-preview", "gemini-2.5-flash-lite"],
        "deep": ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash"],
    },
    "xai": {
        "quick": ["grok-4-1-fast-non-reasoning", "grok-4-fast-non-reasoning", "grok-4-1-fast-reasoning"],
        "deep": ["grok-4-0709", "grok-4-1-fast-reasoning", "grok-4-fast-reasoning", "grok-4-1-fast-non-reasoning"],
    },
    "zhipu": {
        "quick": ["GLM-4.7", "GLM-4.5-Air"],
        "deep": ["GLM-4.7", "GLM-4.5", "GLM-4.5-Air"],
    },
    "openrouter": {
        "quick": ["nvidia/nemotron-3-nano-30b-a3b:free", "z-ai/glm-4.5-air:free"],
        "deep": ["z-ai/glm-4.5-air:free", "nvidia/nemotron-3-nano-30b-a3b:free"],
    },
}

PROVIDER_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "xai": "XAI_API_KEY",
    "zhipu": "ZHIPUAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _format_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def _ollama_model_options() -> Dict[str, List[str]]:
    installed = get_installed_ollama_models()
    models = installed or ["glm-4.7-flash:latest", "gpt-oss:latest", "qwen3:latest"]
    return {"quick": models, "deep": models}


def _pick_preferred_model(models: List[str], preferred_names: List[str]) -> str:
    if not models:
        return ""

    lowered = [(model, model.lower()) for model in models]
    for preferred in preferred_names:
        preferred_lower = preferred.lower()
        for model, model_lower in lowered:
            if model_lower == preferred_lower:
                return model
        for model, model_lower in lowered:
            if preferred_lower in model_lower:
                return model
    return models[0]


def _build_translation_selections(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "llm_provider": (payload.get("llm_provider") or DEFAULT_CONFIG["llm_provider"]).lower(),
        "deep_thinker": payload.get("deep_model") or DEFAULT_CONFIG["deep_think_llm"],
        "shallow_thinker": payload.get("quick_model") or DEFAULT_CONFIG["quick_think_llm"],
        "backend_url": payload.get("backend_url") or DEFAULT_CONFIG["backend_url"],
        "api_key": (payload.get("api_key") or "").strip(),
    }


def _provider_api_key_env(provider: str) -> str | None:
    return PROVIDER_API_KEY_ENV.get((provider or "").lower())


@contextmanager
def _temporary_provider_api_key(provider: str, api_key: str):
    env_name = _provider_api_key_env(provider)
    api_key = (api_key or "").strip()
    if not env_name or not api_key:
        yield
        return

    with API_KEY_ENV_LOCK:
        previous = os.environ.get(env_name)
        os.environ[env_name] = api_key
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = previous


def _get_symbol_index() -> list[dict]:
    global SYMBOL_INDEX
    if SYMBOL_INDEX is None:
        try:
            SYMBOL_INDEX = load_symbol_index()
        except Exception:
            SYMBOL_INDEX = []
    return SYMBOL_INDEX


def _get_display_name(ticker: str) -> str:
    canonical = ticker.strip().upper()
    for entry in _get_symbol_index():
        if entry.get("canonical_ticker", "").upper() == canonical:
            name = str(entry.get("name", "")).strip()
            if name:
                return name
    return canonical


def _serialize_symbol_candidates(user_input: str) -> List[Dict[str, str]]:
    candidates = search_symbol_candidates(user_input, symbol_index=_get_symbol_index(), limit=8)
    market_labels = {
        "cn_a": "A股",
        "hk": "港股",
        "global": "海外",
    }
    return [
        {
            "canonical_ticker": item.get("canonical_ticker", ""),
            "name": item.get("name", "") or item.get("canonical_ticker", ""),
            "market": item.get("market", ""),
            "market_label": market_labels.get(item.get("market", ""), item.get("market", "")),
        }
        for item in candidates
    ]


def get_ui_options() -> Dict[str, Any]:
    models = dict(MODEL_OPTIONS)
    models["ollama"] = _ollama_model_options()
    ollama_defaults = models["ollama"]
    default_provider = "ollama"
    default_quick = ollama_defaults["quick"][0] if ollama_defaults["quick"] else DEFAULT_CONFIG["quick_think_llm"]
    default_deep = _pick_preferred_model(
        ollama_defaults["deep"],
        ["glm-4.7", "glm-4.7-flash", "glm-4.7:latest", "glm-4.7-flash:latest"],
    ) or default_quick
    model_defaults = {}
    for provider, provider_models in models.items():
        provider_quick = (provider_models.get("quick") or [default_quick])[0]
        provider_deep = (provider_models.get("deep") or [default_deep])[0]
        if provider == "ollama":
            provider_deep = _pick_preferred_model(
                provider_models.get("deep") or [],
                ["glm-4.7-flash:latest", "glm-4.7-flash", "glm-4.7:latest", "glm-4.7"],
            ) or provider_quick
        model_defaults[provider] = {
            "quick": provider_quick,
            "deep": provider_deep,
        }
    return {
        "providers": PROVIDER_OPTIONS,
        "models": models,
        "analysts": ANALYST_OPTIONS,
        "research_depths": [
            {"label": "Shallow", "value": 1},
            {"label": "Medium", "value": 3},
            {"label": "Deep", "value": 5},
        ],
        "defaults": {
            "provider": default_provider,
            "quick_model": default_quick,
            "deep_model": default_deep,
            "model_defaults": model_defaults,
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "research_depth": DEFAULT_CONFIG["max_debate_rounds"],
            "analysts": [item["id"] for item in ANALYST_OPTIONS],
        },
    }


def _text_excerpt(text: str, limit: int = 220) -> str:
    plain = re.sub(r"\s+", " ", text or "").strip()
    if len(plain) <= limit:
        return plain
    return plain[: max(limit - 3, 0)].rstrip() + "..."


def _extract_rating(text: str) -> str:
    match = re.search(r"Rating\*?\*?:\s*([A-Za-z]+)", text or "", flags=re.IGNORECASE)
    if match:
        return match.group(1).capitalize()
    match = re.search(r"\b(Buy|Sell|Hold)\b", text or "", flags=re.IGNORECASE)
    return match.group(1).capitalize() if match else "Unknown"


def _extract_numbered_section(text: str, label: str) -> str:
    if not text:
        return ""
    pattern = rf"{re.escape(label)}\*?\*?:\s*(.+?)(?=\n\d+\.\s+\*\*|\Z)"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_chinese_summary(text: str) -> str:
    if not text:
        return ""
    for label in ("执行摘要", "摘要", "投资逻辑"):
        pattern = rf"{re.escape(label)}[:：]\s*(.+?)(?=\n(?:\d+[\.、]|##|###)|\Z)"
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


# Clean UTF-8 summary helpers used by the report list/detail APIs.
def _preferred_text_excerpt(text: str, limit: int = 220) -> str:
    plain = re.sub(r"\s+", " ", text or "").strip()
    if len(plain) <= limit:
        return plain
    return plain[: max(limit - 3, 0)].rstrip() + "..."


def _preferred_chinese_summary(text: str) -> str:
    if not text:
        return ""
    for label in ("执行摘要", "摘要", "投资逻辑", "投资要点", "核心结论", "结论"):
        pattern = rf"(?:^|\n)(?:#+\s*)?(?:\d+[\.、]?\s*)?{re.escape(label)}\s*[:：]?\s*\n?(?P<body>.*?)(?=\n(?:---|#{1,6}\s+|\d+[\.、]\s+)|\Z)"
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            summary = _extract_bullets_or_sentences(match.group("body"))
            if summary:
                return summary
    return ""


def _markdown_to_plain_text(text: str) -> str:
    if not text:
        return ""
    plain = re.sub(r"```[\s\S]*?```", " ", text)
    plain = re.sub(r"`([^`]+)`", r"\1", plain)
    plain = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", plain)
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
    plain = re.sub(r"^\s{0,3}#{1,6}\s*", "", plain, flags=re.MULTILINE)
    plain = re.sub(r"^\s*[-*+]\s+", "", plain, flags=re.MULTILINE)
    plain = re.sub(r"^\s*\d+\.\s+", "", plain, flags=re.MULTILINE)
    plain = re.sub(r"\*\*([^*]+)\*\*", r"\1", plain)
    plain = re.sub(r"\*([^*]+)\*", r"\1", plain)
    plain = re.sub(r"_([^_]+)_", r"\1", plain)
    plain = re.sub(r"\|", " ", plain)
    plain = re.sub(r"\n{2,}", "\n", plain)
    return re.sub(r"\s+", " ", plain).strip()


def _looks_mojibake(text: str) -> bool:
    if not text:
        return False
    markers = (
        "\u9225",
        "\u951b",
        "\u9286",
        "\u9428",
        "\u93c8",
        "\u7487",
        "\u9352",
        "\u95c3",
        "\u93c3",
    )
    return any(marker in text for marker in markers)


def _extract_bullets_or_sentences(text: str, max_items: int = 3) -> str:
    if not text:
        return ""
    plain_text = _markdown_to_plain_text(text)
    candidates = []
    for line in text.splitlines():
        stripped = line.strip(" -*\t")
        if (
            len(stripped) >= 12
            and not re.match(r"^(?:第?[IVX\d]+[\.、]?\s*)?(?:分析报告|生成时间|日期|股票代码|ticker|symbol)\b", stripped, flags=re.IGNORECASE)
        ):
            candidates.append(stripped)
    if not candidates:
        sentences = re.split(r"(?<=[。.!?])\s+", plain_text)
        candidates = [
            item.strip()
            for item in sentences
            if len(item.strip()) >= 12
            and not re.match(r"^(?:第?[IVX\d]+[\.、]?\s*)?(?:分析报告|生成时间|日期|股票代码|ticker|symbol)\b", item.strip(), flags=re.IGNORECASE)
        ]
    return " ".join(candidates[:max_items]).strip()


def _extract_report_highlights(text: str) -> str:
    if not text:
        return ""
    section_patterns = [
        r"(?:^|\n)(?:#+\s*)?(?:\d+[\.、]?\s*)?执行摘要\s*[:：]?\s*(?P<body>.*?)(?=\n(?:#+\s*)?(?:\d+[\.、]?\s*)?(?:投资要点|投资逻辑|核心结论|结论)|\n\d+\.\s+\*\*|\Z)",
        r"(?:^|\n)(?:#+\s*)?(?:\d+[\.、]?\s*)?投资要点\s*[:：]?\s*(?P<body>.*?)(?=\n(?:#+\s*)?(?:\d+[\.、]?\s*)?(?:执行摘要|投资逻辑|核心结论|结论)|\n\d+\.\s+\*\*|\Z)",
        r"(?:^|\n)(?:#+\s*)?(?:\d+[\.、]?\s*)?投资逻辑\s*[:：]?\s*(?P<body>.*?)(?=\n(?:#+\s*)?(?:\d+[\.、]?\s*)?(?:执行摘要|投资要点|核心结论|结论)|\n\d+\.\s+\*\*|\Z)",
        r"(?:^|\n)(?:#+\s*)?(?:\d+[\.、]?\s*)?核心结论\s*[:：]?\s*(?P<body>.*?)(?=\n(?:#+\s*)?(?:\d+[\.、]?\s*)?(?:执行摘要|投资要点|投资逻辑|结论)|\n\d+\.\s+\*\*|\Z)",
        r"(?:^|\n)(?:#+\s*)?(?:\d+[\.、]?\s*)?结论\s*[:：]?\s*(?P<body>.*?)(?=\n(?:#+\s*)?(?:\d+[\.、]?\s*)?(?:执行摘要|投资要点|投资逻辑|核心结论)|\n\d+\.\s+\*\*|\Z)",
    ]
    for pattern in section_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            summary = _extract_bullets_or_sentences(match.group("body"))
            if summary:
                return summary
    heading_patterns = [
        r"(?:^|\n)#+\s*执行摘要\s*\n(?P<body>.*?)(?=\n#+\s|\Z)",
        r"(?:^|\n)#+\s*投资要点\s*\n(?P<body>.*?)(?=\n#+\s|\Z)",
        r"(?:^|\n)#+\s*投资逻辑\s*\n(?P<body>.*?)(?=\n#+\s|\Z)",
        r"(?:^|\n)#+\s*Executive Summary\s*\n(?P<body>.*?)(?=\n#+\s|\Z)",
        r"(?:^|\n)\d+\.\s+\*\*Executive Summary\*\*\s*(?P<body>.*?)(?=\n\d+\.\s+\*\*|\Z)",
        r"(?:^|\n)\d+\.\s+\*\*Investment Thesis\*\*\s*(?P<body>.*?)(?=\n\d+\.\s+\*\*|\Z)",
    ]
    for pattern in heading_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            summary = _extract_bullets_or_sentences(match.group("body"))
            if summary:
                return summary
    return ""


def _clean_summary_text(text: str) -> str:
    summary = _markdown_to_plain_text(text or "")
    summary = re.sub(r"\s+", " ", summary).strip()
    summary = summary.replace("**", "").replace("`", "")
    summary = re.sub(r"^(?:交易分析报告|分析报告)\s*[:：-]?\s*", "", summary)
    summary = re.sub(r"^([A-Z0-9.\-]+)\s+", "", summary)
    summary = re.sub(r"^生成时间\s*[:：].*?(?=[A-Za-z一-龥])", "", summary)
    summary = re.sub(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X)[\.\s]+(?:分析师团队报告|分析报告)\s*", "", summary)
    return summary.strip(" -:：")


def _summarize_report_excerpt(text: str, limit: int = 220) -> str:
    return _preferred_text_excerpt(_clean_summary_text(text), limit=limit)


def _extract_preferred_summary(translated_text: str, decision_text: str, fallback_text: str) -> str:
    decision_summary = (
        _extract_numbered_section(decision_text, "Investment Thesis")
        or _extract_numbered_section(decision_text, "Executive Summary")
        or _extract_report_highlights(decision_text)
    )

    translated_summary = ""
    if translated_text and not _looks_mojibake(translated_text):
        translated_summary = _preferred_chinese_summary(translated_text) or _extract_report_highlights(translated_text)

    fallback_summary = (
        _extract_numbered_section(fallback_text, "Executive Summary")
        or _extract_numbered_section(fallback_text, "Investment Thesis")
        or _extract_report_highlights(fallback_text)
    )

    return (
        translated_summary
        or decision_summary
        or fallback_summary
        or _extract_bullets_or_sentences(fallback_text)
        or _markdown_to_plain_text(fallback_text)
    )


def _parse_report_timestamp(report_id: str, stat_mtime: float) -> str:
    match = re.search(r"_(\d{8}_\d{6})$", report_id)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.fromtimestamp(stat_mtime).strftime("%Y-%m-%d %H:%M:%S")


def _escape_inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noreferrer">\1</a>', escaped)
    return escaped


def markdown_to_html(markdown_text: str) -> str:
    lines = (markdown_text or "").replace("\r\n", "\n").split("\n")
    html_parts: List[str] = []
    paragraph: List[str] = []
    unordered: List[str] = []
    ordered: List[str] = []
    quote: List[str] = []
    code_lines: List[str] = []
    in_code = False
    code_lang = ""
    i = 0

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            html_parts.append(f"<p>{_escape_inline(' '.join(item.strip() for item in paragraph))}</p>")
            paragraph = []

    def flush_unordered():
        nonlocal unordered
        if unordered:
            items = "".join(f"<li>{_escape_inline(item)}</li>" for item in unordered)
            html_parts.append(f"<ul>{items}</ul>")
            unordered = []

    def flush_ordered():
        nonlocal ordered
        if ordered:
            items = "".join(f"<li>{_escape_inline(item)}</li>" for item in ordered)
            html_parts.append(f"<ol>{items}</ol>")
            ordered = []

    def flush_quote():
        nonlocal quote
        if quote:
            html_parts.append(f"<blockquote>{markdown_to_html(chr(10).join(quote))}</blockquote>")
            quote = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            flush_unordered()
            flush_ordered()
            flush_quote()
            if not in_code:
                in_code = True
                code_lang = stripped[3:].strip()
                code_lines = []
            else:
                code_html = html.escape("\n".join(code_lines))
                class_attr = f' class="language-{html.escape(code_lang)}"' if code_lang else ""
                html_parts.append(f"<pre><code{class_attr}>{code_html}</code></pre>")
                in_code = False
                code_lang = ""
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        if not stripped:
            flush_paragraph()
            flush_unordered()
            flush_ordered()
            flush_quote()
            i += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            flush_unordered()
            flush_ordered()
            quote.append(stripped[1:].strip())
            i += 1
            continue

        table_match = "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:-]+\|[\s|:-]*$", lines[i + 1])
        if table_match:
            flush_paragraph()
            flush_unordered()
            flush_ordered()
            flush_quote()
            header_cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            body_rows = []
            i += 2
            while i < len(lines) and "|" in lines[i]:
                body_rows.append([cell.strip() for cell in lines[i].strip().strip("|").split("|")])
                i += 1
            header_html = "".join(f"<th>{_escape_inline(cell)}</th>" for cell in header_cells)
            body_html = []
            for row in body_rows:
                cells = "".join(f"<td>{_escape_inline(cell)}</td>" for cell in row)
                body_html.append(f"<tr>{cells}</tr>")
            html_parts.append(
                "<div class=\"table-wrap\"><table><thead><tr>"
                + header_html
                + "</tr></thead><tbody>"
                + "".join(body_html)
                + "</tbody></table></div>"
            )
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            flush_unordered()
            flush_ordered()
            flush_quote()
            level = len(heading.group(1))
            html_parts.append(f"<h{level}>{_escape_inline(heading.group(2))}</h{level}>")
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,})$", stripped):
            flush_paragraph()
            flush_unordered()
            flush_ordered()
            flush_quote()
            html_parts.append("<hr />")
            i += 1
            continue

        unordered_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if unordered_match:
            flush_paragraph()
            flush_ordered()
            flush_quote()
            unordered.append(unordered_match.group(1).strip())
            i += 1
            continue

        ordered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ordered_match:
            flush_paragraph()
            flush_unordered()
            flush_quote()
            ordered.append(ordered_match.group(1).strip())
            i += 1
            continue

        paragraph.append(stripped)
        i += 1

    flush_paragraph()
    flush_unordered()
    flush_ordered()
    flush_quote()
    return "\n".join(html_parts)


def load_report_list() -> List[Dict[str, Any]]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    reports = []
    for folder in sorted(REPORTS_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not folder.is_dir():
            continue
        decision_text = ""
        decision_path = folder / "5_portfolio" / "decision.md"
        if decision_path.exists():
            decision_text = decision_path.read_text(encoding="utf-8", errors="ignore")
        complete_path = folder / "complete_report.md"
        complete_text = complete_path.read_text(encoding="utf-8", errors="ignore") if complete_path.exists() else ""
        translated_path = folder / "complete_report_zh.md"
        translated_text = translated_path.read_text(encoding="utf-8", errors="ignore") if translated_path.exists() else ""
        preferred_report_text = translated_text or complete_text
        list_summary = _summarize_report_excerpt(
            _extract_preferred_summary(translated_text, decision_text, preferred_report_text)
        )
        reports.append(
            {
                "id": folder.name,
                "ticker": folder.name.rsplit("_", 2)[0],
                "display_name": _get_display_name(folder.name.rsplit("_", 2)[0]),
                "created_at": _parse_report_timestamp(folder.name, folder.stat().st_mtime),
                "decision": _extract_rating(decision_text or preferred_report_text),
                "summary": list_summary,
                "has_translation": translated_path.exists(),
                "report_language": "zh" if translated_text else "en",
                "sections": {
                    "analysts": (folder / "1_analysts").exists(),
                    "research": (folder / "2_research").exists(),
                    "trading": (folder / "3_trading").exists(),
                    "risk": (folder / "4_risk").exists(),
                    "portfolio": (folder / "5_portfolio").exists(),
                },
            }
        )
    return reports


def load_report_detail(report_id: str) -> Dict[str, Any]:
    report_dir = REPORTS_DIR / report_id
    if not report_dir.exists():
        raise FileNotFoundError(report_id)

    section_specs = [
        ("market", "Market Analyst", report_dir / "1_analysts" / "market.md"),
        ("sentiment", "Social Analyst", report_dir / "1_analysts" / "sentiment.md"),
        ("news", "News Analyst", report_dir / "1_analysts" / "news.md"),
        ("fundamentals", "Fundamentals Analyst", report_dir / "1_analysts" / "fundamentals.md"),
        ("bull", "Bull Researcher", report_dir / "2_research" / "bull.md"),
        ("bear", "Bear Researcher", report_dir / "2_research" / "bear.md"),
        ("manager", "Research Manager", report_dir / "2_research" / "manager.md"),
        ("trader", "Trader", report_dir / "3_trading" / "trader.md"),
        ("aggressive", "Aggressive Analyst", report_dir / "4_risk" / "aggressive.md"),
        ("conservative", "Conservative Analyst", report_dir / "4_risk" / "conservative.md"),
        ("neutral", "Neutral Analyst", report_dir / "4_risk" / "neutral.md"),
        ("portfolio", "Portfolio Manager", report_dir / "5_portfolio" / "decision.md"),
    ]

    sections = []
    for key, title, path in section_specs:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        sections.append(
            {
                "key": key,
                "title": title,
                "markdown": content,
                "html": markdown_to_html(content),
                "excerpt": _text_excerpt(content),
            }
        )

    decision_path = report_dir / "5_portfolio" / "decision.md"
    decision_text = decision_path.read_text(encoding="utf-8", errors="ignore") if decision_path.exists() else ""
    complete_path = report_dir / "complete_report.md"
    complete_text = complete_path.read_text(encoding="utf-8", errors="ignore") if complete_path.exists() else ""
    translated_path = report_dir / "complete_report_zh.md"
    translated_text = translated_path.read_text(encoding="utf-8", errors="ignore") if translated_path.exists() else ""
    preferred_full_text = translated_text or complete_text
    detail_summary = (
        _preferred_text_excerpt(
            _extract_preferred_summary(translated_text, decision_text, preferred_full_text),
            600,
        )
        if translated_text
        else "该历史报告暂无中文完整报告。"
    )

    return {
        "id": report_id,
        "ticker": report_id.rsplit("_", 2)[0],
        "display_name": _get_display_name(report_id.rsplit("_", 2)[0]),
        "created_at": _parse_report_timestamp(report_id, report_dir.stat().st_mtime),
        "decision": _extract_rating(decision_text or preferred_full_text),
        "executive_summary": detail_summary,
        "investment_thesis": "当前右侧仅展示中文完整报告。" if translated_text else "当前记录缺少中文完整报告。",
        "full_report_html": markdown_to_html(preferred_full_text),
        "translated_report_html": markdown_to_html(translated_text) if translated_text else "",
        "has_translation": bool(translated_text),
        "sections": sections,
    }


class WebAnalysisTracker:
    FIXED_AGENTS = {
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
        "Portfolio Management": ["Portfolio Manager"],
    }

    ANALYST_MAPPING = {
        "market": "Market Analyst",
        "social": "Social Analyst",
        "news": "News Analyst",
        "fundamentals": "Fundamentals Analyst",
    }

    REPORT_SECTIONS = {
        "market_report": ("market", "Market Analyst"),
        "sentiment_report": ("social", "Social Analyst"),
        "news_report": ("news", "News Analyst"),
        "fundamentals_report": ("fundamentals", "Fundamentals Analyst"),
        "investment_plan": (None, "Research Manager"),
        "trader_investment_plan": (None, "Trader"),
        "final_trade_decision": (None, "Portfolio Manager"),
    }

    ANALYST_ORDER = ["market", "social", "news", "fundamentals"]
    ANALYST_REPORT_MAP = {
        "market": "market_report",
        "social": "sentiment_report",
        "news": "news_report",
        "fundamentals": "fundamentals_report",
    }

    def __init__(self, selected_analysts: List[str]) -> None:
        self.selected_analysts = [item.lower() for item in selected_analysts]
        self.agent_status = {}
        for analyst_key in self.selected_analysts:
            if analyst_key in self.ANALYST_MAPPING:
                self.agent_status[self.ANALYST_MAPPING[analyst_key]] = "pending"
        for team_agents in self.FIXED_AGENTS.values():
            for agent in team_agents:
                self.agent_status[agent] = "pending"

        self.report_sections = {}
        for section, (analyst_key, _) in self.REPORT_SECTIONS.items():
            if analyst_key is None or analyst_key in self.selected_analysts:
                self.report_sections[section] = ""

        self.messages: List[Dict[str, str]] = []
        self.tool_calls: List[Dict[str, str]] = []
        self.current_section = ""
        self._last_message_id = None

    def add_message(self, kind: str, content: str) -> None:
        if content:
            self.messages.append({"time": datetime.now().strftime("%H:%M:%S"), "type": kind, "content": _text_excerpt(content, 260)})
            self.messages = self.messages[-18:]

    def add_tool_call(self, name: str, args: Any) -> None:
        self.tool_calls.append(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "name": name,
                "args": _text_excerpt(json.dumps(args, ensure_ascii=False) if isinstance(args, (dict, list)) else str(args), 180),
            }
        )
        self.tool_calls = self.tool_calls[-18:]

    def update_status(self, agent: str, status: str) -> None:
        if agent in self.agent_status:
            self.agent_status[agent] = status

    def update_section(self, key: str, content: str) -> None:
        if key in self.report_sections and content:
            self.report_sections[key] = content
            self.current_section = key

    def update_analyst_statuses(self, chunk: Dict[str, Any]) -> None:
        found_active = False
        for analyst_key in self.ANALYST_ORDER:
            if analyst_key not in self.selected_analysts:
                continue
            agent_name = self.ANALYST_MAPPING[analyst_key]
            report_key = self.ANALYST_REPORT_MAP[analyst_key]
            if chunk.get(report_key):
                self.update_section(report_key, chunk[report_key])
            has_report = bool(self.report_sections.get(report_key))
            if has_report:
                self.update_status(agent_name, "completed")
            elif not found_active:
                self.update_status(agent_name, "running")
                found_active = True
            else:
                self.update_status(agent_name, "pending")

        if not found_active and self.selected_analysts and self.agent_status.get("Bull Researcher") == "pending":
            self.update_status("Bull Researcher", "running")

    def apply_chunk(self, chunk: Dict[str, Any]) -> None:
        if chunk.get("messages"):
            last_message = chunk["messages"][-1]
            msg_id = getattr(last_message, "id", None)
            if msg_id != self._last_message_id:
                self._last_message_id = msg_id
                content = getattr(last_message, "content", None)
                if isinstance(content, list):
                    content = " ".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in content)
                elif isinstance(content, dict):
                    content = content.get("text", "")
                if content:
                    self.add_message("message", str(content))
                for tool_call in getattr(last_message, "tool_calls", []) or []:
                    if isinstance(tool_call, dict):
                        self.add_tool_call(tool_call.get("name", ""), tool_call.get("args", {}))
                    else:
                        self.add_tool_call(getattr(tool_call, "name", ""), getattr(tool_call, "args", {}))

        self.update_analyst_statuses(chunk)

        if chunk.get("investment_debate_state"):
            debate_state = chunk["investment_debate_state"]
            bull_hist = debate_state.get("bull_history", "").strip()
            bear_hist = debate_state.get("bear_history", "").strip()
            judge = debate_state.get("judge_decision", "").strip()
            if bull_hist or bear_hist:
                self.update_status("Bull Researcher", "running")
                self.update_status("Bear Researcher", "running")
                self.update_status("Research Manager", "running")
            if judge:
                self.update_section("investment_plan", judge)
                self.update_status("Bull Researcher", "completed")
                self.update_status("Bear Researcher", "completed")
                self.update_status("Research Manager", "completed")
                self.update_status("Trader", "running")

        if chunk.get("trader_investment_plan"):
            self.update_section("trader_investment_plan", chunk["trader_investment_plan"])
            self.update_status("Trader", "completed")
            self.update_status("Aggressive Analyst", "running")

        if chunk.get("risk_debate_state"):
            risk_state = chunk["risk_debate_state"]
            if risk_state.get("aggressive_history"):
                self.update_status("Aggressive Analyst", "running")
            if risk_state.get("conservative_history"):
                self.update_status("Conservative Analyst", "running")
            if risk_state.get("neutral_history"):
                self.update_status("Neutral Analyst", "running")
            if risk_state.get("judge_decision"):
                self.update_section("final_trade_decision", risk_state["judge_decision"])
                self.update_status("Aggressive Analyst", "completed")
                self.update_status("Conservative Analyst", "completed")
                self.update_status("Neutral Analyst", "completed")
                self.update_status("Portfolio Manager", "completed")

    def snapshot(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agents": self.agent_status,
            "reports": {key: bool(value) for key, value in self.report_sections.items()},
            "current_section": self.current_section,
            "messages": self.messages[-8:],
            "tool_calls": self.tool_calls[-8:],
            "stats": stats,
        }


class JobManager:
    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "status": "queued",
            "created_at": _iso_now(),
            "started_at": None,
            "completed_at": None,
            "payload": payload,
            "progress": {},
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
        thread = threading.Thread(target=self._run_job, args=(job_id,), daemon=True)
        thread.start()
        return self.get(job_id)

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            jobs = [self._serialize(job) for job in self._jobs.values()]
        return sorted(jobs, key=lambda item: item["created_at"], reverse=True)

    def get(self, job_id: str) -> Dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._serialize(job) if job else None

    def _update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(fields)

    def _serialize(self, job: Dict[str, Any] | None) -> Dict[str, Any] | None:
        if not job:
            return None
        return {
            "id": job["id"],
            "status": job["status"],
            "created_at": _format_timestamp(job["created_at"]),
            "started_at": _format_timestamp(job["started_at"]),
            "completed_at": _format_timestamp(job["completed_at"]),
            "payload": job["payload"],
            "progress": job["progress"],
            "result": job["result"],
            "error": job["error"],
        }

    def _run_job(self, job_id: str) -> None:
        payload = self._jobs[job_id]["payload"]
        self._update(job_id, status="running", started_at=_iso_now())
        stats_handler = StatsCallbackHandler()
        try:
            ticker = resolve_ticker_input((payload.get("ticker") or "").strip())
            analysis_date = payload.get("analysis_date") or datetime.now().strftime("%Y-%m-%d")
            selected_analysts = payload.get("analysts") or [item["id"] for item in ANALYST_OPTIONS]
            tracker = WebAnalysisTracker(selected_analysts)

            config = DEFAULT_CONFIG.copy()
            config["llm_provider"] = payload.get("llm_provider", DEFAULT_CONFIG["llm_provider"]).lower()
            config["quick_think_llm"] = payload.get("quick_model", DEFAULT_CONFIG["quick_think_llm"])
            config["deep_think_llm"] = payload.get("deep_model", DEFAULT_CONFIG["deep_think_llm"])
            config["backend_url"] = payload.get("backend_url") or DEFAULT_CONFIG["backend_url"]
            research_depth = int(payload.get("research_depth", DEFAULT_CONFIG["max_debate_rounds"]))
            config["max_debate_rounds"] = research_depth
            config["max_risk_discuss_rounds"] = research_depth
            if payload.get("google_thinking_level"):
                config["google_thinking_level"] = payload["google_thinking_level"]
            if payload.get("openai_reasoning_effort"):
                config["openai_reasoning_effort"] = payload["openai_reasoning_effort"]
            if payload.get("anthropic_effort"):
                config["anthropic_effort"] = payload["anthropic_effort"]
            with _temporary_provider_api_key(config["llm_provider"], payload.get("api_key", "")):
                graph = TradingAgentsGraph(selected_analysts, config=config, debug=True, callbacks=[stats_handler])
                init_state = graph.propagator.create_initial_state(ticker, analysis_date)
                args = graph.propagator.get_graph_args(callbacks=[stats_handler])

                first_agent = tracker.ANALYST_MAPPING.get(selected_analysts[0], "Market Analyst")
                tracker.update_status(first_agent, "running")
                self._update(job_id, progress=tracker.snapshot(stats_handler.get_stats()))

                trace = []
                for chunk in graph.graph.stream(init_state, **args):
                    trace.append(chunk)
                    tracker.apply_chunk(chunk)
                    self._update(job_id, progress=tracker.snapshot(stats_handler.get_stats()))

                if not trace:
                    raise RuntimeError("Analysis produced no graph output.")

                final_state = trace[-1]
                translated_report = None
                translation_warning = None
                if payload.get("translate_to_chinese", True):
                    complete_report = build_complete_report_markdown(final_state, ticker)
                    try:
                        translated_report = translate_report_to_chinese(
                            complete_report,
                            {
                                "llm_provider": config["llm_provider"],
                                "deep_thinker": config["deep_think_llm"],
                                "shallow_thinker": config["quick_think_llm"],
                                "backend_url": config["backend_url"],
                            },
                        )
                    except Exception as exc:
                        translation_warning = f"Chinese translation skipped: {exc}"

                report_id = f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                report_path = REPORTS_DIR / report_id
                save_report_to_disk(final_state, ticker, report_path, translated_report)

            decision_text = final_state.get("risk_debate_state", {}).get("judge_decision", "") or final_state.get("final_trade_decision", "")
            self._update(
                job_id,
                status="completed",
                completed_at=_iso_now(),
                progress=tracker.snapshot(stats_handler.get_stats()),
                result={
                    "report_id": report_id,
                    "ticker": ticker,
                    "decision": _extract_rating(decision_text),
                    "analysis_date": analysis_date,
                    "warning": translation_warning,
                },
            )
        except Exception as exc:
            error_text = f"{exc}\n\n{traceback.format_exc(limit=8)}"
            self._update(job_id, status="failed", completed_at=_iso_now(), error=error_text)


JOB_MANAGER = JobManager()


class TradingAgentsWebHandler(BaseHTTPRequestHandler):
    server_version = "TradingAgentsWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_asset("index.html", "text/html; charset=utf-8")
            return
        if parsed.path.startswith("/assets/"):
            asset_name = parsed.path.replace("/assets/", "", 1)
            content_type = "text/plain; charset=utf-8"
            if asset_name.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif asset_name.endswith(".js"):
                content_type = "application/javascript; charset=utf-8"
            self._serve_asset(asset_name, content_type)
            return
        if parsed.path == "/api/options":
            self._write_json(get_ui_options())
            return
        if parsed.path == "/api/reports":
            self._write_json({"reports": load_report_list()})
            return
        if parsed.path.startswith("/api/reports/"):
            report_id = parsed.path.replace("/api/reports/", "", 1)
            try:
                self._write_json(load_report_detail(report_id))
            except FileNotFoundError:
                self._write_json({"error": "Report not found."}, status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path == "/api/jobs":
            self._write_json({"jobs": JOB_MANAGER.list()})
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.replace("/api/jobs/", "", 1)
            job = JOB_MANAGER.get(job_id)
            if job:
                self._write_json(job)
            else:
                self._write_json({"error": "Job not found."}, status=HTTPStatus.NOT_FOUND)
            return
        self._write_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/analyze":
            payload = self._read_json()
            raw_ticker = (payload.get("ticker") or "").strip()
            if not raw_ticker:
                self._write_json({"error": "Ticker is required."}, status=HTTPStatus.BAD_REQUEST)
                return
            candidates = _serialize_symbol_candidates(raw_ticker)
            if len(candidates) > 1 and raw_ticker.upper() not in {item["canonical_ticker"].upper() for item in candidates}:
                self._write_json(
                    {
                        "error": "Ambiguous ticker input.",
                        "ticker": raw_ticker,
                        "candidates": candidates,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            job = JOB_MANAGER.create(payload)
            self._write_json(job, status=HTTPStatus.ACCEPTED)
            return
        if parsed.path == "/api/generate-zh-report":
            payload = self._read_json()
            report_id = (payload.get("report_id") or "").strip()
            if not report_id:
                self._write_json({"error": "Report ID is required."}, status=HTTPStatus.BAD_REQUEST)
                return
            report_dir = REPORTS_DIR / report_id
            if not report_dir.exists():
                self._write_json({"error": "Report not found."}, status=HTTPStatus.NOT_FOUND)
                return
            try:
                selections = _build_translation_selections(payload)
                with _temporary_provider_api_key(selections["llm_provider"], selections.get("api_key", "")):
                    output_path = translate_saved_report_to_chinese(
                        report_dir,
                        selections,
                        overwrite=True,
                    )
                self._write_json(
                    {
                        "ok": True,
                        "report_id": report_id,
                        "translated_report_file": str(output_path),
                    }
                )
            except Exception as exc:
                self._write_json(
                    {
                        "error": f"Failed to generate Chinese report: {exc}",
                        "details": traceback.format_exc(limit=8),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return
        if parsed.path.startswith("/api/reports/") and parsed.path.endswith("/generate-zh"):
            report_id = parsed.path.replace("/api/reports/", "", 1).replace("/generate-zh", "").strip("/")
            report_dir = REPORTS_DIR / report_id
            if not report_dir.exists():
                self._write_json({"error": "Report not found."}, status=HTTPStatus.NOT_FOUND)
                return
            payload = self._read_json()
            try:
                selections = _build_translation_selections(payload)
                with _temporary_provider_api_key(selections["llm_provider"], selections.get("api_key", "")):
                    output_path = translate_saved_report_to_chinese(
                        report_dir,
                        selections,
                        overwrite=True,
                    )
                self._write_json(
                    {
                        "ok": True,
                        "report_id": report_id,
                        "translated_report_file": str(output_path),
                    }
                )
            except Exception as exc:
                self._write_json(
                    {
                        "error": f"Failed to generate Chinese report: {exc}",
                        "details": traceback.format_exc(limit=8),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return
        self._write_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _serve_asset(self, asset_name: str, content_type: str) -> None:
        asset_path = ASSET_DIR / asset_name
        if not asset_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = asset_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _write_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), TradingAgentsWebHandler)
    print(f"TradingAgents Web UI running at http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    run_server()
