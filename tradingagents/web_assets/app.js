/**
 * TradingAgents Web Application
 * Enhanced with ScoreGauge and improved visual design
 */

const state = {
  options: null,
  reports: [],
  jobs: [],
  activeReportId: null,
  detailCache: new Map(),
  pendingPayload: null,
};

const els = {
  provider: document.getElementById("provider"),
  backendUrl: document.getElementById("backend-url"),
  apiKey: document.getElementById("api-key"),
  apiKeyField: document.getElementById("api-key-field"),
  apiKeyLabel: document.getElementById("api-key-label"),
  apiKeyHelper: document.getElementById("api-key-helper"),
  quickModelSelect: document.getElementById("quick-model-select"),
  quickModel: document.getElementById("quick-model"),
  deepModelSelect: document.getElementById("deep-model-select"),
  deepModel: document.getElementById("deep-model"),
  analysisDate: document.getElementById("analysis-date"),
  researchDepth: document.getElementById("research-depth"),
  analystOptions: document.getElementById("analyst-options"),
  reportsList: document.getElementById("reports-list"),
  reportDetail: document.getElementById("report-detail"),
  jobsPanel: document.getElementById("jobs-panel"),
  jobsSection: document.getElementById("jobs-section"),
  heroMetrics: document.getElementById("hero-metrics"),
  reportCount: document.getElementById("report-count"),
  feedback: document.getElementById("submit-feedback"),
  form: document.getElementById("analysis-form"),
  symbolModal: document.getElementById("symbol-modal"),
  symbolModalClose: document.getElementById("symbol-modal-close"),
  symbolModalCopy: document.getElementById("symbol-modal-copy"),
  symbolCandidateList: document.getElementById("symbol-candidate-list"),
};

/**
 * Decision class mapping for badges
 */
function decisionClass(value) {
  const norm = (value || "").toLowerCase();
  if (norm === "buy" || norm === "overweight") return "buy";
  if (norm === "hold") return "hold";
  if (norm === "sell" || norm === "underweight") return "sell";
  return "unknown";
}

/**
 * Decision display text (Chinese)
 */
function decisionText(value) {
  const norm = (value || "").toLowerCase();
  if (norm === "buy") return "买入";
  if (norm === "overweight") return "增持";
  if (norm === "hold") return "持有";
  if (norm === "sell") return "卖出";
  if (norm === "underweight") return "减持";
  return value || "未知";
}

/**
 * HTML escape utility
 */
function htmlEscape(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/**
 * Get score class based on value
 */
function getScoreClass(score) {
  if (score >= 60) return "score-high";
  if (score >= 40) return "score-medium";
  return "score-low";
}

/**
 * Get sentiment label based on score
 */
function getSentimentLabel(score) {
  if (score >= 80) return "强烈看好";
  if (score >= 60) return "偏多";
  if (score >= 40) return "中性";
  if (score >= 20) return "偏空";
  return "强烈看空";
}

/**
 * Extract score from report text
 */
function extractScore(text) {
  if (!text) return null;

  // Look for Chinese patterns: **情绪评分**: 75 or 评分：75
  const patterns = [
    /\*\*情绪评分\*\*[:：]\s*(\d+)/,
    /\*\*评分\*\*[:：]\s*(\d+)/,
    /情绪评分[:：]\s*(\d+)/,
    /评分[:：]\s*(\d+)/,
    /sentiment score[:：]\s*(\d+)/i,
  ];

  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) {
      const score = parseInt(match[1], 10);
      if (score >= 0 && score <= 100) {
        return score;
      }
    }
  }

  return null;
}

/**
 * JSON fetch utility
 */
async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

/**
 * Submit analysis payload
 */
async function submitAnalysisPayload(payload) {
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (response.status === 409 && data.candidates?.length) {
    return { ambiguous: true, data };
  }
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return { ambiguous: false, data };
}

/**
 * Close symbol selection modal
 */
function closeSymbolModal() {
  state.pendingPayload = null;
  els.symbolModal.hidden = true;
  els.symbolCandidateList.innerHTML = "";
}

/**
 * Open symbol selection modal
 */
