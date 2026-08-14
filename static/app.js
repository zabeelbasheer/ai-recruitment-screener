const state = { user: null };

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  return response.json();
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

checkSession();
