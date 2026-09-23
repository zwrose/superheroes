"""#1272 layer 2e WO-B2: gate-policy rules may carry a validated followUp."""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TDI)

_fake_git = _TDI._fake_git

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
SEAT_MAP = {"seats": {dim: {"vendor": "claude", "model": "sonnet-5", "engine": "claude"}
                      for dim in ("architecture-reviewer", "code-reviewer", "security-reviewer",
                                  "test-reviewer", "premortem-reviewer")}}

_WELL_FORMED = {
    "item": "defer auth redesign",
    "revisitTrigger": "when #1300 lands",
    "classClosure": "tracked separately",
}


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RC = _load("round_certification")
SC = _load("session_contract")
RGP = _load("review_gate_policy")


def _load_core_md():
    path = os.path.join(_LIB, "core_md.py")
    spec = importlib.util.spec_from_file_location("core_md_gate_follow_up", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude",
            "seatMap": SEAT_MAP, "baseGuard": RC.BASE_GUARD_CHECKED}
    base.update(over)
    return base


class FakeAdapters(object):
    ADAPTER_PHASES = (RD.P_PANEL, RD.P_VERIFIERS, RD.P_SYNTHESIS, RD.P_GAPSWEEP, RD.P_AUDITS,
                      RD.P_SCOPED, RD.P_VERIFY, RD.P_FIXER)

    def __init__(self):
        self.rosters = {RD.P_PANEL: list(RD.DIMENSIONS),
                        RD.P_VERIFIERS: [],
                        RD.P_SYNTHESIS: ["synthesis"],
                        RD.P_FIXER: ["dispatch-fixer"],
                        RD.P_VERIFY: ["verify"]}
        self.roster_reasons = {}
        self.faults = {}
        self.assemble_reason = None
        self.assembled = []
        self.policies = {}

    def roster_for(self, phase, state, config):
        if phase in self.roster_reasons:
            return [], self.roster_reasons[phase]
        return list(self.rosters.get(phase, [])), None

    def payload_fault(self, phase, payload, seat_key, record_boundary=False):
        return self.faults.get(seat_key)

    def missing_policy(self, phase):
        return self.policies.get(phase, "seat-status")

    def is_orchestrator_fulfilled(self, phase):
        return phase in (RD.P_VERIFY,)

    def orchestrator_payload_fault(self, phase, payload):
        if phase == RD.P_VERIFY:
            return RD.verify_result_fault(payload)
        return "orchestrator-payload-unknown-phase:%s" % phase

    def assemble(self, phase, envelopes, state, config, dispatch_manifest=None, canary=None,
                 session_dir=None):
        if self.assemble_reason:
            return None, self.assemble_reason
        return list(self.assembled), None


@pytest.fixture
def adapters(monkeypatch):
    fake = FakeAdapters()
    monkeypatch.setitem(sys.modules, "round_adapters", fake)
    return fake


def _gitdir(tmp_path):
    return str(tmp_path / "gitdir")


def _advance(d, tmp_path, **kw):
    return RD.cmd_advance(d, git=_fake_git(_gitdir(tmp_path)), **kw)


def _state(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok, state
    return state


def _session(tmp_path, name="s", **cfg_over):
    d = str(tmp_path / name)
    os.makedirs(d, exist_ok=True)
    out = RD.cmd_next(d, _cfg(**cfg_over))
    assert out["ok"], out
    return d


def _overlay(policy, *, source="calibration/test.json"):
    raw = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "identity": {
            "source": source,
            "schema": RGP.GATE_POLICY_SCHEMA,
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "policy": policy,
    }


def _repo_with_gate_policy(tmp_path, rules):
    cm = _load_core_md()
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    facts = {"verifyCommand": "none", "stackTags": [], "threatModel": "", "patterns": ""}
    in_repo = os.path.join(repo, ".claude", "superheroes", "core.md")
    os.makedirs(os.path.dirname(in_repo), exist_ok=True)
    with open(in_repo, "w", encoding="utf-8") as fh:
        fh.write(cm.render_core(facts, "confirmed", "2026-01-01", "2026-01-01"))
    policy = {"schema": "gate-policy/1", "default": "park", "rules": rules}
    assert cm.write_review_gate_policy(repo, policy, root=None)["action"] == "written"
    return repo


def _parked_at_owner_gate(tmp_path, adapters, phase, name=None):
    label = name or ("park-" + phase)
    d = _session(tmp_path, name=label)
    state = _state(d)
    state["step"] = phase
    state["pending"] = {"action": phase, "round": 1, "phase": phase, "attempt": 0, "payload": {}}
    if phase == RD.P_JUDGMENT:
        state["_judgmentFindings"] = [
            {"title": "widen the API", "severity": "Important", "file": "f.py", "line": 1,
             "tradeoff": True}]
        state["_judgmentMechanical"] = []
    if phase == RD.P_STALL:
        state["_stallChoices"] = list(RD.STALL_CHOICES)
        state["_acceptRiskEligible"] = False
    RD.save_state(d, state)
    return d


def _judgment_session_with_repo(tmp_path, adapters, repo, name="judgment"):
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_JUDGMENT, name=name)
    state = _state(d)
    state["config"]["repoRoot"] = repo
    RD.save_state(d, state)
    return d


