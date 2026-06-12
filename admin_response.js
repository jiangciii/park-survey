const detailTitle = document.getElementById("detailTitle");
const metaList = document.getElementById("metaList");
const answerSections = document.getElementById("answerSections");
const ceBody = document.getElementById("ceBody");

function responseIdFromPath() {
  const parts = window.location.pathname.split("/");
  return parts[parts.length - 1];
}

function parseExcelSerialDate(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 30000 || numeric > 60000) return null;
  // Excel serial dates are local spreadsheet times. Shift by China offset before
  // formatting with Asia/Shanghai so 46164.63 displays as 2026-05-22 afternoon.
  return new Date((numeric - 25569) * 86400000 - 8 * 60 * 60 * 1000);
}

function formatTime(value) {
  if (!value) return "未提交";
  const parsed = parseExcelSerialDate(value) || new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value).replace("T", " ").slice(0, 19);
  }
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  })
    .format(parsed)
    .replace(/\//g, "-");
}

function formatResponseTime(ms) {
  if (!ms) return "—";
  return `${Math.round(ms / 1000)}秒`;
}

function ceSchemeCopy(prefix, row) {
  return `${row[`${prefix}_density`]}密度 · ${row[`${prefix}_type`]} · ${row[`${prefix}_price`]}元 · ${row[`${prefix}_space_compensation`]} · ${row[`${prefix}_revenue_feedback`]}`;
}

function renderMeta(respondent) {
  const items = [
    ["答卷编号", respondent.respondent_id],
    ["完成码", respondent.completion_code || "—"],
    ["作答状态", respondent.status === "completed" ? "已完成" : "未完成"],
    ["开始时间", formatTime(respondent.survey_started_at)],
    ["提交时间", formatTime(respondent.submit_time)],
    ["作答时长", respondent.duration_label],
    ["常去公园", respondent.park_type_usual || "—"],
    ["联想对象", respondent.park_type_imagined || "—"],
  ];

  metaList.innerHTML = items
    .map(
      ([label, value]) => `
        <div class="meta-item">
          <strong>${label}</strong>
          <div>${value}</div>
        </div>
      `,
    )
    .join("");
}

function renderAnswers(sections) {
  answerSections.innerHTML = sections
    .map(
      (section) => `
        <section class="answer-section">
          <h3 style="margin:0 0 14px;">${section.title}</h3>
          ${section.questions
            .map(
              (question) => `
                <div class="question-row">
                  <h4>${question.display_id} ${question.title}</h4>
                  <p>${question.statement}</p>
                  <span class="answer-chip">${question.answer_display || "未作答"}</span>
                </div>
              `,
            )
            .join("")}
        </section>
      `,
    )
    .join("");
}

function renderCeRows(rows) {
  if (!rows.length) {
    ceBody.innerHTML = `
      <tr>
        <td colspan="5" class="muted">暂无 CE 选择记录</td>
      </tr>
    `;
    return;
  }

  ceBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>Task ${row.task_id}</td>
          <td>${ceSchemeCopy("option_a", row)}</td>
          <td>${ceSchemeCopy("option_b", row)}</td>
          <td><strong>${row.chosen_option}</strong></td>
          <td>${formatResponseTime(row.response_time_ms)}</td>
        </tr>
      `,
    )
    .join("");
}

async function loadDetail() {
  const respondentId = responseIdFromPath();
  const response = await fetch(`/api/admin/responses/${respondentId}`, {
    credentials: "same-origin",
  });

  if (response.status === 401) {
    window.location.href = "/admin/login";
    return;
  }

  if (response.status === 404) {
    detailTitle.textContent = "答卷不存在";
    return;
  }

  const data = await response.json();
  detailTitle.textContent = `答卷详情 · ${data.respondent.respondent_id}`;
  renderMeta(data.respondent);
  renderAnswers(data.answer_sections || []);
  renderCeRows(data.ce_choices || []);
}

loadDetail();
