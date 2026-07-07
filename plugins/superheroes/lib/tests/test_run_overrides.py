import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import run_overrides

def test_write_then_read_roundtrips(tmp_path, monkeypatch):
    # pin the control-plane store under tmp so the test never touches the real store
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)
    ov = {"reviewer": {"engine": "codex"}}
    snap = {"workItem": "wi", "phases": [], "version": 1}
    run_overrides.write("wi", root, ov, snap)
    got = run_overrides.read("wi", root)
    assert got["overrides"] == ov
    assert got["frozenSnapshot"]["workItem"] == "wi"

def test_read_absent_fails_open_to_no_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)
    got = run_overrides.read("wi-none", root)
    assert got["overrides"] == {} and got["frozenSnapshot"] is None

def test_read_corrupt_fails_open(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)
    # write a garbage record at the expected path, then confirm read fails open
    run_overrides.write("wi", root, {"reviewer": {"engine": "codex"}}, {"version": 1})
    path = run_overrides._record_path("wi", root)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    got = run_overrides.read("wi", root)
    assert got["overrides"] == {} and got["frozenSnapshot"] is None
