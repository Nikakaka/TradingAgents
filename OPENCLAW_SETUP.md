# OpenClaw 定时任务接入说明

当前仓库已经提供了适合 OpenClaw 调度的非交互入口，可以直接配置为定时分析任务。

## 可用入口

- `run_tradingagents.cmd`
  直接按命令行参数执行一次分析。
- `run_tradingagents_job.cmd`
  按单个 JSON 任务文件执行一次分析，适合单标的定时任务。
- `run_tradingagents_batch.cmd`
  按 JSON 数组批量执行多个分析任务，适合观察列表轮询。
- `generate_openclaw_watchlist.cmd`
  生成 OpenClaw 可直接使用的观察列表任务文件。
- `scripts/run_tradingagents.py`
  支持 `--config-file`、`--result-json`、动态日期占位等能力。
- `scripts/run_tradingagents_batch.py`
  支持批量执行、JSON 汇总、Markdown 日报和上一份报告结论对比。

## 单标的定时任务

推荐在 OpenClaw 中配置为：

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\run_tradingagents_job.cmd openclaw\tasks\9988_hk_daily.json
```

或者：

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\run_tradingagents_job.cmd openclaw\tasks\300750_sz_daily.json
```

## 观察列表批量任务

如果你希望一个定时任务同时分析多个标的，推荐使用：

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\run_tradingagents_batch.cmd openclaw\tasks\daily_watchlist.json --result-json results\openclaw\daily_watchlist_summary.json --result-markdown results\openclaw\daily_watchlist_summary.md
```

这样会同时生成：

- `results/openclaw/daily_watchlist_summary.json`
- `results/openclaw/daily_watchlist_summary.md`

其中 Markdown 日报会：

- 按买入、持有、卖出、其他、失败分组
- 展示股票中文名和 ticker
- 优先提取中文报告摘要
- 标注当前结论与上一份报告是否发生变化

## 任务文件格式

任务文件为 JSON，常用字段如下：

```json
{
  "ticker": "9988.HK",
  "analysis_date": "today",
  "analysts": "market,social,news,fundamentals",
  "research_depth": 1,
  "skip_translation": false,
  "result_json": "results/openclaw/9988_hk_daily.json"
}
```

`analysis_date` 支持动态占位：

- `today`
- `today-1`
- `today-2`
- `today+1`

## 生成观察列表

### 使用内置预设

当前内置预设有：

- `hk_internet`
- `cn_ev`
- `cn_ai`

示例：

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\generate_openclaw_watchlist.cmd hk_internet --output openclaw\tasks\hk_internet_daily.json
```

### 使用自定义股票池

可以直接传入逗号分隔的股票列表：

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\generate_openclaw_watchlist.cmd --tickers "9988.HK,300750.SZ,0700.HK" --output openclaw\tasks\custom_watchlist.json
```

也可以从文本文件读取，一行一个标的或公司名：

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\generate_openclaw_watchlist.cmd --tickers-file openclaw\tasks\my_watchlist.txt --output openclaw\tasks\my_watchlist.json
```

说明：

- 输入 ticker 时会直接使用规范化后的代码。
- 输入公司名时会尝试解析为当前支持的规范 ticker。
- 如果公司名存在歧义，例如“腾讯”或“宁德时代”，脚本会提示候选代码，请改用明确 ticker。

## Dry Run 验证

正式接入 OpenClaw 前，建议先做 dry run：

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\run_tradingagents_job.cmd openclaw\tasks\9988_hk_daily.json --dry-run
```

批量任务也支持：

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\run_tradingagents_batch.cmd openclaw\tasks\daily_watchlist.json --dry-run --result-json results\openclaw\daily_watchlist_summary.json --result-markdown results\openclaw\daily_watchlist_summary.md
```

## 推荐默认配置

当前项目默认推荐配置：

- `provider = zhipu`
- `quick_model = GLM-4.5-Air`
- `deep_model = GLM-4.7`
- `research_depth = 1`

如果需要更快的定时轮询，也可以只启用部分分析团队，并跳过中文翻译。
