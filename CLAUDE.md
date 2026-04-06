# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TradingAgents is a multi-agent LLM financial trading framework that uses specialized agents (analysts, researchers, traders, risk managers) to analyze stocks and make trading decisions. Built with LangGraph for agent orchestration.

<!-- AUTO-GENERATED: Commands -->
## Commands

### Root Level Commands

| Command | Description |
|---------|-------------|
| `.\run_tradingagents.cmd --ticker 9988.HK --date today` | Run single stock analysis |
| `.\run_tradingagents_batch.cmd <task-file.json>` | Run batch analysis from JSON task file |
| `.\run_tradingagents_job.cmd <task-file.json>` | Run single task from JSON config |
| `.\run_scheduled_job.cmd morning` | Morning position analysis (depth=1) |
| `.\run_scheduled_job.cmd evening` | Evening position analysis (depth=2) |

### Python Scripts

| Script | Description |
|--------|-------------|
| `python scripts/run_tradingagents.py --ticker 9988.HK` | Main single stock runner |
| `python scripts/run_tradingagents_batch.py <tasks.json>` | Batch runner for multiple stocks |
| `python scripts/run_tradingagents_batch.py <tasks.json> --regenerate-summary` | Regenerate summary from existing results |
| `python scripts/position_analysis.py analyze --positions-file positions.txt` | Unified position analysis CLI |
| `python scripts/generate_position_tasks.py --depth 1 --output tasks.json` | Generate OpenClaw task files |
| `python scripts/send_feishu_notification.py --task morning --result results.json` | Send Feishu notification |
| `python scripts/quick_import.py` | Quick import positions from TDX export |
| `python scripts/generate_openclaw_watchlist.py --tickers "0700.HK,9988.HK"` | Generate watchlist task file |

### Testing

```bash
python -m pytest tests/
python -m pytest tests/test_model_registry.py -v
```

### Installation

```bash
pip install .
pip install -e .  # Editable install
```
<!-- END AUTO-GENERATED -->

<!-- AUTO-GENERATED: Environment -->
## Environment Variables

Required API keys (set in `.env`):

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | No | OpenAI GPT models |
| `GOOGLE_API_KEY` | No | Google Gemini models |
| `ANTHROPIC_API_KEY` | No | Anthropic Claude models |
| `XAI_API_KEY` | No | xAI Grok models |
| `ZHIPUAI_API_KEY` | No | ZhipuAI (GLM) models |
| `OPENROUTER_API_KEY` | No | OpenRouter API gateway |
| `FEISHU_WEBHOOK_URL` | No | Feishu notifications |
| `TRADING_ACCOUNT_ID` | No | Trading account identifier |
| `ALPHA_VANTAGE_API_KEY` | No | Alpha Vantage data |

At least one LLM provider API key is required.
<!-- END AUTO-GENERATED -->

## Architecture

### Core Components

```
tradingagents/
├── graph/
│   └── trading_graph.py    # Main orchestration class (TradingAgentsGraph)
├── agents/
│   ├── analysts/           # Market, news, social, fundamentals analysts
│   ├── researchers/        # Bull/bear researchers for debate
│   ├── trader/             # Trading decision agent
│   ├── risk_mgmt/          # Risk debate agents
│   └── managers/           # Portfolio manager, research manager
├── llm_clients/            # Multi-provider LLM clients (OpenAI, Anthropic, Google, xAI, Ollama, ZhipuAI)
├── dataflows/              # Data vendors (yfinance, akshare, sina, efinance, alpha_vantage)
└── brokers/                # Position file parser (Tongdaxin, CSV, Excel exports)
```

### Data Sources

| Source | Type | Coverage |
|--------|------|-----------|
| yfinance | Market data, News | Global stocks |
| akshare | Market data, News | A-shares, HK stocks |
| sina_finance | Real-time quotes | A-shares |
| efinance_cn | Fund flows | A-shares |
| alpha_vantage | Market data | Global stocks |

### Key Classes

- **TradingAgentsGraph**: Main entry point. `propagate(ticker, date)` returns analysis results.
- **create_llm_client()**: Factory for LLM clients supporting multiple providers.
- **DEFAULT_CONFIG**: Configuration for models, debate rounds, data vendors.

### Data Flow

1. User provides ticker + date
2. Analysts gather data (market, news, social, fundamentals)
3. Researchers debate (bull vs bear)
4. Trader proposes transaction
5. Risk management evaluates
6. Portfolio manager makes final decision

### Configuration

Key settings in `DEFAULT_CONFIG`:
- `llm_provider`: "openai", "anthropic", "google", "xai", "ollama", "openrouter"
- `deep_think_llm` / `quick_think_llm`: Model names for complex/quick tasks
- `max_debate_rounds`: Research debate depth (1-3)
- `data_vendors`: Data source preferences per category

## OpenClaw Integration

Scheduled tasks are configured via `openclaw cron`:

```bash
openclaw cron list                                    # View tasks
openclaw cron add --name "task" --cron "30 11 * * 1-5" --message "..."  # Add task
openclaw cron run <job-id>                            # Run immediately
```

Task files in `openclaw/tasks/*.json`:
```json
{
  "ticker": "9988.HK",
  "analysis_date": "today",
  "analysts": "market,social,news,fundamentals",
  "research_depth": 1,
  "result_json": "results/openclaw/9988_hk.json"
}
```

## Position Analysis Workflow

1. Import positions: `python scripts/quick_import.py`
2. Generate tasks: `python scripts/generate_position_tasks.py --depth 1 --output openclaw/tasks/positions_morning.json`
3. Run batch: `.\run_tradingagents_batch.cmd openclaw/tasks/positions_morning.json`
4. Results saved to `results/openclaw/` and `reports/`

## Important Files

| File | Description |
|------|-------------|
| `positions.txt` | Current portfolio (TDX export format, GBK encoding) - not in git |
| `config/feishu.json` | Feishu webhook configuration |
| `openclaw/tasks/*.json` | Analysis task files (positions_*.json not in git) |
| `.env` | Environment variables (not in git) |
| `results/openclaw/` | Batch analysis results (not in git) |
| `reports/` | Generated reports (not in git) |
