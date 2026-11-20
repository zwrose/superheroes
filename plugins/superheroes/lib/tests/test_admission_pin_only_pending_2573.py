"""#2573: pending admission applies to ladder and pin-only models alike."""
import copy
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import dispatch_allowlist as DA  # noqa: E402
import model_registry as MR  # noqa: E402


# bite-axis: a probe-pending model is excluded from reviewer-deep's allowlist and refused by its dispatch guard, whether reached through the ladder or pin-only append; removing the admission mark admits the same model and effort.
@pytest.mark.parametrize(
    ("model_id", "effort"),
    [
        ("gpt-6.2-astra", "high"),
        ("gpt-6-astra", "high"),
        ("gpt-6.1-sol", "xhigh"),
    ],
)
def test_pending_admission_blocks_every_allowlist_path(monkeypatch, model_id, effort):
    models = copy.deepcopy(MR._MODELS)
    models["codex"][model_id]["registration"] = "probe-pending"
    monkeypatch.setattr(MR, "_MODELS", models)

    ok, reason = MR.codex_pin_verdict("reviewer-deep", model_id)
    assert ok is False
    assert reason.startswith("pin-probe-pending:")
    held = DA.validate("reviewer-deep", "codex", model_id, effort)
    assert held["ok"] is False, held
    assert all(model != model_id for model, _ in MR.allowlist("reviewer-deep", "codex"))

    del models["codex"][model_id]["registration"]

    admitted = DA.validate("reviewer-deep", "codex", model_id, effort)
    assert admitted["ok"] is True, admitted
    assert admitted["model_id"] == model_id
    assert admitted["effort"] == effort
