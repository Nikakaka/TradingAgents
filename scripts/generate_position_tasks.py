#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate OpenClaw task files from current positions.

This script reads positions from positions.txt and generates task files
for scheduled analysis at different research depths.

Usage:
    python scripts/generate_position_tasks.py --depth 1 --output openclaw/tasks/positions_morning.json
    python scripts/generate_position_tasks.py --depth 3 --output openclaw/tasks/positions_evening.json
    python scripts/generate_position_tasks.py --positions-dir "G:/Finance/持仓" --depth 1 --output tasks.json
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from tradingagents.brokers.position_parser import PositionParser
from tradingagents.default_config import DEFAULT_CONFIG


def find_latest_positions_file(positions_dir: str) -> Path | None:
    """Find the most recent positions file in a directory.

    Looks for files matching patterns like:
    - *资金股份查询*.txt
    - *持仓*.txt
    - positions*.txt
    """
    dir_path = Path(positions_dir)
    if not dir_path.exists():
        return None

    # Common patterns for position files
    patterns = [
        "*资金股份查询*.txt",
        "*持仓*.txt",
        "positions*.txt",
        "*股份*.txt",
    ]

    candidates = []
    for pattern in patterns:
        candidates.extend(dir_path.glob(pattern))

    if not candidates:
        return None

    # Sort by modification time, return most recent
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def resolve_positions_file(
    positions_file: str | None,
    positions_dir: str | None,
    prefer_latest: bool = True
) -> Path | None:
    """Resolve the positions file to use.

    Priority:
    1. If positions_file is specified and exists, use it
    2. If positions_dir is specified, find latest file there
    3. Fall back to default positions.txt
    """
    # Explicit file specified
    if positions_file:
        path = Path(positions_file)
        if path.exists():
            return path
        # Try relative to repo root
        repo_path = REPO_ROOT / positions_file
        if repo_path.exists():
            return repo_path
        print(f"[WARN] Specified positions file not found: {positions_file}")

    # Directory specified - find latest file
    if positions_dir:
        latest = find_latest_positions_file(positions_dir)
        if latest:
            print(f"[INFO] Found latest positions file: {latest}")
            return latest
        print(f"[WARN] No positions file found in directory: {positions_dir}")

    # Default fallback
    default_path = REPO_ROOT / "positions.txt"
    if default_path.exists():
        return default_path

    return None


def generate_tasks(
    positions_file: str | None,
    output_file: str,
    research_depth: int = 1,
    positions_dir: str | None = None
) -> int:
    """Generate OpenClaw task file from positions."""

    # Load positions
    broker = PositionParser(account_id=os.getenv("TRADING_ACCOUNT_ID", ""))

    positions_path = resolve_positions_file(positions_file, positions_dir)

    if positions_path is None:
        print(f"[ERROR] No positions file found")
        print(f"  Searched: positions_file={positions_file}, positions_dir={positions_dir}, default=positions.txt")
        return 1

    print(f"[INFO] Loading positions from: {positions_path}")
    positions = broker.get_positions_from_file(str(positions_path))

    if not positions.positions:
        print("[ERROR] No positions found")
        return 1

    # Filter zero-quantity positions
    active_positions = [p for p in positions.positions if p.quantity > 0]
    print(f"[INFO] Found {len(active_positions)} active positions")

    # Generate tasks
    tasks = []
    for pos in active_positions:
        task = {
            "ticker": pos.symbol,
            "analysis_date": "today",
            "analysts": "market,social,news,fundamentals",
            "research_depth": research_depth,
            "skip_translation": False,
            "result_json": f"results/openclaw/{pos.symbol.replace('.', '_').lower()}_depth{research_depth}.json",
            "position_info": {
                "quantity": pos.quantity,
                "cost_price": pos.cost_price,
                "current_price": pos.current_price,
                "market_value": pos.market_value,
                "profit_loss": pos.profit_loss,
                "profit_loss_pct": pos.profit_loss_pct,
            }
        }
        tasks.append(task)

    # Write output
    output_path = Path(output_file)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

    print(f"[OK] Generated {len(tasks)} tasks")
    print(f"[OK] Output: {output_path}")

    # Print task summary
    print("\nTask Summary:")
    print("-" * 60)
    for task in tasks:
        ticker = task["ticker"]
        result = task["result_json"]
        print(f"  {ticker:<12} -> {result}")
    print("-" * 60)

    return 0


def main():
    parser = argparse.ArgumentParser(description="Generate OpenClaw task files from positions")
    parser.add_argument("--positions-file", default=None, help="Path to positions file (optional)")
    parser.add_argument("--positions-dir", default=None, help="Directory to search for latest positions file (optional)")
    parser.add_argument("--output", required=True, help="Output task file path")
    parser.add_argument("--depth", type=int, default=1, help="Research depth (1=quick, 2=medium, 3=deep)")
    args = parser.parse_args()

    return generate_tasks(args.positions_file, args.output, args.depth, args.positions_dir)


if __name__ == "__main__":
    raise SystemExit(main())
