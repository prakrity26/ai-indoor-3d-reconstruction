import { api } from "../api.js";
import { h, button, emptyState, statusBadge, progressBar, timeAgo, toast, iconButton, fill } from "../ui.js";
import { pageHeader, splatLine } from "./common.js";

export async function render(main, _params, ctx) {
  let jobs = (await api.list()).filter((p) => p.origin !== "sample");
  const body = h("div");

  function row(job) {
    return h("tr", {},
      h("td", {}, h("a", { class: "row-title", href: `#/projects/${job.job_id}` }, h("span", {}, h("strong", { text: job.name }), h("span", { class: "muted small block", text: job.filename })))),
      h("td", {}, statusBadge(job.status)),
      h("td", { class: "stage-cell" },
        job.status === "failed"
          ? h("span", { class: "small error-text", text: job.error || "Failed" })
          : h("div", {}, progressBar(job.progress, job.status), h("span", { class: "small muted", text: job.status === "succeeded" ? "Mesh done" : job.stage || "Waiting for a worker" })),
        job.splat_status === "running" ? progressBar(job.splat_progress, "running") : null,
        splatLine(job)),
      h("td", {}, h("span", { class: "muted small", text: timeAgo(job.created_at) })),
      h("td", { class: "right" },
        job.status === "succeeded" ? button("Open", { size: "sm", iconName: "cube", onClick: () => ctx.navigate(`#/studio/${job.job_id}`) }) : null,
        job.status === "failed" ? button("Retry", { size: "sm", iconName: "refresh", onClick: async () => {
          try { await api.retry(job.job_id); toast("Queued again", "success"); await reload(); } catch (error) { toast(error.message, "error"); }
        } }) : null,
        iconButton("info", "Details", () => ctx.navigate(`#/projects/${job.job_id}`))));
  }

  function paint() {
    const active = jobs.filter((j) => j.status === "queued" || j.status === "running" || j.splat_status === "queued" || j.splat_status === "running").length;
    if (!jobs.length) {
      fill(body, emptyState("activity", "No processing jobs", "Uploads appear here while the reconstruction worker processes them.", button("Create project", { kind: "primary", iconName: "plus", onClick: () => ctx.navigate("#/new") })));
      return;
    }
    fill(body, h("div", {},
      active ? h("div", { class: "callout callout-info" }, h("span", { text: `${active} job${active === 1 ? "" : "s"} in progress. This page refreshes automatically.` })) : null,
      h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { text: "Project" }), h("th", { text: "Status" }), h("th", { text: "Stage" }), h("th", { text: "Submitted" }), h("th", { class: "right", text: "" }))),
        h("tbody", {}, ...jobs.map(row))))));
  }

  async function reload() {
    const latest = await api.list().catch(() => null);
    if (!latest) return;
    jobs = latest.filter((p) => p.origin !== "sample");
    paint();
  }

  paint();
  main.append(
    pageHeader("Processing jobs", "Each upload runs through frame extraction, camera poses, depth, point cloud, filtering, mesh, labels, and evaluation.",
      button("Refresh", { iconName: "refresh", onClick: reload })),
    body,
    h("p", { class: "muted small footnote", text: "Mesh jobs need: python -m queue.workers --pipeline mesh. Photoreal splats need a GPU worker: see notebooks/colab_gpu_worker.ipynb." }));
  const timer = setInterval(reload, 3000);
  return () => clearInterval(timer);
}
