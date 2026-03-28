import argparse
import json
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from cli.main import build_complete_report_markdown, save_report_to_disk, translate_report_to_chinese
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


VALID_ANALYSTS = ("market", "social", "news", "fundamentals")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run TradingAgents non-interactively for OpenClaw or other automation."
    )
    parser.add_argument(
        "--config-file",
        default=None,
        help="JSON file containing task parameters. CLI flags override values from the file.",
    )
    parser.add_argument("--ticker", default="9988.HK", help="Ticker symbol to analyze.")
    parser.add_argument(
        "--date",
        dest="analysis_date",
        default=str(date.today()),
        help="Analysis date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--analysts",
        default="market,social,news,fundamentals",
        help="Comma-separated analysts to enable. Options: market,social,news,fundamentals",
    )
    parser.add_argument(
        "--research-depth",
        type=int,
        default=DEFAULT_CONFIG["max_debate_rounds"],
        help="Debate depth for research and risk teams.",
    )
    parser.add_argument("--provider", default=DEFAULT_CONFIG["llm_provider"], help="LLM provider key.")
    parser.add_argument("--quick-model", default=DEFAULT_CONFIG["quick_think_llm"], help="Quick-thinking model.")
    parser.add_argument("--deep-model", default=DEFAULT_CONFIG["deep_think_llm"], help="Deep-thinking model.")
    parser.add_argument("--backend-url", default=DEFAULT_CONFIG["backend_url"], help="Provider base URL.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory where reports are written. Defaults to reports/<ticker>_<date>_<timestamp>",
    )
    parser.add_argument(
        "--result-json",
        default=None,
        help="Optional file path where the final JSON result will also be written.",
    )
    parser.add_argument(
        "--skip-translation",
        action="store_true",
        help="Skip generating complete_report_zh.md.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved configuration and exit without running analysis.",
    )
    return parser


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def parser_defaults() -> dict[str, Any]:
    return vars(build_parser().parse_args([]))


def apply_config_file(args: argparse.Namespace) -> argparse.Namespace:
    config_file = getattr(args, "config_file", None)
    if not config_file:
        return args

    config_path = Path(config_file)
    if not config_path.is_absolute():
        config_path = (REPO_ROOT / config_path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Task config file not found: {config_path}")

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Task config JSON must be an object.")

    defaults = parser_defaults()
    merged = vars(args).copy()

    for key, value in payload.items():
        normalized_key = key.replace("-", "_")
        if normalized_key in merged:
            merged[normalized_key] = value

    for key, default_value in defaults.items():
        current_value = getattr(args, key)
        if current_value != default_value:
            merged[key] = current_value

    return argparse.Namespace(**merged)


def parse_analysts(raw_value: str) -> list[str]:
    analysts = [item.strip().lower() for item in raw_value.split(",") if item.strip()]
    if not analysts:
        raise ValueError("At least one analyst must be provided.")

    invalid = [item for item in analysts if item not in VALID_ANALYSTS]
    if invalid:
        raise ValueError(f"Unsupported analysts: {', '.join(invalid)}")

    deduped = []
    for analyst in analysts:
        if analyst not in deduped:
            deduped.append(analyst)
    return deduped


def build_output_dir(ticker: str, analysis_date: str, output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    safe_date = analysis_date.replace("-", "")
    return Path("reports") / f"{safe_ticker}_{safe_date}_{timestamp}"


def resolve_analysis_date(raw_value: str) -> str:
    value = (raw_value or "").strip().lower()
    if not value:
        return str(date.today())
    if value == "today":
        return str(date.today())
    if value.startswith("today-") and value[6:].isdigit():
        return str(date.today() - timedelta(days=int(value[6:])))
    if value.startswith("today+") and value[6:].isdigit():
        return str(date.today() + timedelta(days=int(value[6:])))
    datetime.strptime(raw_value, "%Y-%m-%d")
    return raw_value


def build_config(args: argparse.Namespace) -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = args.provider.lower()
    config["quick_think_llm"] = args.quick_model
    config["deep_think_llm"] = args.deep_model
    config["backend_url"] = args.backend_url
    config["max_debate_rounds"] = args.research_depth
    config["max_risk_discuss_rounds"] = args.research_depth
    return config


def write_result_json(result_json: str | None, payload: dict[str, Any]) -> None:
    if not result_json:
        return
    result_path = Path(result_json)
    if not result_path.is_absolute():
        result_path = (REPO_ROOT / result_path).resolve()
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_translation_error_log(output_dir: Path, args: argparse.Namespace, exc: Exception) -> Path:
    log_path = output_dir / "translation_error.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now().isoformat(timespec='seconds')}] Translation failed\n")
        handle.write(f"Ticker: {args.ticker}\n")
        handle.write(f"Provider: {args.provider}\n")
        handle.write(f"Quick model: {args.quick_model}\n")
        handle.write(f"Deep model: {args.deep_model}\n")
        handle.write(f"Backend URL: {args.backend_url}\n")
        handle.write(f"Error: {exc}\n")
        handle.write(traceback.format_exc())
        handle.write("\n")
    return log_path


def main() -> int:
    load_dotenv()
    args = apply_config_file(parse_args())
    args.analysis_date = resolve_analysis_date(args.analysis_date)
    analysts = parse_analysts(args.analysts)
    output_dir = build_output_dir(args.ticker, args.analysis_date, args.output_dir)
    config = build_config(args)

    summary = {
        "ticker": args.ticker,
        "analysis_date": args.analysis_date,
        "analysts": analysts,
        "research_depth": args.research_depth,
        "provider": config["llm_provider"],
        "quick_model": config["quick_think_llm"],
        "deep_model": config["deep_think_llm"],
        "backend_url": config["backend_url"],
        "output_dir": str(output_dir.resolve()),
        "skip_translation": args.skip_translation,
        "config_file": str(Path(args.config_file).resolve()) if args.config_file else None,
    }

    if args.dry_run:
        result = {"status": "dry_run", **summary}
        write_result_json(args.result_json, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    graph = TradingAgentsGraph(
        selected_analysts=analysts,
        config=config,
        debug=False,
    )
    final_state, decision = graph.propagate(args.ticker, args.analysis_date)

    translated_report = None
    complete_report = build_complete_report_markdown(final_state, args.ticker)
    if not args.skip_translation:
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
            log_path = write_translation_error_log(output_dir, args, exc)
            print(
                json.dumps(
                    {
                        "warning": "translation_failed",
                        "ticker": args.ticker,
                        "translation_error_log": str(log_path.resolve()),
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )

    report_file = save_report_to_disk(
        final_state,
        args.ticker,
        output_dir,
        translated_report=translated_report,
    )

    result = {
        "status": "ok",
        **summary,
        "decision": decision,
        "report_file": str(report_file.resolve()),
        "translated_report_file": str((output_dir / "complete_report_zh.md").resolve()) if translated_report else None,
        "translation_error_log": str((output_dir / "translation_error.log").resolve())
        if (output_dir / "translation_error.log").exists()
        else None,
    }
    write_result_json(args.result_json, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
