(function () {
  const runtime = window.__SURVEY_RUNTIME__ || {};
  const apiBaseUrl = (runtime.apiBaseUrl || "").replace(/\/+$/, "");
  const staticMode = runtime.staticMode === true || runtime.submitMode === "download";

  const API = {
    start: buildApiUrl("/api/respondents/start"),
    draft: buildApiUrl("/api/respondents/draft"),
    submit: buildApiUrl("/api/respondents/submit"),
  };

  const DRAFT_SYNC_DELAY = 900;
  const MAX_DRAFT_AGE_MS = 2 * 60 * 60 * 1000;

  const originalPersistDraft = window.persistDraft;
  const originalResetQuestionnaire = window.resetQuestionnaire;
  const originalUpdateDock = window.updateDock;

  let draftTimer = null;
  let startPromise = null;

  function safeRespondentId() {
    if (state.respondentMeta.respondent_id) return state.respondentMeta.respondent_id;
    const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
    const random = Math.random().toString(36).slice(2, 6).toUpperCase();
    state.respondentMeta.respondent_id = `LOCAL-${stamp}-${random}`;
    return state.respondentMeta.respondent_id;
  }

  function csvCell(value) {
    let text = value;
    if (value === null || value === undefined) text = "";
    if (Array.isArray(value) || (typeof value === "object" && value !== null)) {
      text = JSON.stringify(value);
    }
    text = String(text);
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  function flattenObject(input, prefix = "", output = {}) {
    Object.entries(input || {}).forEach(([key, value]) => {
      const nextKey = prefix ? `${prefix}_${key}` : key;
      if (Array.isArray(value)) {
        output[nextKey] = value.join("|");
      } else if (value && typeof value === "object") {
        flattenObject(value, nextKey, output);
      } else {
        output[nextKey] = value;
      }
    });
    return output;
  }

  function downloadTextFile(filename, text, mimeType) {
    const blob = new Blob(["\ufeff", text], { type: `${mimeType};charset=utf-8` });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function payloadFilename(payload, suffix) {
    const id = payload.respondent_meta?.respondent_id || safeRespondentId();
    return `park_survey_${id}_${suffix}`;
  }

  function downloadJsonPayload(payload) {
    downloadTextFile(payloadFilename(payload, "result.json"), JSON.stringify(payload, null, 2), "application/json");
  }

  function downloadRespondentCsv(payload) {
    const respondent = {
      ...flattenObject(payload.respondent_meta || {}, "respondent"),
      ...flattenObject(payload.non_ce_answers || {}, "answer"),
      ...flattenObject(payload.derived_meta || {}, "derived"),
    };
    const headers = Object.keys(respondent);
    const rows = [headers.join(","), headers.map((header) => csvCell(respondent[header])).join(",")];
    downloadTextFile(payloadFilename(payload, "respondent.csv"), rows.join("\n"), "text/csv");
  }

  function downloadCeCsv(payload) {
    const rows = (payload.ce_answers || []).map((item) => ({
      respondent_id: payload.respondent_meta?.respondent_id || "",
      ...flattenObject(item),
    }));
    const headers = Array.from(rows.reduce((set, row) => {
      Object.keys(row).forEach((key) => set.add(key));
      return set;
    }, new Set(["respondent_id"])));
    const csvRows = [
      headers.join(","),
      ...rows.map((row) => headers.map((header) => csvCell(row[header])).join(",")),
    ];
    downloadTextFile(payloadFilename(payload, "ce_choices.csv"), csvRows.join("\n"), "text/csv");
  }

  function saveStaticSubmission(payload) {
    const key = "park-questionnaire-static-submissions";
    const list = JSON.parse(localStorage.getItem(key) || "[]");
    list.unshift({
      respondent_id: payload.respondent_meta?.respondent_id || "",
      submitted_at: payload.respondent_meta?.submitted_at || new Date().toISOString(),
      payload,
    });
    localStorage.setItem(key, JSON.stringify(list.slice(0, 20)));
  }

  function ensureStaticExportControls() {
    const endLinks = document.querySelector(".end-links");
    if (!endLinks || document.getElementById("downloadJsonButton")) return;

    const note = document.createElement("div");
    note.className = "contact-footnote";
    note.textContent = "当前为 GitHub Pages 静态访问版，数据不会自动上传服务器。请下载 JSON / CSV 结果并妥善保存。";
    endLinks.parentNode.insertBefore(note, endLinks);

    const jsonButton = document.createElement("button");
    jsonButton.className = "text-link";
    jsonButton.id = "downloadJsonButton";
    jsonButton.type = "button";
    jsonButton.textContent = "下载 JSON 结果";
    jsonButton.addEventListener("click", () => downloadJsonPayload(currentPayload()));

    const respondentCsvButton = document.createElement("button");
    respondentCsvButton.className = "text-link";
    respondentCsvButton.id = "downloadRespondentCsvButton";
    respondentCsvButton.type = "button";
    respondentCsvButton.textContent = "下载普通题 CSV";
    respondentCsvButton.addEventListener("click", () => downloadRespondentCsv(currentPayload()));

    const ceCsvButton = document.createElement("button");
    ceCsvButton.className = "text-link";
    ceCsvButton.id = "downloadCeCsvButton";
    ceCsvButton.type = "button";
    ceCsvButton.textContent = "下载 CE CSV";
    ceCsvButton.addEventListener("click", () => downloadCeCsv(currentPayload()));

    endLinks.insertBefore(jsonButton, endLinks.firstChild);
    endLinks.insertBefore(respondentCsvButton, restartButton);
    endLinks.insertBefore(ceCsvButton, restartButton);
  }

  function installStaticMode() {
    submitSurvey = async function submitSurveyStatic(payload) {
      payload.respondent_meta.respondent_id = safeRespondentId();
      saveStaticSubmission(payload);
      return {
        respondent_id: payload.respondent_meta.respondent_id,
        completion_code: state.respondentMeta.completion_code || `LOCAL-${payload.respondent_meta.respondent_id.slice(-4)}`,
        static_mode: true,
      };
    };

    showEndScreen = async function showEndScreenStatic() {
      state.respondentMeta.submitted_at = new Date().toISOString();
      state.respondentMeta.respondent_id = safeRespondentId();
      const payload = currentPayload();
      const result = await submitSurvey(payload);
      state.respondentMeta.completion_code = result.completion_code;
      if (typeof originalPersistDraft === "function") originalPersistDraft();
      setAppScreen("end");
      ensureStaticExportControls();
      if (typeof showToast === "function") {
        showToast("静态版已生成结果，请在封底下载 JSON / CSV");
      }
    };

    updateDock = function updateDockStatic() {
      if (typeof originalUpdateDock === "function") originalUpdateDock();
      if (state.sectionIndex === SECTIONS.length - 1) {
        nextButton.textContent = "提交问卷";
      }
    };

    startButton.addEventListener("click", () => {
      if (state.appScreen === "cover" && !hasProgress()) {
        resetRespondentSessionStart();
        if (typeof originalPersistDraft === "function") originalPersistDraft();
      }
    });

    ensureStaticExportControls();
    updateDock();
  }

  if (staticMode) {
    installStaticMode();
    return;
  }

  function buildApiUrl(path) {
    return apiBaseUrl ? `${apiBaseUrl}${path}` : path;
  }

  function clientMeta() {
    return {
      user_agent: navigator.userAgent,
      language: navigator.language,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
      platform: navigator.platform || null,
    };
  }

  async function requestJSON(url, options) {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "same-origin",
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || "请求失败");
    }
    return data;
  }

  function currentPayload() {
    const payload = buildPayload();
    payload.respondent_meta.respondent_id = state.respondentMeta.respondent_id || null;
    return payload;
  }

  function hasProgress() {
    return Object.keys(answerMap).length > 0 || state.ceResults.length > 0 || state.appScreen !== "cover";
  }

  function resetRespondentSessionStart() {
    state.respondentMeta.started_at = new Date().toISOString();
    state.respondentMeta.submitted_at = null;
    state.respondentMeta.respondent_id = null;
    state.respondentMeta.completion_code = null;
  }

  function isDraftStale() {
    if (state.respondentMeta.submitted_at) return false;
    if (!hasProgress()) return false;
    const startedAt = Date.parse(state.respondentMeta.started_at || "");
    if (Number.isNaN(startedAt)) return true;
    return Date.now() - startedAt > MAX_DRAFT_AGE_MS;
  }

  async function ensureRespondentStarted() {
    if (state.respondentMeta.respondent_id) return state.respondentMeta.respondent_id;
    if (startPromise) return startPromise;

    startPromise = requestJSON(API.start, {
      method: "POST",
      body: JSON.stringify({
        started_at: state.respondentMeta.started_at,
        client_meta: clientMeta(),
      }),
    })
      .then((data) => {
        state.respondentMeta.respondent_id = data.respondent_id;
        state.respondentMeta.completion_code = null;
        if (typeof originalPersistDraft === "function") originalPersistDraft();
        return data.respondent_id;
      })
      .finally(() => {
        startPromise = null;
      });

    return startPromise;
  }

  async function syncDraftNow() {
    if (!hasProgress()) return;
    const respondentId = await ensureRespondentStarted();
    await requestJSON(API.draft, {
      method: "POST",
      body: JSON.stringify({
        respondent_id: respondentId,
        payload: currentPayload(),
        client_meta: clientMeta(),
      }),
    });
  }

  function scheduleDraftSync() {
    if (state.respondentMeta.submitted_at) return;
    clearTimeout(draftTimer);
    draftTimer = setTimeout(() => {
      syncDraftNow().catch(() => {
        // Draft sync should not block the questionnaire flow.
      });
    }, DRAFT_SYNC_DELAY);
  }

  persistDraft = function persistDraftWithServerSync() {
    if (typeof originalPersistDraft === "function") originalPersistDraft();
    scheduleDraftSync();
  };

  submitSurvey = async function submitSurveyToServer(payload) {
    const respondentId = await ensureRespondentStarted();
    payload.respondent_meta.respondent_id = respondentId;
    return requestJSON(API.submit, {
      method: "POST",
      body: JSON.stringify({
        respondent_id: respondentId,
        payload,
        client_meta: clientMeta(),
      }),
    });
  };

  showEndScreen = async function showEndScreenWithSubmit() {
    state.respondentMeta.submitted_at = new Date().toISOString();
    const payload = currentPayload();
    const originalLabel = nextButton.textContent;
    nextButton.disabled = true;
    nextButton.textContent = "提交中...";

    try {
      const result = await submitSurvey(payload);
      state.respondentMeta.respondent_id = result.respondent_id || state.respondentMeta.respondent_id;
      state.respondentMeta.completion_code = result.completion_code || null;
      clearTimeout(draftTimer);
      setAppScreen("end");
      localStorage.removeItem(typeof STORAGE_KEY === "string" ? STORAGE_KEY : "park-questionnaire-0417-draft");
    } catch (error) {
      state.respondentMeta.submitted_at = null;
      if (typeof showToast === "function") {
        showToast("提交失败，请稍后重试");
      }
      if (typeof originalUpdateDock === "function") originalUpdateDock();
    } finally {
      nextButton.textContent = originalLabel;
      nextButton.disabled = false;
    }
  };

  resetQuestionnaire = function resetQuestionnaireWithRespondent() {
    if (typeof originalResetQuestionnaire === "function") originalResetQuestionnaire();
    state.respondentMeta.respondent_id = null;
    state.respondentMeta.completion_code = null;
    clearTimeout(draftTimer);
  };

  updateDock = function updateDockWithSubmitLabel() {
    if (typeof originalUpdateDock === "function") originalUpdateDock();
    if (state.sectionIndex === SECTIONS.length - 1) {
      nextButton.textContent = "提交问卷";
    }
  };

  startButton.addEventListener("click", () => {
    if (state.appScreen === "cover" && !hasProgress()) {
      resetRespondentSessionStart();
      if (typeof originalPersistDraft === "function") originalPersistDraft();
    }
    ensureRespondentStarted().catch(() => {
      if (typeof showToast === "function") {
        showToast("初始化答卷失败，请稍后再试");
      }
    });
  });

  window.addEventListener("pagehide", () => {
    if (!state.respondentMeta.respondent_id || !hasProgress() || state.respondentMeta.submitted_at) return;
    const body = JSON.stringify({
      respondent_id: state.respondentMeta.respondent_id,
      payload: currentPayload(),
      client_meta: clientMeta(),
    });
    navigator.sendBeacon?.(API.draft, new Blob([body], { type: "application/json" }));
  });

  if (state.respondentMeta.respondent_id) {
    scheduleDraftSync();
  }

  if (isDraftStale()) {
    resetQuestionnaire();
    if (typeof showToast === "function") {
      showToast("检测到过期草稿，已为你重新开始答卷");
    }
  }

  updateDock();
})();