function openSymbolModal(rawInput, candidates) {
  state.pendingPayload = state.pendingPayload || {};
  els.symbolModal.hidden = false;
  els.symbolModalCopy.textContent = `"${rawInput}" 对应多个股票，请先确认这次要分析的上市标的。`;
  els.symbolCandidateList.innerHTML = candidates
    .map((item) => `
      <button class="candidate-btn" type="button" data-ticker="${htmlEscape(item.canonical_ticker)}">
        <div class="candidate-line">
          <span class="candidate-name">${htmlEscape(item.name || item.canonical_ticker)}</span>
          <span class="badge subtle">${htmlEscape(item.market_label || item.market || "")}</span>
        </div>
        <div class="micro-copy">${htmlEscape(item.canonical_ticker)}</div>
      </button>
    `)
    .join("");

  els.symbolCandidateList.querySelectorAll("[data-ticker]").forEach((button) => {
    button.addEventListener("click", async () => {
      const chosenTicker = button.dataset.ticker;
      const payload = { ...state.pendingPayload, ticker: chosenTicker };
      document.getElementById("ticker").value = chosenTicker;
      closeSymbolModal();
      els.feedback.textContent = `已选择 ${chosenTicker}，任务提交中...`;
      try {
        const { data } = await submitAnalysisPayload(payload);
        els.feedback.textContent = `已提交任务 ${data.id}，正在后台分析。`;
        await refreshJobs();
      } catch (error) {
        els.feedback.textContent = error.message;
      }
    });
  });
}

/**
 * Render hero metrics section
 */
function renderHeroMetrics() {
  const running = state.jobs.filter((job) => job.status === "running").length;
  const completed = state.reports.length;
  const buyCount = state.reports.filter((item) => (item.decision || "").toLowerCase() === "buy").length;
  els.heroMetrics.innerHTML = `
    <div class="metric-card">
      <span class="metric-label">运行中任务</span>
      <div class="metric-value">${running}</div>
    </div>
    <div class="metric-card">
      <span class="metric-label">已保存报告</span>
      <div class="metric-value">${completed}</div>
    </div>
    <div class="metric-card">
      <span class="metric-label">买入评级</span>
      <div class="metric-value">${buyCount}</div>
    </div>
  `;
}

/**
 * Populate form options from API
 */
function populateFormOptions() {
  const { providers, models, analysts, research_depths: depths, defaults } = state.options;
  els.provider.innerHTML = providers.map((item) => `<option value="${item.id}">${item.label}</option>`).join("");
  els.provider.value = defaults.provider;

  els.researchDepth.innerHTML = depths.map((item) => `<option value="${item.value}">${item.label}</option>`).join("");
  els.researchDepth.value = String(defaults.research_depth);
  els.analysisDate.value = defaults.analysis_date;

  // Enhanced analyst options with icons
  const analystIcons = {
    market: `<svg class="analyst-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>`,
    social: `<svg class="analyst-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
    news: `<svg class="analyst-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/></svg>`,
    fundamentals: `<svg class="analyst-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h20"/><path d="M2 8h5"/><path d="M2 13h5"/><path d="M2 18h5"/><path d="M13 3v18"/><path d="M8 8l5 5-5 5"/><path d="M16 8l5 5-5 5"/></svg>`,
  };

  els.analystOptions.innerHTML = analysts
    .map((item) => `
      <label class="analyst-chip">
        <input type="checkbox" name="analysts" value="${item.id}" ${defaults.analysts.includes(item.id) ? "checked" : ""}>
        <span>
          ${analystIcons[item.id] || ""}
          ${item.label}
        </span>
      </label>
    `)
    .join("");

  updateProviderDependentFields();
}

/**
 * Update provider-dependent form fields
 */
