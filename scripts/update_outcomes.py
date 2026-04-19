#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Update analysis outcomes with actual price changes.

This script updates historical analysis records with actual price outcomes
(5-day and 20-day price changes) for calibration purposes.

Usage:
    python scripts/update_outcomes.py --ticker 9988.HK --date 2024-01-15 --outcome-5d 0.05
    python scripts/update_outcomes.py --auto --days 30  # Auto-update analyses from last 30 days
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.agents.utils.analysis_memory import get_analysis_memory, get_calibration
from tradingagents.agents.utils.agent_utils import get_stock_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_price_change(ticker: str, start_date: str, days: int) -> float:
    """Calculate price change percentage after N trading days.

    Args:
        ticker: Stock ticker symbol
        start_date: Analysis date (YYYY-MM-DD)
        days: Number of trading days

    Returns:
        Price change as decimal (e.g., 0.05 for 5% gain)
    """
    try:
        # Get stock data
        result = get_stock_data(ticker)

        if isinstance(result, str) and "失败" in result:
            logger.error(f"Failed to get stock data for {ticker}: {result}")
            return 0.0

        if isinstance(result, dict):
            # Try to get price history
            history = result.get("history", [])
            if not history:
                logger.warning(f"No price history for {ticker}")
                return 0.0

            # Find the analysis date and calculate outcome
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")

            # Find entry closest to start_date
            start_price = None
            end_price = None
            end_dt = start_dt + timedelta(days=days * 2)  # Calendar days buffer

            for item in history:
                try:
                    item_date = datetime.strptime(item.get("Date", item.get("date", "")), "%Y-%m-%d")
                    price = item.get("Close", item.get("close", 0))

                    if start_price is None and item_date >= start_dt:
                        start_price = price

                    if start_price is not None:
                        trading_days_elapsed = sum(
                            1 for h in history
                            if start_dt <= datetime.strptime(h.get("Date", h.get("date", "")), "%Y-%m-%d") <= item_date
                        )
                        if trading_days_elapsed >= days:
                            end_price = price
                            break
                except (ValueError, TypeError):
                    continue

            if start_price and end_price and start_price > 0:
                return (end_price - start_price) / start_price

        return 0.0

    except Exception as e:
        logger.error(f"Error calculating price change: {e}")
        return 0.0


def update_single_outcome(ticker: str, date: str, outcome_5d: float = None, outcome_20d: float = None):
    """Update outcome for a single analysis record."""
    memory = get_analysis_memory()

    result = memory.update_outcome(
        ticker=ticker,
        analysis_date=date,
        outcome_5d=outcome_5d,
        outcome_20d=outcome_20d,
    )

    if result:
        logger.info(f"Updated: {ticker} {date} - 5d={outcome_5d}, 20d={outcome_20d}, correct={result.was_correct}")
    else:
        logger.warning(f"Record not found: {ticker} {date}")

    return result


def auto_update_outcomes(days: int = 30):
    """Automatically update outcomes for analyses from the last N days.

    For each analysis record without outcome data, fetch current prices
    and calculate the price changes.
    """
    memory = get_analysis_memory()
    records = memory.get_recent_analyses(days=days)

    if not records:
        logger.info("No analyses found that need outcome updates")
        return

    logger.info(f"Found {len(records)} analyses to update")

    updated_count = 0
    for record in records:
        try:
            # Calculate days since analysis
            analysis_dt = datetime.strptime(record.analysis_date, "%Y-%m-%d")
            days_elapsed = (datetime.now() - analysis_dt).days

            # Only update if enough time has passed
            if days_elapsed < 5:
                logger.debug(f"Skipping {record.ticker} {record.analysis_date} - not enough days elapsed")
                continue

            # Calculate outcomes
            outcome_5d = get_price_change(record.ticker, record.analysis_date, 5)

            # Only calculate 20d outcome if enough time has passed
            outcome_20d = None
            if days_elapsed >= 20:
                outcome_20d = get_price_change(record.ticker, record.analysis_date, 20)

            # Update the record
            memory.update_outcome(
                ticker=record.ticker,
                analysis_date=record.analysis_date,
                outcome_5d=outcome_5d,
                outcome_20d=outcome_20d,
            )
            updated_count += 1
            logger.info(f"Updated {record.ticker} {record.analysis_date}: 5d={outcome_5d:.2%}, 20d={outcome_20d:.2% if outcome_20d else 'N/A'}")

        except Exception as e:
            logger.error(f"Failed to update {record.ticker} {record.analysis_date}: {e}")

    logger.info(f"Updated {updated_count}/{len(records)} analyses")


