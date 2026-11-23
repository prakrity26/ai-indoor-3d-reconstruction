import { api } from "../api.js";
import { h, button, emptyState, timeAgo, toast, copyText, absoluteUrl, confirmDialog, fill } from "../ui.js";
import { pageHeader, projectThumb } from "./common.js";

export function embedCode(project) {
  return `<iframe src="${absoluteUrl(project.embed_url)}" width="800" height="500" style="border:0;border-radius:12px" allow="fullscreen" title="${project.name.replace(/"/g, "&quot;")}"></iframe>`;
}

export async function render(main, _params, ctx) {
  let projects = await api.list();
  const list = h("div");

  function paint() {
    const shared = projects.filter((p) => p.visibility === "public");
    if (!shared.length) {
      fill(list, emptyState("share", "Nothing shared yet", "Open a ready project in the 3D Studio and choose Share to create a public link.", button("My projects", { kind: "primary", onClick: () => ctx.navigate("#/projects") })));
      return;
    }
    fill(list, h("div", { class: "share-list" }, ...shared.map((p) => {
      const link = absoluteUrl(p.share_url);
      return h("article", { class: "panel share-item" },
        h("a", { class: "share-thumb", href: `#/studio/${p.job_id}` }, projectThumb(p)),
        h("div", { class: "share-body" },
          h("div", { class: "panel-head" }, h("h2", { text: p.name }), h("span", { class: "muted small", text: `Updated ${timeAgo(p.updated_at)}` })),
          h("div", { class: "copy-row" }, h("input", { class: "input mono", readonly: true, value: link, "aria-label": "Share link" }), button("Copy link", { size: "sm", iconName: "copy", onClick: () => copyText(link) })),
          h("div", { class: "share-actions" },
            button("Open", { size: "sm", iconName: "eye", onClick: () => window.open(p.share_url, "_blank", "noopener") }),
            button("Copy embed code", { size: "sm", iconName: "link", onClick: () => copyText(embedCode(p)) }),
            button("Edit scene", { size: "sm", iconName: "edit", onClick: () => ctx.navigate(`#/studio/${p.job_id}`) }),
            button("Make private", { size: "sm", kind: "danger-ghost", iconName: "lock", onClick: async () => {
              const ok = await confirmDialog({ title: "Stop sharing?", message: "The current link will stop working. Sharing again creates the same link unless you reset it.", confirmLabel: "Make private" });
              if (!ok) return;
              try {
                const updated = await api.setVisibility(p.job_id, "private");
                projects = projects.map((x) => (x.job_id === p.job_id ? { ...x, ...updated } : x));
                toast("Scene is private", "success");
                paint();
              } catch (error) { toast(error.message, "error"); }
            } }))));
    })));
  }

  paint();
  main.append(pageHeader("Shared scenes", "Published 3D experiences. Anyone with a link can view them; nobody can edit them."), list);
  return null;
}
