// First-run guidance: a welcome tour, a getting-started checklist on the dashboard, and a
// one-time tip on each page that says what to do there. Everything can be dismissed, and
// Settings → Guidance brings it all back.

import { h, icon, button, modal, toast, fill } from "./ui.js";
import { prefs, setPref } from "./prefs.js";

// ---- welcome tour --------------------------------------------------------------------------------
const TOUR = [
  {
    icon: "cube",
    title: "Welcome to Indoor Spaces",
    text: "Turn a phone video of a room into an interactive 3D scene you can explore, annotate, and share. This quick tour takes 30 seconds.",
  },
  {
    icon: "upload",
    title: "1. Record and upload",
    text: "Walk slowly around the room for 30–90 seconds, then upload the video on Create project. We check it in the browser first and tell you if anything looks off.",
  },
  {
    icon: "activity",
    title: "2. We process it in the background",
    text: "A worker extracts frames, estimates camera poses and depth, and builds a mesh. You can keep using the app: you get a pop-up as each step finishes, and the bell icon keeps a history.",
  },
  {
    icon: "pin",
    title: "3. Explore and annotate",
    text: "Open the finished scene in the 3D Studio. Drag to orbit, scroll to zoom, press Edit to drop hotspots and save viewpoints.",
  },
  {
    icon: "share",
    title: "4. Share it",
    text: "Make a scene public to get a link and embed code. You can make it private again or reset the link at any time.",
  },
];

/** Show the welcome tour. `force` shows it even when it was already seen. */
export function showWelcome(ctx, { force = false } = {}) {
  if (!force && prefs().onboarded) return;
  let step = 0;
  const body = h("div", { class: "tour" });
  const dots = h("div", { class: "tour-dots" });
  let closeModal = null;

  const finish = (hash) => {
    setPref("onboarded", true);
    closeModal?.();
    if (hash) ctx.navigate(hash);
  };

  function paint() {
    const s = TOUR[step];
    const last = step === TOUR.length - 1;
    fill(dots, ...TOUR.map((_, i) => h("span", { class: `tour-dot${i === step ? " on" : ""}` })));
    fill(body,
      h("div", { class: "tour-icon" }, icon(s.icon, 30)),
      h("h3", { text: s.title }),
      h("p", { class: "muted", text: s.text }),
      dots,
      h("div", { class: "tour-actions" },
        step === 0
          ? button("Skip tour", { kind: "ghost", onClick: () => { finish(); toast("You can replay the tour from Settings → Guidance.", "info"); } })
          : button("Back", { kind: "ghost", onClick: () => { step -= 1; paint(); } }),
        last
          ? h("div", { class: "tour-final" },
              button("Explore the sample room", { onClick: () => finish("#/studio") }),
              button("Create my first project", { kind: "primary", iconName: "plus", onClick: () => finish("#/new") }))
          : button(step === 0 ? "Show me around" : "Next", { kind: "primary", onClick: () => { step += 1; paint(); } })));
  }

  paint();
  closeModal = modal({ title: "Getting started", body, actions: [], onClose: () => setPref("onboarded", true) });
}

