#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Send Feishu notification for scheduled analysis results.

Usage:
    python scripts/send_feishu_notification.py --task morning --result results/openclaw/batch_xxx.json
    python scripts/send_feishu_notification.py --task evening --result results/openclaw/batch_xxx.json
"""

import argparse
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


def load_result_json(result_path: str) -> dict:
    """Load result JSON file."""
    path = Path(result_path)
    if not path.is_absolute():
        path = REPO_ROOT / path

    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_notification_content(result: dict, task_type: str) -> str:
    """Build Feishu notification content from result."""

    depth = 1 if task_type == "morning" else 3
    depth_label = "快速" if depth == 1 else "深度"

    lines = [
        f"**研究深度**: {depth} ({depth_label}分析)",
        "",
    ]

    # Summary counts
    counts = result.get("counts", {})
    if counts:
        lines.extend([
            "**分析结果**:",
            f"- 买入建议: {counts.get('buy', 0)} 只",
            f"- 持有建议: {counts.get('hold', 0)} 只",
            f"- 卖出建议: {counts.get('sell', 0)} 只",
            f"- 其他: {counts.get('other', 0)} 只",
            f"- 失败: {counts.get('failed', 0)} 只",
            "",
        ])

    # Position details from results
    results = result.get("results", [])
    if results:
        lines.append("**持仓详情**:")
        lines.append("| 代码 | 名称 | 建议 | 状态 |")
        lines.append("|------|------|------|------|")

        # Sort by decision
        decision_order = {"买入": 0, "卖出": 1, "持有": 2, "待定": 3, "失败": 4}
        sorted_results = sorted(
            results,
            key=lambda x: decision_order.get(x.get("decision", "待定"), 3)
        )

        for item in sorted_results:
            ticker = item.get("ticker", "-")
            name = item.get("display_name", ticker)[:8]
            decision = item.get("decision", "-")
            if decision and decision.upper() in ("BUY", "买入"):
                decision = "买入"
            elif decision and decision.upper() in ("SELL", "卖出"):
                decision = "卖出"
            elif decision and decision.upper() in ("HOLD", "持有"):
                decision = "持有"
            status = "✓" if item.get("status") == "ok" else "✗"
            lines.append(f"| {ticker} | {name} | {decision} | {status} |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Send Feishu notification for scheduled analysis")
    parser.add_argument("--task", required=True, choices=["morning", "evening"],
                        help="Task type (morning=depth1, evening=depth3)")
    parser.add_argument("--result", required=True, help="Path to result JSON file")
    parser.add_argument("--title", help="Custom notification title")
    args = parser.parse_args()

    webhook = get_feishu_webhook()
    if not webhook:
        print("[WARN] No Feishu webhook configured. Set FEISHU_WEBHOOK_URL or create config/feishu.json")
        return 0

    result = load_result_json(args.result)

    task_name = "早盘快速分析" if args.task == "morning" else "收盘深度分析"
    title = args.title or f"TradingAgents {task_name} - {datetime.now().strftime('%Y-%m-%d')}"

    content = build_notification_content(result, args.task)

    success = send_feishu_notification(webhook, title, content)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
