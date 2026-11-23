// DOM helpers. Text always goes through textContent, never innerHTML, so user input is inert.

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "text") el.textContent = value;
    else if (key === "style" && typeof value === "object") Object.assign(el.style, value);
    else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, String(value));
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

const ICONS = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  folder: "M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  plus: "M12 5v14M5 12h14",
  activity: "M3 12h4l3-8 4 16 3-8h4",
  cube: "M12 2 3 7v10l9 5 9-5V7zM3 7l9 5 9-5M12 12v10",
  share: "M18 8a3 3 0 1 0-2.8-4M6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm12 7a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM8.6 13.5l6.8 4M15.4 6.5l-6.8 4",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  upload: "M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  edit: "M4 20h4L19 9l-4-4L4 16zM14 6l4 4",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  pin: "M12 21s-7-6.3-7-12a7 7 0 0 1 14 0c0 5.7-7 12-7 12zm0-9a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  camera: "M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1zm8 9a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  reset: "M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5",
  expand: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
  zoomIn: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-5-5M11 8v6M8 11h6",
  zoomOut: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-5-5M8 11h6",
  rotate: "M21 12a9 9 0 1 1-3-6.7M21 4v5h-5",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  copy: "M9 9h11v11H9zM5 15H4V4h11v1",
  download: "M12 4v12M7 11l5 5 5-5M4 20h16",
  check: "M5 12l5 5 9-10",
  alert: "M12 3 2 21h20zM12 10v4M12 17.5v.5",
  x: "M6 6l12 12M18 6 6 18",
  refresh: "M20 11a8 8 0 0 0-14.9-3M4 4v4h4M4 13a8 8 0 0 0 14.9 3M20 20v-4h-4",
  menu: "M4 6h16M4 12h16M4 18h16",
  walk: "M13 4a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM9 21l2-6 3 3v3M7 11l3-4 4 2 2 3M11 15l1-6",
  orbit: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2.5 12c0-2.5 4.3-4.5 9.5-4.5s9.5 2 9.5 4.5-4.3 4.5-9.5 4.5S2.5 14.5 2.5 12z",
  arrowLeft: "M19 12H5M11 6l-6 6 6 6",
  info: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 11v6M12 7.5v.5",
  lock: "M6 11h12v10H6zM8 11V7a4 4 0 0 1 8 0v4",
  globe: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM2 12h20M12 2c3 3.5 3 16.5 0 20M12 2c-3 3.5-3 16.5 0 20",
  sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  save: "M5 3h11l5 5v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM7 3v5h8M7 21v-7h10v7",
  flip: "M12 3v18M7 8l5-5 5 5M7 16l5 5 5-5",
  bell: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0",
  compass: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM16.2 7.8l-2.1 6.3-6.3 2.1 2.1-6.3z",
  wifiOff: "M2 2l20 20M8.5 16.5a5 5 0 0 1 7 0M5 13a10 10 0 0 1 5.2-2.8M19 13a10 10 0 0 0-2-1.5M2 8.8a15 15 0 0 1 4.2-2.6M22 8.8A15 15 0 0 0 10.7 5M12 20h.01",
};

export function icon(name, size = 18) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("icon");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", ICONS[name] || ICONS.info);
  svg.append(path);
  return svg;
}

export function button(label, { kind = "secondary", iconName, onClick, title, disabled, type = "button", size } = {}) {
  return h(
    "button",
    { type, class: `btn btn-${kind}${size ? " btn-" + size : ""}`, title, disabled, onClick },
    iconName ? icon(iconName, size === "sm" ? 16 : 18) : null,
    label ? h("span", { text: label }) : null,
  );
}

export function iconButton(name, title, onClick, extra = "") {
  return h("button", { type: "button", class: `icon-btn ${extra}`, title, "aria-label": title, onClick }, icon(name));
}

// ---- status ---------------------------------------------------------------------------------
const STATUS_LABEL = { queued: "Queued", running: "Processing", succeeded: "Ready", failed: "Failed" };

export function statusBadge(status) {
  return h("span", { class: `badge badge-${status}` }, h("span", { class: "dot" }), STATUS_LABEL[status] || status);
}

export function progressBar(value, status) {
  const pct = status === "succeeded" ? 100 : Math.max(0, Math.min(100, value || 0));
  return h("div", { class: `progress progress-${status}`, role: "progressbar", "aria-valuenow": pct, "aria-valuemin": 0, "aria-valuemax": 100 },
    h("div", { class: "progress-fill", style: { width: `${pct}%` } }));
}

