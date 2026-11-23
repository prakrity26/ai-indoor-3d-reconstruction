"""Static checks on the web platform modules (no browser needed)."""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "ui" / "web" / "assets" / "js"
_IMPORT = re.compile(r"import\s*\{([^}]*)\}\s*from")
_LOCAL = re.compile(r"\b(?:const|let|var|function)\s+([A-Za-z_$][\w$]*)")


def test_no_local_name_shadows_an_import() -> None:
    """A local `const fill = …` next to `import { fill }` broke the upload button silently."""
    problems = []
    for path in sorted(JS.rglob("*.js")):
        source = path.read_text(encoding="utf-8")
        imported = {
            name.split(" as ")[-1].strip()
            for group in _IMPORT.findall(source)
            for name in group.split(",")
            if name.strip()
        }
        for match in _LOCAL.finditer(source):
            if match.group(1) in imported:
                line = source.count("\n", 0, match.start()) + 1
                problems.append(f"{path.relative_to(JS)}:{line} redeclares imported '{match.group(1)}'")
    assert not problems, "\n".join(problems)


def test_page_tip_never_returns_null() -> None:
    """Pages append pageTip() directly; a dismissed tip returning null printed "null" on the dashboard."""
    source = (JS / "guide.js").read_text(encoding="utf-8")
    body = source.split("export function pageTip", 1)[1].split("\nexport function", 1)[0]
    assert "return null" not in body
