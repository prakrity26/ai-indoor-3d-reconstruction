// Mesh viewer on top of <model-viewer>: orbit / zoom / pan, reset, fullscreen, hotspots, viewpoints.
// Used by the 3D Studio (editable) and the public share page (read-only).

import { h, icon, fill } from "./ui.js";

const IMAGE = /\.(png|jpe?g|gif|webp|avif)(\?|#|$)/i;
const VIDEO = /\.(mp4|webm|ogg)(\?|#|$)/i;

function fixed(n, digits = 4) {
  return Number(n).toFixed(digits).replace(/\.?0+$/, "") || "0";
}

export function mediaNode(url) {
  if (!url) return null;
  if (IMAGE.test(url)) return h("img", { class: "hotspot-media", src: url, alt: "", loading: "lazy" });
  if (VIDEO.test(url)) return h("video", { class: "hotspot-media", src: url, controls: true, preload: "metadata" });
  return h("a", { class: "hotspot-link", href: url, target: "_blank", rel: "noopener noreferrer" }, icon("link", 14), "Open attached media");
}

/**
 * @param {HTMLElement} host - element the viewer fills
 * @param {object} options
 *   src: GLB url
 *   editable: boolean - clicking the model calls onPick({position, normal})
 *   onPick, onHotspotSelect(id), onLoad, onError
 */
export function createMeshViewer(host, options = {}) {
  const mv = h("model-viewer", {
    class: "mesh-viewer",
    "camera-controls": true,
    "touch-action": "none",
    "interaction-prompt": "none",
    "shadow-intensity": "0.6",
    exposure: "1",
    alt: "Reconstructed indoor scene",
    "min-camera-orbit": "auto auto 0.05m",
    "max-field-of-view": "100deg",
    "interpolation-decay": "120",
  });
  const loading = h("div", { class: "viewer-loading" }, h("div", { class: "spinner" }), h("span", { text: "Loading scene…" }));
  host.append(mv, loading);

  let doc = { hotspots: [], viewpoints: [], settings: {} };
  let initial = null;
  let selected = "";
  let editable = Boolean(options.editable);
  let downAt = null;

  mv.addEventListener("load", () => {
    loading.remove();
    const orbit = mv.getCameraOrbit();
    const target = mv.getCameraTarget();
    initial = {
      orbit: `${fixed(orbit.theta)}rad ${fixed(orbit.phi)}rad ${fixed(orbit.radius)}m`,
      target: `${fixed(target.x)}m ${fixed(target.y)}m ${fixed(target.z)}m`,
      fov: `${fixed(mv.getFieldOfView(), 2)}deg`,
    };
    const start = doc.viewpoints.find((v) => v.id === doc.settings.default_viewpoint);
    if (start) goTo(start, true);
    if (options.onLoad) options.onLoad();
  });
  mv.addEventListener("error", () => {
    fill(loading, h("span", { text: "The 3D file could not be loaded." }));
    if (options.onError) options.onError();
  });

  // Distinguish a click from an orbit drag before placing a hotspot.
  mv.addEventListener("pointerdown", (event) => { downAt = { x: event.clientX, y: event.clientY }; });
  mv.addEventListener("click", (event) => {
    if (!editable || !options.onPick || !downAt) return;
    if (Math.hypot(event.clientX - downAt.x, event.clientY - downAt.y) > 5) return;
    if (event.target !== mv) return; // clicks on a hotspot button
    const hit = mv.positionAndNormalFromPoint(event.clientX, event.clientY);
    if (!hit) return;
    options.onPick({
      position: `${fixed(hit.position.x)}m ${fixed(hit.position.y)}m ${fixed(hit.position.z)}m`,
      normal: `${fixed(hit.normal.x)}m ${fixed(hit.normal.y)}m ${fixed(hit.normal.z)}m`,
    });
  });

  function renderHotspots() {
    mv.querySelectorAll(".hotspot").forEach((node) => node.remove());
    for (const spot of doc.hotspots) {
      const open = spot.id === selected;
      const card = h("div", { class: "hotspot-card" },
        h("strong", { text: spot.title }),
        spot.description ? h("p", { text: spot.description }) : null,
        mediaNode(spot.media_url));
      const node = h("button", {
        type: "button",
        class: `hotspot hotspot-${spot.kind}${open ? " open" : ""}`,
        slot: `hotspot-${spot.id}`,
        "data-position": spot.position,
        "data-normal": spot.normal,
        "data-visibility-attribute": "visible",
        "aria-label": spot.title,
        style: { "--spot": spot.color },
        onClick: (event) => {
          event.stopPropagation();
          select(selected === spot.id ? "" : spot.id);
          if (options.onHotspotSelect) options.onHotspotSelect(selected);
        },
      },
      spot.kind === "label" ? h("span", { class: "hotspot-label", text: spot.title }) : h("span", { class: "hotspot-dot" }),
      spot.kind === "label" ? null : card);
      mv.append(node);
    }
  }

  function applySettings() {
    const s = doc.settings || {};
    mv.style.background = s.background || "";
    mv.setAttribute("exposure", String(s.exposure ?? 1));
    mv.setAttribute("shadow-intensity", String(s.shadow ?? 0.6));
    if (s.auto_rotate) mv.setAttribute("auto-rotate", "");
    else mv.removeAttribute("auto-rotate");
  }

  function setDoc(next) {
    doc = next || doc;
    renderHotspots();
    applySettings();
  }

  function select(id) {
    selected = id || "";
    mv.querySelectorAll(".hotspot").forEach((node) => {
      node.classList.toggle("open", node.slot === `hotspot-${selected}`);
    });
  }

  function goTo(view, instant = false) {
    mv.cameraTarget = view.target;
    mv.cameraOrbit = view.orbit;
    mv.fieldOfView = view.fov || "45deg";
    if (instant) mv.jumpCameraToGoal();
  }

  function currentView() {
    const orbit = mv.getCameraOrbit();
    const target = mv.getCameraTarget();
    return {
      orbit: `${fixed(orbit.theta)}rad ${fixed(orbit.phi)}rad ${fixed(orbit.radius)}m`,
      target: `${fixed(target.x)}m ${fixed(target.y)}m ${fixed(target.z)}m`,
      fov: `${fixed(mv.getFieldOfView(), 2)}deg`,
    };
  }

  function reset() {
    const start = doc.viewpoints.find((v) => v.id === doc.settings.default_viewpoint);
    if (start) return goTo(start);
    if (initial) return goTo(initial);
    mv.cameraOrbit = "auto auto auto";
    mv.cameraTarget = "auto auto auto";
    mv.fieldOfView = "auto";
  }

  function zoom(direction) {
    if (typeof mv.zoom === "function") {
      mv.zoom(direction > 0 ? 3 : -3);
      return;
    }
    const orbit = mv.getCameraOrbit();
    const radius = orbit.radius * (direction > 0 ? 0.8 : 1.25);
    mv.cameraOrbit = `${orbit.theta}rad ${orbit.phi}rad ${radius}m`;
  }

  mv.setAttribute("src", options.src); // attribute, not property: works before the element upgrades
  return {
    element: mv,
    setDoc,
    select,
    goTo,
    currentView,
    reset,
    zoom,
    setEditable(value) {
      editable = Boolean(value);
      mv.classList.toggle("editing", editable);
    },
    setAutoRotate(on) {
      doc.settings.auto_rotate = on;
      applySettings();
    },
    destroy() {
      mv.remove();
      loading.remove();
    },
  };
}

/** Walk mode: the Gaussian splat viewer page in an iframe (first-person, W A S D). */
export const SPLAT_UP_ORDER = ["auto", "-y", "+z", "+y", "-z", "+x", "-x"];

export function createSplatViewer(host, plyUrl, up = "auto") {
  const frame = h("iframe", { class: "splat-frame", title: "Walkable Gaussian splat", src: `/viewer?embed=1&up=${encodeURIComponent(up)}&ply=${encodeURIComponent(plyUrl)}`, allow: "fullscreen" });
  host.append(frame);
  return {
    element: frame,
    reset() { frame.src = frame.src; },
    /** Re-frame the camera with a different up axis; returns the axis actually used. */
    setUp(spec) {
      const fn = frame.contentWindow && frame.contentWindow.setSplatUp;
      return typeof fn === "function" ? fn(spec) : null;
    },
    destroy() { frame.remove(); },
  };
}

/** Floating controls shared by the studio and share page. */
export function viewerToolbar({ onReset, onZoomIn, onZoomOut, onFullscreen, onAutoRotate, onFlipUp, autoRotate = false }) {
  const rotate = h("button", { type: "button", class: `tool${autoRotate ? " on" : ""}`, title: "Auto-rotate", "aria-label": "Auto-rotate", "aria-pressed": String(autoRotate),
    onClick: () => {
      const on = !rotate.classList.contains("on");
      rotate.classList.toggle("on", on);
      rotate.setAttribute("aria-pressed", String(on));
      onAutoRotate(on);
    } }, icon("rotate"));
  const tool = (name, title, fn) => (fn ? h("button", { type: "button", class: "tool", title, "aria-label": title, onClick: fn }, icon(name)) : null);
  return h("div", { class: "viewer-tools" },
    tool("zoomIn", "Zoom in", onZoomIn),
    tool("zoomOut", "Zoom out", onZoomOut),
    tool("reset", "Reset camera", onReset),
    onAutoRotate ? rotate : null,
    tool("flip", "Flip up direction (if the room looks sideways or upside down)", onFlipUp),
    tool("expand", "Fullscreen", onFullscreen));
}

export function toggleFullscreen(element) {
  if (document.fullscreenElement) document.exitFullscreen();
  else if (element.requestFullscreen) element.requestFullscreen();
}
