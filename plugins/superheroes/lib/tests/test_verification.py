import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.abspath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import circuit_breaker as CB  # noqa: E402
import verification as V  # noqa: E402


def _f(file, title, severity, **kw):
    base = {"file": file, "line": 1, "title": title, "severity": severity}
    base.update(kw)
    return base


def _stage(findings):
    return V.stage_ids(findings)


# --- apply_verdicts -----------------------------------------------------------

def test_refuted_with_reason_dropped_and_was_blocking_tagged():
    findings = _stage([_f("a.py", "bug", "Critical")])
    verdicts = [{"id": "v0", "verdict": "REFUTED", "reason": "not reproducible"}]
    out = V.apply_verdicts(findings, verdicts)
    assert out["findings"] == []
    assert len(out["drops"]) == 1
    assert out["drops"][0]["reason"] == "not reproducible"
    assert out["drops"][0]["was_blocking_tagged"] is True


def test_refuted_empty_or_missing_reason_not_dropped_fail_closed():
    for reason in ("", None, "   "):
        findings = _stage([_f("a.py", "bug", "Important")])
        verdicts = [{"id": "v0", "verdict": "REFUTED", "reason": reason}]
        out = V.apply_verdicts(findings, verdicts)
        assert len(out["findings"]) == 1
        assert out["findings"][0]["verdict"] == "PLAUSIBLE"
        assert out["drops"] == []


def test_confirmed_survives_with_evidence():
    findings = _stage([_f("a.py", "bug", "Minor", body="the issue")])
    verdicts = [{"id": "v0", "verdict": "CONFIRMED", "reason": "verified",
                 "evidence": "ran test and saw failure"}]
    out = V.apply_verdicts(findings, verdicts)
    assert len(out["findings"]) == 1
    assert out["findings"][0]["verdict"] == "CONFIRMED"
    assert out["findings"][0]["evidence"] == "ran test and saw failure"


def test_plausible_survives():
    findings = _stage([_f("a.py", "bug", "Important")])
    verdicts = [{"id": "v0", "verdict": "PLAUSIBLE", "reason": "could not fully verify"}]
    out = V.apply_verdicts(findings, verdicts)
    assert len(out["findings"]) == 1
    assert out["findings"][0]["verdict"] == "PLAUSIBLE"


def test_no_verdict_keeps_on_uncertain_as_plausible():
    findings = _stage([_f("a.py", "bug", "Important")])
    out = V.apply_verdicts(findings, [])
    assert len(out["findings"]) == 1
    assert out["findings"][0]["verdict"] == "PLAUSIBLE"
    assert out["findings"][0]["severity"] == "Important"


def test_unknown_malformed_verdict_keeps_on_uncertain():
    findings = _stage([_f("a.py", "bug", "Important")])
    for bad in ("MAYBE", 123, None):
        verdicts = [{"id": "v0", "verdict": bad, "reason": "hmm"}]
        out = V.apply_verdicts(findings, verdicts)
        assert len(out["findings"]) == 1
        assert out["findings"][0]["verdict"] == "PLAUSIBLE"


def test_severity_normalize_and_downgrade_recorded():
    findings = _stage([_f("a.py", "overstated", "Critical")])
    verdicts = [{"id": "v0", "verdict": "CONFIRMED", "reason": "real but minor",
                 "severity": "Minor"}]
    out = V.apply_verdicts(findings, verdicts)
    assert out["findings"][0]["severity"] == "Minor"
    assert len(out["downgrades"]) == 1
    assert out["downgrades"][0]["from"] == "Critical"
    assert out["downgrades"][0]["to"] == "Minor"


def test_was_blocking_tagged_for_critical_and_important_drops():
    for sev in ("Critical", "Important"):
        findings = _stage([_f("a.py", "bug", sev)])
        verdicts = [{"id": "v0", "verdict": "REFUTED", "reason": "false positive"}]
        out = V.apply_verdicts(findings, verdicts)
        assert out["drops"][0]["was_blocking_tagged"] is True


