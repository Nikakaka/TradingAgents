#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Position Analysis CLI - Unified entry point for position analysis workflow.

This script provides a unified interface for:
1. Importing positions from broker export files
2. Generating analysis tasks
3. Running analysis
4. Generating reports

Usage:
    # Analyze positions from a file
    python scripts/position_analysis.py analyze --positions-file positions.txt

    # Import and analyze (one command)
    python scripts/position_analysis.py import --file "G:\\Finance\\持仓\\持仓导出.txt" --analyze

    # Generate watchlist for specific stocks (not position-based)
    python scripts/position_analysis.py watchlist --tickers "0700.HK,9988.HK"

    # Quick import with file dialog
    python scripts/position_analysis.py quick-import

    # Schedule for daily analysis
    python scripts/position_analysis.py schedule --time 16:30
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from tradingagents.brokers.position_parser import PositionParser, AccountInfo
from tradingagents.default_config import DEFAULT_CONFIG


def print_summary_report(results_file: Path) -> None:
    """Print a concise summary report to terminal."""
    if not results_file.exists():
        print(f"[WARN] Results file not found: {results_file}")
        return

    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("\n" + "=" * 70)
    print("                    持仓分析结果汇总")
    print("=" * 70)
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"任务文件: {data.get('batch_file', 'N/A')}")
    print(f"分析状态: {data.get('status', 'unknown')}")

    counts = data.get("counts", {})
    print(f"\n结论统计:")
    print(f"  买入: {counts.get('buy', 0)}  |  持有: {counts.get('hold', 0)}  |  卖出: {counts.get('sell', 0)}  |  其他: {counts.get('other', 0)}  |  失败: {counts.get('failed', 0)}")

    print("\n" + "-" * 70)
    print(f"{'股票':<15} {'名称':<12} {'建议':<6} {'状态':<8} {'变化'}")
    print("-" * 70)

    # Sort by decision priority: SELL > BUY > HOLD > other > failed
    def sort_key(item):
        decision = str(item.get("decision", "")).upper()
        if "SELL" in decision:
            return (0, item.get("ticker", ""))
        elif "BUY" in decision:
            return (1, item.get("ticker", ""))
        elif "HOLD" in decision:
            return (2, item.get("ticker", ""))
        else:
            return (3, item.get("ticker", ""))

    results = data.get("results", [])
    for item in sorted(results, key=sort_key):
        ticker = item.get("ticker", "N/A")
        name = item.get("display_name", "")[:10] if item.get("display_name") else ""
        decision = str(item.get("decision", "N/A")).upper()
        status = item.get("status", "unknown")
        change = item.get("decision_change", "-")

        # Decision label
        if "BUY" in decision:
            decision_label = "买入"
        elif "SELL" in decision:
            decision_label = "卖出"
        elif "HOLD" in decision:
            decision_label = "持有"
        else:
            decision_label = decision[:6] if decision else "N/A"

        # Status label
        status_label = "成功" if status == "ok" else status[:6]

        print(f"{ticker:<15} {name:<12} {decision_label:<6} {status_label:<8} {change}")

    print("-" * 70)

    # Print report summary for each stock
    print("\n详细摘要:")
    print("=" * 70)
    for item in sorted(results, key=sort_key):
        ticker = item.get("ticker", "N/A")
        name = item.get("display_name", ticker)
        decision = str(item.get("decision", "N/A")).upper()
        summary = item.get("report_summary", "")

        if "BUY" in decision:
            icon = "📈"
        elif "SELL" in decision:
            icon = "📉"
        else:
            icon = "➡️"

        print(f"\n{icon} {name} ({ticker})")
        print(f"   建议: {decision}")
        if summary:
            print(f"   摘要: {summary}")
        if item.get("preferred_report_file"):
            print(f"   报告: {item['preferred_report_file']}")

    print("\n" + "=" * 70)
    print(f"完整报告: {results_file.with_suffix('.md')}")
    print(f"JSON结果: {results_file}")
    print("=" * 70 + "\n")


