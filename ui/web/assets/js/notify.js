// Notification centre: a bell with history, plus a background watcher that tells the user what
// their jobs are doing on every page, so nobody has to sit on the Processing jobs page wondering.
//
// The watcher polls GET /jobs, compares each job with what it saw last time, and turns changes
// into notifications: started, each pipeline stage, finished, failed, splat progress, and
// "nothing has picked this up" warnings when no worker is running. The last snapshot is kept in
// localStorage so a job that finished while the tab was closed is reported on the next visit.

import { api } from "./api.js";
import { h, icon, toast, timeAgo, fill } from "./ui.js";
import { prefs } from "./prefs.js";

const HISTORY_KEY = "indoor3d.notifications";
const SNAPSHOT_KEY = "indoor3d.jobSnapshot";
const WARNED_KEY = "indoor3d.jobWarned";
const MAX_HISTORY = 40;

const QUEUED_WARN_SECONDS = 45; // mesh job queued this long → probably no worker running
const SPLAT_WARN_SECONDS = 120; // splat queued this long → probably no GPU worker connected
const STALLED_SECONDS = 300; // running job with no progress update for this long

const FAST_POLL = 3000;
const IDLE_POLL = 15000;

// ---- small storage helpers (storage may be unavailable) ----------------------------------------
function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || "null") ?? fallback; } catch { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* not persisted */ }
}

// ---- history + bell ----------------------------------------------------------------------------
let history = load(HISTORY_KEY, []);
let navigate = (hash) => { location.hash = hash; };
const bells = [];
let panel = null;

function unread() {
  return history.filter((n) => !n.read).length;
}

function paintBells() {
  const count = unread();
  for (const bell of bells) {
    const badge = bell.querySelector(".bell-count");
    badge.textContent = count > 9 ? "9+" : String(count);
    badge.hidden = count === 0;
    bell.setAttribute("aria-label", count ? `Notifications, ${count} unread` : "Notifications");
  }
  const base = document.title.replace(/^\(\d+\+?\)\s*/, "");
  document.title = count && document.hidden ? `(${count}) ${base}` : base;
}

function record(entry) {
  history.unshift({ id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, at: new Date().toISOString(), read: false, ...entry });
  history = history.slice(0, MAX_HISTORY);
  save(HISTORY_KEY, history);
  paintBells();
  if (panel) paintPanel();
}

/**
 * Tell the user something happened. Shows a toast and keeps it in the bell's history.
 *   notify({ title, message, kind, href, actionLabel, toast: true, keep: true, desktop: false })
 */
export function notify({ title, message, kind = "info", href, actionLabel, keep = true, showToast = true, desktop = false, duration }) {
  if (keep) record({ title, message, kind, href });
  if (showToast) {
    toast(message, kind, {
      title,
      duration,
      action: href ? { label: actionLabel || "View", onClick: () => navigate(href) } : undefined,
    });
  }
  if (desktop && document.hidden && prefs().desktopAlerts === "on" && "Notification" in window && Notification.permission === "granted") {
    try {
      const n = new Notification(title || "Indoor Spaces", { body: message, icon: "/assets/favicon.svg", tag: href || title });
      n.onclick = () => { window.focus(); if (href) navigate(href); n.close(); };
    } catch { /* some browsers only allow notifications from a service worker */ }
  }
}

function togglePanel(anchor) {
  if (panel) { closePanel(); return; }
  panel = h("div", { class: "notif-panel", role: "dialog", "aria-label": "Notifications" });
  document.body.append(panel);
  position(anchor);
  paintPanel();
  setTimeout(() => {
    document.addEventListener("mousedown", outside);
    document.addEventListener("keydown", onKey);
  });
}

function position(anchor) {
  const r = anchor.getBoundingClientRect();
  const width = Math.min(360, window.innerWidth - 24);
  panel.style.width = `${width}px`;
  panel.style.top = `${Math.min(r.bottom + 8, window.innerHeight - 200)}px`;
  panel.style.left = `${Math.max(12, Math.min(r.left, window.innerWidth - width - 12))}px`;
}

function outside(event) {
  if (panel && !panel.contains(event.target) && !event.target.closest(".bell")) closePanel();
}
function onKey(event) { if (event.key === "Escape") closePanel(); }

function closePanel() {
  if (!panel) return;
  panel.remove();
  panel = null;
  document.removeEventListener("mousedown", outside);
  document.removeEventListener("keydown", onKey);
  // Opening the panel counts as reading what was in it.
  if (unread()) {
    history = history.map((n) => ({ ...n, read: true }));
    save(HISTORY_KEY, history);
    paintBells();
  }
}

