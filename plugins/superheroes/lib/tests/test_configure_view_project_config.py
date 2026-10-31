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


_RETIRED_NAMES = ("Dial", "Budget N")


def _expected_rows():
    return ["%d. %s" % (item["number"], item["name"]) for item in PC.ITEMS]


def test_all_items_in_registry_order_unstamped(tmp_path):
    # axis: the view lists every registry item, in order, and no retired one
    repo, store = _setup_repo(tmp_path, unstamped=True)
    screen = CV.render(repo, root=store)
    rows = _numbered_rows(_project_config_section(screen))
    assert [row.split(" — ", 1)[0] for row in rows] == _expected_rows()
    assert not any(name in row for row in rows for name in _RETIRED_NAMES)


def test_stale_dial_and_budget_n_stamps_are_not_shown(tmp_path):
    # axis: a profile still carrying a stamped dial or budgetN renders without a dial row
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config(repo, {"dial": {"min": 5, "max": 10}, "budgetN": 3}, root=store)
    block = _project_config_section(CV.render(repo, root=store))
    rows = _numbered_rows(block)
    assert [row.split(" — ", 1)[0] for row in rows] == _expected_rows()
    text = "\n".join(block)
    assert "Dial" not in text and "Budget N" not in text and "dial" not in text
    assert "malformed" not in text


def test_block_driven_by_items_registry(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    extra = {
        "number": 20,
        "slug": "testOnlyItem",
        "name": "Test-only item",
        "home": PC.HOME_PROJECT_CONFIGURATION,
        "shape": "prose",
        "plugin_default": None,
    }
    monkeypatch.setattr(CV.project_config, "ITEMS", tuple(list(PC.ITEMS) + [extra]))
    screen = CV.render(repo, root=store)
    rows = _numbered_rows(_project_config_section(screen))
    assert len(rows) == 18
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
    assert len(rows) == 17
    assert all("unset" in row or "plugin default" in row for row in rows)


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
    CM.write_project_config(repo, {"conditionWindows": "not-windows"}, root=store)
    screen = CV.render(repo, root=store)
    block = _project_config_section(screen)
    windows_row = next(row for row in block if row.startswith("7. Condition windows"))
    assert "malformed" in windows_row


def test_dependencies_raises_shows_not_available(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)

    def _boom(*a, **k):
        raise RuntimeError("deps failed")

    monkeypatch.setattr(CV.project_config, "dependencies", _boom)
    screen = CV.render(repo, root=store)
    block = _project_config_section(screen)
    assert "dependencies: (not available)" in block
    assert len(_numbered_rows(block)) == 17


def test_dependencies_absent_show_fallback(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr(CV.project_config, "_detect_launch_ledger", lambda *a, **k: None)
    screen = CV.render(repo, root=store)
    block = _project_config_section(screen)
    joined = "\n".join(block)
    assert "launchLedger: absent — fallback:" in joined
    assert "collector: absent — fallback:" in joined
    assert "detectorTestBoundary: absent — fallback:" in joined


def test_item_14_row_follows_item_10_and_reads_unset(tmp_path):
    repo, store = _setup_repo(tmp_path, unstamped=True)
    rows = _numbered_rows(_project_config_section(CV.render(repo, root=store)))
    numbers = [row.split(".", 1)[0] for row in rows]
    assert numbers[numbers.index("10") + 1] == "14"
    assert rows[numbers.index("14")] == (
        "14. Who it's for and what it's for — unset (absence disables the rules that read it)"
    )


def test_item_14_stamped_shows_as_one_line_of_prose(tmp_path):
    repo, store = _setup_repo(tmp_path)
    PC.set_item(repo, "whoItsFor", "Home cooks\nwho want a weeknight recipe.", root=store)
    block = _project_config_section(CV.render(repo, root=store))
    row = next(r for r in block if r.startswith("14. "))
    assert row == "14. Who it's for and what it's for — Home cooks who want a weeknight recipe."


def test_adopted_item_13_row_points_to_canon(tmp_path):
    repo, store = _setup_repo(tmp_path)
    subprocess.run(["git", "-C", repo, "remote", "remove", "origin"], check=True)
    CM.write_project_config_item(
        repo, "materialConsequenceLine",
        {"canon": "standing-rulings", "migratedOn": "2026-10-05"}, root=store)
    block = _project_config_section(CV.render(repo, root=store))
    row = next(r for r in block if r.startswith("13. "))
    import definition_doc

    canon_path = definition_doc.resolve_canon(root=repo, cwd=repo, store_root=store)["path"]
    assert row == (
        "13. Material consequence line — points to the project's Canon standing rulings (%s)"
        " — no value of its own" % canon_path)


def test_adopted_item_13_row_survives_a_failed_canon_lookup(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config_item(
        repo, "materialConsequenceLine",
        {"canon": "standing-rulings", "migratedOn": "2026-10-05"}, root=store)
    import definition_doc

    def _boom(**kwargs):
        raise definition_doc.CanonLookupError("no default ref")

    monkeypatch.setattr(definition_doc, "resolve_canon", _boom)
    block = _project_config_section(CV.render(repo, root=store))
    row = next(r for r in block if r.startswith("13. "))
    assert row == (
        "13. Material consequence line — points to the project's Canon standing rulings"
        " (Canon lookup failed: CanonLookupError) — no value of its own")


def test_item_17_stamped_list_shows_as_json_on_its_row(tmp_path):
    # axis: a stamped list is shown as JSON, never as a Python list
    repo, store = _setup_repo(tmp_path)
    PC.set_item(repo, "cloudSetupCommands", ["npm ci", "make"], root=store)
    block = _project_config_section(CV.render(repo, root=store))
    row = next(r for r in block if r.startswith("17. "))
    assert row == '17. Cloud setup commands — ["npm ci","make"]'
