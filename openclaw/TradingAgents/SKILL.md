---
name: tradingagents
description: Run TradingAgents locally to analyze a stock and return the generated report.
user-invocable: true
---

# TradingAgents

Use this skill when the user asks for a stock analysis report and the local TradingAgents workspace is available.

## Workspace

`G:\AI\TradingAgents-new\TradingAgents`

## Command

Direct single run:

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\run_tradingagents.cmd --ticker 9988.HK --date 2026-03-28 --provider ollama --quick-model gpt-oss:latest --deep-model glm-4.7-flash:latest
```

Scheduled OpenClaw run:

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\run_tradingagents_job.cmd openclaw\tasks\9988_hk_daily.json
```

## Behavior

1. Parse the JSON output from the command.
2. Read `report_file`.
3. If `translated_report_file` exists, prefer that as the user-facing report.
4. Summarize the report in the chat and cite the saved report path.

## Notes

- Use `run_tradingagents_job.cmd` plus a JSON task file for recurring OpenClaw jobs.
- Use `--analysts market,social,news,fundamentals` unless the user asks for a narrower scope.
- Use `--research-depth 1` for faster scheduled runs and `--research-depth 3` for more detailed runs.
- If the user wants only the raw saved report, return the output path without extra summarization.
- If the command fails, surface the error and suggest retrying with `--skip-translation` to isolate whether the failure is in report generation or translation.
