"""Tests for pilot_policy.py — policy resolution, material guard, and reach exercise."""
import json
import os
import shutil
import stat
import tempfile

import pytest

import pilot_policy as pp


def _sample_policy(**overrides):
    doc = {
        "schemaVersion": 1,
        "declaration": "example-project-pilot-policy",
        "protectedTargets": ["https://app.example.com:443", "example_prod"],
        "datastore": {
            "expectedIdentity": "example_dev",
            "connectionDetail": "postgres://localhost:5432/example_dev",
            "observer": {
                "command": ["/opt/pilot/db-identity"],
                "connectionEnvVar": "PILOT_DB_URL",
            },
        },
        "slots": {
            "slot-a": {
                "origin": "http://127.0.0.1:5173",
                "permittedRedirects": ["http://127.0.0.1:5173"],
                "expectedIdentities": {"owner": "pilot-owner@example.test"},
                "mintableAccounts": ["pilot-owner"],
            }
        },
    }
    doc.update(overrides)
    return doc


def _write_policy(policy_root, declaration, doc, *, mode=0o600):
    path = os.path.join(policy_root, declaration + ".json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle)
    os.chmod(path, mode)
    return path


# --- declaration grammar (fail closed before filesystem) ----------------------

@pytest.mark.parametrize(
    "declaration",
    [
        "../../etc/passwd",
        "a/b",
        ".",
        "..",
        "/etc/passwd",
    ],
)
def test_resolve_policy_document_refuses_invalid_declaration(private_tmp, declaration):
    policy_root = os.path.join(private_tmp, "policy-root")
    os.makedirs(policy_root)
    reach_root = os.path.join(private_tmp, "reach")
    os.makedirs(reach_root)
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(
            policy_root,
            declaration,
            reach_roots=[reach_root],
        )
    assert exc.value.reason == pp.REFUSAL_DECLARATION_INVALID


# --- policy root vs reach roots -----------------------------------------------

def test_resolve_policy_document_refuses_policy_root_inside_reach(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    policy_root = os.path.join(reach_root, "policy")
    os.makedirs(policy_root)
    declaration = "example-project-pilot-policy"
    _write_policy(policy_root, declaration, _sample_policy())
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(
            policy_root,
            declaration,
            reach_roots=[reach_root],
        )
    assert exc.value.reason == pp.REFUSAL_POLICY_ROOT_IN_REACH


def test_resolve_policy_document_refuses_reach_inside_policy_root(private_tmp):
    policy_root = os.path.join(private_tmp, "policy")
    reach_root = os.path.join(policy_root, "worktree")
    os.makedirs(reach_root)
    declaration = "example-project-pilot-policy"
    _write_policy(policy_root, declaration, _sample_policy())
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(
            policy_root,
            declaration,
            reach_roots=[reach_root],
        )
    assert exc.value.reason == pp.REFUSAL_POLICY_ROOT_IN_REACH


def test_resolve_policy_document_refuses_symlinked_policy_root_into_reach(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    real_policy_root = os.path.join(reach_root, "hidden-policy")
    os.makedirs(real_policy_root)
    link_policy_root = os.path.join(private_tmp, "policy-link")
    os.symlink(real_policy_root, link_policy_root)
    declaration = "example-project-pilot-policy"
    _write_policy(real_policy_root, declaration, _sample_policy())
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(
            link_policy_root,
            declaration,
            reach_roots=[reach_root],
        )
    assert exc.value.reason == pp.REFUSAL_POLICY_ROOT_IN_REACH


def test_paths_do_not_false_positive_on_string_prefix(private_tmp):
    parent = os.path.join(private_tmp, "prefix-edge")
    policy_root = os.path.join(parent, "bc")
    reach_root = os.path.join(parent, "b")
    os.makedirs(policy_root)
    os.makedirs(reach_root)
    declaration = "example-project-pilot-policy"
    _write_policy(policy_root, declaration, _sample_policy())
    doc = pp.resolve_policy_document(
        policy_root,
        declaration,
        reach_roots=[reach_root],
    )
    assert doc["declaration"] == declaration


# --- document path symlink checks ---------------------------------------------

def test_resolve_policy_document_refuses_symlinked_document(private_tmp):
    policy_root = os.path.join(private_tmp, "policy")
    os.makedirs(policy_root)
    declaration = "example-project-pilot-policy"
    target = os.path.join(policy_root, "target.json")
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(_sample_policy(), handle)
    os.chmod(target, 0o600)
    link_path = os.path.join(policy_root, declaration + ".json")
    os.symlink(target, link_path)
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(
            policy_root,
            declaration,
            reach_roots=[os.path.join(private_tmp, "reach")],
        )
    assert exc.value.reason == pp.REFUSAL_DOCUMENT_SYMLINK


def test_resolve_policy_document_refuses_symlinked_ancestor(private_tmp):
    policy_root = os.path.join(private_tmp, "policy")
    real_dir = os.path.join(private_tmp, "real-dir")
    os.makedirs(real_dir)
    linked = os.path.join(policy_root, "linked")
    os.makedirs(policy_root)
    os.symlink(real_dir, linked)
    declaration = "example-project-pilot-policy"
    _write_policy(real_dir, declaration, _sample_policy())
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(
            linked,
            declaration,
            reach_roots=[os.path.join(private_tmp, "reach")],
        )
    assert exc.value.reason == pp.REFUSAL_DOCUMENT_SYMLINK


# --- document permissions -----------------------------------------------------

def test_resolve_policy_document_refuses_group_writable_document(private_tmp):
    policy_root = os.path.join(private_tmp, "policy")
    os.makedirs(policy_root)
    declaration = "example-project-pilot-policy"
    _write_policy(policy_root, declaration, _sample_policy(), mode=0o662)
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(
            policy_root,
            declaration,
            reach_roots=[os.path.join(private_tmp, "reach")],
        )
    assert exc.value.reason == pp.REFUSAL_DOCUMENT_MODE_INSECURE


def test_resolve_policy_document_refuses_world_writable_document(private_tmp):
    policy_root = os.path.join(private_tmp, "policy")
    os.makedirs(policy_root)
    declaration = "example-project-pilot-policy"
    _write_policy(policy_root, declaration, _sample_policy(), mode=0o606)
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(
            policy_root,
            declaration,
            reach_roots=[os.path.join(private_tmp, "reach")],
        )
    assert exc.value.reason == pp.REFUSAL_DOCUMENT_MODE_INSECURE


# --- validate_policy schemaVersion --------------------------------------------

def test_validate_policy_refuses_schema_version_true():
    doc = _sample_policy(schemaVersion=True)
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.validate_policy(doc)
    assert exc.value.reason == pp.REFUSAL_SCHEMA_VERSION_UNSUPPORTED


# --- happy path ---------------------------------------------------------------

def test_resolve_policy_document_happy_path(private_tmp):
    policy_root = os.path.join(private_tmp, "policy")
    os.makedirs(policy_root)
    declaration = "example-project-pilot-policy"
    expected = _sample_policy()
    _write_policy(policy_root, declaration, expected, mode=0o600)
    reach_root = os.path.join(private_tmp, "reach")
    os.makedirs(reach_root)
    doc = pp.resolve_policy_document(
        policy_root,
        declaration,
        reach_roots=[reach_root],
    )
    assert doc == expected
    material = pp.policy_material(doc)
    assert material == {
        "expected-identity": ["pilot-owner@example.test"],
        "mintable-account": ["pilot-owner"],
        "connection-detail": [
            "example_dev",
            "postgres://localhost:5432/example_dev",
        ],
    }


# --- assert_results_only ------------------------------------------------------

def test_assert_results_only_refuses_nested_material():
    secret = "pilot-owner@example.test"
    material = {"expected-identity": [secret], "mintable-account": [], "connection-detail": []}
    result = {"layers": [[{"nested": {"identity": secret}}]]}
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.assert_results_only(result, material)
    assert exc.value.reason == pp.REFUSAL_MATERIAL_IN_RESULT
    assert exc.value.detail == "expected-identity"
    assert secret not in str(exc.value)


def test_assert_results_only_refuses_non_mapping_material():
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.assert_results_only({"ok": True}, ["not", "a", "mapping"])
    assert exc.value.reason == pp.REFUSAL_MATERIAL_INVALID


def test_assert_results_only_refuses_empty_indexed_material():
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.assert_results_only(
            {"ok": True},
            {"expected-identity": [], "mintable-account": [], "connection-detail": []},
        )
    assert exc.value.reason == pp.REFUSAL_MATERIAL_INVALID


def test_assert_results_only_passes_clean_result():
    material = {
        "expected-identity": ["pilot-owner@example.test"],
        "mintable-account": [],
        "connection-detail": ["postgres://localhost:5432/example_dev"],
    }
    result = {"ok": True, "checks": [{"check": "target-binding", "result": "pass"}]}
    pp.assert_results_only(result, material)


@pytest.mark.parametrize(
    "secret",
    [
        'postgres://u:p"w@host/db',
        "postgres://u:p\\w@host/db",
    ],
)
def test_assert_results_only_refuses_json_escapable_material_in_nested_result(secret):
    material = {"expected-identity": [], "mintable-account": [], "connection-detail": [secret]}
    result = {"layers": [[{"nested": {"note": secret}}]]}
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.assert_results_only(result, material)
    assert exc.value.reason == pp.REFUSAL_MATERIAL_IN_RESULT
    assert exc.value.detail == "connection-detail"
    assert secret not in str(exc.value)


# --- G2 empty reach_roots -----------------------------------------------------

def test_resolve_policy_document_refuses_empty_reach_roots(private_tmp):
    policy_root = os.path.join(private_tmp, "policy")
    os.makedirs(policy_root)
    declaration = "example-project-pilot-policy"
    _write_policy(policy_root, declaration, _sample_policy())
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(policy_root, declaration, reach_roots=[])
    assert exc.value.reason == pp.REFUSAL_REACH_ROOT_INVALID


def test_resolve_policy_document_refuses_policy_root_in_reach_control(private_tmp):
    policy_root = os.path.join(private_tmp, "policy")
    os.makedirs(policy_root)
    declaration = "example-project-pilot-policy"
    _write_policy(policy_root, declaration, _sample_policy())
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(
            policy_root,
            declaration,
            reach_roots=[policy_root],
        )
    assert exc.value.reason == pp.REFUSAL_POLICY_ROOT_IN_REACH


# --- T4 validate_policy structural refusals -----------------------------------

def _policy_missing_key(key):
    doc = _sample_policy()
    del doc[key]
    return doc


def _policy_with_extra_key():
    doc = _sample_policy()
    doc["extra"] = True
    return doc


@pytest.mark.parametrize(
    "doc_factory",
    [
        lambda: _policy_missing_key("declaration"),
        _policy_with_extra_key,
        lambda: {**_sample_policy(), "datastore": "not-a-dict"},
        lambda: {
            **_sample_policy(),
            "slots": {
                "slot-a": {
                    "origin": "http://127.0.0.1:5173",
                    "permittedRedirects": [],
                    "expectedIdentities": {},
                }
            },
        },
        lambda: {**_sample_policy(), "protectedTargets": []},
        lambda: {**_sample_policy(), "protectedTargets": [123]},
    ],
)
def test_validate_policy_refuses_structural_violations(doc_factory):
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.validate_policy(doc_factory())
    assert exc.value.reason == pp.REFUSAL_DOCUMENT_INVALID


def test_resolve_policy_document_refuses_declaration_mismatch(private_tmp):
    policy_root = os.path.join(private_tmp, "policy")
    os.makedirs(policy_root)
    declaration = "example-project-pilot-policy"
    doc = _sample_policy(declaration="other-name")
    _write_policy(policy_root, declaration, doc)
    reach_root = os.path.join(private_tmp, "reach")
    os.makedirs(reach_root)
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(
            policy_root,
            declaration,
            reach_roots=[reach_root],
        )
    assert exc.value.reason == pp.REFUSAL_DOCUMENT_INVALID


def test_resolve_policy_document_refuses_invalid_document_shape(private_tmp):
    policy_root = os.path.join(private_tmp, "policy")
    os.makedirs(policy_root)
    declaration = "example-project-pilot-policy"
    doc = _sample_policy()
    doc["extra"] = True
    _write_policy(policy_root, declaration, doc)
    reach_root = os.path.join(private_tmp, "reach")
    os.makedirs(reach_root)
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.resolve_policy_document(
            policy_root,
            declaration,
            reach_roots=[reach_root],
        )
    assert exc.value.reason == pp.REFUSAL_DOCUMENT_INVALID


# --- exercise_no_policy_material_in_reach -------------------------------------

def test_exercise_refuses_missing_reach_root(private_tmp):
    missing = os.path.join(private_tmp, "missing-reach")
    material = {"expected-identity": ["x"], "mintable-account": [], "connection-detail": []}
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.exercise_no_policy_material_in_reach([missing], material)
    assert exc.value.reason == pp.REFUSAL_REACH_ROOT_INVALID


def test_exercise_refuses_reach_root_that_is_a_file(private_tmp):
    reach_file = os.path.join(private_tmp, "reach-file")
    with open(reach_file, "w", encoding="utf-8") as handle:
        handle.write("not a directory")
    material = {"expected-identity": ["x"], "mintable-account": [], "connection-detail": []}
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.exercise_no_policy_material_in_reach([reach_file], material)
    assert exc.value.reason == pp.REFUSAL_REACH_ROOT_INVALID


def test_exercise_fails_vacuous_on_empty_tree(private_tmp):
    reach_root = os.path.join(private_tmp, "empty-reach")
    os.makedirs(reach_root)
    material = {"expected-identity": ["x"], "mintable-account": [], "connection-detail": []}
    receipt = pp.exercise_no_policy_material_in_reach([reach_root], material)
    assert receipt["result"] == "fail"
    assert receipt["reason"] == pp.REFUSAL_EXERCISE_VACUOUS


def test_exercise_refuses_empty_material(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    os.makedirs(reach_root)
    with open(os.path.join(reach_root, "file.txt"), "w", encoding="utf-8") as handle:
        handle.write("content")
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.exercise_no_policy_material_in_reach(
            [reach_root],
            {"expected-identity": [], "mintable-account": [], "connection-detail": []},
        )
    assert exc.value.reason == pp.REFUSAL_EXERCISE_VACUOUS


def test_exercise_refuses_vacuous_material_with_empty_string_needle(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    os.makedirs(reach_root)
    with open(os.path.join(reach_root, "file.txt"), "w", encoding="utf-8") as handle:
        handle.write("harmless")
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.exercise_no_policy_material_in_reach(
            [reach_root],
            {
                "expected-identity": [""],
                "mintable-account": [],
                "connection-detail": [],
            },
        )
    assert exc.value.reason == pp.REFUSAL_EXERCISE_VACUOUS


@pytest.mark.skipif(os.getuid() == 0, reason="unreadable-directory test cannot bite as root")
def test_exercise_fails_on_unreadable_subdirectory(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    locked_dir = os.path.join(reach_root, "locked")
    os.makedirs(reach_root)
    os.makedirs(locked_dir)
    with open(os.path.join(reach_root, "readable.txt"), "w", encoding="utf-8") as handle:
        handle.write("harmless")
    with open(os.path.join(locked_dir, "secret.txt"), "w", encoding="utf-8") as handle:
        handle.write("PILOT-SECRET-IDENTITY")
    os.chmod(locked_dir, 0o000)
    try:
        material = {
            "expected-identity": ["PILOT-SECRET-IDENTITY"],
            "mintable-account": [],
            "connection-detail": [],
        }
        receipt = pp.exercise_no_policy_material_in_reach([reach_root], material)
        assert receipt["result"] == "fail"
        assert receipt["reason"] == pp.REFUSAL_EXERCISE_UNREADABLE
    finally:
        os.chmod(locked_dir, 0o700)


@pytest.mark.skipif(os.getuid() == 0, reason="unreadable-file test cannot bite as root")
def test_exercise_fails_on_unreadable_file(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    os.makedirs(reach_root)
    unreadable = os.path.join(reach_root, "secret.bin")
    with open(unreadable, "wb") as handle:
        handle.write(b"payload")
    os.chmod(unreadable, 0o000)
    try:
        material = {"expected-identity": ["needle"], "mintable-account": [], "connection-detail": []}
        receipt = pp.exercise_no_policy_material_in_reach([reach_root], material)
        assert receipt["result"] == "fail"
        assert receipt["reason"] == pp.REFUSAL_EXERCISE_UNREADABLE
    finally:
        os.chmod(unreadable, 0o600)


@pytest.mark.parametrize(
    "material_class,value",
    [
        ("expected-identity", "pilot-owner@example.test"),
        ("mintable-account", "pilot-owner"),
        ("connection-detail", "postgres://localhost:5432/example_dev"),
    ],
)
def test_exercise_fails_per_material_class(private_tmp, material_class, value):
    reach_root = os.path.join(private_tmp, "reach")
    os.makedirs(reach_root)
    planted = os.path.join(reach_root, "planted.txt")
    with open(planted, "w", encoding="utf-8") as handle:
        handle.write("prefix %s suffix" % value)
    material = {
        "expected-identity": [],
        "mintable-account": [],
        "connection-detail": [],
    }
    material[material_class] = [value]
    receipt = pp.exercise_no_policy_material_in_reach([reach_root], material)
    assert receipt["result"] == "fail"
    assert receipt["reason"] == pp.REASON_EXERCISE_MATERIAL_FOUND
    assert receipt["findings"] == [{"path": planted, "materialClass": material_class}]
    serialized = json.dumps(receipt)
    assert value not in serialized


def test_exercise_passes_with_clean_files(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    os.makedirs(reach_root)
    for name in ("a.txt", "b.txt"):
        with open(os.path.join(reach_root, name), "w", encoding="utf-8") as handle:
            handle.write("clean content for %s" % name)
    material = {
        "expected-identity": ["needle-not-present"],
        "mintable-account": ["also-absent"],
        "connection-detail": ["missing-too"],
    }
    receipt = pp.exercise_no_policy_material_in_reach([reach_root], material)
    assert receipt["result"] == "pass"
    assert receipt["reason"] is None
    assert receipt["scannedFiles"] > 0
    assert receipt["findings"] == []
    assert receipt["symlinksSkipped"] == 0
    assert len(receipt["coverageLimits"]) == 1


def test_exercise_does_not_follow_symlinks(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    outside = os.path.join(private_tmp, "outside")
    os.makedirs(reach_root)
    os.makedirs(outside)
    secret = "hidden-connection-detail"
    outside_file = os.path.join(outside, "secret.txt")
    with open(outside_file, "w", encoding="utf-8") as handle:
        handle.write(secret)
    os.symlink(outside_file, os.path.join(reach_root, "link.txt"))
    with open(os.path.join(reach_root, "visible.txt"), "w", encoding="utf-8") as handle:
        handle.write("visible only")
    material = {
        "expected-identity": [],
        "mintable-account": [],
        "connection-detail": [secret],
    }
    receipt = pp.exercise_no_policy_material_in_reach([reach_root], material)
    assert receipt["result"] == "pass"
    assert receipt["scannedFiles"] == 1
    assert receipt["symlinksSkipped"] == 1
    assert len(receipt["coverageLimits"]) == 2
    assert "symbolic link" in receipt["coverageLimits"][1].lower()


def test_exercise_finds_needle_split_across_chunk_boundary(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    os.makedirs(reach_root)
    needle = b"PILOT-CHUNK-BOUNDARY-NEEDLE"
    half = len(needle) // 2
    filler = b"f" * (pp._EXERCISE_CHUNK_SIZE - half)
    content = filler + needle
    planted = os.path.join(reach_root, "chunked.bin")
    with open(planted, "wb") as handle:
        handle.write(content)
    material = {
        "expected-identity": [needle.decode("utf-8")],
        "mintable-account": [],
        "connection-detail": [],
    }
    receipt = pp.exercise_no_policy_material_in_reach([reach_root], material)
    assert receipt["result"] == "fail"
    assert receipt["reason"] == pp.REASON_EXERCISE_MATERIAL_FOUND
    assert receipt["findings"] == [{"path": planted, "materialClass": "expected-identity"}]


def test_paths_filesystem_root_ancestor():
    assert pp._is_same_or_ancestor("/", "/private/tmp/example") is True


def test_exercise_symlink_free_reach_has_zero_skipped(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    os.makedirs(reach_root)
    with open(os.path.join(reach_root, "clean.txt"), "w", encoding="utf-8") as handle:
        handle.write("no symlinks here")
    material = {
        "expected-identity": ["absent"],
        "mintable-account": [],
        "connection-detail": [],
    }
    receipt = pp.exercise_no_policy_material_in_reach([reach_root], material)
    assert receipt["symlinksSkipped"] == 0
    assert len(receipt["coverageLimits"]) == 1