def _ledger_by_key(state):
    return {SC.finding_identity_key(e): e
            for e in (state.get("dispositionLedger") or []) if isinstance(e, dict)}


_CONFIRMED_STALL_TARGET = {"id": "v0", "title": "bug", "severity": "Important", "file": "f.py",
                           "line": 1, "verdict": "CONFIRMED", "evidence": "tests pass"}


def test_e1_judgment_skip_follow_up_loads_and_folds(tmp_path, adapters):
    # axis: e1 — valid followUp on judgment skip folds and certifies
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
        "followUp": dict(_WELL_FORMED),
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo)
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    # the rule's followUp reaches the fold through matches[].rule only, never action.dispositions
    assert out["policyApplied"]["action"]["dispositions"] == [
        {"findingClass": "judgment:important", "disposition": "skip"}]
    assert out["policyApplied"]["matches"][0]["rule"]["followUp"] == _WELL_FORMED
    state = _state(d)
    assert state["terminal"] == "converged"
    entries = list(_ledger_by_key(state).values())
    assert len(entries) == 1
    assert entries[0].get("followUp") == _WELL_FORMED
    assert SC.follow_up_shape_fault(entries[0].get("followUp")) is None


def test_e2_stall_accept_risk_follow_up_loads_and_folds(tmp_path, adapters):
    # axis: e2 — valid followUp on stall accept-risk folds and certifies
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-stall-menu",
        "findingClass": "stall:accept-risk-eligible",
        "disposition": "accept-the-disclosed-risk",
        "followUp": dict(_WELL_FORMED),
    }])
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_STALL)
    state = _state(d)
    state["config"]["repoRoot"] = repo
    state["_acceptRiskEligible"] = True
    state["_stallTargets"] = [dict(_CONFIRMED_STALL_TARGET)]
    RD.save_state(d, state)
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    assert out["policyApplied"]["action"].get("followUp") == _WELL_FORMED
    state = _state(d)
    assert state["terminal"] == "converged"
    entries = list(_ledger_by_key(state).values())
    assert len(entries) == 1
    assert entries[0].get("followUp") == _WELL_FORMED
    assert SC.follow_up_shape_fault(entries[0].get("followUp")) is None


def test_e3_follow_up_item_less_refused_at_load_and_write():
    # axis: e3 — item-less followUp refused for new gate-policy rules
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "skip",
            "followUp": {"revisitTrigger": "later", "classClosure": "none"},
        }],
    }
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["ok"] is False
    assert loaded["reason"] == "layer-follow-up-malformed"
    refusal = RGP.validate_policy_for_write(policy)
    assert refusal is not None and "rules[0].followUp" in refusal


def test_e3b_follow_up_present_empty_item_refused_at_load_and_write():
    # axis: e3b — present-but-empty item refused at load and write
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "skip",
            "followUp": {"item": "", "revisitTrigger": "later", "classClosure": "none"},
        }],
    }
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["reason"] == "layer-follow-up-malformed"
    assert loaded["ok"] is False
    refusal = RGP.validate_policy_for_write(policy)
    assert refusal is not None and "rules[0].followUp" in refusal


def test_e4_follow_up_on_judgment_fix_not_allowed():
    # axis: e4 — followUp on judgment fix rule refused
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "fix-as-suggested",
            "followUp": dict(_WELL_FORMED),
        }],
    }
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["reason"] == "layer-follow-up-not-allowed"
    assert loaded["ok"] is False


@pytest.mark.parametrize("gate,finding_class,disposition", [
    (RGP.GATE_PRESENT_JUDGMENT, sorted(RGP.judgment_finding_classes())[0], "fix-as-suggested"),
    (RGP.GATE_PRESENT_STALL_MENU, RGP.STALL_CLASS_ELIGIBLE, "hold"),
])
def test_e4b_follow_up_not_allowed_refused_at_calibration_write(gate, finding_class, disposition):
    # axis: e4b — the write path names the allow-list refusal itself, not the load token behind it
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": gate,
            "findingClass": finding_class,
            "disposition": disposition,
            "followUp": dict(_WELL_FORMED),
        }],
    }
    assert RGP.validate_policy_for_write(policy) == (
        "rules[0].followUp: not allowed for disposition %r" % disposition)


