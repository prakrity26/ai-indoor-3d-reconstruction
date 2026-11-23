// App shell: sidebar navigation and a hash router. Each page module renders into <main>.

import { h, icon, toast, fill } from "./ui.js";
import { applyTheme } from "./prefs.js";
import * as dashboard from "./pages/dashboard.js";
import * as projects from "./pages/projects.js";
import * as create from "./pages/create.js";
import * as jobs from "./pages/jobs.js";
import * as studio from "./pages/studio.js";
import * as shared from "./pages/shared.js";
import * as settings from "./pages/settings.js";

const NAV = [
  ["#/", "Dashboard", "home"],
  ["#/projects", "My projects", "folder"],
  ["#/new", "Create project", "plus"],
  ["#/jobs", "Processing jobs", "activity"],
  ["#/studio", "3D Studio", "cube"],
  ["#/shared", "Shared scenes", "share"],
  ["#/settings", "Settings", "settings"],
];

const ROUTES = [
  [/^\/$/, dashboard.render, "Dashboard"],
  [/^\/projects$/, projects.render, "My projects"],
  [/^\/projects\/([A-Za-z0-9_-]+)$/, projects.renderDetail, "Project"],
  [/^\/new$/, create.render, "Create project"],
  [/^\/jobs$/, jobs.render, "Processing jobs"],
  [/^\/studio$/, studioPicker, "3D Studio"],
  [/^\/studio\/([A-Za-z0-9_-]+)$/, studio.render, "3D Studio"],
  [/^\/shared$/, shared.render, "Shared scenes"],
  [/^\/settings$/, settings.render, "Settings"],
];

const main = document.getElementById("main");
const nav = document.getElementById("nav");
let cleanup = null;
let leaveGuard = null;
let currentHash = location.hash;
let renderToken = 0;

function parse(hash) {
  const raw = (hash || "#/").replace(/^#/, "") || "/";
  const [path, search = ""] = raw.split("?");
  return { path: path || "/", query: new URLSearchParams(search) };
}

function paintNav(path) {
  fill(nav, ...NAV.map(([href, label, iconName]) => {
    const base = href.slice(1);
    const active = base === "/" ? path === "/" : path === base || path.startsWith(base + "/");
    return h("a", { href, class: `nav-item${active ? " active" : ""}`, "aria-current": active ? "page" : null }, icon(iconName), h("span", { text: label }));
  }));
}

async function studioPicker(target, _params, ctx) {
  // "3D Studio" in the sidebar: open the most recent ready scene, or explain how to get one.
  const { api } = await import("./api.js");
  const ready = (await api.list()).filter((p) => p.status === "succeeded").sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
  if (ready.length) {
    ctx.navigate(`#/studio/${ready[0].job_id}`, { replace: true });
    return null;
  }
  const { emptyState, button } = await import("./ui.js");
  target.append(emptyState("cube", "No scene to open yet", "When a reconstruction finishes, it opens here for exploring and editing.", button("Create project", { kind: "primary", iconName: "plus", onClick: () => ctx.navigate("#/new") })));
  return null;
}

const ctx = {
  navigate(hash, { replace = false } = {}) {
    if (replace) {
      history.replaceState(null, "", hash);
      route();
    } else if (location.hash === hash) {
      route();
    } else {
      location.hash = hash;
    }
  },
  refresh: () => route({ force: true }),
  setLeaveGuard(fn) { leaveGuard = fn; },
};

async function route({ force = false } = {}) {
  if (!force && leaveGuard && location.hash !== currentHash) {
    const ok = await leaveGuard();
    if (!ok) {
      history.replaceState(null, "", currentHash);
      return;
    }
  }
  currentHash = location.hash;
  leaveGuard = null;
  if (cleanup) { try { cleanup(); } catch { /* page already gone */ } cleanup = null; }

  const { path, query } = parse(location.hash);
  paintNav(path);
  document.body.classList.remove("nav-open");
  const match = ROUTES.map(([re, fn, title]) => [path.match(re), fn, title]).find(([m]) => m);
  const token = ++renderToken;
  fill(main, h("div", { class: "page-loading" }, h("div", { class: "spinner" })));
  main.className = "main";
  if (!match) {
    fill(main, h("div", { class: "empty" }, h("h3", { text: "Page not found" }), h("a", { href: "#/", class: "link", text: "Back to the dashboard" })));
    return;
  }
  const [m, render, title] = match;
  document.title = `${title} · Indoor Spaces`;
  const page = h("div", { class: "page" });
  try {
    const result = await render(page, { id: m[1], query }, ctx);
    if (token !== renderToken) { if (typeof result === "function") result(); return; }
    fill(main, page);
    if (page.classList.contains("main-studio")) main.classList.add("main-studio");
    cleanup = typeof result === "function" ? result : null;
  } catch (error) {
    if (token !== renderToken) return;
    fill(main, h("div", { class: "empty" }, icon("alert", 28), h("h3", { text: error.status === 404 ? "Not found" : "Something went wrong" }), h("p", { class: "muted", text: error.message }), h("a", { href: "#/", class: "link", text: "Back to the dashboard" })));
    if (error.status !== 404) toast(error.message, "error");
  }
  main.focus({ preventScroll: true });
}

applyTheme();
document.getElementById("nav-toggle").addEventListener("click", () => document.body.classList.toggle("nav-open"));
document.getElementById("scrim").addEventListener("click", () => document.body.classList.remove("nav-open"));
window.addEventListener("hashchange", () => route());
route({ force: true });
