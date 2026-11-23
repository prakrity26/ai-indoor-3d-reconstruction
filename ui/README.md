# ui

**Phases:** 13 (web platform) · **Status:** implemented

## `ui/web/`: the web platform

A single-page app served by the API at `/`. Plain ES modules, no build step, no framework. Every
text value goes through `textContent`, so project names and hotspot text cannot inject HTML.

| File | Role |
|---|---|
| `index.html` | App shell: sidebar, top bar, `<main>` |
| `share.html` | Public read-only viewer for `/s/<token>` and `/embed/<token>` |
| `assets/app.css` | Design tokens (light and dark), layout, components |
| `assets/js/main.js` | Hash router (`#/`, `#/projects`, `#/projects/<id>`, `#/new`, `#/jobs`, `#/studio/<id>`, `#/shared`, `#/settings`) |
| `assets/js/api.js` | REST client, upload with progress |
| `assets/js/viewer.js` | Mesh viewer on `<model-viewer>` (orbit, zoom, pan, reset, fullscreen, hotspots, viewpoints) and the splat iframe |
| `assets/js/pages/*.js` | One module per section |

External scripts: `<model-viewer>` 4.0.0 (Google CDN) for meshes; three.js 0.170 and
GaussianSplats3D 0.4.7 (unpkg) inside `splat_viewer.html`. The browser needs internet access once
to load them.

```bash
pip install -e ".[api]"
python -m api            # http://127.0.0.1:8000
```

## Viewers served by the API

| File | Route | Role |
|---|---|---|
| `splat_viewer.html` | `/viewer?ply=…` | First-person walk viewer for Gaussian splats (Walk mode, shared links, embeds) |
| `orbit.html` | `/orbit` | Mesh orbit viewer used by the studio |

Nothing in `ui/` imports `model/` or runs reconstruction.
