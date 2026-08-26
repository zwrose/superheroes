"""Receipt schema declaration — one source of truth for top-level keys (#1107 WO-S1)."""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"],
            "diff": "diff --git a/f.py b/f.py\n", "fixerVendor": "claude"}
    base.update(over)
    return base


def _certified_spine():
    return {
        "schemaVersion": 3,
        "verdict": "converged",
        "certificationShape": "audited-chain",
        "certification": {"shape": "audited-chain"},
        "scriptRan": {"byPhase": {}},
        "seatMap": {},
        "rounds": [],
        "findings": [],
        "decisions": [],
        "degraded": [],
        "skippedBlockers": [],
    }


def test_receipt_key_forms_cover_every_declared_key():
    """The declaration must enumerate every top-level receipt key exactly once."""
    declared = set(RD.RECEIPT_KEY_FORMS)
    for form in RD._ALL_RECEIPT_FORMS:
        required = set(RD._receipt_required_keys(form))
        optional = set(RD._receipt_optional_keys(form))
        forbidden = set(RD._receipt_forbidden_keys(form))
        assert required & forbidden == set(), "required and forbidden must not overlap for %r" % form
        assert optional & forbidden == set(), "optional and forbidden must not overlap for %r" % form
        assert required & optional == set(), "required and optional must not overlap for %r" % form
        assert required | optional | forbidden == declared


def _representative_receipt_state(session_dir="/tmp"):
    state = RD.new_state(_cfg(repoRoot=session_dir))
    state["terminal"] = "converged"
    state["certification"] = {"shape": "audited-chain"}
    state["rounds"] = {
        "1": {
            "roundKind": "panel",
            "seatStatus": {},
            "blockingCount": 0,
            "verifyResult": "pass",
            "verifyPasses": [{"cluster": "c0"}],
            "lensCoverage": {"ran": 5, "expected": 5, "floor": 5},
        },
    }
    state["findings"] = [{"id": "f1", "file": "a.py", "line": 1, "title": "t",
                          "severity": "Nit", "verdict": "open"}]
    state["decisions"] = [{"kind": "test"}]
    state["seatMap"] = {"code-reviewer": "claude"}
    state["_policyApplied"] = [{"policy": "stall-accept-risk"}]
    cfg = state["config"]
    cfg["baseRef"] = "abc123"
    cfg["baseGuard"] = RD.BASE_GUARD_CHECKED
    return state


def test_receipt_key_forms_match_builder_emission():
    """BP-A2: every builder-emitted top-level key is declared, and every certified/interim key is emitted."""
    state = _representative_receipt_state()
    declared = set(RD.RECEIPT_KEY_FORMS)
    certified = set(RD.build_receipt(state, "/tmp").keys())
    interim = set(RD.build_interim_receipt(state, "/tmp", "park").keys())
    emitted = certified | interim
    assert certified <= declared, "certified keys not declared: %s" % sorted(certified - declared)
    assert interim <= declared, "interim keys not declared: %s" % sorted(interim - declared)
    certified_interim_declared = {
        key for key, forms in RD.RECEIPT_KEY_FORMS.items()
        if RD.RECEIPT_FORM_CERTIFIED in forms or RD.RECEIPT_FORM_INTERIM in forms
    }
    assert emitted == certified_interim_declared, (
        "certified/interim declared/ emitted mismatch — only in declared: %s; only in emitted: %s"
        % (sorted(certified_interim_declared - emitted), sorted(emitted - certified_interim_declared)))


def test_certified_receipt_with_schema_validates():
    """BP-R1-A pin: certified receipts carrying schema (legacy shape) must pass validate_receipt."""
    receipt = dict(_certified_spine())
    receipt["schema"] = RD.RECEIPT_CERTIFIED_SCHEMA % 3
    ok, reason = RD.validate_receipt(receipt)
    assert ok is True, reason


def test_certified_optional_schema_and_forbidden_attestation():
    """BP-R1-B: optional schema is not forbidden; attestation remains forbidden on certified."""
    without_schema = dict(_certified_spine())
    ok, reason = RD.validate_receipt(without_schema)
    assert ok is True, reason

    with_attestation = dict(_certified_spine())
    with_attestation["attestation"] = {"by": "owner"}
    ok, reason = RD.validate_receipt(with_attestation)
    assert ok is False, reason
    assert "attestation" in reason


