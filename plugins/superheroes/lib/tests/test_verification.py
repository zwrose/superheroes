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
        "unverified": [], "ambiguous": [],
    }
    findings = _stage([_f("a.py", "bug", "Important")])
    out = V.apply_verdicts(findings, "not-a-list")
    assert len(out["findings"]) == 1 and out["drops"] == []
    out2 = V.apply_verdicts(findings, [None, 42, {"verdict": "REFUTED"}])
    assert len(out2["findings"]) == 1 and out2["drops"] == []


def test_confirmed_with_downgrade_survives_and_records_downgrade():
    findings = _stage([_f("a.py", "race", "Critical")])
    verdicts = [{"id": "v0", "verdict": "CONFIRMED", "reason": "exists but minor",
                 "severity": "Nit", "evidence": "ran repro, only reachable in dev"}]
    out = V.apply_verdicts(findings, verdicts)
    assert len(out["findings"]) == 1
    assert out["findings"][0]["verdict"] == "CONFIRMED"
    assert out["findings"][0]["severity"] == "Nit"
    assert len(out["downgrades"]) == 1


# A2: a duplicate verdict id is ambiguous → honor none → KEEP-ON-UNCERTAIN (never the
# last REFUTED silently winning and dropping the finding), and the id is disclosed.
def test_duplicate_verdict_id_is_ambiguous_keep_on_uncertain_and_disclosed():
    findings = _stage([_f("a.py", "real", "Critical")])
    verdicts = [
        {"id": "v0", "verdict": "PLAUSIBLE", "reason": "x"},
        {"id": "v0", "verdict": "REFUTED", "reason": "safe"},
    ]
    out = V.apply_verdicts(findings, verdicts)
    assert len(out["findings"]) == 1                    # survives — not dropped
    assert out["findings"][0]["verdict"] == "PLAUSIBLE"
    assert out["findings"][0]["severity"] == "Critical"  # own pre-verification severity kept
    assert out["drops"] == []
    assert "v0" in out["ambiguous"]                     # disclosed, not silent
    assert "v0" not in out["unverified"]                # ambiguous ≠ silent


# A3: a rejected verdict (reasonless-REFUTED) must NOT apply its `severity` — the finding
# keeps its own pre-verification severity, and no downgrade is recorded.
def test_reasonless_refuted_with_severity_keeps_original_severity_no_downgrade():
    findings = _stage([_f("a.py", "real", "Critical")])
    verdicts = [{"id": "v0", "verdict": "REFUTED", "reason": "", "severity": "Nit"}]
    out = V.apply_verdicts(findings, verdicts)
    assert len(out["findings"]) == 1
    assert out["findings"][0]["verdict"] == "PLAUSIBLE"
    assert out["findings"][0]["severity"] == "Critical"  # NOT demoted to the rejected Nit
    assert out["downgrades"] == []
    assert out["drops"] == []


# A4a: a CONFIRMED with no executed receipt is an unproven claim → downgraded to PLAUSIBLE;
# a CONFIRMED WITH evidence stays CONFIRMED and carries the receipt.
def test_confirmed_without_evidence_downgraded_to_plausible():
    findings = _stage([_f("a.py", "claim", "Critical")])
    out = V.apply_verdicts(findings, [{"id": "v0", "verdict": "CONFIRMED", "reason": "looks real"}])
    assert out["findings"][0]["verdict"] == "PLAUSIBLE"
    assert "evidence" not in out["findings"][0]
    # empty-string evidence is not a receipt either
    findings_e = _stage([_f("a.py", "claim", "Critical")])
    out_e = V.apply_verdicts(findings_e, [{"id": "v0", "verdict": "CONFIRMED", "evidence": "   "}])
    assert out_e["findings"][0]["verdict"] == "PLAUSIBLE"
    # with a real receipt it stays CONFIRMED and carries the evidence
    findings2 = _stage([_f("a.py", "claim", "Critical")])
    out2 = V.apply_verdicts(findings2, [{"id": "v0", "verdict": "CONFIRMED", "reason": "real",
                                         "evidence": "ran repro, line 12 raises"}])
    assert out2["findings"][0]["verdict"] == "CONFIRMED"
    assert out2["findings"][0]["evidence"] == "ran repro, line 12 raises"


