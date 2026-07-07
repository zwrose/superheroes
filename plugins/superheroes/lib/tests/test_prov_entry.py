# plugins/superheroes/lib/tests/test_prov_entry.py
"""UFR-6/UFR-8: prov_entry.py --step build-denial records a build-step denial via
ship_gate.record_build_denial WITHOUT resolving HEAD (a denial is not head-scoped —
ship_gate.decide checks buildDenials before the covers/head freshness check), so it must
land even when git rev-parse would be flaky/unavailable."""
import json
import os
import subprocess
import sys

LIB_R = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run(args, cwd, env_root):
    env = dict(os.environ)
    env["SUPERHEROES_STORE_ROOT"] = str(env_root)
    return subprocess.run(
        [sys.executable, os.path.join(LIB_R, "prov_entry.py")] + args,
        capture_output=True, text=True, cwd=str(cwd), timeout=30, env=env,
    )


def test_build_denial_records_without_head_resolution(tmp_path):
    r = _run(["--step", "build-denial", "--work-item", "wi-x",
              "--denied-step", "build:task-3", "--denied-command", "python3 -c x"],
             tmp_path, tmp_path / "store")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out.get("ok") is True

    sys.path.insert(0, LIB_R)
    import control_plane, ship_gate
    paths = control_plane.paths(str(tmp_path), "wi-x", root=str(tmp_path / "store"))
    prov = ship_gate.read_provenance(paths["provenance"])
    assert prov["buildDenials"] == [{"step": "build:task-3", "command": "python3 -c x"}]


def test_build_denial_preserves_prior_build_evidence(tmp_path):
    sys.path.insert(0, LIB_R)
    import control_plane, ship_gate
    paths = control_plane.paths(str(tmp_path), "wi-y", root=str(tmp_path / "store"))
    ship_gate.write_build(paths["provenance"], engine="subagent-driven-development", head="abc123")

    r = _run(["--step", "build-denial", "--work-item", "wi-y",
              "--denied-step", "build:task-4", "--denied-command", "node -e y"],
             tmp_path, tmp_path / "store")
    assert r.returncode == 0, r.stderr
    prov = ship_gate.read_provenance(paths["provenance"])
    assert prov["build"]["head"] == "abc123"          # build evidence untouched
    assert prov["buildDenials"] == [{"step": "build:task-4", "command": "node -e y"}]


def test_build_denial_appends_not_clobber(tmp_path):
    sys.path.insert(0, LIB_R)
    import control_plane, ship_gate
    paths = control_plane.paths(str(tmp_path), "wi-z", root=str(tmp_path / "store"))

    r1 = _run(["--step", "build-denial", "--work-item", "wi-z",
               "--denied-step", "build:task-1", "--denied-command", "cmd-1"],
              tmp_path, tmp_path / "store")
    r2 = _run(["--step", "build-denial", "--work-item", "wi-z",
               "--denied-step", "build:task-2", "--denied-command", "cmd-2"],
              tmp_path, tmp_path / "store")
    assert r1.returncode == 0 and r2.returncode == 0
    prov = ship_gate.read_provenance(paths["provenance"])
    assert [d["step"] for d in prov["buildDenials"]] == ["build:task-1", "build:task-2"]


def test_build_denial_fails_closed_on_garbled_provenance(tmp_path):
    sys.path.insert(0, LIB_R)
    import control_plane
    paths = control_plane.paths(str(tmp_path), "wi-garbled", root=str(tmp_path / "store"))
    os.makedirs(os.path.dirname(paths["provenance"]), exist_ok=True)
    with open(paths["provenance"], "w", encoding="utf-8") as fh:
        fh.write("{garbled")

    r = _run(["--step", "build-denial", "--work-item", "wi-garbled",
              "--denied-step", "build:task-1", "--denied-command", "cmd"],
             tmp_path, tmp_path / "store")
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out.get("ok") is False
    assert "build-denial write failed" in out.get("error", "")
    with open(paths["provenance"], encoding="utf-8") as fh:
        assert fh.read() == "{garbled"   # never clobbered
