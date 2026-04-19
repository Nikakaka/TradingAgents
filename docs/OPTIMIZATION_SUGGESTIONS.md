# TradingAgents 优化建议

基于对 `G:\AI\daily_stock_analysis` 项目的源码分析，整理以下可借鉴的架构设计与实现思路。

---

## 一、项目架构对比

| 维度 | TradingAgents (当前) | daily_stock_analysis |
|------|---------------------|---------------------|
| **智能体编排** | LangGraph 状态图 | 自研顺序管道 (Technical → Intel → Risk → Decision) |
| **策略定义** | 硬编码在 Python 中 | YAML 文件定义，支持热加载 |
| **数据源** | 单一供应商 + 配置优先级 | DataFetcherManager 自动故障转移 |
| **分析模式** | 单一模式 | quick/standard/full/specialist 四种模式 |
| **上下文传递** | 状态字典 | AgentContext 结构化对象 |
| **置信度校准** | 无 | 基于历史准确率的动态校准 |
| **超时控制** | 无 | 管道级 + 阶段级超时保护 |

---

## 二、核心可借鉴功能

### 1. YAML 技能系统 (高优先级)

**现状问题**: TradingAgents 的交易策略硬编码在 Python 代码中，添加新策略需要修改代码。

**借鉴方案**: 引入 YAML 定义的技能系统。

```yaml
# strategies/dragon_head.yaml (示例)
name: dragon_head
display_name: 龙头策略
description: 识别行业龙头股的强势突破信号
category: trend
core_rules: [1, 3, 5]
required_tools: [get_stock_data, get_technical_indicators]
instructions: |
  ## 龙头策略分析指南

  1. **识别龙头特征**
     - 市值排名行业前三
     - 近5日涨幅领跑行业
     - 成交量持续放大

  2. **入场条件**
     - 股价突破近20日高点
     - 量比 > 1.5
     - MACD 金叉确认

  3. **止损设置**
     - 跌破5日均线减仓
     - 跌破10日均线清仓
```

**实现要点**:
- `SkillManager` 加载 `strategies/*.yaml` 和 `strategies/*/SKILL.md`
- 自动生成技能提示词注入到分析师的系统提示中
- 支持用户自定义技能目录覆盖内置技能

**TradingAgents 改造路径**:
```
tradingagents/
├── strategies/              # 新增：策略定义目录
│   ├── trend_follow.yaml
│   ├── mean_reversion.yaml
│   └── custom/              # 用户自定义策略
├── skills/                  # 新增：技能管理模块
│   ├── __init__.py
│   ├── base.py              # Skill 数据类 + SkillManager
│   └── loader.py            # YAML/Markdown 加载器
└── agents/
    └── analysts/
        └── market_analyst.py  # 注入技能指令
```

---

### 2. 多模式分析管道 (高优先级)

**现状问题**: TradingAgents 缺少不同深度/成本的分析模式。

**借鉴方案**: 引入四种分析模式。

| 模式 | 管道流程 | LLM 调用数 | 适用场景 |
|------|---------|-----------|---------|
| `quick` | Technical → Decision | ~2 | 快速扫描、大盘股监控 |
| `standard` | Technical → Intel → Decision | ~3 | 日常分析（默认） |
| `full` | Technical → Intel → Risk → Decision | ~4 | 重点持仓、深度分析 |
| `specialist` | Technical → Intel → Risk → Skills → Decision | ~5+ | 特定策略评估 |

**实现要点**:
```python
class AnalysisMode(Enum):
    QUICK = "quick"           # 快速模式
    STANDARD = "standard"     # 标准模式（默认）
    FULL = "full"             # 完整模式
    SPECIALIST = "specialist" # 专家模式（带策略评估）

class TradingAgentsGraph:
    def __init__(self, mode: AnalysisMode = AnalysisMode.STANDARD):
        self.mode = mode
        self._build_pipeline()

    def _build_pipeline(self):
        if self.mode == AnalysisMode.QUICK:
            self.pipeline = ["market_analyst", "portfolio_manager"]
        elif self.mode == AnalysisMode.STANDARD:
            self.pipeline = ["market_analyst", "news_analyst", "portfolio_manager"]
        elif self.mode == AnalysisMode.FULL:
            self.pipeline = ["market_analyst", "news_analyst", "risk_manager", "portfolio_manager"]
        # ...
```

---

### 3. 数据源自动故障转移 (中优先级)

**现状问题**: 当首选数据源失败时，需要手动切换或报错。

**借鉴方案**: DataFetcherManager 自动故障转移。

