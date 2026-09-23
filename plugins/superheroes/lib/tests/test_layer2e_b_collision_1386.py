"""#1386: clamp-exact legacy-key collision — long bare key vs short finding at same location."""
import importlib.util
import os
import sys

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
FI = _load("finding_identity")


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


def _clamp_exact_pair():
    """Legacy long-title row (bare key) plus distinct short finding whose minted key is that bare key."""
    long = _long_finding()
    bare, long_minted = SC.location_key(long), SC.minted_identity_key(long)
    assert bare != long_minted
    clamped = FI.clamp_title(long["title"])
    short = {"file": "f.py", "line": 5, "title": clamped, "severity": "Important"}
    assert SC.minted_identity_key(short) == bare
    assert SC.minted_identity_key(short) != long_minted
    return long, short, bare, long_minted


def _assert_collision_refusal(refusal, bare):
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == SC.DISPOSITION_LEDGER_LEGACY_KEY_COLLISION_TOKEN
    assert bare in refusal["detail"]


def test_edge1_ledger_owned_clamp_exact_refuses():
    """edge 1: clamp-exact long/short pair on ledger-owned branch refuses."""
    long, short, bare, _long_minted = _clamp_exact_pair()
    state = _ledger_owned_state(
        dispositionLedger=[dict(long, **{
            SC.FINDING_KEY_FIELD: bare,
            "disposition": "fixed",
            "dispositionRound": 1,
        })],
        findings=[short],
    )
    rows = list(state["dispositionLedger"]) + list(state["findings"])
    collision = SC.legacy_key_collision(rows)
    assert collision == (bare, bare)
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    _assert_collision_refusal(refusal, bare)


def test_edge2_legacy_branch_clamp_exact_refuses():
    """edge 2: clamp-exact pair on legacy branch refuses the same way."""
    long, short, bare, _long_minted = _clamp_exact_pair()
    state = _legacy_state(
        _records=[{"findings": [dict(long, **{SC.FINDING_KEY_FIELD: bare})]}],
        findings=[short],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    _assert_collision_refusal(refusal, bare)


def test_edge3_clamp_exact_order_independent():
    """edge 3: clamp-exact pair with short row first still refuses."""
    long, short, bare, _long_minted = _clamp_exact_pair()
    state = _ledger_owned_state(
        dispositionLedger=[short],
        findings=[dict(long, **{
            SC.FINDING_KEY_FIELD: bare,
            "disposition": "fixed",
            "dispositionRound": 1,
        })],
    )
    rows = [short, dict(long, **{SC.FINDING_KEY_FIELD: bare})]
    collision = SC.legacy_key_collision(rows)
    assert collision == (bare, bare)
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    _assert_collision_refusal(refusal, bare)


def test_edge4_both_in_disposition_ledger_refuses():
    """edge 4: clamp-exact pair both inside dispositionLedger refuses."""
    long, short, bare, _long_minted = _clamp_exact_pair()
    state = _ledger_owned_state(
        dispositionLedger=[
            dict(long, **{
                SC.FINDING_KEY_FIELD: bare,
                "disposition": "refuted",
                "dispositionRound": 1,
                "refutedReason": "stale",
            }),
            short,
        ],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    _assert_collision_refusal(refusal, bare)


def test_edge5_same_legacy_finding_twice_admitted():
    """edge 5: same legacy finding twice under bare key is admitted."""
    long, _short, bare, _long_minted = _clamp_exact_pair()
    state = _ledger_owned_state(
        dispositionLedger=[dict(long, **{
            SC.FINDING_KEY_FIELD: bare,
            "disposition": "fixed",
            "dispositionRound": 1,
        })],
        findings=[dict(long, **{SC.FINDING_KEY_FIELD: bare})],
    )
    rows = list(state["dispositionLedger"]) + list(state["findings"])
    collision = SC.legacy_key_collision(rows)
    assert collision is None
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    assert bare in by_key


def test_edge6_legacy_row_alone_admitted():
    """edge 6: legacy row alone is admitted (unchanged)."""
    long = _long_finding()
    bare, _long_minted = SC.location_key(long), SC.minted_identity_key(long)
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


def test_edge7_short_title_alone_covered_by_e5():
    """edge 7: short-title bare==minted admitted — covered by test_e5_short_title_bare_equals_minted_no_collision."""
    pass


def test_edge8_non_dict_rows_skipped_collision_detected():
    """edge 8: non-dict rows interleaved — skipped, collision still detected."""
    long, short, bare, _long_minted = _clamp_exact_pair()
    rows = [
        "not-a-dict",
        dict(long, **{SC.FINDING_KEY_FIELD: bare}),
        short,
    ]
    assert SC.legacy_key_collision(rows) == (bare, bare)


def test_edge9_key_only_ledger_row_sparse_control():
    """edge 9: key-only ledger row beside full legacy live row — admitted."""
    long, _short, bare, _long_minted = _clamp_exact_pair()
    key_only = {
        SC.FINDING_KEY_FIELD: bare,
        "disposition": "fixed",
        "dispositionRound": 1,
    }
    state = _ledger_owned_state(
        dispositionLedger=[key_only],
        findings=[dict(long, **{SC.FINDING_KEY_FIELD: bare})],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
