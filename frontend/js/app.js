// app.js — boot, chat bubbles, SSE event handling, agent panel, memory callout (#5), debate (#1), toasts.
// Each subsystem initialises independently so one failing file (e.g. missing i18n.json) cannot blank the whole app.
import { state, save, $, esc } from "./config.js";
import { streamAsk } from "./api.js";
import { initI18n, t, setLang } from "./i18n.js";
import { initHerd, refreshHerd } from "./herd.js";
import { renderActions } from "./actions.js";
import { loadBriefing, initBriefing } from "./briefing.js";
import { initVoice, speak } from "./voice.js";
import { initPhoto, diagnoseCard, clearPhoto } from "./photo.js";

const AGENTS = { Manager: ["🧑‍🌾", "#4f46e5"], Health: ["🩺", "#dc2626"], Nutrition: ["🌾", "#16a34a"], Breeding: ["🐄", "#db2777"], Inventory: ["📦", "#d97706"], Finance: ["💰", "#0d9488"] };
const TYPING = '<div class="mem"></div><div class="main"><span class="typing" aria-label="…"><i></i><i></i><i></i></span></div>';
let busy = false, closeStream = null;

export function toast(msg, type = "info") {
  const d = document.createElement("div"); d.className = "toast " + type; d.textContent = msg; $("#toasts").append(d); setTimeout(() => d.remove(), 3000);
}
function bubble(who, html) {
  const d = document.createElement("div"); d.className = "msg " + who;
  const time = new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  d.innerHTML = `<div class="body">${html}</div><div class="meta">${time} ${who === "ai" ? '<button class="replay" aria-label="Replay">🔊</button>' : ""}</div>`;
  $("#chat").append(d); d.scrollIntoView({ block: "end" }); return d;
}
function setBusy(b) { busy = b; $("#sendBtn").disabled = b; }

function resetAgents() {
  $("#agents").innerHTML = Object.entries(AGENTS).map(([n, [i, c]]) => `<li class="agent idle" id="ag-${n}" style="--c:${c}"><span class="ico">${i}</span><div><b>${n}</b><p class="finding" hidden></p></div><span class="st"></span></li>`).join("");
  $("#debateList").innerHTML = ""; $("#debateBox").hidden = true;
}
function setAgent(n, s, finding) {
  const el = $("#ag-" + n); if (!el) return;
  el.className = "agent " + s; el.querySelector(".st").innerHTML = s === "working" ? '<span class="spinner"></span>' : s === "done" ? "✅" : "";
  if (finding) { const p = el.querySelector(".finding"); p.textContent = finding; p.hidden = false; }
}
function addDebate(ev) {
  const box = $("#debateList"); $("#debateBox").hidden = false;
  box.insertAdjacentHTML("beforeend", `<div class="dbub ${box.children.length % 2 ? "r" : ""}" style="--c:${(AGENTS[ev.from] || [0, "#555"])[1]}"><b>${esc(ev.from)} → ${esc(ev.to)}</b><p>${esc(ev.text)}</p></div>`);
}
function onEvent(ev, b) {
  switch (ev.type) { // unknown types are ignored silently
    case "memory": b.querySelector(".mem").insertAdjacentHTML("beforeend", `<div class="callout"><b>${t("memory")}</b> ${esc(ev.text)}</div>`); break;
    case "agent_start": setAgent(ev.agent, "working"); break;
    case "agent_done": setAgent(ev.agent, "done", ev.finding); break;
    case "debate": addDebate(ev); break;
    case "final":
      b.querySelector(".main").textContent = ev.summary; renderActions(ev.actions || []); setBusy(false);
      if (state.voiceOn) speak(ev.summary, ev.lang || state.lang);
      break;
    case "error":
      closeStream?.(); setBusy(false); b.querySelector(".main").textContent = t("retry"); toast(t("retry"), "error"); break;
  }
  b.scrollIntoView({ block: "end" });
}

export function sendQuery(text) {
  const inp = $("#chatInput"), q = (text ?? inp.value).trim();
  if (busy || (!q && !state.pendingPhoto)) return;
  inp.value = ""; speechSynthesis?.cancel();
  if (state.pendingPhoto) { // photo diagnosis flow (#11)
    const f = state.pendingPhoto, cow = $("#photoCow").value, url = URL.createObjectURL(f);
    clearPhoto(); setBusy(true);
    bubble("farmer", `<img class="thumb" src="${url}" alt="">${esc(q)}`);
    const b = bubble("ai", TYPING);
    diagnoseCard(f, cow).then(h => b.querySelector(".main").innerHTML = h)
      .catch(() => { b.querySelector(".main").textContent = t("error"); toast(t("error"), "error"); }).finally(() => setBusy(false));
    return;
  }
  setBusy(true); bubble("farmer", esc(q)); resetAgents();
  const b = bubble("ai", TYPING);
  closeStream = streamAsk(q, state.lang, ev => onEvent(ev, b));
}

const updVoice = () => { const b = $("#voiceToggle"); b.textContent = `🔊 ${t("voice")}: ${t(state.voiceOn ? "on" : "off")}`; b.setAttribute("aria-pressed", state.voiceOn); };

// Runs one init step; on failure logs a clear message and keeps the rest of the app working.
function safe(name, fn) {
  try { return fn(); }
  catch (err) { console.error(`[farm-assistant] "${name}" failed to initialise:`, err); return undefined; }
}
async function safeAsync(name, fn) {
  try { return await fn(); }
  catch (err) { console.error(`[farm-assistant] "${name}" failed:`, err); return undefined; }
}

async function boot() {
  // Wiring that depends on no external file runs first, so the page is always interactive.
  safe("agents panel", resetAgents);
  safe("action plan", () => renderActions([]));
  safe("herd", initHerd);
  safe("voice", initVoice);
  safe("photo", initPhoto);
  safe("briefing", initBriefing);
  safe("chat controls", () => {
    $("#sendBtn").onclick = () => sendQuery();
    $("#chatInput").addEventListener("keydown", e => { if (e.key === "Enter") sendQuery(); });
    $("#sugs").onclick = e => { const b = e.target.closest("button"); if (b) sendQuery(b.textContent); };
    $("#agents").onclick = e => e.target.closest(".agent")?.classList.toggle("open");
    $("#chat").onclick = e => { if (e.target.closest(".replay")) speak(e.target.closest(".msg").querySelector(".body").textContent, state.lang, true); };
    $("#voiceToggle").onclick = () => { state.voiceOn = !state.voiceOn; save(); if (!state.voiceOn) speechSynthesis?.cancel(); updVoice(); };
  });

  // Files fetched at runtime: each can fail independently.
  const i18nOk = await safeAsync("i18n.json", initI18n);
  if (i18nOk === undefined) toast("Translations failed to load (i18n.json). Check the console.", "error");
  safe("language selector", () => {
    $("#lang").value = state.lang;
    $("#lang").onchange = e => setLang(e.target.value);
  });
  safe("voice toggle label", updVoice);
  safe("language change listener", () => document.addEventListener("langchange", () => { loadBriefing(); updVoice(); }));

  await safeAsync("herd data", refreshHerd);
  await safeAsync("briefing data", loadBriefing);
}
boot();
