---
name: tradingagents
description: Run the local TradingAgents workspace to analyze a stock and return the saved report paths.
user-invocable: true
---

# TradingAgents Skill

Use this skill when the user asks for a stock analysis report and this workspace is available.

## Workspace

`G:\AI\TradingAgents-new\TradingAgents`

## Recommended command

For direct single-run invocation:

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\run_tradingagents.cmd --ticker 9988.HK --date 2026-03-28 --provider ollama --quick-model gpt-oss:latest --deep-model glm-4.7-flash:latest
```

For OpenClaw scheduled tasks, prefer the config-file runner:

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\run_tradingagents_job.cmd openclaw\tasks\9988_hk_daily.json
```

## Behavior

1. Parse the JSON output from the runner.
2. Read `report_file`.
3. If `translated_report_file` exists, prefer that file for the user-facing answer.
4. Summarize the final report and mention the saved file paths.

## Guardrails

- Keep ticker, date, model provider, and model names explicit.
- Do not use the interactive `python -m cli.main` flow from automation.
- For scheduled jobs, prefer `run_tradingagents_job.cmd` with a JSON task file.
- If the full run fails, retry once with `--analysts market --research-depth 1 --skip-translation` to isolate whether the issue is data, graph depth, or translation.
- If the user wants only the raw report, return the file paths without extra summarization.
