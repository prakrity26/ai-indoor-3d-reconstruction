// Building blocks shared by several pages.

import { h, icon, statusBadge, progressBar, timeAgo } from "../ui.js";
export { pageTip } from "../guide.js";

/** "What happens next" line so the user always knows whether to wait, act, or leave. */
export function nextStep(text) {
  return h("div", { class: "next-step" }, icon("compass", 16), h("span", { text }));
}

export function projectThumb(project) {
  const box = h("div", { class: "thumb" });
  if (project.thumbnail_url) {
    box.append(h("img", { src: project.thumbnail_url, alt: "", loading: "lazy" }));
  } else {
    box.append(h("div", { class: "thumb-placeholder" }, icon(project.status === "failed" ? "alert" : "cube", 30)));
  }
  if (project.status !== "succeeded") {
    box.append(h("div", { class: "thumb-overlay" }, statusBadge(project.status)));
  }
  return box;
}

export function projectCard(project, navigate) {
  const target = project.status === "succeeded" ? `#/studio/${project.job_id}` : `#/projects/${project.job_id}`;
  const meta = [];
  if (project.origin === "sample") meta.push("Sample");
  if (project.visibility === "public") meta.push("Shared");
  meta.push(timeAgo(project.updated_at || project.created_at) || "");
  return h("a", { class: "project-card", href: target },
    projectThumb(project),
    h("div", { class: "project-card-body" },
      h("div", { class: "project-card-title" }, h("strong", { text: project.name }), project.status === "succeeded" ? statusBadge("succeeded") : null),
      h("div", { class: "muted small", text: meta.filter(Boolean).join(" · ") }),
      project.status === "running" || project.status === "queued"
        ? h("div", { class: "card-progress" }, progressBar(project.progress, project.status), h("span", { class: "small muted", text: project.stage || "Waiting for a worker" }))
        : null,
      project.status === "failed" ? h("div", { class: "small error-text", text: project.error || "Processing failed." }) : null,
      splatLine(project)));
}

/** One line about the photoreal splat, or null when none was requested. */
export function splatLine(project) {
  const s = project.splat_status;
  if (!s || s === "none") return null;
  const text = {
    queued: "Splat: waiting for a GPU worker",
    running: `Splat: ${project.splat_stage || "training"} · ${project.splat_progress}%`,
    succeeded: "Photoreal splat ready",
    failed: "Splat failed",
  }[s];
  return h("div", { class: `splat-line splat-${s}` }, icon(s === "succeeded" ? "walk" : s === "failed" ? "alert" : "activity", 14), h("span", { text }));
}

export function pageHeader(title, subtitle, ...actions) {
  return h("div", { class: "page-header" },
    h("div", {}, h("h1", { text: title }), subtitle ? h("p", { class: "muted", text: subtitle }) : null),
    actions.length ? h("div", { class: "page-actions" }, ...actions) : null);
}

export function captureTips() {
  const tips = [
    ["Move slowly", "Walk steadily and keep the camera moving; avoid fast turns."],
    ["Light the room", "Turn lights on. Dark or flickering scenes reconstruct poorly."],
    ["Overlap your path", "Circle the room and revisit spots so frames overlap."],
    ["Stay horizontal", "Hold the phone level at chest height, landscape works best."],
    ["30–90 seconds", "Long enough to cover the room, short enough to process quickly."],
    ["Avoid mirrors and glass", "Reflective and blank surfaces confuse depth estimation."],
  ];
  return h("ul", { class: "tips" }, ...tips.map(([title, text]) =>
    h("li", {}, h("span", { class: "tip-icon" }, icon("check", 14)), h("div", {}, h("strong", { text: title }), h("span", { class: "muted", text: text })))));
}
