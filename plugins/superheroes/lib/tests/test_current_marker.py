# plugins/superheroes/lib/tests/test_current_marker.py
import subprocess
import control_plane as cp


def test_set_get_current_roundtrip(tmp_path):
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    root = str(tmp_path / "store")
    assert cp.get_current(str(tmp_path), root=root) is None
    cp.set_current(str(tmp_path), "wi-42", root=root)
    assert cp.get_current(str(tmp_path), root=root) == "wi-42"