def summary_command(args: argparse.Namespace) -> int:
    """Show summary of existing analysis results."""
    results_dir = REPO_ROOT / "results" / "positions"

    if not results_dir.exists():
        print("[ERROR] No analysis results found. Run 'analyze' first.")
        return 1

    # Find the latest results file
    result_files = sorted(results_dir.glob("results_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)

    if not result_files:
        print("[ERROR] No analysis results found. Run 'analyze' first.")
        return 1

    if args.latest:
        result_file = result_files[0]
    elif args.file:
        result_file = Path(args.file)
        if not result_file.exists():
            print(f"[ERROR] File not found: {result_file}")
            return 1
    else:
        # Show list of available results
        print("Available analysis results:")
        print("-" * 50)
        for i, f in enumerate(result_files[:10], 1):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            print(f"  {i}. {f.name} ({mtime.strftime('%Y-%m-%d %H:%M')})")
        print("-" * 50)
        print("Use --latest to show the latest result, or --file <path> to specify.")
        return 0

    print(f"[INFO] Showing summary from: {result_file}")
    print_summary_report(result_file)
    return 0


def analyze_command(args: argparse.Namespace) -> int:
    """Analyze positions from file or API."""
    from tradingagents.brokers.position_parser import PositionParser

    broker = PositionParser(account_id=args.account_id or os.getenv("TRADING_ACCOUNT_ID", ""))

    # Load positions
    positions_file = args.positions_file or os.getenv("POSITIONS_FILE", "positions.txt")

    if positions_file and Path(positions_file).exists():
        print(f"[INFO] Loading positions from: {positions_file}")
        positions = broker.get_positions_from_file(positions_file)
    else:
        # Try default files
        default_files = [
            REPO_ROOT / "positions.txt",
            REPO_ROOT / "positions.csv",
            REPO_ROOT / "positions.xls",
            REPO_ROOT / "positions.xlsx",
        ]
        for f in default_files:
            if f.exists():
                print(f"[INFO] Loading positions from: {f}")
                positions = broker.get_positions_from_file(str(f))
                break
        else:
            print("[ERROR] No positions file found. Use --positions-file to specify one.")
            return 1

    if not positions.positions:
        print("[WARN] No positions found")
        return 0

    print(f"\n[INFO] Found {len(positions.positions)} positions")
    print(f"[INFO] Total market value: CNY {positions.market_value:,.2f}")

    # Filter out zero-quantity positions
    active_positions = [p for p in positions.positions if p.quantity > 0]
    if len(active_positions) < len(positions.positions):
        print(f"[INFO] Excluding {len(positions.positions) - len(active_positions)} positions with zero quantity")
        positions.positions = active_positions

    # Generate task file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_file = REPO_ROOT / "openclaw" / "tasks" / f"positions_{timestamp}.json"
    task_file.parent.mkdir(parents=True, exist_ok=True)

    broker.generate_analysis_tasks(
        positions=positions,
        output_path=str(task_file),
        analysts=args.analysts,
        research_depth=args.research_depth,
        provider=args.provider,
        quick_model=args.quick_model,
        deep_model=args.deep_model,
    )

    print(f"[INFO] Task file: {task_file}")

    # Run analysis
    if not args.dry_run:
        batch_script = REPO_ROOT / "scripts" / "run_tradingagents_batch.py"
        result_json = REPO_ROOT / "results" / "positions" / f"results_{timestamp}.json"
        result_md = REPO_ROOT / "results" / "positions" / f"report_{timestamp}.md"
        result_json.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            str(batch_script),
            str(task_file),
            "--result-json", str(result_json),
            "--result-markdown", str(result_md),
        ]

        if args.stop_on_error:
            cmd.append("--stop-on-error")

        print(f"\n[INFO] Running analysis for {len(positions.positions)} positions...")
        print(f"[INFO] This may take a while depending on the number of positions.")

        result = subprocess.run(cmd, cwd=str(REPO_ROOT))

        if result.returncode == 0:
            print(f"\n[DONE] Analysis complete!")
            print(f"  Results: {result_json}")
            print(f"  Report: {result_md}")

            # Print summary report
            print_summary_report(result_json)
        else:
            print(f"\n[ERROR] Analysis failed with code {result.returncode}")
            return 1
    else:
        print(f"\n[INFO] Dry run - task file generated but analysis not executed")

    return 0


def import_command(args: argparse.Namespace) -> int:
    """Import positions from broker export file."""
    import shutil

    broker = PositionParser(account_id=args.account_id or os.getenv("TRADING_ACCOUNT_ID", ""))

    if not args.file:
        # Try to find the latest export file
        export_dirs = [
            Path(r"G:\Finance\持仓"),
            Path.home() / "Downloads",
        ]

        export_files = []
        for d in export_dirs:
            if d.exists():
                for ext in ["*.txt", "*.csv", "*.xls", "*.xlsx"]:
                    export_files.extend(d.glob(ext))

        if export_files:
            export_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            args.file = str(export_files[0])
            print(f"[INFO] Found latest export: {args.file}")
        else:
            print("[ERROR] No export file found. Use --file to specify one.")
            return 1

    if not Path(args.file).exists():
        print(f"[ERROR] File not found: {args.file}")
        return 1

    # Parse positions
    print(f"[INFO] Importing positions from: {args.file}")
    positions = broker.get_positions_from_file(args.file)

    if not positions.positions:
        print("[ERROR] No positions found in file")
        return 1

    print(f"\n[SUCCESS] Imported {len(positions.positions)} positions")
    print(f"[INFO] Total market value: CNY {positions.market_value:,.2f}")

    # Print summary
    print("\nPositions:")
    print("-" * 80)
    print(f"{'Symbol':<12} {'Name':<15} {'Qty':>8} {'Cost':>10} {'Price':>10} {'Value':>12} {'P/L%':>8}")
    print("-" * 80)
    for pos in sorted(positions.positions, key=lambda p: p.market_value, reverse=True):
        print(f"{pos.symbol:<12} {pos.name:<15} {pos.quantity:>8,} {pos.cost_price:>10.3f} {pos.current_price:>10.3f} {pos.market_value:>12,.2f} {pos.profit_loss_pct:>7.2f}%")
    print("-" * 80)
    print(f"Total: CNY {positions.market_value:,.2f}")

    # Copy to project directory
    dest_file = REPO_ROOT / "positions.txt"
    shutil.copy(args.file, dest_file)
    print(f"\n[INFO] Copied to: {dest_file}")

    # Analyze if requested
    if args.analyze:
        print("\n[INFO] Starting analysis...")
        args.positions_file = str(dest_file)
        args.dry_run = False
        return analyze_command(args)

    return 0


def watchlist_command(args: argparse.Namespace) -> int:
    """Generate watchlist task file for OpenClaw."""
    # Import the existing function
    from scripts.generate_openclaw_watchlist import PRESETS, load_custom_symbols, build_tasks

    if args.preset:
        if args.preset not in PRESETS:
            print(f"[ERROR] Unknown preset: {args.preset}")
            print(f"[INFO] Available presets: {', '.join(PRESETS.keys())}")
            return 1
        items = PRESETS[args.preset]
        watchlist_name = args.preset
    elif args.tickers:
        items = load_custom_symbols(args)
        watchlist_name = "custom"
    elif args.from_positions:
        # Generate watchlist from current positions
        broker = PositionParser()
        positions_file = args.from_positions
        if not Path(positions_file).exists():
            positions_file = REPO_ROOT / "positions.txt"

        if not Path(positions_file).exists():
            print(f"[ERROR] Positions file not found: {positions_file}")
            return 1

        positions = broker.get_positions_from_file(str(positions_file))
        items = [{"ticker": p.symbol, "name": p.name} for p in positions.positions if p.quantity > 0]
        watchlist_name = "positions"
        print(f"[INFO] Generated watchlist from {len(items)} positions")
    else:
        print("[ERROR] Specify --preset, --tickers, or --from-positions")
        return 1

    # Build tasks
    tasks = []
    for item in items:
        task = {
            "ticker": item["ticker"],
            "analysis_date": args.analysis_date,
            "analysts": args.analysts,
            "research_depth": args.research_depth,
            "skip_translation": args.skip_translation,
            "result_json": f"results/openclaw/{item['ticker'].replace('.', '_').lower()}_{watchlist_name}.json",
        }
        if args.provider != DEFAULT_CONFIG.get("llm_provider"):
            task["provider"] = args.provider
        if args.quick_model != DEFAULT_CONFIG.get("quick_think_llm"):
            task["quick_model"] = args.quick_model
        if args.deep_model != DEFAULT_CONFIG.get("deep_think_llm"):
            task["deep_model"] = args.deep_model
        tasks.append(task)

    # Output
    output_path = Path(args.output) if args.output else REPO_ROOT / "openclaw" / "tasks" / f"{watchlist_name}.json"
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "watchlist": watchlist_name,
        "output": str(output_path),
        "task_count": len(tasks),
    }, ensure_ascii=False, indent=2))

    return 0


