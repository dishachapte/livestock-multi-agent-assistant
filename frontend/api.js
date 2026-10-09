// api.js — the ONLY module that talks to the backend. Real fetch/EventSource or mock.json, chosen by CONFIG.USE_MOCK.
import { CONFIG, state } from "./config.js";
let mock;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const M = async () => (mock ??= await (await fetch("mock.json")).json());
const ok = r => { if (!r.ok) throw new Error(r.status); return r; };
const jget = async p => (await ok(await fetch(CONFIG.API_BASE + p))).json();
const jpost = async p => (await ok(await fetch(CONFIG.API_BASE + p, { method: "POST" }))).json();
// Mock lookup: use the requested language, falling back to English.
const pick = (byLang, lang) => byLang[lang] || byLang.en;

// Real call first (if enabled); on failure or in mock mode use mock.json with a fake delay.
async function call(real, fake) {
  if (!CONFIG.USE_MOCK) { try { return await real(); } catch (e) { console.warn("API failed, using mock:", e); } }
  await sleep(300 + Math.random() * 300);
  return fake(await M());
}

export const getBriefing = lang => call(() => jget(`/api/briefing?lang=${lang}`), m => pick(m.briefing, lang));
export const getHerd = () => call(() => jget("/api/herd"), m => m.herd);
export const getCow = id => call(() => jget(`/api/cow/${id}`), m => m.cow[id] || m.cow["1"]);
export const getSensorReadings = id => call(() => jget(`/api/cow/${id}/readings`), m => {
  const cowId = m.cow[id] ? id : "1";
  const milkHistory = m.cow[cowId].milk_history;
  return {
    ...m.sensor_readings[cowId],
    milkYield: milkHistory[milkHistory.length - 1]?.litres
  };
});
export const diagnose = (file, cowId) => call(async () => {
  const f = new FormData(); f.append("image", file); if (cowId) f.append("cow_id", cowId);
  return (await ok(await fetch(CONFIG.API_BASE + "/api/diagnose", { method: "POST", body: f }))).json();
}, m => m.diagnose);
export const approveAction = id => call(() => jpost(`/api/actions/${id}/approve`),
  m => ({ status: "done", result: pick(m.approve, state.lang)[state.actions[id]?.action.type] || "Done" }));
export const rejectAction = id => call(() => jpost(`/api/actions/${id}/reject`), () => ({ status: "rejected" }));
export const getVetReportUrl = cowId => `${CONFIG.API_BASE}/api/vet-report/${cowId}`;

// Streams SSE events to onEvent(obj). Returns close(). Mock mode replays mock.json -> ask_stream[lang] on a timer.
export function streamAsk(query, lang, onEvent) {
  let closed = false, es; const timers = [];
  const close = () => { closed = true; timers.forEach(clearTimeout); es?.close(); };
  if (!CONFIG.USE_MOCK) {
    es = new EventSource(`${CONFIG.API_BASE}/api/ask?query=${encodeURIComponent(query)}&lang=${lang}`);
    es.onmessage = e => { try { const o = JSON.parse(e.data); onEvent(o); if (o.type === "final") close(); } catch (err) { console.warn("Bad SSE data", err); } };
    es.onerror = () => { close(); onEvent({ type: "error" }); };
  } else {
    M().then(m => pick(m.ask_stream, lang).forEach((ev, i) =>
      timers.push(setTimeout(() => { if (!closed) { onEvent(ev); if (ev.type === "final") close(); } }, (i + 1) * CONFIG.MOCK_STREAM_DELAY_MS))));
  }
  return close;
}
