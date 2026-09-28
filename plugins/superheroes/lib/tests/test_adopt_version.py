import json
import os
import subprocess
import sys

import pytest

import adopt_version as av

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_LIB, "adopt_version.py")

_TRANSITION = """# Transition

## 0.35.1
### Before you upgrade
text
#### Detail

## 0.20.0
### Notes

```
## 0.30.0
```

## 0.10.0
### Other

## 0.9.0
"""


def _version(cache, version, files=None, transition=None):
    root = cache / version
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in (files or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    if transition is not None:
        (root / "TRANSITION.md").write_text(transition)
    return root


def _run(capsys, *argv):
    code = av.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def _plan(capsys, cache, from_version, *extra, role="workhorse"):
    return _run(capsys, "plan", "--role", role, "--from-root", str(cache / from_version), *extra)


def _empty_buckets():
    return {b: {"added": [], "removed": [], "changed": []}
            for b in ("charter", "covenantHooks", "libs", "other")}


def test_installed_versions_sorted_numerically_and_default_to(tmp_path, capsys):
    cache = tmp_path / "cache"
    for v in ("0.9.0", "0.10.0", "0.35.1"):
        _version(cache, v, transition="")
    (cache / "foo").mkdir()
    (cache / "bar.txt").write_text("x")
    code, out = _plan(capsys, cache, "0.9.0")
    assert code == 0
    assert out["installed"] == ["0.9.0", "0.10.0", "0.35.1"]
    assert out["to"] == "0.35.1"
    assert out["from"] == "0.9.0"
    assert out["fromRoot"] == str(cache / "0.9.0")
    assert out["toRoot"] == str(cache / "0.35.1")
    assert out["cacheDir"] == str(cache)


def test_transition_sections_in_range_in_file_order(tmp_path, capsys):
    cache = tmp_path / "cache"
    _version(cache, "0.9.0")
    _version(cache, "0.10.0")
    _version(cache, "0.35.1", transition=_TRANSITION)
    code, out = _plan(capsys, cache, "0.9.0")
    assert code == 0
    assert out["transitionSections"] == [
        {"version": "0.35.1", "line": 3, "beforeYouUpgrade": True,
         "subheadings": ["Before you upgrade", "Detail"]},
        {"version": "0.20.0", "line": 8, "beforeYouUpgrade": False, "subheadings": ["Notes"]},
        {"version": "0.10.0", "line": 15, "beforeYouUpgrade": False, "subheadings": ["Other"]},
    ]
    assert out["missingTransitionSections"] == []


def test_missing_transition_sections_lists_headingless_in_range_and_to(tmp_path, capsys):
    cache = tmp_path / "cache"
    text = "## 0.3.0\n### Notes\n"
    _version(cache, "0.1.0")
    _version(cache, "0.2.0")
    _version(cache, "0.3.0")
    _version(cache, "0.4.0", transition=text)
    code, out = _plan(capsys, cache, "0.1.0")
    assert code == 0
    assert out["missingTransitionSections"] == ["0.2.0", "0.4.0"]
    assert [s["version"] for s in out["transitionSections"]] == ["0.3.0"]

    _version(cache, "0.3.0", transition=text)
    code, out = _plan(capsys, cache, "0.1.0", "--to", "0.3.0")
    assert code == 0
    assert out["missingTransitionSections"] == ["0.2.0"]


def test_diff_buckets(tmp_path, capsys):
    cache = tmp_path / "cache"
    _version(cache, "1.0.0", {
        "skills/workhorse/reference/removed.md": "r",
        "skills/workhorse/reference/changed.md": "a",
        "rubric/covenant.md": "a",
        "hooks/old.json": "r",
        "lib/old.py": "r",
        "bin/y": "a",
        "skills/detective/SKILL.md": "a",
        "lib/tests/test_gone.py": "r",
        "README.md": "r",
        "lib/same.py": "same",
    })
    _version(cache, "1.1.0", {
        "skills/workhorse/reference/added.md": "n",
        "skills/workhorse/reference/changed.md": "b",
        "rubric/covenant.md": "b",
        "hooks/hooks.json": "n",
        "lib/x.py": "n",
        "bin/y": "b",
        "skills/detective/SKILL.md": "b",
        "lib/tests/test_x.py": "n",
        "lib/same.py": "same",
    }, transition="## 1.1.0\n")
    code, out = _plan(capsys, cache, "1.0.0")
    assert code == 0
    assert out["buckets"] == {
        "charter": {"added": ["skills/workhorse/reference/added.md"],
                    "removed": ["skills/workhorse/reference/removed.md"],
                    "changed": ["skills/workhorse/reference/changed.md"]},
        "covenantHooks": {"added": ["hooks/hooks.json"], "removed": ["hooks/old.json"],
                          "changed": ["rubric/covenant.md"]},
        "libs": {"added": ["lib/x.py"], "removed": ["lib/old.py"], "changed": ["bin/y"]},
        "other": {"added": ["lib/tests/test_x.py"],
                  "removed": ["README.md", "lib/tests/test_gone.py"],
                  "changed": ["skills/detective/SKILL.md"]},
    }
    assert out["counts"] == {"charter": 3, "covenantHooks": 3, "libs": 3, "other": 4}


def test_diff_ignores_pycache_in_use_and_orphaned_at(tmp_path, capsys):
    cache = tmp_path / "cache"
    _version(cache, "1.0.0", {
        "lib/__pycache__/m.pyc": "a",
        "__pycache__/top.pyc": "a",
        ".in_use": "a",
        ".orphaned_at": "a",
        "lib/.in_use": "a",
    })
    _version(cache, "1.1.0", {
        "lib/__pycache__/m.pyc": "b",
        "__pycache__/top.pyc": "b",
        ".in_use": "b",
        ".orphaned_at": "b",
        "lib/.in_use": "b",
        "lib/__pycache__/new.pyc": "n",
    }, transition="## 1.1.0\n")
    code, out = _plan(capsys, cache, "1.0.0")
    assert code == 0
    assert out["buckets"] == _empty_buckets()
    assert out["counts"] == {"charter": 0, "covenantHooks": 0, "libs": 0, "other": 0}


def test_symlinks_compared_by_target(tmp_path, capsys):
    cache = tmp_path / "cache"
    old = _version(cache, "1.0.0", {"lib/target.py": "same"})
    new = _version(cache, "1.1.0", {"lib/target.py": "same"}, transition="## 1.1.0\n")
    (old / "lib" / "link").symlink_to("target.py")
    (new / "lib" / "link").symlink_to("elsewhere.py")
    (old / "lib" / "keep").symlink_to("target.py")
    (new / "lib" / "keep").symlink_to("target.py")
    code, out = _plan(capsys, cache, "1.0.0")
    assert code == 0
    assert out["buckets"]["libs"] == {"added": [], "removed": [], "changed": ["lib/link"]}


def test_up_to_date_when_from_equals_to(tmp_path, capsys):
    cache = tmp_path / "cache"
    _version(cache, "0.9.0", {"lib/a.py": "a"})
    _version(cache, "0.35.1", {"lib/a.py": "b"})
    code, out = _plan(capsys, cache, "0.35.1")
    assert code == 0
    assert out["upToDate"] is True
    assert out["transitionSections"] == []
    assert out["missingTransitionSections"] == []
    assert out["buckets"] == _empty_buckets()
    assert out["counts"] == {"charter": 0, "covenantHooks": 0, "libs": 0, "other": 0}


def test_from_and_cache_dir_equals_from_root(tmp_path, capsys):
    cache = tmp_path / "cache"
    _version(cache, "0.9.0", {"lib/a.py": "a"})
    _version(cache, "0.10.0", {"lib/a.py": "b"}, transition="## 0.10.0\n")
    code_root, by_root = _plan(capsys, cache, "0.9.0")
    code_from, by_from = _run(capsys, "plan", "--role", "workhorse", "--from", "0.9.0",
                              "--cache-dir", str(cache))
    assert code_root == code_from == 0
    assert by_from == by_root
    assert by_from["buckets"]["libs"]["changed"] == ["lib/a.py"]


def test_explicit_cache_dir_overrides_from_root_parent(tmp_path, capsys):
    cache = tmp_path / "cache"
    _version(cache, "0.9.0")
    _version(cache, "0.10.0", transition="## 0.10.0\n")
    outside = tmp_path / "elsewhere" / "0.9.0"
    outside.mkdir(parents=True)
    code, out = _run(capsys, "plan", "--role", "workhorse", "--from-root", str(outside),
                     "--cache-dir", str(cache))
    assert code == 0
    assert out["cacheDir"] == str(cache)
    assert out["fromRoot"] == str(cache / "0.9.0")


def test_refusal_cache_dir_missing(tmp_path, capsys):
    code, out = _run(capsys, "plan", "--role", "workhorse", "--from", "0.1.0",
                     "--cache-dir", str(tmp_path / "nope"))
    assert code == 1
    assert out["ok"] is False
    assert out["reason"] == "cache-dir-missing"
    (tmp_path / "file").write_text("x")
    code, out = _run(capsys, "plan", "--role", "workhorse", "--from", "0.1.0",
                     "--cache-dir", str(tmp_path / "file"))
    assert code == 1
    assert out["reason"] == "cache-dir-missing"


def test_refusal_from_not_installed(tmp_path, capsys):
    cache = tmp_path / "cache"
    _version(cache, "0.9.0")
    (cache / "foo").mkdir()
    code, out = _run(capsys, "plan", "--role", "workhorse", "--from-root", str(cache / "foo"))
    assert code == 1
    assert out["reason"] == "from-not-installed"
    code, out = _run(capsys, "plan", "--role", "workhorse", "--from", "0.8.0",
                     "--cache-dir", str(cache))
    assert code == 1
    assert out["reason"] == "from-not-installed"


def test_refusal_to_not_installed(tmp_path, capsys):
    cache = tmp_path / "cache"
    _version(cache, "0.9.0")
    code, out = _plan(capsys, cache, "0.9.0", "--to", "9.9.9")
    assert code == 1
    assert out["reason"] == "to-not-installed"


def test_refusal_to_older_than_from(tmp_path, capsys):
    cache = tmp_path / "cache"
    _version(cache, "0.9.0")
    _version(cache, "0.35.1")
    code, out = _plan(capsys, cache, "0.35.1", "--to", "0.9.0")
    assert code == 1
    assert out["reason"] == "to-older-than-from"


def test_refusal_transition_unreadable(tmp_path, capsys):
    cache = tmp_path / "cache"
    _version(cache, "0.9.0")
    to_root = _version(cache, "0.10.0")
    code, out = _plan(capsys, cache, "0.9.0")
    assert code == 1
    assert out["reason"] == "transition-unreadable"
    (to_root / "TRANSITION.md").mkdir()
    code, out = _plan(capsys, cache, "0.9.0")
    assert code == 1
    assert out["reason"] == "transition-unreadable"


def test_bad_role_and_bad_source_are_usage_errors(tmp_path):
    cache = tmp_path / "cache"
    _version(cache, "0.9.0")
    root = str(cache / "0.9.0")
    for argv in (
        ["plan", "--role", "bogus", "--from-root", root],
        ["plan", "--from-root", root],
        ["plan", "--role", "workhorse"],
        ["plan", "--role", "workhorse", "--from-root", root, "--from", "0.9.0",
         "--cache-dir", str(cache)],
        ["plan", "--role", "workhorse", "--from", "0.9.0"],
    ):
        with pytest.raises(SystemExit) as excinfo:
            av.main(argv)
        assert excinfo.value.code == 2


def _snapshot(root):
    seen = {}
    for dirpath, dirnames, filenames in os.walk(root):
        seen[dirpath] = None
        for name in filenames:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as handle:
                seen[full] = handle.read()
    return seen


def test_plan_is_read_only(tmp_path, capsys):
    cache = tmp_path / "cache"
    _version(cache, "0.9.0", {"lib/a.py": "a", "lib/__pycache__/m.pyc": "a"})
    _version(cache, "0.10.0", {"lib/a.py": "b", "lib/new.py": "n"}, transition=_TRANSITION)
    before = _snapshot(tmp_path)
    code, _ = _plan(capsys, cache, "0.9.0")
    assert code == 0
    assert _snapshot(tmp_path) == before


def test_cli_subprocess_entry(tmp_path):
    cache = tmp_path / "cache"
    _version(cache, "0.9.0", {"lib/a.py": "a"})
    _version(cache, "0.10.0", {"lib/a.py": "b"}, transition="## 0.10.0\n")
    proc = subprocess.run(
        [sys.executable, "-B", _SCRIPT, "plan", "--role", "workhorse",
         "--from-root", str(cache / "0.9.0")],
        capture_output=True, text=True)
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert out["buckets"]["libs"]["changed"] == ["lib/a.py"]
    proc = subprocess.run(
        [sys.executable, "-B", _SCRIPT, "plan", "--role", "workhorse",
         "--from-root", str(cache / "0.9.0"), "--to", "9.9.9"],
        capture_output=True, text=True)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["reason"] == "to-not-installed"
