import { api } from "../api.js";
import { h, button, icon, iconButton, emptyState, statusBadge, timeAgo, modal, field, toast, confirmDialog, fill } from "../ui.js";
import { projectCard, pageHeader, projectThumb, pageTip, nextStep } from "./common.js";

const FILTERS = [["all", "All"], ["succeeded", "Ready"], ["running", "Processing"], ["queued", "Queued"], ["failed", "Failed"]];

export async function render(main, params, ctx) {
  let projects = await api.list();
  let filter = params.query.get("status") || "all";
  let search = "";
  let layout = localStorage.getItem("projects.layout") || "grid";

  const results = h("div");
  const searchInput = h("input", { type: "search", class: "input", placeholder: "Search projects", "aria-label": "Search projects",
    onInput: (event) => { search = event.target.value.toLowerCase(); paint(); } });
  const chips = h("div", { class: "chips" });
  const layoutToggle = h("div", { class: "segmented" });

  function paintControls() {
    fill(chips, ...FILTERS.map(([value, label]) => {
      const count = value === "all" ? projects.length : projects.filter((p) => p.status === value).length;
      return h("button", { type: "button", class: `chip${filter === value ? " on" : ""}`, onClick: () => { filter = value; paintControls(); paint(); } }, `${label} `, h("span", { class: "chip-count", text: String(count) }));
    }));
    fill(layoutToggle, 
      h("button", { type: "button", class: layout === "grid" ? "on" : "", onClick: () => setLayout("grid") }, "Grid"),
      h("button", { type: "button", class: layout === "list" ? "on" : "", onClick: () => setLayout("list") }, "List"));
  }

  function setLayout(next) {
    layout = next;
    try { localStorage.setItem("projects.layout", next); } catch { /* storage unavailable */ }
    paintControls();
    paint();
  }

  function visible() {
    return projects.filter((p) => (filter === "all" || p.status === filter)
      && (!search || p.name.toLowerCase().includes(search) || (p.description || "").toLowerCase().includes(search) || p.filename.toLowerCase().includes(search)));
  }

  function paint() {
    const items = visible();
    if (!projects.length) {
      fill(results, emptyState("folder", "No projects yet", "Every video you upload becomes a project here.", button("Create project", { kind: "primary", iconName: "plus", onClick: () => ctx.navigate("#/new") })));
      return;
    }
    if (!items.length) {
      fill(results, emptyState("folder", "No matches", "Try a different search or filter."));
      return;
    }
    if (layout === "grid") {
      fill(results, h("div", { class: "card-grid" }, ...items.map((p) => projectCard(p, ctx.navigate))));
      return;
    }
    fill(results, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { text: "Project" }), h("th", { text: "Status" }), h("th", { text: "Visibility" }), h("th", { text: "Updated" }), h("th", { class: "right", text: "" }))),
      h("tbody", {}, ...items.map((p) => h("tr", {},
        h("td", {}, h("a", { class: "row-title", href: `#/projects/${p.job_id}` }, h("span", { class: "row-thumb" }, projectThumb(p)), h("span", {}, h("strong", { text: p.name }), h("span", { class: "muted small block", text: p.filename })))),
        h("td", {}, statusBadge(p.status)),
        h("td", {}, h("span", { class: "muted small", text: p.visibility === "public" ? "Shared" : "Private" })),
        h("td", {}, h("span", { class: "muted small", text: timeAgo(p.updated_at || p.created_at) })),
        h("td", { class: "right" }, p.status === "succeeded" ? button("Open", { size: "sm", iconName: "cube", onClick: () => ctx.navigate(`#/studio/${p.job_id}`) }) : null,
          iconButton("info", "Details", () => ctx.navigate(`#/projects/${p.job_id}`)))))))));
  }

  paintControls();
  paint();
  main.append(
    pageHeader("My projects", "All of your reconstructed indoor spaces.", button("New project", { kind: "primary", iconName: "plus", onClick: () => ctx.navigate("#/new") })),
    pageTip("projects"),
    h("div", { class: "toolbar" }, searchInput, chips, layoutToggle),
    results);

  const timer = setInterval(async () => {
    const latest = await api.list().catch(() => null);
    if (!latest) return;
    if (JSON.stringify(latest.map((p) => [p.job_id, p.status, p.progress, p.name])) !== JSON.stringify(projects.map((p) => [p.job_id, p.status, p.progress, p.name]))) {
      projects = latest;
      paintControls();
      paint();
    }
  }, 4000);
  return () => clearInterval(timer);
}

