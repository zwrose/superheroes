# plugins/superheroes/lib/tests/test_architect_config.py
"""Conformance: the-architect doc-policy record (CONVENTIONS §2.3/§3.3/§4.2)."""
import importlib.util
import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AC = _load("architect_config")


def test_read_policy_absent_is_none(tmp_path):
    # No project store / no doc-policy.json yet → None.
    assert AC.read_policy(str(tmp_path), root=str(tmp_path / "store")) is None


def test_write_then_read_roundtrips(tmp_path):
    store = str(tmp_path / "store")
    pol = {"location": "docs/specs", "visibility": AC.GITIGNORED, "confirmed": True}
    written = AC.write_policy(str(tmp_path), pol, root=store)
    assert written["location"] == "docs/specs"
    got = AC.read_policy(str(tmp_path), root=store)
    assert got["location"] == "docs/specs"
    assert got["visibility"] == AC.GITIGNORED
    assert got["confirmed"] is True


def test_read_policy_migrates_missing_fields(tmp_path):
    # A record from an earlier version (no `confirmed`, no schemaVersion) is tolerated and
    # filled forward on read; a subsequent read sees the current shape.
    store = str(tmp_path / "store")
    p = AC.policy_path(str(tmp_path), root=store)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        json.dump({"location": "docs/superheroes", "visibility": "committed"}, fh)
    got = AC.read_policy(str(tmp_path), root=store)
    assert got["confirmed"] is False  # defaulted (treated as provisional)
    assert got["location"] == "docs/superheroes"


def test_read_policy_corrupt_is_none(tmp_path):
    store = str(tmp_path / "store")
    p = AC.policy_path(str(tmp_path), root=store)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write("{ not json")
    assert AC.read_policy(str(tmp_path), root=store) is None


def test_read_policy_rejects_out_of_repo_location(tmp_path):
    # UFR-4: a recorded location that escapes the repo (absolute, or ../) is not honored —
    # it is normalized back to the safe default rather than letting a write land outside.
    store = str(tmp_path / "store")
    for bad in ("/etc/passwd-dir", "../../escape", "docs/../../x"):
        p = AC.policy_path(str(tmp_path), root=store)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            json.dump({"location": bad, "visibility": "committed"}, fh)
        got = AC.read_policy(str(tmp_path), root=store)
        assert got["location"] == AC.DEFAULT_LOCATION, bad


def test_analyze_prefers_existing_superheroes_docs(tmp_path):
    os.makedirs(str(tmp_path / "docs" / "superheroes" / "wi"), exist_ok=True)
    rec = AC.analyze_repo(str(tmp_path))
    assert rec["location"] == "docs/superheroes"


def test_analyze_recommends_gitignored_when_docs_ignored(tmp_path):
    os.makedirs(str(tmp_path / "docs"), exist_ok=True)
    with open(str(tmp_path / ".gitignore"), "w") as fh:
        fh.write("docs/\n")
    rec = AC.analyze_repo(str(tmp_path))
    assert rec["visibility"] == AC.GITIGNORED


def test_analyze_greenfield_defaults(tmp_path):
    rec = AC.analyze_repo(str(tmp_path))
    assert rec["location"] == AC.DEFAULT_LOCATION
    assert rec["visibility"] == AC.COMMITTED


import subprocess


def _git_init(path):
    subprocess.run(["git", "init", "-q", path], check=True)
    subprocess.run(["git", "-C", path, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", path, "config", "user.name", "t"], check=True)


def test_ensure_ignored_adds_scoped_rule(tmp_path):
    repo = str(tmp_path)
    _git_init(repo)
    assert AC.ensure_ignored(repo, "docs/superheroes") is True
    gi = open(os.path.join(repo, ".gitignore")).read()
    assert "docs/superheroes/" in gi
    # idempotent: second call adds no duplicate
    AC.ensure_ignored(repo, "docs/superheroes")
    assert open(os.path.join(repo, ".gitignore")).read().count("docs/superheroes/") == 1


def test_ensure_ignored_refuses_already_tracked(tmp_path):
    repo = str(tmp_path)
    _git_init(repo)
    os.makedirs(os.path.join(repo, "docs", "superheroes"), exist_ok=True)
    with open(os.path.join(repo, "docs", "superheroes", "f.md"), "w") as fh:
        fh.write("x")
    subprocess.run(["git", "-C", repo, "add", "docs/superheroes/f.md"], check=True)
    # location already tracked → an ignore rule won't untrack it → could-not-ensure
    assert AC.ensure_ignored(repo, "docs/superheroes") is False


def test_ensure_ignored_keeps_unrelated_visible(tmp_path):
    repo = str(tmp_path)
    _git_init(repo)
    AC.ensure_ignored(repo, "docs/superheroes")
    # an unrelated path is NOT ignored by the scoped rule
    out = subprocess.run(["git", "-C", repo, "check-ignore", "src/app.py"],
                         capture_output=True, text=True)
    assert out.returncode != 0  # not ignored


def test_ensure_ignored_refuses_unwritable_gitignore(tmp_path):
    # The other half of UFR-8: a .gitignore that can't be written → could-not-ensure (False),
    # not a silent exposed write. Force it by making .gitignore a directory.
    repo = str(tmp_path)
    _git_init(repo)
    os.makedirs(os.path.join(repo, ".gitignore"))
    assert AC.ensure_ignored(repo, "docs/superheroes") is False


def test_gitignore_covers_trusts_git_not_ignored(tmp_path):
    # An ignore + negation pattern where git authoritatively says NOT ignored (rc 1);
    # the textual fallback must not override git's verdict (premortem-003).
    # `docs/superheroes/` + `!docs/superheroes/` makes git return rc 1 for the probe.
    repo = str(tmp_path)
    _git_init(repo)
    with open(os.path.join(repo, ".gitignore"), "w") as fh:
        fh.write("docs/superheroes/\n!docs/superheroes/\n")
    assert AC._gitignore_covers(repo, "docs/superheroes") is False
