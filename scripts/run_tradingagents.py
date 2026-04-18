import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from cli.main import save_report_to_disk
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
        "--dry-run",
        action="store_true",
        help="Print the resolved configuration and exit without running analysis.",
    )
    parser.add_argument(
        "--position-quantity",
        type=float,
        default=None,
        help="Position quantity for portfolio context.",
    )
    parser.add_argument(
        "--position-cost",
        type=float,
        default=None,
        help="Position cost price for P&L calculation.",
    )
    parser.add_argument(
        "--position-value",
        type=float,
        default=None,
        help="Current position market value.",
    )
    parser.add_argument(
        "--position-pnl",
        type=float,
        default=None,
        help="Position profit/loss amount.",
    )
    parser.add_argument(
        "--position-pnl-pct",
        type=float,
        default=None,
        help="Position profit/loss percentage.",
    )
    return parser


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def parser_defaults() -> dict[str, Any]:
    defaults = vars(build_parser().parse_args([]))
    # Ensure position fields are included in defaults
    for key in ["position_quantity", "position_cost", "position_value", "position_pnl", "position_pnl_pct"]:
        if key not in defaults:
            defaults[key] = None
    return defaults


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

    # Handle position_info from config file
    if "position_info" in payload:
        pos_info = payload["position_info"]
        if isinstance(pos_info, dict):
            if "quantity" in pos_info and args.position_quantity is None:
                merged["position_quantity"] = pos_info["quantity"]
            if "cost_price" in pos_info and args.position_cost is None:
                merged["position_cost"] = pos_info["cost_price"]
            if "market_value" in pos_info and args.position_value is None:
                merged["position_value"] = pos_info["market_value"]
            if "profit_loss" in pos_info and args.position_pnl is None:
                merged["position_pnl"] = pos_info["profit_loss"]
            if "profit_loss_pct" in pos_info and args.position_pnl_pct is None:
                merged["position_pnl_pct"] = pos_info["profit_loss_pct"]

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

    # Increase recursion limit for deeper analysis
    # Each debate round adds approximately 50-100 recursion steps
    # depth=1 needs ~200, depth=2 needs ~350, depth=3 needs ~500+
    if args.research_depth >= 3:
        config["max_recur_limit"] = 800
    elif args.research_depth >= 2:
        config["max_recur_limit"] = 600
    else:
        config["max_recur_limit"] = 400

    return config


def write_result_json(result_json: str | None, payload: dict[str, Any]) -> None:
    if not result_json:
        return
    result_path = Path(result_json)
    if not result_path.is_absolute():
        result_path = (REPO_ROOT / result_path).resolve()
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    load_dotenv()
    args = apply_config_file(parse_args())
    args.analysis_date = resolve_analysis_date(args.analysis_date)
    analysts = parse_analysts(args.analysts)
    output_dir = build_output_dir(args.ticker, args.analysis_date, args.output_dir)
    config = build_config(args)

    # Build position info dict if available
    position_info = None
    if any([
        args.position_quantity is not None,
        args.position_cost is not None,
        args.position_value is not None,
        args.position_pnl is not None,
        args.position_pnl_pct is not None,
    ]):
        position_info = {
            "quantity": args.position_quantity,
            "cost_price": args.position_cost,
            "market_value": args.position_value,
            "profit_loss": args.position_pnl,
            "profit_loss_pct": args.position_pnl_pct,
        }

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
        "config_file": str(Path(args.config_file).resolve()) if args.config_file else None,
        "position_info": position_info,
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

    # 直接保存中文报告，无需翻译
    report_file = save_report_to_disk(
        final_state,
        args.ticker,
        output_dir,
    )

    result = {
        "status": "ok",
        **summary,
        "decision": decision,
        "report_file": str(report_file.resolve()),
    }
    write_result_json(args.result_json, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