def show_stats():
    """Show memory statistics."""
    memory = get_analysis_memory()
    stats = memory.get_stats()

    print("\n=== 分析记忆统计 ===")
    print(f"总分析记录: {stats['total_analyses']}")
    print(f"有结果追踪: {stats['with_outcomes']}")
    print(f"判断正确数: {stats['overall_correct']}")

    print("\n按信号类型:")
    for signal, data in stats["by_signal"].items():
        accuracy = data["correct"] / data["with_outcome"] if data["with_outcome"] > 0 else 0
        print(f"  {signal}: 总数={data['total']}, 有结果={data['with_outcome']}, 正确率={accuracy:.1%}")


def show_calibration(ticker: str = None):
    """Show calibration information for a ticker."""
    calibration = get_calibration(ticker=ticker)

    print(f"\n=== 校准信息 {'(' + ticker + ')' if ticker else '(全局)'} ===")
    if calibration.calibrated:
        print(f"已校准: 是")
        print(f"校准因子: {calibration.calibration_factor:.2f}")
        print(f"样本数: {calibration.total_samples}")
        print(f"整体准确率: {calibration.accuracy:.1%}")
        print(f"买入准确率: {calibration.buy_accuracy:.1%}")
        print(f"卖出准确率: {calibration.sell_accuracy:.1%}")
        print(f"持有准确率: {calibration.hold_accuracy:.1%}")
    else:
        print(f"已校准: 否 (样本不足，需要至少5条有结果的记录)")
        print(f"当前样本数: {calibration.total_samples}")


def main():
    parser = argparse.ArgumentParser(
        description="Update analysis outcomes for calibration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update a single analysis with known outcome
  python scripts/update_outcomes.py --ticker 9988.HK --date 2024-01-15 --outcome-5d 0.05 --outcome-20d 0.08

  # Auto-update analyses from last 30 days
  python scripts/update_outcomes.py --auto --days 30

  # Show memory statistics
  python scripts/update_outcomes.py --stats

  # Show calibration for a ticker
  python scripts/update_outcomes.py --calibration --ticker 9988.HK
        """,
    )

    parser.add_argument("--ticker", help="Stock ticker symbol")
    parser.add_argument("--date", help="Analysis date (YYYY-MM-DD)")
    parser.add_argument("--outcome-5d", type=float, help="5-day price change (as decimal, e.g., 0.05 for 5%)")
    parser.add_argument("--outcome-20d", type=float, help="20-day price change (as decimal)")
    parser.add_argument("--auto", action="store_true", help="Auto-update recent analyses")
    parser.add_argument("--days", type=int, default=30, help="Days to look back for auto-update (default: 30)")
    parser.add_argument("--stats", action="store_true", help="Show memory statistics")
    parser.add_argument("--calibration", action="store_true", help="Show calibration information")

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    if args.calibration:
        show_calibration(args.ticker)
        return

    if args.auto:
        auto_update_outcomes(args.days)
        return

    if args.ticker and args.date:
        update_single_outcome(
            ticker=args.ticker,
            date=args.date,
            outcome_5d=args.outcome_5d,
            outcome_20d=args.outcome_20d,
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
