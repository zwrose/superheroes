"""Tests for adopt_version.py — the read-only adoption plan helper."""
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import adopt_version  # noqa: E402

TRANSITION = """# Transition

## 0.35.1

### Before you upgrade

Do a thing.

#### Detail

## 0.20.0

### Notes

## 0.10.0

## 0.9.0

```
## 0.30.0
```
"""


def put(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def make_cache(tmp_path, versions=("0.9.0", "0.35.1"), transition=TRANSITION):
    cache = tmp_path / "cache"
    for v in versions:
        (cache / v).mkdir(parents=True)
    if transition is not None:
        put(cache / versions[-1], "TRANSITION.md", transition)
    return cache


def run(capsys, *argv):
    code = adopt_version.main(["plan", *argv])
    out = json.loads(capsys.readouterr().out)
    return code, out


def snap(root):
    return {
        str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
        for p in sorted(root.rglob("*"))
    }


def test_installed_list_sorted_numerically(tmp_path, capsys):
    cache = make_cache(tmp_path, versions=("0.9.0", "0.10.0", "0.35.1"))
    (cache / "foo").mkdir()
    (cache / "bar.txt").write_text("x")
    code, out = run(capsys, "--role", "workhorse", "--from", "0.9.0",
                    "--cache-dir", str(cache))
    assert code == 0
    assert out["installed"] == ["0.9.0", "0.10.0", "0.35.1"]
    assert out["to"] == "0.35.1"


def test_transition_sections_in_range_in_file_order(tmp_path, capsys):
    cache = make_cache(tmp_path, versions=("0.9.0", "0.10.0", "0.35.1"))
    code, out = run(capsys, "--role", "workhorse", "--from-root", str(cache / "0.9.0"))
    assert code == 0
    sections = out["transitionSections"]
    assert [s["version"] for s in sections] == ["0.35.1", "0.20.0", "0.10.0"]
    assert [s["line"] for s in sections] == [3, 11, 15]
    assert [s["beforeYouUpgrade"] for s in sections] == [True, False, False]
    assert sections[0]["subheadings"] == ["Before you upgrade", "Detail"]
    assert sections[1]["subheadings"] == ["Notes"]


def test_missing_transition_sections(tmp_path, capsys):
    cache = make_cache(tmp_path, versions=("0.9.0", "0.11.0", "0.12.0"),
                       transition="## 0.12.0\n")
    code, out = run(capsys, "--role", "workhorse", "--from", "0.9.0",
                    "--cache-dir", str(cache), "--to", "0.12.0")
    assert code == 0
    assert out["missingTransitionSections"] == ["0.11.0"]
    put(cache / "0.12.0", "TRANSITION.md", "## 0.11.0\n")
    code, out = run(capsys, "--role", "workhorse", "--from", "0.9.0",
                    "--cache-dir", str(cache))
    assert out["missingTransitionSections"] == ["0.12.0"]


def test_diff_buckets(tmp_path, capsys):
    cache = make_cache(tmp_path)
    old, new = cache / "0.9.0", cache / "0.35.1"
    put(old, "TRANSITION.md", TRANSITION)
    for rel in ("skills/workhorse/reference/x.md", "skills/showrunner/SKILL.md",
                "rubric/covenant.md", "hooks/hooks.json", "lib/x.py", "bin/y",
                "lib/tests/test_x.py", "docs/same.md"):
        put(old, rel, "old")
        put(new, rel, "old" if rel == "docs/same.md" else "new")
    put(new, "skills/workhorse/added.md", "n")
    put(new, "hooks/added.sh", "n")
    put(new, "lib/added.py", "n")
    put(new, "lib/tests/test_added.py", "n")
    put(old, "skills/workhorse/gone.md", "o")
    put(old, "hooks/gone.sh", "o")
    put(old, "bin/gone", "o")
    put(old, "other/gone.md", "o")
    code, out = run(capsys, "--role", "workhorse", "--from", "0.9.0",
                    "--cache-dir", str(cache))
    assert code == 0
    assert out["buckets"] == {
        "charter": {"added": ["skills/workhorse/added.md"],
                    "removed": ["skills/workhorse/gone.md"],
                    "changed": ["skills/workhorse/reference/x.md"]},
        "covenantHooks": {"added": ["hooks/added.sh"], "removed": ["hooks/gone.sh"],
                          "changed": ["hooks/hooks.json", "rubric/covenant.md"]},
        "libs": {"added": ["lib/added.py"], "removed": ["bin/gone"],
                 "changed": ["bin/y", "lib/x.py"]},
        "other": {"added": ["lib/tests/test_added.py"],
                  "removed": ["other/gone.md"],
                  "changed": ["lib/tests/test_x.py", "skills/showrunner/SKILL.md"]},
    }
    assert out["counts"] == {"charter": 3, "covenantHooks": 4, "libs": 4, "other": 4}


def test_symlink_targets_compared_not_followed(tmp_path, capsys):
    cache = make_cache(tmp_path)
    old, new = cache / "0.9.0", cache / "0.35.1"
    put(old, "lib/target.py", "same")
    put(new, "lib/target.py", "same")
    os.symlink("target.py", old / "lib" / "same_link")
    os.symlink("target.py", new / "lib" / "same_link")
    os.symlink("a.py", old / "lib" / "moved_link")
    os.symlink("b.py", new / "lib" / "moved_link")
    code, out = run(capsys, "--role", "workhorse", "--from", "0.9.0",
                    "--cache-dir", str(cache))
    assert code == 0
    assert out["buckets"]["libs"] == {"added": [], "removed": [],
                                      "changed": ["lib/moved_link"]}


def test_ignored_paths_absent_from_every_bucket(tmp_path, capsys):
    cache = make_cache(tmp_path)
    old, new = cache / "0.9.0", cache / "0.35.1"
    put(old, "TRANSITION.md", TRANSITION)
    put(old, "lib/__pycache__/x.pyc", "a")
    put(new, "lib/__pycache__/x.pyc", "b")
    put(old, ".in_use", "a")
    put(new, ".in_use", "b")
    put(old, ".orphaned_at", "a")
    put(new, "skills/workhorse/.orphaned_at/f", "b")
    code, out = run(capsys, "--role", "workhorse", "--from", "0.9.0",
                    "--cache-dir", str(cache))
    assert code == 0
    assert out["counts"] == {"charter": 0, "covenantHooks": 0, "libs": 0, "other": 0}
    assert all(not v for b in out["buckets"].values() for v in b.values())


def test_up_to_date(tmp_path, capsys):
    cache = make_cache(tmp_path)
    put(cache / "0.35.1", "lib/x.py", "x")
    code, out = run(capsys, "--role", "detective", "--from", "0.35.1",
                    "--cache-dir", str(cache))
    assert code == 0
    assert out["upToDate"] is True
    assert out["transitionSections"] == []
    assert out["missingTransitionSections"] == []
    assert out["counts"] == {"charter": 0, "covenantHooks": 0, "libs": 0, "other": 0}
    assert all(not v for b in out["buckets"].values() for v in b.values())


def test_from_and_from_root_agree(tmp_path, capsys):
    cache = make_cache(tmp_path)
    put(cache / "0.35.1", "lib/x.py", "x")
    _, by_root = run(capsys, "--role", "workhorse", "--from-root", str(cache / "0.9.0"))
    _, by_from = run(capsys, "--role", "workhorse", "--from", "0.9.0",
                     "--cache-dir", str(cache))
    assert by_root == by_from
    assert by_root["ok"] is True


def test_refusal_cache_dir_missing(tmp_path, capsys):
    code, out = run(capsys, "--role", "workhorse", "--from", "0.9.0",
                    "--cache-dir", str(tmp_path / "nope"))
    assert code == 1
    assert out["ok"] is False
    assert out["reason"] == "cache-dir-missing"


def test_refusal_from_not_installed(tmp_path, capsys):
    cache = make_cache(tmp_path)
    (cache / "foo").mkdir()
    code, out = run(capsys, "--role", "workhorse", "--from-root", str(cache / "foo"))
    assert (code, out["reason"]) == (1, "from-not-installed")
    code, out = run(capsys, "--role", "workhorse", "--from", "0.1.0",
                    "--cache-dir", str(cache))
    assert (code, out["reason"]) == (1, "from-not-installed")


def test_refusal_to_not_installed(tmp_path, capsys):
    cache = make_cache(tmp_path)
    code, out = run(capsys, "--role", "workhorse", "--from", "0.9.0",
                    "--cache-dir", str(cache), "--to", "9.9.9")
    assert (code, out["reason"]) == (1, "to-not-installed")


def test_refusal_to_older_than_from(tmp_path, capsys):
    cache = make_cache(tmp_path)
    code, out = run(capsys, "--role", "workhorse", "--from", "0.35.1",
                    "--cache-dir", str(cache), "--to", "0.9.0")
    assert (code, out["reason"]) == (1, "to-older-than-from")


def test_refusal_transition_unreadable(tmp_path, capsys):
    cache = make_cache(tmp_path, transition=None)
    code, out = run(capsys, "--role", "workhorse", "--from", "0.9.0",
                    "--cache-dir", str(cache))
    assert (code, out["reason"]) == (1, "transition-unreadable")


def test_bad_role_is_usage_error(tmp_path):
    cache = make_cache(tmp_path)
    with pytest.raises(SystemExit) as exc:
        adopt_version.main(["plan", "--role", "bogus", "--from", "0.9.0",
                            "--cache-dir", str(cache)])
    assert exc.value.code == 2


def test_plan_is_read_only(tmp_path, capsys):
    cache = make_cache(tmp_path)
    put(cache / "0.9.0", "lib/x.py", "old")
    put(cache / "0.35.1", "lib/x.py", "new")
    before = snap(cache)
    code, _ = run(capsys, "--role", "workhorse", "--from", "0.9.0",
                  "--cache-dir", str(cache))
    assert code == 0
    assert snap(cache) == before


def test_cli_entry_point_subprocess(tmp_path):
    cache = make_cache(tmp_path)
    put(cache / "0.35.1", "lib/x.py", "new")
    proc = subprocess.run(
        [sys.executable, "-B", os.path.join(_LIB, "adopt_version.py"), "plan",
         "--role", "workhorse", "--from-root", str(cache / "0.9.0")],
        capture_output=True, text=True)
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert out["buckets"]["libs"]["added"] == ["lib/x.py"]