def test_unmatched_verdict_id_reported():
    findings = _stage([_f("a.py", "bug", "Important")])
    verdicts = [{"id": "v99", "verdict": "REFUTED", "reason": "wrong id"}]
    out = V.apply_verdicts(findings, verdicts)
    assert len(out["findings"]) == 1
    assert out["unmatched"] == ["v99"]


def test_empty_and_garbage_inputs_never_raise_or_drop():
    assert V.apply_verdicts([], []) == {
        "findings": [], "drops": [], "downgrades": [], "unmatched": [],
    }
    findings = _stage([_f("a.py", "bug", "Important")])
    out = V.apply_verdicts(findings, "not-a-list")
    assert len(out["findings"]) == 1 and out["drops"] == []
    out2 = V.apply_verdicts(findings, [None, 42, {"verdict": "REFUTED"}])
    assert len(out2["findings"]) == 1 and out2["drops"] == []


def test_confirmed_with_downgrade_survives_and_records_downgrade():
    findings = _stage([_f("a.py", "race", "Critical")])
    verdicts = [{"id": "v0", "verdict": "CONFIRMED", "reason": "exists but minor",
                 "severity": "Nit"}]
    out = V.apply_verdicts(findings, verdicts)
    assert len(out["findings"]) == 1
    assert out["findings"][0]["verdict"] == "CONFIRMED"
    assert out["findings"][0]["severity"] == "Nit"
    assert len(out["downgrades"]) == 1


# --- stage_ids / cluster_findings ---------------------------------------------

def test_stage_ids_assigns_unique_v_ids_despite_identity_collision():
    f1 = _f("a.py", "same title", "Important")
    f2 = _f("a.py", "Same Title!", "Minor")
    assert CB.finding_identity(f1) == CB.finding_identity(f2)
    staged = V.stage_ids([f1, f2])
    assert [x["id"] for x in staged] == ["v0", "v1"]
    assert staged[0] is not f1 and staged[1] is not f2


def test_cluster_findings_groups_by_file_and_line_bucket():
    findings = V.stage_ids([
        _f("a.py", "one", "Minor", line=10),
        _f("a.py", "two", "Minor", line=50),
        _f("a.py", "three", "Minor", line=150),
        _f("b.py", "four", "Minor", line=10),
    ])
    clusters = V.cluster_findings(findings)
    keys = [c["key"] for c in clusters]
    assert keys == ["a.py:0", "a.py:1", "b.py:0"]
    by_key = {c["key"]: c for c in clusters}
    assert [f["title"] for f in by_key["a.py:0"]["findings"]] == ["one", "two"]
    assert by_key["a.py:0"]["ids"] == ["v0", "v1"]
    assert by_key["a.py:1"]["ids"] == ["v2"]
    assert by_key["b.py:0"]["ids"] == ["v3"]
    all_ids = []
    for c in clusters:
        all_ids.extend(c["ids"])
    assert all_ids == ["v0", "v1", "v2", "v3"]


# --- merge_and_rank -----------------------------------------------------------

def _output_ids(result):
    if result.get("merges"):
        ids = []
        for m in result["merges"]:
            ids.extend(m["member_ids"])
        return ids
    return [f["id"] for f in result["findings"] if "id" in f]


def test_merge_and_rank_no_grouping_standalone_ranked():
    survivors = [
        {"id": "v0", "file": "b.py", "line": 5, "title": "b", "severity": "Minor", "verdict": "PLAUSIBLE"},
        {"id": "v1", "file": "a.py", "line": 10, "title": "a", "severity": "Critical", "verdict": "CONFIRMED"},
        {"id": "v2", "file": "a.py", "line": 1, "title": "c", "severity": "Important", "verdict": "PLAUSIBLE"},
    ]
    out = V.merge_and_rank(survivors)
    assert out["merges"] == []
    assert [f["id"] for f in out["findings"]] == ["v1", "v2", "v0"]