def test_one_line_certification_only_key_forbids_attested_and_interim():
    """Adding a certification-only key is one declaration line — attested/interim reject it."""
    fake_key = "_wo1107FakeCertOnly"
    assert fake_key not in RD.RECEIPT_KEY_FORMS
    patched = dict(RD.RECEIPT_KEY_FORMS)
    patched[fake_key] = {RD.RECEIPT_FORM_CERTIFIED: RD.RECEIPT_KEY_REQUIRED}
    original = RD.RECEIPT_KEY_FORMS
    RD.RECEIPT_KEY_FORMS = patched
    try:
        attested = RD.build_attestation_receipt("/tmp", RD.new_state(_cfg()), {"ref": "1"}, "note")
        attested["artifacts"] = {"session/x": "abc"}
        attested["roster"] = {"test-reviewer": "recorded"}
        attested[fake_key] = True
        ok, reason = RD.validate_receipt(attested)
        assert ok is False, reason
        assert fake_key in reason

        interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "park")
        interim[fake_key] = True
        ok, reason = RD.validate_receipt(interim)
        assert ok is False, reason
        assert fake_key in reason
    finally:
        RD.RECEIPT_KEY_FORMS = original


def test_builders_strip_exactly_forbidden_keys():
    """Each builder's output must not carry forbidden keys for its form."""
    state = RD.new_state(_cfg())
    state["terminal"] = "halted"
    state["certification"] = {"shape": None, "reason": "test"}

    certified = RD.build_receipt(state)
    assert set(RD._receipt_forbidden_keys(RD.RECEIPT_FORM_CERTIFIED)) & set(certified) == set()

    interim = RD.build_interim_receipt(state, None, "tripwire")
    forbidden_interim = set(RD._receipt_forbidden_keys(RD.RECEIPT_FORM_INTERIM))
    assert forbidden_interim & set(interim) == set()
    assert "schema" in interim and "stop" in interim

    attested = RD.build_attestation_receipt("/tmp", state, {"ref": "1"}, "note")
    forbidden_attested = set(RD._receipt_forbidden_keys(RD.RECEIPT_FORM_ATTESTED))
    assert forbidden_attested & set(attested) == set()
    assert "schema" in attested and "attestation" in attested


def _builder_strip_set(form, state, session_dir="/tmp"):
    """Keys removed by the form's builder relative to build_receipt's pre-strip output."""
    pre = RD.build_receipt(state, session_dir, form=form)
    if form == RD.RECEIPT_FORM_CERTIFIED:
        post = RD.build_receipt(state, session_dir, form=form)
    elif form == RD.RECEIPT_FORM_INTERIM:
        post = RD.build_interim_receipt(state, session_dir, "park")
    elif form == RD.RECEIPT_FORM_ATTESTED:
        post = RD.build_attestation_receipt(session_dir, state, {"ref": "1"}, "note")
    else:
        raise ValueError(form)
    return set(pre.keys()) - set(post.keys())


def test_builder_strip_must_match_forbidden_set():
    """BP-R1-C: each builder strips exactly the forbidden keys present in the pre-strip output."""
    state = RD.new_state(_cfg())
    state["terminal"] = "halted"
    state["certification"] = {"shape": None, "reason": "test"}

    for form in RD._ALL_RECEIPT_FORMS:
        forbidden = set(RD._receipt_forbidden_keys(form))
        pre = RD.build_receipt(state, "/tmp", form=form)
        if form == RD.RECEIPT_FORM_CERTIFIED:
            assert forbidden & set(pre.keys()) == set()
            continue
        if form == RD.RECEIPT_FORM_INTERIM:
            post = RD.build_interim_receipt(state, "/tmp", "park")
        elif form == RD.RECEIPT_FORM_ATTESTED:
            post = RD.build_attestation_receipt("/tmp", state, {"ref": "1"}, "note")
        else:
            raise ValueError(form)
        stripped = set(pre.keys()) - set(post.keys())
        assert stripped == forbidden & set(pre.keys()), (
            "form %r: stripped %s != forbidden & pre %s"
            % (form, sorted(stripped), sorted(forbidden & set(pre.keys()))))
        assert forbidden & set(post.keys()) == set()
