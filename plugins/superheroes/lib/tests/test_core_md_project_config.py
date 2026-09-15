# plugins/superheroes/lib/tests/test_core_md_project_config.py
"""Conformance: projectConfiguration, declaredDependencies, threat model, guardian cadence writers."""
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


CM = _load("core_md")
GS = _load("guardian_sweep")

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

_THREAT_BODY = "multi-tenant with shared auth"
_PROJECT_CFG = {"lint": {"enabled": True}}
_DECLARED_DEPS = {"eslint": "^9.0.0"}
_CADENCE = {"minMerges": 5, "minDays": 7}
_GUARDIAN_BLOCK = {
    "thresholds": {"complexity": 42},
    "coverage": ["src/"],
    "vitals": False,
    "verifyBudgetSeconds": 120,
    "reportCard": {"enabled": True},
    "cadence": {"minMerges": 10, "minDays": 14},
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


def _write_guardian_layer(repo, store, config_block=None):
    layer = CM.layer_path(repo, "guardian", store)
    os.makedirs(os.path.dirname(layer), exist_ok=True)
    body = "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
    if config_block is not None:
        body += "```json guardian-config\n%s\n```\n" % json.dumps(config_block, indent=2)
    open(layer, "w").write(body)
    return layer


def _parsed_snapshot(repo, store):
    path = CM.core_path(repo, store)
    return CM.parse_core(open(path, encoding="utf-8").read())


def _other_fields_unchanged(before, after, owned_field):
    for key in before:
        if key == owned_field:
            continue
        assert before[key] == after[key], "field %s changed" % key


def test_parse_absent_project_configuration_reads_empty_dict():
    text = CM.render_core(dict(_CORE_FACTS), "confirmed", "2026-06-26", "2026-06-26")
    got = CM.parse_core(text)
    assert got["projectConfiguration"] == {}
    assert got["declaredDependencies"] == {}


def test_parse_non_object_project_configuration_reads_empty_dict():
    block = {
        "schemaVersion": CM.SCHEMA_VERSION,
        "verifyCommand": "npm test",
        "stackTags": [],
        "projectConfiguration": "bad",
        "declaredDependencies": [],
    }
    text = CM.render_core(
        dict(_CORE_FACTS, projectConfiguration="bad", declaredDependencies=[]),
        "confirmed", "2026-06-26", "2026-06-26")
    text = text.replace(
        json.dumps({
            "schemaVersion": CM.SCHEMA_VERSION,
            "verifyCommand": "npm test",
            "stackTags": ["node"],
            "enginePreferences": {},
        }, indent=2),
        json.dumps(block, indent=2),
    )
    got = CM.parse_core(text)
    assert got["projectConfiguration"] == {}
    assert got["declaredDependencies"] == {}


def test_render_omits_empty_project_configuration_keys():
    text = CM.render_core(dict(_CORE_FACTS), "confirmed", "2026-06-26", "2026-06-26")
    block = json.loads(CM._JSON_BLOCK.search(text).group(1))
    assert CM.PROJECT_CONFIGURATION_KEY not in block
    assert CM.DECLARED_DEPENDENCIES_KEY not in block


def test_read_v2_profile_upgrades_in_memory(tmp_path):
    repo, store = _setup_repo(tmp_path, schema=2)
    before = open(CM.core_path(repo, store)).read()
    got = CM.read(repo, root=store)
    assert got["schemaVersion"] == CM.SCHEMA_VERSION
    assert got["behind"] is False
    assert got["projectConfiguration"] == {}
    assert open(CM.core_path(repo, store)).read() == before


def test_read_v4_profile_behind(tmp_path):
    repo, store = _setup_repo(tmp_path, schema=4)
    got = CM.read(repo, root=store)
    assert got["behind"] is True


@pytest.mark.parametrize("writer_name", [
    "write_project_config",
    "write_declared_dependencies",
    "write_threat_model",
    "write_guardian_cadence",
])
def test_behind_schema_refuses_all_writers(tmp_path, writer_name):
    repo, store = _setup_repo(tmp_path, schema=CM.SCHEMA_VERSION + 1)
    _write_guardian_layer(repo, store, _GUARDIAN_BLOCK)
    writer = getattr(CM, writer_name)
    if writer_name == "write_threat_model":
        res = writer(repo, _THREAT_BODY, root=store)
    elif writer_name == "write_guardian_cadence":
        res = writer(repo, _CADENCE, root=store)
    else:
        res = writer(repo, {"k": "v"}, root=store)
    assert res["action"] == "behind"


def test_write_project_config_written_and_roundtrip(tmp_path):
    repo, store = _setup_repo(tmp_path)
    before = _parsed_snapshot(repo, store)
    res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
    assert res["action"] == "written"
    after = _parsed_snapshot(repo, store)
    assert after["projectConfiguration"] == _PROJECT_CFG
    _other_fields_unchanged(before, after, "projectConfiguration")


def test_write_declared_dependencies_written_and_roundtrip(tmp_path):
    repo, store = _setup_repo(tmp_path)
    before = _parsed_snapshot(repo, store)
    res = CM.write_declared_dependencies(repo, _DECLARED_DEPS, root=store)
    assert res["action"] == "written"
    after = _parsed_snapshot(repo, store)
    assert after["declaredDependencies"] == _DECLARED_DEPS
    _other_fields_unchanged(before, after, "declaredDependencies")


def test_write_threat_model_written_and_roundtrip(tmp_path):
    repo, store = _setup_repo(tmp_path)
    before = _parsed_snapshot(repo, store)
    res = CM.write_threat_model(repo, _THREAT_BODY, root=store)
    assert res["action"] == "written"
    after = _parsed_snapshot(repo, store)
    assert after["threatModel"] == _THREAT_BODY
    _other_fields_unchanged(before, after, "threatModel")


def test_write_guardian_cadence_preserves_siblings(tmp_path):
    repo, store = _setup_repo(tmp_path)
    layer = _write_guardian_layer(repo, store, dict(_GUARDIAN_BLOCK))
    before = json.loads(GS._CONFIG_BLOCK.search(open(layer).read()).group(1))
    res = CM.write_guardian_cadence(repo, _CADENCE, root=store)
    assert res["action"] == "written"
    after = json.loads(GS._CONFIG_BLOCK.search(open(layer).read()).group(1))
    assert after["cadence"] == _CADENCE
    for key in ("thresholds", "coverage", "vitals", "verifyBudgetSeconds", "reportCard"):
        assert after[key] == before[key]


def test_write_project_config_noop_when_unchanged(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config(repo, _PROJECT_CFG, root=store)
    res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
    assert res["action"] == "noop"


def test_write_declared_dependencies_noop_when_unchanged(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_declared_dependencies(repo, _DECLARED_DEPS, root=store)
    res = CM.write_declared_dependencies(repo, _DECLARED_DEPS, root=store)
    assert res["action"] == "noop"


def test_write_threat_model_noop_when_unchanged(tmp_path):
    repo, store = _setup_repo(tmp_path)
    res = CM.write_threat_model(repo, "single-user", root=store)
    assert res["action"] == "noop"


def test_write_guardian_cadence_noop_when_unchanged(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _write_guardian_layer(repo, store, dict(_GUARDIAN_BLOCK))
    res = CM.write_guardian_cadence(
        repo, _GUARDIAN_BLOCK["cadence"], root=store)
    assert res["action"] == "noop"


def test_write_project_config_refused_absent_core(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.BUILDER_DISPATCH_REASON_ABSENT


def test_write_project_config_refused_unparseable_core(tmp_path):
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    open(path, "w").write("not core\n")
    res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.BUILDER_DISPATCH_REASON_UNPARSEABLE


def test_write_project_config_refused_not_a_mapping():
    res = CM.write_project_config(".", "bad", root=None)
    assert res["action"] == "refused"
    assert res["reason"] == CM.PROJECT_CONFIG_REASON_NOT_A_MAPPING


def test_write_declared_dependencies_refused_not_a_mapping():
    res = CM.write_declared_dependencies(".", [], root=None)
    assert res["action"] == "refused"
    assert res["reason"] == CM.DECLARED_DEPS_REASON_NOT_A_MAPPING


def test_write_project_config_deferred_lock_contended(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)

    @contextlib.contextmanager
    def _contended(cwd, root=None):
        yield False

    monkeypatch.setattr(CM.mode_registry, "config_lock", _contended)
    res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
    assert res["action"] == "deferred"


def test_write_project_config_deferred_store_unwritable(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr(CM.mode_registry, "ensure_project_store", lambda *a, **k: None)
    res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
    assert res["action"] == "deferred"


def test_write_project_config_refused_round_trip(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr(
        CM, "_json_block_key_round_trip_ok", lambda *a, **k: True)
    res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
    assert res["action"] == "written"
    monkeypatch.setattr(
        CM, "_json_block_key_round_trip_ok",
        lambda orig, new, key: False)
    res = CM.write_project_config(repo, {"other": True}, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.PROJECT_CONFIG_REASON_ROUND_TRIP


def test_write_project_config_behind_refuses_without_neutralization(tmp_path):
    repo, store = _setup_repo(tmp_path, schema=CM.SCHEMA_VERSION + 1)
    res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
    assert res["action"] == "behind"


def test_cli_write_project_config_refused_invalid_json(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    rc = CM.main(["write-project-config", "--cwd", repo, "--root", store])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "refused"


def test_cli_write_project_config_refused_not_object(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO('"string"'))
    rc = CM.main(["write-project-config", "--cwd", repo, "--root", store])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "refused"
    assert out["reason"] == CM.PROJECT_CONFIG_REASON_NOT_A_MAPPING


def test_cli_write_project_config_from_stdin(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_PROJECT_CFG)))
    rc = CM.main(["write-project-config", "--cwd", repo, "--root", store])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "written"


def test_cli_write_declared_dependencies_from_stdin(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_DECLARED_DEPS)))
    rc = CM.main(["write-declared-dependencies", "--cwd", repo, "--root", store])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "written"


def test_cli_write_threat_model_from_stdin(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(_THREAT_BODY))
    rc = CM.main(["write-threat-model", "--cwd", repo, "--root", store])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "written"


def test_cli_write_guardian_cadence_from_stdin(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    _write_guardian_layer(repo, store, dict(_GUARDIAN_BLOCK))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_CADENCE)))
    rc = CM.main(["write-guardian-cadence", "--cwd", repo, "--root", store])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "written"


def test_write_guardian_cadence_refused_layer_absent(tmp_path):
    repo, store = _setup_repo(tmp_path)
    res = CM.write_guardian_cadence(repo, _CADENCE, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.GUARDIAN_CADENCE_REASON_LAYER_ABSENT


def test_write_guardian_cadence_refused_no_fence(tmp_path):
    repo, store = _setup_repo(tmp_path)
    layer = CM.layer_path(repo, "guardian", store)
    os.makedirs(os.path.dirname(layer), exist_ok=True)
    open(layer, "w").write("<!-- guardian: schemaVersion=1 status=confirmed -->\n\nbody\n")
    res = CM.write_guardian_cadence(repo, _CADENCE, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.GUARDIAN_CADENCE_REASON_NO_FENCE


def test_write_guardian_cadence_refused_malformed_fence(tmp_path):
    repo, store = _setup_repo(tmp_path)
    layer = _write_guardian_layer(repo, store, None)
    open(layer, "w").write(
        "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
        "```json guardian-config\n{ broken\n```\n")
    res = CM.write_guardian_cadence(repo, _CADENCE, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.GUARDIAN_CADENCE_REASON_UNPARSEABLE


def test_write_guardian_cadence_refused_non_object_fence(tmp_path):
    repo, store = _setup_repo(tmp_path)
    layer = _write_guardian_layer(repo, store, None)
    open(layer, "w").write(
        "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
        "```json guardian-config\n[]\n```\n")
    res = CM.write_guardian_cadence(repo, _CADENCE, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.GUARDIAN_CADENCE_REASON_UNPARSEABLE


def test_write_guardian_cadence_refused_invalid_cadence_not_object():
    res = CM.write_guardian_cadence(".", "bad", root=None)
    assert res["action"] == "refused"
    assert res["reason"] == CM.GUARDIAN_CADENCE_REASON_INVALID_CADENCE


def test_write_guardian_cadence_refused_invalid_min_merges(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _write_guardian_layer(repo, store, dict(_GUARDIAN_BLOCK))
    res = CM.write_guardian_cadence(repo, {"minMerges": 0, "minDays": 7}, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.GUARDIAN_CADENCE_REASON_INVALID_CADENCE


def test_write_guardian_cadence_refused_invalid_min_days(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _write_guardian_layer(repo, store, dict(_GUARDIAN_BLOCK))
    res = CM.write_guardian_cadence(
        repo, {"minMerges": 5, "minDays": -1}, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.GUARDIAN_CADENCE_REASON_INVALID_CADENCE


def test_write_guardian_cadence_refused_round_trip_sibling_loss(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    _write_guardian_layer(repo, store, dict(_GUARDIAN_BLOCK))

    def _broken(orig, new):
        return True

    monkeypatch.setattr(CM, "_guardian_config_round_trip_ok", _broken)
    res = CM.write_guardian_cadence(repo, _CADENCE, root=store)
    assert res["action"] == "written"
    monkeypatch.setattr(CM, "_guardian_config_round_trip_ok", lambda o, n: False)
    res = CM.write_guardian_cadence(repo, {"minMerges": 6, "minDays": 8}, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.GUARDIAN_CADENCE_REASON_ROUND_TRIP


def test_write_threat_model_refused_absent_core(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    res = CM.write_threat_model(repo, _THREAT_BODY, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.SHOW_IT_REASON_ABSENT


def test_write_threat_model_refused_unparseable_core(tmp_path):
    repo, store = _setup_repo(tmp_path)
    open(CM.core_path(repo, store), "w").write("broken\n")
    res = CM.write_threat_model(repo, _THREAT_BODY, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.SHOW_IT_REASON_UNPARSEABLE


def test_bite_write_project_config_round_trip_axis(tmp_path, monkeypatch):
    """axis: round-trip — refuse when re-parse would change verifyCommand."""
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    original_text = open(path).read()

    _original_splice = CM._splice_single_json_block

    def corrupting_splice(text, new_body):
        bad_body = json.loads(new_body)
        bad_body["verifyCommand"] = "CORRUPTED"
        return _original_splice(text, json.dumps(bad_body, indent=2))

    monkeypatch.setattr(CM, "_splice_single_json_block", corrupting_splice)
    res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.PROJECT_CONFIG_REASON_ROUND_TRIP
    assert open(path).read() == original_text


def test_bite_write_project_config_behind_schema_axis(tmp_path):
    """axis: behind-schema — refuse when core.md schema is newer than this build."""
    repo, store = _setup_repo(tmp_path, schema=CM.SCHEMA_VERSION + 1)
    res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
    assert res["action"] == "behind"


def test_bite_cli_write_project_config_payload_shape_axis(tmp_path, capsys, monkeypatch):
    """axis: payload-shape — CLI must refuse a JSON value that is not an object."""
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO('"string"'))
    rc = CM.main(["write-project-config", "--cwd", repo, "--root", store])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "refused"
    assert out["reason"] == CM.PROJECT_CONFIG_REASON_NOT_A_MAPPING


def test_bite_guardian_cadence_sibling_preservation_axis(tmp_path, monkeypatch):
    """axis: sibling preservation — refuse when cadence write drops guardian-config siblings."""
    repo, store = _setup_repo(tmp_path)
    layer = _write_guardian_layer(repo, store, dict(_GUARDIAN_BLOCK))
    before = open(layer).read()

    def wholesale_splice(text, new_body):
        return (
            "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
            "```json guardian-config\n"
            '{"cadence": {"minMerges": 5, "minDays": 7}}\n'
            "```\n"
        )

    monkeypatch.setattr(CM, "_splice_guardian_config_block", wholesale_splice)
    res = CM.write_guardian_cadence(repo, _CADENCE, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.GUARDIAN_CADENCE_REASON_ROUND_TRIP
    assert open(layer).read() == before


def test_bite_guardian_cadence_validation_axis(tmp_path):
    """axis: cadence validation — refuse non-positive minMerges."""
    repo, store = _setup_repo(tmp_path)
    _write_guardian_layer(repo, store, dict(_GUARDIAN_BLOCK))
    res = CM.write_guardian_cadence(repo, {"minMerges": 0, "minDays": 7}, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.GUARDIAN_CADENCE_REASON_INVALID_CADENCE
