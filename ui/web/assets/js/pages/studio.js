import { api } from "../api.js";
import { h, button, icon, iconButton, toast, modal, field, copyText, absoluteUrl, confirmDialog, statusBadge, emptyState, fill } from "../ui.js";
import { createMeshViewer, createSplatViewer, viewerToolbar, toggleFullscreen } from "../viewer.js";
import { prefs } from "../prefs.js";
import { embedCode } from "./shared.js";

const KINDS = [["info", "Information marker"], ["label", "Text label"], ["media", "Image / video"]];
const COLORS = ["#6e8bff", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#14b8a6", "#f8fafc"];

export async function render(main, params, ctx) {
  let project = await api.get(params.id);
  if (project.status !== "succeeded" || (!project.mesh_url && !project.splat_url)) {
    main.append(emptyState("cube", "This scene is not ready yet", project.status === "failed" ? project.error || "Processing failed." : "The 3D Studio opens when processing finishes.",
      button("View project", { kind: "primary", onClick: () => ctx.navigate(`#/projects/${project.job_id}`) })));
    return null;
  }

  let doc = await api.studio(project.job_id);
  let savedJson = JSON.stringify(doc);
  let mode = prefs().viewerMode === "walk" && project.splat_url ? "walk" : project.mesh_url ? "orbit" : "walk";
  let editing = false;
  let selected = "";
  let tab = "hotspots";
  let viewer = null;
  let saving = false;

  const dirty = () => JSON.stringify(doc) !== savedJson;

  // ---- layout ---------------------------------------------------------------------------------
  const stage = h("div", { class: "studio-stage" });
  const host = h("div", { class: "viewer-host" });
  const hint = h("div", { class: "viewer-hint" });
  const panelBody = h("div", { class: "studio-panel-body" });
  const tabs = h("div", { class: "tabs", role: "tablist" });
  const saveBtn = button("Save", { kind: "primary", iconName: "save", size: "sm", onClick: () => save() });
  const editBtn = button("Edit", { iconName: "edit", size: "sm", onClick: () => setEditing(!editing) });
  const modeSwitch = h("div", { class: "segmented" });
  const title = h("strong", { class: "studio-title", text: project.name });

  stage.append(host, hint);
  main.classList.add("main-studio");
  main.append(h("div", { class: "studio" },
    h("div", { class: "studio-bar" },
      h("a", { class: "icon-btn", href: `#/projects/${project.job_id}`, title: "Project details", "aria-label": "Project details" }, icon("arrowLeft")),
      h("div", { class: "studio-name" }, title, h("span", { class: "muted small", text: project.origin === "sample" ? "Sample scene" : project.visibility === "public" ? "Shared" : "Private" })),
      modeSwitch,
      h("div", { class: "studio-actions" }, editBtn, button("Share", { iconName: "share", size: "sm", onClick: () => openShare() }), saveBtn)),
    h("div", { class: "studio-body" },
      stage,
      h("aside", { class: "studio-panel" }, tabs, panelBody))));

  // ---- viewer ---------------------------------------------------------------------------------
  function mountViewer() {
    if (viewer) viewer.destroy();
    host.querySelectorAll(".viewer-tools").forEach((n) => n.remove());
    if (mode === "walk") {
      viewer = createSplatViewer(host, project.splat_url);
      host.append(viewerToolbar({ onReset: () => viewer.reset(), onFullscreen: () => toggleFullscreen(stage) }));
    } else {
      viewer = createMeshViewer(host, {
        src: project.mesh_url,
        editable: editing,
        onPick: addHotspot,
        onHotspotSelect: (id) => { selected = id; tab = "hotspots"; paintPanel(); },
      });
      viewer.setDoc(doc);
      viewer.setEditable(editing);
      host.append(viewerToolbar({
        onReset: () => viewer.reset(),
        onZoomIn: () => viewer.zoom(1),
        onZoomOut: () => viewer.zoom(-1),
        onFullscreen: () => toggleFullscreen(stage),
        onAutoRotate: (on) => { doc.settings.auto_rotate = on; viewer.setDoc(doc); paintPanel(); paintBar(); },
        autoRotate: doc.settings.auto_rotate,
      }));
    }
    paintHint();
  }

  function paintHint() {
    let text = "";
    if (mode === "walk") text = "Click the scene, then move with W A S D. Esc releases the mouse. Hotspots are edited in Orbit mode.";
    else if (editing) text = "Edit mode: click the model to place a hotspot. Drag to orbit, right-drag to pan.";
    else if (prefs().editHints !== "off") text = "Drag to orbit · scroll to zoom · right-drag or two fingers to pan · distances are relative";
    hint.textContent = text;
    hint.hidden = !text;
    stage.classList.toggle("editing", editing && mode === "orbit");
  }

  function paintBar() {
    fill(modeSwitch, 
      h("button", { type: "button", class: mode === "orbit" ? "on" : "", disabled: !project.mesh_url, title: project.mesh_url ? "Orbit the mesh" : "No mesh for this scene", onClick: () => setMode("orbit") }, icon("orbit", 16), "Orbit"),
      h("button", { type: "button", class: mode === "walk" ? "on" : "", disabled: !project.splat_url, title: project.splat_url ? "Walk the Gaussian splat" : "A walkable splat needs the GPU worker", onClick: () => setMode("walk") }, icon("walk", 16), "Walk"));
    saveBtn.disabled = !dirty() || saving;
    saveBtn.querySelector("span").textContent = saving ? "Saving…" : dirty() ? "Save" : "Saved";
    editBtn.classList.toggle("btn-active", editing);
    editBtn.disabled = mode !== "orbit";
  }

  function setMode(next) {
    if (next === mode) return;
    mode = next;
    if (mode === "walk") editing = false;
    mountViewer();
    paintBar();
  }

  function setEditing(on) {
    editing = on && mode === "orbit";
    if (viewer?.setEditable) viewer.setEditable(editing);
    if (editing) tab = "hotspots";
    paintHint();
    paintBar();
    paintPanel();
  }

  function changed() {
    if (viewer?.setDoc) viewer.setDoc(doc);
    if (viewer?.select) viewer.select(selected);
    paintBar();
  }

  // ---- hotspots -------------------------------------------------------------------------------
  function addHotspot({ position, normal }) {
    const id = Math.random().toString(36).slice(2, 10);
    doc.hotspots.push({ id, kind: "info", title: `Marker ${doc.hotspots.length + 1}`, description: "", position, normal, media_url: "", color: COLORS[0] });
    selected = id;
    tab = "hotspots";
    changed();
    paintPanel();
    const input = panelBody.querySelector(`[data-hotspot="${id}"] input`);
    if (input) { input.focus(); input.select(); }
  }

  function hotspotEditor(spot) {
    // Update the list row in place; re-rendering the list would steal focus from the input.
    const update = (key) => (event) => {
      spot[key] = event.target.value;
      changed();
      if (key === "title") {
        const label = panelBody.querySelector(`[data-hotspot="${spot.id}"] .item-title`);
        if (label) label.textContent = spot.title;
      }
    };
    const kind = h("select", { class: "input", onChange: (e) => { spot.kind = e.target.value; changed(); paintPanel(); } }, ...KINDS.map(([v, l]) => h("option", { value: v, selected: spot.kind === v }, l)));
    const desc = h("textarea", { class: "input", rows: 3, maxlength: 1000, placeholder: "Description shown when the marker is opened", onInput: update("description") });
    desc.value = spot.description || "";
    return h("div", { class: "hotspot-editor" },
      field("Title", h("input", { class: "input", value: spot.title, maxlength: 80, onInput: update("title") })),
      field("Type", kind),
      spot.kind !== "label" ? field("Description", desc) : null,
      spot.kind === "media" ? field("Image or video link", h("input", { class: "input", value: spot.media_url, placeholder: "https://…/photo.jpg or .mp4", onChange: update("media_url") }), "Must start with https://, http://, or /") : null,
      h("div", { class: "field" }, h("span", { class: "field-label", text: "Colour" }),
        h("div", { class: "swatches" }, ...COLORS.map((c) => h("button", { type: "button", class: `swatch${spot.color === c ? " on" : ""}`, style: { background: c }, title: c, "aria-label": `Colour ${c}`,
          onClick: () => { spot.color = c; changed(); paintPanel(); } })))),
      h("div", { class: "row-between" },
        button("Delete marker", { kind: "danger-ghost", size: "sm", iconName: "trash", onClick: () => {
          doc.hotspots = doc.hotspots.filter((s) => s.id !== spot.id);
          selected = "";
          changed();
          paintPanel();
        } })));
  }

  function hotspotsTab() {
    const list = h("ul", { class: "item-list" });
    fill(list, ...doc.hotspots.map((spot) => {
        const open = spot.id === selected;
        return h("li", { class: `item${open ? " open" : ""}`, "data-hotspot": spot.id },
          h("button", { type: "button", class: "item-head", onClick: () => { selected = open ? "" : spot.id; viewer?.select?.(selected); paintPanel(); } },
            h("span", { class: "item-dot", style: { background: spot.color } }),
            h("span", { class: "item-title", text: spot.title }),
            h("span", { class: "muted small", text: KINDS.find(([v]) => v === spot.kind)?.[1] || "" })),
          open ? hotspotEditor(spot) : null);
      }));
    return h("div", {},
      h("p", { class: "muted small", text: editing ? "Click anywhere on the model to drop a marker." : "Turn on Edit, then click the model to add hotspots, labels, and media." }),
      !editing && mode === "orbit" ? button("Start editing", { size: "sm", iconName: "edit", onClick: () => setEditing(true) }) : null,
      doc.hotspots.length ? list : h("div", { class: "panel-empty" }, icon("pin", 22), h("span", { text: "No hotspots yet" })));
  }

  // ---- viewpoints -----------------------------------------------------------------------------
  function viewpointsTab() {
    const nameInput = h("input", { class: "input", placeholder: "View name, e.g. Entrance", maxlength: 60 });
    const add = () => {
      if (!viewer?.currentView) return;
      const name = nameInput.value.trim() || `View ${doc.viewpoints.length + 1}`;
      doc.viewpoints.push({ id: Math.random().toString(36).slice(2, 10), name, ...viewer.currentView() });
      nameInput.value = "";
      changed();
      paintPanel();
      toast(`Saved "${name}"`, "success");
    };
    nameInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); add(); } });
    return h("div", {},
      h("p", { class: "muted small", text: "Frame the camera, then save the view. Viewers can jump between saved views." }),
      h("div", { class: "copy-row" }, nameInput, button("Save view", { size: "sm", iconName: "camera", onClick: add, disabled: mode !== "orbit" })),
      doc.viewpoints.length
        ? h("ul", { class: "item-list" }, ...doc.viewpoints.map((view) => h("li", { class: "item" },
            h("div", { class: "item-head" },
              h("button", { type: "button", class: "item-title link-btn", onClick: () => viewer?.goTo?.(view), text: view.name }),
              doc.settings.default_viewpoint === view.id ? h("span", { class: "tag", text: "Start view" }) : null,
              h("span", { class: "item-actions" },
                iconButton("eye", "Go to view", () => viewer?.goTo?.(view)),
                iconButton("pin", doc.settings.default_viewpoint === view.id ? "Unset start view" : "Use as start view", () => {
                  doc.settings.default_viewpoint = doc.settings.default_viewpoint === view.id ? "" : view.id;
                  changed(); paintPanel();
                }),
                iconButton("trash", "Delete view", () => {
                  doc.viewpoints = doc.viewpoints.filter((v) => v.id !== view.id);
                  if (doc.settings.default_viewpoint === view.id) doc.settings.default_viewpoint = "";
                  changed(); paintPanel();
                }))))))
        : h("div", { class: "panel-empty" }, icon("camera", 22), h("span", { text: "No saved views" })));
  }

  // ---- scene settings -------------------------------------------------------------------------
  function sceneTab() {
    const s = doc.settings;
    const range = (key, min, max, step) => {
      const out = h("span", { class: "muted small", text: String(s[key]) });
      return h("div", { class: "range-row" }, h("input", { type: "range", min, max, step, value: s[key], onInput: (e) => { s[key] = Number(e.target.value); out.textContent = e.target.value; changed(); } }), out);
    };
    return h("div", { class: "form" },
      field("Background", h("div", { class: "row" }, h("input", { type: "color", value: s.background, onInput: (e) => { s.background = e.target.value; changed(); } }), h("span", { class: "muted small mono", text: s.background }))),
      field("Exposure", range("exposure", 0.2, 2.5, 0.05)),
      field("Shadow", range("shadow", 0, 1, 0.05)),
      h("label", { class: "check" }, h("input", { type: "checkbox", checked: s.auto_rotate, onChange: (e) => { s.auto_rotate = e.target.checked; changed(); mountViewer(); } }), "Auto-rotate when the scene opens"),
      field("Start view", h("select", { class: "input", onChange: (e) => { s.default_viewpoint = e.target.value; changed(); } },
        h("option", { value: "" }, "Automatic framing"),
        ...doc.viewpoints.map((v) => h("option", { value: v.id, selected: s.default_viewpoint === v.id }, v.name)))));
  }

  function infoTab() {
    const sum = project.summary || {};
    const fact = (label, value) => (value == null ? null : h("div", { class: "fact" }, h("span", { class: "muted small", text: label }), h("strong", { text: String(value) })));
    return h("div", {},
      h("p", { text: project.description || "No description." }),
      h("div", { class: "facts facts-col" },
        fact("Status", project.status === "succeeded" ? "Ready" : project.status),
        fact("Representation", [project.mesh_url && "Mesh (GLB)", project.splat_url && "Gaussian splat"].filter(Boolean).join(" + ")),
        fact("Mesh vertices", sum.mesh_vertices?.toLocaleString()),
        fact("Posed frames", sum.selected_frames ? `${sum.posed_frames} / ${sum.selected_frames}` : null),
        fact("Scale", "Relative, not metres")),
      button("Project details", { size: "sm", iconName: "info", onClick: () => ctx.navigate(`#/projects/${project.job_id}`) }));
  }

  function paintPanel() {
    const items = [["hotspots", `Hotspots (${doc.hotspots.length})`], ["viewpoints", `Views (${doc.viewpoints.length})`], ["scene", "Scene"], ["info", "Info"]];
    fill(tabs, ...items.map(([value, label]) => h("button", { type: "button", role: "tab", "aria-selected": String(tab === value), class: tab === value ? "on" : "", onClick: () => { tab = value; paintPanel(); } }, label)));
    const body = { hotspots: hotspotsTab, viewpoints: viewpointsTab, scene: sceneTab, info: infoTab }[tab]();
    const note = mode === "walk" && tab !== "info"
      ? h("div", { class: "callout callout-info" }, h("span", { text: "Walk mode shows the Gaussian splat. Switch to Orbit to edit hotspots and views." }))
      : null;
    fill(panelBody, ...[note, body].filter(Boolean));
  }

  // ---- save / share ---------------------------------------------------------------------------
  async function save() {
    if (!dirty() || saving) return true;
    saving = true;
    paintBar();
    try {
      doc = await api.saveStudio(project.job_id, doc);
      savedJson = JSON.stringify(doc);
      toast("Scene saved", "success");
      return true;
    } catch (error) {
      toast(error.message, "error");
      return false;
    } finally {
      saving = false;
      paintBar();
      changed();
      paintPanel();
    }
  }

  function openShare() {
    const body = h("div", { class: "form" });
    const paintShare = () => {
      const isPublic = project.visibility === "public";
      const link = isPublic ? absoluteUrl(project.share_url) : "";
      fill(body, 
        h("div", { class: "visibility" },
          h("button", { type: "button", class: `vis-option${!isPublic ? " on" : ""}`, onClick: () => setVis("private") }, icon("lock"), h("div", {}, h("strong", { text: "Private" }), h("span", { class: "muted small", text: "Only you can open it." }))),
          h("button", { type: "button", class: `vis-option${isPublic ? " on" : ""}`, onClick: () => setVis("public") }, icon("globe"), h("div", {}, h("strong", { text: "Anyone with the link" }), h("span", { class: "muted small", text: "View only. Hotspots and views included." })))),
        isPublic ? field("Share link", h("div", { class: "copy-row" }, h("input", { class: "input mono", readonly: true, value: link }), button("Copy", { size: "sm", iconName: "copy", onClick: () => copyText(link) }))) : null,
        isPublic ? field("Embed on a website", h("div", { class: "copy-row" }, h("input", { class: "input mono", readonly: true, value: embedCode(project) }), button("Copy", { size: "sm", iconName: "copy", onClick: () => copyText(embedCode(project)) }))) : null,
        isPublic ? h("div", { class: "row-between" },
          button("Open shared view", { size: "sm", iconName: "eye", onClick: () => window.open(project.share_url, "_blank", "noopener") }),
          button("Reset link", { size: "sm", kind: "danger-ghost", iconName: "refresh", onClick: async () => {
            const ok = await confirmDialog({ title: "Reset share link?", message: "The old link stops working immediately. Anyone you shared it with will need the new link.", confirmLabel: "Reset link", danger: true });
            if (!ok) return;
            project = { ...project, ...(await api.rotateShare(project.job_id)) };
            paintShare();
          } })) : null,
        dirty() ? h("div", { class: "callout callout-warning" }, icon("alert"), h("span", { text: "You have unsaved changes. Save so viewers see the latest hotspots." })) : null);
    };
    const setVis = async (visibility) => {
      try {
        project = { ...project, ...(await api.setVisibility(project.job_id, visibility)) };
        toast(visibility === "public" ? "Scene is shared" : "Scene is private", "success");
        paintShare();
      } catch (error) { toast(error.message, "error"); }
    };
    paintShare();
    modal({ title: `Share "${project.name}"`, body, actions: [{ label: "Done", kind: "primary" }] });
  }

  // ---- lifecycle ------------------------------------------------------------------------------
  const onKey = (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") { event.preventDefault(); save(); }
    if (event.key === "Escape" && editing && !document.querySelector(".modal")) setEditing(false);
  };
  const onUnload = (event) => { if (dirty()) { event.preventDefault(); event.returnValue = ""; } };
  document.addEventListener("keydown", onKey);
  window.addEventListener("beforeunload", onUnload);
  ctx.setLeaveGuard(async () => {
    if (!dirty()) return true;
    return confirmDialog({ title: "Leave without saving?", message: "Your hotspot and view changes will be lost.", confirmLabel: "Leave", danger: true });
  });

  paintBar();
  paintPanel();
  mountViewer();
  if (params.query.get("share") === "1") openShare();

  return () => {
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("beforeunload", onUnload);
    main.classList.remove("main-studio");
    if (viewer) viewer.destroy();
  };
}
