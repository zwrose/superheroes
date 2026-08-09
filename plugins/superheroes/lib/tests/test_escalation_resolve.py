# plugins/superheroes/lib/tests/test_escalation_resolve.py
import importlib.util
import json
import os
import sys
import io

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
_PLUGIN_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ER = _load(os.path.join(_HERE, "..", "escalation_resolve.py"), "escalation_resolve")


def _run(capsys, *args):
    rc = ER.main(["escalation_resolve.py", *args])
    return rc, json.loads(capsys.readouterr().out)


# --- positive paths (direct in-tree call against the merged plugin root) ---

def test_route_resolves_in_repo(capsys):
    rc, out = _run(capsys, "route", "--root", _REPO_ROOT,
                   "--on-floor", "false", "--ground-truth-locus", "owner",
                   "--owner-weighable", "true", "--reversible", "true", "--confidence", "high")
    assert rc == 0 and out["mode"] == "notify" and out["degraded"] is False


def test_classify_resolves_in_repo(capsys):
    rc, out = _run(capsys, "classify", "--root", _REPO_ROOT, "--action", "git push origin main")
    assert rc == 0 and out["on_floor"] is True and out["degraded"] is False


def test_guard_refuses_band_safety_file_in_repo(capsys):
    # a real superheroes safety file, in-repo (dogfood) -> refused, not degraded
    rc, out = _run(capsys, "guard", "--root", _REPO_ROOT,
                   "--path", os.path.join(_REPO_ROOT, "plugins/superheroes/lib/loop_state.py"))
    assert rc == 0 and out["allow"] is False and out["degraded"] is False


def test_guard_allows_ordinary_file_in_repo(capsys):
    # decisions.py is NOT in the safety set -> allowed
    rc, out = _run(capsys, "guard", "--root", _REPO_ROOT,
                   "--path", os.path.join(_REPO_ROOT, "plugins/superheroes/lib/decisions.py"))
    assert rc == 0 and out["allow"] is True and out["degraded"] is False


def test_rubric_resolves_in_repo(capsys):
    # rubric is now resolved directly under the (single) superheroes plugin root.
    rc, out = _run(capsys, "rubric", "--root", _REPO_ROOT)
    assert rc == 0 and out["degraded"] is False
    assert out["path"].endswith(os.path.join("superheroes", "rubric", "escalation-base.md"))


def test_rubric_resolves_under_plugin_root_without_repo_root(capsys):
    # No --root: the rubric still resolves under the wrapper's own plugin root (the in-tree
    # lookup, distinct from the old subprocess seam). Equivalence note: this replaces the old
    # architect_lib cross-plugin rubric resolution, which is gone in one tree.
    rc, out = _run(capsys, "rubric")
    assert rc == 0 and out["degraded"] is False
    assert out["path"] == os.path.join(_PLUGIN_ROOT, "rubric", "escalation-base.md")


# --- fail-closed: the core raises -> the wrapper holds the conservative posture ---
# Equivalence note: the old "lib-unresolvable -> conservative" tests are removed (the lib is
# always resolvable in one tree). The core-error branch below preserves the SAME conservative
# posture (route->gate, classify->on_floor True, guard->allow False), now via the direct seam.

def _boom(*a, **k):
    raise RuntimeError("core blew up")


def test_route_core_error_fails_closed_to_gate(capsys, monkeypatch):
    monkeypatch.setattr(ER.escalation, "route", _boom)
    rc, out = _run(capsys, "route", "--root", _REPO_ROOT,
                   "--on-floor", "false", "--ground-truth-locus", "owner",
                   "--owner-weighable", "true", "--reversible", "true", "--confidence", "high")
    assert rc == 0 and out["mode"] == "gate" and out["degraded"] is True


def test_classify_core_error_fails_closed_to_on_floor(capsys, monkeypatch):
    monkeypatch.setattr(ER.escalation, "classify_floor", _boom)
    rc, out = _run(capsys, "classify", "--root", _REPO_ROOT, "--action", "rename a local variable")
    assert rc == 0 and out["on_floor"] is True and out["degraded"] is True


def test_guard_core_error_fails_closed_to_refuse(capsys, monkeypatch):
    monkeypatch.setattr(ER.escalation, "is_safety_machinery", _boom)
    rc, out = _run(capsys, "guard", "--root", _REPO_ROOT, "--path", "src/feature.py")
    assert rc == 0 and out["allow"] is False and out["degraded"] is True


def _stdin_guard(capsys, payload, *args):
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(payload)
        return _run(capsys, "guard", *args)
    finally:
        sys.stdin = old_stdin


def _stdin_guard_rc(payload, *args):
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(payload)
        return ER.main(["escalation_resolve.py", "guard", *args])
    finally:
        sys.stdin = old_stdin