# A7: a finding that received NO matching verdict survives PLAUSIBLE and its id is disclosed
# in `unverified`; a finding with a real verdict does not appear there.
def test_unverified_lists_findings_with_no_matching_verdict():
    findings = _stage([_f("a.py", "silent", "Important"), _f("b.py", "judged", "Minor")])
    verdicts = [{"id": "v1", "verdict": "PLAUSIBLE", "reason": "looked at it"}]
    out = V.apply_verdicts(findings, verdicts)
    assert out["findings"][0]["verdict"] == "PLAUSIBLE"  # v0 kept-on-uncertain
    assert "v0" in out["unverified"]
    assert "v1" not in out["unverified"]


# H: _kept_severity's fail-closed default — an off-scale/missing finding severity with no
# honored verdict resolves to the blocking floor "Important", never silently "Nit".
def test_kept_severity_fail_closed_default_when_off_scale():
    assert V._kept_severity({"severity": "bogus"}, None, False) == V._DEFAULT_BLOCKING_SEVERITY
    assert V._DEFAULT_BLOCKING_SEVERITY == "Important"
    assert V._kept_severity({}, None, False) == "Important"                      # missing severity
    assert V._kept_severity({"severity": "bogus"}, {"severity": "Nit"}, False) == "Important"  # rejected verdict's Nit ignored
    assert V._kept_severity({"severity": "bogus"}, {"severity": "Minor"}, True) == "Minor"     # honored verdict tier applies
    # end-to-end: an off-scale finding with no verdict lands on the floor, not "Nit"
    out = V.apply_verdicts(_stage([_f("a.py", "weird", "bogus-tier")]), [])
    assert out["findings"][0]["severity"] == "Important"


# H: a REFUTED drop of a NON-blocking finding is tagged False (guards a constant-True mutant).
def test_refuted_drop_of_non_blocking_finding_not_blocking_tagged():
    findings = _stage([_f("a.py", "style", "Nit")])
    verdicts = [{"id": "v0", "verdict": "REFUTED", "reason": "not even an issue"}]
    out = V.apply_verdicts(findings, verdicts)
    assert len(out["drops"]) == 1
    assert out["drops"][0]["was_blocking_tagged"] is False


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
    """Reconstruct which INPUT survivor ids the output actually covers, read from the REAL
    `findings` (never from an echo of the input grouping). A merged finding — identified by
    its `id` matching a merge's `kept_id` — contributes that merge's `member_ids`; a
    standalone finding contributes its own id. So the coverage set FAILS if a real survivor
    is dropped from `findings` (the old helper read `merges[].member_ids`, an echo of the
    INPUT grouping, which made the grouped branch tautological)."""
    merges_by_kept = {m["kept_id"]: m["member_ids"] for m in result.get("merges", [])}
    ids = []
    for f in result["findings"]:
        fid = f.get("id")
        if fid in merges_by_kept:
            ids.extend(merges_by_kept[fid])
        elif "id" in f:
            ids.append(fid)
    return ids


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
         "verdict": "CONFIRMED", "evidence": "ran repro, line 2 raises", "body": "part two"},
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
    assert merged["verdict"] == "CONFIRMED"          # a Critical member is CONFIRMED-with-evidence
    assert merged["evidence"] == "ran repro, line 2 raises"  # its receipt is carried onto the merged finding
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


