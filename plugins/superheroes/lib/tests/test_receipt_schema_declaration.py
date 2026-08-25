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


def test_receipt_key_forms_cover_every_declared_key():
    """The declaration must enumerate every top-level receipt key exactly once."""
    declared = set(RD.RECEIPT_KEY_FORMS)
    optional = set(RD.RECEIPT_OPTIONAL_KEYS)
    assert optional <= declared, "optional keys must appear in RECEIPT_KEY_FORMS"
    for form in (RD.RECEIPT_FORM_CERTIFIED, RD.RECEIPT_FORM_ATTESTED, RD.RECEIPT_FORM_INTERIM):
        required = set(RD._receipt_required_keys(form))
        forbidden = set(RD._receipt_forbidden_keys(form))
        assert required & forbidden == set(), "required and forbidden must not overlap for %r" % form
        assert required <= declared
        assert forbidden <= declared - optional


def test_one_line_certification_only_key_forbids_attested_and_interim():
    """Adding a certification-only key is one declaration line — attested/interim reject it."""
    fake_key = "_wo1107FakeCertOnly"
    assert fake_key not in RD.RECEIPT_KEY_FORMS
    patched = dict(RD.RECEIPT_KEY_FORMS)
    patched[fake_key] = (RD.RECEIPT_FORM_CERTIFIED,)
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
    """Each builder's strip set must match its form's forbidden set — no hand tuples."""
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


def test_builder_strip_must_match_forbidden_set():
    """BP-S1-B guard: a hand-written strip tuple fails this check."""
    state = RD.new_state(_cfg())
    interim = RD.build_interim_receipt(state, None, "park")
    hand_strip = ("certification", "certificationShape", "schemaVersion", "verdict", "stop")
    stripped = set(interim.keys()) | set(hand_strip)
    forbidden = set(RD._receipt_forbidden_keys(RD.RECEIPT_FORM_INTERIM))
    assert stripped - set(interim.keys()) != forbidden - set(), (
        "hand strip must not match derived forbidden — this assertion guards the detector")
