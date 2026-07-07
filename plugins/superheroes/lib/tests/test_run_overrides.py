import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import run_overrides
import control_plane

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


def _snapshot_tree(base):
    """{abspath: bytes} of every file under base (empty if base is absent)."""
    snap = {}
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            p = os.path.join(dirpath, name)
            with open(p, "rb") as fh:
                snap[p] = fh.read()
    return snap


def test_write_touches_only_control_plane_never_profile(tmp_path, monkeypatch):
    """FR-12: a per-run override is DURABLE (control-plane) but must NEVER mutate the project's saved
    calibration/profile — 'saved calibration unchanged after a run with overrides'. Assert every file
    the write creates or modifies lives strictly under the control-plane issue dir, and that a
    pre-seeded profile/config file elsewhere in the repo is byte-for-byte unchanged. A regression that
    stamped the override into the profile (or anywhere outside the issue dir) fails this."""
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)

    # Pre-seed a saved-calibration / profile file at a plausible in-repo config location and record it.
    config_dir = os.path.join(root, ".superheroes")
    os.makedirs(config_dir, exist_ok=True)
    profile = os.path.join(config_dir, "review-crew.md")
    with open(profile, "w", encoding="utf-8") as fh:
        fh.write("## Model tiers\n- reviewer: opus\n")

    # Snapshot the WHOLE repo subtree (profile included) before the write.
    before = _snapshot_tree(root)

    run_overrides.write("wi", root, {"reviewer": {"engine": "codex"}},
                        {"workItem": "wi", "phases": [], "version": 1})

    after = _snapshot_tree(root)

    # The record is written and lands directly under the control-plane issue dir (its durable home).
    issue_dir = os.path.realpath(control_plane.issue_dir(os.getcwd(), "wi", root))
    record = os.path.realpath(run_overrides._record_path("wi", root))
    assert os.path.isfile(record), "the override record must be written (durable)"
    assert os.path.dirname(record) == issue_dir, "the record must live directly under the control-plane issue dir"

    # Every file the write created or changed is confined under the control-plane STORE (the
    # `checkouts/` subtree — which also holds the store's git-repo scaffolding from ensure_store);
    # nothing under the profile/config location is created or modified (FR-12 'saved calibration
    # unchanged'). The profile sits OUTSIDE `checkouts/`, so a regression that stamped it fails here.
    store_subtree = os.path.realpath(os.path.join(root, "checkouts")) + os.sep
    changed = {p for p in after if after.get(p) != before.get(p)}
    for p in changed:
        assert os.path.realpath(p).startswith(store_subtree), \
            "write escaped the control-plane store: %s" % p
    # And the pre-seeded profile is byte-for-byte unchanged (belt-and-suspenders on the config file).
    assert after.get(profile) == before.get(profile), "the saved-calibration profile must be untouched"
    assert not os.path.realpath(profile).startswith(store_subtree), \
        "test invariant: the profile must live outside the control-plane store to be a real witness"