```python
class DataFetcherManager:
    """优先级驱动的数据源管理器，自动故障转移。"""

    def __init__(self, priority_order: List[str]):
        self.fetchers: Dict[str, DataFetcher] = {}
        self.priority_order = priority_order

    async def fetch(self, data_type: str, **params) -> Optional[Dict]:
        """按优先级尝试数据源，返回首个成功结果。"""
        errors = []
        for source_name in self.priority_order:
            fetcher = self.fetchers.get(source_name)
            if not fetcher:
                continue
            try:
                result = await fetcher.fetch(data_type, **params)
                if result:
                    logger.info(f"[DataFetcher] {data_type} from {source_name}")
                    return result
            except Exception as e:
                errors.append(f"{source_name}: {e}")
                logger.warning(f"[DataFetcher] {source_name} failed: {e}")

        logger.error(f"[DataFetcher] All sources failed for {data_type}: {errors}")
        return None
```

**TradingAgents 改造路径**:
```python
# 在 default_config.py 中
"data_vendors": {
    "core_stock_apis": ["ifind", "efinance", "sina", "akshare", "yfinance"],
    "priority_order": {  # 新增：按数据类型的优先级
        "realtime_quote": ["sina", "efinance", "ifind"],
        "daily_history": ["akshare", "yfinance", "ifind"],
        "news": ["akshare", "ifind"],
    }
}
```

---

### 4. AgentContext 结构化上下文 (中优先级)

**现状问题**: 阶段间数据传递依赖松散的状态字典，缺乏类型约束。

**借鉴方案**: 引入 AgentContext 结构化对象。

```python
@dataclass
class AgentContext:
    """管道各阶段共享的分析上下文。"""

    # 基本信息
    query: str                           # 用户查询
    stock_code: str = ""                 # 股票代码
    stock_name: str = ""                 # 股票名称
    session_id: str = ""                 # 会话ID

    # 阶段产出
    opinions: List[AgentOpinion] = field(default_factory=list)  # 各阶段观点
    risk_flags: List[Dict[str, Any]] = field(default_factory=list)

    # 缓存数据
    data: Dict[str, Any] = field(default_factory=dict)  # 预取的数据
    meta: Dict[str, Any] = field(default_factory=dict)  # 元数据

    def add_opinion(self, opinion: AgentOpinion) -> None:
        """添加阶段观点。"""
        opinion.agent_name = opinion.agent_name or "unknown"
        self.opinions.append(opinion)

    def set_data(self, key: str, value: Any) -> None:
        """缓存数据供后续阶段使用。"""
        self.data[key] = value

    def get_data(self, key: str) -> Optional[Any]:
        """获取缓存数据。"""
        return self.data.get(key)

@dataclass
class AgentOpinion:
    """结构化的阶段分析观点。"""

    agent_name: str = ""
    signal: str = "hold"                 # buy/hold/sell
    confidence: float = 0.5              # 置信度 0-1
    reasoning: str = ""                  # 推理过程
    key_levels: Dict[str, float] = field(default_factory=dict)  # 关键价位
    raw_data: Dict[str, Any] = field(default_factory=dict)
```

**优势**:
- 类型安全，IDE 自动补全
- 明确的数据流向
- 便于调试和追踪

---

### 5. 置信度历史校准 (中优先级)

**现状问题**: 分析师的置信度依赖 LLM 主观判断，缺乏历史准确性反馈。

**借鉴方案**: 基于历史分析准确率的动态校准。

```python
class AgentMemory:
    """智能体记忆系统，存储历史分析并校准置信度。"""

    def get_calibration(
        self,
        agent_name: str,
        stock_code: Optional[str] = None,
        skill_id: Optional[str] = None,
    ) -> CalibrationResult:
        """获取历史校准因子。"""
        # 查询该智能体/股票/技能的历史准确率
        history = self._query_history(agent_name, stock_code, skill_id)

        if len(history) < 5:  # 样本不足
            return CalibrationResult(calibrated=False)

        accuracy = sum(h.was_correct for h in history) / len(history)

        # 校准因子：准确率越高，置信度压缩越少
        calibration_factor = accuracy / 0.5  # 以50%为基准

        return CalibrationResult(
            calibrated=True,
            calibration_factor=min(1.5, max(0.5, calibration_factor)),
            total_samples=len(history),
        )

    def record_outcome(
        self,
        agent_name: str,
        stock_code: str,
        date: str,
        signal: str,
        confidence: float,
        outcome_5d: Optional[float] = None,
        outcome_20d: Optional[float] = None,
    ) -> None:
        """记录分析结果，供后续校准使用。"""
        # 判断是否正确
        was_correct = self._evaluate_correctness(signal, outcome_5d, outcome_20d)
        # 存储到数据库/文件
        self._store(agent_name, stock_code, date, signal, confidence, was_correct)
```

**校准流程**:
1. 分析师产出 `opinion.confidence = 0.7`
2. 查询该分析师在该股票的历史准确率（如 60%）
3. 应用校准因子: `0.7 * (0.6 / 0.5) = 0.84` → 裁剪到 `0.7`
4. 存储本次分析，后续跟踪实际走势

---

### 6. 管道超时保护 (中优先级)

