# shared

Code used by more than one service, with no reconstruction logic.

**Status:** placeholder

| Package | Role |
|---------|------|
| `schemas` | Pydantic job/artifact contracts (API ↔ worker ↔ UI) |
| `config` | Environment and device settings |
| `utilities` | Small helpers (paths, logging) |

Keep this package free of OpenCV, PyTorch, and Open3D so the API image does not inherit the ML stack.
