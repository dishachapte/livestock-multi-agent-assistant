// config.js — USE_MOCK flag, API base, shared state (language, voice) and tiny DOM helpers.
export const CONFIG = {
  USE_MOCK: false,
  API_BASE: "http://localhost:8000",
  DEFAULT_LANG: "hi",
  MOCK_STREAM_DELAY_MS: 700
};
const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
export const state = { lang: load("lang", CONFIG.DEFAULT_LANG), voiceOn: load("voiceOn", true), pendingPhoto: null, actions: {} };
export const save = () => { localStorage.setItem("lang", JSON.stringify(state.lang)); localStorage.setItem("voiceOn", JSON.stringify(state.voiceOn)); };
export const LOCALE = { en: "en-IN", hi: "hi-IN", ta: "ta-IN", te: "te-IN", mr: "mr-IN", kn: "kn-IN", bn: "bn-IN" };
export const $ = (s, r = document) => r.querySelector(s);
export const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