function updateProviderDependentFields() {
  const provider = els.provider.value;
  const providerMeta = state.options.providers.find((item) => item.id === provider);
  const modelSet = state.options.models[provider] || { quick: [], deep: [] };
  els.backendUrl.value = providerMeta?.base_url || "";
  els.quickModelSelect.innerHTML = modelSet.quick.map((model) => `<option value="${model}">${model}</option>`).join("");
  els.deepModelSelect.innerHTML = modelSet.deep.map((model) => `<option value="${model}">${model}</option>`).join("");
  const defaults = state.options.defaults;
  const providerDefaults = defaults.model_defaults?.[provider] || {};
  const nextQuick = providerDefaults.quick || modelSet.quick[0] || defaults.quick_model || "";
  const nextDeep = providerDefaults.deep || modelSet.deep[0] || defaults.deep_model || nextQuick;
  if (els.quickModel.dataset.provider !== provider) {
    els.quickModel.value = nextQuick;
  }
  if (els.deepModel.dataset.provider !== provider) {
    els.deepModel.value = nextDeep;
  }
  els.quickModelSelect.value = modelSet.quick.includes(els.quickModel.value) ? els.quickModel.value : (modelSet.quick[0] || "");
  els.deepModelSelect.value = modelSet.deep.includes(els.deepModel.value) ? els.deepModel.value : (modelSet.deep[0] || "");
  els.quickModel.dataset.provider = provider;
  els.deepModel.dataset.provider = provider;
  const requiresApiKey = providerMeta?.requires_api_key !== false;
  const hasEnvKey = state.options.providers_with_env_key?.includes(provider);
  els.apiKeyField.hidden = !requiresApiKey;
  els.apiKey.disabled = !requiresApiKey;
  els.apiKey.value = requiresApiKey ? els.apiKey.value : "";
  els.apiKeyLabel.textContent = providerMeta?.api_key_label || "API Key";
  els.apiKey.placeholder = providerMeta?.api_key_placeholder || "输入当前模型供应商的 API Key";
  if (hasEnvKey) {
    els.apiKeyHelper.textContent = "✓ 已从环境变量读取，留空使用已有 Key，也可输入覆盖。";
    els.apiKeyHelper.style.color = "#22c55e";
  } else {
    els.apiKeyHelper.textContent = providerMeta?.api_key_helper || "可直接覆盖当前任务使用的 API Key；留空时沿用本机已有环境变量。";
    els.apiKeyHelper.style.color = "";
  }
}

/**
 * Calculate job progress percentage based on agent status
 */
function calculateJobProgress(job) {
  const agents = job.progress?.agents || {};
  const agentStatuses = Object.values(agents);
  if (agentStatuses.length === 0) return 0;

  const completed = agentStatuses.filter(s => s === "completed").length;
  return Math.round((completed / agentStatuses.length) * 100);
}

/**
 * Render jobs panel with enhanced progress display
 */
function renderJobs() {
  // Show/hide jobs section based on whether there are jobs
  const hasJobs = state.jobs.length > 0;
  els.jobsSection.hidden = !hasJobs;

  if (!hasJobs) {
    els.jobsPanel.className = "jobs-panel empty-state";
    els.jobsPanel.textContent = "当前还没有运行中的任务。";
    return;
  }

  els.jobsPanel.className = "jobs-panel";
  els.jobsPanel.innerHTML = state.jobs
    .map((job) => {
      const stats = job.progress?.stats || {};
      const agents = job.progress?.agents || {};
      const progress = calculateJobProgress(job);

      // Agent status chips
      const agentBadges = Object.entries(agents)
        .map(([name, status]) => `
          <span class="agent-chip ${status}">
            <span class="status-dot"></span>
            ${htmlEscape(name)}
          </span>
        `)
        .join("");

      const latestMessage = job.progress?.messages?.at(-1)?.content || "";
      const resultLink = job.result?.report_id
        ? `<button class="ghost-btn" data-open-report="${job.result.report_id}">查看报告</button>`
        : "";

      const statusBadge = job.status === "running"
        ? `<span class="decision running" style="background: rgba(13, 107, 99, 0.12); color: var(--accent);">运行中</span>`
        : job.status === "completed"
        ? `<span class="decision buy">完成</span>`
        : `<span class="decision sell">${htmlEscape(job.status)}</span>`;

      return `
        <article class="job-card animate-fade-in">
          <div class="row-between">
            <div>
              <strong style="font-size: 16px;">${htmlEscape(job.payload.ticker || "")}</strong>
              <div class="micro-copy" style="margin-top: 4px;">
                ${htmlEscape(job.payload.analysis_date || "")} · ${htmlEscape(job.payload.llm_provider || "")}
              </div>
            </div>
            ${statusBadge}
          </div>

          ${job.status === "running" ? `
            <div class="job-progress-bar">
              <div class="job-progress-fill" style="width: ${progress}%;"></div>
            </div>
          ` : ""}

          <p class="micro-copy" style="margin-top: 10px; color: var(--muted);">
            ${htmlEscape(latestMessage || "任务已提交，等待进一步进度。")}
          </p>

          <div class="agent-status-grid">
            ${agentBadges}
          </div>

          <div class="mini-grid" style="margin-top: 14px;">
            <div class="mini-box"><strong>LLM 调用</strong>${stats.llm_calls ?? 0}</div>
            <div class="mini-box"><strong>工具调用</strong>${stats.tool_calls ?? 0}</div>
          </div>

          ${job.error ? `<pre class="report-html" style="margin-top: 12px; color: var(--sell);">${htmlEscape(job.error)}</pre>` : ""}
          ${resultLink}
        </article>
      `;
    })
    .join("");

  els.jobsPanel.querySelectorAll("[data-open-report]").forEach((button) => {
    button.addEventListener("click", () => openReport(button.dataset.openReport));
  });
}