function paintPanel() {
  const items = history.length
    ? h("ul", { class: "notif-list" }, ...history.map((n) =>
        h("li", { class: `notif notif-${n.kind}${n.read ? "" : " unread"}` },
          h("button", { type: "button", class: "notif-item", disabled: !n.href, onClick: () => { closePanel(); if (n.href) navigate(n.href); } },
            h("span", { class: "notif-icon" }, icon({ error: "alert", warning: "alert", success: "check" }[n.kind] || "info", 15)),
            h("span", { class: "notif-text" },
              n.title ? h("strong", { text: n.title }) : null,
              h("span", { text: n.message }),
              h("span", { class: "muted small", text: timeAgo(n.at) || "just now" }))))))
    : h("div", { class: "notif-empty" }, icon("bell", 22), h("p", { class: "muted small", text: "No notifications yet. Updates about your uploads and processing jobs appear here." }));
  fill(panel,
    h("div", { class: "notif-head" },
      h("strong", { text: "Notifications" }),
      history.length ? h("button", { type: "button", class: "link-btn", onClick: () => { history = []; save(HISTORY_KEY, history); paintBells(); paintPanel(); } }, "Clear all") : null),
    items);
}

/** A bell button; mount as many as needed (sidebar and mobile top bar). */
export function bellButton(extraClass = "") {
  const bell = h("button", { type: "button", class: `icon-btn bell ${extraClass}`, title: "Notifications", onClick: (e) => togglePanel(e.currentTarget) },
    icon("bell"), h("span", { class: "bell-count", hidden: true }));
  bells.push(bell);
  paintBells();
  return bell;
}

// ---- connection banner -------------------------------------------------------------------------
let offline = false;
let banner = null;

function setOffline(next) {
  if (next === offline) return;
  offline = next;
  if (offline) {
    banner = h("div", { class: "offline-banner", role: "alert" }, icon("wifiOff", 16),
      h("span", { text: "Can't reach the server. Your work is safe; we'll reconnect automatically. Is the API (python -m api) running?" }));
    document.body.append(banner);
  } else {
    banner?.remove();
    banner = null;
    toast("Connected to the server again.", "success");
  }
}

// ---- job watcher -------------------------------------------------------------------------------
let snapshot = load(SNAPSHOT_KEY, null); // { job_id: {status, stage, splat_status, splat_stage, name} }
let warned = new Set(load(WARNED_KEY, []));
let timer = null;

function secondsSince(iso) {
  const t = new Date(iso || "").getTime();
  return Number.isNaN(t) ? 0 : (Date.now() - t) / 1000;
}

function warnOnce(key, payload) {
  if (warned.has(key)) return;
  warned.add(key);
  save(WARNED_KEY, [...warned].slice(-200));
  notify(payload);
}

function viewingJob(id) {
  return location.hash === `#/projects/${id}` || location.hash === "#/jobs";
}

