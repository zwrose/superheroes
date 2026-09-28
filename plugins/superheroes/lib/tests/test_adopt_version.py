import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_LIB, "adopt_version.py")

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import adopt_version as av  # noqa: E402


def _mkver(cache, ver):
    os.makedirs(os.path.join(cache, ver), exist_ok=True)


def _plan(capsys, *argv):
    code = av.main(["plan", *argv])
    out = capsys.readouterr().out.strip()
    return code, json.loads(out) if out else None


def _subplan(*argv):
    return subprocess.run(
        [sys.executable, "-B", _SCRIPT, "plan", *argv],
        capture_output=True,
        text=True,
    )


def test_installed_list_default_to(capsys, tmp_path):
    cache = tmp_path / "cache"
    for v in ("0.9.0", "0.10.0", "0.35.1"):
        _mkver(cache, v)
    (cache / "foo").mkdir()
    (cache / "bar.txt").write_text("x")
    (cache / "0.35.1" / "TRANSITION.md").write_text("## 0.35.1\n")
    code, data = _plan(
        capsys, "--role", "showrunner", "--from", "0.9.0", "--cache-dir", str(cache),
    )
    assert code == 0
    assert data["installed"] == ["0.9.0", "0.10.0", "0.35.1"]
    assert data["to"] == "0.35.1"


def test_transition_sections_between_versions(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "0.9.0")
    _mkver(cache, "0.10.0")
    _mkver(cache, "0.35.1")
    transition = """\
## 0.35.1
### Before you upgrade
note
## 0.20.0
### Other
```
## 0.30.0
```
## 0.10.0
## 0.9.0
"""
    (cache / "0.35.1" / "TRANSITION.md").write_text(transition)
    code, data = _plan(
        capsys, "--role", "showrunner", "--from", "0.9.0", "--to", "0.35.1",
        "--cache-dir", str(cache),
    )
    assert code == 0
    secs = data["transitionSections"]
    assert [s["version"] for s in secs] == ["0.35.1", "0.20.0", "0.10.0"]
    assert secs[0]["beforeYouUpgrade"] is True
    assert secs[1]["beforeYouUpgrade"] is False
    assert secs[2]["beforeYouUpgrade"] is False
    assert secs[0]["line"] == 1


