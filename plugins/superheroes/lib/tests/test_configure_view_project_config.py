# plugins/superheroes/lib/tests/test_configure_view_project_config.py
"""Configure view: the project-configuration block and its fail-closed edges."""
import importlib.util
import json
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
PC = _load("project_config")
CM = _load("core_md")
MR = _load("mode_registry")
GS = _load("guardian_sweep")
SC = _load("store_core")

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}


def _init_repo(d, remote=None):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)


def _setup_repo(tmp_path, schema=None, extra_block=None, *, unstamped=False):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path, "git@github.com:o/r.git")
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    if schema is None:
        facts = dict(_CORE_FACTS)
        if unstamped:
            facts["threatModel"] = ""
        CM.write(repo, facts, "confirmed", root=store, now="2026-06-26")
    else:
        CM.mode_registry.ensure_project_store(repo, store)
        block = {
            "schemaVersion": schema,
            "verifyCommand": "npm test",
            "stackTags": ["node"],
        }
        if extra_block:
            block.update(extra_block)
        cdir = os.path.join(repo, ".claude", "superheroes")
        os.makedirs(cdir, exist_ok=True)
        text = (
            "<!-- superheroes-core: schemaVersion=%d status=confirmed created=2026-06-26 "
            "updated=2026-06-26 -->\n\n## Threat model\n\nsingle-user\n\n"
            "## Canonical patterns\n\n- x: a.ts:1\n\n"
            "```json superheroes-core\n%s\n```\n"
            % (schema, json.dumps(block, indent=2))
        )
        open(os.path.join(cdir, "core.md"), "w").write(text)
    return repo, store


def _project_config_section(screen):
    start = screen.index("## Project configuration")
    rest = screen[start + len("## Project configuration") :]
    end = rest.find("\n## Layer:")
    if end == -1:
        end = rest.find("\n## Model tiers")
    block = rest[:end] if end != -1 else rest
    return block.strip().splitlines()


def _numbered_rows(lines):
    return [ln for ln in lines if ln and ln[0].isdigit() and ". " in ln]


def test_all_thirteen_items_in_registry_order_unstamped(tmp_path):
    repo, store = _setup_repo(tmp_path, unstamped=True)
    screen = CV.render(repo, root=store)
    rows = _numbered_rows(_project_config_section(screen))
    assert len(rows) == 13
    for item, row in zip(PC.ITEMS, rows):
        assert row.startswith("%d. %s —" % (item["number"], item["name"]))


def test_block_driven_by_items_registry(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    extra = {
        "number": 14,
        "slug": "testOnlyItem",
        "name": "Test-only item",
        "home": PC.HOME_PROJECT_CONFIGURATION,
        "shape": "prose",
        "plugin_default": None,
    }
    monkeypatch.setattr(CV.project_config, "ITEMS", tuple(list(PC.ITEMS) + [extra]))
    screen = CV.render(repo, root=store)
    rows = _numbered_rows(_project_config_section(screen))
    assert len(rows) == 14
    assert any("Test-only item" in row for row in rows)


def test_render_writes_nothing(tmp_path):
    # axis: rendering writes nothing — wo_e_1276_read-only-view
    repo, store = _setup_repo(tmp_path)
    core_path = CM.core_path(repo, store)
    before = open(core_path, "rb").read()
    CV.render(repo, root=store)
    after = open(core_path, "rb").read()
    assert before == after


def test_no_profile_renders_without_raising(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    screen = CV.render(repo, root=store)
    block = _project_config_section(screen)
    assert "profile: no core calibration yet" in block
    rows = _numbered_rows(block)
    assert len(rows) == 13
    assert all("unset" in row or "plugin default" in row or "derived from dial" in row for row in rows)


def test_corrupt_profile_says_unreadable_and_no_stamped(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config(repo, {"stackingTool": "gh-stack"}, root=store)
    open(CM.core_path(repo, store), "w").write("not core\n")
    screen = CV.render(repo, root=store)
    block = _project_config_section(screen)
    assert "profile: core.md unreadable" in "\n".join(block)
    assert "gh-stack" not in "\n".join(block)


def test_behind_schema_says_view_only(tmp_path):
    repo, store = _setup_repo(tmp_path, schema=CM.SCHEMA_VERSION + 1)
    screen = CV.render(repo, root=store)
    block = _project_config_section(screen)
    assert "profile: schema behind plugin — view only" in block


def test_read_raises_shows_not_available(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("read failed")

    monkeypatch.setattr(CV.project_config, "view", _boom)
    screen = CV.render(str(tmp_path), root=str(tmp_path / "store"))
    block = _project_config_section(screen)
    assert block == ["(not available)"]


def test_long_prose_stamped_truncated_for_display(tmp_path):
    repo, store = _setup_repo(tmp_path)
    long_text = "line one\n" + ("x" * 200)
    PC.set_item(repo, "p0Definition", long_text, root=store)
    screen = CV.render(repo, root=store)
    block = _project_config_section(screen)
    p0_row = next(row for row in block if row.startswith("2. P0 definition"))
    assert "xxx" in p0_row
    assert long_text not in screen
    stored = PC.get_item(repo, "p0Definition", root=store)
    assert stored["raw"] == long_text


def test_malformed_stamped_value_shown_as_malformed(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config(repo, {"dial": "not-a-dial"}, root=store)
    screen = CV.render(repo, root=store)
    block = _project_config_section(screen)
    dial_row = next(row for row in block if row.startswith("3. Dial"))
    assert "malformed" in dial_row


def test_dependencies_raises_shows_not_available(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)

    def _boom(*a, **k):
        raise RuntimeError("deps failed")

    monkeypatch.setattr(CV.project_config, "dependencies", _boom)
    screen = CV.render(repo, root=store)
    block = _project_config_section(screen)
    assert "dependencies: (not available)" in block
    assert len(_numbered_rows(block)) == 13


def test_dependencies_absent_show_fallback(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr(CV.project_config, "_detect_launch_ledger", lambda *a, **k: None)
    screen = CV.render(repo, root=store)
    block = _project_config_section(screen)
    joined = "\n".join(block)
    assert "launchLedger: absent — fallback:" in joined
    assert "collector: absent — fallback:" in joined
    assert "detectorTestBoundary: absent — fallback:" in joined
