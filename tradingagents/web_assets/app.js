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
  heroMetrics: document.getElementById("hero-metrics"),
  reportCount: document.getElementById("report-count"),
  feedback: document.getElementById("submit-feedback"),
  form: document.getElementById("analysis-form"),
  symbolModal: document.getElementById("symbol-modal"),
  symbolModalClose: document.getElementById("symbol-modal-close"),
  symbolModalCopy: document.getElementById("symbol-modal-copy"),
  symbolCandidateList: document.getElementById("symbol-candidate-list"),
};

function decisionClass(value) {
  const norm = (value || "").toLowerCase();
  if (norm === "buy" || norm === "overweight") return "buy";
  if (norm === "hold") return "hold";
  if (norm === "sell" || norm === "underweight") return "sell";
  return "unknown";
}

function htmlEscape(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

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

function closeSymbolModal() {
  state.pendingPayload = null;
  els.symbolModal.hidden = true;
  els.symbolCandidateList.innerHTML = "";
}

function openSymbolModal(rawInput, candidates) {
  state.pendingPayload = state.pendingPayload || {};
  els.symbolModal.hidden = false;
  els.symbolModalCopy.textContent = `“${rawInput}” 对应多个股票，请先确认这次要分析的上市标的。`;
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

function renderHeroMetrics() {
  const running = state.jobs.filter((job) => job.status === "running").length;
  const completed = state.reports.length;
  const buyCount = state.reports.filter((item) => (item.decision || "").toLowerCase() === "buy").length;
  els.heroMetrics.innerHTML = `
    <div class="metric-card">
      <span class="metric-label">Running Jobs</span>
      <div class="metric-value">${running}</div>
    </div>
    <div class="metric-card">
      <span class="metric-label">Saved Reports</span>
      <div class="metric-value">${completed}</div>
    </div>
    <div class="metric-card">
      <span class="metric-label">Buy Ratings</span>
      <div class="metric-value">${buyCount}</div>
    </div>
  `;
}

function populateFormOptions() {
  const { providers, models, analysts, research_depths: depths, defaults } = state.options;
  els.provider.innerHTML = providers.map((item) => `<option value="${item.id}">${item.label}</option>`).join("");
  els.provider.value = defaults.provider;

  els.researchDepth.innerHTML = depths.map((item) => `<option value="${item.value}">${item.label}</option>`).join("");
  els.researchDepth.value = String(defaults.research_depth);
  els.analysisDate.value = defaults.analysis_date;

  els.analystOptions.innerHTML = analysts
    .map((item) => `
      <label class="chip">
        <input type="checkbox" name="analysts" value="${item.id}" ${defaults.analysts.includes(item.id) ? "checked" : ""}>
        <span>${item.label}</span>
      </label>
    `)
    .join("");

  updateProviderDependentFields();
}

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
  // Show different helper text based on whether env key exists
  if (hasEnvKey) {
    els.apiKeyHelper.textContent = "✓ 已从环境变量读取，留空使用已有 Key，也可输入覆盖。";
    els.apiKeyHelper.style.color = "#22c55e";
  } else {
    els.apiKeyHelper.textContent = providerMeta?.api_key_helper || "可直接覆盖当前任务使用的 API Key；留空时沿用本机已有环境变量。";
    els.apiKeyHelper.style.color = "";
  }
}

function renderJobs() {
  if (!state.jobs.length) {
    els.jobsPanel.className = "jobs-panel empty-state";
    els.jobsPanel.textContent = "当前还没有运行中的任务。";
    return;
  }

  els.jobsPanel.className = "jobs-panel";
  els.jobsPanel.innerHTML = state.jobs
    .map((job) => {
      const stats = job.progress?.stats || {};
      const agents = job.progress?.agents || {};
      const agentBadges = Object.entries(agents)
        .map(([name, status]) => `<span class="badge ${status === "completed" ? "" : "subtle"}">${htmlEscape(name)} · ${htmlEscape(status)}</span>`)
        .join("");
      const latestMessage = job.progress?.messages?.at(-1)?.content || "";
      const resultLink = job.result?.report_id
        ? `<button class="ghost-btn" data-open-report="${job.result.report_id}">查看报告</button>`
        : "";

      return `
        <article class="job-card">
          <div class="row-between">
            <div>
              <strong>${htmlEscape(job.payload.ticker || "")}</strong>
              <div class="micro-copy">${htmlEscape(job.payload.analysis_date || "")} · ${htmlEscape(job.payload.llm_provider || "")}</div>
            </div>
            <span class="decision ${decisionClass(job.result?.decision || job.status)}">${htmlEscape(job.status)}</span>
          </div>
          <p class="micro-copy">${htmlEscape(latestMessage || "任务已提交，等待进一步进度。")}</p>
          <div class="mini-grid">
            <div class="mini-box"><strong>LLM Calls</strong>${stats.llm_calls ?? 0}</div>
            <div class="mini-box"><strong>Tool Calls</strong>${stats.tool_calls ?? 0}</div>
          </div>
          <div class="chips" style="margin-top:12px;">${agentBadges}</div>
          ${job.error ? `<pre class="report-html">${htmlEscape(job.error)}</pre>` : ""}
          ${resultLink}
        </article>
      `;
    })
    .join("");

  els.jobsPanel.querySelectorAll("[data-open-report]").forEach((button) => {
    button.addEventListener("click", () => openReport(button.dataset.openReport));
  });
}

function renderReports() {
  els.reportCount.textContent = String(state.reports.length);
  if (!state.reports.length) {
    els.reportsList.className = "reports-list empty-state";
    els.reportsList.textContent = "还没有可展示的报告。";
    return;
  }

  els.reportsList.className = "reports-list";
  els.reportsList.innerHTML = state.reports
    .map((report) => `
      <article class="report-card ${state.activeReportId === report.id ? "active" : ""}" data-report-id="${report.id}">
        <div class="row-between">
          <div>
            <strong>${htmlEscape(report.display_name || report.ticker)}</strong>
            <div class="micro-copy">${htmlEscape(report.ticker)}</div>
          </div>
          <span class="decision ${decisionClass(report.decision)}">${htmlEscape(report.decision)}</span>
        </div>
        <p class="meta-line">${htmlEscape(report.created_at)}</p>
        <p>${htmlEscape(report.summary || "暂无摘要。")}</p>
        <div class="chips">
          ${Object.entries(report.sections || {})
            .filter(([, enabled]) => enabled)
            .map(([section]) => `<span class="badge">${htmlEscape(section)}</span>`)
            .join("")}
        </div>
      </article>
    `)
    .join("");

  els.reportsList.querySelectorAll("[data-report-id]").forEach((card) => {
    card.addEventListener("click", () => openReport(card.dataset.reportId));
  });
}

function renderReportDetail(detail) {
  els.reportDetail.innerHTML = `
    <div class="detail-header">
      <section class="detail-hero">
        <p class="eyebrow">Final Call</p>
        <h2>${htmlEscape(detail.display_name || detail.ticker)}</h2>
        <p class="micro-copy">${htmlEscape(detail.ticker)}</p>
        <p>报告已直接生成中文版本。</p>
      </section>
      <section class="detail-stats">
        <div class="summary-card">
          <div class="row-between">
            <span class="micro-copy">Decision</span>
            <span class="decision ${decisionClass(detail.decision)}">${htmlEscape(detail.decision)}</span>
          </div>
          <p class="meta-line">生成时间：${htmlEscape(detail.created_at)}</p>
          <p>完整报告已按中文输出，可直接阅读。</p>
        </div>
      </section>
    </div>
    <div class="detail-sections">
      <section class="summary-card">
        <div class="card-head">
          <h3>完整报告</h3>
        </div>
        <div class="report-html">${detail.full_report_html}</div>
      </section>
    </div>
  `;
}

async function openReport(reportId) {
  state.activeReportId = reportId;
  renderReports();
  if (!state.detailCache.has(reportId)) {
    const detail = await fetchJson(`/api/reports/${encodeURIComponent(reportId)}`);
    state.detailCache.set(reportId, detail);
  }
  renderReportDetail(state.detailCache.get(reportId));
}

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

async function refreshJobs() {
  const data = await fetchJson("/api/jobs");
  state.jobs = data.jobs || [];
  renderJobs();
  renderHeroMetrics();
}

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

async function init() {
  state.options = await fetchJson("/api/options");
  populateFormOptions();
  await Promise.all([refreshReports(true), refreshJobs()]);
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
