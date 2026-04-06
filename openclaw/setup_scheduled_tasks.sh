#!/bin/bash
# ============================================================
# OpenClaw Scheduled Tasks Setup Script for Linux/macOS
# ============================================================
#
# 此脚本设置 crontab 任务，在交易日自动运行持仓分析
# 早盘: 11:30 快速分析 (depth=1)
# 收盘: 16:30 深度分析 (depth=3)
#
# 配置文件: openclaw/config/scheduled_tasks.json
# 任务运行器: openclaw/run_task.py
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_EXE="${PYTHON_EXE:-python3}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================================"
echo "OpenClaw 定时任务设置"
echo "============================================================"
echo ""
echo "项目目录: $PROJECT_DIR"
echo ""

# 检查 Python
if ! command -v "$PYTHON_EXE" &> /dev/null; then
    echo -e "${RED}[ERROR] Python not found. Please ensure Python is installed.${NC}"
    exit 1
fi

# 检查配置文件
CONFIG_FILE="$PROJECT_DIR/openclaw/config/scheduled_tasks.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}[WARN] 配置文件不存在: $CONFIG_FILE${NC}"
    echo "[INFO] 使用默认配置"
fi

# 检查飞书配置
FEISHU_CONFIG="$PROJECT_DIR/config/feishu.json"
if [ -f "$FEISHU_CONFIG" ]; then
    echo -e "${GREEN}[OK] 找到飞书配置文件: $FEISHU_CONFIG${NC}"
else
    echo -e "${YELLOW}[INFO] 未找到飞书配置文件: $FEISHU_CONFIG${NC}"
    echo "[INFO] 请设置环境变量 FEISHU_WEBHOOK_URL 或创建 config/feishu.json"
    echo ""
fi

# 检查持仓文件
POSITIONS_FILE="$PROJECT_DIR/positions.txt"
if [ -f "$POSITIONS_FILE" ]; then
    echo -e "${GREEN}[OK] 找到持仓文件: $POSITIONS_FILE${NC}"
else
    echo -e "${YELLOW}[WARN] 未找到持仓文件: $POSITIONS_FILE${NC}"
    echo "[INFO] 请先运行 python scripts/quick_import.py 导入持仓"
    echo ""
fi

# 创建日志目录
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

echo ""
echo "设置 crontab 任务..."
echo ""

# 生成 crontab 条目
MORNING_CRON="30 11 * * 1-5 cd $PROJECT_DIR && $PYTHON_EXE openclaw/run_task.py --task morning >> $LOG_DIR/morning_analysis.log 2>&1"
EVENING_CRON="30 16 * * 1-5 cd $PROJECT_DIR && $PYTHON_EXE openclaw/run_task.py --task evening >> $LOG_DIR/evening_analysis.log 2>&1"

# 检查是否已有条目
EXISTING_MORNING=$(crontab -l 2>/dev/null | grep -F "run_task.py --task morning" || true)
EXISTING_EVENING=$(crontab -l 2>/dev/null | grep -F "run_task.py --task evening" || true)

if [ -n "$EXISTING_MORNING" ]; then
    echo -e "${YELLOW}[INFO] 早盘任务已存在，将更新${NC}"
    # 删除旧条目
    crontab -l 2>/dev/null | grep -v "run_task.py --task morning" | crontab - || true
fi

if [ -n "$EXISTING_EVENING" ]; then
    echo -e "${YELLOW}[INFO] 收盘任务已存在，将更新${NC}"
    # 删除旧条目
    crontab -l 2>/dev/null | grep -v "run_task.py --task evening" | crontab - || true
fi

# 添加新条目
(crontab -l 2>/dev/null; echo "$MORNING_CRON") | crontab -
(crontab -l 2>/dev/null; echo "$EVENING_CRON") | crontab -

echo -e "${GREEN}[OK] 早盘任务创建成功${NC}"
echo "    运行时间: 工作日 11:30"
echo "    研究深度: 1 (快速分析)"
echo "    日志文件: $LOG_DIR/morning_analysis.log"
echo ""

echo -e "${GREEN}[OK] 收盘任务创建成功${NC}"
echo "    运行时间: 工作日 16:30"
echo "    研究深度: 3 (深度分析)"
echo "    日志文件: $LOG_DIR/evening_analysis.log"
echo ""

echo "============================================================"
echo "设置完成"
echo "============================================================"
echo ""
echo "当前 crontab:"
crontab -l
echo ""
echo "管理任务:"
echo "  查看任务: crontab -l"
echo "  编辑任务: crontab -e"
echo "  删除所有: crontab -r"
echo ""
echo "手动运行测试:"
echo "  早盘分析: python openclaw/run_task.py --task morning"
echo "  收盘分析: python openclaw/run_task.py --task evening"
echo "  自定义深度: python openclaw/run_task.py --depth 2"
echo "  查看配置: python openclaw/run_task.py --list"
echo ""
echo "飞书通知配置:"
echo "  方式1: 设置环境变量 FEISHU_WEBHOOK_URL"
echo "  方式2: 创建文件 $PROJECT_DIR/config/feishu.json"
echo "         内容: {\"webhook_url\": \"https://open.feishu.cn/open-apis/bot/v2/hook/xxx\"}"
echo ""
