#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OpenClaw Task Runner - 用于定时任务调用的统一入口

这个脚本是 OpenClaw cron 系统的统一入口点：
1. 从 positions.txt 读取持仓
2. 生成任务文件
3. 执行批量分析
4. 发送飞书通知

使用方法:
    python openclaw/run_task.py --task morning   # 早盘快速分析 (depth=1)
    python openclaw/run_task.py --task evening   # 收盘深度分析 (depth=3)
    python openclaw/run_task.py --depth 2        # 自定义深度
    python openclaw/run_task.py --task morning --force  # 强制运行（忽略交易日检查）
"""

import argparse
import json
import os
import subprocess
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


def load_scheduled_tasks_config() -> dict:
    """Load scheduled tasks configuration."""
    config_path = REPO_ROOT / "openclaw" / "config" / "scheduled_tasks.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tasks": [], "holidays": []}


def is_trading_day(date: datetime, holidays: list[str]) -> bool:
    """Check if the given date is a trading day."""
    # Weekend check
    if date.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    # Holiday check
    if date.strftime("%Y-%m-%d") in holidays:
        return False

    return True


def get_feishu_webhook() -> str | None:
    """Get Feishu webhook URL from environment or config."""
    webhook = os.getenv("FEISHU_WEBHOOK_URL") or os.getenv("FEISHU_WEBHOOK")
    if not webhook:
        config_file = REPO_ROOT / "config" / "feishu.json"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    webhook = config.get("webhook_url")
            except Exception:
                pass
    return webhook


def send_feishu_notification(webhook_url: str, title: str, content: str) -> bool:
    """Send notification to Feishu via webhook."""
    if not webhook_url:
        print("[WARN] No Feishu webhook URL configured. Skipping notification.")
        return False

    import httpx

    message = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": content
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                }
            ]
        }
    }

    try:
        response = httpx.post(webhook_url, json=message, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get("StatusCode") == 0 or result.get("code") == 0:
            print(f"[OK] Feishu notification sent successfully")
            return True
        else:
            print(f"[ERROR] Feishu API error: {result}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to send Feishu notification: {e}")
        return False


def build_notification_content(positions_info: dict, results: dict, research_depth: int) -> str:
    """Build Feishu notification content from analysis results."""

    lines = [
        f"**研究深度**: {research_depth}",
        f"**持仓数量**: {positions_info.get('position_count', 0)} 只",
        f"**总市值**: CNY {positions_info.get('market_value', 0):,.2f}",
        "",
    ]

    # Summary counts
    counts = {"buy": 0, "hold": 0, "sell": 0, "other": 0, "failed": 0}
    if "results" in results:
        for item in results["results"]:
            decision = str(item.get("decision", "")).upper()
            if "BUY" in decision:
                counts["buy"] += 1
            elif "SELL" in decision:
                counts["sell"] += 1
            elif "HOLD" in decision:
                counts["hold"] += 1
            elif item.get("status") != "ok":
                counts["failed"] += 1
            else:
                counts["other"] += 1

    lines.extend([
        "**分析结果**:",
        f"- 买入建议: {counts['buy']} 只",
        f"- 持有建议: {counts['hold']} 只",
        f"- 卖出建议: {counts['sell']} 只",
        "",
    ])

    # Position details
    if "positions" in positions_info:
        lines.append("**持仓详情**:")
        lines.append("| 代码 | 名称 | 数量 | 盈亏% | 建议 |")
        lines.append("|------|------|------|-------|------|")

        sorted_positions = sorted(
            positions_info["positions"],
            key=lambda p: p.get("profit_loss_pct", 0),
            reverse=True
        )

        decision_map = {}
        if "results" in results:
            for item in results["results"]:
                ticker = item.get("ticker", "")
                decision = str(item.get("decision", "")).upper()
                if "BUY" in decision:
                    decision_map[ticker] = "买入"
                elif "SELL" in decision:
                    decision_map[ticker] = "卖出"
                elif "HOLD" in decision:
                    decision_map[ticker] = "持有"
                else:
                    decision_map[ticker] = "待定"

        for pos in sorted_positions:
            ticker = pos.get("symbol", "")
            decision = decision_map.get(ticker, "-")
            name = pos.get("name", "")[:6]
            quantity = pos.get("quantity", 0)
            pnl_pct = pos.get("profit_loss_pct", 0)
            lines.append(f"| {ticker} | {name} | {quantity:,} | {pnl_pct:+.1f}% | {decision} |")

    return "\n".join(lines)


def run_task(task_name: str, research_depth: int, force: bool = False, no_notify: bool = False) -> int:
    """Run a scheduled task."""

    config = load_scheduled_tasks_config()
    holidays = config.get("holidays", [])

    print("=" * 60)
    print(f"OpenClaw Task Runner - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Task: {task_name}, Depth: {research_depth}")
    print("=" * 60)

    # Check trading day
    if not force and not is_trading_day(datetime.now(), holidays):
        print("[INFO] Not a trading day. Skipping analysis.")
        return 0

    # Step 1: Generate task file
    print("\n[STEP 1] Generating task file...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_file = REPO_ROOT / "openclaw" / "tasks" / f"positions_{timestamp}.json"

    generate_script = REPO_ROOT / "scripts" / "generate_position_tasks.py"
    generate_cmd = [
        sys.executable,
        str(generate_script),
        "--depth", str(research_depth),
        "--output", str(task_file),
    ]

    result = subprocess.run(generate_cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] Failed to generate task file: {result.stderr}")
        return 1

    if not task_file.exists():
        print(f"[ERROR] Task file not created: {task_file}")
        return 1

    print(f"[OK] Task file created: {task_file}")

    # Load task file to get position info
    with open(task_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    positions_info = {
        "position_count": len(tasks),
        "market_value": sum(t.get("position_info", {}).get("market_value", 0) for t in tasks),
        "positions": [t.get("position_info", {}) for t in tasks if t.get("position_info")],
    }
    for i, pos in enumerate(positions_info["positions"]):
        if "symbol" not in pos:
            pos["symbol"] = tasks[i].get("ticker", "")

    # Step 2: Run batch analysis
    print("\n[STEP 2] Running batch analysis...")
    result_json = REPO_ROOT / "results" / "openclaw" / f"batch_{timestamp}.json"
    result_md = REPO_ROOT / "results" / "openclaw" / f"report_{timestamp}.md"
    result_json.parent.mkdir(parents=True, exist_ok=True)

    batch_script = REPO_ROOT / "scripts" / "run_tradingagents_batch.py"
    batch_cmd = [
        sys.executable,
        str(batch_script),
        str(task_file),
        "--result-json", str(result_json),
        "--result-markdown", str(result_md),
    ]

    print(f"[INFO] Running: {' '.join(batch_cmd)}")
    result = subprocess.run(batch_cmd, cwd=str(REPO_ROOT))

    if result.returncode != 0:
        print(f"[ERROR] Batch analysis failed with code {result.returncode}")

    # Load results
    results = {"status": "ok", "results": []}
    if result_json.exists():
        with open(result_json, "r", encoding="utf-8") as f:
            results = json.load(f)

    # Step 3: Send notification
    if not no_notify:
        print("\n[STEP 3] Sending notification...")
        webhook = get_feishu_webhook()
        if webhook:
            depth_label = "深度" if research_depth >= 3 else "快速"
            title = f"TradingAgents 持仓分析 ({depth_label}分析) - {datetime.now().strftime('%Y-%m-%d')}"
            content = build_notification_content(positions_info, results, research_depth)
            send_feishu_notification(webhook, title, content)
        else:
            print("[WARN] No Feishu webhook configured. Set FEISHU_WEBHOOK_URL environment variable.")

    print("\n[INFO] Task completed")
    print(f"  Task file: {task_file}")
    print(f"  Result JSON: {result_json}")
    print(f"  Report: {result_md}")

    return 0


def list_tasks() -> int:
    """List all configured tasks."""
    config = load_scheduled_tasks_config()

    print("Configured Scheduled Tasks:")
    print("=" * 60)

    for task in config.get("tasks", []):
        status = "enabled" if task.get("enabled", True) else "disabled"
        print(f"\nTask: {task.get('name')}")
        print(f"  Description: {task.get('description')}")
        print(f"  Schedule: {task.get('schedule')}")
        print(f"  Command: {task.get('command')} {' '.join(task.get('args', []))}")
        print(f"  Status: {status}")

    print("\n" + "=" * 60)
    print(f"Holidays configured: {len(config.get('holidays', []))} days")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="OpenClaw Task Runner - Unified entry point for scheduled tasks"
    )
    parser.add_argument(
        "--task",
        choices=["morning", "evening"],
        help="Predefined task to run (morning=depth1, evening=depth3)"
    )
    parser.add_argument(
        "--depth",
        type=int,
        choices=[1, 2, 3],
        help="Research depth (1=quick, 2=medium, 3=deep)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force run even if not a trading day"
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Skip Feishu notification"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List configured tasks and exit"
    )
    args = parser.parse_args()

    if args.list:
        return list_tasks()

    # Determine research depth
    if args.task == "morning":
        research_depth = 1
    elif args.task == "evening":
        research_depth = 3
    elif args.depth:
        research_depth = args.depth
    else:
        print("[ERROR] Must specify --task or --depth")
        return 1

    task_name = args.task or f"depth{research_depth}"

    return run_task(
        task_name=task_name,
        research_depth=research_depth,
        force=args.force,
        no_notify=args.no_notify
    )


if __name__ == "__main__":
    raise SystemExit(main())
