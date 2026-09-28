# ui

Streamlit client for operators and demos.

**Phase:** 13 (operator UI still a placeholder)  
**Status:** local mid-defense preview added

This package will later upload video, poll job status, and embed an interactive 3D viewer. It must call the API only. It must not import `model/` or run reconstruction locally.

Until Phase 13, use the local preview of an **already reconstructed** job (does not run the engine):

```bash
python -m ui.demo --job-id room20260814
```

That opens a browser with selected frames and `mesh.glb`. Orbit with the mouse. Internet is needed once so the 3D viewer library can load.

If the browser is empty, drag `samples/room20260814/mesh.glb` (or `data/outputs/room20260814/mesh.glb`) onto the file input on the page.

Walkable splat (needs `point_cloud.ply` from Colab):

```bash
python -m ui.splat_demo --job-id img7916
```

