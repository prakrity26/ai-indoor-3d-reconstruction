import { api } from "../api.js";
import { h, field, toast } from "../ui.js";
import { pageHeader } from "./common.js";
import { prefs, setPref, applyTheme } from "../prefs.js";

export async function render(main) {
  const [config, health] = await Promise.all([api.config().catch(() => null), api.health().catch((e) => ({ status: "down", database: e.message }))]);

  const select = (key, options) => {
    const el = h("select", { class: "input", onChange: (e) => { setPref(key, e.target.value); if (key === "theme") applyTheme(); toast("Preference saved", "success"); } },
      ...options.map(([value, label]) => h("option", { value, selected: prefs()[key] === value }, label)));
    return el;
  };
  const row = (label, value) => h("div", { class: "fact" }, h("span", { class: "muted small", text: label }), h("strong", { text: value }));

  main.append(
    pageHeader("Settings", "Preferences are stored in this browser."),
    h("div", { class: "settings-grid" },
      h("section", { class: "panel form" },
        h("div", { class: "panel-head" }, h("h2", { text: "Appearance" })),
        field("Theme", select("theme", [["system", "Match system"], ["light", "Light"], ["dark", "Dark"]])),
        field("Default viewer mode", select("viewerMode", [["orbit", "Orbit (mesh)"], ["walk", "Walk (Gaussian splat, when available)"]]), "Studio opens in this mode when the scene supports it."),
        field("Hotspot placement hint", select("editHints", [["on", "Show"], ["off", "Hide"]]))),
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
