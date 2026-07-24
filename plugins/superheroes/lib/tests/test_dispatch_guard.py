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
