# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

TradingAgents 是一个多智能体 LLM 金融交易框架，使用专业化智能体（分析师、研究员、交易员、风险经理）分析股票并做出交易决策。使用 LangGraph 进行智能体编排。

## 命令

<!-- AUTO-GENERATED: Commands -->
### 已安装命令

| 命令 | 说明 |
|---------|-------------|
| `tradingagents` | 启动交互式命令行界面 |
| `tradingagents-web` | 启动 Web 服务器 |

### 根目录脚本

| 命令 | 说明 |
|---------|-------------|
| `.\run_tradingagents.cmd --ticker 9988.HK --date today` | 运行单股票分析 |
| `.\run_tradingagents_batch.cmd <task-file.json>` | 从 JSON 任务文件运行批量分析 |
| `.\run_tradingagents_job.cmd <task-file.json>` | 从 JSON 配置运行单个任务 |
| `.\run_scheduled_job.cmd morning` | 早盘持仓分析 (depth=1) |
| `.\run_scheduled_job.cmd evening` | 收盘持仓分析 (depth=2) |
| `.\run_tradingagents_web.cmd` | 启动 Web 服务器 |

### Python 脚本

| 脚本 | 说明 |
|--------|-------------|
| `python scripts/run_tradingagents.py --ticker 9988.HK` | 主单股票运行器 |
| `python scripts/run_tradingagents_batch.py <tasks.json>` | 多股票批量运行器 |
| `python scripts/run_tradingagents_batch.py <tasks.json> --regenerate-summary` | 从现有结果重新生成摘要 |
| `python scripts/position_analysis.py analyze --positions-file positions.txt` | 统一持仓分析 CLI |
| `python scripts/generate_position_tasks.py --depth 1 --output tasks.json` | 生成 OpenClaw 任务文件 |
| `python scripts/send_feishu_notification.py --task morning --result results.json` | 发送飞书通知 |
| `python scripts/quick_import.py` | 从通达信导出快速导入持仓 |
| `python scripts/generate_openclaw_watchlist.py --tickers "0700.HK,9988.HK"` | 生成观察列表任务文件 |
| `python scripts/test_ifind_integration.py` | 测试同花顺 iFinD 数据源集成 |

### CLI 参数（run_tradingagents.py）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--ticker` | `9988.HK` | 股票代码 |
| `--date` | 今天 | 分析日期（支持 `today`、`today-1`、`YYYY-MM-DD`） |
| `--analysts` | `market,social,news,fundamentals` | 启用的分析师 |
| `--research-depth` | `1` | 研究辩论深度 (1-3) |
| `--provider` | 配置默认值 | LLM 提供商 |
| `--quick-model` | 配置默认值 | 快速任务模型 |
| `--deep-model` | 配置默认值 | 深度推理模型 |
| `--output-dir` | `reports/<ticker>_<date>_<timestamp>` | 输出目录 |
| `--result-json` | 无 | 结果 JSON 输出路径 |
| `--dry-run` | `false` | 仅打印配置不运行 |
| `--config-file` | 无 | 从 JSON 文件加载配置 |
| `--position-quantity` | 无 | 持仓数量 |
| `--position-cost` | 无 | 持仓成本价 |
| `--position-value` | 无 | 持仓市值 |
| `--position-pnl` | 无 | 持仓盈亏金额 |
| `--position-pnl-pct` | 无 | 持仓盈亏百分比 |

<!-- END AUTO-GENERATED -->

### 测试

```bash
python -m pytest tests/
python -m pytest tests/test_model_registry.py -v
```

### 安装

```bash
pip install .
pip install -e .  # 可编辑安装
```

## 环境变量

<!-- AUTO-GENERATED: Environment -->
所需 API 密钥（在 `.env` 中设置）：

### LLM 提供商（至少需要一个）

| 变量 | 必需 | 说明 |
|----------|----------|-------------|
| `OPENAI_API_KEY` | 否 | OpenAI GPT 模型 |
| `GOOGLE_API_KEY` | 否 | Google Gemini 模型 |
| `ANTHROPIC_API_KEY` | 否 | Anthropic Claude 模型 |
| `XAI_API_KEY` | 否 | xAI Grok 模型 |
| `ZHIPUAI_API_KEY` | 否 | 智谱AI (GLM) 模型 |
| `OPENROUTER_API_KEY` | 否 | OpenRouter API 网关 |

### 数据源

| 变量 | 必需 | 说明 |
|----------|----------|-------------|
| `ALPHA_VANTAGE_API_KEY` | 否 | Alpha Vantage 全球股票数据 |
| `IFIND_REFRESH_TOKEN` | 否 | 同花顺 iFinD 刷新令牌（付费数据源） |

### 通知与账户

