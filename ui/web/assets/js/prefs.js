// Per-browser preferences. Storage can be unavailable (private windows), so every access is guarded.

const DEFAULTS = { theme: "system", viewerMode: "orbit", editHints: "on" };
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