/**
 * Render reports list with enhanced cards (compact view)
 */
function renderReports() {
  els.reportCount.textContent = String(state.reports.length);
  if (!state.reports.length) {
    els.reportsList.className = "reports-list empty-state";
    els.reportsList.textContent = "还没有可展示的报告。";
    return;
  }

  els.reportsList.className = "reports-list";
  els.reportsList.innerHTML = state.reports
    .map((report) => {
      const score = report.score || 50;
      const scoreClass = getScoreClass(score);

      return `
        <article class="report-card ${state.activeReportId === report.id ? "active" : ""}" data-report-id="${report.id}">
          <div style="display: flex; align-items: center; gap: 10px;">
            <strong style="font-size: 15px;">${htmlEscape(report.display_name || report.ticker)}</strong>
            <span class="badge subtle" style="font-size: 10px;">${htmlEscape(report.ticker)}</span>
          </div>
          <p class="meta-line" style="margin-top: 3px; font-size: 12px;">${htmlEscape(report.created_at)}</p>

          <div style="display: flex; align-items: center; gap: 12px; margin-top: 10px;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span class="report-score-value ${scoreClass}" style="font-size: 18px; font-weight: 700;">${score}</span>
              <span style="font-size: 11px; color: var(--muted);">分</span>
            </div>
            <span class="decision ${decisionClass(report.decision)}">${decisionText(report.decision)}</span>
          </div>
        </article>
      `;
    })
    .join("");

  els.reportsList.querySelectorAll("[data-report-id]").forEach((card) => {
    card.addEventListener("click", () => openReport(card.dataset.reportId));
  });
}

/**
 * Render report detail with ScoreGauge
 */
function renderReportDetail(detail) {
  const score = detail.score || extractScore(detail.full_report_html) || 50;
  const scoreClass = getScoreClass(score);
  const sentimentLabel = getSentimentLabel(score);

  els.reportDetail.innerHTML = `
    <div class="detail-header">
      <section class="detail-hero" style="padding: 18px 22px;">
        <p class="eyebrow" style="margin-bottom: 6px;">分析报告</p>
        <h2 style="font-size: clamp(22px, 2.5vw, 28px); margin-bottom: 4px;">${htmlEscape(detail.display_name || detail.ticker)}</h2>
        <p class="micro-copy" style="font-size: 12px; opacity: 0.8;">
          ${htmlEscape(detail.ticker)} · ${htmlEscape(detail.created_at)}
        </p>
      </section>

      <section class="score-gauge-section" id="score-gauge-container" style="padding: 16px;">
        <!-- ScoreGauge will be rendered here -->
      </section>
    </div>

    <div class="detail-sections" style="margin-top: 20px;">
      <!-- Key Metrics -->
      <div class="key-metrics-grid">
        <div class="key-metric-item">
          <span class="key-metric-label">决策评级</span>
          <span class="key-metric-value">
            <span class="decision ${decisionClass(detail.decision)}">${decisionText(detail.decision)}</span>
          </span>
        </div>
        <div class="key-metric-item">
          <span class="key-metric-label">情绪评分</span>
          <span class="key-metric-value ${scoreClass}">${score}</span>
        </div>
        <div class="key-metric-item">
          <span class="key-metric-label">情绪指标</span>
          <span class="key-metric-value" style="font-size: 14px;">${sentimentLabel}</span>
        </div>
      </div>

      <!-- Summary -->
      ${detail.executive_summary ? `
        <section class="executive-summary-card" style="margin-top: 20px;">
          <h4>摘要</h4>
          <p>${htmlEscape(detail.executive_summary)}</p>
        </section>
      ` : ""}

      <!-- Full Report -->
      <section class="summary-card" style="margin-top: 20px;">
        <div class="card-head">
          <h3>完整报告</h3>
        </div>
        <div class="report-html">${detail.full_report_html}</div>
      </section>
    </div>
  `;

  // Render ScoreGauge if available
  const gaugeContainer = document.getElementById("score-gauge-container");
  if (gaugeContainer && window.ScoreGauge) {
    window.ScoreGauge.render(gaugeContainer, {
      score: score,
      size: "md",
      showLabel: true
    });
  }
}

