# plugins/superheroes/lib/tests/test_project_config.py
"""Conformance: the thirteen configuration items registry, read contract, setter, and dependencies."""
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
GS = _load("guardian_sweep")

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

_GUARDIAN_BLOCK = {
    "thresholds": {"complexity": 42},
    "coverage": ["src/"],
    "vitals": False,
    "verifyBudgetSeconds": 120,
    "reportCard": {"enabled": True},
    "cadence": {"minMerges": 10, "minDays": 14},
}

_VALID_LADDER = [
    {
        "name": "high",
        "examples": [{"text": "data loss", "citation": "runbook §2"}],
    }
]


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


def _setup_repo(tmp_path, schema=None, extra_block=None, *, unstamped=False):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    if schema is None:
        facts = dict(_CORE_FACTS)
        if unstamped:
            facts["threatModel"] = ""
        CM.write(repo, facts, "confirmed", root=store, now="2026-06-26")
    else:
        CM.mode_registry.ensure_project_store(repo, store)
        _write_core(repo, schema, extra_block=extra_block)
    return repo, store


def _write_guardian_layer(repo, store, config_block=None):
    layer = CM.layer_path(repo, "guardian", store)
    os.makedirs(os.path.dirname(layer), exist_ok=True)
    body = "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
    if config_block is not None:
        body += "```json guardian-config\n%s\n```\n" % json.dumps(config_block, indent=2)
    open(layer, "w").write(body)
    return layer


def _item_by_slug(payload, slug):
    for item in payload["items"]:
        if item["slug"] == slug:
            return item
    raise KeyError(slug)


def test_registry_has_thirteen_items_in_order():
    assert len(PC.ITEMS) == 13
    assert [item["number"] for item in PC.ITEMS] == list(range(1, 14))
    assert [item["slug"] for item in PC.ITEMS] == [
        "severityLadder",
        "p0Definition",
        "dial",
        "budgetN",
        "groundTruthSources",
        "digestFloor",
        "conditionWindows",
        "stackingTool",
        "keepOrRetireReporting",
        "threatModel",
        "guardianStaleness",
        "keepList",
        "materialConsequenceLine",
    ]


def test_exactly_five_plugin_defaults():
    # axis: exactly five items carry a plugin default — wo_b_1276_default-count
    defaulted = [item for item in PC.ITEMS if item["plugin_default"] is not None]
    assert len(defaulted) == 5
    assert {item["slug"] for item in defaulted} == {
        "dial",
        "budgetN",
        "conditionWindows",
        "keepOrRetireReporting",
        "guardianStaleness",
    }


def test_view_lists_all_thirteen_unstamped_profile(tmp_path):
    repo, store = _setup_repo(tmp_path, unstamped=True)
    got = PC.view(repo, root=store)
    assert len(got["items"]) == 13
    assert [item["slug"] for item in got["items"]] == [item["slug"] for item in PC.ITEMS]
    plugin_default = [item for item in got["items"] if item["source"] == "plugin-default"]
    derived = [item for item in got["items"] if item["source"] == "derived"]
    unset = [item for item in got["items"] if item["source"] == "unset"]
    assert len(plugin_default) == 4
    assert len(derived) == 1
    assert derived[0]["slug"] == "budgetN"
    assert len(unset) == 8


def test_budget_n_derived_when_absent(tmp_path):
    repo, store = _setup_repo(tmp_path)
    item = _item_by_slug(PC.read(repo, root=store), "budgetN")
    assert item["raw"] is None
    assert item["source"] == "derived"
    assert item["effective"] == PC.BUDGET_DERIVATION_PROSE


def test_budget_n_stamped_integer(tmp_path):
    repo, store = _setup_repo(tmp_path)
    PC.set_item(repo, "budgetN", 4, root=store)
    item = _item_by_slug(PC.read(repo, root=store), "budgetN")
    assert item["raw"] == 4
    assert item["source"] == "stamped"
    assert item["effective"] == 4


def test_derive_budget_floors_at_one():
    assert PC.derive_budget({"min": 20, "max": 30}, 1) == 1
    assert PC.derive_budget(1, 10) == 1
    assert PC.derive_budget({"min": 50, "max": 50}, 10) == 5


