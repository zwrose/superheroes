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
    assert len(PC.ITEMS) == 15
    assert [item["number"] for item in PC.ITEMS] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14, 11, 12, 13, 15]
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
        "whoItsFor",
        "guardianStaleness",
        "keepList",
        "materialConsequenceLine",
        "cloudBuilds",
    ]


def test_exactly_five_plugin_defaults():
    # axis: exactly six items carry a plugin default — wo_b_1276_default-count
    defaulted = [item for item in PC.ITEMS if item["plugin_default"] is not None]
    assert len(defaulted) == 6
    assert {item["slug"] for item in defaulted} == {
        "dial",
        "budgetN",
        "conditionWindows",
        "keepOrRetireReporting",
        "guardianStaleness",
        "cloudBuilds",
    }


def test_view_lists_all_thirteen_unstamped_profile(tmp_path):
    repo, store = _setup_repo(tmp_path, unstamped=True)
    got = PC.view(repo, root=store)
    assert len(got["items"]) == 15
    assert [item["slug"] for item in got["items"]] == [item["slug"] for item in PC.ITEMS]
    plugin_default = [item for item in got["items"] if item["source"] == "plugin-default"]
    derived = [item for item in got["items"] if item["source"] == "derived"]
    unset = [item for item in got["items"] if item["source"] == "unset"]
    assert len(plugin_default) == 5
    assert len(derived) == 1
    assert derived[0]["slug"] == "budgetN"
    assert len(unset) == 9


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
    got = PC.dependencies(repo, root=store)
    assert got[slug]["status"] == "absent"
    assert "fallback" in got[slug]


