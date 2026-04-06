---
name: tradingagents
description: Run TradingAgents to analyze stocks and return investment reports.
user-invocable: true
---

# TradingAgents Skill

Use this skill to run stock analysis on the TradingAgents workspace.

## Workspace

`G:\AI\TradingAgents-new\TradingAgents`

## Commands

### Single Stock Analysis

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\run_tradingagents.cmd --ticker 9988.HK --date today --analysts market,social,news,fundamentals --research-depth 1
```

### Batch Analysis (Multiple Stocks)

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
.\run_tradingagents_batch.cmd openclaw\tasks\positions_morning.json --result-json results\openclaw\batch_summary.json
```

### Scheduled Position Analysis

**Morning Quick Analysis (depth=1, ~30 mins):**
```powershell
cd G:\AI\TradingAgents-new\TradingAgents; .\run_scheduled_job.cmd morning
```

**Evening Deep Analysis (depth=2, ~150 mins):**
```powershell
cd G:\AI\TradingAgents-new\TradingAgents; .\run_scheduled_job.cmd evening
```

**IMPORTANT: Use semicolon `;` instead of `&&` for command chaining in PowerShell.**

### Generate Position Tasks

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
python scripts\generate_position_tasks.py --depth 1 --output openclaw\tasks\positions_morning.json
python scripts\generate_position_tasks.py --depth 2 --output openclaw\tasks\positions_evening.json
```

### Regenerate Batch Summary from Existing Results

When individual stock analyses have been re-run and the batch summary is out of sync, regenerate it without re-running analysis:

```powershell
cd G:\AI\TradingAgents-new\TradingAgents
python scripts\run_tradingagents_batch.py openclaw\tasks\positions_evening.json --regenerate-summary --result-json results\openclaw\batch_regenerated.json
```

## Task Files

| File | Description |
|------|-------------|
| `openclaw/tasks/positions_morning.json` | Morning quick analysis (depth=1) |
| `openclaw/tasks/positions_evening.json` | Evening deep analysis (depth=2) |

## Scheduled Tasks

Two OpenClaw cron jobs are configured:

| Name | Schedule | Command |
|------|----------|---------|
| 早盘持仓分析 | 11:30 Mon-Fri | `run_scheduled_job.cmd morning` |
| 收盘持仓分析 | 16:30 Mon-Fri | `run_scheduled_job.cmd evening` |

## Decision Extraction

When parsing analysis results, the `decision` field in JSON contains the full LLM reasoning process. Extract the final rating from the **last non-empty line** or by looking for these patterns:

**5-Level Rating System (in order of conviction):**
| Rating | Chinese | Meaning |
|--------|---------|---------|
| BUY | 买入 | Strong buy recommendation |
| OVERWEIGHT | 增持 | Add to position |
| HOLD | 持有 | Maintain current position |
| UNDERWEIGHT | 减持 | Reduce position |
| SELL | 卖出 | Exit position |

**Extraction rules:**
1. Look for `Rating: **OVERWEIGHT**` or `RATING: HOLD` patterns
2. The last line of the decision field is usually the final rating
3. OVERWEIGHT/UNDERWEIGHT must be matched before BUY/SELL to avoid partial matches

## Behavior

1. Run the analysis command
2. Parse JSON output for `report_file` and `translated_report_file`
3. Read the report file
4. Summarize findings and cite saved paths

## Guardrails

- Keep ticker, date, and model parameters explicit
- For scheduled jobs, use `run_scheduled_job.cmd`
- If analysis fails, retry with `--analysts market --research-depth 1 --skip-translation`
- Return file paths for raw report requests

## Timeout Configuration

**CRITICAL: Batch analysis jobs require extended timeout.**

When running `run_scheduled_job.cmd` via exec tool, ALWAYS set timeout appropriately:

- **Morning (depth=1)**: timeout=9000 (2.5 hours)
- **Evening (depth=2)**: timeout=18000 (5 hours)

```json
// Morning analysis
{"command": "cd G:\\AI\\TradingAgents-new\\TradingAgents; .\\run_scheduled_job.cmd morning", "timeout": 9000}

// Evening analysis
{"command": "cd G:\\AI\\TradingAgents-new\\TradingAgents; .\\run_scheduled_job.cmd evening", "timeout": 18000}
```

**Expected execution times:**
- Morning (depth=1): 20-120 minutes for 12 stocks
- Evening (depth=2): 90-240 minutes for 12 stocks

## IMPORTANT: Always Execute Fresh Analysis

**When running scheduled jobs via cron, you MUST:**

1. **Execute the command and WAIT for completion** - Do NOT just read existing result files
2. **Verify new results were generated** - Check the timestamp in result filenames matches current time
3. **If execution time is too short**, something is wrong:
   - Morning: should take at least 5 minutes
   - Evening: should take at least 10 minutes
4. **Do NOT read cached results** - Always use fresh analysis results

## Exec Tool Configuration for Long-Running Commands

**CRITICAL: When using the exec tool for batch analysis, you MUST:**

1. **Use explicit timeout parameter**: `{"timeout": 18000}` for evening, `{"timeout": 9000}` for morning
2. **Wait for the command to fully complete** - Do NOT return early
3. **Check the result JSON timestamp** after completion to verify it's from the current run
4. **Read the result files** and summarize the analysis

**Example correct exec usage:**
```
Use exec tool with:
{
  "command": "cd G:\\AI\\TradingAgents-new\\TradingAgents; .\\run_scheduled_job.cmd evening",
  "timeout": 18000
}
```

Then WAIT for the command output showing "Completed with exit code: 0" and the result file paths.