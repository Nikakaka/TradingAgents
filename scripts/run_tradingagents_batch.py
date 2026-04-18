import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import gc
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_SINGLE = REPO_ROOT / "scripts" / "run_tradingagents.py"
REPORTS_DIR = REPO_ROOT / "reports"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tradingagents.market_utils import load_symbol_index

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


SUMMARY_HEADINGS = (
    "\u6267\u884c\u6458\u8981",
    "\u6295\u8d44\u8981\u70b9",
    "\u6295\u8d44\u903b\u8f91",
    "\u6838\u5fc3\u7ed3\u8bba",
    "Executive Summary",
    "Investment Thesis",
    "Key Takeaways",
)

# Portfolio manager decision section markers (used to find the final executive summary)
PORTFOLIO_DECISION_MARKERS = (
    "\u6295\u8d44\u7ec4\u5408\u7ecf\u7406\u51b3\u7b56",  # 投资组合经理决策
    "\u4e94\u3001\u6295\u8d44\u7ec4\u5408\u7ecf\u7406",  # 五、投资组合经理
    "Portfolio Manager Decision",
    "V. \u6295\u8d44\u7ec4\u5408\u7ecf\u7406",  # V. 投资组合经理
)

DISPLAY_NAME_OVERRIDES = {
    "159934.SZ": "\u9ec4\u91d19999\uff08\u4ee3\u7406\uff1a\u9ec4\u91d1ETF\uff09",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a batch of TradingAgents tasks for OpenClaw watchlists."
    )
    parser.add_argument("batch_file", help="JSON array file containing task objects.")
    parser.add_argument("--result-json", default=None, help="Optional batch summary JSON output path.")
    parser.add_argument(
        "--result-markdown",
        default=None,
        help="Optional Markdown daily report output path.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop batch execution after the first task failure.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve each task and print results without running analysis.",
    )
    parser.add_argument(
        "--retry-on-rate-limit",
        action="store_true",
        default=True,
        help="Retry a task when the upstream provider returns a rate-limit error.",
    )
    parser.add_argument(
        "--max-rate-limit-retries",
        type=int,
        default=2,
        help="Maximum retry attempts for 429/1302 rate-limit failures.",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=int,
        default=15,
        help="Base backoff in seconds for rate-limit retries.",
    )
    parser.add_argument(
        "--inter-task-delay-seconds",
        type=int,
        default=10,
        help="Delay in seconds between tasks to reduce provider burst traffic.",
    )
    parser.add_argument(
        "--regenerate-summary",
        action="store_true",
        help="Regenerate batch summary from existing result files without running analysis.",
    )
    return parser.parse_args()


def resolve_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def load_batch_file(path_value: str) -> list[dict[str, Any]]:
    batch_path = resolve_path(path_value)
    if batch_path is None or not batch_path.exists():
        raise FileNotFoundError(f"Batch config file not found: {path_value}")

    payload = json.loads(batch_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("Batch config JSON must be an array of task objects.")

    normalized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Each batch task must be a JSON object.")
        normalized.append(item.copy())
    return normalized


def ensure_result_json(task: dict[str, Any], index: int) -> Path:
    result_json = task.get("result_json")
    if result_json:
        result_path = resolve_path(str(result_json))
    else:
        ticker = str(task.get("ticker", f"task_{index + 1}")).replace(".", "_").lower()
        result_path = resolve_path(f"results/openclaw/{ticker}_batch.json")
        assert result_path is not None
        task["result_json"] = str(result_path.relative_to(REPO_ROOT)).replace("\\", "/")

    assert result_path is not None
    result_path.parent.mkdir(parents=True, exist_ok=True)
    return result_path


def run_task(task: dict[str, Any], index: int, dry_run: bool) -> dict[str, Any]:
    result_path = ensure_result_json(task, index)

    with tempfile.TemporaryDirectory(prefix="tradingagents_batch_", dir=REPO_ROOT) as tmpdir:
        config_path = Path(tmpdir) / f"task_{index + 1}.json"
        config_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")

        command = [
            sys.executable,
            str(RUN_SINGLE),
            "--config-file",
            str(config_path),
            "--result-json",
            str(result_path),
        ]
        if dry_run:
            command.append("--dry-run")

        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    payload: dict[str, Any] = {}

    if result_path.exists():
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}

    if not payload and stdout:
        try:
            payload = json.loads(stdout)
        except Exception:
            payload = {}

    if completed.returncode != 0:
        error_text = stderr or stdout or "Task execution failed."
        return {
            "status": "error",
            "ticker": task.get("ticker"),
            "analysis_date": task.get("analysis_date"),
            "provider": task.get("provider"),
            "quick_model": task.get("quick_model"),
            "deep_model": task.get("deep_model"),
            "result_json": str(result_path),
            "returncode": completed.returncode,
            "error": error_text,
            "stdout": stdout,
            "stderr": stderr,
        }

    payload["returncode"] = completed.returncode
    payload["result_json"] = str(result_path)
    return payload


