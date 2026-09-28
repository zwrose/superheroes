import json
import os
import subprocess
import sys

import pytest

import adopt_version as av

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_SCRIPT = os.path.join(_LIB, "adopt_version.py")
ROLE = "workhorse"


def _cache(tmp_path, versions):
    for ver, files in versions.items():
        root = tmp_path / ver
        root.mkdir(parents=True)
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if content is None:
                path.symlink_to("target")
            else:
                path.write_text(content, encoding="utf-8")


def _plan(capsys, cache, from_ver, to_ver=None, from_root=None, role=ROLE):
    cache = os.path.abspath(str(cache))
    if from_root is not None:
        argv = ["plan", "--role", role, "--from-root", from_root]
    else:
        argv = ["plan", "--role", role, "--from", from_ver, "--cache-dir", cache]
    if to_ver is not None:
        argv.extend(["--to", to_ver])
    code = av.main(argv)
    out = capsys.readouterr().out.strip()
    return code, json.loads(out) if out else {}


def _snapshot_tree(root):
    root = os.path.abspath(root)
    snap = {}
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            snap[rel] = open(full, "rb").read()
    return snap


def test_installed_list_and_default_to(tmp_path, capsys):
    for name in ("0.9.0", "0.10.0", "0.35.1", "foo"):
        (tmp_path / name).mkdir()
    (tmp_path / "bar.txt").write_text("x")
    (tmp_path / "0.35.1" / "TRANSITION.md").write_text("## 0.35.1\n", encoding="utf-8")
    code, data = _plan(capsys, tmp_path, "0.9.0")
    assert code == 0
    assert data["installed"] == ["0.9.0", "0.10.0", "0.35.1"]
    assert data["to"] == "0.35.1"


def test_transition_sections_between_versions(tmp_path, capsys):
    transition = """\
## 0.35.1
### Before you upgrade
note
## 0.20.0
### Other
## 0.10.0
## 0.9.0
```
## 0.30.0
```
"""
    _cache(tmp_path, {
        "0.9.0": {"keep.txt": "same"},
        "0.10.0": {"keep.txt": "same"},
        "0.35.1": {"keep.txt": "same", "TRANSITION.md": transition},
    })
    code, data = _plan(capsys, tmp_path, "0.9.0", to_ver="0.35.1")
    assert code == 0
    secs = data["transitionSections"]
    assert [s["version"] for s in secs] == ["0.35.1", "0.20.0", "0.10.0"]
    assert secs[0]["line"] == 1
    assert secs[0]["beforeYouUpgrade"] is True
    assert secs[1]["beforeYouUpgrade"] is False
    assert secs[2]["beforeYouUpgrade"] is False


def test_missing_transition_sections(tmp_path, capsys):
    transition = "## 0.10.0\n"
    _cache(tmp_path, {
        "0.9.0": {},
        "0.10.0": {},
        "0.35.1": {"TRANSITION.md": transition},
    })
    code, data = _plan(capsys, tmp_path, "0.9.0", to_ver="0.35.1")
    assert code == 0
    assert data["missingTransitionSections"] == ["0.35.1"]


def test_diff_buckets(tmp_path, capsys):
    other_role = "showrunner"
    _cache(tmp_path, {
        "1.0.0": {
            f"skills/{ROLE}/old.md": "a",
            f"skills/{other_role}/SKILL.md": "a",
            "rubric/covenant.md": "a",
            "hooks/hooks.json": "a",
            "lib/x.py": "a",
            "bin/y": "a",
            "lib/tests/test_x.py": "a",
            "same.txt": "same",
        },
        "2.0.0": {
            f"skills/{ROLE}/new.md": "b",
            f"skills/{other_role}/SKILL.md": "b",
            "rubric/covenant.md": "b",
            "hooks/hooks.json": "b",
            "lib/x.py": "b",
            "bin/y": "b",
            "lib/tests/test_x.py": "b",
            "same.txt": "same",
            "TRANSITION.md": "## 2.0.0\n",
        },
    })
    code, data = _plan(capsys, tmp_path, "1.0.0", to_ver="2.0.0")
    assert code == 0
    b = data["buckets"]
    assert b["charter"]["added"] == [f"skills/{ROLE}/new.md"]
    assert b["charter"]["removed"] == [f"skills/{ROLE}/old.md"]
    assert b["charter"]["changed"] == []
    assert b["covenantHooks"]["changed"] == ["hooks/hooks.json", "rubric/covenant.md"]
    assert b["libs"]["changed"] == ["bin/y", "lib/x.py"]
    assert b["other"]["changed"] == ["lib/tests/test_x.py", f"skills/{other_role}/SKILL.md"]
    assert "same.txt" not in sum((b[k][t] for k in b for t in b[k]), [])