def quick_import_command(args: argparse.Namespace) -> int:
    """Quick import with file dialog."""
    try:
        from tkinter import Tk, filedialog
        HAS_TKINTER = True
    except ImportError:
        HAS_TKINTER = False

    if not HAS_TKINTER:
        print("[ERROR] tkinter not available. Use --file option instead.")
        return 1

    root = Tk()
    root.withdraw()
    root.call('wm', 'attributes', '.', '-topmost', True)

    file_path = filedialog.askopenfilename(
        title="Select Position Export File",
        filetypes=[
            ("All supported formats", "*.csv *.xlsx *.xls *.txt"),
            ("CSV files", "*.csv"),
            ("Excel files", "*.xlsx *.xls"),
            ("Text files", "*.txt"),
            ("All files", "*.*"),
        ],
        initialdir=r"G:\Finance\持仓" if Path(r"G:\Finance\持仓").exists() else str(Path.home()),
    )

    root.destroy()

    if not file_path:
        print("[INFO] No file selected")
        return 0

    # Call import command
    args.file = file_path
    args.analyze = args.analyze or False
    return import_command(args)


def schedule_command(args: argparse.Namespace) -> int:
    """Setup scheduled task for daily position analysis."""
    import platform

    system = platform.system()

    if system == "Windows":
        # Create Windows Task Scheduler task
        task_name = "TradingAgents_DailyPositionAnalysis"
        script_path = REPO_ROOT / "scripts" / "position_analysis.py"
        python_path = sys.executable

        # Create task command
        cmd = [
            "schtasks", "/create",
            "/tn", task_name,
            "/tr", f'"{python_path}" "{script_path}" analyze',
            "/sc", "daily",
            "/st", args.time or "16:30",
            "/f",  # Force overwrite if exists
        ]

        print(f"[INFO] Creating Windows scheduled task: {task_name}")
        print(f"[INFO] Command: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"[SUCCESS] Scheduled task created successfully")
            print(f"[INFO] Task will run daily at {args.time or '16:30'}")
            return 0
        else:
            print(f"[ERROR] Failed to create scheduled task: {result.stderr}")
            return 1

    else:
        # Create cron job for Linux/Mac
        cron_entry = f"{args.time or '16:30'} * * 1-5 {python_path} {script_path} analyze"

        print("[INFO] Add the following line to your crontab (crontab -e):")
        print(f"  {cron_entry}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TradingAgents Position Analysis CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze positions from file
  python scripts/position_analysis.py analyze --positions-file positions.txt

  # Import and analyze in one command
  python scripts/position_analysis.py import --file export.txt --analyze

  # Quick import with file dialog
  python scripts/position_analysis.py quick-import --analyze

  # Generate watchlist from positions
  python scripts/position_analysis.py watchlist --from-positions positions.txt

  # Setup daily scheduled analysis
  python scripts/position_analysis.py schedule --time 16:30
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze positions from file")
    analyze_parser.add_argument("--positions-file", help="Path to positions file")
    analyze_parser.add_argument("--account-id", help="Broker account ID")
    analyze_parser.add_argument("--analysts", default="market,social,news,fundamentals")
    analyze_parser.add_argument("--research-depth", type=int, default=1)
    analyze_parser.add_argument("--provider", default=DEFAULT_CONFIG.get("llm_provider", "jd"))
    analyze_parser.add_argument("--quick-model", default=DEFAULT_CONFIG.get("quick_think_llm", "MiniMax-M2.5"))
    analyze_parser.add_argument("--deep-model", default=DEFAULT_CONFIG.get("deep_think_llm", "GLM-5"))
    analyze_parser.add_argument("--dry-run", action="store_true", help="Generate tasks without running")
    analyze_parser.add_argument("--stop-on-error", action="store_true")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import positions from broker export")
    import_parser.add_argument("--file", help="Path to broker export file")
    import_parser.add_argument("--account-id", help="Broker account ID")
    import_parser.add_argument("--analyze", action="store_true", help="Run analysis after import")

    # Watchlist command
    watchlist_parser = subparsers.add_parser("watchlist", help="Generate OpenClaw watchlist")
    watchlist_parser.add_argument("--preset", choices=["hk_internet", "cn_ev", "cn_ai"], help="Preset watchlist")
    watchlist_parser.add_argument("--tickers", help="Comma-separated tickers")
    watchlist_parser.add_argument("--from-positions", help="Generate from positions file")
    watchlist_parser.add_argument("--output", help="Output JSON file path")
    watchlist_parser.add_argument("--analysts", default="market,social,news,fundamentals")
    watchlist_parser.add_argument("--research-depth", type=int, default=1)
    watchlist_parser.add_argument("--analysis-date", default="today")
    watchlist_parser.add_argument("--provider", default=DEFAULT_CONFIG.get("llm_provider", "jd"))
    watchlist_parser.add_argument("--quick-model", default=DEFAULT_CONFIG.get("quick_think_llm", "MiniMax-M2.5"))
    watchlist_parser.add_argument("--deep-model", default=DEFAULT_CONFIG.get("deep_think_llm", "GLM-5"))
    watchlist_parser.add_argument("--skip-translation", action="store_true")

    # Quick import command
    quick_parser = subparsers.add_parser("quick-import", help="Quick import with file dialog")
    quick_parser.add_argument("--analyze", action="store_true", help="Run analysis after import")

    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Setup scheduled analysis")
    schedule_parser.add_argument("--time", default="16:30", help="Time to run (HH:MM)")

    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Show summary of analysis results")
    summary_parser.add_argument("--latest", action="store_true", help="Show latest results")
    summary_parser.add_argument("--file", help="Path to specific results JSON file")

    args = parser.parse_args()

    if args.command == "analyze":
        return analyze_command(args)
    elif args.command == "import":
        return import_command(args)
    elif args.command == "watchlist":
        return watchlist_command(args)
    elif args.command == "summary":
        return summary_command(args)
    elif args.command == "quick-import":
        return quick_import_command(args)
    elif args.command == "schedule":
        return schedule_command(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