def test_guard_stdin_path_reads_path(capsys):
    path = os.path.join(_REPO_ROOT, "plugins/superheroes/lib/decisions.py")
    rc, out = _stdin_guard(capsys, path, "--root", _REPO_ROOT, "--stdin-path")
    assert rc == 0 and out["allow"] is True and out["degraded"] is False


def test_guard_stdin_path_empty_fails(capsys):
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO("")
        rc = ER.main(["escalation_resolve.py", "guard", "--root", _REPO_ROOT, "--stdin-path"])
    finally:
        sys.stdin = old_stdin
    assert rc == 2


def test_guard_path_and_stdin_path_mutually_exclusive():
    rc = ER.main(["escalation_resolve.py", "guard", "--root", _REPO_ROOT,
                  "--path", "x", "--stdin-path"])
    assert rc == 2


def test_guard_stdin_path_with_metacharacters(capsys, tmp_path):
    nasty = str(tmp_path / "src" / "$(echo pwned).py")
    os.makedirs(os.path.dirname(nasty), exist_ok=True)
    with open(nasty, "w", encoding="utf-8") as fh:
        fh.write("# probe\n")
    rc, out = _stdin_guard(capsys, nasty, "--stdin-path")
    assert rc == 0 and out["allow"] is True


def test_guard_stdin_path_refuses_embedded_newline(capsys, monkeypatch):
    safety = os.path.join(_REPO_ROOT, "plugins/superheroes/lib/round_driver.py")
    stdin_payload = "safe.py\n" + safety
    validated = []
    real = ER.escalation.is_safety_machinery

    def record(path, band_roots):
        validated.append(path)
        return real(path, band_roots)

    monkeypatch.setattr(ER.escalation, "is_safety_machinery", record)
    rc = _stdin_guard_rc(stdin_payload, "--root", _REPO_ROOT, "--stdin-path")
    assert rc == 2
    assert validated == []


def test_guard_stdin_path_refuses_leading_trailing_whitespace(capsys, monkeypatch):
    path = os.path.join(_REPO_ROOT, "plugins/superheroes/lib/decisions.py")
    validated = []
    real = ER.escalation.is_safety_machinery

    def record(path, band_roots):
        validated.append(path)
        return real(path, band_roots)

    monkeypatch.setattr(ER.escalation, "is_safety_machinery", record)
    rc = _stdin_guard_rc(" " + path + " ", "--root", _REPO_ROOT, "--stdin-path")
    assert rc == 2
    assert validated == []


def test_guard_stdin_path_refuses_two_records(capsys, monkeypatch):
    path1 = os.path.join(_REPO_ROOT, "plugins/superheroes/lib/decisions.py")
    path2 = os.path.join(_REPO_ROOT, "plugins/superheroes/lib/loop_state.py")
    validated = []
    real = ER.escalation.is_safety_machinery

    def record(path, band_roots):
        validated.append(path)
        return real(path, band_roots)

    monkeypatch.setattr(ER.escalation, "is_safety_machinery", record)
    rc = _stdin_guard_rc(path1 + "\n" + path2, "--root", _REPO_ROOT, "--stdin-path")
    assert rc == 2
    assert validated == []


def test_guard_stdin_path_refuses_nul(capsys, monkeypatch):
    path = os.path.join(_REPO_ROOT, "plugins/superheroes/lib/decisions.py")
    validated = []
    real = ER.escalation.is_safety_machinery

    def record(path, band_roots):
        validated.append(path)
        return real(path, band_roots)

    monkeypatch.setattr(ER.escalation, "is_safety_machinery", record)
    rc = _stdin_guard_rc(path + "\0", "--root", _REPO_ROOT, "--stdin-path")
    assert rc == 2
    assert validated == []


def test_guard_stdin_path_validates_exact_path(capsys, monkeypatch):
    path = os.path.join(_REPO_ROOT, "plugins/superheroes/lib/decisions.py")
    validated = []
    real = ER.escalation.is_safety_machinery

    def record(path, band_roots):
        validated.append(path)
        return real(path, band_roots)

    monkeypatch.setattr(ER.escalation, "is_safety_machinery", record)
    rc, out = _stdin_guard(capsys, path, "--root", _REPO_ROOT, "--stdin-path")
    assert rc == 0 and out["allow"] is True and validated == [path]


def test_rubric_absent_fails_closed(capsys, tmp_path, monkeypatch):
    # If the rubric file cannot be located under any candidate root, the wrapper degrades to
    # the embedded fail-closed posture (path None, degraded True) — the skill applies the floor.
    # Point the plugin-root lookup at an empty dir so neither --root nor _PLUGIN_ROOT resolves.
    monkeypatch.setattr(ER, "_PLUGIN_ROOT", str(tmp_path))
    rc, out = _run(capsys, "rubric", "--root", str(tmp_path))
    assert rc == 0 and out["path"] is None and out["degraded"] is True
