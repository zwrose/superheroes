from audits import apply_audit_results, AUDIT_RULINGS


def finding(fid, file="src/a.py", line=5, title="bug", severity="Important"):
    return {"id": fid, "file": file, "line": line, "title": title, "severity": severity}


def _audit_by_id(out, fid):
    return next(a for a in out["audits"] if a["id"] == fid)


def test_rulings_constant():
    assert AUDIT_RULINGS == ("discharged", "not-discharged", "discharged-but-new-issue")


# --- happy paths --------------------------------------------------------------

def test_discharged_with_reason():
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "discharged", "reason": "fix verified by test X"}])
    assert out["discharged"] == ["v0"]
    assert out["notDischarged"] == []
    assert _audit_by_id(out, "v0")["ruling"] == "discharged"
    assert out["newIssues"] == []


def test_discharged_carries_evidence():
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "discharged", "reason": "r", "evidence": "pytest passed"}])
    assert _audit_by_id(out, "v0")["evidence"] == "pytest passed"


def test_plain_not_discharged():
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "not-discharged", "reason": "still broken"}])
    assert out["discharged"] == []
    assert out["notDischarged"] == ["v0"]
    assert out["malformed"] == []
    assert _audit_by_id(out, "v0")["ruling"] == "not-discharged"


# --- fail-closed: silence / missing -------------------------------------------

def test_no_matching_result_is_unaudited_not_discharged():
    out = apply_audit_results([finding("v0")], [])
    assert out["unaudited"] == ["v0"]
    assert out["notDischarged"] == ["v0"]
    assert out["discharged"] == []
    assert _audit_by_id(out, "v0")["ruling"] == "not-discharged"


# --- fail-closed: unmatched result --------------------------------------------

def test_unmatched_result_disclosed_and_ignored():
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "discharged", "reason": "ok"},
         {"id": "v9", "ruling": "discharged", "reason": "phantom"}])
    assert out["discharged"] == ["v0"]
    assert out["unmatched"] == ["v9"]


# --- fail-closed: ambiguous (duplicate results) -------------------------------

def test_duplicate_results_are_ambiguous_and_honored_none():
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "discharged", "reason": "a"},
         {"id": "v0", "ruling": "discharged", "reason": "b"}])
    assert out["ambiguous"] == ["v0"]
    assert out["notDischarged"] == ["v0"]
    assert out["discharged"] == []
    assert out["unaudited"] == []  # ambiguous is NOT counted as silence
    assert _audit_by_id(out, "v0")["ruling"] == "not-discharged"


# --- fail-closed: reasonless discharged ---------------------------------------

def test_discharged_without_reason_is_malformed_not_discharged():
    for res in ({"id": "v0", "ruling": "discharged"},
                {"id": "v0", "ruling": "discharged", "reason": "   "}):
        out = apply_audit_results([finding("v0")], [res])
        assert out["malformed"] == ["v0"]
        assert out["notDischarged"] == ["v0"]
        assert out["discharged"] == []
        assert _audit_by_id(out, "v0")["ruling"] == "not-discharged"


# --- discharged-but-new-issue -------------------------------------------------

def test_discharged_but_new_issue_valid_flow():
    new = {"file": "src/b.py", "line": 20, "title": "leak", "severity": "Important",
           "body": "introduced by the fix"}
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "discharged-but-new-issue", "reason": "fixed but leaked",
          "newIssues": [new]}])
    # the fix itself counts discharged
    assert out["discharged"] == ["v0"]
    assert out["notDischarged"] == []
    assert _audit_by_id(out, "v0")["ruling"] == "discharged-but-new-issue"
    # the new-issue candidate is emitted, tagged with its origin
    assert len(out["newIssues"]) == 1
    emitted = out["newIssues"][0]
    assert emitted["originAuditId"] == "v0"
    assert emitted["title"] == "leak"
    assert emitted["file"] == "src/b.py"