# A1: an empty-member group must not crash merge_and_rank — reject the grouping and fail
# open to unmerged survivors, dropping nothing.
def test_merge_and_rank_empty_member_group_fails_open_no_raise():
    survivors = [
        {"id": "v0", "file": "a.py", "line": 1, "title": "a", "severity": "Critical", "verdict": "PLAUSIBLE"},
        {"id": "v1", "file": "b.py", "line": 1, "title": "b", "severity": "Important", "verdict": "PLAUSIBLE"},
    ]
    grouping = [
        {"group_id": "empty", "member_ids": []},           # would make max() raise if honored
        {"group_id": "g", "member_ids": ["v0", "v1"]},
    ]
    out = V.merge_and_rank(survivors, grouping)            # must NOT raise
    assert sorted(f["id"] for f in out["findings"]) == ["v0", "v1"]
    assert out["merges"] == []
    assert set(_output_ids(out)) == {"v0", "v1"}


# F1: an unhashable (list/dict) severity must not crash merge_and_rank — never-raise. The
# rank guard returns the unknown rank without a dict lookup, so the finding still survives.
def test_merge_and_rank_unhashable_severity_never_raises():
    out = V.merge_and_rank([{"id": "v0", "severity": []}])    # list severity — must NOT raise
    assert len(out["findings"]) == 1
    assert out["findings"][0]["id"] == "v0"
    out2 = V.merge_and_rank([{"id": "v0", "severity": {}}])   # dict severity — must NOT raise
    assert len(out2["findings"]) == 1


# A4b: the merged finding's verdict follows the highest-severity representative, never
# any-member — so a PLAUSIBLE-Critical + CONFIRMED-Minor group cannot fabricate a
# receiptless CONFIRMED Critical.
def test_merge_group_verdict_follows_representative_not_any_member():
    survivors = [
        {"id": "v0", "file": "a.py", "line": 1, "title": "p", "severity": "Critical", "verdict": "PLAUSIBLE"},
        {"id": "v1", "file": "a.py", "line": 2, "title": "c", "severity": "Minor",
         "verdict": "CONFIRMED", "evidence": "r"},
    ]
    grouping = [{"group_id": "g", "member_ids": ["v0", "v1"]}]
    out = V.merge_and_rank(survivors, grouping)
    assert len(out["findings"]) == 1
    merged = out["findings"][0]
    assert merged["severity"] == "Critical"
    assert merged["verdict"] == "PLAUSIBLE"     # rep (Critical) was PLAUSIBLE
    assert "evidence" not in merged             # the Minor member's receipt is NOT carried onto the Critical


# F2(a): a PLAUSIBLE-Critical + CONFIRMED-Critical group merges to CONFIRMED regardless of
# member order — GATE-eligibility must not depend on model-supplied member order — and the
# confirming member's evidence is carried.
def test_merge_group_confirmed_at_max_severity_is_order_independent():
    survivors = [
        {"id": "v0", "file": "x", "line": 1, "title": "p", "severity": "Critical", "verdict": "PLAUSIBLE"},
        {"id": "v1", "file": "x", "line": 2, "title": "c", "severity": "Critical",
         "verdict": "CONFIRMED", "evidence": "ran repro, line 2 raises"},
    ]
    for order in (["v0", "v1"], ["v1", "v0"]):
        out = V.merge_and_rank(survivors, [{"group_id": "g", "member_ids": order}])
        assert len(out["findings"]) == 1
        merged = out["findings"][0]
        assert merged["severity"] == "Critical"
        assert merged["verdict"] == "CONFIRMED", f"order {order} must be CONFIRMED"
        assert merged["evidence"] == "ran repro, line 2 raises", f"evidence carried for order {order}"