| 变量 | 必需 | 说明 |
|----------|----------|-------------|
| `FEISHU_WEBHOOK_URL` | 否 | 飞书通知 Webhook |
| `TRADING_ACCOUNT_ID` | 否 | 交易账户标识符 |
<!-- END AUTO-GENERATED -->

## 架构

### 核心组件

```
tradingagents/
├── graph/
│   └── trading_graph.py    # 主编排类 (TradingAgentsGraph)
├── agents/
│   ├── analysts/           # 市场、新闻、情绪、基本面分析师
│   ├── researchers/        # 多头/空头研究员进行辩论
│   ├── trader/             # 交易决策智能体
│   ├── risk_mgmt/          # 风险辩论智能体
│   └── managers/           # 投资组合经理、研究经理
├── llm_clients/            # 多提供商 LLM 客户端 (OpenAI, Anthropic, Google, xAI, Ollama, 智谱AI)
├── dataflows/              # 数据供应商 (yfinance, akshare, sina, efinance, ifind, alpha_vantage)
├── brokers/                # 持仓文件解析器 (通达信, CSV, Excel 导出)
├── web_server.py           # Web 服务器
└── reporting.py            # 报告生成（支持中文）
```

### 数据源

| 数据源 | 类型 | 覆盖范围 | 说明 |
|--------|------|----------|------|
| 同花顺 iFinD | 行情、新闻、资金流向 | A股、港股 | 付费，数据最全面 |
| akshare | 行情、新闻 | A股、港股 | 免费，全面 |
| sina_finance | 实时行情 | A股 | 免费，无速率限制 |
| efinance_cn | 资金流向 | A股 | 东方财富，免费 |
| yfinance | 行情、新闻 | 全球股票 | 免费 |
| alpha_vantage | 行情 | 全球股票 | 免费 |

### 核心类

- **TradingAgentsGraph**：主入口点。`propagate(ticker, date)` 返回分析结果。
- **create_llm_client()**：支持多提供商的 LLM 客户端工厂。
- **DEFAULT_CONFIG**：模型、辩论轮数、数据供应商的配置。

### 数据流

1. 用户提供股票代码 + 日期
2. 分析师收集数据（市场、新闻、情绪、基本面）
3. 研究员辩论（多头 vs 空头）
4. 交易员提出交易提案
5. 风险管理评估
6. 投资组合经理做出最终决策

### 配置

`DEFAULT_CONFIG` 中的关键设置：
- `llm_provider`："openai"、"anthropic"、"google"、"xai"、"ollama"、"openrouter"、"zhipuai"
- `deep_think_llm` / `quick_think_llm`：复杂/快速任务的模型名称
- `max_debate_rounds`：研究辩论深度 (1-3)
- `data_vendors`：各类数据的数据源偏好

## OpenClaw 集成

通过 `openclaw cron` 配置定时任务：

```bash
openclaw cron list                                    # 查看任务
openclaw cron add --name "task" --cron "30 11 * * 1-5" --message "..."  # 添加任务
openclaw cron run <job-id>                            # 立即运行
```

`openclaw/tasks/*.json` 中的任务文件：
```json
{
  "ticker": "9988.HK",
  "analysis_date": "today",
  "analysts": "market,social,news,fundamentals",
  "research_depth": 1,
  "result_json": "results/openclaw/9988_hk.json"
}
```

## 持仓分析工作流

1. 导入持仓：`python scripts/quick_import.py`
2. 生成任务：`python scripts/generate_position_tasks.py --depth 1 --output openclaw/tasks/positions_morning.json`
3. 运行批量：`.\run_tradingagents_batch.cmd openclaw/tasks/positions_morning.json`
4. 结果保存到 `results/openclaw/` 和 `reports/`

## Web 界面

启动 Web 服务器：
```bash
python -m tradingagents.web_server
# 或
tradingagents-web
```

Web 界面功能：
- 单股票分析
- 批量分析
- 历史分析记录查看
- 实时进度显示
- 中文报告输出

## 重要文件

| 文件 | 说明 |
|------|-------------|
| `positions.txt` | 当前持仓（通达信导出格式，GBK 编码）- 不在 git 中 |
| `config/feishu.json` | 飞书 Webhook 配置 |
| `openclaw/tasks/*.json` | 分析任务文件 (positions_*.json 不在 git 中) |
| `.env` | 环境变量（不在 git 中） |
| `results/openclaw/` | 批量分析结果（不在 git 中） |
| `reports/` | 生成的报告（不在 git 中） |

## 报告输出

所有报告默认输出中文，包括：
- 市场分析报告
- 新闻分析报告
- 情绪分析报告
- 基本面分析报告
- 投资计划
- 最终交易决策
