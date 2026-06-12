const statsGrid = document.getElementById("statsGrid");
const responsesBody = document.getElementById("responsesBody");
const emptyState = document.getElementById("emptyState");
const refreshButton = document.getElementById("refreshButton");
const logoutButton = document.getElementById("logoutButton");
const searchInput = document.getElementById("searchInput");
const statusFilter = document.getElementById("statusFilter");

const FILTER_STATE = {
  status: "all",
  search: "",
};

let refreshTimer = null;

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
    return String(value).replace("T", " ").slice(0, 16);
  }
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  })
    .format(parsed)
    .replace(/\//g, "-");
}

function renderStats(data) {
  const cards = [
    { label: "总提交人数", value: data.total_submissions, note: "包含完整与未完整答卷" },
    { label: "完整答卷数", value: data.completed_submissions, note: "已完成并正式提交" },
    { label: "未完成答卷数", value: data.incomplete_submissions, note: "开始后中断或未完整作答" },
    { label: "平均作答时长", value: data.avg_duration_label, note: "仅基于完整答卷计算" },
  ];

  statsGrid.innerHTML = cards
    .map(
      (card) => `
        <section class="panel stat-card">
          <h3>${card.label}</h3>
          <div class="stat-value">${card.value}</div>
          <div class="stat-note">${card.note}</div>
        </section>
      `,
    )
    .join("");
}

function renderResponses(rows) {
  if (!rows.length) {
    responsesBody.innerHTML = "";
    emptyState.hidden = false;
    return;
  }

  emptyState.hidden = true;
  responsesBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td><strong>${row.respondent_id}</strong></td>
          <td>${row.completion_code || "—"}</td>
          <td>${formatTime(row.submit_time || row.updated_at)}</td>
          <td><span class="status ${row.status}">${row.status === "completed" ? "已完成" : "未完成"}</span></td>
          <td>${row.duration_label}</td>
          <td>${row.park_type_usual || "—"}</td>
          <td>${row.park_type_imagined || "—"}</td>
          <td>${row.ce_progress}</td>
          <td><a class="subtle-link" href="/admin/responses/${row.respondent_id}">查看详情</a></td>
        </tr>
      `,
    )
    .join("");
}

async function fetchDashboard() {
  const params = new URLSearchParams();
  if (FILTER_STATE.status !== "all") params.set("status", FILTER_STATE.status);
  if (FILTER_STATE.search) params.set("search", FILTER_STATE.search);

  const response = await fetch(`/api/admin/dashboard?${params.toString()}`, {
    credentials: "same-origin",
  });
  if (response.status === 401) {
    window.location.href = "/admin/login";
    return null;
  }

  const data = await response.json();
  renderStats(data);
  renderResponses(data.responses || []);
  return data;
}

function setActiveStatus(status) {
  FILTER_STATE.status = status;
  statusFilter.querySelectorAll(".segment").forEach((button) => {
    button.classList.toggle("active", button.dataset.status === status);
  });
}

statusFilter.addEventListener("click", (event) => {
  const target = event.target.closest("[data-status]");
  if (!target) return;
  setActiveStatus(target.dataset.status);
  fetchDashboard();
});

searchInput.addEventListener("input", () => {
  FILTER_STATE.search = searchInput.value.trim();
  fetchDashboard();
});

refreshButton.addEventListener("click", () => {
  fetchDashboard();
});

logoutButton.addEventListener("click", async () => {
  await fetch("/api/admin/logout", {
    method: "POST",
    credentials: "same-origin",
  });
  window.location.href = "/admin/login";
});

fetchDashboard();
refreshTimer = window.setInterval(fetchDashboard, 15000);

window.addEventListener("beforeunload", () => {
  if (refreshTimer) window.clearInterval(refreshTimer);
});