def test_discharged_but_new_issue_empty_is_malformed_not_discharged():
    for res in ({"id": "v0", "ruling": "discharged-but-new-issue", "reason": "r"},
                {"id": "v0", "ruling": "discharged-but-new-issue", "reason": "r", "newIssues": []},
                {"id": "v0", "ruling": "discharged-but-new-issue", "reason": "r",
                 "newIssues": ["not-a-dict"]}):
        out = apply_audit_results([finding("v0")], [res])
        assert out["malformed"] == ["v0"], res
        assert out["notDischarged"] == ["v0"]
        assert out["discharged"] == []
        assert out["newIssues"] == []
        assert _audit_by_id(out, "v0")["ruling"] == "not-discharged"


def test_new_issue_non_dict_candidates_dropped_but_valid_ones_kept():
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "discharged-but-new-issue", "reason": "r",
          "newIssues": ["junk", {"title": "real", "file": "x", "line": 1, "severity": "Minor"}]}])
    assert out["discharged"] == ["v0"]
    assert [c["title"] for c in out["newIssues"]] == ["real"]
    assert out["newIssues"][0]["originAuditId"] == "v0"


# --- fail-closed: unknown ruling / junk ---------------------------------------

def test_unknown_ruling_is_malformed_not_discharged():
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "FIXED", "reason": "r"}])
    assert out["malformed"] == ["v0"]
    assert out["notDischarged"] == ["v0"]
    assert _audit_by_id(out, "v0")["ruling"] == "not-discharged"


def test_non_dict_result_ignored_finding_stays_unaudited():
    out = apply_audit_results([finding("v0")], ["junk", 5, None])
    assert out["unaudited"] == ["v0"]
    assert out["notDischarged"] == ["v0"]


def test_never_raises_on_junk_input():
    for audited, results in (
            (None, None),
            ("nope", "nope"),
            ([None, 5, "x"], [None]),
            ([{"no": "id"}], [{"no": "id"}]),
            ([finding("v0")], {"not": "a list"}),
            ([{"id": None}], [{"id": None, "ruling": "discharged"}]),
    ):
        out = apply_audit_results(audited, results)
        assert set(out) == {"audits", "discharged", "notDischarged", "newIssues",
                            "unaudited", "ambiguous", "malformed", "unmatched",
                            "unauthenticated", "echoMismatch"}


def test_idless_finding_is_kept_not_discharged():
    out = apply_audit_results([{"file": "x", "title": "t"}], [])
    # an id-less finding cannot be keyed into the id lists, but it is NEVER certified discharged:
    # it is kept as a fail-closed not-discharged audit entry (mirrors apply_verdicts).
    assert out["discharged"] == []
    assert out["notDischarged"] == []  # no id to list
    assert len(out["audits"]) == 1
    assert out["audits"][0]["ruling"] == "not-discharged"
    assert out["audits"][0]["id"] is None


# --- provenance: authenticate against the ORCHESTRATOR's dispatch manifest, not the echo ----

def test_collection_manifest_authenticates_and_records_trusted_value():
    """#507 WO-FIX-RECOVERY: a clearing ruling is authenticated against the ORCHESTRATOR's
    out-of-band collection manifest (must exist AND equal the driver-recorded selection). The audit
    entry records THAT trusted vendor — never the result's own echo."""
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "discharged", "reason": "verified", "auditorVendor": "codex"}],
        expected_auditors={"v0": "codex"},
        collection_manifest={"v0": "codex"})
    assert out["discharged"] == ["v0"]
    assert out["unauthenticated"] == []
    assert out["echoMismatch"] == []
    assert _audit_by_id(out, "v0")["auditor"] == "codex"


def test_missing_manifest_entry_is_unauthenticated():
    """The R2 defect fixed at the root: a clearing ruling that echoes the expected vendor but has NO
    manifest entry (the orchestrator never recorded who executed it) authenticates NOTHING — the
    echo is the auditor's own words used as their credential. Fail closed to unauthenticated."""
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "discharged", "reason": "trust me", "auditorVendor": "codex"}],
        expected_auditors={"v0": "codex"},
        collection_manifest={})  # orchestrator recorded no dispatch for v0
    assert out["discharged"] == []
    assert out["notDischarged"] == ["v0"]
    assert out["unauthenticated"] == ["v0"]