# F2(b): a PLAUSIBLE-Critical + CONFIRMED-Minor group stays PLAUSIBLE-Critical in BOTH orders
# — a lower-severity confirmation never promotes the merged finding (the A4b invariant), and
# no receipt is fabricated onto the Critical.
def test_merge_group_lower_severity_confirmed_never_promotes_either_order():
    survivors = [
        {"id": "v0", "file": "x", "line": 1, "title": "p", "severity": "Critical", "verdict": "PLAUSIBLE"},
        {"id": "v1", "file": "x", "line": 2, "title": "c", "severity": "Minor",
         "verdict": "CONFIRMED", "evidence": "ran repro"},
    ]
    for order in (["v0", "v1"], ["v1", "v0"]):
        out = V.merge_and_rank(survivors, [{"group_id": "g", "member_ids": order}])
        merged = out["findings"][0]
        assert merged["severity"] == "Critical"
        assert merged["verdict"] == "PLAUSIBLE", f"order {order} must stay PLAUSIBLE"
        assert "evidence" not in merged, f"no fabricated receipt for order {order}"


# F2(c): a PLAUSIBLE-Critical + PLAUSIBLE-Critical group stays PLAUSIBLE (no member confirms).
def test_merge_group_all_plausible_at_max_severity_stays_plausible():
    survivors = [
        {"id": "v0", "file": "x", "line": 1, "title": "p", "severity": "Critical", "verdict": "PLAUSIBLE"},
        {"id": "v1", "file": "x", "line": 2, "title": "q", "severity": "Critical", "verdict": "PLAUSIBLE"},
    ]
    out = V.merge_and_rank(survivors, [{"group_id": "g", "member_ids": ["v0", "v1"]}])
    merged = out["findings"][0]
    assert merged["severity"] == "Critical"
    assert merged["verdict"] == "PLAUSIBLE"
    assert "evidence" not in merged


# G1: for NON-TIER (malformed/unhashable) severities the merged verdict AND severity must be
# order-independent. `_merge_group` coerces each member to an EFFECTIVE severity — a valid
# tier passes through, anything else falls to the fail-closed blocking default — so both the
# merged severity and the confirming-member comparison are deterministic regardless of member
# order (unreachable in the real pipeline, but a fail-closed fold must be unconditionally so).
def test_merge_group_malformed_severity_deterministic_and_valid_tier():
    survivors = [
        {"id": "a", "file": "x", "line": 1, "title": "p", "severity": [], "verdict": "PLAUSIBLE"},
        {"id": "b", "file": "x", "line": 2, "title": "c", "severity": {},
         "verdict": "CONFIRMED", "evidence": "r"},
    ]
    results = []
    for order in (["a", "b"], ["b", "a"]):
        out = V.merge_and_rank(survivors, [{"group_id": "g", "member_ids": order}])
        assert len(out["findings"]) == 1
        merged = out["findings"][0]
        assert merged["severity"] in V._TIERS      # coerced to a valid tier, fail-closed
        results.append((merged["verdict"], merged["severity"]))
    assert results[0] == results[1], f"non-tier merge must be order-independent, got {results}"


# G1: a valid tier is unchanged by the effective-severity coercion (`_eff_sev` is identity on
# a tier) — the coercion only touches non-tier severities.
def test_eff_sev_identity_on_valid_tier_and_default_otherwise():
    for tier in V._TIERS:
        assert V._eff_sev(tier) == tier
    for bad in ("bogus", None, [], {}, 123):
        assert V._eff_sev(bad) == V._DEFAULT_BLOCKING_SEVERITY


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


def test_union_dimensions_joins_strings_and_flattens_lists():
    assert V._union_dimensions([
        {"dimension": "a"},
        {"dimension": "b"},
    ]) == "a + b"
    assert V._union_dimensions([
        {"dimension": "a"},
        {"dimension": ["b", "c"]},
    ]) == "a + b + c"
    assert V._union_dimensions([
        {"dimension": ["b", "c"]},
        {"dimension": ["b", "d"]},
    ]) == "b + c + d"


def test_union_dimensions_no_dims_leaves_merge_without_dimension_key():
    merged = V._merge_group([{"severity": "Minor"}, {"severity": "Minor"}])
    assert "dimension" not in merged
