// actions.js — Action Plan cards with Approve / Reject (#6). One decision per card, tracked in state.actions.
import { state, $, esc } from "./config.js";
import { approveAction, rejectAction } from "./api.js";
import { markCow, downloadVetReport } from "./herd.js";
import { toast } from "./app.js";
import { t } from "./i18n.js";
const ICON = { vet_visit: "🩺", reorder: "📦", isolate: "🚫", feed_change: "🌾", vet_report: "📄" };

export function renderActions(list) {
  const box = $("#actionList");
  if (!list.length) { box.innerHTML = `<p class="empty">${t("noActions")}</p>`; return; }
  state.actions = {}; list.forEach(a => state.actions[a.id] = { action: a, status: "pending" });
  const rank = { high: 0, medium: 1, low: 2 };
  box.innerHTML = [...list].sort((a, b) => rank[a.priority] - rank[b.priority]).map(a => `<article class="act ${a.priority}" id="act-${a.id}">
    <span class="badge ${a.priority}">${t(a.priority)}</span><span class="ico" aria-hidden="true">${ICON[a.type] || "📋"}</span><p>${esc(a.text)}</p>
    <div class="btns"><button class="ok" data-a="approve" data-id="${a.id}">${t("approve")}</button><button data-a="reject" data-id="${a.id}">${t("reject")}</button></div></article>`).join("");
}

async function act(id, kind) {
  const s = state.actions[id]; if (!s || s.status !== "pending") return;
  s.status = "busy";
  const card = $("#act-" + id), box = card.querySelector(".btns"), orig = box.innerHTML;
  box.innerHTML = '<span class="spinner" role="status"></span>';
  try {
    if (kind === "approve") {
      const r = await approveAction(id), a = s.action, p = a.params || {};
      s.status = "done"; box.innerHTML = `<span class="ok res">✅ ${esc(r.result)}</span>`; toast(r.result, "success");
      if (a.type === "vet_visit") (p.cows || []).forEach(c => { markCow(c, "red"); downloadVetReport(c); });
      if (a.type === "isolate") markCow(p.cow ?? p.cows?.[0], "red");
    } else {
      await rejectAction(id); s.status = "rejected";
      card.classList.add("rejected"); box.innerHTML = `<span>❌ ${t("rejected")}</span>`;
    }
  } catch { s.status = "pending"; box.innerHTML = orig; toast(t("error"), "error"); }
}
$("#actionList").addEventListener("click", e => { const b = e.target.closest("button[data-a]"); if (b) act(b.dataset.id, b.dataset.a); });