def test_set_preserves_sibling_project_configuration_keys(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config(repo, _PROJECT_CFG_SEED, root=store)
    before = dict(CM.read(repo, root=store)["projectConfiguration"])
    res = PC.set_item(repo, "digestFloor", "weekly", root=store)
    assert res["action"] == "written"
    after = dict(CM.read(repo, root=store)["projectConfiguration"])
    for key, value in before.items():
        if key != "digestFloor":
            assert after[key] == value


def test_set_threat_model_leaves_json_block_untouched(tmp_path):
    repo, store = _setup_repo(tmp_path)
    before_text = open(CM.core_path(repo, store), encoding="utf-8").read()
    before_block = json.loads(CM._JSON_BLOCK.search(before_text).group(1))
    res = PC.set_item(repo, "threatModel", "multi-tenant", root=store)
    assert res["action"] == "written"
    after_text = open(CM.core_path(repo, store), encoding="utf-8").read()
    after_block = json.loads(CM._JSON_BLOCK.search(after_text).group(1))
    assert after_block == before_block
    assert CM.read(repo, root=store)["threatModel"] == "multi-tenant"


def test_set_guardian_staleness_preserves_sibling_knobs(tmp_path):
    repo, store = _setup_repo(tmp_path)
    layer = _write_guardian_layer(repo, store, dict(_GUARDIAN_BLOCK))
    before = json.loads(GS._CONFIG_BLOCK.search(open(layer).read()).group(1))
    res = PC.set_item(repo, "guardianStaleness", {"minMerges": 5, "minDays": 7}, root=store)
    assert res["action"] == "written"
    after = json.loads(GS._CONFIG_BLOCK.search(open(layer).read()).group(1))
    assert after["cadence"] == {"minMerges": 5, "minDays": 7}
    for key in ("thresholds", "coverage", "vitals", "verifyBudgetSeconds", "reportCard"):
        assert after[key] == before[key]


def test_set_severity_ladder_refuses_missing_citation(tmp_path):
    repo, store = _setup_repo(tmp_path)
    bad = [{"name": "high", "examples": [{"text": "data loss"}]}]
    res = PC.set_item(repo, "severityLadder", bad, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == PC.REASON_LADDER_CITATION_REQUIRED


def test_set_unknown_slug_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    res = PC.set_item(repo, "notAnItem", True, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == PC.REASON_UNKNOWN_SLUG


def test_get_unknown_slug_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = PC.get_item(repo, "notAnItem", root=store)
    assert got["action"] == "refused"
    assert got["reason"] == PC.REASON_UNKNOWN_SLUG


def test_read_no_profile(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    got = PC.read(repo, root=store)
    assert got["profileAbsent"] is True
    assert got["behind"] is False
    item = _item_by_slug(got, "dial")
    assert item["source"] == "plugin-default"
    item = _item_by_slug(got, "severityLadder")
    assert item["source"] == "unset"


def test_read_corrupt_profile(tmp_path):
    repo, store = _setup_repo(tmp_path)
    open(CM.core_path(repo, store), "w").write("not core\n")
    got = PC.read(repo, root=store)
    assert got["profileUnparseable"] is True


def test_read_behind_schema(tmp_path):
    repo, store = _setup_repo(tmp_path, schema=CM.SCHEMA_VERSION + 1)
    got = PC.read(repo, root=store)
    assert got["behind"] is True
    res = PC.set_item(repo, "dial", 25, root=store)
    assert res["action"] == "behind"


def test_read_absent_project_configuration_key(tmp_path):
    repo, store = _setup_repo(tmp_path)
    item = _item_by_slug(PC.read(repo, root=store), "stackingTool")
    assert item["raw"] is None
    assert item["source"] == "unset"


def test_read_non_object_project_configuration(tmp_path):
    repo, store = _setup_repo(
        tmp_path,
        schema=CM.SCHEMA_VERSION,
        extra_block={CM.PROJECT_CONFIGURATION_KEY: "bad"},
    )
    item = _item_by_slug(PC.read(repo, root=store), "stackingTool")
    assert item["raw"] is None
    assert item["source"] == "unset"


def test_read_malformed_item_value(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config(repo, {"dial": "not-a-dial"}, root=store)
    item = _item_by_slug(PC.read(repo, root=store), "dial")
    assert item["malformed"] is True
    assert item["source"] == "unset"
    assert item["effective"] is None


def test_set_malformed_value_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    res = PC.set_item(repo, "dial", "bad", root=store)
    assert res["action"] == "refused"


def test_guardian_absent_reads_plugin_default(tmp_path):
    repo, store = _setup_repo(tmp_path)
    item = _item_by_slug(PC.read(repo, root=store), "guardianStaleness")
    assert item["raw"] is None
    assert item["source"] == "plugin-default"
    assert item["effective"] == dict(GS.CADENCE_DEFAULTS)


def test_guardian_layer_without_fence_reads_plugin_default(tmp_path):
    repo, store = _setup_repo(tmp_path)
    layer = CM.layer_path(repo, "guardian", store)
    os.makedirs(os.path.dirname(layer), exist_ok=True)
    open(layer, "w").write("<!-- guardian: schemaVersion=1 status=confirmed -->\n")
    item = _item_by_slug(PC.read(repo, root=store), "guardianStaleness")
    assert item["raw"] is None
    assert item["source"] == "plugin-default"


def test_guardian_stamped_cadence_reads_stamped(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _write_guardian_layer(repo, store, {"cadence": {"minMerges": 12, "minDays": 7}})
    item = _item_by_slug(PC.read(repo, root=store), "guardianStaleness")
    assert item["source"] == "stamped"
    assert item["raw"] == {"minMerges": 12, "minDays": 7}


def test_guardian_stamped_defaults_still_stamped(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _write_guardian_layer(repo, store, {"cadence": dict(GS.CADENCE_DEFAULTS)})
    item = _item_by_slug(PC.read(repo, root=store), "guardianStaleness")
    assert item["source"] == "stamped"


def test_set_passes_through_core_md_refusal(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    res = PC.set_item(repo, "dial", 25, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == PC.REASON_PROFILE_ABSENT


def test_set_passes_through_deferred(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)

    @contextlib.contextmanager
    def _contended(cwd, root=None):
        yield False

    monkeypatch.setattr(CM.mode_registry, "config_lock", _contended)
    res = PC.set_item(repo, "dial", 25, root=store)
    assert res["action"] == "deferred"


def test_set_read_mismatch_reported(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    real_read = PC.read

    def _lying_read(cwd, root=None):
        payload = real_read(cwd, root)
        for item in payload["items"]:
            if item["slug"] == "dial":
                item["raw"] = 99
        return payload

    monkeypatch.setattr(PC, "read", _lying_read)
    res = PC.set_item(repo, "dial", 25, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == PC.REASON_SET_MISMATCH


@pytest.mark.parametrize("slug", [
    "launchLedger",
    "collector",
    "keepOrRetireBackfill",
    "detectorTestBoundary",
])
def test_dependencies_fallback_when_absent(tmp_path, monkeypatch, slug):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr(PC, "_detect_launch_ledger", lambda *a, **k: None)
    monkeypatch.setattr(PC, "_detect_detector_test_boundary", lambda: None)
    got = PC.dependencies(repo, root=store)
    assert got[slug]["status"] == "absent"
    assert "fallback" in got[slug]


def test_dependency_detector_boundary_detected():
    got = PC.dependencies(_REPO_ROOT, root=None)
    assert got["detectorTestBoundary"]["status"] == "detected"


def test_dependency_collector_declared(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_declared_dependencies(repo, {"collector": "pinned"}, root=store)
    got = PC.dependencies(repo, root=store)
    assert got["collector"]["status"] == "declared"


def test_cli_view(tmp_path, capsys):
    repo, store = _setup_repo(tmp_path)
    rc = PC.main(["view", "--cwd", repo, "--root", store])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["items"]) == 13


def test_cli_get_and_set(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO("25"))
    rc = PC.main(["set", "--item", "dial", "--cwd", repo, "--root", store])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["action"] == "written"
    rc = PC.main(["get", "--item", "dial", "--cwd", repo, "--root", store])
    assert rc == 0
    got = json.loads(capsys.readouterr().out)
    assert got["raw"] == 25
    assert got["source"] == "stamped"


def test_cli_dependencies(tmp_path, capsys):
    repo, store = _setup_repo(tmp_path)
    rc = PC.main(["dependencies", "--cwd", repo, "--root", store])
    assert rc == 0
    got = json.loads(capsys.readouterr().out)
    assert "collector" in got