def is_rate_limit_error(result: dict[str, Any]) -> bool:
    haystacks = [
        str(result.get("error") or ""),
        str(result.get("stderr") or ""),
        str(result.get("stdout") or ""),
    ]
    normalized = "\n".join(haystacks).lower()
    patterns = (
        "ratelimiterror",
        "rate limit",
        "error code: 429",
        "\"code\": \"1302\"",
        "'code': '1302'",
        "达到速率限制",
        "速率限制",
    )
    return any(pattern in normalized for pattern in patterns)


def run_task_with_retries(
    task: dict[str, Any],
    index: int,
    dry_run: bool,
    retry_on_rate_limit: bool,
    max_rate_limit_retries: int,
    retry_backoff_seconds: int,
) -> dict[str, Any]:
    attempt = 0
    last_result: dict[str, Any] | None = None

    while True:
        attempt += 1
        if attempt > 1:
            ticker = task.get("ticker") or f"task_{index + 1}"
            print(
                f"[batch] retry attempt {attempt - 1}/{max_rate_limit_retries} for {ticker}",
                flush=True,
            )

        result = run_task(task, index, dry_run)
        result["attempt"] = attempt
        last_result = result

        # Force garbage collection after each task to free memory
        gc.collect()

        should_retry = (
            retry_on_rate_limit
            and not dry_run
            and result.get("status") == "error"
            and is_rate_limit_error(result)
            and attempt <= max_rate_limit_retries
        )
        if not should_retry:
            return result

        sleep_seconds = retry_backoff_seconds * attempt
        ticker = task.get("ticker") or f"task_{index + 1}"
        print(
            f"[batch] rate limit detected for {ticker}, sleeping {sleep_seconds}s before retry",
            flush=True,
        )
        time.sleep(sleep_seconds)


def load_display_names() -> dict[str, str]:
    try:
        return {
            str(item.get("canonical_ticker", "")).upper(): str(item.get("name", "")).strip()
            for item in load_symbol_index()
            if item.get("canonical_ticker") and item.get("name")
        }
    except Exception:
        return {}


def display_name(ticker: str, display_names: dict[str, str]) -> str:
    if (ticker or "").upper() in DISPLAY_NAME_OVERRIDES:
        return DISPLAY_NAME_OVERRIDES[(ticker or "").upper()]
    return display_names.get((ticker or "").upper(), ticker or "-")


def read_text_if_exists(path_value: str | Path | None) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.exists():
        return ""
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            continue
    return path.read_text(errors="ignore")


