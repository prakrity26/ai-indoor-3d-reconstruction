// Per-browser preferences. Storage can be unavailable (private windows), so every access is guarded.

const DEFAULTS = {
  theme: "system",
  viewerMode: "orbit",
  editHints: "on",
  jobAlerts: "on", // toasts when a job starts, finishes, or fails
  stageAlerts: "on", // short toasts for each pipeline stage
  desktopAlerts: "off", // system notifications when the tab is in the background
  pageTips: "on", // one-time "what to do here" tips on each page
  onboarded: false, // welcome guide shown
  seenTips: [], // page tips already dismissed
  checklistHidden: false, // getting-started checklist dismissed
  visitedStudio: false, // opened any scene in the 3D Studio
  visitedOwnStudio: false, // opened one of the user's own scenes
};
const KEY = "indoor3d.prefs";

export function prefs() {
  try {
    return { ...DEFAULTS, ...(JSON.parse(localStorage.getItem(KEY) || "{}")) };
  } catch {
    return { ...DEFAULTS };
  }
}

export function setPref(key, value) {
  const next = { ...prefs(), [key]: value };
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* not persisted */ }
}

export function applyTheme() {
  const theme = prefs().theme;
  if (theme === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", theme);
}