/**
 * Open report detail
 */
async function openReport(reportId) {
  state.activeReportId = reportId;
  renderReports();
  if (!state.detailCache.has(reportId)) {
    const detail = await fetchJson(`/api/reports/${encodeURIComponent(reportId)}`);
    state.detailCache.set(reportId, detail);
  }
  renderReportDetail(state.detailCache.get(reportId));
}

/**
 * Refresh reports list
 */
async function refreshReports(selectLatest = false) {
  const data = await fetchJson("/api/reports");
  state.reports = data.reports || [];
  renderReports();
  renderHeroMetrics();
  if (selectLatest && state.reports[0]) {
    await openReport(state.reports[0].id);
  } else if (state.activeReportId && state.reports.some((item) => item.id === state.activeReportId)) {
    await openReport(state.activeReportId);
  }
}

/**
 * Refresh jobs list
 */
async function refreshJobs() {
  const data = await fetchJson("/api/jobs");
  state.jobs = data.jobs || [];
  renderJobs();
  renderHeroMetrics();
}

/**
 * Handle form submission
 */
async function handleSubmit(event) {
  event.preventDefault();
  const analysts = [...document.querySelectorAll('input[name="analysts"]:checked')].map((input) => input.value);
  const payload = {
    ticker: document.getElementById("ticker").value.trim(),
    analysis_date: els.analysisDate.value,
    llm_provider: els.provider.value,
    backend_url: els.backendUrl.value.trim(),
    api_key: els.apiKey.value.trim(),
    quick_model: els.quickModel.value,
    deep_model: els.deepModel.value,
    research_depth: Number(els.researchDepth.value),
    analysts,
  };

  if (!payload.ticker) {
    els.feedback.textContent = "请输入股票代码或公司名。";
    return;
  }

  if (!analysts.length) {
    els.feedback.textContent = "至少选择一个分析团队。";
    return;
  }

  els.feedback.textContent = "任务提交中...";
  try {
    const result = await submitAnalysisPayload(payload);
    if (result.ambiguous) {
      state.pendingPayload = payload;
      els.feedback.textContent = "该名称对应多个股票，请先在弹窗中确认标的。";
      openSymbolModal(payload.ticker, result.data.candidates);
      return;
    }
    const job = result.data;
    els.feedback.textContent = `已提交任务 ${job.id}，正在后台分析。`;
    await refreshJobs();
  } catch (error) {
    els.feedback.textContent = error.message;
  }
}

/**
 * Initialize application
 */
async function init() {
  state.options = await fetchJson("/api/options");
  populateFormOptions();
  await Promise.all([refreshReports(true), refreshJobs()]);

  // Event listeners
  els.provider.addEventListener("change", updateProviderDependentFields);

  els.quickModelSelect.addEventListener("change", () => {
    els.quickModel.value = els.quickModelSelect.value;
  });
  els.deepModelSelect.addEventListener("change", () => {
    els.deepModel.value = els.deepModelSelect.value;
  });

  els.quickModel.addEventListener("input", () => {
    if ([...els.quickModelSelect.options].some((option) => option.value === els.quickModel.value)) {
      els.quickModelSelect.value = els.quickModel.value;
    }
  });
  els.deepModel.addEventListener("input", () => {
    if ([...els.deepModelSelect.options].some((option) => option.value === els.deepModel.value)) {
      els.deepModelSelect.value = els.deepModel.value;
    }
  });

  els.symbolModalClose.addEventListener("click", closeSymbolModal);
  els.symbolModal.addEventListener("click", (event) => {
    if (event.target === els.symbolModal) {
      closeSymbolModal();
    }
  });

  els.form.addEventListener("submit", handleSubmit);

  // Auto-refresh interval
  setInterval(async () => {
    await refreshJobs();
    const hasNewCompleted = state.jobs.some((job) => job.result?.report_id && !state.reports.find((report) => report.id === job.result.report_id));
    if (hasNewCompleted) {
      await refreshReports();
    }
  }, 5000);
}

init().catch((error) => {
  els.feedback.textContent = error.message;
});
