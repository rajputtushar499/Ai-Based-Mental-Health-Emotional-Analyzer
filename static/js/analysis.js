/* Text + speech analysis pages. */
let speechChart = null;

function renderResult(d) {
  const m = EMO[d.emotion] || EMO.neutral;
  const bars = Object.entries(d.scores).map(([k, v]) => {
    const em = EMO[k] || EMO.neutral;
    return `<div class="bar-row"><span>${esc(em.label.split(" /")[0])}</span><div class="bar"><i style="width:${v}%;background:${em.color}"></i></div><b>${v}%</b></div>`;
  }).join("");
  const tips = d.recommendation.tips.map((t) => `<li>${esc(t)}</li>`).join("");
  let html = "";
  if (d.support_notice) html += `<div class="support-alert"><i class="bi bi-heart me-2"></i>${esc(d.support_notice)}</div>`;
  if (d.alert) html += `<div class="support-alert"><i class="bi bi-heart me-2"></i>${esc(d.alert.message)}</div>`;
  html += `<div class="card-x mb-3">
    ${d.demo ? '<div class="alert alert-warning py-2 small">Demo prediction: the AI model was not used for this result.</div>' : ""}
    <div class="result-main">
      <div class="ring" style="--p:${d.confidence};--ring-c:${m.color}"><span>${d.confidence}%</span></div>
      <div><div class="small text-muted">Possible emotional state</div>${emotionBadge(d.emotion)}
      <div class="small text-muted mt-1">Confidence ${d.confidence}%${d.duration ? " &middot; Audio " + d.duration + " s" : ""}</div></div>
    </div>
    <h3 class="h6 mt-4">Emotion probability</h3>${bars}
    ${d.input_type === "speech" ? '<div class="chart-box mt-3" style="height:230px"><canvas id="speech-chart"></canvas></div>' : ""}
  </div>
  <div class="card-x mb-3"><h3 class="h6">AI-generated emotional insight</h3><div class="insight">${esc(d.insight)}</div>
    <div class="small text-muted mt-2">Model: ${esc(d.model)}</div>
    ${d.features ? `<div class="small text-muted mt-1">Librosa features: ${d.features.mfcc_coefficients} MFCC, ${d.features.mel_bands} mel bands, ${d.features.chroma_bins} chroma bins, ZCR ${d.features.zero_crossing_rate}, energy ${d.features.energy_rms}.${d.transcript_used ? " Transcript signals were included." : ""}</div>` : ""}</div>
  <div class="card-x"><h3 class="h6">General wellness recommendation: ${esc(d.recommendation.title)}</h3>
    <ul class="tips mb-2">${tips}</ul><p class="small text-muted mb-0">${esc(d.recommendation.note)}</p></div>`;
  const box = document.getElementById("result");
  box.innerHTML = html;
  box.classList.remove("d-none");
  document.getElementById("result-placeholder").classList.add("d-none");

  if (d.input_type === "speech" && window.Chart) {
    const labels = Object.keys(d.scores).map((k) => EMO[k].label.split(" /")[0]);
    if (speechChart) speechChart.destroy();
    speechChart = new Chart(document.getElementById("speech-chart"), {
      type: "bar",
      data: { labels, datasets: [{ data: Object.values(d.scores), backgroundColor: Object.keys(d.scores).map((k) => EMO[k].color), borderRadius: 6 }] },
      options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: { max: 100, ticks: { callback: (v) => v + "%" } } } },
    });
  }
}

/* ------------------------------ text page ------------------------------ */
function initText() {
  const form = document.getElementById("text-form");
  if (!form) return;
  const input = document.getElementById("text-input");
  const counter = document.getElementById("char-count");
  const max = input.maxLength;
  input.addEventListener("input", () => { counter.textContent = `${input.value.length} / ${max}`; });
  document.querySelectorAll("#sample-chips .chip").forEach((chip) => chip.addEventListener("click", () => {
    input.value = chip.dataset.sample; input.dispatchEvent(new Event("input")); input.focus();
  }));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showFormError("");
    const text = input.value.trim();
    if (text.length < 3) return showFormError("Please enter some text to analyze.");
    const btn = document.getElementById("analyze-btn");
    setBusy(btn, true, "Analyzing...");
    try { renderResult(await api("/api/analyze/text", { method: "POST", json: { text } })); }
    catch (err) { showFormError(err.message); }
    finally { setBusy(btn, false); }
  });
}

