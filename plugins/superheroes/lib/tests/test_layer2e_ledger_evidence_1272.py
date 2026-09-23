"""#1272 layer 2e: legacy key collision, receipt findingKey, transient identity, evidence binding."""
import glob
import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SC = _load("session_contract")
RC = _load("round_certification")
RD = _load("round_driver")


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}


def _ledger_owned_state(**over):
    base = {
        "schemaVersion": 5,
        "dispositionLedgerOwner": "ledger",
        "dispositionLedger": [],
        "findings": [],
        "_records": [],
    }
    base.update(over)
    return base


def _legacy_state(**over):
    base = {
        "schemaVersion": 5,
        "dispositionLedger": [],
        "findings": [],
        "_records": [],
    }
    base.update(over)
    return base


def _long_finding(title_suffix=" alpha"):
    prefix = "x" * 165
    return {"file": "f.py", "line": 5, "title": prefix + title_suffix, "severity": "Important"}


def _bare_minted(long):
    bare = SC.location_key(long)
    minted = SC.minted_identity_key(long)
    return bare, minted


def _assert_legacy_collision_refusal(refusal, bare, minted):
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == SC.DISPOSITION_LEDGER_LEGACY_KEY_COLLISION_TOKEN
    assert bare in refusal["detail"]
    assert minted in refusal["detail"]


# --- Part 1: legacy key collision edges e1–e8 -----------------------------------------