def test_merge_and_rank_valid_grouping_folds_and_covers_all_ids():
    survivors = [
        {"id": "v0", "file": "a.py", "line": 1, "title": "a", "severity": "Minor",
         "verdict": "PLAUSIBLE", "body": "part one"},
        {"id": "v1", "file": "a.py", "line": 2, "title": "b", "severity": "Critical",
         "verdict": "CONFIRMED", "body": "part two"},
        {"id": "v2", "file": "b.py", "line": 1, "title": "c", "severity": "Nit", "verdict": "PLAUSIBLE"},
    ]
    grouping = [
        {"group_id": "g1", "member_ids": ["v0", "v1"]},
        {"group_id": "g2", "member_ids": ["v2"]},
    ]
    out = V.merge_and_rank(survivors, grouping)
    assert len(out["findings"]) == 2
    merged = next(f for f in out["findings"] if f.get("id") != "v2")
    assert merged["severity"] == "Critical"
    assert merged["verdict"] == "CONFIRMED"
    assert "part one" in merged["body"] and "part two" in merged["body"]
    assert len(out["merges"]) == 2
    g1 = next(m for m in out["merges"] if m["group_id"] == "g1")
    assert g1["member_ids"] == ["v0", "v1"]
    assert set(_output_ids(out)) == {"v0", "v1", "v2"}


def test_merge_and_rank_malformed_grouping_fail_open():
    survivors = [
        {"id": "v0", "file": "a.py", "line": 1, "title": "a", "severity": "Minor", "verdict": "PLAUSIBLE"},
        {"id": "v1", "file": "b.py", "line": 1, "title": "b", "severity": "Important", "verdict": "PLAUSIBLE"},
    ]
    cases = [
        [{"group_id": "g1", "member_ids": ["v0"]}],           # missing v1
        [{"group_id": "g1", "member_ids": ["v0", "v0"]}],   # duplicate
        [{"group_id": "g1", "member_ids": ["v0", "v9"]}],   # unknown id
        "not-a-list",
    ]
    for grouping in cases:
        out = V.merge_and_rank(survivors, grouping)
        assert sorted(f["id"] for f in out["findings"]) == ["v0", "v1"]
        assert out["merges"] == []
        assert set(_output_ids(out)) == {"v0", "v1"}


def test_merge_and_rank_idless_survivor_passes_through_never_dropped():
    survivors = [
        {"id": "v0", "file": "a.py", "line": 1, "title": "a", "severity": "Critical", "verdict": "CONFIRMED"},
        {"file": "b.py", "line": 2, "title": "no id", "severity": "Important", "verdict": "PLAUSIBLE"},
    ]
    out = V.merge_and_rank(survivors)
    titles = sorted(f["title"] for f in out["findings"])
    assert titles == ["a", "no id"]          # the id-less survivor is NOT dropped
    assert len(out["findings"]) == 2


def test_merge_and_rank_non_dict_survivor_ignored():
    out = V.merge_and_rank(["garbage", {"id": "v0", "severity": "Minor"}])
    assert len(out["findings"]) == 1


def test_coverage_property_mixed_with_and_without_grouping():
    survivors = [
        {"id": "v0", "file": "a.py", "line": 1, "title": "a", "severity": "Minor", "verdict": "PLAUSIBLE"},
        {"id": "v1", "file": "a.py", "line": 2, "title": "b", "severity": "Important", "verdict": "CONFIRMED"},
        {"id": "v2", "file": "c.py", "line": 3, "title": "c", "severity": "Nit", "verdict": "PLAUSIBLE"},
    ]
    input_ids = {s["id"] for s in survivors}
    for grouping in (
        None,
        [{"group_id": "g1", "member_ids": ["v0", "v1"]}, {"group_id": "g2", "member_ids": ["v2"]}],
    ):
        out = V.merge_and_rank(survivors, grouping)
        assert set(_output_ids(out)) == input_ids
        assert len(_output_ids(out)) == len(input_ids)