function compare(job, before) {
  const name = `"${job.name || job.filename || "Your project"}"`;
  const details = `#/projects/${job.job_id}`;
  const alerts = prefs().jobAlerts !== "off";

  if (before && alerts) {
    // ---- mesh pipeline -------------------------------------------------------------------------
    if (before.status !== job.status) {
      if (job.status === "running") {
        notify({ title: "Processing started", message: `${name} was picked up by a worker. We'll let you know when each step finishes.`, kind: "progress", href: details, actionLabel: "Watch progress" });
      } else if (job.status === "succeeded") {
        notify({ title: "Your 3D scene is ready", message: `${name} finished processing. Open it to explore, add hotspots, and share.`, kind: "success", href: `#/studio/${job.job_id}`, actionLabel: "Open in 3D Studio", duration: 10000, desktop: true });
      } else if (job.status === "failed") {
        notify({ title: "Processing failed", message: `${name}: ${job.error || "the pipeline stopped."} Open the project to retry.`, kind: "error", href: details, actionLabel: "See what happened", duration: 0, desktop: true });
      } else if (job.status === "queued" && before.status === "failed") {
        notify({ title: "Retry queued", message: `${name} is waiting for a worker again.`, kind: "info", href: details });
      }
    } else if (job.status === "running" && job.stage && job.stage !== before.stage && prefs().stageAlerts !== "off" && !viewingJob(job.job_id)) {
      // Stage changes are frequent, so they get a short toast and stay out of the history.
      notify({ title: name.replace(/"/g, ""), message: `${job.stage} · ${job.progress || 0}%`, kind: "progress", href: details, actionLabel: "Details", keep: false, duration: 2600 });
    }

    // ---- photoreal splat -----------------------------------------------------------------------
    if ((before.splat_status || "none") !== (job.splat_status || "none")) {
      if (job.splat_status === "queued") {
        notify({ title: "Splat queued", message: `${name} is waiting for a GPU worker. Start the Colab notebook if it isn't running.`, kind: "info", href: details });
      } else if (job.splat_status === "running") {
        notify({ title: "GPU training started", message: `A GPU worker started training the photoreal splat for ${name}. This usually takes 30–90 minutes; you can keep using the app.`, kind: "progress", href: details });
      } else if (job.splat_status === "succeeded") {
        notify({ title: "Photoreal splat ready", message: `${name} can now be explored in Walk mode.`, kind: "success", href: `#/studio/${job.job_id}`, actionLabel: "Walk through it", duration: 10000, desktop: true });
      } else if (job.splat_status === "failed") {
        notify({ title: "Splat training failed", message: `${name}: ${job.splat_error || "the GPU worker stopped."} The mesh is still available.`, kind: "error", href: details, actionLabel: "Details", duration: 0, desktop: true });
      }
    } else if (job.splat_status === "running" && job.splat_stage && job.splat_stage !== before.splat_stage && prefs().stageAlerts !== "off" && !viewingJob(job.job_id)) {
      notify({ title: `Splat · ${name.replace(/"/g, "")}`, message: `${job.splat_stage} · ${job.splat_progress || 0}%`, kind: "progress", href: details, keep: false, duration: 2600 });
    }
  }

  // ---- "are you stuck?" hints: shown once per job, even with alerts off ----------------------------
  if (job.status === "queued" && secondsSince(job.updated_at || job.created_at) > QUEUED_WARN_SECONDS) {
    warnOnce(`queued:${job.job_id}:${job.updated_at}`, {
      title: "Still waiting for a worker",
      message: `${name} hasn't started yet. Usually this means no worker is running. Start one with: python -m queue.workers --pipeline mesh`,
      kind: "warning", href: details, duration: 15000,
    });
  }
  if (job.status === "running" && secondsSince(job.updated_at) > STALLED_SECONDS) {
    warnOnce(`stalled:${job.job_id}:${job.updated_at}`, {
      title: "No progress for a while",
      message: `${name} has been on "${job.stage || "the same step"}" for over ${Math.round(STALLED_SECONDS / 60)} minutes. Large videos can be slow; if the worker stopped, it will be marked failed and you can retry.`,
      kind: "warning", href: details, duration: 15000,
    });
  }
  if (job.splat_status === "queued" && secondsSince(job.splat_updated_at || job.updated_at) > SPLAT_WARN_SECONDS) {
    warnOnce(`splatq:${job.job_id}:${job.splat_updated_at || job.updated_at}`, {
      title: "No GPU worker connected",
      message: `The photoreal splat for ${name} is waiting. Run the worker gateway and the Colab notebook (see the README). The mesh does not need it.`,
      kind: "warning", href: details, duration: 15000,
    });
  }
}

async function poll() {
  let jobs;
  try {
    jobs = await api.list();
    setOffline(false);
  } catch (error) {
    if (error.status === 0) setOffline(true);
    schedule(FAST_POLL);
    return;
  }
  const first = snapshot === null;
  const next = {};
  for (const job of jobs) {
    if (job.origin === "sample") continue;
    const before = first ? null : snapshot[job.job_id];
    // A job we have never seen that already finished/failed: it happened while the tab was closed.
    if (!first && !before && (job.status === "succeeded" || job.status === "failed")) {
      compare(job, { ...job, status: "queued", splat_status: job.splat_status });
    } else {
      compare(job, before);
    }
    next[job.job_id] = { status: job.status, stage: job.stage, splat_status: job.splat_status, splat_stage: job.splat_stage };
  }
  snapshot = next;
  save(SNAPSHOT_KEY, snapshot);
  const busy = jobs.some((j) => ["queued", "running"].includes(j.status) || ["queued", "running"].includes(j.splat_status));
  schedule(busy ? FAST_POLL : IDLE_POLL);
}

function schedule(ms) {
  clearTimeout(timer);
  timer = setTimeout(poll, ms);
}

/** Check right away (e.g. after an upload) instead of waiting for the next tick. */
export function pokeWatcher() {
  schedule(400);
}

export function startNotifications({ navigate: nav }) {
  if (nav) navigate = nav;
  document.addEventListener("visibilitychange", () => { paintBells(); if (!document.hidden) pokeWatcher(); });
  window.addEventListener("resize", () => closePanel());
  poll();
}

/** Ask the browser for permission to show desktop notifications. Resolves to true when allowed. */
export async function requestDesktopPermission() {
  if (!("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  return (await Notification.requestPermission()) === "granted";
}
