// photo.js — cattle photo upload, validation/compression and the diagnosis result card (#11).
import { state, $, esc } from "./config.js";
import { diagnose } from "./api.js";
import { t } from "./i18n.js";
import { toast } from "./app.js";
import { getHerdList } from "./herd.js";
const MAX = 5 * 1024 * 1024;

async function shrink(f) { // downscale to <=1600px JPEG
  const img = await createImageBitmap(f), s = Math.min(1, 1600 / Math.max(img.width, img.height)), c = document.createElement("canvas");
  c.width = img.width * s; c.height = img.height * s; c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  return new Promise(r => c.toBlob(b => r(new File([b], f.name.replace(/\.\w+$/, ".jpg"), { type: "image/jpeg" })), "image/jpeg", .8));
}
async function setPhoto(f) {
  if (!f) return;
  if (!f.type.startsWith("image/")) return toast(t("error"), "error");
  if (f.size > MAX) f = await shrink(f);
  if (f.size > MAX) return toast(t("error"), "error");
  state.pendingPhoto = f; $("#prevImg").src = URL.createObjectURL(f);
  $("#photoCow").innerHTML = `<option value="">${t("cowOptional")}</option>` + getHerdList().map(c => `<option value="${c.id}">#${c.id} ${esc(c.name)}</option>`).join("");
  $("#preview").hidden = false;
}
export function clearPhoto() { state.pendingPhoto = null; $("#preview").hidden = true; $("#photoInput").value = ""; }

export async function diagnoseCard(file, cowId) {
  const r = await diagnose(file, cowId), u = r.urgency || "medium";
  return `<div class="diag"><span class="badge ${u}">${t("urgency")}: ${t(u)}</span>
  <ul>${(r.conditions || []).map(c => `<li>${esc(c)}</li>`).join("")}</ul>
  <p><b>${t("advice")}:</b> ${esc(r.advice || "")}</p><div class="warn" role="note">⚠️ ${esc(r.disclaimer || t("disclaimer"))}</div></div>`;
}
export function initPhoto() {
  $("#photoBtn").onclick = () => $("#photoInput").click();
  $("#photoInput").onchange = e => setPhoto(e.target.files[0]);
  $("#rmPhoto").onclick = clearPhoto;
  $("#demoPhoto").onclick = async e => {
    e.preventDefault();
    try { const b = await (await fetch("assets/demo-photos/demo1.svg")).blob(); setPhoto(new File([b], "demo1.svg", { type: b.type || "image/svg+xml" })); }
    catch { toast(t("error"), "error"); }
  };
}