def markdown_to_plain_text(content: str) -> str:
    text = content.replace("\r\n", "\n")
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+\.\s*", "", text, flags=re.M)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"_{1,2}(.*?)_{1,2}", r"\1", text)
    text = re.sub(r"\|", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def extract_sentences(text: str, max_sentences: int = 3, max_chars: int = 320) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ""

    pieces = re.split(r"(?<=[\u3002\uff01\uff1f.!?])\s+", compact)
    chosen: list[str] = []
    current_length = 0
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        chosen.append(piece)
        current_length += len(piece)
        if len(chosen) >= max_sentences or current_length >= max_chars:
            break

    summary = " ".join(chosen).strip()
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary


def extract_report_summary(content: str) -> str:
    """Extract summary from report content.

    Priority:
    1. Executive summary from Portfolio Manager Decision section (most authoritative)
    2. First available summary section as fallback

    Supports multiple formats:
    - Markdown heading: ## 执行摘要
    - Bold inline: **执行摘要**：内容...
    """
    if not content:
        return ""

    lines = content.replace("\r\n", "\n").split("\n")

    # First, try to find the Portfolio Manager Decision section and extract its summary
    portfolio_section_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        for marker in PORTFOLIO_DECISION_MARKERS:
            if marker in stripped:
                portfolio_section_start = i
                break
        if portfolio_section_start is not None:
            break

    # If portfolio section found, look for executive summary within it
    if portfolio_section_start is not None:
        # Look for executive summary in bold inline format: **执行摘要**：内容
        for line in lines[portfolio_section_start:]:
            stripped = line.strip()
            # Check for bold inline format: **执行摘要**：内容
            for heading in SUMMARY_HEADINGS[:4]:  # Chinese headings
                pattern = f"**{heading}**\uff1a"  # **执行摘要**：
                if pattern in stripped:
                    # Extract content after the colon
                    idx = stripped.find(pattern) + len(pattern)
                    summary_text = stripped[idx:].strip()
                    if summary_text:
                        return extract_sentences(markdown_to_plain_text(summary_text))
                # Also try with regular colon
                pattern = f"**{heading}**:"
                if pattern in stripped:
                    idx = stripped.find(pattern) + len(pattern)
                    summary_text = stripped[idx:].strip()
                    if summary_text:
                        return extract_sentences(markdown_to_plain_text(summary_text))

        # Fallback: look for heading format
        capture = False
        bucket: list[str] = []
        for line in lines[portfolio_section_start:]:
            stripped = line.strip()
            heading = stripped.lstrip("#").strip().rstrip(":\uff1a")

            # Check for executive summary heading
            if any(heading == item for item in SUMMARY_HEADINGS[:4]):  # Chinese headings
                capture = True
                continue
            if any(heading == item for item in SUMMARY_HEADINGS[4:]):  # English headings
                capture = True
                continue

            # Stop at next major section (## heading) or next analyst section
            if capture and stripped.startswith("#"):
                break

            if capture:
                bucket.append(line)

        if bucket:
            excerpt = markdown_to_plain_text("\n".join(bucket)).strip()
            if excerpt:
                return extract_sentences(excerpt)

    # Fallback: extract from first available summary section
    capture = False
    bucket: list[str] = []
    for line in lines:
        stripped = line.strip()
        heading = stripped.lstrip("#").strip().rstrip(":\uff1a")

        if any(heading == item for item in SUMMARY_HEADINGS):
            capture = True
            continue

        if capture and stripped.startswith("#"):
            break

        if capture:
            bucket.append(line)

    excerpt = markdown_to_plain_text("\n".join(bucket)).strip()
    if not excerpt:
        excerpt = markdown_to_plain_text(content)
    return extract_sentences(excerpt)


def extract_decision_from_text(content: str) -> str | None:
    """Extract trading decision from text content.

    Supports 5-level rating system: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL
    """
    if not content:
        return None

    # Decision patterns in order of priority (most specific first)
    # OVERWEIGHT/UNDERWEIGHT must be checked before BUY/SELL to avoid partial matches
    patterns = (
        r"FINAL RECOMMENDATION:\s*(OVERWEIGHT|UNDERWEIGHT|BUY|HOLD|SELL)",
        r"FINAL TRANSACTION PROPOSAL:\s*\**\s*(OVERWEIGHT|UNDERWEIGHT|BUY|HOLD|SELL)",
        r"RATING:\s*\*{0,2}\s*(OVERWEIGHT|UNDERWEIGHT|BUY|HOLD|SELL)",
        r"RECOMMENDATION:\s*(OVERWEIGHT|UNDERWEIGHT|BUY|HOLD|SELL)",
        r"RATING:\s*(OVERWEIGHT|UNDERWEIGHT|BUY|HOLD|SELL)",
        r"\b(Overweight|Underweight|Buy|Hold|Sell)\b",
    )
    match = None
    for pattern in patterns:
        match = re.search(pattern, content, flags=re.I)
        if match:
            break
    if not match:
        return None
    return match.group(1).upper()


def decision_label(decision: str | None) -> str:
    mapping = {
        "BUY": "\u4e70\u5165",
        "OVERWEIGHT": "\u589e\u6301",
        "HOLD": "\u6301\u6709",
        "UNDERWEIGHT": "\u51cf\u6301",
        "SELL": "\u5356\u51fa",
    }
    return mapping.get((decision or "").upper(), decision or "\u672a\u77e5")


def decision_bucket(item: dict[str, Any]) -> str:
    """Bucket items by decision for summary grouping.

    Groups: buy (BUY, OVERWEIGHT), hold, sell (SELL, UNDERWEIGHT), other, failed
    """
    if item.get("status") not in {"ok", "dry_run"}:
        return "failed"
    decision = extract_decision_from_text(str(item.get("decision") or "")) or str(item.get("decision") or "").upper()
    if decision in ("BUY", "OVERWEIGHT"):
        return "buy"
    if decision == "HOLD":
        return "hold"
    if decision in ("SELL", "UNDERWEIGHT"):
        return "sell"
    return "other"


def bucket_title(bucket: str) -> str:
    titles = {
        "buy": "\u4e70\u5165",
        "hold": "\u6301\u6709",
        "sell": "\u5356\u51fa",
        "other": "\u5176\u4ed6",
        "failed": "\u5931\u8d25",
    }
    return titles.get(bucket, bucket)


def summary_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"buy": 0, "hold": 0, "sell": 0, "other": 0, "failed": 0}
    for item in items:
        counts[decision_bucket(item)] += 1
    return counts