// ---- project detail -----------------------------------------------------------------------------

export function renameDialog(project, onSaved) {
  const nameInput = h("input", { class: "input", value: project.name, maxlength: 120 });
  const descInput = h("textarea", { class: "input", rows: 4, maxlength: 2000 });
  descInput.value = project.description || "";
  modal({
    title: "Edit project",
    body: h("div", { class: "form" }, field("Name", nameInput), field("Description", descInput, "Shown on the project page and the shared scene.")),
    actions: [
      { label: "Cancel" },
      { label: "Save", kind: "primary", onClick: async () => {
        try {
          const updated = await api.update(project.job_id, { name: nameInput.value, description: descInput.value });
          toast("Project saved", "success");
          onSaved(updated);
        } catch (error) {
          toast(error.message, "error");
          return true;
        }
        return false;
      } },
    ],
  });
}

export async function deleteProject(project, ctx) {
  const ok = await confirmDialog({
    title: "Delete project?",
    message: `"${project.name}" and its video, frames, mesh, splat, hotspots, and share link will be permanently removed. This cannot be undone.`,
    confirmLabel: "Delete project",
    danger: true,
  });
  if (!ok) return false;
  try {
    await api.remove(project.job_id);
    toast("Project deleted", "success");
    ctx.navigate("#/projects");
    return true;
  } catch (error) {
    toast(error.message, "error");
    return false;
  }
}