def test_dependency_detector_boundary_declared(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_declared_dependencies(
        repo, {"detectorTestBoundary": "bite-proof.md"}, root=store,
    )
    got = PC.dependencies(repo, root=store)
    assert got["detectorTestBoundary"]["status"] == "declared"


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
    assert len(payload["items"]) == 15


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


_MARKER = {"canon": "standing-rulings", "migratedOn": "2026-10-05"}


def _split_json_block(text):
    start = text.index("```json superheroes-core\n") + len("```json superheroes-core\n")
    end = text.index("\n```", start)
    return text[:start], json.loads(text[start:end]), text[end:]


def test_item_14_unset_reads_unset(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = PC.get_item(repo, "whoItsFor", root=store)
    assert got["source"] == "unset"
    assert got["raw"] is None
    assert got["malformed"] is False


def test_set_item_14_writes_only_its_own_key(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config(repo, dict(_PROJECT_CFG_SEED), root=store)
    core = CM.core_path(repo, store)
    before = open(core, encoding="utf-8").read()
    prose_before, block_before, tail_before = _split_json_block(before)
    got = PC.set_item(repo, "whoItsFor", "Home cooks who want one weeknight recipe.", root=store)
    assert got["action"] == "written"
    after = open(core, encoding="utf-8").read()
    prose_after, block_after, tail_after = _split_json_block(after)
    assert prose_after == prose_before
    assert tail_after == tail_before
    cfg_after = block_after.pop("projectConfiguration")
    cfg_before = block_before.pop("projectConfiguration")
    assert block_after == block_before
    assert cfg_after.pop("whoItsFor") == "Home cooks who want one weeknight recipe."
    assert cfg_after == cfg_before
    stored = PC.get_item(repo, "whoItsFor", root=store)
    assert stored["source"] == "stamped"
    assert stored["raw"] == "Home cooks who want one weeknight recipe."


# axis: item 14 refuses an empty or whitespace-only value — wo_a_1618_who-its-for-non-empty
@pytest.mark.parametrize("value", ["", "   ", "\n\t \n"], ids=["empty", "spaces", "newlines"])
def test_set_item_14_refuses_empty_and_whitespace(tmp_path, value):
    repo, store = _setup_repo(tmp_path)
    core = CM.core_path(repo, store)
    before = open(core, "rb").read()
    got = PC.set_item(repo, "whoItsFor", value, root=store)
    assert got == {"action": "refused", "reason": "malformed-value"}
    assert open(core, "rb").read() == before


def test_set_item_14_refuses_non_string(tmp_path):
    repo, store = _setup_repo(tmp_path)
    assert PC.set_item(repo, "whoItsFor", ["a"], root=store)["reason"] == "malformed-value"


@pytest.mark.parametrize("value", ["", "   "], ids=["empty", "spaces"])
def test_item_14_empty_stored_value_reads_malformed(tmp_path, value):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config_item(repo, "whoItsFor", value, root=store)
    got = PC.get_item(repo, "whoItsFor", root=store)
    assert got["malformed"] is True
    assert got["source"] == "unset"


def test_item_13_marker_reads_as_canon_pointer(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config_item(repo, "materialConsequenceLine", dict(_MARKER), root=store)
    got = PC.get_item(repo, "materialConsequenceLine", root=store)
    assert got["source"] == "canon-pointer"
    assert got["raw"] == _MARKER
    assert got["effective"] == "the project's Canon standing rulings"
    assert got["malformed"] is False


# axis: only the exact two-key marker is an adopted item 13 — wo_a_1618_marker-shape
@pytest.mark.parametrize("bad", [
    {"canon": "standing-rulings"},
    {"canon": "other", "migratedOn": "2026-10-05"},
    {"canon": "standing-rulings", "migratedOn": "not-a-date"},
    {"canon": "standing-rulings", "migratedOn": "2026-10-05", "extra": 1},
    {"anything": "else"},
    ["standing-rulings"],
    7,
    True,
], ids=["missing-date", "wrong-canon", "bad-date", "extra-key", "other-dict", "list", "int", "bool"])
def test_item_13_non_marker_non_string_is_malformed(tmp_path, bad):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config_item(repo, "materialConsequenceLine", bad, root=store)
    got = PC.get_item(repo, "materialConsequenceLine", root=store)
    assert got["source"] == "unset"
    assert got["malformed"] is True
    assert PC.is_material_line_marker(bad) is False


def test_is_material_line_marker_accepts_the_marker():
    assert PC.is_material_line_marker(dict(_MARKER)) is True
    assert PC.MATERIAL_LINE_MARKER_CANON == "standing-rulings"


# axis: an adopted item 13 refuses a set and writes nothing — wo_a_1618_adopted-set-refusal
def test_set_item_13_on_adopted_project_refused_and_writes_nothing(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config_item(repo, "materialConsequenceLine", dict(_MARKER), root=store)
    core = CM.core_path(repo, store)
    before = open(core, "rb").read()
    got = PC.set_item(repo, "materialConsequenceLine", "a new example", root=store)
    assert got == {
        "action": "refused",
        "reason": "material-line-in-canon",
        "detail": (
            "Item 13 now points to the project's Canon standing rulings and holds no value of "
            "its own. Record a new example in Canon as a standing ruling, by Canon's write "
            "procedure."
        ),
    }
    assert open(core, "rb").read() == before


def test_set_item_13_dict_on_adopted_project_refused_before_validation(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config_item(repo, "materialConsequenceLine", dict(_MARKER), root=store)
    got = PC.set_item(repo, "materialConsequenceLine", dict(_MARKER), root=store)
    assert got["reason"] == "material-line-in-canon"


def test_set_item_13_dict_on_non_adopted_project_is_malformed(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = PC.set_item(repo, "materialConsequenceLine", dict(_MARKER), root=store)
    assert got == {"action": "refused", "reason": "malformed-value"}


def test_set_item_13_on_non_adopted_project_written_as_today(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = PC.set_item(repo, "materialConsequenceLine", "plugin default, plus mine", root=store)
    assert got["action"] == "written"
    stored = PC.get_item(repo, "materialConsequenceLine", root=store)
    assert stored["source"] == "stamped"
    assert stored["raw"] == "plugin default, plus mine"
    again = PC.set_item(repo, "materialConsequenceLine", "a second wording", root=store)
    assert again["action"] == "written"
