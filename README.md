<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="./assets/wechat.png" target="_blank"><img alt="WeChat" src="https://img.shields.io/badge/WeChat-TauricResearch-brightgreen?logo=wechat&logoColor=white"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <br>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/Join_GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>

---

# TradingAgents: 多智能体 LLM 金融交易框架

## 新闻
- [2026-04] **TradingAgents v0.2.2** 发布，支持 GPT-5.4/Gemini 3.1/Claude 4.6 模型，新增五档评级体系、OpenAI Responses API、Anthropic effort 控制，以及跨平台稳定性优化。
- [2026-03] **TradingAgents v0.2.1** 发布，新增 Web 界面、同花顺 iFinD 数据源支持、中文报告输出。
- [2026-02] **TradingAgents v0.2.0** 发布，支持多 LLM 提供商（GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x），改进系统架构。
- [2026-01] **Trading-R1** [技术报告](https://arxiv.org/abs/2509.11420) 发布，[Terminal](https://github.com/TauricResearch/Trading-R1) 即将上线。

<div align="center">
<a href="https://www.star-history.com/#TauricResearch/TradingAgents&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" />
   <img alt="TradingAgents Star History" src="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" style="width: 80%; height: auto;" />
 </picture>
</a>
</div>

> 🎉 **TradingAgents** 正式发布！我们收到了大量关于这项工作的咨询，感谢社区的热情支持。
>
> 因此我们决定完全开源这个框架。期待与您共同构建有影响力的项目！

<div align="center">

🚀 [TradingAgents 框架](#tradingagents-框架) | ⚡ [安装与命令行](#安装与命令行) | 🎬 [演示](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [包使用](#tradingagents-包使用) | 🌐 [Web 界面](#web-界面) | 🤝 [贡献](#贡献) | 📄 [引用](#引用)

</div>

## TradingAgents 框架

TradingAgents 是一个多智能体交易框架，模拟真实交易公司的运作方式。通过部署专业化的 LLM 智能体：从基本面分析师、情绪分析师、技术分析师，到交易员、风险管理团队，平台协作评估市场状况并指导交易决策。此外，这些智能体进行动态讨论以确定最优策略。

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents 框架设计用于研究目的。交易表现可能因多种因素而异，包括所选的骨干语言模型、模型温度、交易周期、数据质量和其他非确定性因素。[这不是财务、投资或交易建议。](https://tauric.ai/disclaimer/)

我们的框架将复杂的交易任务分解为专业角色。这确保系统实现稳健、可扩展的市场分析和决策方法。

### 分析师团队
- **基本面分析师**：评估公司财务和业绩指标，识别内在价值和潜在风险信号。
- **情绪分析师**：使用情绪评分算法分析社交媒体和公众情绪，衡量短期市场情绪。
- **新闻分析师**：监控全球新闻和宏观经济指标，解读事件对市场状况的影响。
- **技术分析师**：利用技术指标（如 MACD 和 RSI）检测交易模式并预测价格走势。

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### 研究员团队
- 由多头和空头研究员组成，他们批判性评估分析师团队提供的见解。通过结构化辩论，他们平衡潜在收益与固有风险。

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### 交易员智能体
- 综合分析师和研究员的报告做出明智的交易决策。根据全面的市场见解确定交易的时机和规模。

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### 风险管理与投资组合经理
- 持续评估投资组合风险，评估市场波动性、流动性和其他风险因素。风险管理团队评估并调整交易策略，向投资组合经理提供评估报告以供最终决策。
- 投资组合经理批准/拒绝交易提案。如果批准，订单将发送到模拟交易所并执行。

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## 安装与命令行

### 安装

克隆 TradingAgents：
```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

使用您喜欢的环境管理器创建虚拟环境：
```bash
conda create -n tradingagents python=3.13
conda activate tradingagents
```

安装包及其依赖：
```bash
pip install .
```

### 所需 API

TradingAgents 支持多个 LLM 提供商。为您选择的提供商设置 API 密钥：

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export ZHIPUAI_API_KEY=...         # 智谱AI (GLM)
export OPENROUTER_API_KEY=...      # OpenRouter
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
```

对于本地模型，在配置中设置 `llm_provider: "ollama"`。

或者，将 `.env.example` 复制到 `.env` 并填入您的密钥：
```bash
cp .env.example .env
```

### 命令行使用

启动交互式命令行：
```bash
tradingagents          # 已安装的命令
python -m cli.main     # 替代方案：直接从源码运行
```
您将看到一个界面，可以选择所需的股票代码、分析日期、LLM 提供商、研究深度等。

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

界面将显示加载中的结果，让您跟踪智能体运行时的进度。

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## Web 界面

TradingAgents 提供了 Web 界面，方便进行交互式分析：

```bash
# 启动 Web 服务器
tradingagents-web
# 或
python -m tradingagents.web_server
```

Web 界面功能：
- 单股票分析
- 批量分析
- 历史分析记录查看
- 实时进度显示
- 中文报告输出

## TradingAgents 包使用

### 实现细节

我们使用 LangGraph 构建 TradingAgents 以确保灵活性和模块化。框架支持多个 LLM 提供商：OpenAI、Google、Anthropic、xAI、智谱AI、OpenRouter 和 Ollama。

### Python 使用

要在代码中使用 TradingAgents，可以导入 `tradingagents` 模块并初始化 `TradingAgentsGraph()` 对象。`.propagate()` 函数将返回一个决策。您可以运行 `main.py`，这里也有一个快速示例：

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# 前向传播
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

您也可以调整默认配置来设置您选择的 LLM、辩论轮数等。

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # openai, google, anthropic, xai, openrouter, ollama
config["deep_think_llm"] = "gpt-5.2"     # 复杂推理模型
config["quick_think_llm"] = "gpt-5-mini" # 快速任务模型
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

参见 `tradingagents/default_config.py` 了解所有配置选项。

## 数据源

| 数据源 | 类型 | 覆盖范围 | 说明 |
|--------|------|----------|------|
| 同花顺 iFinD | 行情、新闻、资金流向 | A股、港股 | 付费，数据最全面 |
| akshare | 行情、新闻 | A股、港股 | 免费，全面 |
| sina_finance | 实时行情 | A股 | 免费，无速率限制 |
| efinance_cn | 资金流向 | A股 | 东方财富，免费 |
| yfinance | 行情、新闻 | 全球股票 | 免费 |
| alpha_vantage | 行情 | 全球股票 | 免费 |

## 贡献

我们欢迎社区贡献！无论是修复 bug、改进文档还是建议新功能，您的输入都有助于使这个项目更好。如果您对这一研究方向感兴趣，请考虑加入我们的开源金融 AI 研究社区 [Tauric Research](https://tauric.ai/)。

## 引用

如果 *TradingAgents* 对您有所帮助，请引用我们的工作 :)

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```
