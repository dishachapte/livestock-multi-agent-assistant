// briefing.js — morning briefing banner (#3): priority chips, refresh, spoken once after first user interaction.
import { state, $, esc } from "./config.js";
import { getBriefing } from "./api.js";
import { t } from "./i18n.js";
import { speak } from "./voice.js";
let text = "", spoken = false;
const rank = { high: 0, medium: 1, low: 2 };

export async function loadBriefing() {
  const c = $("#briefChips"); c.innerHTML = '<span class="shimmer"></span>';
  try {
    const alerts = (await getBriefing(state.lang)).alerts.sort((a, b) => rank[a.priority] - rank[b.priority]);
    c.innerHTML = alerts.map(a => `<span class="chip ${a.priority}">${esc(a.text)}</span>`).join('<i aria-hidden="true">·</i>') || t("empty");
    text = alerts.map(a => a.text).join(". ");
  } catch { c.innerHTML = `<span>${t("error")}</span>`; }
}
export const playBriefing = () => text && speak(text, state.lang, true);
export function initBriefing() {
  $("#refreshBrief").onclick = loadBriefing;
  $("#playBrief").onclick = playBriefing;
  // Autoplay rules: only speak after the first click/tap.
  document.addEventListener("pointerdown", () => { if (!spoken && state.voiceOn && text) { spoken = true; playBriefing(); } }, { once: true });
}
