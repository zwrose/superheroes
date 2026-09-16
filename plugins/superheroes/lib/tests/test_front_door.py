# plugins/superheroes/lib/tests/test_front_door.py
"""Conformance: front-door grading against the severity ladder and evidence bar."""
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


FD = _load("front_door")
PC = _load("project_config")
CM = _load("core_md")

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

_VALID_LADDER = [
    {
        "name": "Band 1",
        "examples": [{"text": "data loss", "citation": "runbook §2"}],
    },
    {
        "name": "Band 2",
        "examples": [{"text": "degraded UX", "citation": "runbook §3"}],
    },
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


def _setup_repo(tmp_path, schema=None, extra_block=None):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    if schema is None:
        CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    else:
        CM.mode_registry.ensure_project_store(repo, store)
        _write_core(repo, schema, extra_block=extra_block)
    return repo, store


def _stamp_ladder(repo, store, ladder=None):
    CM.write_project_config(
        repo,
        {"severityLadder": ladder if ladder is not None else _VALID_LADDER},
        root=store,
    )


def _claim(**kwargs):
    return dict(kwargs)


# --- C3 table and named cases ---


def test_no_ladder_refuses_p0_and_p1(tmp_path):
    repo, store = _setup_repo(tmp_path)
    for tier in ("P0", "P1"):
        got = FD.grade(
            repo,
            _claim(tier=tier, band="Band 1", evidence="field"),
            root=store,
        )
        assert got["outcome"] == "refused"
        assert got["reason"] == FD.REASON_LADDER_UNSTAMPED
        assert got["tier"] is None


def test_no_ladder_queues_instead_of_filing(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = FD.grade(
        repo,
        _claim(tier="P2", band="Band 2", evidence="lab"),
        root=store,
    )
    assert got["outcome"] == "queued"
    assert got["reason"] == FD.REASON_LADDER_UNSTAMPED
    assert got["tier"] is None
    assert got["record"]["tier"] == "P2"


def test_no_ladder_declined_grades(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = FD.grade(
        repo,
        _claim(tier="declined", band=None, evidence="field"),
        root=store,
    )
    assert got == {
        "outcome": "graded",
        "tier": "declined",
        "reason": None,
        "record": {"band": None, "tier": "declined", "evidence": "field"},
    }


def test_stamped_ladder_unknown_band_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    got = FD.grade(
        repo,
        _claim(tier="P1", band="Band 9", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_BAND_UNKNOWN


def test_argued_evidence_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    got = FD.grade(
        repo,
        _claim(tier="P1", band="Band 1", evidence="argued"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_EVIDENCE_ARGUED


def test_p0_unstamped_definition_refuses_top_band_field(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    got = FD.grade(
        repo,
        _claim(tier="P0", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_P0_DEFINITION_UNSTAMPED
    assert got["tier"] is None


def test_p0_unstamped_definition_refuses_top_band_lab(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    got = FD.grade(
        repo,
        _claim(tier="P0", band="Band 1", evidence="lab"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_P0_DEFINITION_UNSTAMPED
    assert got["tier"] is None


def test_p0_unstamped_definition_refuses_non_top_band(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    got = FD.grade(
        repo,
        _claim(tier="P0", band="Band 2", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_P0_DEFINITION_UNSTAMPED
    assert got["tier"] is None


def test_p0_stamped_definition_still_grades_conforming_claim(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    PC.set_item(
        repo,
        "p0Definition",
        "Band 1 by citation plus field evidence",
        root=store,
    )
    got = FD.grade(
        repo,
        _claim(tier="P0", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "graded"
    assert got["tier"] == "P0"
    assert got["reason"] is None


def test_p1_and_p2_unaffected_by_unstamped_p0_definition(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    p1 = FD.grade(
        repo,
        _claim(tier="P1", band="Band 2", evidence="lab"),
        root=store,
    )
    assert p1["outcome"] == "graded"
    assert p1["tier"] == "P1"
    p2 = FD.grade(
        repo,
        _claim(tier="P2", band="Band 2", evidence="field"),
        root=store,
    )
    assert p2["outcome"] == "graded"
    assert p2["tier"] == "P2"


def test_p0_stamped_definition_excludes_band(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    PC.set_item(
        repo,
        "p0Definition",
        "Band 1 by citation plus field evidence",
        root=store,
    )
    got = FD.grade(
        repo,
        _claim(tier="P0", band="Band 2", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_P0_BAND_EXCLUDED


def test_p0_stamped_definition_requires_matching_evidence(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    PC.set_item(
        repo,
        "p0Definition",
        "Band 1 by citation plus field evidence",
        root=store,
    )
    got = FD.grade(
        repo,
        _claim(tier="P0", band="Band 1", evidence="lab"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_P0_EVIDENCE_EXCLUDED


def test_p0_stamped_definition_does_not_match_band_prefix_of_another(tmp_path):
    repo, store = _setup_repo(tmp_path)
    ladder = [
        {"name": "Band 1", "examples": [{"text": "minor", "citation": "runbook §1"}]},
        {"name": "Band 10", "examples": [{"text": "major", "citation": "runbook §10"}]},
    ]
    _stamp_ladder(repo, store, ladder=ladder)
    PC.set_item(
        repo,
        "p0Definition",
        "Band 10 by citation plus field evidence",
        root=store,
    )
    got = FD.grade(
        repo,
        _claim(tier="P0", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_P0_BAND_EXCLUDED


def test_p0_stamped_definition_long_band_name_prefix_match(tmp_path):
    repo, store = _setup_repo(tmp_path)
    ladder = [
        {
            "name": "Band 1, users harmed or misled",
            "examples": [{"text": "data loss", "citation": "runbook §2"}],
        },
    ]
    _stamp_ladder(repo, store, ladder=ladder)
    PC.set_item(
        repo,
        "p0Definition",
        "Band 1 by citation plus field evidence",
        root=store,
    )
    got = FD.grade(
        repo,
        _claim(tier="P0", band="Band 1, users harmed or misled", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "graded"
    assert got["tier"] == "P0"


def test_p1_and_p2_grade_with_stamped_ladder(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    p1 = FD.grade(
        repo,
        _claim(tier="P1", band="Band 2", evidence="lab"),
        root=store,
    )
    assert p1["outcome"] == "graded"
    assert p1["tier"] == "P1"
    p2 = FD.grade(
        repo,
        _claim(tier="P2", band="Band 2", evidence="field"),
        root=store,
    )
    assert p2["outcome"] == "graded"
    assert p2["tier"] == "P2"


# --- fail-closed edges ---


def test_edge_no_profile_at_all(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    got = FD.grade(
        repo,
        _claim(tier="P1", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == PC.REASON_PROFILE_ABSENT


def test_edge_corrupt_profile_json(tmp_path):
    repo, store = _setup_repo(tmp_path)
    open(CM.core_path(repo, store), "w").write("not core\n")
    got = FD.grade(
        repo,
        _claim(tier="P1", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == PC.REASON_PROFILE_UNPARSEABLE


def test_edge_structural_refusal_duplicate_core_blocks(tmp_path):
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    text = open(path, encoding="utf-8").read()
    open(path, "w", encoding="utf-8").write(text + "\n" + text)
    got = FD.grade(
        repo,
        _claim(tier="P1", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] is not None
    assert got["reason"].startswith("multiple-core-blocks:")


def test_edge_structural_refusal_duplicate_top_level_key(tmp_path):
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    text = open(path, encoding="utf-8").read()
    block = (
        '{\n  "schemaVersion": %d,\n  "verifyCommand": "npm test",\n'
        '  "stackTags": [],\n  "verifyCommand": "dup"\n}'
        % CM.SCHEMA_VERSION
    )
    open(path, "w", encoding="utf-8").write(
        text.split("```json superheroes-core")[0]
        + "```json superheroes-core\n"
        + block
        + "\n```\n"
    )
    got = FD.grade(
        repo,
        _claim(tier="P0", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == "duplicate-core-key:verifyCommand"


def test_edge_newer_schema_behind(tmp_path):
    repo, store = _setup_repo(tmp_path, schema=CM.SCHEMA_VERSION + 1)
    got = FD.grade(
        repo,
        _claim(tier="P2", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == CM.BUILDER_DISPATCH_DEFER_SCHEMA_BEHIND


def test_edge_claim_not_object():
    got = FD.grade(".", "not-a-mapping")
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_CLAIM_NOT_OBJECT


def test_edge_claim_missing_tier(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = FD.grade(repo, {"band": "Band 1", "evidence": "field"}, root=store)
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_CLAIM_MISSING_TIER


def test_edge_unknown_tier(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = FD.grade(
        repo,
        _claim(tier="P9", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_TIER_UNKNOWN


def test_edge_unknown_evidence(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = FD.grade(
        repo,
        _claim(tier="P1", band="Band 1", evidence="hearsay"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_EVIDENCE_UNKNOWN


def test_edge_band_present_ladder_unset(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = FD.grade(
        repo,
        _claim(tier="P1", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_LADDER_UNSTAMPED


def test_edge_band_absent_on_banded_tier(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    got = FD.grade(repo, _claim(tier="P1", evidence="field"), root=store)
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_BAND_REQUIRED


def test_edge_malformed_stamped_ladder(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config(repo, {"severityLadder": "not-a-ladder"}, root=store)
    got = FD.grade(
        repo,
        _claim(tier="P1", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == PC.REASON_MALFORMED_VALUE


def test_edge_malformed_stamped_p0_definition(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    CM.write_project_config(
        repo,
        {
            "severityLadder": _VALID_LADDER,
            "p0Definition": 42,
        },
        root=store,
    )
    got = FD.grade(
        repo,
        _claim(tier="P0", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == PC.REASON_MALFORMED_VALUE


def test_edge_malformed_ladder_no_band_names(tmp_path):
    repo, store = _setup_repo(tmp_path)
    bad = [{"examples": [{"text": "x", "citation": "y"}]}]
    CM.write_project_config(repo, {"severityLadder": bad}, root=store)
    got = FD.grade(
        repo,
        _claim(tier="P1", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == PC.REASON_MALFORMED_VALUE


# --- bite-proof axis lines ---


def test_bite_ladder_gate_unstamped_p0_axis(tmp_path):
    # axis: unstamped ladder refuses P0 and P1 — wo_c_1276_ladder-gate
    repo, store = _setup_repo(tmp_path)
    got = FD.grade(
        repo,
        _claim(tier="P0", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_LADDER_UNSTAMPED


def test_bite_carve_out_gate_p2_queues_without_ladder_axis(tmp_path):
    # axis: P2 queues instead of filing when the ladder is unstamped — wo_c_1276_carve-out-gate
    repo, store = _setup_repo(tmp_path)
    got = FD.grade(
        repo,
        _claim(tier="P2", band="Band 1", evidence="field"),
        root=store,
    )
    assert got["outcome"] == "queued"
    assert got["reason"] == FD.REASON_LADDER_UNSTAMPED


def test_bite_evidence_bar_argued_axis(tmp_path):
    # axis: argued evidence never grades — wo_c_1276_evidence-bar
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    got = FD.grade(
        repo,
        _claim(tier="P1", band="Band 1", evidence="argued"),
        root=store,
    )
    assert got["outcome"] == "refused"
    assert got["reason"] == FD.REASON_EVIDENCE_ARGUED


# --- CLI ---


def test_cli_grade(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    _stamp_ladder(repo, store)
    claim = json.dumps(_claim(tier="P1", band="Band 1", evidence="field"))
    monkeypatch.setattr("sys.stdin", io.StringIO(claim))
    rc = FD.main(["grade", "--cwd", repo, "--root", store])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "graded"
    assert out["tier"] == "P1"
