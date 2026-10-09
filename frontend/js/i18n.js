// i18n.js — UI label translation (i18n.json) and language switching. Missing keys fall back to English.
import { state, save } from "./config.js";
let T = {};
export const t = k => (T[state.lang] || {})[k] ?? (T.en || {})[k] ?? k;
export function apply() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach(e => e.textContent = t(e.dataset.i18n));
  document.querySelectorAll("[data-i18n-placeholder]").forEach(e => e.placeholder = t(e.dataset.i18nPlaceholder));
}
export async function initI18n() { T = await (await fetch("i18n.json")).json(); apply(); }
export function setLang(l) { state.lang = l; save(); apply(); document.dispatchEvent(new CustomEvent("langchange")); }
