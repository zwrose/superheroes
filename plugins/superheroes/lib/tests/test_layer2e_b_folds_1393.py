"""#1393 — the clamp-exact legacy-key collision and the gate-policy write path for a follow-up on a
rule that may not carry one."""
import hashlib
import importlib.util
import json
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
RD = _load("round_driver")
RGP = _load("review_gate_policy")
FI = _load("finding_identity")

_WELL_FORMED = {"item": "defer", "revisitTrigger": "when M2 opens", "classClosure": "tracked"}


# --- the clamp-exact collision --------------------------------------------------------------------

def _clamp_pair():
    """A long-title finding and a distinct finding whose title is exactly its clamped form."""
    long = {"file": "f.py", "line": 5, "title": ("word " * 40) + "tail", "severity": "Important"}
    short = dict(long, title=FI.clamp_title(long["title"]))
    bare = SC.location_key(long)
    assert SC.location_key(short) == bare
    assert SC.minted_identity_key(short) == bare
    assert SC.minted_identity_key(long) != bare
    return long, short, bare, SC.minted_identity_key(long)


def _legacy_row(long, bare):
    return dict(long, **{SC.FINDING_KEY_FIELD: bare, "disposition": "refuted",
                         "dispositionRound": 1, "refutedReason": "stale"})


def _assert_collision(refusal, bare, minted):
    assert refusal is not None
    assert refusal["bindingFailure"] == SC.DISPOSITION_LEDGER_LEGACY_KEY_COLLISION_TOKEN
    assert bare in refusal["detail"] and minted in refusal["detail"]


def test_clamp_exact_pair_collides_in_helper():
    # axis: a legacy bare-keyed row beside a distinct finding claiming the same bare key collides
    long, short, bare, minted = _clamp_pair()
    assert SC.legacy_key_collision([_legacy_row(long, bare), dict(short)]) == (bare, minted)


def test_clamp_exact_pair_refused_through_certification_ledger_owner():
    # axis: the stale `refuted` disposition is refused, never joined to the new short-title finding
    long, short, bare, minted = _clamp_pair()
    state = {"schemaVersion": 5, "dispositionLedgerOwner": "ledger",
             "dispositionLedger": [_legacy_row(long, bare)], "findings": [dict(short)],
             "_records": []}
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    _assert_collision(refusal, bare, minted)


def test_clamp_exact_pair_refused_through_certification_legacy_branch():
    # axis: the same refusal on the branch with no ledger owner
    long, short, bare, minted = _clamp_pair()
    state = {"schemaVersion": 5, "dispositionLedger": [_legacy_row(long, bare)],
             "findings": [dict(short)], "_records": []}
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    _assert_collision(refusal, bare, minted)


def test_same_finding_duplicate_under_bare_key_admitted():
    # axis: a legacy row and its own bare-keyed copy are one claimant — admitted, disposition joined
    long, _short, bare, _minted = _clamp_pair()
    live = dict(long, **{SC.FINDING_KEY_FIELD: bare})
    assert SC.legacy_key_collision([_legacy_row(long, bare), live]) is None
    state = {"schemaVersion": 5, "dispositionLedgerOwner": "ledger",
             "dispositionLedger": [_legacy_row(long, bare)], "findings": [live], "_records": []}
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    assert by_key[bare]["disposition"] == "refuted"


def test_key_writer_and_certifier_agree_on_the_bare_key():
    # axis: the writer keeps a legacy bare key exactly when certification admits it — one rule
    long, short, bare, minted = _clamp_pair()
    cases = {
        "clamp-exact pair": [_legacy_row(long, bare), dict(short)],
        "same-finding copy": [_legacy_row(long, bare), dict(long, **{SC.FINDING_KEY_FIELD: bare})],
        "legacy alone": [_legacy_row(long, bare)],
    }
    for name, rows in cases.items():
        written = RD._mint_finding_keys([dict(r) for r in rows])
        writer_keeps_bare = written[0][SC.FINDING_KEY_FIELD] == bare
        certifier_admits = SC.legacy_key_collision(rows) is None
        assert writer_keeps_bare == certifier_admits, name
    assert SC.legacy_key_collision(cases["clamp-exact pair"]) == (bare, minted)


# --- gate-policy follow-up: the write path and the resolved action ---------------------------------

def _judgment_policy(disposition, follow_up):
    cls = sorted(RGP.judgment_finding_classes())[0]
    return cls, {"schema": RGP.GATE_POLICY_SCHEMA, "default": "park",
                 "rules": [{"gate": RGP.GATE_PRESENT_JUDGMENT, "findingClass": cls,
                            "disposition": disposition, "followUp": follow_up}]}


def test_write_path_names_follow_up_not_allowed():
    # axis: validate_policy_for_write's allow-list leg names the rule, not the coarse layer token
    _cls, policy = _judgment_policy("fix-as-suggested", dict(_WELL_FORMED))
    assert RGP.validate_policy_for_write(policy) == (
        "rules[0].followUp: not allowed for disposition 'fix-as-suggested'")


def test_resolved_judgment_action_carries_no_follow_up():
    # axis: the follow-up rides matches[].rule only — action.dispositions has no second copy
    cls, policy = _judgment_policy("skip", dict(_WELL_FORMED))
    raw = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    overlay = {"identity": {"source": "calibration/test.json", "schema": RGP.GATE_POLICY_SCHEMA,
                            "sha256": hashlib.sha256(raw).hexdigest()},
               "policy": policy}
    result = RGP.resolve_judgment([{"findingClass": cls, "id": "a"}], overlay)
    assert result["action"] == {"dispositions": [{"findingClass": cls, "disposition": "skip"}]}
    assert result["matches"][0]["rule"]["followUp"] == _WELL_FORMED