def preferred_report_path(item: dict[str, Any]) -> Path | None:
    """Get the preferred report file path.

    Priority:
    1. report_file (complete_report.md) - now outputs Chinese directly
    2. translated_report_file (legacy, for backwards compatibility)
    """
    # Check report_file first (now outputs Chinese directly)
    report_file = item.get("report_file")
    if report_file:
        path = Path(report_file)
        if path.exists():
            return path

    # Fallback to translated_report_file for legacy reports
    translated_file = item.get("translated_report_file")
    if translated_file:
        path = Path(translated_file)
        if path.exists():
            return path

    return None


def find_previous_report(item: dict[str, Any]) -> tuple[str | None, str | None]:
    ticker = str(item.get("ticker") or "").strip()
    current_report = item.get("report_file")
    if not ticker or not current_report:
        return None, None

    current_dir = Path(current_report).resolve().parent
    if not REPORTS_DIR.exists():
        return None, None

    candidates = []
    for directory in REPORTS_DIR.glob(f"{ticker}_*"):
        if not directory.is_dir() or directory.resolve() == current_dir:
            continue
        candidates.append(directory)

    if not candidates:
        return None, None

    previous_dir = sorted(candidates, key=lambda path: path.name)[-1]

    decision_file = previous_dir / "5_portfolio" / "decision.md"
    previous_decision = extract_decision_from_text(read_text_if_exists(decision_file))

    previous_report = previous_dir / "complete_report_zh.md"
    if not previous_report.exists():
        previous_report = previous_dir / "complete_report.md"
    if not previous_report.exists():
        return previous_decision, None

    return previous_decision, str(previous_report.resolve())


def decision_change_label(current_decision: str | None, previous_decision: str | None) -> str:
    if not current_decision and not previous_decision:
        return "\u65e0\u6cd5\u5224\u65ad"
    if not previous_decision:
        return "\u65e0\u53ef\u5bf9\u6bd4\u7684\u4e0a\u4e00\u4efd\u62a5\u544a"
    if not current_decision:
        return f"\u5f53\u524d\u7ed3\u8bba\u7f3a\u5931\uff0c\u4e0a\u4e00\u4efd\u4e3a{decision_label(previous_decision)}"
    if current_decision.upper() == previous_decision.upper():
        return f"\u4e0e\u4e0a\u4e00\u4efd\u62a5\u544a\u4e00\u81f4\uff08{decision_label(current_decision)}\uff09"
    return f"\u7531 {decision_label(previous_decision)} \u53d8\u4e3a {decision_label(current_decision)}"