// ---- formatting -------------------------------------------------------------------------------
export function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";
  const seconds = Math.round((Date.now() - then.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const units = [["year", 31536000], ["month", 2592000], ["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, size] of units) {
    if (seconds >= size) {
      const n = Math.floor(seconds / size);
      return `${n} ${unit}${n === 1 ? "" : "s"} ago`;
    }
  }
  return "";
}

export function formatBytes(bytes) {
  if (bytes == null) return "";
  const units = ["B", "KB", "MB", "GB"];
  let n = bytes;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatNumber(n) {
  return n == null ? "—" : Number(n).toLocaleString();
}

// ---- toast / modal ------------------------------------------------------------------------------
const TOAST_ICON = { error: "alert", warning: "alert", success: "check", info: "info", progress: "activity" };
const MAX_TOASTS = 4;

/**
 * Show a short message in the corner.
 *   toast("Saved", "success")
 *   toast("Living room is ready", "success", { title: "Processing finished", action: { label: "Open", onClick }, duration: 8000 })
 * kind: info | success | warning | error | progress. duration 0 keeps it until closed.
 * Hovering pauses the timer so there is time to read it. Returns a function that closes it.
 */
export function toast(message, kind = "info", { title, action, duration } = {}) {
  let host = document.getElementById("toasts");
  if (!host) {
    host = h("div", { id: "toasts", role: "region", "aria-label": "Notifications", "aria-live": "polite" });
    document.body.append(host);
  }
  while (host.children.length >= MAX_TOASTS) host.firstChild.remove();
  const ms = duration ?? (kind === "error" ? 7000 : action || title ? 6000 : 3600);
  let timer = null;
  const close = () => {
    clearTimeout(timer);
    node.classList.add("leaving");
    setTimeout(() => node.remove(), 300);
  };
  const start = () => { if (ms > 0) timer = setTimeout(close, ms); };
  const node = h("div", { class: `toast toast-${kind}`, role: kind === "error" ? "alert" : "status" },
    h("span", { class: "toast-icon" }, icon(TOAST_ICON[kind] || "info", 16)),
    h("div", { class: "toast-body" },
      title ? h("strong", { class: "toast-title", text: title }) : null,
      h("span", { text: message }),
      action ? h("button", { type: "button", class: "toast-action", onClick: () => { close(); action.onClick(); } }, action.label) : null),
    h("button", { type: "button", class: "toast-close", "aria-label": "Dismiss", onClick: close }, icon("x", 14)));
  node.addEventListener("mouseenter", () => clearTimeout(timer));
  node.addEventListener("mouseleave", start);
  host.append(node);
  start();
  return close;
}

export function modal({ title, body, actions = [], onClose }) {
  const backdrop = h("div", { class: "modal-backdrop" });
  const close = () => {
    backdrop.remove();
    document.removeEventListener("keydown", onKey);
    if (onClose) onClose();
  };
  const onKey = (event) => { if (event.key === "Escape") close(); };
  const footer = h("div", { class: "modal-actions" }, ...actions.map((action) =>
    button(action.label, { kind: action.kind || "secondary", onClick: async () => {
      if (action.onClick) {
        const keepOpen = await action.onClick();
        if (keepOpen === true) return;
      }
      close();
    } })));
  const dialog = h("div", { class: "modal", role: "dialog", "aria-modal": "true", "aria-label": title },
    h("div", { class: "modal-head" }, h("h2", { text: title }), iconButton("x", "Close", close)),
    h("div", { class: "modal-body" }, body),
    actions.length ? footer : null);
  backdrop.append(dialog);
  backdrop.addEventListener("mousedown", (event) => { if (event.target === backdrop) close(); });
  document.addEventListener("keydown", onKey);
  document.body.append(backdrop);
  const first = dialog.querySelector("input, textarea, select");
  if (first) setTimeout(() => first.focus(), 30);
  return close;
}

export function confirmDialog({ title, message, confirmLabel = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    let answered = false;
    modal({
      title,
      body: h("p", { text: message }),
      actions: [
        { label: "Cancel", onClick: () => { answered = true; resolve(false); } },
        { label: confirmLabel, kind: danger ? "danger" : "primary", onClick: () => { answered = true; resolve(true); } },
      ],
      onClose: () => { if (!answered) resolve(false); },
    });
  });
}

export function field(label, control, hint) {
  return h("label", { class: "field" }, h("span", { class: "field-label", text: label }), control, hint ? h("span", { class: "field-hint", text: hint }) : null);
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to clipboard", "success");
  } catch {
    toast("Copy failed. Select the text and copy it manually.", "error");
  }
}

export function emptyState(iconName, title, message, action) {
  return h("div", { class: "empty" }, h("div", { class: "empty-icon" }, icon(iconName, 28)), h("h3", { text: title }), h("p", { text: message }), action || null);
}

export function absoluteUrl(path) {
  return new URL(path, location.origin).href;
}

/** replaceChildren that skips null/false children (replaceChildren would print "null"). */
export function fill(el, ...children) {
  el.replaceChildren(...children.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false));
}
