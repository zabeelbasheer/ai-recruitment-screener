const state = { user: null };

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function showApp() {
  document.getElementById("login-section").classList.add("hidden");
  document.getElementById("app-nav").classList.remove("hidden");
  document.getElementById("user-bar").classList.remove("hidden");
  document.getElementById("user-label").textContent = `${state.user.name} (${state.user.role})`;
  document.getElementById("screen-tab").classList.remove("hidden");
}

function showLogin() {
  document.getElementById("login-section").classList.remove("hidden");
  document.getElementById("app-nav").classList.add("hidden");
  document.getElementById("user-bar").classList.add("hidden");
  document.getElementById("screen-tab").classList.add("hidden");
  document.getElementById("history-tab").classList.add("hidden");
}

async function checkSession() {
  try {
    state.user = await api("/session");
    showApp();
  } catch {
    showLogin();
  }
}

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = document.getElementById("login-name").value;
  const role = document.getElementById("login-role").value;
  const password = document.getElementById("login-password").value;
  const errorEl = document.getElementById("login-error");
  errorEl.classList.add("hidden");
  try {
    state.user = await api("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, role, password }),
    });
    showApp();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await api("/logout", { method: "POST" });
  state.user = null;
  showLogin();
});

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
    document.getElementById(`${btn.dataset.tab}-tab`).classList.remove("hidden");
    if (btn.dataset.tab === "history" && typeof loadHistory === "function") loadHistory();
  });
});

function renderScorecard(candidate) {
  const criteria = (candidate.criterion_scores || [])
    .map((cs) => `<div class="criterion"><strong>${cs.name}</strong>: ${cs.score}/5 — ${escapeHtml(cs.rationale)}</div>`)
    .join("");
  const failures = (candidate.hard_filter_failures || [])
    .map((f) => `<div class="criterion">${escapeHtml(f)}</div>`)
    .join("");
  return `
    <div class="scorecard">
      <h3>${escapeHtml(candidate.candidate_name)}</h3>
      <div class="fit-pct">${candidate.fit_pct}%</div>
      ${!candidate.hard_filter_passed ? `<p class="error">Failed hard filters</p>${failures}` : ""}
      ${criteria}
      <p><strong>Strengths:</strong> ${(candidate.strengths || []).join(", ") || "None"}</p>
      <p><strong>Gaps:</strong> ${(candidate.gaps || []).map(escapeHtml).join(", ") || "None"}</p>
    </div>
  `;
}

function renderBatchTable(result) {
  const rows = result.candidates
    .map(
      (c, i) => `
      <tr data-index="${i}">
        <td>${escapeHtml(c.candidate_name)}</td>
        <td>${c.fit_pct}%</td>
        <td>${c.parse_failed ? "Could not process" : c.hard_filter_passed ? "Passed filters" : "Failed filters"}</td>
      </tr>`
    )
    .join("");
  return `
    <table>
      <thead><tr><th>Candidate</th><th>Fit %</th><th>Status</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div id="scorecard-detail"></div>
  `;
}

let lastRunId = null;
let lastBatchResult = null;

document.getElementById("screen-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const statusEl = document.getElementById("screen-status");
  const resultsArea = document.getElementById("results-area");
  const fairnessBanner = document.getElementById("fairness-banner");
  fairnessBanner.classList.add("hidden");
  resultsArea.innerHTML = "";
  statusEl.textContent = "Screening in progress…";
  statusEl.classList.remove("hidden");

  const jdText = document.getElementById("jd-text").value;
  const files = document.getElementById("resume-files").files;
  const formData = new FormData();
  formData.append("jd_text", jdText);

  try {
    let payload;
    if (files.length === 1) {
      formData.append("resume", files[0]);
      payload = await api("/screen/single", { method: "POST", body: formData });
      resultsArea.innerHTML = renderScorecard(payload.result);
    } else {
      Array.from(files).forEach((f) => formData.append("resumes", f));
      payload = await api("/screen/batch", { method: "POST", body: formData });
      lastRunId = payload.run_id;
      lastBatchResult = payload.result;
      if (payload.result.fairness_flag) {
        fairnessBanner.textContent = payload.result.fairness_flag.message;
        fairnessBanner.classList.remove("hidden");
      }
      resultsArea.innerHTML = renderBatchTable(payload.result) + `<button id="export-csv-btn">Export CSV</button>`;
      document.querySelectorAll("#results-area tr[data-index]").forEach((row) => {
        row.addEventListener("click", () => {
          const candidate = lastBatchResult.candidates[Number(row.dataset.index)];
          document.getElementById("scorecard-detail").innerHTML = renderScorecard(candidate);
        });
      });
      document.getElementById("export-csv-btn").addEventListener("click", () => {
        window.location.href = `/export/csv/${lastRunId}`;
      });
    }
    statusEl.classList.add("hidden");
  } catch (err) {
    statusEl.textContent = err.message;
  }
});

async function loadHistory() {
  const listEl = document.getElementById("history-list");
  listEl.textContent = "Loading…";
  try {
    const runs = await api("/runs");
    if (runs.length === 0) {
      listEl.textContent = "No screening runs yet.";
      return;
    }
    listEl.innerHTML = runs
      .map(
        (r) => `
        <div class="scorecard">
          <p><strong>${escapeHtml(r.username)}</strong> (${r.role}) — ${r.mode} — ${new Date(r.created_at).toLocaleString()}</p>
          <p>${escapeHtml(r.jd_text.slice(0, 120))}${r.jd_text.length > 120 ? "…" : ""}</p>
          ${r.mode === "batch" ? `<button onclick="window.location.href='/export/csv/${r.id}'">Export CSV</button>` : ""}
        </div>`
      )
      .join("");
  } catch (err) {
    listEl.textContent = err.message;
  }
}

document.getElementById("refresh-history-btn").addEventListener("click", loadHistory);

checkSession();
