#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通达信持仓快速导出助手

这个脚本会：
1. 打开文件对话框让您选择导出的CSV文件
2. 自动解析并转换为TradingAgents需要的格式
3. 立即运行分析

使用方法：
1. 在通达信中导出持仓为CSV
2. 运行此脚本: python scripts\quick_import.py
3. 选择导出的CSV文件
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tkinter import Tk, filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

from tradingagents.brokers.position_parser import PositionParser


def quick_import():
    """快速导入并分析"""
    print("=" * 60)
    print("持仓快速导入")
    print("=" * 60)

    # Step 1: 选择文件
    print("\n[步骤1] 选择持仓文件...")
    print("支持格式: CSV, XLS, XLSX")
    print()

    if HAS_TKINTER:
        root = Tk()
        root.withdraw()
        root.call('wm', 'attributes', '.', '-topmost', True)

        file_path = filedialog.askopenfilename(
            title="选择持仓文件 (CSV/Excel)",
            filetypes=[
                ("所有支持的格式", "*.csv *.xlsx *.xls"),
                ("CSV文件", "*.csv"),
                ("Excel文件", "*.xlsx *.xls"),
                ("所有文件", "*.*")
            ],
            initialdir=r"G:\Finance\持仓"  # 默认打开您的持仓目录
        )

        root.destroy()

        if not file_path:
            print("[INFO] 未选择文件，已退出")
            return

        print(f"[OK] 已选择文件: {file_path}")

    else:
        print("使用命令行模式，请输入文件路径：")
        file_path = input("CSV文件路径: ").strip().strip('"')
        if not file_path or not Path(file_path).exists():
            print("[ERROR] 文件不存在")
            return

    # Step 2: 解析持仓
    print("\n[步骤2] 解析持仓数据...")
    broker = PositionParser()

    try:
        positions = broker.get_positions_from_file(file_path)
        print(f"[OK] 解析成功，共 {len(positions.positions)} 个持仓")

        print("\n持仓明细:")
        print("-" * 60)
        for pos in sorted(positions.positions, key=lambda p: p.market_value, reverse=True):
            print(f"  {pos.symbol} {pos.name}")
            print(f"    数量: {pos.quantity:,}股  成本: {pos.cost_price:.3f}  现价: {pos.current_price:.3f}")
            print(f"    市值: {pos.market_value:,.0f}  盈亏: {pos.profit_loss_pct:+.2f}%")
        print("-" * 60)
        print(f"总市值: {positions.market_value:,.2f}")
        print(f"总盈亏: {positions.profit_loss:,.2f}")

    except Exception as e:
        print(f"[ERROR] 解析失败: {e}")
        return

    # Step 3: 复制到项目目录
    print("\n[步骤3] 复制到项目目录...")
    project_file = Path(__file__).parent.parent / "positions.csv"

    import shutil
    shutil.copy(file_path, project_file)
    print(f"[OK] 已复制到: {project_file}")

    # Step 4: 询问是否立即分析
    print("\n[步骤4] 运行分析？")
    choice = input("是否立即运行持仓分析? (Y/N): ").strip().lower()

    if choice == 'y':
        print("\n正在运行分析...")
        os.system(f'python scripts/auto_position_analysis.py --positions-file positions.csv --force')


def watch_folder():
    """监控文件夹，自动处理新文件"""
    print("=" * 60)
    print("文件夹监控模式")
    print("=" * 60)
    print("\n将通达信导出的CSV文件放到以下目录，脚本会自动处理：")
    print(f"  {Path(__file__).parent.parent}")
    print("\n按 Ctrl+C 退出监控\n")

    project_dir = Path(__file__).parent.parent
    processed_files = set()

    import time

    try:
        while True:
            for csv_file in project_dir.glob("*.csv"):
                if csv_file.name not in processed_files and "position" not in csv_file.name.lower():
                    print(f"\n[发现新文件] {csv_file}")
                    processed_files.add(csv_file.name)

                    try:
                        broker = PositionParser()
                        positions = broker.get_positions_from_file(str(csv_file))
                        print(f"[OK] 解析成功，{len(positions.positions)} 个持仓")

                        # 复制为默认文件
                        import shutil
                        shutil.copy(csv_file, project_dir / "positions.csv")
                        print(f"[OK] 已更新 positions.csv")

                        # 运行分析
                        os.system(f'python scripts/auto_position_analysis.py --positions-file positions.csv --force')

                    except Exception as e:
                        print(f"[ERROR] 处理失败: {e}")

            time.sleep(2)

    except KeyboardInterrupt:
        print("\n\n已退出监控")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="通达信持仓快速导入")
    parser.add_argument('--watch', action='store_true', help='监控文件夹模式')
    args = parser.parse_args()

    if args.watch:
        watch_folder()
    else:
        quick_import()