def test_ignore_pycache_and_marker_paths(tmp_path, capsys):
    transition = "## 2.0.0\n"
    _cache(tmp_path, {
        "1.0.0": {
            "__pycache__/x.pyc": "a",
            ".in_use": "a",
            ".orphaned_at": "a",
            "TRANSITION.md": transition,
        },
        "2.0.0": {
            "__pycache__/x.pyc": "b",
            ".in_use": "b",
            ".orphaned_at": "b",
            "TRANSITION.md": transition,
        },
    })
    code, data = _plan(capsys, tmp_path, "1.0.0", to_ver="2.0.0")
    assert code == 0
    for bk in data["buckets"].values():
        for lst in bk.values():
            assert lst == []


def test_up_to_date(tmp_path, capsys):
    _cache(tmp_path, {"1.0.0": {"x.txt": "a"}})
    code, data = _plan(capsys, tmp_path, "1.0.0", to_ver="1.0.0")
    assert code == 0
    assert data["upToDate"] is True
    assert data["transitionSections"] == []
    assert data["missingTransitionSections"] == []
    assert data["counts"] == {"charter": 0, "covenantHooks": 0, "libs": 0, "other": 0}


def test_from_and_from_root_equivalent(tmp_path, capsys):
    _cache(tmp_path, {
        "1.0.0": {"a.txt": "1"},
        "2.0.0": {"a.txt": "2", "TRANSITION.md": "## 2.0.0\n"},
    })
    from_root = os.path.join(str(tmp_path), "1.0.0")
    code_a, data_a = _plan(capsys, tmp_path, "1.0.0", from_root=from_root)
    code_b, data_b = _plan(capsys, tmp_path, "1.0.0", to_ver="2.0.0")
    assert code_a == code_b == 0
    for key in ("installed", "from", "to", "buckets", "counts", "transitionSections"):
        assert data_a[key] == data_b[key]


@pytest.mark.parametrize(
    "reason,setup,argv_extra",
    [
        ("cache-dir-missing", lambda p: None, ["--from", "1.0.0", "--cache-dir", "/no/such/cache"]),
        ("from-not-installed", lambda p: None, ["--from", "not-a-version", "--cache-dir"]),
        ("from-not-installed", lambda p: (p / "1.0.0").mkdir(), ["--from", "9.9.9", "--cache-dir"]),
        ("to-not-installed", lambda p: (p / "1.0.0").mkdir(), ["--from", "1.0.0", "--cache-dir", "--to", "9.9.9"]),
        ("to-older-than-from", lambda p: [(p / v).mkdir() for v in ("1.0.0", "2.0.0")],
         ["--from", "2.0.0", "--cache-dir", "--to", "1.0.0"]),
        ("transition-unreadable", lambda p: [(p / v).mkdir() for v in ("1.0.0", "2.0.0")],
         ["--from", "1.0.0", "--cache-dir", "--to", "2.0.0"]),
    ],
)
def test_refusal_tokens(tmp_path, capsys, reason, setup, argv_extra):
    setup(tmp_path)
    cache = str(tmp_path)
    argv = ["plan", "--role", ROLE]
    resolved = []
    i = 0
    while i < len(argv_extra):
        tok = argv_extra[i]
        if tok == "--cache-dir":
            resolved.append("--cache-dir")
            i += 1
            if i < len(argv_extra) and not argv_extra[i].startswith("--"):
                resolved.append(argv_extra[i])
                i += 1
            else:
                resolved.append(cache)
        else:
            resolved.append(tok)
            i += 1
    code = av.main(argv + resolved)
    data = json.loads(capsys.readouterr().out)
    assert code == 1
    assert data["reason"] == reason


def test_bad_role_exit_2():
    with pytest.raises(SystemExit) as exc:
        av.main(["plan", "--role", "invalid", "--from", "1.0.0", "--cache-dir", "/tmp"])
    assert exc.value.code == 2


def test_subprocess_entry(tmp_path):
    _cache(tmp_path, {
        "1.0.0": {},
        "2.0.0": {"TRANSITION.md": "## 2.0.0\n"},
    })
    cache = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-B", _SCRIPT, "plan", "--role", ROLE,
         "--from", "1.0.0", "--cache-dir", cache, "--to", "2.0.0"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["ok"] is True


def test_read_only_snapshot(tmp_path, capsys):
    _cache(tmp_path, {
        "1.0.0": {"z.txt": "a"},
        "2.0.0": {"z.txt": "b", "TRANSITION.md": "## 2.0.0\n"},
    })
    before = _snapshot_tree(tmp_path)
    code, _ = _plan(capsys, tmp_path, "1.0.0", to_ver="2.0.0")
    assert code == 0
    assert _snapshot_tree(tmp_path) == before
