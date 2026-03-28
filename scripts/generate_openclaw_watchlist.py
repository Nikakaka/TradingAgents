import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.market_utils import resolve_ticker_input, search_symbol_candidates

PRESETS = {
    "hk_internet": [
        {"ticker": "0700.HK", "name": "\u817e\u8baf\u63a7\u80a1"},
        {"ticker": "9988.HK", "name": "\u963f\u91cc\u5df4\u5df4-W"},
        {"ticker": "9618.HK", "name": "\u4eac\u4e1c\u96c6\u56e2-SW"},
        {"ticker": "3690.HK", "name": "\u7f8e\u56e2-W"},
        {"ticker": "1024.HK", "name": "\u5feb\u624b-W"},
    ],
    "cn_ev": [
        {"ticker": "300750.SZ", "name": "\u5b81\u5fb7\u65f6\u4ee3"},
        {"ticker": "002594.SZ", "name": "\u6bd4\u4e9a\u8fea"},
        {"ticker": "300014.SZ", "name": "\u4ebf\u7eac\u9502\u80fd"},
        {"ticker": "688223.SH", "name": "\u6676\u79d1\u80fd\u6e90"},
        {"ticker": "300274.SZ", "name": "\u9633\u5149\u7535\u6e90"},
    ],
    "cn_ai": [
        {"ticker": "300308.SZ", "name": "\u4e2d\u9645\u65ed\u521b"},
        {"ticker": "603019.SH", "name": "\u4e2d\u79d1\u66d9\u5149"},
        {"ticker": "688256.SH", "name": "\u5bd2\u6b66\u7eaa"},
        {"ticker": "002230.SZ", "name": "\u79d1\u5927\u8baf\u98de"},
        {"ticker": "300502.SZ", "name": "\u65b0\u6613\u76db"},
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an OpenClaw batch watchlist file for TradingAgents."
    )
    parser.add_argument(
        "preset",
        nargs="?",
        choices=sorted(PRESETS.keys()),
        help="Preset watchlist name.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path. Defaults to openclaw/tasks/<preset>.json",
    )
    parser.add_argument(
        "--tickers",
        default="",
        help="Comma-separated custom tickers or company names.",
    )
    parser.add_argument(
        "--tickers-file",
        default=None,
        help="Text file with one ticker/company name per line.",
    )
    parser.add_argument("--provider", default=DEFAULT_CONFIG["llm_provider"], help="LLM provider.")
    parser.add_argument("--quick-model", default=DEFAULT_CONFIG["quick_think_llm"], help="Quick model.")
    parser.add_argument("--deep-model", default=DEFAULT_CONFIG["deep_think_llm"], help="Deep model.")
    parser.add_argument("--backend-url", default=DEFAULT_CONFIG["backend_url"], help="Provider backend URL.")
    parser.add_argument("--research-depth", type=int, default=1, help="Research depth.")
    parser.add_argument("--analysts", default="market,social,news,fundamentals", help="Comma-separated analysts.")
    parser.add_argument("--analysis-date", default="today", help="Analysis date or dynamic token.")
    parser.add_argument("--skip-translation", action="store_true", help="Skip translation.")
    return parser.parse_args()


def load_custom_symbols(args: argparse.Namespace) -> list[dict]:
    raw_values: list[str] = []
    if args.tickers:
        raw_values.extend(item.strip() for item in args.tickers.split(",") if item.strip())

    if args.tickers_file:
        ticker_file = Path(args.tickers_file)
        if not ticker_file.is_absolute():
            ticker_file = (REPO_ROOT / ticker_file).resolve()
        if not ticker_file.exists():
            raise FileNotFoundError(f"Ticker list file not found: {ticker_file}")

        for line in ticker_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            raw_values.append(stripped)

    symbols = []
    seen = set()
    for item in raw_values:
        ticker = resolve_ticker_input(item)
        if ticker == item:
            candidates = search_symbol_candidates(item, limit=5)
            if len(candidates) == 1:
                ticker = str(candidates[0]["canonical_ticker"])
            elif len(candidates) > 1:
                choices = ", ".join(str(candidate["canonical_ticker"]) for candidate in candidates[:3])
                raise ValueError(
                    f"Ambiguous symbol input '{item}'. Please use an explicit ticker. Candidates: {choices}"
                )
        if ticker not in seen:
            symbols.append({"ticker": ticker, "name": item})
            seen.add(ticker)
    return symbols


def build_slug(source_name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", source_name.strip()).strip("_").lower()
    return slug or "custom_watchlist"


def resolve_watchlist_items(args: argparse.Namespace) -> tuple[str, list[dict]]:
    custom_items = load_custom_symbols(args)
    if custom_items:
        source_name = build_slug(Path(args.tickers_file).stem if args.tickers_file else "custom_watchlist")
        return source_name, custom_items
    if args.preset:
        return args.preset, PRESETS[args.preset]
    raise ValueError("Please provide a preset or custom symbols via --tickers / --tickers-file.")


def build_tasks(args: argparse.Namespace) -> list[dict]:
    watchlist_name, watchlist_items = resolve_watchlist_items(args)
    tasks = []
    for item in watchlist_items:
        ticker = item["ticker"]
        task = {
            "ticker": ticker,
            "analysis_date": args.analysis_date,
            "analysts": args.analysts,
            "research_depth": args.research_depth,
            "skip_translation": args.skip_translation,
            "result_json": f"results/openclaw/{ticker.replace('.', '_').lower()}_{watchlist_name}.json",
        }
        if args.provider != DEFAULT_CONFIG["llm_provider"]:
            task["provider"] = args.provider
        if args.quick_model != DEFAULT_CONFIG["quick_think_llm"]:
            task["quick_model"] = args.quick_model
        if args.deep_model != DEFAULT_CONFIG["deep_think_llm"]:
            task["deep_model"] = args.deep_model
        if args.backend_url != DEFAULT_CONFIG["backend_url"]:
            task["backend_url"] = args.backend_url
        tasks.append(task)
    return tasks


def main() -> int:
    args = parse_args()
    watchlist_name, _ = resolve_watchlist_items(args)
    output_path = Path(args.output) if args.output else Path("openclaw") / "tasks" / f"{watchlist_name}.json"
    if not output_path.is_absolute():
        output_path = (REPO_ROOT / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_tasks(args)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "watchlist": watchlist_name,
                "output": str(output_path),
                "task_count": len(payload),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
