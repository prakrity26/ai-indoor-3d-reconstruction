import { api } from "../api.js";
import { h, button, icon, emptyState, statusBadge, progressBar, timeAgo } from "../ui.js";
import { projectCard, pageHeader, captureTips, splatLine, pageTip } from "./common.js";
import { checklist } from "../guide.js";

export async function render(main, _params, ctx) {
  const projects = await api.list();
  const ready = projects.filter((p) => p.status === "succeeded");
  const active = projects.filter((p) => p.status === "queued" || p.status === "running" || p.splat_status === "queued" || p.splat_status === "running");
  const shared = projects.filter((p) => p.visibility === "public");
  const failed = projects.filter((p) => p.status === "failed");

  const stat = (label, value, iconName, href) =>
    h("a", { class: "stat", href }, h("div", { class: "stat-icon" }, icon(iconName)), h("div", {}, h("div", { class: "stat-value", text: String(value) }), h("div", { class: "muted small", text: label })));

  const checklistSlot = h("div");
  const list = checklist(projects, ctx, () => checklistSlot.replaceChildren());
  if (list) checklistSlot.append(list);

  const recent = [...projects].sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || "")).slice(0, 6);

  main.append(
    pageHeader("Dashboard", "Capture a room on your phone, upload it, and explore it in 3D.",
      button("New project", { kind: "primary", iconName: "plus", onClick: () => ctx.navigate("#/new") })),
    pageTip("dashboard"),
    checklistSlot,
    h("div", { class: "stats" },
      stat("Projects", projects.length, "folder", "#/projects"),
      stat("Ready to explore", ready.length, "cube", "#/projects?status=succeeded"),
      stat("Processing", active.length, "activity", "#/jobs"),
      stat("Shared scenes", shared.length, "share", "#/shared")),
    h("div", { class: "dash-grid" },
      h("section", { class: "panel" },
        h("div", { class: "panel-head" }, h("h2", { text: "Recent projects" }), h("a", { href: "#/projects", class: "link", text: "View all" })),
        recent.length
          ? h("div", { class: "card-grid" }, ...recent.map((p) => projectCard(p, ctx.navigate)))
          : emptyState("cube", "No projects yet", "Upload an indoor video to create your first 3D scene.", button("Create project", { kind: "primary", iconName: "plus", onClick: () => ctx.navigate("#/new") }))),
      h("aside", { class: "dash-side" },
        h("section", { class: "panel" },
          h("div", { class: "panel-head" }, h("h2", { text: "Processing" }), h("a", { href: "#/jobs", class: "link", text: "All jobs" })),
          active.length || failed.length
            ? h("ul", { class: "job-mini" }, ...[...active, ...failed.slice(0, 3)].map((job) =>
                h("li", {},
                  h("a", { href: `#/projects/${job.job_id}` },
                    h("div", { class: "job-mini-top" }, h("strong", { text: job.name }), statusBadge(job.status)),
                    job.status === "failed"
                      ? h("span", { class: "small error-text", text: job.error || "Failed" })
                      : job.status === "succeeded"
                        ? null
                        : h("div", {}, progressBar(job.progress, job.status), h("span", { class: "small muted", text: `${job.stage || "Waiting for a worker"} · ${timeAgo(job.created_at)}` })),
                    splatLine(job)))))
            : h("p", { class: "muted small", text: "Nothing is processing right now." })),
        h("section", { class: "panel" },
          h("div", { class: "panel-head" }, h("h2", { text: "Capture tips" })),
          captureTips()))),
  );

  if (active.length) {
    const timer = setInterval(async () => {
      const latest = await api.list().catch(() => null);
      if (!latest) return;
      const changed = latest.some((p) => {
        const old = projects.find((o) => o.job_id === p.job_id);
        return !old || old.status !== p.status || old.progress !== p.progress || old.stage !== p.stage
          || old.splat_status !== p.splat_status || old.splat_progress !== p.splat_progress;
      });
      if (changed) ctx.refresh();
    }, 3000);
    return () => clearInterval(timer);
  }
  return null;
}