def test_missing_transition_sections(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    _mkver(cache, "1.1.0")
    _mkver(cache, "2.0.0")
    (cache / "2.0.0" / "TRANSITION.md").write_text("## 1.0.0\n")
    code, data = _plan(
        capsys, "--role", "workhorse", "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 0
    assert data["missingTransitionSections"] == ["1.1.0", "2.0.0"]
    assert data["unresolvedGaps"] == [{"version": None, "reason": "changelog-unreadable"}]


def test_gap_benign_changelog_section(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    _mkver(cache, "2.0.0")
    (cache / "2.0.0" / "TRANSITION.md").write_text("## 1.0.0\n")
    (cache / "2.0.0" / "CHANGELOG.md").write_text(
        "## [2.0.0](https://example.test) (2026-01-01)\n"
    )
    code, data = _plan(
        capsys, "--role", "workhorse", "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 0
    assert data["unresolvedGaps"] == []
    assert data["changelogSections"] == ["2.0.0"]


def test_gap_hold_no_section_either_file(capsys, tmp_path):
    cache = tmp_path / "cache"
    for v in ("1.0.0", "1.5.0", "2.0.0"):
        _mkver(cache, v)
    (cache / "2.0.0" / "TRANSITION.md").write_text("## 2.0.0\n")
    (cache / "2.0.0" / "CHANGELOG.md").write_text(
        "## [2.0.0](https://example.test) (2026-01-01)\n"
    )
    code, data = _plan(
        capsys, "--role", "workhorse", "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 0
    assert data["unresolvedGaps"] == [{"version": "1.5.0", "reason": "no-section"}]


def test_gap_hold_changelog_missing(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    _mkver(cache, "2.0.0")
    (cache / "2.0.0" / "TRANSITION.md").write_text("## 2.0.0\n")
    code, data = _plan(
        capsys, "--role", "workhorse", "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 0
    assert data["unresolvedGaps"] == [{"version": None, "reason": "changelog-unreadable"}]


def test_gap_changelog_heading_in_fence_ignored(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    _mkver(cache, "2.0.0")
    (cache / "2.0.0" / "TRANSITION.md").write_text("## 1.0.0\n")
    (cache / "2.0.0" / "CHANGELOG.md").write_text(
        "```\n## [2.0.0](https://example.test)\n```\n"
    )
    code, data = _plan(
        capsys, "--role", "workhorse", "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 0
    assert data["unresolvedGaps"] == [{"version": "2.0.0", "reason": "no-section"}]


def test_up_to_date_has_no_gaps(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    code, data = _plan(
        capsys, "--role", "showrunner", "--from-root", str(cache / "1.0.0"),
    )
    assert code == 0
    assert data["upToDate"] is True
    assert data["unresolvedGaps"] == []
    assert data["changelogSections"] == []


def test_refuse_version_tree_traversal_error(capsys, tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    _mkver(cache, "2.0.0")
    (cache / "2.0.0" / "TRANSITION.md").write_text("## 2.0.0\n")
    real_scandir = os.scandir

    def scandir_raises(path):
        if str(path).startswith(str(cache)):
            raise PermissionError("injected")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", scandir_raises)
    code, data = _plan(
        capsys, "--role", "showrunner", "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 1
    assert data["reason"] == "version-tree-unreadable"


def test_charter_bucket_uses_command_charters(capsys, tmp_path):
    cache = tmp_path / "cache"
    role = "showrunner"
    fr, tr = cache / "1.0.0", cache / "2.0.0"
    for sub in ("skills/showrunner-resume", "skills/showrunner-handoff"):
        os.makedirs(fr / sub, exist_ok=True)
        os.makedirs(tr / sub, exist_ok=True)
        (fr / sub / "SKILL.md").write_text("a")
        (tr / sub / "SKILL.md").write_text("b")
    trans = "## 2.0.0\n"
    (fr / "TRANSITION.md").write_text(trans)
    (tr / "TRANSITION.md").write_text(trans)
    code, data = _plan(
        capsys, "--role", role, "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 0
    changed = data["buckets"]["charter"]["changed"]
    assert "skills/showrunner-resume/SKILL.md" in changed
    assert "skills/showrunner-handoff/SKILL.md" in changed


def test_diff_buckets(capsys, tmp_path):
    cache = tmp_path / "cache"
    role = "showrunner"
    fr = cache / "1.0.0"
    tr = cache / "2.0.0"
    for root in (fr, tr):
        for sub in (
            f"skills/{role}/reference",
            "skills/workhorse",
            "rubric",
            "hooks",
            "lib",
            "lib/tests",
            "bin",
        ):
            os.makedirs(root / sub, exist_ok=True)
    (fr / "skills" / role / "reference" / "chg.md").write_text("a")
    (tr / "skills" / role / "reference" / "chg.md").write_text("b")
    (tr / "skills" / role / "reference" / "add.md").write_text("new")
    (fr / "skills" / role / "reference" / "rem.md").write_text("old")
    (fr / "skills" / "workhorse" / "SKILL.md").write_text("a")
    (tr / "skills" / "workhorse" / "SKILL.md").write_text("b")
    (fr / "rubric" / "covenant.md").write_text("a")
    (tr / "rubric" / "covenant.md").write_text("b")
    (tr / "hooks" / "add.json").write_text("{}")
    (fr / "hooks" / "rem.json").write_text("{}")
    (tr / "lib" / "x.py").write_text("new")
    (fr / "lib" / "gone.py").write_text("x")
    (fr / "bin" / "y").write_text("a")
    (tr / "bin" / "y").write_text("b")
    (tr / "lib" / "tests" / "test_x.py").write_text("new")
    (fr / "skills" / "workhorse" / "old.md").write_text("o")
    trans = "## 2.0.0\n"
    (fr / "TRANSITION.md").write_text(trans)
    (tr / "TRANSITION.md").write_text(trans)
    code, data = _plan(
        capsys, "--role", role, "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 0
    b = data["buckets"]
    assert len(b["charter"]["added"]) == len(b["charter"]["removed"]) == len(b["charter"]["changed"]) == 1
    assert f"skills/{role}/reference/add.md" in b["charter"]["added"]
    assert f"skills/{role}/reference/rem.md" in b["charter"]["removed"]
    assert f"skills/{role}/reference/chg.md" in b["charter"]["changed"]
    assert b["other"]["added"] == ["lib/tests/test_x.py"]
    assert b["other"]["removed"] == ["skills/workhorse/old.md"]
    assert b["other"]["changed"] == ["skills/workhorse/SKILL.md"]
    assert b["covenantHooks"]["added"] == ["hooks/add.json"]
    assert b["covenantHooks"]["removed"] == ["hooks/rem.json"]
    assert b["covenantHooks"]["changed"] == ["rubric/covenant.md"]
    assert b["libs"]["added"] == ["lib/x.py"]
    assert b["libs"]["removed"] == ["lib/gone.py"]
    assert b["libs"]["changed"] == ["bin/y"]


def test_ignore_skip_components(capsys, tmp_path):
    cache = tmp_path / "cache"
    fr, tr = cache / "1.0.0", cache / "2.0.0"
    for root in (fr, tr):
        os.makedirs(root / "lib" / "__pycache__", exist_ok=True)
    (fr / "lib" / "__pycache__" / "x.pyc").write_bytes(b"a")
    (tr / "lib" / "__pycache__" / "x.pyc").write_bytes(b"b")
    (fr / ".in_use").write_text("a")
    (tr / ".in_use").write_text("b")
    (fr / ".orphaned_at").write_text("a")
    (tr / ".orphaned_at").write_text("b")
    trans = "## 2.0.0\n"
    (fr / "TRANSITION.md").write_text(trans)
    (tr / "TRANSITION.md").write_text(trans)
    code, data = _plan(
        capsys, "--role", "detective", "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 0
    for bucket in data["buckets"].values():
        assert bucket["added"] == []
        assert bucket["removed"] == []
        assert bucket["changed"] == []


def test_up_to_date(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    code, data = _plan(
        capsys, "--role", "showrunner", "--from-root", str(cache / "1.0.0"),
    )
    assert code == 0
    assert data["upToDate"] is True
    assert data["transitionSections"] == []
    assert data["missingTransitionSections"] == []
    for bucket in data["buckets"].values():
        assert bucket == {"added": [], "removed": [], "changed": []}


def test_from_cache_dir_matches_from_root(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    _mkver(cache, "2.0.0")
    (cache / "2.0.0" / "TRANSITION.md").write_text("## 2.0.0\n")
    _, a = _plan(
        capsys, "--role", "showrunner", "--from-root", str(cache / "1.0.0"), "--to", "2.0.0",
    )
    _, b = _plan(
        capsys, "--role", "showrunner", "--from", "1.0.0", "--cache-dir", str(cache), "--to", "2.0.0",
    )
    assert a == b


def test_refuse_cache_dir_missing(capsys, tmp_path):
    code, data = _plan(
        capsys, "--role", "showrunner", "--from", "1.0.0",
        "--cache-dir", str(tmp_path / "nope"),
    )
    assert code == 1
    assert data["reason"] == "cache-dir-missing"


def test_refuse_from_not_installed_non_version_basename(capsys, tmp_path):
    cache = tmp_path / "cache"
    os.makedirs(cache / "not-a-version")
    code, data = _plan(
        capsys, "--role", "showrunner", "--from-root", str(cache / "not-a-version"),
    )
    assert code == 1
    assert data["reason"] == "from-not-installed"


def test_refuse_from_not_installed_version_absent(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    code, data = _plan(
        capsys, "--role", "showrunner", "--from", "9.9.9", "--cache-dir", str(cache),
    )
    assert code == 1
    assert data["reason"] == "from-not-installed"


def test_refuse_to_not_installed(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    code, data = _plan(
        capsys, "--role", "showrunner", "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 1
    assert data["reason"] == "to-not-installed"


def test_refuse_to_older_than_from(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    _mkver(cache, "2.0.0")
    code, data = _plan(
        capsys, "--role", "showrunner", "--from", "2.0.0", "--to", "1.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 1
    assert data["reason"] == "to-older-than-from"


def test_refuse_transition_unreadable(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    _mkver(cache, "2.0.0")
    code, data = _plan(
        capsys, "--role", "showrunner", "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 1
    assert data["reason"] == "transition-unreadable"


def test_bad_role_exit_2():
    with pytest.raises(SystemExit) as exc:
        av.main(["plan", "--role", "nope", "--from-root", "/tmp/x"])
    assert exc.value.code == 2


def test_cli_subprocess_entry(tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    proc = _subplan("--role", "showrunner", "--from-root", str(cache / "1.0.0"))
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["ok"] is True


def test_read_only_snapshot(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "1.0.0")
    _mkver(cache, "2.0.0")
    (cache / "2.0.0" / "TRANSITION.md").write_text("## 2.0.0\n")
    (cache / "1.0.0" / "lib").mkdir()
    (cache / "1.0.0" / "lib" / "a.py").write_text("x")
    (cache / "2.0.0" / "lib").mkdir()
    (cache / "2.0.0" / "lib" / "a.py").write_text("y")

    def snap(root):
        items = []
        for dp, _, fns in os.walk(root):
            for fn in fns:
                p = os.path.join(dp, fn)
                items.append((p, open(p, "rb").read()))
        return sorted(items)

    before = snap(cache)
    code, _ = _plan(
        capsys, "--role", "showrunner", "--from", "1.0.0", "--to", "2.0.0",
        "--cache-dir", str(cache),
    )
    assert code == 0
    assert snap(cache) == before