def enrich_results(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    display_names = load_display_names()
    enriched: list[dict[str, Any]] = []

    for item in items:
        ticker = str(item.get("ticker") or "")
        preferred_report = preferred_report_path(item)
        report_text = read_text_if_exists(preferred_report)
        current_decision = extract_decision_from_text(str(item.get("decision") or ""))
        if not current_decision:
            current_decision = extract_decision_from_text(report_text)
        previous_decision, previous_report = find_previous_report(item)

        enriched_item = item.copy()
        enriched_item["decision"] = current_decision or item.get("decision")
        enriched_item["display_name"] = display_name(ticker, display_names)
        enriched_item["preferred_report_file"] = str(preferred_report.resolve()) if preferred_report else None
        enriched_item["report_summary"] = extract_report_summary(report_text)
        enriched_item["previous_decision"] = previous_decision
        enriched_item["previous_report_file"] = previous_report
        enriched_item["decision_change"] = decision_change_label(current_decision, previous_decision)
        enriched.append(enriched_item)

    return enriched


def build_markdown_summary(items: list[dict[str, Any]], batch_file: str) -> str:
    counts = summary_counts(items)
    lines = [
        "# \u4ea4\u6613\u6295\u7814\u65e5\u62a5",
        "",
        f"- \u4efb\u52a1\u6587\u4ef6\uff1a`{batch_file}`",
        f"- \u6807\u7684\u603b\u6570\uff1a{len(items)}",
        (
            f"- \u4e70\u5165\uff1a{counts['buy']} | \u6301\u6709\uff1a{counts['hold']} | "
            f"\u5356\u51fa\uff1a{counts['sell']} | \u5176\u4ed6\uff1a{counts['other']} | "
            f"\u5931\u8d25\uff1a{counts['failed']}"
        ),
        "",
    ]

    # Add portfolio summary if position info available
    positions_with_pnl = [item for item in items if item.get("position_info")]
    if positions_with_pnl:
        total_value = sum(
            item["position_info"].get("market_value", 0) or 0
            for item in positions_with_pnl
        )
        total_pnl = sum(
            item["position_info"].get("profit_loss", 0) or 0
            for item in positions_with_pnl
        )
        if total_value > 0:
            total_pnl_pct = (total_pnl / total_value) * 100
            lines.append("## \u6301\u4ed3\u6c47\u603b")
            lines.append("")
            lines.append(f"- \u603b\u5e02\u503c\uff1a\u00a5{total_value:,.2f}")
            lines.append(f"- \u603b\u76c8\u4e8f\uff1a\u00a5{total_pnl:,.2f} ({total_pnl_pct:+.2f}%)")
            lines.append("")

    lines.append("## \u7ed3\u8bba\u603b\u89c8")
    lines.append("")
    lines.append("| \u6807\u7684 | \u7ed3\u8bba | \u53d8\u5316 | \u72b6\u6001 |")
    lines.append("| --- | --- | --- | --- |")
    for item in items:
        display = item.get("display_name") or item.get("ticker") or "-"
        ticker = item.get("ticker") or "-"
        decision = decision_label(str(item.get("decision") or "").upper()) if item.get("decision") else "\u672a\u77e5"
        lines.append(
            f"| {display} ({ticker}) | {decision} | {item.get('decision_change') or '-'} | {item.get('status') or '-'} |"
        )
    lines.append("")

    for bucket in ("buy", "hold", "sell", "other", "failed"):
        bucket_items = [item for item in items if decision_bucket(item) == bucket]
        if not bucket_items:
            continue

        lines.append(f"## {bucket_title(bucket)}")
        lines.append("")

        for item in bucket_items:
            display = item.get("display_name") or item.get("ticker") or "-"
            ticker = item.get("ticker") or "-"
            status = item.get("status") or "-"
            decision = item.get("decision")

            lines.append(f"### {display} ({ticker})")
            lines.append("")
            lines.append(f"- \u8fd0\u884c\u72b6\u6001\uff1a{status}")
            lines.append(f"- \u5206\u6790\u65e5\u671f\uff1a{item.get('analysis_date') or '-'}")
            lines.append(f"- \u6a21\u578b\u4f9b\u5e94\u5546\uff1a{item.get('provider') or '-'}")
            if decision:
                lines.append(f"- \u6700\u7ec8\u7ed3\u8bba\uff1a{decision_label(str(decision).upper())}")
            lines.append(f"- \u7ed3\u8bba\u53d8\u5316\uff1a{item.get('decision_change') or '-'}")

            # Position info
            pos_info = item.get("position_info")
            if pos_info:
                lines.append("")
                lines.append("**\u6301\u4ed3\u4fe1\u606f**")
                if pos_info.get("quantity"):
                    lines.append(f"- \u6301\u4ed3\u6570\u91cf\uff1a{pos_info['quantity']}")
                if pos_info.get("cost_price"):
                    lines.append(f"- \u6210\u672c\u4ef7\uff1a\u00a5{pos_info['cost_price']:.2f}")
                if pos_info.get("market_value"):
                    lines.append(f"- \u5e02\u503c\uff1a\u00a5{pos_info['market_value']:,.2f}")
                if pos_info.get("profit_loss") is not None:
                    pnl = pos_info['profit_loss']
                    pnl_pct = pos_info.get('profit_loss_pct', 0) or 0
                    pnl_sign = "+" if pnl >= 0 else ""
                    lines.append(f"- \u76c8\u4e8f\uff1a\u00a5{pnl:,.2f} ({pnl_sign}{pnl_pct:.2f}%)")

            if item.get("previous_report_file"):
                lines.append(f"- \u4e0a\u4e00\u4efd\u62a5\u544a\uff1a`{item['previous_report_file']}`")
            if item.get("report_summary"):
                lines.append(f"- \u62a5\u544a\u6458\u8981\uff1a{item['report_summary']}")
            if item.get("preferred_report_file"):
                lines.append(f"- \u5f53\u524d\u62a5\u544a\uff1a`{item['preferred_report_file']}`")
            if item.get("translated_report_file") and item.get("report_file"):
                lines.append(f"- \u82f1\u6587\u62a5\u544a\uff1a`{item['report_file']}`")
            if item.get("error"):
                lines.append(f"- \u9519\u8bef\u4fe1\u606f\uff1a{str(item['error']).strip()}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_text_output(path_value: str | None, content: str, encoding: str = "utf-8") -> str | None:
    path = resolve_path(path_value)
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)
    return str(path)


def load_existing_result(task: dict[str, Any], index: int) -> dict[str, Any] | None:
    """Load existing result from result_json path if available.

    Returns None if result file doesn't exist or is invalid.
    """
    result_json = task.get("result_json")
    if not result_json:
        return None

    result_path = resolve_path(result_json)
    if result_path is None or not result_path.exists():
        return None

    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        payload["result_json"] = str(result_path)
        payload["loaded_from_existing"] = True
        return payload
    except Exception:
        return None


def regenerate_summary_from_existing_results(
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Regenerate results from existing result files without running analysis.

    This is useful when individual stock analyses have been re-run and the
    batch summary needs to be updated.
    """
    results: list[dict[str, Any]] = []
    for index, task in enumerate(tasks):
        ticker = task.get("ticker") or f"task_{index + 1}"
        result = load_existing_result(task, index)

        if result is None:
            result = {
                "status": "error",
                "ticker": task.get("ticker"),
                "analysis_date": task.get("analysis_date"),
                "error": f"Result file not found or invalid for {ticker}",
                "result_json": task.get("result_json"),
            }
        else:
            result["status"] = result.get("status", "ok")

        results.append(result)
        print(
            f"[regenerate] loaded {ticker} with status={result.get('status')}",
            flush=True,
        )

    return results


def main() -> int:
    args = parse_args()
    tasks = load_batch_file(args.batch_file)
    results: list[dict[str, Any]] = []

    # Regenerate summary mode: load existing results without running analysis
    if args.regenerate_summary:
        print("[batch] regenerating summary from existing result files", flush=True)
        results = regenerate_summary_from_existing_results(tasks)
    else:
        # Normal mode: run analysis for each task
        for index, task in enumerate(tasks):
            ticker = task.get("ticker") or f"task_{index + 1}"
            print(
                f"[batch] starting {index + 1}/{len(tasks)}: {ticker}",
                flush=True,
            )
            result = run_task_with_retries(
                task,
                index,
                args.dry_run,
                args.retry_on_rate_limit,
                max(args.max_rate_limit_retries, 0),
                max(args.retry_backoff_seconds, 1),
            )
            results.append(result)
            print(
                f"[batch] finished {ticker} with status={result.get('status')} attempt={result.get('attempt', 1)}",
                flush=True,
            )
            if args.stop_on_error and result.get("status") == "error":
                break
            if (
                not args.dry_run
                and index < len(tasks) - 1
                and args.inter_task_delay_seconds > 0
            ):
                print(
                    f"[batch] sleeping {args.inter_task_delay_seconds}s before next task",
                    flush=True,
                )
                time.sleep(args.inter_task_delay_seconds)

    enriched_results = enrich_results(results)
    summary = {
        "status": "ok" if all(item.get("status") != "error" for item in results) else "partial_error",
        "batch_file": str(resolve_path(args.batch_file)),
        "dry_run": args.dry_run,
        "task_count": len(tasks),
        "completed_count": len(results),
        "counts": summary_counts(enriched_results),
        "results": enriched_results,
    }

    write_text_output(args.result_json, json.dumps(summary, ensure_ascii=False, indent=2))

    if args.result_markdown:
        markdown = build_markdown_summary(enriched_results, summary["batch_file"])
        write_text_output(args.result_markdown, markdown, encoding="utf-8-sig")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