**现状问题**: 单次分析可能耗时过长，无超时保护。

**借鉴方案**: 管道级 + 阶段级超时保护。

```python
class AgentOrchestrator:
    def __init__(self, timeout_seconds: int = 0):
        self.timeout_seconds = timeout_seconds
        self._MIN_STAGE_BUDGET_S = 15  # 阶段最小预算

    def _execute_pipeline(self, ctx: AgentContext) -> OrchestratorResult:
        t0 = time.time()

        for agent in self.agents:
            elapsed = time.time() - t0
            remaining = self.timeout_seconds - elapsed if self.timeout_seconds else None

            # 超时检查
            if remaining is not None and remaining <= 0:
                logger.error(f"[Orchestrator] pipeline timed out")
                return self._build_timeout_result(ctx, elapsed)

            # 预算不足检查（跳过当前阶段）
            if remaining is not None and remaining < self._MIN_STAGE_BUDGET_S:
                logger.warning(f"[Orchestrator] insufficient budget, skip stage")
                return self._build_partial_result(ctx, elapsed)

            # 执行阶段
            result = agent.run(ctx, timeout_seconds=remaining)
            # ...
```

---

### 7. 工具注册表与访问控制 (低优先级)

**现状问题**: 所有智能体可访问所有工具，缺乏权限隔离。

**借鉴方案**: ToolRegistry + 按智能体过滤。

```python
class BaseAgent:
    tool_names: Optional[List[str]] = None  # None 表示可访问所有工具

    def _filtered_registry(self) -> ToolRegistry:
        """返回过滤后的工具注册表。"""
        if self.tool_names is None:
            return self.tool_registry

        filtered = ToolRegistry()
        for name in self.tool_names:
            tool_def = self.tool_registry.get(name)
            if tool_def:
                filtered.register(tool_def)
        return filtered

# 使用示例
class MarketAnalyst(BaseAgent):
    tool_names = ["get_stock_data", "get_technical_indicators", "get_news"]

class RiskManager(BaseAgent):
    tool_names = ["get_stock_data", "get_fundamental_data"]
```

---

### 8. 风控覆写机制 (低优先级)

**现状问题**: 风险管理建议可能被忽略。

**借鉴方案**: 风控智能体可强制下调最终决策。

```python
def _apply_risk_override(self, ctx: AgentContext) -> None:
    """应用风控覆写规则到最终决策。"""
    risk_opinion = next(
        (op for op in reversed(ctx.opinions) if op.agent_name == "risk"),
        None
    )
    if not risk_opinion:
        return

    risk_raw = risk_opinion.raw_data or {}
    adjustment = risk_raw.get("signal_adjustment", "").lower()

    current_signal = ctx.get_data("final_decision")
    new_signal = current_signal

    # 风控覆写逻辑
    if adjustment == "veto" and current_signal == "buy":
        new_signal = "hold"  # 禁止买入
    elif adjustment == "downgrade_one":
        new_signal = _downgrade_signal(current_signal, steps=1)
    elif adjustment == "downgrade_two":
        new_signal = _downgrade_signal(current_signal, steps=2)

    if new_signal != current_signal:
        ctx.set_data("final_decision", new_signal)
        ctx.set_data("risk_override", {
            "from": current_signal,
            "to": new_signal,
            "reason": risk_raw.get("reasoning", ""),
        })
```

---

## 三、实施建议

### 阶段一：基础架构优化 (1-2 周)

1. **引入 AgentContext**: 重构阶段间数据传递
2. **实现数据源故障转移**: 提升 API 调用稳定性
3. **添加管道超时保护**: 防止分析卡死

### 阶段二：策略系统 (2-3 周)

1. **设计 YAML 技能格式**: 参考上文示例
2. **实现 SkillManager**: 加载和管理技能
3. **改造分析师**: 支持技能指令注入

### 阶段三：高级功能 (3-4 周)

1. **实现多模式管道**: quick/standard/full/specialist
2. **添加置信度校准**: 基于历史准确率
3. **实现风控覆写**: 强制风险干预

---

## 四、代码参考

完整的 daily_stock_analysis 源码位于：`G:\AI\daily_stock_analysis`

关键文件：
- `src/agent/orchestrator.py` - 多智能体管道编排
- `src/agent/skills/base.py` - 技能系统基础类
- `src/agent/agents/base_agent.py` - 智能体基类
- `src/agent/memory.py` - 历史记忆与校准
- `src/agent/tools/registry.py` - 工具注册表

---

## 五、风险与注意事项

1. **兼容性**: 改造需保持现有 CLI/Web 接口兼容
2. **测试覆盖**: 新功能需补充单元测试和集成测试
3. **性能**: 管道模式变化可能影响 LLM 调用成本
4. **迁移路径**: 建议通过 feature flag 控制新旧逻辑切换

---

*文档生成时间: 2026-04-19*
