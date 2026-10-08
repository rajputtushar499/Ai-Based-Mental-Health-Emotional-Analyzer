/* Dashboard, history, recommendations and privacy-page actions. */
const charts = {};
function drawChart(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}

async function initDashboard() {
  if (!document.getElementById("stat-cards")) return;
  let d;
  try { d = await api("/api/dashboard?tz_offset=" + new Date().getTimezoneOffset()); }
  catch (err) { return toast(err.message, "error"); }

  document.getElementById("stat-total").textContent = d.total;
  document.getElementById("stat-text").textContent = d.types.text;
  document.getElementById("stat-speech").textContent = d.types.speech;
  if (d.total === 0) document.getElementById("empty-state").classList.remove("d-none");
  if (d.latest) {
    document.getElementById("stat-latest").innerHTML = emotionBadge(d.latest.emotion);
    document.getElementById("stat-latest-conf").textContent = `Confidence ${d.latest.confidence}%`;
    document.getElementById("stat-frequent").innerHTML = emotionBadge(d.most_frequent);
    document.getElementById("stat-score").textContent = d.average_score;
    document.getElementById("stat-score-bar").style.width = d.average_score + "%";
  }
  if (d.alert) {
    const box = document.getElementById("alert-box");
    box.innerHTML = `<i class="bi bi-heart me-2"></i>${esc(d.alert.message)}`;
    box.classList.remove("d-none");
  }

  const keys = Object.keys(d.distribution);
  drawChart("chart-distribution", { type: "doughnut",
    data: { labels: keys.map((k) => EMO[k].label.split(" /")[0]), datasets: [{ data: keys.map((k) => d.distribution[k]), backgroundColor: keys.map((k) => EMO[k].color), borderWidth: 2 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } } });
  drawChart("chart-weekly", { type: "line",
    data: { labels: d.weekly.labels, datasets: [
      { label: "Wellbeing score", data: d.weekly.wellbeing, borderColor: "#2fb57d", backgroundColor: "#2fb57d", tension: .3, spanGaps: true },
      { label: "Negative emotions %", data: d.weekly.negative, borderColor: "#e07a5f", backgroundColor: "#e07a5f", tension: .3, spanGaps: true }] },
    options: { maintainAspectRatio: false, scales: { y: { min: 0, max: 100 } }, plugins: { legend: { position: "bottom" } } } });
  drawChart("chart-types", { type: "pie",
    data: { labels: ["Text", "Speech"], datasets: [{ data: [d.types.text, d.types.speech], backgroundColor: ["#2b7a6b", "#8c7bc4"] }] },
    options: { maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } } });

  const body = document.getElementById("recent-body");
  body.innerHTML = d.recent.length ? d.recent.map((r) =>
    `<tr><td>${esc(formatDate(r.created_at))}</td><td><span class="badge-type">${esc(r.input_type)}</span></td><td>${emotionBadge(r.emotion)}${r.demo ? '<span class="badge-demo">demo</span>' : ""}</td><td>${r.confidence}%</td></tr>`).join("")
    : '<tr><td colspan="4" class="text-muted">Nothing here yet.</td></tr>';
}

