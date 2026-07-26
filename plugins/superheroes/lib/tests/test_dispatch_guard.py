import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "dispatch_guard.py")
_MR_MOD = os.path.join(_HERE, "..", "model_registry.py")


def _load_dispatch_guard():
    spec = importlib.util.spec_from_file_location("dispatch_guard", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_model_registry():
    spec = importlib.util.spec_from_file_location("model_registry", _MR_MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DG = _load_dispatch_guard()
MR = _load_model_registry()

_PARK_TAIL = (
    "an unlisted model is a park, not a pick (#600). "
    "Pick a listed model or amend lib/model_registry.py."
)

_FORBIDDEN_LITERALS = (
    "composer-2.5",
    "cursor-grok",
    "gpt-5.6",
    "gpt-5.3",
    "haiku",
    "sonnet",
    "opus",
    "gpt-4",
    "fable",
)


def test_we511_shape_parks():
    result = DG.validate("implementer", "cursor", "gpt-5.3-codex-high")
    assert result["ok"] is False
    assert "gpt-5.3-codex-high" in result["reason"]
    assert "composer-2.5" in result["allowlist"]
    assert "cursor-grok-4.5-high" in result["allowlist"]
    assert result["resolved_model"] is None


def test_listed_models_pass():
    r1 = DG.validate("implementer", "cursor", "composer-2.5")
    assert r1["ok"] is True
    assert r1["resolved_model"] == "composer-2.5"

    r2 = DG.validate("implementer", "cursor", "cursor-grok-4.5-high")
    assert r2["ok"] is True
    assert r2["resolved_model"] == "cursor-grok-4.5-high"

    r3 = DG.validate("implementer", "codex", "gpt-5.6-terra")
    assert r3["ok"] is True
    assert r3["resolved_model"] == "gpt-5.6-terra"


def test_registry_model_id_form_passes():
    result = DG.validate("implementer", "cursor", "cursor-grok-4.5", "high")
    assert result["ok"] is True
    assert result["resolved_model"] == "cursor-grok-4.5-high"


def test_defaulted_resolves_to_listed():
    r1 = DG.validate("implementer", "cursor", None)
    assert r1["ok"] is True
    assert r1["resolved_model"] == "composer-2.5"

    r2 = DG.validate("implementer", "codex", None)
    assert r2["ok"] is True
    assert r2["resolved_model"] == "gpt-5.6-terra"


def test_registered_role_with_no_model_on_vendor_parks():
    result = DG.validate("synthesis", "codex", None)
    assert result["ok"] is False
    assert "no sanctioned model" in result["reason"]


def test_non_str_role_parks_with_role_reason():
    result = DG.validate(123, "cursor", "composer-2.5")
    assert result["ok"] is False
    assert "is not a string" in result["reason"]


def test_unknown_role_parks_with_role_reason():
    result = DG.validate("bogus-role", "cursor", "composer-2.5")
    assert result["ok"] is False
    assert "unknown role" in result["reason"]


def test_unknown_vendor_parks():
    result = DG.validate("implementer", "openai", "x")
    assert result["ok"] is False
    assert "unknown vendor" in result["reason"]


def test_off_allowlist_effort_parks():
    result = DG.validate("implementer", "cursor", "cursor-grok-4.5", "low")
    assert result["ok"] is False
    assert "cursor-grok-4.5" in result["reason"]
    assert result["allowlist"]


def test_non_str_model_parks():
    result = DG.validate("implementer", "cursor", 123)
    assert result["ok"] is False
    assert result["allowlist"]
    assert "not on the" in result["reason"]


@pytest.mark.parametrize(
    "role,vendor",
    [(role, vendor) for role in MR.roles() for vendor in MR.vendors()],
)
def test_allowlist_is_derived_not_shadowed_pair(role, vendor):
    result = DG.validate(role, vendor, "__nope__")
    expected = {
        MR.dispatch_token(vendor, m, e)
        for m, e in MR.allowlist(role, vendor)
        if MR.dispatch_token(vendor, m, e) is not None
    }
    assert set(result["allowlist"]) == expected


def test_allowlist_is_derived_not_shadowed_source_scan():
    with open(_MOD, encoding="utf-8") as fh:
        source = fh.read()
    for literal in _FORBIDDEN_LITERALS:
        assert literal not in source, (
            f"dispatch_guard.py must not hardcode model literal {literal!r}"
        )


def test_cli_park_exits_1_and_names_allowlist():
    proc = subprocess.run(
        [
            sys.executable,
            _MOD,
            "check",
            "--role",
            "implementer",
            "--vendor",
            "cursor",
            "--model",
            "gpt-5.3-codex-high",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert "composer-2.5" in payload["allowlist"]
    assert proc.stderr.strip()


def test_cli_pass_exits_0():
    proc = subprocess.run(
        [
            sys.executable,
            _MOD,
            "check",
            "--role",
            "implementer",
            "--vendor",
            "cursor",
            "--model",
            "composer-2.5",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["resolved_model"]


def _assert_success_triple(payload):
    assert payload["ok"] is True
    assert payload["resolved_model"] == payload["dispatch_token"]
    assert payload["model_id"] is not None
    assert payload["dispatch_token"] is not None
    assert payload["effort_source"] is not None
    assert isinstance(payload["allowlist_pairs"], list)
    json.dumps(payload)


def test_issue_636_reviewer_deep_cursor_bare_registry_id():
    result = DG.validate("reviewer-deep", "cursor", "cursor-grok-4.5")
    assert result["ok"] is True
    assert result["model_id"] == "cursor-grok-4.5"
    assert result["effort"] == "high"
    assert result["dispatch_token"] == "cursor-grok-4.5-high"
    assert result["resolved_model"] == "cursor-grok-4.5-high"
    assert result["effort_source"] == "resolved-unique"
    _assert_success_triple(result)


def test_structured_triple_success_all_vendors():
    r_cursor = DG.validate("reviewer-deep", "cursor", "cursor-grok-4.5")
    _assert_success_triple(r_cursor)
    assert r_cursor["model_id"] == "cursor-grok-4.5"

    r_codex = DG.validate("brief-check", "codex", None)
    _assert_success_triple(r_codex)
    assert r_codex["model_id"] == "gpt-5.6-sol"
    assert r_codex["effort"] == "xhigh"
    assert r_codex["dispatch_token"] == "gpt-5.6-sol"

    r_claude = DG.validate("reviewer", "claude", "sonnet")
    _assert_success_triple(r_claude)
    assert r_claude["model_id"] == "sonnet-5"
    assert r_claude["effort"] == "high"
    assert r_claude["dispatch_token"] == "sonnet"


def test_opus_resolves_lowest_rung():
    result = DG.validate("reviewer", "claude", "opus")
    assert result["ok"] is True
    assert result["model_id"] == "opus-4.8"
    assert result["effort"] == "high"
    assert result["effort_source"] == "resolved-lowest-rung"
    _assert_success_triple(result)


def test_effort_source_given():
    result = DG.validate("implementer", "cursor", "cursor-grok-4.5", "high")
    assert result["ok"] is True
    assert result["effort_source"] == "given"


def test_effort_source_token_encoded():
    result = DG.validate("implementer", "cursor", "cursor-grok-4.5-high")
    assert result["ok"] is True
    assert result["effort_source"] == "token-encoded"


def test_effort_source_seat_default():
    result = DG.validate("implementer", "cursor", None)
    assert result["ok"] is True
    assert result["effort_source"] == "seat-default"
    assert result["model_id"] == "composer-2.5"
    assert result["effort"] is None


def test_allowlist_pairs_matches_registry():
    result = DG.validate("implementer", "cursor", None)
    expected = [[m, e] for m, e in MR.allowlist("implementer", "cursor")]
    assert result["allowlist_pairs"] == expected
    assert ["composer-2.5", None] in result["allowlist_pairs"]


def test_park_payload_has_full_key_set():
    result = DG.validate("implementer", "unknown-vendor", "x")
    keys = {
        "ok",
        "role",
        "vendor",
        "model_id",
        "effort",
        "dispatch_token",
        "effort_source",
        "resolved_model",
        "allowlist",
        "allowlist_pairs",
        "reason",
    }
    assert set(result) == keys
    assert result["allowlist_pairs"] == []


def test_fail_closed_edge_1_non_str_role():
    result = DG.validate(123, "cursor", "composer-2.5")
    assert result["ok"] is False
    assert result["allowlist"] == []
    assert result["allowlist_pairs"] == []
    assert _PARK_TAIL not in result["reason"]


def test_fail_closed_edge_2_unknown_vendor():
    result = DG.validate("implementer", "openai", "x")
    assert result["ok"] is False
    assert result["allowlist"] == []
    assert _PARK_TAIL not in result["reason"]


def test_fail_closed_edge_3_unknown_role():
    result = DG.validate("bogus-role", "cursor", "composer-2.5")
    assert result["ok"] is False
    assert result["allowlist"] == []
    assert _PARK_TAIL not in result["reason"]


def test_fail_closed_edge_4_no_sanctioned_model_on_vendor():
    result = DG.validate("synthesis", "codex", None)
    assert result["ok"] is False
    assert result["allowlist"] == []
    assert "no sanctioned model" in result["reason"]
    assert _PARK_TAIL not in result["reason"]


def test_fail_closed_edge_5_non_str_model():
    result = DG.validate("implementer", "cursor", 123)
    assert result["ok"] is False
    assert _PARK_TAIL in result["reason"]


def test_fail_closed_edge_6_unparseable_model():
    result = DG.validate("implementer", "cursor", "__nope__")
    assert result["ok"] is False
    assert _PARK_TAIL in result["reason"]


def test_fail_closed_edge_7_wrong_seat_allowlist():
    result = DG.validate("reviewer-deep", "cursor", "composer-2.5")
    assert result["ok"] is False
    assert _PARK_TAIL in result["reason"]


def test_fail_closed_edge_8_effort_not_on_pair():
    result = DG.validate("implementer", "cursor", "cursor-grok-4.5", "low")
    assert result["ok"] is False
    assert _PARK_TAIL in result["reason"]


def test_fail_closed_edge_9_token_effort_conflict():
    result = DG.validate(
        "implementer", "cursor", "cursor-grok-4.5-high", "low"
    )
    assert result["ok"] is False
    assert _PARK_TAIL in result["reason"]
    assert "conflicts" in result["reason"]


def test_fail_closed_edge_10_model_none_seat_default():
    result = DG.validate("implementer", "cursor", None)
    assert result["ok"] is True
    assert result["effort_source"] == "seat-default"


def test_fail_closed_edge_11_override_only_fable():
    result = DG.validate("implementer", "claude", "fable")
    assert result["ok"] is False
    assert result["resolved_model"] is None
    assert _PARK_TAIL in result["reason"]