/* ----------------------------- speech page ----------------------------- */
function writeStr(view, offset, s) { for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i)); }

/** Convert a decoded AudioBuffer to a mono 16-bit WAV Blob (works in every browser). */
function audioBufferToWav(buffer) {
  const ch = buffer.numberOfChannels, len = buffer.length, mono = new Float32Array(len);
  for (let c = 0; c < ch; c++) { const data = buffer.getChannelData(c); for (let i = 0; i < len; i++) mono[i] += data[i] / ch; }
  const view = new DataView(new ArrayBuffer(44 + len * 2)), sr = buffer.sampleRate;
  writeStr(view, 0, "RIFF"); view.setUint32(4, 36 + len * 2, true); writeStr(view, 8, "WAVE"); writeStr(view, 12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, sr, true);
  view.setUint32(28, sr * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  writeStr(view, 36, "data"); view.setUint32(40, len * 2, true);
  for (let i = 0; i < len; i++) { const s = Math.max(-1, Math.min(1, mono[i])); view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true); }
  return new Blob([view], { type: "audio/wav" });
}

function initSpeech() {
  const card = document.getElementById("speech-card");
  if (!card) return;
  const maxSeconds = parseInt(card.dataset.maxSeconds, 10) || 60;
  const fileInput = document.getElementById("audio-file"), dropZone = document.getElementById("drop-zone");
  const preview = document.getElementById("audio-preview"), fileName = document.getElementById("file-name");
  const analyzeBtn = document.getElementById("speech-analyze-btn");
  const recordBtn = document.getElementById("record-btn"), status = document.getElementById("record-status");
  let selected = null, recorder = null, stream = null, chunks = [], timer = null, previewUrl = null;

  function setFile(file) {
    selected = file; showFormError("");
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl; preview.classList.remove("d-none");
    fileName.textContent = `${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
    analyzeBtn.disabled = false;
  }

  fileInput.addEventListener("change", () => { if (fileInput.files[0]) setFile(fileInput.files[0]); });
  ["dragenter", "dragover"].forEach((ev) => dropZone.addEventListener(ev, (e) => { e.preventDefault(); dropZone.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => dropZone.addEventListener(ev, (e) => { e.preventDefault(); dropZone.classList.remove("drag"); }));
  dropZone.addEventListener("drop", (e) => { if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); });

  // Microphone recording (converted to WAV in the browser)
  const canRecord = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  if (!canRecord) { recordBtn.disabled = true; document.getElementById("record-unsupported").classList.remove("d-none"); }

  function stopRecording() { if (recorder && recorder.state !== "inactive") recorder.stop(); }

  recordBtn.addEventListener("click", async () => {
    if (recorder && recorder.state === "recording") return stopRecording();
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch (e) { return showFormError("Microphone access was blocked. Allow it in your browser, or upload a file instead."); }
    chunks = []; recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    recorder.onstop = async () => {
      clearInterval(timer); stream.getTracks().forEach((t) => t.stop());
      recordBtn.querySelector("span").textContent = "Record with microphone"; status.classList.remove("recording"); status.textContent = "Processing...";
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const buf = await ctx.decodeAudioData(await new Blob(chunks).arrayBuffer());
        ctx.close();
        setFile(new File([audioBufferToWav(buf)], "recording.wav", { type: "audio/wav" }));
        status.textContent = "Recording ready.";
      } catch (e) { status.textContent = ""; showFormError("The recording could not be processed in this browser. Please upload a file instead."); }
    };
    recorder.start();
    let seconds = 0;
    recordBtn.querySelector("span").textContent = "Stop recording"; status.classList.add("recording");
    status.textContent = "Recording... 0s";
    timer = setInterval(() => { seconds++; status.textContent = `Recording... ${seconds}s`; if (seconds >= maxSeconds) stopRecording(); }, 1000);
  });

  analyzeBtn.addEventListener("click", async () => {
    if (!selected) return showFormError("Please choose or record an audio file first.");
    showFormError("");
    const fd = new FormData();
    fd.append("audio", selected, selected.name);
    fd.append("use_transcript", document.getElementById("use-transcript").checked ? "true" : "false");
    setBusy(analyzeBtn, true, "Analyzing audio...");
    try { renderResult(await api("/api/analyze/speech", { method: "POST", formData: fd })); }
    catch (err) { showFormError(err.message); }
    finally { setBusy(analyzeBtn, false); }
  });
}

document.addEventListener("DOMContentLoaded", () => { initText(); initSpeech(); });
