import { api } from "../api.js";
import { h, button, icon, field, toast, formatBytes, fill } from "../ui.js";
import { pageHeader, captureTips } from "./common.js";

// Checks we can run in the browser before uploading. The worker runs deeper checks in Phase 1.
function inspectVideo(file, config) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.muted = true;
    const done = (info) => resolve({ url, ...info });
    video.onloadedmetadata = () => done({ duration: video.duration, width: video.videoWidth, height: video.videoHeight });
    video.onerror = () => done({ duration: NaN, width: 0, height: 0, unreadable: true });
    video.src = url;
    setTimeout(() => done({ duration: NaN, width: 0, height: 0, unreadable: true }), 8000);
  }).then((info) => ({ ...info, warnings: qualityWarnings(file, info, config) }));
}

function qualityWarnings(file, info, config) {
  const out = [];
  const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
  if (!config.video_extensions.includes(ext)) out.push(["error", `${ext} is not supported. Use ${config.video_extensions.join(", ")}.`]);
  if (file.size > config.max_upload_mb * 1024 * 1024) out.push(["error", `The file is ${formatBytes(file.size)}; the limit is ${config.max_upload_mb} MB.`]);
  if (info.unreadable) {
    out.push(["info", "Your browser cannot preview this format. It can still be uploaded; the server checks it."]);
    return out;
  }
  if (info.duration < 8) out.push(["warning", `Only ${info.duration.toFixed(1)} s long. Aim for 30–90 seconds to cover the room.`]);
  else if (info.duration > 300) out.push(["warning", `${Math.round(info.duration / 60)} minutes long. Processing will be slow; 30–90 seconds is usually enough.`]);
  const shortSide = Math.min(info.width, info.height);
  if (shortSide && shortSide < 480) out.push(["warning", `Low resolution (${info.width}×${info.height}). 720p or higher reconstructs better.`]);
  if (info.height > info.width) out.push(["info", "Portrait video detected. Landscape usually covers walls better."]);
  return out;
}