def test_e5_follow_up_on_stall_hold_not_allowed():
    # axis: e5 — followUp on stall hold rule refused
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_STALL_MENU,
            "findingClass": RGP.STALL_CLASS_ELIGIBLE,
            "disposition": "hold",
            "followUp": dict(_WELL_FORMED),
        }],
    }
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["ok"] is False
    assert loaded["reason"] == "layer-follow-up-not-allowed"


def test_e6_null_follow_up_malformed():
    # axis: e6 — followUp null refused as malformed
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "skip",
            "followUp": None,
        }],
    }
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["ok"] is False
    assert loaded["reason"] == "layer-follow-up-malformed"


def test_e7_rule_without_follow_up_normalizes_unchanged():
    # axis: e7 — rule without followUp normalizes exactly as before
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "skip",
        }],
    }
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["ok"] is True
    rule = loaded["layer"]["rules"][0]
    assert rule == {
        "gate": RGP.GATE_PRESENT_JUDGMENT,
        "findingClass": cls,
        "disposition": "skip",
    }
    assert "followUp" not in rule


def test_e8_invalid_overlay_follow_up_falls_back_to_shipped_default(tmp_path, adapters):
    # axis: e8 — refused overlay with followUp on fix falls back to shipped default (park)
    cls = sorted(RGP.judgment_finding_classes())[0]
    cm = _load_core_md()
    repo = str(tmp_path / "repo-invalid-overlay")
    os.makedirs(repo)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    facts = {"verifyCommand": "none", "stackTags": [], "threatModel": "", "patterns": ""}
    in_repo = os.path.join(repo, ".claude", "superheroes", "core.md")
    os.makedirs(os.path.dirname(in_repo), exist_ok=True)
    with open(in_repo, "w", encoding="utf-8") as fh:
        fh.write(cm.render_core(facts, "confirmed", "2026-01-01", "2026-01-01"))
    invalid = {
        "schema": "gate-policy/1",
        "default": "park",
        "rules": [{
            "gate": "present-judgment",
            "findingClass": cls,
            "disposition": "fix-as-suggested",
            "followUp": dict(_WELL_FORMED),
        }],
    }
    assert cm.write_review_gate_policy(repo, invalid, root=None)["action"] == "refused"
    overlay_env = _overlay(invalid, source=in_repo)
    with open(in_repo, encoding="utf-8") as fh:
        text = fh.read()
    block = cm.parse_core(text)
    block["reviewGatePolicy"] = overlay_env
    new_body = json.dumps(block, indent=2)
    new_text = re.sub(
        r"```json\n.*?\n```",
        "```json\n" + new_body + "\n```",
        text,
        count=1,
        flags=re.DOTALL,
    )
    with open(in_repo, "w", encoding="utf-8") as fh:
        fh.write(new_text)
    parsed = RGP.parse_overlay(overlay_env)
    assert parsed["ok"] is False
    assert parsed["reason"] == "layer-follow-up-not-allowed"
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="invalid-overlay")
    out = _advance(d, tmp_path)
    assert out["ok"] is False
    assert out["reason"] == "advance-judgment-park"
    assert out["detail"] == "gate-policy-unmatched-class:judgment:important"


def test_e9_layer_identity_sha256_covers_follow_up():
    # axis: e9 — changed followUp changes layer identity sha256
    cls = sorted(RGP.judgment_finding_classes())[0]
    base_rule = {
        "gate": RGP.GATE_PRESENT_JUDGMENT,
        "findingClass": cls,
        "disposition": "skip",
        "followUp": dict(_WELL_FORMED),
    }
    policy_a = {"schema": RGP.GATE_POLICY_SCHEMA, "default": "park", "rules": [base_rule]}
    policy_b = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [dict(base_rule, followUp=dict(_WELL_FORMED, item="other item"))],
    }
    a = RGP.parse_overlay(_overlay(policy_a))
    b = RGP.parse_overlay(_overlay(policy_b))
    assert a["ok"] and b["ok"]
    assert a["layer"]["identity"]["sha256"] != b["layer"]["identity"]["sha256"]
    forged = {"identity": dict(a["layer"]["identity"]), "policy": policy_b}
    out = RGP.parse_overlay(forged)
    assert out["ok"] is False, out
    assert out["reason"] == "overlay-digest-mismatch"


def test_judgment_follow_up_fault_nonlist_dispositions():
    # axis: malformed dispositions must not crash the submit chokepoint
    assert RD.judgment_follow_up_fault({"dispositions": 1}) is None
    assert RD.judgment_follow_up_fault({"dispositions": True}) is None
