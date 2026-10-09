// herd.js — herd health grid (#13), filters, cow profile modal with Chart.js, vet-report download (#8).
import { CONFIG, $, esc } from "./config.js";
import { getHerd, getCow, getSensorReadings, getVetReportUrl } from "./api.js";
import { t } from "./i18n.js";
import { toast } from "./app.js";
let herd = [], filter = "all", chart, readingTimer, lastFocus;
export const getHerdList = () => herd;

export async function refreshHerd() {
  $("#herdGrid").innerHTML = '<div class="skeleton"></div>'.repeat(8);
  try { herd = await getHerd(); render(); } catch { $("#herdGrid").innerHTML = `<p class="empty">${t("error")}</p>`; }
}
function render() {
  const c = s => herd.filter(h => h.status === s).length;
  $("#legend").textContent = `🔴 ${c("red")} · 🟡 ${c("yellow")} · 🟢 ${c("green")}`;
  document.querySelectorAll("#filters button").forEach(b => b.setAttribute("aria-pressed", b.dataset.f === filter));
  const list = herd.filter(h => filter === "all" || h.status === filter);
  $("#herdGrid").innerHTML = list.length ? list.map(h => `<button class="tile ${h.status}" data-id="${h.id}" title="${esc(h.reason)}" aria-label="${esc(h.name)} #${h.id}: ${esc(h.reason)}"><span>🐄</span><b>#${h.id}</b><small>${esc(h.name)}</small></button>`).join("") : `<p class="empty">${t("empty")}</p>`;
}
export function markCow(id, status, reason) {
  const h = herd.find(x => x.id == id); if (!h) return;
  h.status = status; if (reason) h.reason = reason; render();
  document.querySelector(`.tile[data-id="${id}"]`)?.classList.add("pulse");
}
export async function downloadVetReport(id, btn) {
  if (CONFIG.USE_MOCK) return toast(t("pdfMock"), "info");
  if (btn) btn.disabled = true;
  try {
    const r = await fetch(getVetReportUrl(id)); if (!r.ok) throw new Error(r.status);
    const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = `vet_report_cow_${id}.pdf`; a.click(); URL.revokeObjectURL(a.href);
  } catch { toast(t("error"), "error"); }
  if (btn) btn.disabled = false;
}
async function openCow(id) {
  clearInterval(readingTimer);
  readingTimer = null;
  lastFocus = document.activeElement; const h = herd.find(x => x.id == id) || { name: "", status: "green", reason: "" };
  $("#modal").hidden = false; $("#mBody").innerHTML = '<div class="skeleton tall"></div>'; $("#mClose").focus();
  try {
    const [c, readings] = await Promise.all([getCow(id), getSensorReadings(id)]);
    $("#mBody").innerHTML = `<h2 id="mTitle">${esc(h.name)} <small>#${id}</small> <span class="badge ${h.status}">${t(h.status)}</span></h2><p>${esc(h.reason)}</p>
    <dl class="details">${Object.entries(c.details).map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>
    <div class="sensor-heading"><h3>${t("sensorReadings")}</h3><span class="sensor-status"><i></i>${t("simulated")}</span></div>
    <div id="cowReadings" class="sensor-grid"></div>
    <h3>${t("milkChart")}</h3><canvas id="milkChart" height="120"></canvas>
    <h3>${t("healthHistory")}</h3><ul class="timeline">${c.health_history.map(x => `<li><b>${esc(x.date)}</b> ${esc(x.issue)} — ${esc(x.treatment)}</li>`).join("") || `<li>${t("empty")}</li>`}</ul>
    <button id="vetBtn" class="primary">${t("vetReport")}</button>`;
    const updateReadings = () => {
      const ranges = [
        { key: "temperature", amount: .15, min: 36, max: 42, decimals: 1, unit: "°C" },
        { key: "activity", amount: 4, min: 0, max: 120, decimals: 0, unit: "" },
        { key: "rumination", amount: 12, min: 0, max: 720, decimals: 0, unit: "" },
        { key: "milkYield", amount: .25, min: 0, max: 40, decimals: 1, unit: "" }
      ];
      $("#cowReadings").innerHTML = ranges.map(({ key, amount, min, max, decimals, unit }) => {
        const base = Number(readings?.[key]);
        if (!Number.isFinite(base)) return "";
        const scale = 10 ** decimals;
        const value = Math.max(min, Math.min(max, Math.round((base + (Math.random() * 2 - 1) * amount) * scale) / scale));
        const label = t(key);
        const suffix = key === "activity" ? "AU" : key === "rumination" ? t("minutesPerDay") : key === "milkYield" ? "L/day" : unit;
        return `<div class="sensor-card"><span>${label}</span><strong>${value}<small>${suffix}</small></strong></div>`;
      }).join("");
    };
    updateReadings();
    readingTimer = setInterval(updateReadings, 3000);
    chart?.destroy();
    if (window.Chart) chart = new Chart($("#milkChart"), { type: "line", data: { labels: c.milk_history.map(m => m.date.slice(5)), datasets: [{ data: c.milk_history.map(m => m.litres), borderColor: "#367654", backgroundColor: "rgba(54,118,84,.12)", fill: true, tension: .3, pointRadius: 0 }] }, options: { plugins: { legend: { display: false } } } });
    $("#vetBtn").onclick = e => downloadVetReport(id, e.target);
  } catch { clearInterval(readingTimer); readingTimer = null; $("#mBody").innerHTML = `<p>${t("error")}</p>`; }
}
function closeModal() { clearInterval(readingTimer); readingTimer = null; chart?.destroy(); chart = null; $("#modal").hidden = true; lastFocus?.focus(); }
export function initHerd() {
  $("#filters").onclick = e => { const f = e.target.dataset.f; if (f) { filter = f; render(); } };
  $("#herdGrid").onclick = e => { const b = e.target.closest(".tile"); if (b) openCow(b.dataset.id); };
  $("#mClose").onclick = closeModal;
  $("#modal").onclick = e => { if (e.target.id === "modal") closeModal(); };
  document.addEventListener("keydown", e => {
    if ($("#modal").hidden) return;
    if (e.key === "Escape") closeModal();
    if (e.key === "Tab") { // focus trap
      const f = [...$("#modal").querySelectorAll("button:not([disabled])")], a = f[0], z = f.at(-1);
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    }
  });
}