export async function render(main, _params, ctx) {
  const config = await api.config();
  let file = null;
  let inspected = null;
  let uploading = false;

  const fileInput = h("input", { type: "file", accept: [...config.video_extensions, "video/*"].join(","), hidden: true, onChange: (e) => choose(e.target.files[0]) });
  const nameInput = h("input", { class: "input", placeholder: "e.g. Living room", maxlength: 120, required: true });
  const descInput = h("textarea", { class: "input", rows: 3, maxlength: 2000, placeholder: "What is this space? Anything viewers should know." });
  const splatInput = h("input", { type: "checkbox", checked: true });
  const dropzone = h("div", { class: "dropzone", tabindex: 0, role: "button", "aria-label": "Choose a video to upload",
    onClick: () => fileInput.click(),
    onKeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } } });
  const preview = h("div", { class: "preview" });
  const warningsBox = h("div");
  const progress = h("div", { class: "upload-progress", hidden: true });
  const submit = button("Upload and start processing", { kind: "primary", iconName: "upload", type: "submit", disabled: true });

  function paintDrop() {
    fill(dropzone, 
      h("div", { class: "drop-icon" }, icon("upload", 26)),
      h("strong", { text: file ? file.name : "Drop an indoor video here" }),
      h("span", { class: "muted small", text: file ? `${formatBytes(file.size)} · click to choose another` : `or click to browse · ${config.video_extensions.join(" ")} · up to ${config.max_upload_mb} MB` }));
  }

  async function choose(next) {
    if (!next || uploading) return;
    if (inspected?.url) URL.revokeObjectURL(inspected.url);
    file = next;
    paintDrop();
    if (!nameInput.value) nameInput.value = next.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim();
    inspected = await inspectVideo(next, config);
    fill(preview, ...[
      inspected.unreadable ? null : h("video", { src: inspected.url, controls: true, muted: true, playsinline: true, class: "preview-video" }),
      h("div", { class: "facts" },
        h("div", { class: "fact" }, h("span", { class: "muted small", text: "Size" }), h("strong", { text: formatBytes(next.size) })),
        Number.isFinite(inspected.duration) ? h("div", { class: "fact" }, h("span", { class: "muted small", text: "Duration" }), h("strong", { text: `${inspected.duration.toFixed(1)} s` })) : null,
        inspected.width ? h("div", { class: "fact" }, h("span", { class: "muted small", text: "Resolution" }), h("strong", { text: `${inspected.width} × ${inspected.height}` })) : null),
    ].filter(Boolean));
    const blocking = inspected.warnings.some(([level]) => level === "error");
    fill(warningsBox, 
      inspected.warnings.length
        ? h("ul", { class: "warn-list" }, ...inspected.warnings.map(([level, text]) => h("li", { class: `warn warn-${level}` }, icon(level === "error" ? "alert" : "info", 16), h("span", { text }))))
        : h("div", { class: "callout callout-ok" }, icon("check"), h("span", { text: "Looks good for reconstruction." })));
    submit.disabled = blocking;
  }

  ["dragenter", "dragover"].forEach((type) => dropzone.addEventListener(type, (e) => { e.preventDefault(); dropzone.classList.add("over"); }));
  ["dragleave", "drop"].forEach((type) => dropzone.addEventListener(type, (e) => { e.preventDefault(); dropzone.classList.remove("over"); }));
  dropzone.addEventListener("drop", (e) => choose(e.dataTransfer?.files?.[0]));

  const form = h("form", { class: "panel form", onSubmit: async (event) => {
    event.preventDefault();
    if (!file || uploading) return;
    if (!nameInput.value.trim()) { nameInput.focus(); toast("Give the project a name", "error"); return; }
    uploading = true;
    submit.disabled = true;
    progress.hidden = false;
    const bar = h("div", { class: "progress-fill", style: { width: "0%" } });
    const label = h("span", { class: "small muted", text: "Uploading… 0%" });
    try {
      // Inside try: any failure here must surface as a message, never a silent dead button.
      fill(progress, h("div", { class: "progress progress-running" }, bar), label);
      const project = await api.upload(file, { name: nameInput.value, description: descInput.value, splat: splatInput.checked }, (fraction) => {
        const pct = Math.round(fraction * 100);
        bar.style.width = `${pct}%`;
        label.textContent = pct >= 100 ? "Saving on the server…" : `Uploading… ${pct}%`;
      });
      toast("Upload complete. Processing has been queued.", "success");
      ctx.navigate(`#/projects/${project.job_id}`);
    } catch (error) {
      const message = error.message || String(error);
      toast(message, "error");
      label.textContent = message;
      uploading = false;
      submit.disabled = false;
    }
  } },
  h("h2", { text: "1. Choose a video" }),
  dropzone, fileInput, preview, warningsBox,
  h("h2", { text: "2. Describe the project" }),
  field("Project name", nameInput),
  field("Description (optional)", descInput),
  h("div", { class: "option-card" },
    h("label", { class: "check" }, splatInput, h("strong", { text: "Also train a photoreal Gaussian splat" })),
    h("p", { class: "muted small", text: "Walkable, photo-realistic view of the room. Trained by a GPU worker (for example Colab) and usually takes 30–90 minutes. The mesh is built either way." })),
  progress,
  h("div", { class: "form-actions" }, button("Cancel", { onClick: () => ctx.navigate("#/") }), submit));

  paintDrop();
  main.append(
    pageHeader("Create project", "Upload a standard smartphone video of an indoor space. 360° video is not supported yet."),
    h("div", { class: "create-grid" },
      form,
      h("aside", { class: "panel" },
        h("div", { class: "panel-head" }, h("h2", { text: "Recording guidelines" })),
        captureTips(),
        h("p", { class: "muted small", text: "Reconstruction runs in the background. You can leave this page; progress shows in Processing jobs." }))));

  return () => { if (inspected?.url) URL.revokeObjectURL(inspected.url); };
}