// ---- getting-started checklist ---------------------------------------------------------------------
/** Dashboard panel that ticks itself off from real project state. Null when hidden or all done. */
export function checklist(projects, ctx, onHide) {
  if (prefs().checklistHidden) return null;
  const own = projects.filter((p) => p.origin !== "sample");
  const steps = [
    { done: prefs().visitedStudio, title: "Explore the sample room", text: "See what a finished scene looks like.", href: sampleHref(projects), cta: "Open sample" },
    { done: own.length > 0, title: "Upload a room video", text: "30–90 seconds, walking slowly.", href: "#/new", cta: "Create project" },
    { done: own.some((p) => p.status === "succeeded"), title: "Let it process", text: "Takes a few minutes. We notify you when it's ready.", href: "#/jobs", cta: "View jobs" },
    { done: prefs().visitedOwnStudio, title: "Open your scene in the 3D Studio", text: "Add hotspots and save viewpoints.", href: firstReady(own), cta: "Open studio" },
    { done: own.some((p) => p.visibility === "public"), title: "Share a scene", text: "Get a public link or embed code.", href: firstReady(own), cta: "Share" },
  ];
  const doneCount = steps.filter((s) => s.done).length;
  if (doneCount === steps.length) return null;
  const nextIndex = steps.findIndex((s) => !s.done);

  return h("section", { class: "panel checklist" },
    h("div", { class: "panel-head" },
      h("div", {}, h("h2", { text: "Getting started" }), h("span", { class: "muted small", text: `${doneCount} of ${steps.length} done` })),
      h("button", { type: "button", class: "link-btn", onClick: () => { setPref("checklistHidden", true); onHide?.(); toast("Checklist hidden. Bring it back from Settings → Guidance.", "info"); } }, "Hide")),
    h("div", { class: "progress progress-running checklist-bar" }, h("div", { class: "progress-fill", style: { width: `${(doneCount / steps.length) * 100}%` } })),
    h("ol", { class: "checklist-steps" }, ...steps.map((s, i) =>
      h("li", { class: `${s.done ? "done" : ""}${i === nextIndex ? " next" : ""}` },
        h("span", { class: "check-mark" }, s.done ? icon("check", 14) : String(i + 1)),
        h("div", {}, h("strong", { text: s.title }), h("span", { class: "muted small", text: s.text })),
        !s.done && s.href ? button(s.cta, { size: "sm", kind: i === nextIndex ? "primary" : "secondary", onClick: () => ctx.navigate(s.href) }) : null))));
}

function sampleHref(projects) {
  const sample = projects.find((p) => p.origin === "sample" && p.status === "succeeded");
  return sample ? `#/studio/${sample.job_id}` : null;
}
function firstReady(own) {
  const ready = own.find((p) => p.status === "succeeded");
  return ready ? `#/studio/${ready.job_id}` : null;
}

// ---- page tips -----------------------------------------------------------------------------------
const TIPS = {
  dashboard: ["Your home base", "See recent projects, anything processing right now, and how to capture a good video. The bell icon collects every update, so you can always check what happened."],
  projects: ["All your scenes", "Filter by status or search by name. Ready scenes open in the 3D Studio; others open their details page with live progress."],
  new: ["Upload a video", "Pick a 30–90 second video of a room. We check length, resolution, and format before uploading, so you'll know right away if something needs fixing."],
  jobs: ["Live processing", "Every upload runs through 9 steps. This page refreshes itself, and you'll also get a notification when a job finishes or fails, wherever you are in the app."],
  detail: ["Project details", "Progress updates live here. When processing finishes you can open the scene, rename it, request a photoreal splat, or share it."],
  shared: ["Public scenes", "Scenes you've made public. Copy a link or embed code, or make a scene private again."],
  settings: ["Make it yours", "Choose a theme, how the viewer opens, and which notifications you get. Under Guidance you can replay the welcome tour."],
};

/**
 * One-time tip banner for a page. Once dismissed (or with tips off) it returns an empty text node,
 * never null: pages pass the result straight to append(), which would print the word "null".
 */
export function pageTip(key) {
  const tip = TIPS[key];
  const p = prefs();
  if (!tip || p.pageTips === "off" || (p.seenTips || []).includes(key)) return document.createTextNode("");
  const node = h("div", { class: "page-tip", role: "note" },
    h("span", { class: "page-tip-icon" }, icon("compass", 18)),
    h("div", {}, h("strong", { text: tip[0] }), h("span", { class: "muted", text: tip[1] })),
    h("button", { type: "button", class: "link-btn", onClick: () => { dismissTip(key); node.remove(); } }, "Got it"));
  return node;
}

export function dismissTip(key) {
  const seen = new Set(prefs().seenTips || []);
  seen.add(key);
  setPref("seenTips", [...seen]);
}

/** Studio is full-screen, so its guide is a toast instead of a banner. */
export function studioGuide(isOwn) {
  setPref("visitedStudio", true);
  if (isOwn) setPref("visitedOwnStudio", true);
  const p = prefs();
  if (p.pageTips === "off" || (p.seenTips || []).includes("studio")) return;
  dismissTip("studio");
  setTimeout(() => toast("Drag to look around, scroll to zoom, right-drag to pan. Press Edit to add hotspots, then Save. Share gives you a public link.", "info",
    { title: "Welcome to the 3D Studio", duration: 12000 }), 600);
}

export function resetGuidance() {
  setPref("onboarded", false);
  setPref("seenTips", []);
  setPref("checklistHidden", false);
}
