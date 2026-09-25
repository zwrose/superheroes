# plugins/superheroes/lib/tests/test_configure_view_vet_checks.py
import importlib.util
import os
import subprocess
import sys

import pytest

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


CV = _load("configure_view")
CM = _load("core_md")
MR = _load("mode_registry")

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}


def _init_repo(d):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(d), "remote", "add", "origin", "git@github.com:o/r.git"],
        check=True,
    )


def _setup_repo(tmp_path, extra_block=None):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    if extra_block:
        path = CM.core_path(repo, store)
        import json

        text = open(path).read()
        inner = CM._JSON_BLOCK.search(text).group(1)
        block = json.loads(inner)
        block.update(extra_block)
        open(path, "w").write(text.replace(inner, json.dumps(block, indent=2)))
    return repo, store


def _vet_section(screen):
    start = screen.index("### Vet checks")
    chunk = screen[start:]
    end = chunk.find("\n## ", 1)
    return chunk[:end] if end != -1 else chunk


def test_view_none_declared(tmp_path):
    # axis: absent vetChecks key renders as none declared (not unreadable)
    repo, store = _setup_repo(tmp_path)
    screen = CV.render(repo, root=store)
    section = _vet_section(screen)
    assert "(none declared — the vet runs no project vet checks)" in section


def test_view_declared_empty(tmp_path):
    # axis: vetChecks [] renders declared-empty copy distinct from absence
    repo, store = _setup_repo(tmp_path, extra_block={"vetChecks": []})
    screen = CV.render(repo, root=store)
    section = _vet_section(screen)
    assert "(declared empty — zero vet checks)" in section


def test_view_declared_checks(tmp_path):
    # axis: valid vetChecks list renders each check's three fields
    checks = [{"name": "A", "evidence": "e", "records": "r"}]
    repo, store = _setup_repo(tmp_path, extra_block={"vetChecks": checks})
    screen = CV.render(repo, root=store)
    section = _vet_section(screen)
    assert "- A" in section
    assert "evidence: e" in section
    assert "the vet records: r" in section


def test_view_malformed_no_none_declared(tmp_path):
    # axis: malformed vetChecks shows unreadable + per-entry reasons (not none declared)
    repo, store = _setup_repo(tmp_path, extra_block={"vetChecks": [{"name": ""}]})
    screen = CV.render(repo, root=store)
    section = _vet_section(screen)
    assert "⚠ vet checks unreadable: vet-checks-malformed" in section
    assert "⚠ malformed entry" in section
    assert "(none declared" not in section


def test_view_no_core_branch(tmp_path):
    # axis: core-md-absent renders plain none-declared copy without unreadable warning
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    screen = CV.render(repo, root=store)
    section = _vet_section(screen)
    assert "(none declared — the vet runs no project vet checks)" in section
    assert "unreadable" not in section
    assert "⚠" not in section


def test_view_read_failure_monkeypatch(tmp_path, monkeypatch):
    # axis: read_vet_checks failure surfaces vet-checks-read-failed in the view
    repo, store = _setup_repo(tmp_path)

    def _boom(*a, **k):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(CV.core_md, "read_vet_checks", _boom)
    screen = CV.render(repo, root=store)
    assert "### Vet checks" in screen
    assert "⚠ vet checks unreadable: vet-checks-read-failed" in screen
