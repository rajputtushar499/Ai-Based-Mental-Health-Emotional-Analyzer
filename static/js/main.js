/* Shared helpers: API wrapper, toasts, emotion metadata, auth forms, logout. */
const EMO = {
  stress:    { label: "Stress",             color: "#e07a5f", icon: "bi-lightning-charge" },
  anxiety:   { label: "Anxiety",            color: "#e3a857", icon: "bi-wind" },
  sadness:   { label: "Sadness / low mood", color: "#5c7cfa", icon: "bi-cloud-rain" },
  happiness: { label: "Happiness",          color: "#2fb57d", icon: "bi-emoji-smile" },
  anger:     { label: "Anger",              color: "#d64550", icon: "bi-fire" },
  fear:      { label: "Fear",               color: "#8c7bc4", icon: "bi-exclamation-triangle" },
  neutral:   { label: "Neutral",            color: "#8a99a6", icon: "bi-emoji-neutral" },
};

class ApiError extends Error {
  constructor(message, status, data) { super(message); this.status = status; this.data = data; }
}

/** fetch wrapper: sends the required header, parses JSON, throws ApiError with a friendly message. */
async function api(url, { method = "GET", json, formData } = {}) {
  const opts = { method, headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" };
  if (json !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(json); }
  if (formData) opts.body = formData;
  let res;
  try { res = await fetch(url, opts); }
  catch (e) { throw new ApiError("Cannot reach the server. Check that the app is still running.", 0); }
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-JSON body */ }
  if (!res.ok) {
    if (res.status === 401 && !location.pathname.startsWith("/login")) {
      location.href = "/login?next=" + encodeURIComponent(location.pathname);
    }
    throw new ApiError((data && data.error) || `Request failed (${res.status}).`, res.status, data);
  }
  return data;
}

function esc(value) {
  const d = document.createElement("div");
  d.textContent = value == null ? "" : String(value);
  return d.innerHTML;
}

function toast(message, type = "ok") {
  const el = document.createElement("div");
  el.className = "toast-x" + (type === "error" ? " error" : "");
  el.textContent = message;
  document.getElementById("toast-area").appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

function emotionBadge(emotion) {
  const m = EMO[emotion] || EMO.neutral;
  return `<span class="badge-emo emo-${esc(emotion)}"><i class="bi ${m.icon}"></i>${esc(m.label)}</span>`;
}

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function showFormError(message) {
  const box = document.getElementById("form-error");
  if (!box) return toast(message, "error");
  box.textContent = message;
  box.classList.toggle("d-none", !message);
}

function setBusy(button, busy, busyText) {
  if (!button) return;
  if (busy) { button.dataset.label = button.innerHTML; button.disabled = true; button.innerHTML = `<span class="spin"></span>${busyText || "Working..."}`; }
  else { button.disabled = false; if (button.dataset.label) button.innerHTML = button.dataset.label; }
}

function safeNext() {
  const next = new URLSearchParams(location.search).get("next");
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

document.addEventListener("DOMContentLoaded", () => {
  // Logout buttons
  document.querySelectorAll('[data-action="logout"]').forEach((btn) => btn.addEventListener("click", async () => {
    try { await api("/api/logout", { method: "POST" }); } catch (e) { /* ignore */ }
    location.href = "/";
  }));

  // Mobile sidebar
  const toggle = document.getElementById("sidebar-toggle");
  if (toggle) toggle.addEventListener("click", () => document.body.classList.toggle("sidebar-open"));

  // Login form
  const loginForm = document.getElementById("login-form");
  if (loginForm) loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = loginForm.querySelector("button[type=submit]");
    showFormError("");
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    if (!email || !password) return showFormError("Please enter your e-mail and password.");
    setBusy(btn, true, "Logging in...");
    try { await api("/api/login", { method: "POST", json: { email, password } }); location.href = safeNext(); }
    catch (err) { showFormError(err.message); setBusy(btn, false); }
  });

  // Register form
  const regForm = document.getElementById("register-form");
  if (regForm) regForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = regForm.querySelector("button[type=submit]");
    showFormError("");
    const payload = { name: document.getElementById("name").value.trim(),
      email: document.getElementById("email").value.trim(), password: document.getElementById("password").value };
    if (!payload.name || !payload.email || !payload.password) return showFormError("Please fill in all fields.");
    setBusy(btn, true, "Creating account...");
    try { await api("/api/register", { method: "POST", json: payload }); location.href = "/dashboard"; }
    catch (err) { showFormError(err.message); setBusy(btn, false); }
  });
});