export async function renderDetail(main, params, ctx) {
  let project = await api.get(params.id);
  const tip = pageTip("detail");

  function fact(label, value) {
    return value == null || value === "" ? null : h("div", { class: "fact" }, h("span", { class: "muted small", text: label }), h("strong", { text: String(value) }));
  }

  async function trainSplat() {
    try {
      project = await api.requestSplat(project.job_id);
      toast("Queued for a GPU worker. We'll notify you when training starts and when it's ready.", "success", { title: "Splat requested" });
      paint();
    } catch (error) { toast(error.message, "error"); }
  }

  function splatPanel() {
    const st = project.splat_status || "none";
    const badge = { none: null, queued: statusBadge("queued"), running: statusBadge("running"), succeeded: statusBadge("succeeded"), failed: statusBadge("failed") }[st];
    let body;
    if (st === "none") {
      body = [
        h("p", { class: "muted", text: "A Gaussian splat is the photo-realistic, walkable version of this room. Training needs a GPU worker (Colab or a cloud GPU) and takes about 30–90 minutes." }),
        project.can_train_splat
          ? button("Train photoreal splat", { kind: "primary", iconName: "walk", onClick: trainSplat })
          : h("p", { class: "muted small", text: "This project has no stored video, so a splat cannot be trained from it." }),
      ];
    } else if (st === "queued") {
      body = [
        h("p", { text: "Waiting for a GPU worker to pick this up." }),
        h("p", { class: "muted small", text: "Start one with notebooks/colab_gpu_worker.ipynb (see the README section “Photoreal splats on a GPU”)." }),
      ];
    } else if (st === "running") {
      body = [
        h("div", { class: "stage-box" },
          h("div", { class: "progress-row" }, h("strong", { text: project.splat_stage || "Training" }), h("span", { class: "muted", text: `${project.splat_progress}%` })),
          h("div", { class: "progress progress-running" }, h("div", { class: "progress-fill", style: { width: `${project.splat_progress}%` } }))),
        h("p", { class: "muted small", text: "Training runs on the GPU worker. You can close this page." }),
      ];
    } else if (st === "succeeded") {
      body = [
        h("p", { text: "The photoreal splat is ready. Open the 3D Studio and switch to Walk." }),
        h("div", { class: "row" },
          button("Walk the room", { kind: "primary", iconName: "walk", onClick: () => ctx.navigate(`#/studio/${project.job_id}`) }),
          project.can_train_splat ? button("Train again", { iconName: "refresh", onClick: trainSplat }) : null),
      ];
    } else {
      body = [
        h("div", { class: "callout callout-error" }, icon("alert"), h("div", {}, h("strong", { text: "Splat training failed" }), h("p", { class: "pre", text: project.splat_error || "Unknown error." }))),
        project.can_train_splat ? button("Train again", { iconName: "refresh", onClick: trainSplat }) : null,
      ];
    }
    return h("section", { class: "panel" }, h("div", { class: "panel-head" }, h("h2", { text: "Photoreal splat" }), badge), ...body);
  }

  function paint() {
    const s = project.summary || {};
    const input = project.input || {};
    const video = input.video || {};
    const warnings = [...(input.warnings || []), ...(project.evaluation_warnings || [])];
    fill(main, 
      h("a", { class: "back", href: "#/projects" }, icon("arrowLeft", 16), "My projects"),
      pageHeader(project.name, project.description || (project.origin === "sample" ? "Checked-in sample reconstruction." : "No description yet."),
        project.status === "succeeded" ? button("Open in 3D Studio", { kind: "primary", iconName: "cube", onClick: () => ctx.navigate(`#/studio/${project.job_id}`) }) : null,
        button("Edit", { iconName: "edit", onClick: () => renameDialog(project, (updated) => { project = { ...project, ...updated }; paint(); }) }),
        project.status === "failed" ? button("Retry", { iconName: "refresh", onClick: async () => {
          try { project = await api.retry(project.job_id); toast("Queued again. A worker will pick it up shortly.", "success"); paint(); } catch (error) { toast(error.message, "error"); }
        } }) : null),
      tip,
      h("div", { class: "detail-grid" },
        h("div", { class: "detail-main" },
          h("section", { class: "panel" },
            h("div", { class: "panel-head" }, h("h2", { text: "Reconstruction" }), statusBadge(project.status)),
            project.status === "queued" || project.status === "running"
              ? h("div", { class: "stage-box" }, h("div", { class: "progress-row" }, h("strong", { text: project.stage || "Waiting for a worker" }), h("span", { class: "muted", text: `${project.progress}%` })),
                  h("div", { class: "progress progress-running" }, h("div", { class: "progress-fill", style: { width: `${project.progress}%` } })),
                  project.status === "queued" ? h("p", { class: "muted small", text: "Start a worker with: python -m queue.workers --pipeline mesh" }) : null)
              : null,
            project.status === "failed" ? h("div", { class: "callout callout-error" }, icon("alert"), h("div", {}, h("strong", { text: "Processing failed" }), h("p", { text: project.error || "Unknown error." }))) : null,
            project.origin !== "sample" ? nextStep({
              queued: "Next: a worker picks this up, usually within seconds. You don't need to stay here: you'll get a notification when it starts and when it's ready.",
              running: `Step ${stepNumber(project.progress)} of 9 is running. Most videos take a few minutes. Feel free to leave this page; the bell will tell you when it's done.`,
              succeeded: "Next: open it in the 3D Studio to look around, add hotspots, save viewpoints, and share it.",
              failed: "Press Retry to run it again. If it fails twice, record a new video: move slowly, light the room well, and overlap your path.",
            }[project.status] || "") : null,
            h("div", { class: "facts" },
              fact("Posed / selected frames", s.selected_frames ? `${s.posed_frames ?? "—"} / ${s.selected_frames}` : null),
              fact("Filtered points", s.filtered_points?.toLocaleString()),
              fact("Mesh vertices", s.mesh_vertices?.toLocaleString()),
              fact("Mesh triangles", s.mesh_triangles?.toLocaleString()),
              fact("Detected objects", s.scene_objects),
              fact("Walkable splat", project.splat_url ? "Yes" : "Not yet"),
              fact("Scale", "Relative (not metres)"))),
          splatPanel(),
          warnings.length
            ? h("section", { class: "panel" }, h("div", { class: "panel-head" }, h("h2", { text: "Input quality" })),
                h("ul", { class: "warn-list" }, ...warnings.map((w) => h("li", { class: `warn warn-${w.severity}` }, icon(w.severity === "error" ? "alert" : "info", 16), h("span", { text: w.message || w.code })))))
            : null,
          project.source_url
            ? h("section", { class: "panel" }, h("div", { class: "panel-head" }, h("h2", { text: "Source video" })),
                h("video", { class: "source-video", src: project.source_url, controls: true, preload: "metadata" }),
                h("div", { class: "facts" },
                  fact("File", project.filename),
                  fact("Resolution", video.width ? `${video.width} × ${video.height}` : null),
                  fact("Duration", video.duration_sec ? `${Number(video.duration_sec).toFixed(1)} s` : null),
                  fact("Frame rate", video.fps ? `${Number(video.fps).toFixed(0)} fps` : null),
                  fact("Extracted frames", input.frames || null)))
            : null),
        h("aside", { class: "detail-side" },
          h("section", { class: "panel" }, h("div", { class: "panel-head" }, h("h2", { text: "Files" })),
            project.artifacts && project.artifacts.length
              ? h("ul", { class: "artifact-list" }, ...project.artifacts.map((a) => h("li", {},
                  h("div", {}, h("strong", { text: a.kind }), a.bytes ? h("span", { class: "muted small block", text: formatSize(a.bytes) }) : null),
                  h("a", { class: "icon-btn", href: a.url, download: "", title: `Download ${a.kind}`, "aria-label": `Download ${a.kind}` }, icon("download")))))
              : h("p", { class: "muted small", text: "Files appear here when processing finishes." })),
          h("section", { class: "panel" }, h("div", { class: "panel-head" }, h("h2", { text: "Sharing" })),
            h("p", { class: "muted small", text: project.visibility === "public" ? "Anyone with the link can view this scene." : "Only you can see this scene." }),
            button(project.visibility === "public" ? "Manage sharing" : "Share scene", { iconName: "share", onClick: () => ctx.navigate(`#/studio/${project.job_id}?share=1`), disabled: project.status !== "succeeded" })),
          h("section", { class: "panel" }, h("div", { class: "panel-head" }, h("h2", { text: "Details" })),
            h("div", { class: "facts facts-col" },
              fact("Project id", project.job_id),
              fact("Created", timeAgo(project.created_at)),
              fact("Updated", timeAgo(project.updated_at)),
              fact("Origin", project.origin === "sample" ? "Sample" : "Upload")),
            project.origin !== "sample"
              ? button("Delete project", { kind: "danger-ghost", iconName: "trash", onClick: () => deleteProject(project, ctx), disabled: project.status === "running" })
              : h("p", { class: "muted small", text: "Sample scenes cannot be deleted." })))));
  }

  paint();
  const timer = setInterval(async () => {
    const busy = (st) => st === "queued" || st === "running";
    if (!busy(project.status) && !busy(project.splat_status)) return;
    const latest = await api.get(project.job_id).catch(() => null);
    if (latest && (latest.status !== project.status || latest.progress !== project.progress || latest.stage !== project.stage
      || latest.splat_status !== project.splat_status || latest.splat_progress !== project.splat_progress || latest.splat_stage !== project.splat_stage)) {
      project = latest;
      paint();
    }
  }, 3000);
  return () => clearInterval(timer);
}

function stepNumber(progress) {
  return Math.min(9, Math.round(((progress || 0) / 100) * 9) + 1); // worker reports index*100/9 before each stage
}

function formatSize(bytes) {
  const mb = bytes / (1024 * 1024);
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