def test_e1_ledger_bare_live_minted_refuses():
    """axis: ledger bare key plus live minted twin refuses disposition-ledger-legacy-key-collision."""
    long = _long_finding()
    bare, minted = _bare_minted(long)
    state = _ledger_owned_state(
        dispositionLedger=[dict(long, **{
            SC.FINDING_KEY_FIELD: bare,
            "disposition": "fixed",
            "dispositionRound": 1,
        })],
        findings=[dict(long, **{SC.FINDING_KEY_FIELD: minted})],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    _assert_legacy_collision_refusal(refusal, bare, minted)


def test_e2_ledger_minted_live_bare_refuses():
    """axis: ledger minted key plus live bare twin refuses disposition-ledger-legacy-key-collision."""
    long = _long_finding()
    bare, minted = _bare_minted(long)
    state = _ledger_owned_state(
        dispositionLedger=[dict(long, **{
            SC.FINDING_KEY_FIELD: minted,
            "disposition": "refuted",
            "dispositionRound": 1,
            "refutedReason": "stale",
        })],
        findings=[dict(long, **{SC.FINDING_KEY_FIELD: bare})],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    _assert_legacy_collision_refusal(refusal, bare, minted)


def test_e3_two_ledger_rows_bare_and_minted_refuses():
    """axis: two ledger rows (bare plus minted) refuse disposition-ledger-legacy-key-collision."""
    long = _long_finding()
    bare, minted = _bare_minted(long)
    state = _ledger_owned_state(
        dispositionLedger=[
            dict(long, **{SC.FINDING_KEY_FIELD: bare, "disposition": "fixed", "dispositionRound": 1}),
            dict(long, **{SC.FINDING_KEY_FIELD: minted}),
        ],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    _assert_legacy_collision_refusal(refusal, bare, minted)


def test_e4_legacy_branch_records_bare_live_minted_refuses():
    """axis: legacy branch _records bare plus live minted refuses disposition-ledger-legacy-key-collision."""
    long = _long_finding()
    bare, minted = _bare_minted(long)
    state = _legacy_state(
        _records=[{"findings": [dict(long, **{SC.FINDING_KEY_FIELD: bare})]}],
        findings=[dict(long, **{SC.FINDING_KEY_FIELD: minted})],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    _assert_legacy_collision_refusal(refusal, bare, minted)


def test_e5_short_title_bare_equals_minted_no_collision():
    """axis: short-title finding whose bare key equals minted key is never a collision."""
    short = {"file": "a.py", "line": 1, "title": "bug", "severity": "Minor"}
    bare = SC.location_key(short)
    assert bare == SC.minted_identity_key(short)
    rows = [dict(short, **{SC.FINDING_KEY_FIELD: bare})]
    assert SC.legacy_key_collision(rows) is None
    state = _ledger_owned_state(
        dispositionLedger=[dict(short, **{SC.FINDING_KEY_FIELD: bare})],
        findings=[dict(short, **{SC.FINDING_KEY_FIELD: bare})],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    assert bare in by_key


def test_e6_bare_keyed_row_alone_no_refusal():
    """axis: bare-keyed row alone does not trigger legacy-key-collision refusal."""
    long = _long_finding()
    bare, _minted = _bare_minted(long)
    state = _ledger_owned_state(
        dispositionLedger=[dict(long, **{
            SC.FINDING_KEY_FIELD: bare,
            "disposition": "fixed",
            "dispositionRound": 1,
        })],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    assert bare in by_key


def test_e7_two_distinct_findings_same_location_no_collision():
    """axis: two distinct findings at one location with different titles are not a collision."""
    alpha = _long_finding(" alpha")
    beta = _long_finding(" beta")
    compiled, _ = RD.mechanical_compile([alpha, beta], None)
    keys = [f[SC.FINDING_KEY_FIELD] for f in compiled]
    assert len(keys) == 2
    state = _ledger_owned_state(
        dispositionLedger=[dict(compiled[0], disposition="fixed", dispositionRound=1)],
        findings=[compiled[1]],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    assert len(by_key) == 2


def test_e8_non_dict_rows_skipped_by_helper():
    """axis: non-dict rows are skipped by legacy_key_collision — malformed refusals unchanged."""
    long = _long_finding()
    bare, minted = _bare_minted(long)
    rows = [
        "not-a-dict",
        dict(long, **{SC.FINDING_KEY_FIELD: bare}),
        dict(long, **{SC.FINDING_KEY_FIELD: minted}),
    ]
    assert SC.legacy_key_collision(rows) == SC.LegacyKeyCollision(bare, minted)
    state = _ledger_owned_state(dispositionLedger=["not-a-dict"])
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    assert refusal is not None
    assert refusal["bindingFailure"] == SC.DISPOSITION_LEDGER_MALFORMED_TOKEN


# --- Part 1b: the clamp-exact pair — a different finding claims the legacy bare key ---------

def _clamp_exact_pair():
    """A long title and the short title equal to its clamp: one bare key, two minted identities."""
    long = _long_finding()
    short = dict(long, title=SC.clamp_title(long["title"]))
    bare, minted = _bare_minted(long)
    assert SC.location_key(short) == bare
    assert SC.minted_identity_key(short) == bare
    assert minted != bare
    return long, short, bare, minted


def _assert_clamp_exact_refusal(by_key, refusal, bare, minted):
    assert by_key == {}
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == SC.DISPOSITION_LEDGER_LEGACY_KEY_COLLISION_TOKEN
    assert refusal["detail"] == (
        "legacy bare key %r (minted %r) is also claimed by a different finding minted %r"
        % (bare, minted, bare))


def test_e9_helper_refuses_clamp_exact_pair_in_either_order():
    """axis: a legacy bare row and a short-title row minting the same bare key collide."""
    long, short, bare, minted = _clamp_exact_pair()
    legacy = dict(long, **{SC.FINDING_KEY_FIELD: bare})
    claimant = dict(short, **{SC.FINDING_KEY_FIELD: bare})
    expected = SC.LegacyKeyCollision(bare, minted, bare)
    assert SC.legacy_key_collision([legacy, claimant]) == expected
    assert SC.legacy_key_collision([claimant, legacy]) == expected


def test_e10_ledger_owned_clamp_exact_stale_disposition_refused_never_joined():
    """axis: ledger-owned read refuses the legacy disposition rather than join it to the short finding."""
    long, short, bare, minted = _clamp_exact_pair()
    state = _ledger_owned_state(
        dispositionLedger=[dict(long, **{
            SC.FINDING_KEY_FIELD: bare,
            "disposition": "fixed",
            "dispositionRound": 1,
        })],
        findings=[dict(short, **{SC.FINDING_KEY_FIELD: bare})],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    _assert_clamp_exact_refusal(by_key, refusal, bare, minted)


def test_e11_legacy_branch_clamp_exact_stale_disposition_refused_never_joined():
    """axis: the legacy (non-owner) read refuses the same pair from _records plus live findings."""
    long, short, bare, minted = _clamp_exact_pair()
    state = _legacy_state(
        _records=[{"findings": [dict(long, **{
            SC.FINDING_KEY_FIELD: bare,
            "disposition": "refuted",
            "dispositionRound": 1,
            "refutedReason": "stale",
        })]}],
        findings=[dict(short, **{SC.FINDING_KEY_FIELD: bare})],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    _assert_clamp_exact_refusal(by_key, refusal, bare, minted)


def test_e12_legacy_row_beside_its_own_bare_keyed_copy_still_joins():
    """axis: the same legacy finding in the ledger and live, both under the bare key, is one finding."""
    long = _long_finding()
    bare, _minted = _bare_minted(long)
    assert SC.legacy_key_collision([
        dict(long, **{SC.FINDING_KEY_FIELD: bare}),
        dict(long, **{SC.FINDING_KEY_FIELD: bare}),
    ]) is None
    state = _ledger_owned_state(
        dispositionLedger=[dict(long, **{
            SC.FINDING_KEY_FIELD: bare,
            "disposition": "fixed",
            "dispositionRound": 1,
        })],
        findings=[dict(long, **{SC.FINDING_KEY_FIELD: bare}, severity="Critical")],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    assert list(by_key) == [bare]
    assert by_key[bare]["disposition"] == "fixed"
    assert by_key[bare]["severity"] == "Critical"


# --- Part 2: receipt findingKey projection ----------------------------------------------

def test_driver_receipt_finding_key_matches_state_row():
    """axis: build_receipt findings row carries findingKey equal to the state row's."""
    finding = {"file": "r.py", "line": 3, "title": "leak", "severity": "Important", "id": "v0"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    RD._set_findings(state, compiled)
    row = state["findings"][0]
    receipt = RD.build_receipt(state)
    assert len(receipt["findings"]) == 1
    projected = receipt["findings"][0]
    assert projected.get(SC.FINDING_KEY_FIELD) == row.get(SC.FINDING_KEY_FIELD)


def test_legacy_receipt_omits_finding_key_even_when_state_has_it():
    """axis: v2 receipt shape stays byte-for-byte on finding rows — no findingKey key."""
    finding = {"file": "a.py", "line": 1, "title": "Issue", "severity": "Important", "id": "F1"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    state["schemaVersion"] = 2
    RD._set_findings(state, compiled)
    assert state["findings"][0].get(SC.FINDING_KEY_FIELD)
    state["terminal"] = "converged"
    state["certification"] = {"shape": "audited-chain"}
    receipt = RD.build_receipt(state)
    assert receipt["schemaVersion"] == 2
    assert SC.FINDING_KEY_FIELD not in receipt["findings"][0]


def test_receipt_with_absent_schema_version_does_not_raise():
    """axis: absent schemaVersion must not raise on findingKey projection gate."""
    finding = {"file": "a.py", "line": 1, "title": "Issue", "severity": "Important", "id": "F1"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    del state["schemaVersion"]
    RD._set_findings(state, compiled)
    state["terminal"] = "converged"
    state["certification"] = {"shape": "audited-chain"}
    receipt = RD.build_receipt(state)
    assert SC.FINDING_KEY_FIELD not in receipt["findings"][0]


# --- Part 3: disposition metadata does not move identity --------------------------------

_DISPOSITION_METADATA_VALUES = {
    "dispositionRound": 1,
    "refutedReason": "stale",
    "outOfScopeReason": "not applicable",
    "followUp": {"note": "later"},
    "mergedInto": "other-key",
    "raisedRound": 2,
}


@pytest.mark.parametrize("field", sorted(_DISPOSITION_METADATA_VALUES))
def test_finding_content_canonical_invariant_under_disposition_metadata(field):
    """axis: attaching disposition metadata leaves finding_content_canonical unchanged."""
    base = {"file": "a.py", "line": 1, "title": "bug", "severity": "Minor"}
    before = SC.finding_content_canonical(base)
    after = SC.finding_content_canonical({**base, field: _DISPOSITION_METADATA_VALUES[field]})
    assert before == after


def test_foreign_preset_preserved_despite_disposition_metadata_diff():
    """axis: foreign preset findingKey survives _set_findings when rows differ only in disposition metadata."""
    foreign_key = "caller-controlled"
    base = {
        "file": "b.py", "line": 10, "title": "bug", "severity": "Important",
        SC.FINDING_KEY_FIELD: foreign_key,
    }
    row_a = dict(base)
    row_b = dict(base, dispositionRound=1, mergedInto="other-key")
    state = RD.new_state(_cfg())
    RD._set_findings(state, [row_a, row_b])
    for row in state["findings"]:
        assert row[SC.FINDING_KEY_FIELD] == foreign_key
        assert "#" not in row[SC.FINDING_KEY_FIELD]


# --- Part 4: evidence_binding one home ------------------------------------------------

def test_evidence_binding_write_kind_execution_only():
    """axis: evidence_binding returns execution-only for WRITE_RESULT_KIND."""
    assert SC.evidence_binding(SC.WRITE_RESULT_KIND) == SC.EXECUTION_ONLY_BINDING


def test_evidence_binding_review_kind_payload_bound():
    """axis: evidence_binding returns payload-bound for non-write result kinds."""
    assert SC.evidence_binding("findings") == SC.PAYLOAD_BOUND_BINDING


def test_write_result_kind_comparison_census():
    """axis: WRITE_RESULT_KIND comparisons live only in session_contract (not round_driver/certification)."""
    patterns = (
        "== session_contract.WRITE_RESULT_KIND",
        "!= session_contract.WRITE_RESULT_KIND",
        "WRITE_RESULT_KIND ==",
    )
    allowed = {"session_contract.py", "engine_dispatch.py"}
    violations = []
    for path in glob.glob(os.path.join(_LIB, "*.py")):
        basename = os.path.basename(path)
        if basename in allowed:
            continue
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        for pattern in patterns:
            if pattern in src:
                violations.append("%s: %s" % (basename, pattern))
    assert violations == []
