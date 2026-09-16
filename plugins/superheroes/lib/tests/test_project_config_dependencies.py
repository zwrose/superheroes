# plugins/superheroes/lib/tests/test_project_config_dependencies.py
"""Conformance: declare_dependency, its CLI, and fail-closed edges."""
import contextlib
import importlib.util
import io
import json
import os
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


PC = _load("project_config")
CM = _load("core_md")

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

_PROJECT_CFG_SEED = {
    "dial": {"min": 5, "max": 10},
    "budgetN": 3,
    "stackingTool": "gh-stack",
}


def _write_core(repo, schema_version, status="confirmed", extra_block=None):
    block = {
        "schemaVersion": schema_version,
        "verifyCommand": "npm test",
        "stackTags": ["node"],
    }
    if extra_block:
        block.update(extra_block)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    text = (
        "<!-- superheroes-core: schemaVersion=%d status=%s created=2026-06-26 "
        "updated=2026-06-26 -->\n\n## Threat model\n\nsingle-user\n\n"
        "## Canonical patterns\n\n- x: a.ts:1\n\n"
        "```json superheroes-core\n%s\n```\n"
        % (schema_version, status, json.dumps(block, indent=2))
    )
    open(os.path.join(d, "core.md"), "w").write(text)
    return text


def _setup_repo(tmp_path, schema=None, extra_block=None):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    if schema is None:
        CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    else:
        CM.mode_registry.ensure_project_store(repo, store)
        _write_core(repo, schema, extra_block=extra_block)
    return repo, store


def _item_snapshot(repo, store):
    payload = PC.read(repo, root=store)
    return {item["slug"]: item for item in payload["items"]}


def test_declare_collector_moves_absent_to_declared(tmp_path):
    repo, store = _setup_repo(tmp_path)
    before = PC.dependencies(repo, root=store)
    assert before["collector"]["status"] == "absent"
    assert "fallback" in before["collector"]
    res = PC.declare_dependency(repo, "collector", "standing-proposals", root=store)
    assert res["action"] == "written"
    after = PC.dependencies(repo, root=store)
    assert after["collector"]["status"] == "declared"
    assert "fallback" not in after["collector"]


def test_declare_preserves_other_three_declarations(tmp_path):
    # axis: sibling declarations survive — wo_h_1276_sibling-declarations
    repo, store = _setup_repo(tmp_path)
    seed = {
        "launchLedger": "ledger-path",
        "keepOrRetireBackfill": {"mode": "opportunistic"},
        "detectorTestBoundary": "rubric/bite-proof.md",
    }
    CM.write_declared_dependencies(repo, seed, root=store)
    res = PC.declare_dependency(repo, "collector", "standing-proposals", root=store)
    assert res["action"] == "written"
    got = CM.read(repo, root=store)["declaredDependencies"]
    for key, value in seed.items():
        assert got[key] == value


def test_declare_leaves_thirteen_configuration_items_unchanged(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config(repo, _PROJECT_CFG_SEED, root=store)
    before = _item_snapshot(repo, store)
    res = PC.declare_dependency(repo, "collector", "standing-proposals", root=store)
    assert res["action"] == "written"
    after = _item_snapshot(repo, store)
    assert before == after


def test_null_withdraws_declaration_and_status_returns(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_declared_dependencies(repo, {"collector": "standing-proposals"}, root=store)
    assert PC.dependencies(repo, root=store)["collector"]["status"] == "declared"
    res = PC.declare_dependency(repo, "collector", None, root=store)
    assert res["action"] == "written"
    got = PC.dependencies(repo, root=store)
    assert got["collector"]["status"] == "absent"
    assert "fallback" in got["collector"]


def test_unknown_dependency_slug_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    res = PC.declare_dependency(repo, "notADependency", "x", root=store)
    assert res["action"] == "refused"
    assert res["reason"] == PC.REASON_UNKNOWN_SLUG


def test_malformed_value_type_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    res = PC.declare_dependency(repo, "collector", 42, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == PC.REASON_MALFORMED_VALUE


def test_empty_string_value_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    res = PC.declare_dependency(repo, "collector", "   ", root=store)
    assert res["action"] == "refused"
    assert res["reason"] == PC.REASON_MALFORMED_VALUE


def test_profile_absent_refused(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    res = PC.declare_dependency(repo, "collector", "standing-proposals", root=store)
    assert res["action"] == "refused"
    assert res["reason"] == PC.REASON_PROFILE_ABSENT


def test_corrupt_profile_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    open(CM.core_path(repo, store), "w").write("not core\n")
    res = PC.declare_dependency(repo, "collector", "standing-proposals", root=store)
    assert res["action"] == "refused"
    assert res["reason"] == PC.REASON_PROFILE_UNPARSEABLE


def test_behind_schema_refused(tmp_path):
    repo, store = _setup_repo(tmp_path, schema=CM.SCHEMA_VERSION + 1)
    res = PC.declare_dependency(repo, "collector", "standing-proposals", root=store)
    assert res["action"] == "behind"


def test_non_object_declared_dependencies_replaced_on_write(tmp_path):
    repo, store = _setup_repo(
        tmp_path,
        schema=CM.SCHEMA_VERSION,
        extra_block={CM.DECLARED_DEPENDENCIES_KEY: []},
    )
    res = PC.declare_dependency(repo, "collector", "standing-proposals", root=store)
    assert res["action"] == "written"
    got = CM.read(repo, root=store)["declaredDependencies"]
    assert got == {"collector": "standing-proposals"}


def test_writer_deferred_passed_through(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)

    @contextlib.contextmanager
    def _contended(cwd, root=None):
        yield False

    monkeypatch.setattr(CM.mode_registry, "config_lock", _contended)
    res = PC.declare_dependency(repo, "collector", "standing-proposals", root=store)
    assert res["action"] == "deferred"


def test_null_absent_key_is_noop(tmp_path):
    repo, store = _setup_repo(tmp_path)
    res = PC.declare_dependency(repo, "collector", None, root=store)
    assert res["action"] == "noop"
    assert CM.read(repo, root=store)["declaredDependencies"] == {}


def test_declare_object_value_written(tmp_path):
    repo, store = _setup_repo(tmp_path)
    value = {"registry": "standing-proposals"}
    res = PC.declare_dependency(repo, "collector", value, root=store)
    assert res["action"] == "written"
    assert CM.read(repo, root=store)["declaredDependencies"]["collector"] == value


def test_declare_read_mismatch_reported(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    real_read = CM.read

    def _lying_read(cwd, root=None):
        facts = real_read(cwd, root)
        if facts is not None:
            facts = dict(facts)
            facts["declaredDependencies"] = {}
        return facts

    monkeypatch.setattr(PC.core_md, "read", _lying_read)
    res = PC.declare_dependency(repo, "collector", "standing-proposals", root=store)
    assert res["action"] == "refused"
    assert res["reason"] == PC.REASON_SET_MISMATCH


def test_cli_declare(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO('"standing-proposals"'))
    rc = PC.main([
        "declare", "--dependency", "collector", "--cwd", repo, "--root", store,
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "written"
    assert PC.dependencies(repo, root=store)["collector"]["status"] == "declared"
