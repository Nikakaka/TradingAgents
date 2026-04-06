# OpenClaw 定时任务配置

本目录包含 OpenClaw 定时任务的配置和脚本。

## 目录结构

```
openclaw/
├── config/
│   └── scheduled_tasks.json     # 定时任务配置文件
├── tasks/
│   ├── positions_morning.json   # 早盘任务列表 (depth=1, 由脚本生成)
│   └── positions_evening.json   # 收盘任务列表 (depth=3, 由脚本生成)
├── run_task.py                  # 任务运行器 (Python 入口)
├── setup_scheduled_tasks.bat    # Windows 任务计划设置脚本
├── setup_scheduled_tasks.sh     # Linux/macOS crontab 设置脚本
└── README.md                    # 本文件
```

## 定时任务

| 任务名称 | 时间 | 研究深度 | 任务文件 |
|---------|------|---------|----------|
| morning_position_analysis | 工作日 11:30 | 1 (快速) | positions_morning.json |
| evening_position_analysis | 工作日 16:30 | 3 (深度) | positions_evening.json |

## 快速开始

### 1. 配置飞书通知

创建 `config/feishu.json` 文件：
```json
{
    "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_KEY"
}
```

或者设置环境变量：
```bash
# Windows
set FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_KEY

# Linux/macOS
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_KEY"
```

### 2. 更新持仓文件

将持仓导出到 `positions.txt`：
```bash
python scripts/quick_import.py
```

或手动从通达信导出持仓到 `positions.txt`。

### 3. 设置定时任务

**Windows:**
```powershell
# 以管理员身份运行
openclaw\setup_scheduled_tasks.bat
```

**Linux/macOS:**
```bash
chmod +x openclaw/setup_scheduled_tasks.sh
./openclaw/setup_scheduled_tasks.sh
```

### 4. 手动测试

```bash
# 早盘分析 (depth=1)
python openclaw/run_task.py --task morning --force

# 收盘分析 (depth=3)
python openclaw/run_task.py --task evening --force

# 自定义深度
python openclaw/run_task.py --depth 2 --force

# 查看配置的任务
python openclaw/run_task.py --list
```

### 5. 使用批处理脚本

```powershell
# 早盘分析
run_scheduled_job.cmd morning

# 收盘分析
run_scheduled_job.cmd evening
```

## 配置文件说明

### scheduled_tasks.json

```json
{
  "tasks": [
    {
      "name": "morning_position_analysis",
      "description": "早盘快速分析 - 工作日 11:30，研究深度 1",
      "schedule": "30 11 * * 1-5",
      "enabled": true,
      "command": "run_scheduled_job.cmd",
      "args": ["morning"],
      "task_file": "openclaw/tasks/positions_morning.json",
      "research_depth": 1
    }
  ],
  "holidays": ["2024-01-01", ...]
}
```

### 任务字段说明

| 字段 | 说明 |
|------|------|
| `name` | 任务名称 |
| `description` | 任务描述 |
| `schedule` | Cron 表达式 (分 时 日 月 周) |
| `enabled` | 是否启用 |
| `command` | 执行命令 |
| `args` | 命令参数 |
| `task_file` | 任务文件路径 |
| `research_depth` | 研究深度 (1=快速, 3=深度) |

## 工作流程

1. **定时触发**: Windows 任务计划或 crontab 在指定时间调用 `run_scheduled_job.cmd`
2. **更新任务**: 从 `positions.txt` 重新生成任务文件 (获取最新持仓和价格)
3. **执行分析**: 调用 `run_tradingagents_batch.py` 执行批量分析
4. **发送通知**: 将分析结果发送到飞书

## 相关文件

| 文件 | 说明 |
|------|------|
| `openclaw/config/scheduled_tasks.json` | 定时任务配置 |
| `openclaw/tasks/positions_morning.json` | 早盘分析任务 |
| `openclaw/tasks/positions_evening.json` | 收盘分析任务 |
| `run_scheduled_job.cmd` | 定时任务执行脚本 |
| `scripts/generate_position_tasks.py` | 任务文件生成脚本 |
| `scripts/run_tradingagents_batch.py` | 批量分析脚本 |
| `scripts/send_feishu_notification.py` | 飞书通知脚本 |

## 管理定时任务

### Windows

```powershell
# 查看任务
schtasks /query /tn "OpenClaw_MorningAnalysis"

# 立即运行
schtasks /run /tn "OpenClaw_MorningAnalysis"

# 删除任务
schtasks /delete /tn "OpenClaw_MorningAnalysis" /f

# 查看所有 OpenClaw 任务
schtasks /query | findstr OpenClaw
```

### Linux/macOS

```bash
# 查看任务
crontab -l

# 编辑任务
crontab -e

# 删除所有任务
crontab -r

# 查看日志
tail -f logs/morning_analysis.log
tail -f logs/evening_analysis.log
```

## 交易日判断

脚本内置了中国股市的节假日列表 (2024-2026)，会自动跳过：
- 周末（周六、周日）
- 法定节假日（春节、国庆等）

可以使用 `--force` 参数强制运行。

## 故障排查

### 任务未运行

1. 检查任务是否正确创建
2. 检查 Python 路径是否正确
3. 查看日志文件是否有错误信息

### 飞书通知未发送

1. 检查 `config/feishu.json` 是否正确配置
2. 检查环境变量 `FEISHU_WEBHOOK_URL` 是否设置
3. 测试飞书 Webhook：
   ```bash
   curl -X POST "YOUR_WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -d '{"msg_type":"text","content":{"text":"测试消息"}}'
   ```

### 分析失败

1. 检查 `positions.txt` 是否存在且有有效内容
2. 检查数据源是否可用
3. 查看 `results/openclaw/` 目录下的分析结果文件
