// voice.js — speech in (SpeechRecognition) and out (speechSynthesis), Chrome-first.
import { state, LOCALE, $ } from "./config.js";
import { toast, sendQuery } from "./app.js";
import { t } from "./i18n.js";
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec, listening = false, voices = [];
if ("speechSynthesis" in window) { voices = speechSynthesis.getVoices(); speechSynthesis.addEventListener("voiceschanged", () => voices = speechSynthesis.getVoices()); }

export function speak(text, lang = state.lang, force = false) {
  if (!("speechSynthesis" in window) || (!state.voiceOn && !force)) return;
  speechSynthesis.cancel();
  const clean = text.replace(/[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\uFE0F]/gu, "").replace(/[*_#`>~]/g, "").trim();
  const u = new SpeechSynthesisUtterance(clean), loc = LOCALE[lang] || "en-IN";
  u.lang = loc;
  u.voice = voices.find(v => v.lang === loc) || voices.find(v => v.lang.startsWith(lang)) || null;
  speechSynthesis.speak(u);
}

export function initVoice() {
  const mic = $("#micBtn");
  if (!SR) { mic.disabled = true; mic.title = t("voiceChrome"); return; }
  mic.onclick = () => {
    if (listening) { rec.stop(); return; }
    rec = new SR(); rec.lang = LOCALE[state.lang]; rec.interimResults = true;
    let final = "";
    rec.onstart = () => { listening = true; mic.classList.add("listening"); $("#listenLbl").hidden = false; };
    rec.onresult = e => {
      let txt = ""; for (const r of e.results) txt += r[0].transcript;
      $("#chatInput").value = txt;
      if (e.results[e.results.length - 1].isFinal) final = txt;
    };
    rec.onerror = e => toast(t(e.error === "not-allowed" ? "micDenied" : "noSpeech"), "error");
    rec.onend = () => { listening = false; mic.classList.remove("listening"); $("#listenLbl").hidden = true; if (final) sendQuery(); };
    rec.start();
  };
}