def test_manifest_vendor_mismatch_is_unauthenticated():
    """The orchestrator's manifest names a DIFFERENT vendor than the driver-recorded selection (a
    misroute) → not-discharged + unauthenticated, regardless of what the result echoes."""
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "discharged", "reason": "verified", "auditorVendor": "codex"}],
        expected_auditors={"v0": "codex"},
        collection_manifest={"v0": "claude"})  # dispatched to the WRONG vendor
    assert out["discharged"] == []
    assert out["notDischarged"] == ["v0"]
    assert out["unauthenticated"] == ["v0"]


def test_echo_mismatch_with_valid_manifest_discharges_and_discloses():
    """When the manifest authenticates, the in-result `auditorVendor` echo is ADVISORY: an echo that
    disagrees with the governing manifest is disclosed via `echoMismatch` but the discharge stands
    (the manifest governs)."""
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "discharged", "reason": "verified", "auditorVendor": "claude"}],
        expected_auditors={"v0": "codex"},
        collection_manifest={"v0": "codex"})  # manifest = selection; echo disagrees
    assert out["discharged"] == ["v0"]
    assert out["unauthenticated"] == []
    assert out["echoMismatch"] == ["v0"]
    entry = _audit_by_id(out, "v0")
    assert entry["auditor"] == "codex"  # the trusted manifest value, not the "claude" echo
    assert entry["echoMismatch"] == {"echo": "claude", "manifest": "codex"}


def test_junk_manifest_never_raises():
    """A malformed collection_manifest (non-dict, junk values) never raises; a clearing ruling with
    no usable manifest entry simply fails closed to unauthenticated."""
    for manifest in (None, "nope", 5, [], {"v0": None}, {"v0": ""}, {"v0": 7}):
        out = apply_audit_results(
            [finding("v0")],
            [{"id": "v0", "ruling": "discharged", "reason": "verified", "auditorVendor": "codex"}],
            expected_auditors={"v0": "codex"},
            collection_manifest=manifest)
        assert out["discharged"] == [], manifest
        assert out["unauthenticated"] == ["v0"], manifest


def test_target_with_no_recorded_selection_cannot_discharge():
    """#507 R2 residual: a clearing ruling on a target with NO recorded independent-auditor
    selection (absent from the driver map, and no auditorVendor on the target) cannot prove
    independence — fail closed to not-discharged + unauthenticated, even if the result echoes a
    vendor. Previously the missing selection SKIPPED the provenance check (fail-open)."""
    target = {"id": "v0", "file": "f.py", "line": 1, "title": "bug", "severity": "Important"}
    out = apply_audit_results(
        [target],
        [{"id": "v0", "ruling": "discharged", "reason": "verified", "auditorVendor": "codex"}],
        expected_auditors={})  # driver enforced provenance, but no selection for v0
    assert out["discharged"] == []
    assert out["notDischarged"] == ["v0"]
    assert out["unauthenticated"] == ["v0"]


def test_no_provenance_signal_preserves_library_accounting():
    """With NEITHER an expected_auditors map NOR a target auditorVendor, provenance is not enforced
    (the pure discharge-accounting library shape) — a discharge is honored as before."""
    out = apply_audit_results(
        [finding("v0")],
        [{"id": "v0", "ruling": "discharged", "reason": "verified"}])
    assert out["discharged"] == ["v0"]
    assert out["unauthenticated"] == []


# --- multiple findings, mixed rulings, partition completeness -----------------

def test_mixed_batch_partition():
    audited = [finding("v0"), finding("v1"), finding("v2"), finding("v3")]
    results = [
        {"id": "v0", "ruling": "discharged", "reason": "ok"},
        {"id": "v1", "ruling": "not-discharged", "reason": "nope"},
        {"id": "v2", "ruling": "discharged-but-new-issue", "reason": "r",
         "newIssues": [{"title": "n", "file": "f", "line": 1, "severity": "Minor"}]},
        # v3 has no result → unaudited
    ]
    out = apply_audit_results(audited, results)
    assert out["discharged"] == ["v0", "v2"]
    assert sorted(out["notDischarged"]) == ["v1", "v3"]
    assert out["unaudited"] == ["v3"]
    # every finding appears exactly once in audits
    assert sorted(a["id"] for a in out["audits"]) == ["v0", "v1", "v2", "v3"]
