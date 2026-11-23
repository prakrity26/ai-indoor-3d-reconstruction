import { api } from "../api.js";
import { h, field, toast, button } from "../ui.js";
import { pageHeader, pageTip } from "./common.js";
import { requestDesktopPermission } from "../notify.js";
import { showWelcome, resetGuidance } from "../guide.js";
import { prefs, setPref, applyTheme } from "../prefs.js";

export async function render(main, _params, ctx) {
  const [config, health] = await Promise.all([api.config().catch(() => null), api.health().catch((e) => ({ status: "down", database: e.message }))]);

  const select = (key, options) => {
    const el = h("select", { class: "input", onChange: async (e) => {
      if (key === "desktopAlerts" && e.target.value === "on" && !(await requestDesktopPermission())) {
        e.target.value = "off";
        toast("Your browser blocked notifications for this site. Allow them in the browser's site settings, then try again.", "warning", { title: "Desktop alerts not enabled" });
        return;
      }
      setPref(key, e.target.value);
      if (key === "theme") applyTheme();
      toast("Preference saved", "success", { duration: 1800 });
    } },
      ...options.map(([value, label]) => h("option", { value, selected: prefs()[key] === value }, label)));
    return el;
  };
  const row = (label, value) => h("div", { class: "fact" }, h("span", { class: "muted small", text: label }), h("strong", { text: value }));

  main.append(
    pageHeader("Settings", "Preferences are stored in this browser."),
    pageTip("settings"),
    h("div", { class: "settings-grid" },
      h("section", { class: "panel form" },
        h("div", { class: "panel-head" }, h("h2", { text: "Appearance" })),
        field("Theme", select("theme", [["system", "Match system"], ["light", "Light"], ["dark", "Dark"]])),
        field("Default viewer mode", select("viewerMode", [["orbit", "Orbit (mesh)"], ["walk", "Walk (Gaussian splat, when available)"]]), "Studio opens in this mode when the scene supports it."),
        field("Hotspot placement hint", select("editHints", [["on", "Show"], ["off", "Hide"]]))),
      h("section", { class: "panel form" },
        h("div", { class: "panel-head" }, h("h2", { text: "Notifications" })),
        field("Job updates", select("jobAlerts", [["on", "Notify me"], ["off", "Don't notify"]]), "When a job starts, finishes, or fails, on any page."),
        field("Step-by-step progress", select("stageAlerts", [["on", "Show each step"], ["off", "Only start and finish"]]), "Short pop-ups as each of the 9 processing steps begins."),
        field("Desktop alerts", select("desktopAlerts", [["off", "Off"], ["on", "On, when this tab is in the background"]]), "Your browser will ask for permission the first time.")),
      h("section", { class: "panel form" },
        h("div", { class: "panel-head" }, h("h2", { text: "Guidance" })),
        field("Page tips", select("pageTips", [["on", "Show"], ["off", "Hide"]]), "A short note at the top of each page the first time you visit it."),
        h("div", { class: "row", style: { flexWrap: "wrap" } },
          button("Replay welcome tour", { iconName: "compass", onClick: () => showWelcome(ctx, { force: true }) }),
          button("Reset all tips", { iconName: "reset", onClick: () => { resetGuidance(); setPref("onboarded", true); toast("Tips and the getting-started checklist will show again.", "success"); } }))),
      h("section", { class: "panel" },
        h("div", { class: "panel-head" }, h("h2", { text: "Platform" }), h("span", { class: `badge badge-${health.status === "ok" ? "succeeded" : "failed"}` }, h("span", { class: "dot" }), health.status === "ok" ? "Online" : "Unavailable")),
        config
          ? h("div", { class: "facts facts-col" },
              row("API version", config.version),
              row("Database", config.database === "postgresql" ? "PostgreSQL" : "SQLite (local file)"),
              row("Queue", config.queue === "redis" ? "Database + Redis wake-up" : "Database polling"),
              row("Upload limit", `${config.max_upload_mb} MB`),
              row("Accepted formats", config.video_extensions.join(" ")),
              row("Scale", config.scale))
          : h("p", { class: "muted", text: "Platform information is unavailable." })),
      h("section", { class: "panel" },
        h("div", { class: "panel-head" }, h("h2", { text: "Account" })),
        h("p", { class: "muted", text: "This build runs in single-user mode with no sign-in. Accounts, teams, and per-user permissions are planned alongside authentication." }))));
  return null;
}
