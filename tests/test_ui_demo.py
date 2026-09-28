from pathlib import Path

from ui.demo import _selected_frames
from ui.splat_demo import find_ply


def test_selected_frames_picks_first_last_style_subset(tmp_path: Path) -> None:
    selected = tmp_path / "selected"
    selected.mkdir()
    for i in range(12):
        (selected / f"f{i:02d}.jpg").write_bytes(b"x")
    names = _selected_frames(tmp_path, limit=4)
    assert len(names) == 4
    assert names[0] == "f00.jpg"
    assert names[-1] == "f11.jpg"


def test_find_ply_none_when_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("ui.splat_demo.ROOT", tmp_path)
    assert find_ply("img7916") is None


def test_sample_mesh_is_present() -> None:
    glb = Path("samples/room20260814/mesh.glb")
    assert glb.is_file()
    assert glb.stat().st_size > 1000