/* ------------------------------- history ------------------------------- */
function initHistory() {
  const body = document.getElementById("history-body");
  if (!body) return;
  let page = 1, pages = 1, debounce = null;
  const q = { search: document.getElementById("f-search"), emotion: document.getElementById("f-emotion"), type: document.getElementById("f-type") };

  async function load() {
    const params = new URLSearchParams({ page, per_page: 10, search: q.search.value.trim(), emotion: q.emotion.value, type: q.type.value });
    try {
      const d = await api("/api/history?" + params);
      pages = d.pages;
      body.innerHTML = d.items.length ? d.items.map((r) => {
        const tip = r.recommendation.length > 110 ? r.recommendation.slice(0, 110) + "..." : r.recommendation;
        return `<tr><td>${esc(formatDate(r.created_at))}</td><td><span class="badge-type">${esc(r.input_type)}</span></td>
          <td>${emotionBadge(r.emotion)}${r.demo ? '<span class="badge-demo">demo</span>' : ""}</td><td>${r.confidence}%</td>
          <td class="small" title="${esc(r.recommendation)}">${esc(tip)}</td>
          <td class="text-end"><button class="btn btn-sm btn-outline-danger" data-del="${r.id}" aria-label="Delete this item"><i class="bi bi-trash"></i></button></td></tr>`;
      }).join("") : '<tr><td colspan="6" class="text-muted">No results match. Analyze some text or speech first, or change the filters.</td></tr>';
      document.getElementById("history-count").textContent = `${d.total} result${d.total === 1 ? "" : "s"} - page ${d.page} of ${d.pages}`;
      document.getElementById("prev-page").disabled = page <= 1;
      document.getElementById("next-page").disabled = page >= pages;
    } catch (err) { toast(err.message, "error"); }
  }

  q.search.addEventListener("input", () => { clearTimeout(debounce); debounce = setTimeout(() => { page = 1; load(); }, 300); });
  q.emotion.addEventListener("change", () => { page = 1; load(); });
  q.type.addEventListener("change", () => { page = 1; load(); });
  document.getElementById("prev-page").addEventListener("click", () => { if (page > 1) { page--; load(); } });
  document.getElementById("next-page").addEventListener("click", () => { if (page < pages) { page++; load(); } });
  body.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-del]");
    if (!btn || !confirm("Delete this history item?")) return;
    try { await api("/api/history/" + btn.dataset.del, { method: "DELETE" }); toast("History item deleted."); load(); }
    catch (err) { toast(err.message, "error"); }
  });
  document.getElementById("clear-history").addEventListener("click", async () => {
    if (!confirm("Delete ALL of your saved results? This cannot be undone.")) return;
    try { await api("/api/history", { method: "DELETE" }); toast("History cleared."); page = 1; load(); }
    catch (err) { toast(err.message, "error"); }
  });
  load();
}

/* --------------------------- recommendations --------------------------- */
async function initRecommendations() {
  const grid = document.getElementById("rec-grid");
  if (!grid) return;
  try {
    const d = await api("/api/recommendations");
    grid.innerHTML = d.recommendations.map((r) => `<div class="col-md-6 col-xl-4"><div class="card-x h-100 rec-card">
      ${emotionBadge(r.emotion)}<h3 class="mt-2">${esc(r.title)}</h3><ul class="tips mb-0">${r.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></div></div>`).join("");
    if (d.latest_emotion) {
      const note = document.getElementById("latest-note");
      note.innerHTML = `Your latest result was <b>${esc(EMO[d.latest_emotion].label)}</b>. Its tips are listed below.`;
      note.classList.remove("d-none");
    }
  } catch (err) { grid.innerHTML = `<div class="col-12 text-danger">${esc(err.message)}</div>`; }
}

/* ------------------------------ privacy page ------------------------------ */
function initPrivacy() {
  const clear = document.getElementById("privacy-clear");
  if (clear) clear.addEventListener("click", async () => {
    if (!confirm("Delete ALL of your saved results?")) return;
    try { await api("/api/history", { method: "DELETE" }); toast("Your history was deleted."); }
    catch (err) { toast(err.message, "error"); }
  });
  const del = document.getElementById("delete-account");
  if (del) del.addEventListener("click", async () => {
    const password = document.getElementById("delete-password").value;
    if (!password) return toast("Enter your password to confirm.", "error");
    if (!confirm("Permanently delete your account and all data?")) return;
    try { await api("/api/account", { method: "DELETE", json: { password } }); location.href = "/"; }
    catch (err) { toast(err.message, "error"); }
  });
}

document.addEventListener("DOMContentLoaded", () => { initDashboard(); initHistory(); initRecommendations(); initPrivacy(); });
