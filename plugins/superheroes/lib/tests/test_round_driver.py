"""Tests for `round_driver` — the ONE-entrypoint review-loop round driver (#507).

The driver collapses review-code's per-round script choreography into ONE entrypoint so the
mandated path is the easiest path. These pin BOTH layers over the shared core:

  - Layer 2 (next/submit CLI): the state-machine protocol — echo validation (stale attempt /
    hash mismatch rejected, exact-duplicate idempotent), v1-state refusal, per-call journalling.
  - Layer 1 (run_loop): the ported run-shape driven end-to-end with scripted seams.

Ported invariants from the retired test_code_loop_plan.py (round-1 full-deep baseline; the #174
confirmation economics incl. cap-parks-on-Critical; fail-toward-run-all on an unknown surface;
exits only off a qualifying round — now also expressible as an audited-chain certification), plus
the new #507 mechanics: audit-keyed stall + self-recovery + stall menu, delta rounds, degraded
independence, receipt-missing seats carried unverified, the author-justification POST-filter, and
the driver receipt + its validator.
"""
import importlib.util
import hashlib
import inspect
import json
import os
import re
import subprocess

import pytest

from source_access_scan import source_obj_accesses_key

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
LPC = _load("loop_plan_common")
FI = _load("finding_identity")

# --- diffs --------------------------------------------------------------------

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
HEAD = ("diff --git a/f.py b/f.py\nindex 2..3 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,3 @@\n-old\n+new\n+more\n+fixed\n")


def _headf(n):
    return ("diff --git a/f.py b/f.py\nindex 2..3 100644\n--- a/f.py\n+++ b/f.py\n"
            "@@ -1 +1,%d @@\n-old\n+new\n" % (n + 2)) + "".join("+z%d\n" % i for i in range(n))


# A brand-new file section — a genuinely-new surface (no fix batch line sits over it). Appended to a
# post-fix head diff so a delta round's scoped finder has a real surface to scan: post #507-WO-R2b an
# EMPTY new surface SKIPS the scoped dispatch, so a test that exercises the scoped finder must offer
# it one. The audited hunk (over the fixed line 1) stays an audit target; this is the new surface.
def _newsurf(tag=""):
    return ("diff --git a/newsurf.py b/newsurf.py\nindex 0..1 100644\n--- a/newsurf.py\n"
            "+++ b/newsurf.py\n@@ -0,0 +1,2 @@\n+ns%s\n+ns2\n" % tag)


HEAD_NEW_SURFACE = HEAD + _newsurf()


def _headf_ns(n):
    return _headf(n) + _newsurf(str(n))


def _big_diff(n_files=25):
    return "".join(
        "diff --git a/f%d.py b/f%d.py\nindex 1..2 100644\n--- a/f%d.py\n+++ b/f%d.py\n"
        "@@ -1 +1 @@\n-a\n+b\n" % (i, i, i, i) for i in range(n_files))


# --- default scripted seams ---------------------------------------------------

def _seams(reviewer=None, verifier=None, synthesis=None, auditor=None, fix_step=None,
           verify_runner=None, io=None):
    def default_reviewer(dim, tier, rnd, ctx):
        return []

    def default_verifier(clusters, rnd):
        return [{"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                for c in (clusters or []) for i in (c.get("ids") or [])]

    def default_synthesis(findings, rnd):
        return None

    def default_auditor(targets, rnd):
        # Echo the selected independent auditor vendor so the discharge passes the provenance gate.
        return [{"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                 "evidence": "tests pass", "auditorVendor": t.get("auditorVendor")}
                for t in (targets or [])]

    def default_fix(batch, rnd, payload):
        return {"fixes": [], "headDiff": HEAD, "changedSubjects": ["Code"]}

    def default_verify(command, rnd):
        return "pass"

    return {
        "reviewer": reviewer or default_reviewer,
        "verifier": verifier or default_verifier,
        "synthesis": synthesis or default_synthesis,
        "auditor": auditor or default_auditor,
        "fix_step": fix_step or default_fix,
        "verify_runner": verify_runner or default_verify,
        "io": io or {},
    }


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude"}
    base.update(over)
    return base


# =============================================================================
# Layer 2 — next/submit protocol
# =============================================================================

def _first_next(session_dir, cfg):
    return RD.cmd_next(session_dir, cfg)


def test_next_emits_round1_full_deep_panel(tmp_path):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    assert n["ok"] and n["action"] == RD.P_PANEL and n["round"] == 1
    # round-1 baseline is the full FIVE-seat reviewer-deep panel (the reversal upgrade).
    assert n["payload"]["tier"] == RD.DEEP
    assert sorted(n["payload"]["dimensions"]) == sorted(RD.DIMENSIONS)


def test_next_is_idempotent_before_submit(tmp_path):
    d = str(tmp_path)
    a = _first_next(d, _cfg())
    b = RD.cmd_next(d)
    assert a["phase"] == b["phase"] and a["attempt"] == b["attempt"]
    assert a["expectedStateHash"] == b["expectedStateHash"]  # hash reproduces on re-emit


def test_submit_stale_attempt_rejected(tmp_path):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    out = RD.cmd_submit(d, n["phase"], n["attempt"] + 3, n["expectedStateHash"], {"seats": {}})
    assert out["ok"] is False and "echo" in out["reason"]


def test_submit_hash_mismatch_rejected(tmp_path):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    out = RD.cmd_submit(d, n["phase"], n["attempt"], "deadbeef", {"seats": {}})
    assert out["ok"] is False and "hash" in out["reason"]


def test_submit_without_state_hash_rejected(tmp_path):
    """#507 v13: the state-hash echo is REQUIRED — a first-time fold with no hash is refused (never
    fold fail-open on an absent hash)."""
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    out = RD.cmd_submit(d, n["phase"], n["attempt"], None, {"seats": {}})
    assert out["ok"] is False and "state-hash" in out["reason"]


def test_submit_duplicate_is_idempotent(tmp_path):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    art = {"seats": {"code-reviewer": {"findings": []}}}
    first = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
    assert first["ok"] is True and not first.get("duplicate")
    dup = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
    assert dup == {"ok": True, "duplicate": True}


# --- #845 panel seat-key guard ------------------------------------------------

_ALL_STEMS = {s: {"findings": []} for s in ("architecture", "code", "security", "test", "premortem")}
_ALL_DIMS = {d: {"findings": []} for d in RD.DIMENSIONS}
_CORRECT_RECOVERY = {"seats": {"code-reviewer": {"findings": []}}}


def _assert_seat_key_refused(d, n, artifact, offending_key):
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)
    assert out["ok"] is False
    assert "seat key" in out["reason"]
    assert offending_key in out["reason"]
    after = RD.cmd_next(d)
    assert after["phase"] == n["phase"]
    assert after["attempt"] == n["attempt"]
    assert after["expectedStateHash"] == n["expectedStateHash"]
    recovery = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                             _CORRECT_RECOVERY)
    assert recovery["ok"] is True
    journal = RD.read_journal(d)
    assert any(e.get("outcome") == "seat-key-mismatch" for e in journal)


@pytest.mark.parametrize("artifact,offending_key", [
    (_ALL_STEMS, "architecture"),
    ({"code-reviewer": {"findings": []}, "architecture": {"findings": []}}, "architecture"),
    ({"code-reviewer": {"findings": []}, "architecture-reviewr": {"findings": []}},
     "architecture-reviewr"),
    ({"seats": {"seatMap": {}}}, "seatMap"),
], ids=["all-stems", "partial-mis-key", "arbitrary-wrong-key", "envelope-in-seats"])
def test_submit_panel_seat_key_refused(tmp_path, artifact, offending_key):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    _assert_seat_key_refused(d, n, artifact, offending_key)


@pytest.mark.parametrize("artifact", [
    _ALL_DIMS,
    {"seats": {"code-reviewer": {"findings": []}}},
    {"seats": {}},
    {"seats": []},
    {"seatMap": {}, "ranManifest": {}, "canaryResult": {}},
], ids=["all-dims", "partial-legitimate", "empty-seats", "non-dict-seats", "metadata-only"])
def test_submit_panel_seat_key_accepted(tmp_path, artifact):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)
    assert out["ok"] is True


def test_submit_panel_seat_key_guard_before_fold(tmp_path):
    """A refused submit must not mutate loop-state — the guard runs before fold/save."""
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    state_path = os.path.join(d, RD.STATE_FILE)
    with open(state_path, "rb") as fh:
        before = fh.read()
    RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                  {"architecture": {"findings": []}})
    with open(state_path, "rb") as fh:
        after = fh.read()
    assert before == after


def test_submit_panel_seat_key_does_not_preempt_fences(tmp_path):
    """Mis-keyed artifact with stale attempt or bad hash keeps the existing fence reasons."""
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    bad = {"architecture": {"findings": []}}
    stale = RD.cmd_submit(d, n["phase"], n["attempt"] + 3, n["expectedStateHash"], bad)
    assert stale["ok"] is False and "echo" in stale["reason"]
    assert "seat key" not in stale["reason"]
    hash_bad = RD.cmd_submit(d, n["phase"], n["attempt"], "deadbeef", bad)
    assert hash_bad["ok"] is False and "hash" in hash_bad["reason"]
    assert "seat key" not in hash_bad["reason"]


def test_cmd_submit_is_only_fold_caller_besides_run_loop():
    """A NEW `_fold` caller is a new submit seam that must either route through
    `panel_seat_key_fault` or be added to this census deliberately.

    Deliberately simple: this pins the ordinary `_fold(...)` caller set and nothing more. It does
    NOT model attribute-style calls, module-level calls, or `_fold_panel` callers — two attempts at
    a fuller AST census both shipped silent gaps, so the broader drift guard is tracked as a
    follow-up rather than half-built here.
    """
    import ast
    mod_path = os.path.join(_LIB, "round_driver.py")
    with open(mod_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    callers = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                if child.func.id == "_fold":
                    callers.add(node.name)
                    break
    assert callers == {"cmd_submit", "run_loop"}


def test_submit_panel_seat_key_custom_dimensions(tmp_path):
    """Guard uses the configured roster from state, not the global DIMENSIONS default."""
    narrow = ["code-reviewer", "test-reviewer"]
    d = str(tmp_path)
    n = _first_next(d, _cfg(dimensions=narrow))
    assert sorted(n["payload"]["dimensions"]) == sorted(narrow)
    accepted = {dim: {"findings": []} for dim in narrow}
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], accepted)
    assert out["ok"] is True

    d2 = str(tmp_path / "refuse")
    os.makedirs(d2, exist_ok=True)
    n2 = _first_next(d2, _cfg(dimensions=narrow))
    refused = {"code-reviewer": {"findings": []}, "architecture-reviewer": {"findings": []}}
    out2 = RD.cmd_submit(d2, n2["phase"], n2["attempt"], n2["expectedStateHash"], refused)
    assert out2["ok"] is False
    assert "architecture-reviewer" in out2["reason"]
    assert "configured dimensions: code-reviewer, test-reviewer" in out2["reason"]


def test_panel_seat_keys_explicit_shape():
    art = {"seats": {"code-reviewer": {}, "seatMap": {}}}
    assert RD.panel_seat_keys(art) == ["code-reviewer", "seatMap"]


def test_panel_seat_keys_legacy_shape():
    art = {"code-reviewer": {}, "seatMap": {}, "ranManifest": {}, "canaryResult": {}}
    assert RD.panel_seat_keys(art) == ["code-reviewer"]


def test_panel_seat_keys_non_dict():
    assert RD.panel_seat_keys(None) == []
    assert RD.panel_seat_keys([]) == []


def test_panel_seat_key_fault_empty_dimensions():
    assert RD.panel_seat_key_fault([], {"architecture": {}}) is None
    assert RD.panel_seat_key_fault(None, {"architecture": {}}) is None


def test_panel_seat_key_fault_stem_hint():
    fault = RD.panel_seat_key_fault(RD.DIMENSIONS, {"architecture": {}})
    assert fault is not None
    assert "seat key" in fault
    assert "architecture is the findings-file stem for architecture-reviewer" in fault


def test_panel_seat_key_fault_no_hint_for_unknown_stem():
    fault = RD.panel_seat_key_fault(RD.DIMENSIONS, {"totally-unknown": {}})
    assert fault is not None
    assert "seat key" in fault
    assert "findings-file stem" not in fault


def test_v1_state_is_refused_with_fresh_start_message(tmp_path):
    d = str(tmp_path)
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump({"schemaVersion": 1, "rounds": {}}, fh)
    out = RD.cmd_next(d)
    assert out["ok"] is False and "fresh session dir" in out["reason"]


def test_journal_appended_per_call(tmp_path):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                  {"seats": {"code-reviewer": {"findings": []}}})
    journal = RD.read_journal(d)
    cmds = [e["cmd"] for e in journal]
    assert "next" in cmds and "submit" in cmds
    assert any(e.get("outcome") == "accepted" for e in journal)


# =============================================================================
# a scripted driver harness (CLI end-to-end)
# =============================================================================

def _drive_cli(session_dir, cfg, respond, max_steps=80):
    """Drive next/submit to a terminal using `respond(phase, payload, round) -> artifact`."""
    first = True
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            return n["payload"]
        art = respond(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    raise AssertionError("driver did not reach a terminal within %d steps" % max_steps)


def _responder(round1_findings=None, scoped=None, audit="discharged", verify="pass",
               head=HEAD, verdict="CONFIRMED"):
    scoped_state = {"fired": False}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {d: {"findings": []} for d in RD.DIMENSIONS}
            if rnd == 1 and round1_findings:
                seats["code-reviewer"] = {"findings": list(round1_findings)}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            out = []
            for c in payload.get("clusters", []):
                for i in c.get("ids", []):
                    v = {"id": i, "verdict": verdict}
                    if verdict == "CONFIRMED":
                        v["evidence"] = "ran"
                    out.append(v)
            return {"verdicts": out}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_GAPSWEEP:
            return {"findings": []}
        if phase == RD.P_AUDITS:
            # The orchestrator records its dispatch manifest out-of-band from the results — the vendor
            # it seated per target, read off the dispatch payload (never the result echo).
            return {"results": [{"id": t["id"], "ruling": audit, "reason": "r", "evidence": "e",
                                 "auditorVendor": t.get("auditorVendor")}
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            if scoped and not scoped_state["fired"]:
                scoped_state["fired"] = True
                return {"findings": list(scoped)}
            return {"findings": []}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiff": head, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": verify}
        return {}

    return respond


# --- #885 submit-shape guards (verify + audits) -------------------------------
#
# A wrong-SHAPE verify or audits artifact used to fold into a TERMINAL, journalled, immutable state
# — the certification receipt was lost and a corrected resubmit refused. These pin the refusal at
# the chokepoint: the pending step survives, the state file is byte-identical, and recovery is a
# corrected resubmit on the SAME phase/attempt/state-hash.

_A_FINDING = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]
_GOOD_VERIFY = {"result": "pass"}


def _drive_to_phase(session_dir, cfg, respond, target_phase, max_steps=80):
    """Drive next/submit with `respond` until the PENDING step is `target_phase`; return that
    `next`. Asserts the loop did not reach a terminal first, so a routing change that stops
    reaching the phase fails loudly instead of silently skipping the test's body."""
    first = True
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        if n.get("phase") == target_phase:
            return n
        assert n["action"] != RD.P_TERMINAL, "reached terminal before %s" % target_phase
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                          respond(n["phase"], n["payload"], n["round"]))
        assert s["ok"], s
    raise AssertionError("never reached %s within %d steps" % (target_phase, max_steps))


def _at(tmp_path, target_phase, cfg=None):
    """Drive a fresh session to `target_phase`. `cfg` overrides the default profile so a test can
    pin real config the guard must stay blind to (e.g. a configured `verifyCommand`)."""
    d = str(tmp_path)
    n = _drive_to_phase(d, cfg or _cfg(), _responder(round1_findings=_A_FINDING), target_phase)
    return d, n


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, RD.STATE_FILE), "rb") as fh:
        return fh.read()


def _assert_shape_refused(d, n, artifact, expected_outcome, must_name, recovery):
    """The whole refusal contract in one place: refused with a shape-naming reason, state
    byte-identical, the pending step intact, a NON-terminal journal event, and the corrected
    artifact accepted on the same phase/attempt/state-hash."""
    before = _state_bytes(d)
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)
    assert out["ok"] is False, out
    for fragment in must_name:
        assert fragment in out["reason"], (fragment, out["reason"])
    assert "resubmit the same phase/attempt/state-hash" in out["reason"]

    assert _state_bytes(d) == before, "a refused submit mutated loop-state"
    ok, state = RD.load_state(d)
    assert ok and not state.get("terminal"), "a shape refusal reached a terminal state"

    journal = RD.read_journal(d)
    assert journal[-1].get("outcome") == expected_outcome, journal[-1]
    assert not any(e.get("outcome") in ("accepted", "terminal-receipt-fault") for e in journal
                   if e is journal[-1])

    again = RD.cmd_next(d)
    assert (again["phase"], again["attempt"], again["expectedStateHash"]) == (
        n["phase"], n["attempt"], n["expectedStateHash"])
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], recovery)["ok"] is True


@pytest.mark.parametrize("artifact,must_name", [
    ({}, ["no usable `result` (got None)", "one of: fail, none, pass, skipped, timeout"]),
    ({"result": None}, ["no usable `result` (got None)"]),
    ({"exitCode": 0, "passed": True, "output": "ok"},
     ["`passed` is the raw runner envelope's key", "`exitCode` is the raw runner envelope's key"]),
    ({"result": "passed"}, ["got 'passed'"]),
    ({"result": "PASS"}, ["got 'PASS'"]),
    ({"result": True}, ["got True"]),
    ({"status": "ok"}, ["`status` is not the driver's key"]),
    # `json.load` accepts ANY JSON root, so a bare list reaches the guard carrying no keys at all —
    # the reason must name the ENVELOPE, not report a `result` such a root could never have.
    ([{"result": "pass"}], ["verify artifact is list, not a result object",
                            "expected {\"result\":"]),
    (None, ["verify artifact is NoneType, not a result object"]),
], ids=["missing", "explicit-none", "runner-envelope-878", "near-miss-token", "wrong-case",
        "non-string", "status-key", "non-dict-list-root", "non-dict-null-root"])
def test_submit_verify_malformed_refused(tmp_path, artifact, must_name):
    d, n = _at(tmp_path, RD.P_VERIFY)
    _assert_shape_refused(d, n, artifact, "verify-result-shape", must_name, _GOOD_VERIFY)


# Every token the guard accepts, paired with the fold arm it lands in. This is the anti-drift pin:
# `_VERIFY_RESULTS` may not accept a token `_fold_verify` has no defined arm for, and may not reject
# one it does. `test_verify_vocabulary_census` holds the two sides equal.
_VERIFY_TOKEN_ARMS = [
    ("pass", None),                    # advances — no halting decision recorded
    ("fail", "verify-fail"),
    ("timeout", "verify-unresolved"),
    ("skipped", "verify-skipped"),
    ("none", "verify-skipped"),
    ("unverified", "verify-skipped"),
]


def test_verify_vocabulary_census():
    assert sorted(t for t, _ in _VERIFY_TOKEN_ARMS) == sorted(RD._VERIFY_RESULTS)


@pytest.mark.parametrize("token,decision_kind", _VERIFY_TOKEN_ARMS,
                         ids=[t for t, _ in _VERIFY_TOKEN_ARMS])
def test_submit_verify_recognized_token_accepted(tmp_path, token, decision_kind):
    """A recognized token is ACCEPTED and folds exactly as it does today — including the deliberate
    fail-closed halts. The guard refuses mis-shape, never a real outcome."""
    d, n = _at(tmp_path, RD.P_VERIFY)
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], {"result": token})
    assert out["ok"] is True, out
    ok, state = RD.load_state(d)
    assert ok
    kinds = [dec.get("kind") for dec in state.get("decisions", [])]
    if decision_kind is None:
        assert not any(k and k.startswith("verify-") for k in kinds), kinds
    else:
        assert decision_kind in kinds, kinds


@pytest.mark.parametrize("token", list(RD._VERIFY_SKIP), ids=list(RD._VERIFY_SKIP))
def test_submit_verify_skip_accepted_with_a_configured_command(tmp_path, token):
    """A skip token is ACCEPTED by the shape guard even when a REAL verify command is configured —
    the guard is deliberately CONFIG-BLIND (vocabulary only) and the FOLD owns the fail-closed
    `verify-skip-but-configured` halt.

    axis: that the guard never refuses an HONESTLY reported skip. A runner that truthfully says
    `skipped`/`none`/`unverified` while a command is configured cannot "correct" that artifact
    without lying, so a config-aware refusal here would trap the orchestrator in an unresolvable
    refusal loop — the exact class this guard exists to remove. The sibling
    `test_verify_skip_with_configured_command_halts` drives `run_loop`, which calls `_fold` directly
    and never reaches the guard, so it does not pin this split: guard ACCEPTS, fold DECIDES.
    """
    d, n = _at(tmp_path, RD.P_VERIFY, cfg=_cfg(verifyCommand="pytest -q"))
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], {"result": token})
    assert out["ok"] is True, out                      # the GUARD accepts
    ok, state = RD.load_state(d)
    assert ok
    kinds = [dec.get("kind") for dec in state.get("decisions", [])]
    assert "verify-skip-but-configured" in kinds, kinds   # the FOLD halts
    assert "verify-skipped" not in kinds, kinds          # never the unverified-advance arm
    assert state.get("terminal") == "halted", state.get("terminal")
    assert state["certification"]["shape"] is None
    assert "pytest -q" in state["certification"]["reason"]


def test_submit_verify_guard_does_not_preempt_fences(tmp_path):
    """A mis-shaped verify artifact with a stale attempt or bad hash keeps the existing fence
    reasons — the shape guard sits AFTER the echo/hash fences, never in front of them."""
    d, n = _at(tmp_path, RD.P_VERIFY)
    bad = {"passed": True}
    stale = RD.cmd_submit(d, n["phase"], n["attempt"] + 3, n["expectedStateHash"], bad)
    assert stale["ok"] is False and "echo" in stale["reason"] and "`result`" not in stale["reason"]
    hash_bad = RD.cmd_submit(d, n["phase"], n["attempt"], "deadbeef", bad)
    assert hash_bad["ok"] is False and "hash" in hash_bad["reason"]
    assert "`result`" not in hash_bad["reason"]


def _audit_artifact(n, **over):
    """A well-formed audits artifact for this round's real targets, with one field overridden."""
    targets = n["payload"]["targets"]
    assert targets, "the audits payload carried no targets to key rulings against"
    result = {"id": targets[0]["id"], "ruling": "discharged", "reason": "r", "evidence": "e",
              "auditorVendor": targets[0].get("auditorVendor")}
    result.update(over)
    return ({"results": [result],
             "collectionManifest": {t["id"]: t.get("auditorVendor") for t in targets}}, targets)


@pytest.mark.parametrize("over,must_name", [
    ({"ruling": "discharged-but-new-issue", "newIssue": "found another bug"},
     ["no usable `newIssues`", "`newIssue` (singular)", "a LIST"]),
    ({"ruling": "discharged-but-new-issue", "newIssues": "found another bug"},
     ["no usable `newIssues`", "non-empty list of issue objects"]),
    ({"ruling": "discharged-but-new-issue", "newIssues": []}, ["no usable `newIssues`"]),
    ({"ruling": "discharged-but-new-issue", "newIssues": ["a string"]}, ["no usable `newIssues`"]),
    ({"ruling": "discharged", "reason": "   "}, ["rules `discharged` with no `reason`"]),
    ({"ruling": "fixed"}, ["unrecognized `ruling` (got 'fixed')", "discharged, not-discharged"]),
    ({"ruling": None}, ["unrecognized `ruling` (got None)"]),
    ({"id": "no-such-target"},
     ["keyed to 'no-such-target', which is not an audit target", "re-key the ruling"]),
    ({"id": None}, ["no usable `id` (got None)"]),
], ids=["new-issue-singular-880", "new-issues-string", "new-issues-empty", "new-issues-non-dict",
        "discharged-blank-reason", "unknown-ruling", "null-ruling", "unmatched-id", "null-id"])
def test_submit_audits_malformed_refused(tmp_path, over, must_name):
    d, n = _at(tmp_path, RD.P_AUDITS)
    bad, _targets = _audit_artifact(n, **over)
    good, _ = _audit_artifact(n)
    _assert_shape_refused(d, n, bad, "audit-ruling-shape", must_name, good)


def test_submit_audits_non_list_results_refused(tmp_path):
    d, n = _at(tmp_path, RD.P_AUDITS)
    good, _ = _audit_artifact(n)
    _assert_shape_refused(d, n, {"results": {"id": "x"}},
                          "audit-ruling-shape",
                          ["`results` is dict, not a list of ruling objects"], good)


def test_submit_audits_repeated_id_accepted_the_fold_governs(tmp_path):
    """A REPEATED result id is not a shape fault — an orchestrator can submit the same ruling
    twice (e.g. one clearing ruling echoed for each slot that shared a result key). Refusing it
    would be an unresolvable loop: the correction such a refusal names is exactly what the
    orchestrator already did. Per-location target ids (`file::title@L<line>`) do not prevent a
    duplicated RESULT id; the pre-#915 case of duplicate target ids in a persisted session is the
    other way the collision arises. `audits.apply_audit_results` already fails closed on the case
    (`ambiguous`: honor NEITHER ruling), and that handling must be what governs — so a doubled
    CLEARING ruling is accepted here and still folds to not-discharged. The fold records outcomes
    under the line-less `finding_identity`, not the per-location target id."""
    d, n = _at(tmp_path, RD.P_AUDITS)
    good, targets = _audit_artifact(n)                  # a `discharged` ruling
    repeated = {"results": list(good["results"]) + list(good["results"]),
                "collectionManifest": good["collectionManifest"]}
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], repeated)
    assert out["ok"] is True, out
    ok, state = RD.load_state(d)
    assert ok
    outcomes = state["auditRounds"][-1]["outcomes"]
    expected_identity = FI.finding_identity(targets[0])
    assert [(o["identity"], o["ruling"]) for o in outcomes] == [(expected_identity, "not-discharged")], outcomes
    assert "@L" not in expected_identity
    assert any(dec.get("kind") == "not-discharged" for dec in state["decisions"]), state["decisions"]


def test_submit_audits_two_targets_one_colliding_id_not_refused():
    """The same collision at the GUARD's own boundary: two targets carrying one line-less id, one
    ruling submitted per target. After #915, audit rosters mint distinct per-location target ids, so
    this collision is reachable only for a session persisted before that change (or any caller that
    deliberately supplies the legacy id shape). This is a unit-level assertion because the loop
    cannot be driven to two colliding targets with the existing helpers — the panel/synthesis merge
    collapses two same-identity findings into one. The chokepoint behavior is pinned by the
    loop-level test above."""
    targets = [{"id": "f.py::unchecked return value"}, {"id": "f.py::unchecked return value"}]
    one_ruling_each = [{"id": "f.py::unchecked return value", "ruling": "discharged", "reason": "r"},
                       {"id": "f.py::unchecked return value", "ruling": "discharged", "reason": "r"}]
    assert RD.audit_results_fault({"results": one_ruling_each}, targets) is None


@pytest.mark.parametrize("artifact", [None, [{"id": "x", "ruling": "discharged"}]],
                         ids=["null-root", "list-root"])
def test_submit_audits_non_dict_artifact_refused(tmp_path, artifact):
    """`json.load` accepts ANY JSON root, so a `null` or bare-list artifact reaches the submit path.
    Unrefused it normalizes to `{}` in the fold, consuming ZERO rulings — every target folds
    `unaudited` → not-discharged with the pending step gone. That is the #885 loss class arriving
    through a root the `results` checks never inspect."""
    d, n = _at(tmp_path, RD.P_AUDITS)
    good, _ = _audit_artifact(n)
    _assert_shape_refused(d, n, artifact, "audit-ruling-shape",
                          ["not a results object", "expected {\"results\":"], good)


def test_submit_audits_non_dict_entry_refused(tmp_path):
    d, n = _at(tmp_path, RD.P_AUDITS)
    good, _ = _audit_artifact(n)
    _assert_shape_refused(d, n, {"results": ["discharged"]}, "audit-ruling-shape",
                          ["results[0] is str, not a ruling object"], good)


@pytest.mark.parametrize("over", [
    {},
    {"ruling": "not-discharged", "reason": "still broken"},
    {"ruling": "not-discharged"},                      # reason is optional on not-discharged
    # The candidate is FULLY shaped on purpose. A title-only candidate is accepted by both the guard
    # and the fold today (usability is dict-shape, deliberately not diff-scoped), but `_fold_scoped`
    # then runs it through `mechanical_compile`, which drops an uncited `file:line`-less candidate
    # and whose drop list that fold does not surface. This fixture must not read as the project
    # asserting that a thin candidate travels safely.
    {"ruling": "discharged-but-new-issue",
     "newIssues": [{"title": "new", "severity": "Important", "file": "f.py", "line": 1}]},
], ids=["discharged", "not-discharged-with-reason", "not-discharged-bare", "discharged-new-issue"])
def test_submit_audits_wellformed_accepted(tmp_path, over):
    d, n = _at(tmp_path, RD.P_AUDITS)
    art, _ = _audit_artifact(n, **over)
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)["ok"] is True


@pytest.mark.parametrize("artifact", [{}, {"results": []}],
                         ids=["absent-results", "empty-results"])
def test_submit_audits_silence_still_accepted(tmp_path, artifact):
    """Genuine auditor SILENCE is a real answer the fold discloses as `unaudited` and fails closed
    on — not a shape fault. The guard must never convert it into a refusal loop the orchestrator
    cannot escape."""
    d, n = _at(tmp_path, RD.P_AUDITS)
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)["ok"] is True


def test_submit_audits_guard_does_not_preempt_fences(tmp_path):
    """The audits twin of `test_submit_verify_guard_does_not_preempt_fences`: a mis-shaped AUDITS
    artifact submitted with a stale attempt or a bad state-hash keeps the ECHO/HASH fence reason —
    the shape refusal never surfaces in front of them.

    axis: the guard's PLACEMENT in `cmd_submit` — after both anti-stale/fork fences. A regression
    that hoists the `P_AUDITS` block above the hash fence would answer a forked submit with a
    "correct your artifact" reason, inviting a resubmit against state that has already moved.
    """
    d, n = _at(tmp_path, RD.P_AUDITS)
    bad, _targets = _audit_artifact(n, ruling="discharged-but-new-issue",
                                    newIssue="found another bug")
    stale = RD.cmd_submit(d, n["phase"], n["attempt"] + 3, n["expectedStateHash"], bad)
    assert stale["ok"] is False and "echo" in stale["reason"], stale
    assert "newIssues" not in stale["reason"], stale
    hash_bad = RD.cmd_submit(d, n["phase"], n["attempt"], "deadbeef", bad)
    assert hash_bad["ok"] is False and "hash" in hash_bad["reason"], hash_bad
    assert "newIssues" not in hash_bad["reason"], hash_bad


def test_submit_audits_unauthenticated_ruling_still_folds(tmp_path):
    """Provenance is a TRUST boundary, not a shape. A correctly-shaped ruling whose collection
    manifest cannot authenticate it must still FOLD to not-discharged — never be handed back as a
    'correctable' shape fault, which would invite the orchestrator to resubmit a forged echo."""
    d, n = _at(tmp_path, RD.P_AUDITS)
    art, targets = _audit_artifact(n)
    art["collectionManifest"] = {}                       # the orchestrator recorded no dispatch
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
    assert out["ok"] is True, out
    ok, state = RD.load_state(d)
    assert ok
    assert any(dec.get("kind") == "audit-provenance-fail" for dec in state["decisions"])


# --- the guards as pure functions ---------------------------------------------

def test_verify_result_fault_pure():
    assert RD.verify_result_fault({"result": "pass"}) is None
    assert RD.verify_result_fault({"result": "timeout"}) is None
    assert RD.verify_result_fault(None) is not None
    assert RD.verify_result_fault([]) is not None
    assert "`passed`" in RD.verify_result_fault({"passed": True})
    assert "`passed`" not in RD.verify_result_fault({"result": "nope"})


def test_audit_results_fault_pure():
    good = [{"id": "a1", "ruling": "not-discharged"}]
    assert RD.audit_results_fault({"results": good}, [{"id": "a1"}]) is None
    assert RD.audit_results_fault({}, [{"id": "a1"}]) is None
    # a non-dict ROOT can carry no rulings at all — refused, naming the envelope (never a `results`
    # complaint about a root that has no keys)
    assert "not a results object" in RD.audit_results_fault(None, [])
    assert "audits artifact is list" in RD.audit_results_fault([{"id": "a1"}], [{"id": "a1"}])
    # a REPEATED id is not a shape fault — line-less identities legitimately collide; the fold's
    # `ambiguous` handling governs (test_submit_audits_repeated_id_accepted_the_fold_governs)
    assert RD.audit_results_fault({"results": good + good}, [{"id": "a1"}, {"id": "a1"}]) is None
    # an empty target set judges no id — the seat-key guard's empty-key rule, audit-side
    assert RD.audit_results_fault({"results": [{"id": "zz", "ruling": "not-discharged"}]}, []) is None
    assert "not an audit target" in RD.audit_results_fault({"results": good}, [{"id": "other"}])
    # a ruling with no binding id is refused even with NO targets to key against — the id branch
    # stands on its own, so its bite-proof reddens on the refusal axis rather than on a message
    assert "no usable `id`" in RD.audit_results_fault(
        {"results": [{"id": None, "ruling": "not-discharged"}]}, [])
    assert "results[0] is str" in RD.audit_results_fault({"results": ["discharged"]}, [])
    # the entry index is named so a multi-result artifact says WHICH ruling is wrong
    two = [{"id": "a1", "ruling": "not-discharged"}, {"id": "a2", "ruling": "nope"}]
    assert "results[1]" in RD.audit_results_fault({"results": two}, [{"id": "a1"}, {"id": "a2"}])


def test_verifier_results_fault_pure():
    assert RD.verifier_results_fault({"verdicts": []}) is None
    assert RD.verifier_results_fault({"verdicts": [{"id": "x", "verdict": "CONFIRMED"}]}) is None
    assert RD.verifier_results_fault(None) is not None
    assert RD.verifier_results_fault({}) is not None
    assert "missing `verdicts`" in RD.verifier_results_fault({}) or \
        "no `verdicts` key" in RD.verifier_results_fault({})
    fault = RD.verifier_results_fault({"findings": []})
    assert fault is not None and "`findings`" in fault
    assert RD.verifier_results_fault({"verdicts": {}}) is not None


def test_submit_verifiers_findings_key_refused(tmp_path):
    d, n = _at(tmp_path, RD.P_VERIFIERS)
    good = {"verdicts": []}
    bad = {"findings": []}
    _assert_shape_refused(d, n, bad, "verifier-results-shape",
                          ["`findings`", "`verdicts`"], good)


def test_submit_verifiers_empty_verdicts_accepted(tmp_path):
    """Fail-closed edge 6: an empty verdict list is a legitimate outcome."""
    d, n = _at(tmp_path, RD.P_VERIFIERS)
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                         {"verdicts": []})["ok"] is True


def test_submit_verifiers_dict_verdicts_refused(tmp_path):
    """Fail-closed edge 7: a dict-typed verdicts is refused."""
    d, n = _at(tmp_path, RD.P_VERIFIERS)
    _assert_shape_refused(d, n, {"verdicts": {}}, "verifier-results-shape",
                          ["not a list"], {"verdicts": []})


def test_bite_verifiers_shape_guard_red(monkeypatch, tmp_path):
    """A/B: correct key succeeds; neutralizing the guard lets a findings-keyed submit through."""
    d, n = _at(tmp_path, RD.P_VERIFIERS)
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                         {"verdicts": []})["ok"] is True

    d2, n2 = _at(tmp_path / "bite", RD.P_VERIFIERS)
    monkeypatch.setattr(RD, "verifier_results_fault", lambda _artifact: None)
    out = RD.cmd_submit(d2, n2["phase"], n2["attempt"], n2["expectedStateHash"],
                        {"findings": []})
    assert out["ok"] is True  # RED with guard neutralized


def test_new_issues_usability_agrees_with_the_running_fold():
    """What the guard ACCEPTS is what the fold can USE — proven by running `apply_audit_results`
    itself, never by re-asserting `has_usable_new_issues` against its own callee.

    axis: DIVERGENCE between the guard's usability predicate and the fold's actual behavior. If the
    fold grows an inline rule the predicate does not share (say, also demanding a `title`), the #880
    split-brain returns — the guard admits a `discharged-but-new-issue` claim the fold then fails
    closed on, and the build loses the ruling it submitted. So each payload is driven through the
    REAL fold: usable ⇒ the finding clears with its candidate emitted; unusable ⇒ it falls closed.
    """
    AU = _load("audits")
    target = {"id": "v0", "file": "f.py", "line": 1, "title": "bug", "severity": "Important"}
    for candidates in ([{"title": "x"}], [{"a": 1}], [{}], [{"a": 1}, 2],
                       [], "str", None, [1, 2]):
        usable = AU.has_usable_new_issues(candidates)
        out = AU.apply_audit_results(
            [target],
            [{"id": "v0", "ruling": "discharged-but-new-issue", "reason": "fixed but leaked",
              "newIssues": candidates}])
        folded = out["audits"][0]["ruling"]
        if usable:
            assert folded == "discharged-but-new-issue", (candidates, out)
            assert out["discharged"] == ["v0"], (candidates, out)
            assert out["newIssues"], (candidates, out)
            assert out["malformed"] == [], (candidates, out)
        else:
            assert folded == "not-discharged", (candidates, out)
            assert out["notDischarged"] == ["v0"], (candidates, out)
            assert out["discharged"] == [], (candidates, out)
            assert out["newIssues"] == [], (candidates, out)


def test_happy_path_audited_chain_certification(tmp_path):
    """Round-1 panel → verify findings → fix → delta round → all discharged → audited-chain."""
    d = str(tmp_path)
    payload = _drive_cli(d, _cfg(), _responder(
        round1_findings=[{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]))
    assert payload["verdict"] == "converged"
    assert payload["certification"]["shape"] == "audited-chain"
    # receipt is written at the terminal and validates.
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason
    assert receipt["scriptRan"]["invocations"] > 0


def test_clean_round1_certifies_full_panel_confirmed(tmp_path):
    """A clean full-deep baseline certifies off the qualifying panel (full-panel-confirmed)."""
    d = str(tmp_path)
    payload = _drive_cli(d, _cfg(), _responder(round1_findings=None))
    assert payload["verdict"] == "converged"
    assert payload["certification"]["shape"] == "full-panel-confirmed"


def test_unknown_delta_surface_runs_full_panel(tmp_path):
    """A malformed/quoted-path head diff → unknown surface → a FULL reviewer-deep panel (the
    existing unknown→run-everything rule), not a scoped audit."""
    d = str(tmp_path)
    bad_head = 'diff --git "a/x y.py" "b/x y.py"\n@@ -1 +1 @@\n-a\n+b\n'
    seen = {"panel_r2": False}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            if rnd >= 2:
                seen["panel_r2"] = True
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "PLAUSIBLE"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiff": bad_head, "changedSubjects": []}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        if phase in (RD.P_AUDITS, RD.P_SCOPED, RD.P_GAPSWEEP):
            return {"results": [], "findings": []}
        return {}

    payload = _drive_cli(d, _cfg(), respond)
    assert seen["panel_r2"] is True
    assert payload["verdict"] == "converged"


# =============================================================================
# scoped-finder new-surface payload + empty-surface skip (#507 WO-R2b)
# =============================================================================

# A multi-file post-fix head diff: f.py carries the fixed hunk (over the fix's line, an AUDIT
# target) PLUS a brand-new hunk far from it, and g.py is an entirely new surface. The split must
# route the two off-target hunks into `newSurface` — the scoped finder's real payload.
_R2B_REVIEWED = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
                 "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
_R2B_HEAD_MF = ("diff --git a/f.py b/f.py\nindex 2..3 100644\n--- a/f.py\n+++ b/f.py\n"
                "@@ -1 +1,2 @@\n-old\n+new\n+fixed\n"
                "@@ -50,0 +50,2 @@\n+brand\n+new\n"
                "diff --git a/g.py b/g.py\nindex 0..1 100644\n--- a/g.py\n+++ b/g.py\n"
                "@@ -0,0 +1,3 @@\n+alpha\n+beta\n+gamma\n")


def test_scoped_finder_payload_carries_computed_new_surface(tmp_path):
    """The dispatch-scoped-finder payload carries EXACTLY the split's computed `newSurface` hunks
    (file → hunk ranges + text) — a multi-file surface must arrive intact, not empty (#507 WO-R2b:
    the field-found defect was an empty `hunks: {}` payload despite a real computed surface)."""
    d = str(tmp_path)
    captured = {"payload": None}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_AUDITS:
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r",
                                 "evidence": "e", "auditorVendor": t.get("auditorVendor")}
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            captured["payload"] = payload
            return {"findings": []}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiff": _R2B_HEAD_MF, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        return {}

    payload = _drive_cli(d, _cfg(diff=_R2B_REVIEWED), respond)
    assert payload["verdict"] == "converged"
    assert captured["payload"] is not None, "the scoped finder was never dispatched"
    hunks = captured["payload"]["hunks"]
    # exactly the split's computed new surface — a non-empty, multi-file map.
    expected = RD.delta_surface.split_fix_surface(
        _R2B_REVIEWED, _R2B_HEAD_MF, [{"file": "f.py", "line": 1}])["newSurface"]
    assert expected and set(expected) == {"f.py", "g.py"}, expected
    assert hunks == expected
    assert sum(len(v) for v in hunks.values()) == 2


def test_empty_new_surface_skips_scoped_finder_with_note(tmp_path):
    """A genuinely empty computed new surface (split `unknown: False`, no new hunks — the fix only
    touched the audited lines) SKIPS the scoped-finder dispatch with a receipt-visible
    `scopedFinder: skipped-empty-surface` note, never a vacuous scan over nothing (#507 WO-R2b)."""
    d = str(tmp_path)
    seen = {"scoped": False}

    base = _responder(round1_findings=[
        {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}])

    def respond(phase, payload, rnd):
        if phase == RD.P_SCOPED:
            seen["scoped"] = True
        return base(phase, payload, rnd)

    payload = _drive_cli(d, _cfg(), respond)
    assert payload["verdict"] == "converged"
    assert seen["scoped"] is False, "the scoped finder was dispatched over an empty surface"
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason
    # the skip is journaled receipt-visibly: as a decision AND on the delta round record.
    kinds = [dc["kind"] for dc in receipt["decisions"]]
    assert "scoped-finder-skipped" in kinds, kinds
    delta_round = [r for r in receipt["rounds"] if r.get("scopedFinder")]
    assert delta_round and delta_round[0]["scopedFinder"] == "skipped-empty-surface", receipt["rounds"]


# =============================================================================
# dispatch-fixer head diff: inline OR absolute headDiffPath; unreadable → full panel (#507)
# =============================================================================

def _multifile_delta_respond(captured, fixer_artifact):
    """A CLI responder for the multi-file delta scenario: round-1 finds one Important at f.py:1,
    audits discharge, the scoped finder's payload is captured. The fixer's artifact (inline `headDiff`
    and/or `headDiffPath`) is supplied by the caller so each test exercises a different head-diff
    source."""
    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_AUDITS:
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r",
                                 "evidence": "e", "auditorVendor": t.get("auditorVendor")}
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            captured["payload"] = payload
            return {"findings": []}
        if phase == RD.P_FIXER:
            return dict(fixer_artifact)
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        return {}
    return respond


def test_fixer_head_diff_path_form_end_to_end(tmp_path):
    """A `dispatch-fixer` artifact may carry the post-fix head diff as an ABSOLUTE `headDiffPath` the
    driver reads itself (a real git diff cannot inline into a JSON submit artifact). The delta split
    reads the file's content, so the scoped finder's payload carries that file's new surface (#507)."""
    d = str(tmp_path)
    head_file = tmp_path / "head-r1.txt"
    head_file.write_text(_R2B_HEAD_MF, encoding="utf-8")
    captured = {"payload": None}
    respond = _multifile_delta_respond(
        captured, {"fixes": [], "headDiffPath": str(head_file), "changedSubjects": ["Code"]})
    payload = _drive_cli(d, _cfg(diff=_R2B_REVIEWED), respond)
    assert payload["verdict"] == "converged"
    assert captured["payload"] is not None, "the scoped finder was never dispatched"
    expected = RD.delta_surface.split_fix_surface(
        _R2B_REVIEWED, _R2B_HEAD_MF, [{"file": "f.py", "line": 1}])["newSurface"]
    assert captured["payload"]["hunks"] == expected and set(expected) == {"f.py", "g.py"}
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert any(r.get("headDiffSource") == "path" for r in receipt["rounds"]), receipt["rounds"]


def test_fixer_unreadable_head_diff_path_schedules_full_panel(tmp_path):
    """An unreadable `headDiffPath` (no inline diff) is an UNKNOWN surface, not an empty one: the
    delta round runs a FULL reviewer-deep panel (unknown→run-everything), never a silent scoped skip
    over nothing. The source is journaled `unknown` and an `unknown-surface` decision is recorded."""
    d = str(tmp_path)
    missing = str(tmp_path / "does-not-exist.txt")
    seen = {"panel_r2": False, "scoped": False}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            if rnd >= 2:
                seen["panel_r2"] = True
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiffPath": missing, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        if phase == RD.P_SCOPED:
            seen["scoped"] = True
            return {"findings": []}
        if phase in (RD.P_AUDITS, RD.P_GAPSWEEP):
            return {"results": [], "findings": []}
        return {}

    payload = _drive_cli(d, _cfg(), respond)
    assert seen["panel_r2"] is True, "an unreadable head diff must run a full panel, not a scoped scan"
    assert seen["scoped"] is False
    assert payload["verdict"] == "converged"
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert any(r.get("headDiffSource") == "unknown" for r in receipt["rounds"]), receipt["rounds"]
    assert any(dc["kind"] == "unknown-surface" for dc in receipt["decisions"]), receipt["decisions"]


def test_fixer_inline_head_diff_wins_over_path(tmp_path):
    """When BOTH inline `headDiff` and `headDiffPath` are present, inline wins: the scoped payload
    carries the inline diff's (multi-file) new surface, not the path file's (empty) one (#507)."""
    d = str(tmp_path)
    other = tmp_path / "other-head.txt"
    other.write_text(HEAD, encoding="utf-8")  # a single-file diff whose only hunk is over the fix
    captured = {"payload": None}
    respond = _multifile_delta_respond(captured, {
        "fixes": [], "headDiff": _R2B_HEAD_MF, "headDiffPath": str(other),
        "changedSubjects": ["Code"]})
    payload = _drive_cli(d, _cfg(diff=_R2B_REVIEWED), respond)
    assert payload["verdict"] == "converged"
    # inline won → the scoped finder fired over the inline diff's two-file surface.
    assert captured["payload"] is not None
    expected = RD.delta_surface.split_fix_surface(
        _R2B_REVIEWED, _R2B_HEAD_MF, [{"file": "f.py", "line": 1}])["newSurface"]
    assert captured["payload"]["hunks"] == expected and set(expected) == {"f.py", "g.py"}
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert any(r.get("headDiffSource") == "inline" for r in receipt["rounds"]), receipt["rounds"]


# =============================================================================
# Layer 1 — run_loop (library) on each leg shape
# =============================================================================

def test_run_loop_code_leg_end_to_end(tmp_path):
    receipt = RD.run_loop(_seams(reviewer=lambda dim, tier, rnd, ctx:
                                 ({"findings": [{"title": "bug", "severity": "Important",
                                                 "file": "f.py", "line": 1}]}
                                  if rnd == 1 and dim == "code-reviewer" else [])),
                          _cfg())
    assert receipt["verdict"] == "converged"
    ok, _ = RD.validate_receipt(receipt)
    assert ok


def test_run_loop_panel_leg_shape(tmp_path):
    """The panel leg-shape config also drives run_loop end-to-end (a clean panel certifies)."""
    receipt = RD.run_loop(_seams(), _cfg(leg="panel"))
    assert receipt["verdict"] == "converged"
    ok, _ = RD.validate_receipt(receipt)
    assert ok


# =============================================================================
# audit-keyed stall → self-recovery once → stall menu
# =============================================================================

def _persistent_not_discharged_seams(io=None):
    counter = {"n": 0}

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [], "headDiff": _headf(counter["n"]), "changedSubjects": ["Code"]}

    def plaus_verifier(clusters, rnd):
        return [{"id": i, "verdict": "PLAUSIBLE"} for i in range(len(clusters or []))]

    return _seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verifier=plaus_verifier,
        auditor=lambda targets, rnd: [{"id": t["id"], "ruling": "not-discharged", "reason": "broken"}
                                      for t in (targets or [])],
        fix_step=fix_step, io=io)


def test_not_discharged_twice_self_recovers_once_then_stall_menu(tmp_path):
    menu_shown = []

    def stall_menu(payload):
        menu_shown.append(payload)
        return "hold"

    seams = _persistent_not_discharged_seams(io={"stall_menu": stall_menu})
    receipt = RD.run_loop(seams, _cfg(maxRounds=20))
    kinds = [dd["kind"] for dd in receipt["decisions"]]
    # exactly one self-recovery, journalled as a decision.
    assert kinds.count("self-recovery") == 1
    # the stall menu was presented without accept-the-risk (PLAUSIBLE stalled target).
    assert len(menu_shown) == 1
    assert menu_shown[0]["choices"] == ["one-more-round", "hold"]
    assert menu_shown[0]["acceptRiskEligible"] is False
    assert receipt["verdict"] == "held"


def _stall_target_state(verdict="CONFIRMED", evidence="ran", identity=None):
    """Build state with a stalled audit target (empty findings list) for accept-risk tests."""
    state = RD.new_state(_cfg())
    state["findings"] = []
    f = {"title": "bug", "severity": "Important", "file": "f.py", "line": 1,
         "verdict": verdict, "evidence": evidence}
    state["fixBatch"] = [f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tgt = state["_auditTargets"][0]
    ident = identity or tgt["identity"]
    state["_auditOutcome"] = {"notDischarged": [tgt["id"]]}
    state["selfRecovered"] = True
    return state, ident, tgt


_STALL_BREAKER = {"reason": "audit-stall", "detail": "stalled", "stalledIdentities": ["v0"]}


def test_accept_the_risk_gated_on_confirmed(tmp_path):
    """accept-the-disclosed-risk is offerable ONLY for a CONFIRMED-with-receipt stalled target."""
    state, ident, _ = _stall_target_state()
    RD._handle_stall(state, state["config"], {"reason": "audit-stall",
                                              "detail": "x", "stalledIdentities": [ident]})
    assert state["_acceptRiskEligible"] is True
    assert "accept-the-disclosed-risk" in state["_stallChoices"]
    # without evidence on the stalled target → NOT eligible.
    state2, ident2, _ = _stall_target_state(verdict="CONFIRMED", evidence=None)
    RD._handle_stall(state2, state2["config"], {"reason": "audit-stall",
                                                "detail": "x", "stalledIdentities": [ident2]})
    assert state2["_acceptRiskEligible"] is False
    assert "accept-the-disclosed-risk" not in state2["_stallChoices"]


def test_accept_risk_eligible_empty_findings_confirmed_stalled_target():
    """accept-risk reads stalled audit targets, not the findings list — empty findings still eligible."""
    state, ident, _ = _stall_target_state()
    RD._handle_stall(state, state["config"], {"reason": "audit-stall",
                                              "detail": "x", "stalledIdentities": [ident]})
    assert state["_acceptRiskEligible"] is True


def test_accept_risk_not_eligible_without_evidence_on_stalled_target():
    state, ident, tgt = _stall_target_state(evidence=None)
    assert tgt.get("evidence") is None
    RD._handle_stall(state, state["config"], {"reason": "audit-stall",
                                              "detail": "x", "stalledIdentities": [ident]})
    assert state["_acceptRiskEligible"] is False


def test_empty_stall_targets_omit_one_more_round_from_menu():
    """one-more-round is not offered when the stall-target snapshot is empty."""
    state = RD.new_state(_cfg())
    state["selfRecovered"] = True
    RD._handle_stall(state, state["config"], _STALL_BREAKER)
    assert state["_stallTargets"] == []
    assert "one-more-round" not in state["_stallChoices"]


def test_second_stall_menu_omits_one_more_round_after_latch():
    """one-more-round is offerable once per session — a second stall menu drops it."""
    state = RD.new_state(_cfg())
    state["selfRecovered"] = True
    state["_oneMoreRoundUsed"] = True
    RD._handle_stall(state, state["config"], _STALL_BREAKER)
    assert "one-more-round" not in state["_stallChoices"]
    assert state["_stallChoices"] == ["hold"]


@pytest.mark.parametrize("choice", ["ship-smaller", "spend-more"])
def test_retired_stall_choice_refused_at_submit(tmp_path, choice):
    d = str(tmp_path)
    state = RD.new_state(_cfg())
    state["selfRecovered"] = True
    RD._handle_stall(state, state["config"], _STALL_BREAKER)
    RD.save_state(d, state)
    n = RD.cmd_next(d)
    assert n["ok"]
    out = RD.cmd_submit(
        d, n["phase"], n["attempt"], n["expectedStateHash"], {"choice": choice})
    assert out["ok"] is False
    assert out["reason"] == "stall-choice-retired:%s" % choice
    ok, reloaded = RD.load_state(d)
    assert ok and reloaded["step"] == RD.P_STALL


def test_one_more_round_accepted_through_cmd_submit(tmp_path):
    """Stepwise owner gate: one-more-round survives cmd_submit and re-enters dispatch-fixer."""
    d = str(tmp_path)
    state, ident, tgt = _stall_target_state()
    RD._handle_stall(state, state["config"], {"reason": "audit-stall",
                                              "detail": "x", "stalledIdentities": [ident]})
    assert "one-more-round" in state["_stallChoices"]
    RD.save_state(d, state)
    n = RD.cmd_next(d)
    assert n["ok"]
    out = RD.cmd_submit(
        d, n["phase"], n["attempt"], n["expectedStateHash"], {"choice": "one-more-round"})
    assert out["ok"] is True, out
    ok, reloaded = RD.load_state(d)
    assert ok
    assert reloaded["step"] == RD.P_FIXER
    assert reloaded["_oneMoreRoundUsed"] is True
    assert reloaded["_fixBatch"] == reloaded["_stallTargets"]


def test_stale_accept_risk_flag_without_stall_targets_fails_closed():
    """A cached _acceptRiskEligible from an older rule must not certify without a qualifying snapshot."""
    state = RD.new_state(_cfg())
    state["selfRecovered"] = True
    state["_acceptRiskEligible"] = True
    state["_stallTargets"] = []
    state["_stallChoices"] = ["accept-the-disclosed-risk", "hold"]
    RD._fold_stall(state, state["config"], {"choice": "accept-the-disclosed-risk"})
    assert state["terminal"] == "stalled"
    assert state["step"] == RD.P_TERMINAL
    assert state["certification"]["shape"] is None


def test_stale_accept_risk_menu_refused_at_submit_chokepoint(tmp_path):
    """Stale persisted menu with accept-the-disclosed-risk must not consume the owner gate."""
    d = str(tmp_path)
    state = RD.new_state(_cfg())
    state["selfRecovered"] = True
    state["_acceptRiskEligible"] = True
    state["_stallTargets"] = []
    state["_stallChoices"] = ["accept-the-disclosed-risk", "hold"]
    state["step"] = RD.P_STALL
    state["pending"] = {"action": RD.P_STALL, "round": 1, "phase": RD.P_STALL, "attempt": 1}
    RD.save_state(d, state)
    n = RD.cmd_next(d)
    assert n["ok"]
    out = RD.cmd_submit(
        d, n["phase"], n["attempt"], n["expectedStateHash"],
        {"choice": "accept-the-disclosed-risk"})
    assert out["ok"] is False
    assert out["reason"] == RD.STALL_ACCEPT_RISK_NOT_ELIGIBLE
    ok, reloaded = RD.load_state(d)
    assert ok and reloaded["step"] == RD.P_STALL
    assert reloaded.get("terminal") is None


def test_stale_accept_risk_flag_is_not_advertised_in_the_stall_menu():
    """The MENU reads the persisted snapshot, not the cached flag (#1037 rider).

    The chokepoint already refused this state (the two tests above); what shipped dishonest was the
    display — a menu offering `accept-the-disclosed-risk` and `acceptRiskEligible: true` for a
    choice the fold would then refuse. Same source for both, so they cannot disagree."""
    state = RD.new_state(_cfg())
    state["selfRecovered"] = True
    state["_acceptRiskEligible"] = True          # cached under a broader (prior) rule
    state["_stallTargets"] = []                  # …with nothing in the snapshot to justify it
    state["_stallChoices"] = ["accept-the-disclosed-risk", "hold"]
    state["step"] = RD.P_STALL
    action = RD._advance(state, state["config"])
    assert action["phase"] == RD.P_STALL, action
    assert action["payload"]["acceptRiskEligible"] is False
    assert "accept-the-disclosed-risk" not in action["payload"]["choices"]
    assert "hold" in action["payload"]["choices"]
    assert RD._stall_policy_class(state) == RD.review_gate_policy.STALL_CLASS_INELIGIBLE


def test_qualifying_snapshot_still_advertises_accept_risk_in_the_stall_menu():
    """A/B for the test above: a real CONFIRMED-with-evidence snapshot still offers the choice."""
    state, ident, _ = _stall_target_state()
    RD._handle_stall(state, state["config"], {"reason": "audit-stall",
                                              "detail": "x", "stalledIdentities": [ident]})
    assert state["_stallTargets"], "the fixture must leave a qualifying snapshot"
    action = RD._advance(state, state["config"])
    assert action["phase"] == RD.P_STALL, action
    assert action["payload"]["acceptRiskEligible"] is True
    assert "accept-the-disclosed-risk" in action["payload"]["choices"]
    assert RD._stall_policy_class(state) == RD.review_gate_policy.STALL_CLASS_ELIGIBLE


def test_stall_policy_class_ignores_the_cached_flag_without_a_snapshot():
    """Gate policy resolves on the snapshot too — the classifier and the fold agree by construction."""
    state = RD.new_state(_cfg())
    state["selfRecovered"] = True
    state["_acceptRiskEligible"] = True
    state["_stallTargets"] = [{"verdict": "PLAUSIBLE", "evidence": "ran"}]   # not CONFIRMED
    assert RD._stall_policy_class(state) == RD.review_gate_policy.STALL_CLASS_INELIGIBLE
    state["_stallTargets"] = [{"verdict": "CONFIRMED", "evidence": "ran"}]   # A/B
    assert RD._stall_policy_class(state) == RD.review_gate_policy.STALL_CLASS_ELIGIBLE


def test_accept_risk_submit_authorized_when_eligible(tmp_path):
    """accept-the-disclosed-risk with a qualifying snapshot is still accepted at submit."""
    d = str(tmp_path)
    state, ident, _ = _stall_target_state()
    RD._handle_stall(state, state["config"], {"reason": "audit-stall",
                                              "detail": "x", "stalledIdentities": [ident]})
    RD.save_state(d, state)
    n = RD.cmd_next(d)
    assert n["ok"]
    out = RD.cmd_submit(
        d, n["phase"], n["attempt"], n["expectedStateHash"],
        {"choice": "accept-the-disclosed-risk"})
    assert out["ok"] is True, out


def test_stall_choice_not_offered_refused_at_submit(tmp_path):
    """A choice absent from the presented menu is refused before fold — pending survives."""
    d = str(tmp_path)
    state = RD.new_state(_cfg())
    state["selfRecovered"] = True
    state["_oneMoreRoundUsed"] = True
    RD._handle_stall(state, state["config"], _STALL_BREAKER)
    assert "one-more-round" not in state["_stallChoices"]
    RD.save_state(d, state)
    n = RD.cmd_next(d)
    assert n["ok"]
    out = RD.cmd_submit(
        d, n["phase"], n["attempt"], n["expectedStateHash"], {"choice": "one-more-round"})
    assert out["ok"] is False
    assert out["reason"] == "stall-choice-not-offered:one-more-round"
    ok, reloaded = RD.load_state(d)
    assert ok and reloaded["step"] == RD.P_STALL


def test_unknown_stall_choice_fails_closed_to_stalled_terminal():
    """An unknown stall choice still parks as `stalled` — fail-closed, not converged."""
    state = RD.new_state(_cfg())
    state["selfRecovered"] = True
    state["_acceptRiskEligible"] = False
    state["_stallChoices"] = ["one-more-round", "hold"]
    RD._fold_stall(state, state["config"], {"choice": "ship-whenever"})
    assert state["terminal"] == "stalled"
    assert state["step"] == RD.P_TERMINAL
    assert state["certification"]["shape"] is None


def _stall_then_clean_auditor_seams(io=None, clean_after=2):
    """Auditor that not-discharges through `clean_after` audit calls, then discharges."""
    audit_calls = {"n": 0}
    counter = {"n": 0}

    def auditor(targets, rnd):
        audit_calls["n"] += 1
        ruling = "not-discharged" if audit_calls["n"] <= clean_after else "discharged"
        return [{"id": t["id"], "ruling": ruling,
                 "reason": "broken" if ruling == "not-discharged" else "fixed",
                 "evidence": "tests pass" if ruling == "discharged" else None,
                 "auditorVendor": t.get("auditorVendor")}
                for t in (targets or [])]

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [], "headDiff": _headf(counter["n"]), "changedSubjects": ["Code"]}

    def plaus_verifier(clusters, rnd):
        return [{"id": i, "verdict": "PLAUSIBLE"} for i in range(len(clusters or []))]

    seams = _seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verifier=plaus_verifier,
        auditor=auditor,
        fix_step=fix_step,
        io=io or {})
    seams["_audit_calls"] = audit_calls
    seams["_fix_calls"] = counter
    return seams


def test_audit_stall_clears_on_clean_round_then_certifies_converged():
    """#960: stall on audit round 2, clean fold on round 3, converged certification on round 4.

    Historical stall pairs must not permanently block certification once a later audit round
  folds clean."""
    seams = _stall_then_clean_auditor_seams(clean_after=2)
    receipt = RD.run_loop(seams, _cfg(maxRounds=20))
    assert receipt["verdict"] == "converged"
    assert receipt.get("certificationShape") is not None
    audit_rounds = [r for r in receipt["rounds"] if r.get("audits")]
    assert len(audit_rounds) >= 3
    assert any(r["round"] == 4 and r.get("audits") for r in receipt["rounds"])
    kinds = [d["kind"] for d in receipt["decisions"]]
    assert kinds.count("self-recovery") == 1


def test_one_more_round_reenters_fixer_then_certifies_converged():
    """#960: one-more-round re-enters dispatch-fixer, re-audits, discharges, and certifies."""
    fix_after_menu = {"n": 0}
    stall_menus = []

    def stall_menu(payload):
        stall_menus.append(dict(payload))
        return "one-more-round"

    base = _stall_then_clean_auditor_seams(io={"stall_menu": stall_menu}, clean_after=3)
    orig_fix = base["fix_step"]

    def fix_step(batch, rnd, payload):
        if stall_menus:
            fix_after_menu["n"] += 1
        return orig_fix(batch, rnd, payload)

    base["fix_step"] = fix_step
    receipt = RD.run_loop(base, _cfg(maxRounds=20))
    assert receipt["verdict"] == "converged"
    assert receipt.get("certificationShape") is not None
    assert len(stall_menus) == 1
    assert "one-more-round" in stall_menus[0]["choices"]
    assert fix_after_menu["n"] >= 1
    assert base["_audit_calls"]["n"] >= 4


def test_second_stall_menu_omits_one_more_round_after_one_more_round_spent():
    """#960: after one-more-round is spent, a second stall menu offers exactly two choices."""
    stall_menus = []

    def stall_menu(payload):
        stall_menus.append(dict(payload))
        return "one-more-round" if len(stall_menus) == 1 else "hold"

    counter = {"n": 0}

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [], "headDiff": _headf(counter["n"]), "changedSubjects": ["Code"]}

    seams = _seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=lambda targets, rnd: [{"id": t["id"], "ruling": "not-discharged", "reason": "broken"}
                                      for t in (targets or [])],
        fix_step=fix_step,
        io={"stall_menu": stall_menu})
    receipt = RD.run_loop(seams, _cfg(maxRounds=20))
    assert len(stall_menus) == 2
    assert "one-more-round" in stall_menus[0]["choices"]
    assert "one-more-round" not in stall_menus[1]["choices"]
    assert stall_menus[1]["choices"] == ["accept-the-disclosed-risk", "hold"]
    assert len(stall_menus[1]["choices"]) == 2
    assert receipt["verdict"] == "held"


def test_one_more_round_empty_stall_targets_parks_cannot_certify():
    state = RD.new_state(_cfg())
    state["selfRecovered"] = True
    state["_acceptRiskEligible"] = False
    state["_stallChoices"] = ["one-more-round", "hold"]
    state["_stallTargets"] = []
    RD._fold_stall(state, state["config"], {"choice": "one-more-round"})
    assert state["terminal"] == "cannot-certify"
    assert state["step"] == RD.P_TERMINAL


def test_stall_self_recovery_unknown_fixer_does_not_stamp_escalated_rung():
    """#608 review: unknown fixer → escalate returns None — must not set a truthy _escalatedRung."""
    state = RD.new_state({"leg": "code", "vendors": ["claude"]})
    assert state["config"]["fixerVendor"] is None
    RD._handle_stall(state, state["config"], _STALL_BREAKER)
    assert state["selfRecovered"] is True
    assert state["step"] == RD.P_FIXER
    assert state.get("_escalatedRung") is None
    # #620 R3a: the null-rung self-recovery decision detail must be honest — never "escalated to None".
    sr = [d for d in state["decisions"] if d["kind"] == "self-recovery"]
    assert len(sr) == 1
    assert "escalated to None" not in sr[0]["detail"]
    assert "no escalation rung available" in sr[0]["detail"]


def test_stall_self_recovery_known_fixer_stamps_escalated_rung():
    """#608 review contrast: known claude fixer at default sonnet-5/high has a next ladder rung."""
    state = RD.new_state({"leg": "code", "vendors": ["claude"], "fixerVendor": "claude"})
    RD._handle_stall(state, state["config"], _STALL_BREAKER)
    assert state["selfRecovered"] is True
    assert state["step"] == RD.P_FIXER
    escalated = state.get("_escalatedRung")
    assert escalated is not None
    assert escalated["rung"] is not None
    assert escalated["vendor"] == "claude"
    # #620 R3a contrast: on the real-rung path the detail names the actual escalation target.
    sr = [d for d in state["decisions"] if d["kind"] == "self-recovery"]
    assert len(sr) == 1
    assert ("fixer escalated to %r" % (escalated["rung"],)) in sr[0]["detail"]


def test_eligible_owner_acceptance_converges_end_to_end(tmp_path):
    """#507 v9: exercise the eligible owner-acceptance stall path to its terminal — an eligible
    CONFIRMED-with-receipt stall, the owner submits `accept-the-disclosed-risk`, and the run
    converges (terminal, certification note records the accepted disclosed risk). Guards against a
    mutation that makes an eligible acceptance hold/park instead of converge."""
    state, ident, _ = _stall_target_state()
    RD._handle_stall(state, state["config"], {"reason": "audit-stall", "detail": "x",
                                              "stalledIdentities": [ident]})
    assert state["_acceptRiskEligible"] is True
    RD._fold_stall(state, state["config"], {"choice": "accept-the-disclosed-risk"})
    assert state["terminal"] == "converged"
    assert state["step"] == RD.P_TERMINAL
    note = (state.get("certification") or {}).get("note") or ""
    assert "accepted the disclosed" in note, note


# =============================================================================
# confirmation economics: cap-parks-on-Critical, budget 2, re-arm
# =============================================================================

def _delta_state_ready(confirmations, surfaced, findings=None, not_discharged=None):
    state = RD.new_state(_cfg(maxRounds=20))
    state["confirmations"] = confirmations
    state["surfacedSinceLastPanel"] = list(surfaced)
    state["round"] = confirmations + 3
    state["findings"] = list(findings or [])
    state["fullPanelRan"] = False
    nd = not_discharged or []
    state["auditRounds"] = [{"round": 2, "outcomes": [{"identity": "x", "ruling": "discharged"}]}]
    state["_auditOutcome"] = {"notDischarged": nd, "discharged": ["x"]}
    state["_changedSubjects"] = ["Code"]
    return state


def test_capped_with_open_critical_parks(tmp_path):
    """A Critical still owed at the 2-panel confirmation cap parks (certification withheld)."""
    state = _delta_state_ready(confirmations=RD.MAX_CONFIRMATIONS, surfaced=["Critical"])
    RD._settle_delta(state, state["config"])
    assert state["terminal"] == "capped-with-open-critical"
    assert state["certification"]["shape"] is None


def test_non_critical_at_cap_certifies(tmp_path):
    """A non-Critical at the cap resolves by scoped verify → certifies (audited-chain)."""
    state = _delta_state_ready(confirmations=RD.MAX_CONFIRMATIONS, surfaced=["Important"])
    RD._settle_delta(state, state["config"])
    assert state["terminal"] == "converged"
    assert state["certification"]["shape"] == "audited-chain"


def test_critical_rearms_one_more_confirmation_under_budget(tmp_path):
    """A Critical surfaced with confirmations under the cap re-arms one more FULL panel."""
    state = _delta_state_ready(confirmations=0, surfaced=["Critical"])
    RD._settle_delta(state, state["config"])
    assert state["terminal"] is None  # not certified — a confirmation is owed
    assert state["step"] == RD.P_PANEL
    assert any(dd["kind"] == "confirmation-rearm" for dd in state["decisions"])


def test_confirmation_budget_two_respected_end_to_end(tmp_path):
    """A Critical surfaced by a delta scoped-finder re-arms a full panel; a subsequent clean panel
    certifies as full-panel-confirmed (one re-arm, budget not exceeded)."""
    scoped_state = {"fired": False}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "scoped-finder" and not scoped_state["fired"]:
            scoped_state["fired"] = True
            return [{"title": "hole", "severity": "Critical", "file": "f.py", "line": 1}]
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
        return []

    counter = {"n": 0}

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [], "headDiff": _headf_ns(counter["n"]), "changedSubjects": ["Code"]}

    receipt = RD.run_loop(_seams(reviewer=reviewer, fix_step=fix_step), _cfg(maxRounds=20))
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"] == "full-panel-confirmed"
    assert any(x["kind"] == "confirmation" for x in receipt["rounds"])


# =============================================================================
# big diff → sharded panel + gap-sweep; degraded independence; receipt-missing
# =============================================================================

def test_big_diff_shards_panel_with_wholediff_crosscutting_lenses(tmp_path):
    state = RD.new_state(_cfg(diff=_big_diff(25)))
    step = RD._advance(state, state["config"])
    payload = step["payload"]
    assert payload["big"] is True and "shards" in payload
    assert payload["shards"]["architecture-reviewer"]["wholeDiff"] is True
    assert payload["shards"]["premortem-reviewer"]["wholeDiff"] is True
    assert "shards" in payload["shards"]["code-reviewer"]  # a local lens gets sharded


def test_big_diff_schedules_gap_sweep(tmp_path):
    """A big diff schedules a gap-sweep after verification (before the fix leg)."""
    seen = {"gap": False}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "gap-sweep":
            seen["gap"] = True
            return []
        return []

    RD.run_loop(_seams(reviewer=reviewer), _cfg(diff=_big_diff(25)))
    assert seen["gap"] is True


def test_degraded_single_vendor_flows_to_certification_shape(tmp_path):
    receipt = RD.run_loop(_seams(reviewer=lambda dim, tier, rnd, ctx:
                                 ({"findings": [{"title": "bug", "severity": "Important",
                                                 "file": "f.py", "line": 1}]}
                                  if rnd == 1 and dim == "code-reviewer" else [])),
                          _cfg(vendors=["claude"], fixerVendor="claude"))
    assert receipt["certificationShape"] == "audited-chain-degraded"
    assert receipt["degraded"], "the lost independence must be named in the receipt"


def test_independent_auditor_selection_two_vendor(tmp_path):
    """#507 v8: with two live vendors the fix's auditor is the NON-fixer vendor (independent). The
    auditor seam captures its targets so the selection is asserted directly — a mutation that
    returns the fixer vendor as `auditorVendor` (losing independence) fails this test."""
    captured = {"targets": None}

    def auditor(targets, rnd):
        captured["targets"] = [dict(t) for t in (targets or [])]
        return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor")} for t in (targets or [])]

    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=auditor), _cfg(vendors=["claude", "codex"], fixerVendor="claude"))
    assert receipt["verdict"] == "converged"
    assert captured["targets"], "the auditor must have received the fix's audit targets"
    t = captured["targets"][0]
    assert t["fixerVendor"] == "claude"
    assert t["auditorVendor"] == "codex"
    assert t["independence"] == "independent"
    assert receipt["certificationShape"] == "audited-chain"  # NOT -degraded


def test_unknown_fixer_vendor_degraded_end_to_end_two_vendor(tmp_path):
    """#608: omitting fixerVendor must not assume claude — unknown fixer degrades, never false independent."""
    captured = {"targets": None}

    def auditor(targets, rnd):
        captured["targets"] = [dict(t) for t in (targets or [])]
        return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor")} for t in (targets or [])]

    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF}
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=auditor), cfg)
    assert receipt["verdict"] == "converged"
    assert captured["targets"]
    t = captured["targets"][0]
    assert t["fixerVendor"] is None
    assert t["independence"] == "degraded"
    assert t["auditorVendor"] == "claude"
    assert receipt["certificationShape"] == "audited-chain-degraded"
    assert receipt["degraded"], "the lost independence must be named in the receipt"


def test_explicit_cross_family_fixer_still_independent_two_vendor(tmp_path):
    """#608 contrast: known codex fixer with two vendors still yields independent audit."""
    captured = {"targets": None}

    def auditor(targets, rnd):
        captured["targets"] = [dict(t) for t in (targets or [])]
        return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor")} for t in (targets or [])]

    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "codex"}
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=auditor), cfg)
    assert receipt["verdict"] == "converged"
    t = captured["targets"][0]
    assert t["independence"] == "independent"
    assert receipt["certificationShape"] == "audited-chain"


def test_audit_result_from_wrong_vendor_is_not_discharged(tmp_path):
    """#507 WO-FIX-RECOVERY (audits): a clearing ruling that the ORCHESTRATOR's dispatch manifest
    does not authenticate is rejected as not-discharged + unauthenticated, so it can never certify a
    fix the independent auditor did not clear. The result's own echo authenticates nothing."""
    import audits
    target = {"id": "v0", "file": "f.py", "line": 1, "title": "bug", "severity": "Important",
              "fixerVendor": "claude", "auditorVendor": "codex", "independence": "independent"}
    # the fixer vendor tries to self-clear — echoing "claude" proves nothing (no manifest either)
    out = audits.apply_audit_results(
        [target], [{"id": "v0", "ruling": "discharged", "reason": "trust me",
                    "auditorVendor": "claude"}])
    assert out["discharged"] == []
    assert out["notDischarged"] == ["v0"]
    assert out["unauthenticated"] == ["v0"]
    # the orchestrator's manifest authenticates the codex dispatch → discharged, trusted vendor recorded
    ok = audits.apply_audit_results(
        [target], [{"id": "v0", "ruling": "discharged", "reason": "fix verified",
                    "auditorVendor": "codex"}],
        collection_manifest={"v0": "codex"})
    assert ok["discharged"] == ["v0"]
    assert ok["unauthenticated"] == []
    assert ok["audits"][0]["auditor"] == "codex"


def test_audit_round_outcomes_carry_class_keys_for_alias_stall(tmp_path):
    """#507 v0: the live audit-round outcomes carry classKey/dimension/taxonomy, so the audit-stall
    breaker's alias-tolerant match stalls a retitled-but-same-class not-discharged finding across
    two consecutive rounds (the contract `check_audit_breaker` advertises but the wire never fed)."""
    import circuit_breaker as CB
    state = RD.new_state(_cfg())
    f = {"title": "leaks memory", "severity": "Important", "file": "f.py", "line": 1,
         "dimension": "Security", "taxonomy": "CWE-401", "classKey": "Security::CWE-401::orig"}
    state["fixBatch"] = [f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tgt = state["_auditTargets"][0]
    assert tgt["classKey"] == "Security::CWE-401::orig"
    RD._fold_audits(state, state["config"], {"results": [
        {"id": tgt["id"], "ruling": "not-discharged", "reason": "still broken"}]})
    round1 = state["auditRounds"][-1]
    assert round1["outcomes"][0]["classKey"] == "Security::CWE-401::orig"
    # a SECOND round: the finding is retitled (a different identity) but keeps its classKey.
    retitled = {"round": state["round"] + 1, "outcomes": [
        {"identity": "f.py::memory not freed", "ruling": "not-discharged",
         "classKey": "Security::CWE-401::orig", "dimension": "Security", "taxonomy": "CWE-401"}]}
    brk = CB.check_audit_breaker([round1, retitled], 20)
    assert brk["halt"] and brk["reason"] == "audit-stall", brk


def test_audit_outcome_carries_title_so_distinct_classkeys_dont_false_stall(tmp_path):
    """#507 R2 v2: two DISTINCT classKeys that share dimension+taxonomy must NOT collide into a
    false audit-stall. The live outcome now carries `title`, so the breaker's canonical class key is
    the full `dim::tax::title`, not the title-less `dim::tax::` alias that merged unrelated findings."""
    import circuit_breaker as CB

    def fold(title, classkey):
        state = RD.new_state(_cfg())
        state["fixBatch"] = [{"title": title, "severity": "Important", "file": "f.py", "line": 1,
                              "dimension": "Security", "taxonomy": "CWE-401", "classKey": classkey}]
        state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
        tgt = state["_auditTargets"][0]
        RD._fold_audits(state, state["config"], {"results": [
            {"id": tgt["id"], "ruling": "not-discharged", "reason": "still broken"}]})
        return state["auditRounds"][-1]

    r1 = fold("secret a", "Security::CWE-401::secret a")
    assert r1["outcomes"][0]["title"] == "secret a"
    r2 = {"round": 2, "outcomes": fold("secret b", "Security::CWE-401::secret b")["outcomes"]}
    brk = CB.check_audit_breaker([r1, r2], 20)
    assert not brk["halt"], brk  # two distinct classKeys → NOT a stall


def test_omitted_seat_zero_finding_withholds_certification(tmp_path):
    """#507 R2 residual-1: an omitted panel seat with ZERO findings must WITHHOLD certification — an
    incomplete panel is 'we did not look', never a clean audited-chain. The converge parks."""
    def reviewer(dim, tier, rnd, ctx):
        return None if dim == "premortem-reviewer" else []

    receipt = RD.run_loop(_seams(reviewer=reviewer), _cfg())
    assert receipt["verdict"] == "cannot-certify"
    assert receipt["certificationShape"] is None


def test_incomplete_panel_flag_cleared_by_complete_panel():
    """The outstanding-coverage-gap flag arms on an incomplete panel and is CLEARED only when a
    complete panel re-establishes coverage (a scoped delta leaves it untouched)."""
    state = RD.new_state(_cfg())
    RD._fold_panel(state, state["config"], {"seats": {
        d: {"findings": []} for d in RD.DIMENSIONS if d != "premortem-reviewer"}})
    assert state["_incompletePanel"] is True
    state["round"] = 3
    RD._fold_panel(state, state["config"], {"seats": {d: {"findings": []} for d in RD.DIMENSIONS}})
    assert state["_incompletePanel"] is False


def test_verify_skip_with_configured_command_halts(tmp_path):
    """#507 R2 residual-2: a skip result while a REAL verify command is configured means the gate
    did NOT run — fail closed to halt, never advance unverified into a round that could certify."""
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "skipped"), _cfg(verifyCommand="pytest -q"))
    assert receipt["verdict"] == "halted"
    assert receipt["certificationShape"] is None


def test_verify_skip_with_no_command_still_advances(tmp_path):
    """A skip result with NO verify command configured is a legitimate unverified advance."""
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "none"), _cfg(verifyCommand="none"))
    assert receipt["verdict"] == "converged"


def test_new_blocker_does_not_drop_unresolved_target_at_different_line():
    """#507 R2 residual-3: a new blocker sharing a not-discharged target's file+title at a DIFFERENT
    line is a distinct finding — the union keys on (identity, line), so the unresolved target is
    NEVER dropped when the new blocker has the same line-less identity."""
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["_auditTargets"] = [{"id": "f.py::same bug", "file": "f.py", "line": 1,
                               "title": "same bug", "severity": "Important"}]
    state["_auditOutcome"] = {"notDischarged": ["f.py::same bug"], "discharged": []}
    state["auditRounds"] = [{"round": 2, "outcomes": [
        {"identity": "f.py::same bug", "ruling": "not-discharged"}]}]
    state["findings"] = [{"title": "same bug", "severity": "Important", "file": "f.py", "line": 2}]
    RD._settle_delta(state, state["config"])
    assert state["step"] == RD.P_FIXER
    assert sorted(b.get("line") for b in state["_fixBatch"]) == [1, 2]


def test_journal_append_records_fault_on_oserror(tmp_path):
    """#507 R2 residual-4: a journal append failure is NOT swallowed — it records a durable fault
    marker (the driver's ran-evidence lost an entry)."""
    d = str(tmp_path)
    os.mkdir(os.path.join(d, RD.JOURNAL_FILE))  # a dir where the file should be → append OSErrors
    RD._journal_append(d, {"cmd": "next", "phase": "dispatch-panel"})
    assert RD._journal_faulted(d) is True


def test_journal_fault_makes_finalize_park(tmp_path):
    """A recorded journal fault makes finalization fail closed (park) — the scriptRan evidence is
    incomplete, so the terminal never certifies over a partial-journal gap."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(round1_findings=None))  # a real terminal + valid receipt
    RD._mark_journal_fault(d, {"cmd": "submit", "phase": "run-verify"}, OSError("disk full"))
    ok, state = RD.load_state(d)
    fail = RD._finalize_receipt(d, state)
    assert fail and "journal" in fail and "park" in fail


def _guard_argv(session_dir, *, fresh=True, mode="branch", base_fetch="fetched", write_meta=True):
    """#648: the extra argv that satisfies the base guard for a CLI `next` on `session_dir`.

    Builds a real two-commit git repo under the session dir, writes meta.json pinned to the first
    commit, and — on fresh state — the real ``git diff <pin>...HEAD`` round-1 diff. Idempotent.
    """
    repo = os.path.join(session_dir, "_gitrepo")
    if not os.path.isdir(os.path.join(repo, ".git")):
        os.makedirs(repo, exist_ok=True)
        subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
        subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
        subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
        subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
        pin = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
        with open(os.path.join(repo, "f.py"), "w", encoding="utf-8") as fh:
            fh.write("a\n")
        subprocess.check_call(["git", "-C", repo, "add", "f.py"], cwd=repo)
        subprocess.check_call(["git", "-C", repo, "commit", "-q", "-m", "change"], cwd=repo)
    else:
        pin = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD~1"], text=True).strip()
    toplevel = subprocess.check_output(
        ["git", "-C", repo, "rev-parse", "--show-toplevel"], text=True).strip()
    meta_path = os.path.join(session_dir, "meta.json")
    if os.path.isfile(meta_path):
        meta = json.load(open(meta_path, encoding="utf-8"))
        if meta.get("baseRef"):
            pin = meta["baseRef"]
    meta = {"mode": mode, "baseRef": pin, "baseBranch": "main", "baseFetch": base_fetch,
            "repoRoot": toplevel}
    if write_meta:
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
    diffpath = os.path.join(session_dir, "round-1", "diff.txt")
    os.makedirs(os.path.dirname(diffpath), exist_ok=True)
    diff_text = subprocess.check_output(
        ["git", "-C", repo, "diff", "%s...HEAD" % pin], text=True)
    with open(diffpath, "w", encoding="utf-8") as fh:
        fh.write(diff_text)
    out = ["--repo-root", repo]
    if fresh:
        out += ["--diff-path", diffpath]
    return out


def test_journal_and_marker_both_unwritable_raises_unrecordable(tmp_path):
    """#507 WO-FIX-RECOVERY: when the journal AND its fault marker are BOTH unwritable there is no
    silent tier below the marker — `_journal_append` raises JournalFaultUnrecordable rather than
    swallowing (the R2 detectability gap one level down). Both writers fail: the target paths are
    directories, so each `open(..., "a")` raises OSError."""
    d = str(tmp_path)
    os.mkdir(os.path.join(d, RD.JOURNAL_FILE))        # journal append → OSError
    os.mkdir(os.path.join(d, RD.JOURNAL_FAULT_FILE))  # fault marker → OSError too
    with pytest.raises(RD.JournalFaultUnrecordable) as ei:
        RD._journal_append(d, {"cmd": "next", "phase": "dispatch-panel"})
    assert ei.value.journal_error is not None and ei.value.marker_error is not None


def test_cli_fails_loud_when_journal_fault_unrecordable(tmp_path, capsys):
    """The CLI invocation itself FAILS (nonzero) with reason `journal-fault-unrecordable` when both
    the journal and its fault marker are unwritable; the underlying errors go to stderr."""
    d = str(tmp_path)
    os.mkdir(os.path.join(d, RD.JOURNAL_FILE))
    os.mkdir(os.path.join(d, RD.JOURNAL_FAULT_FILE))
    rc = RD.main(["next", "--session-dir", d])
    assert rc == 1
    cap = capsys.readouterr()
    out = json.loads(cap.out.strip().splitlines()[-1])
    assert out["ok"] is False
    assert out["reason"] == "journal-fault-unrecordable"
    assert cap.err.strip()  # underlying errors reported to stderr


def test_run_loop_parks_cannot_certify_on_unrecordable_journal_fault():
    """#507 WO-FIX-RECOVERY: the library path never continues (or crashes the caller) on an
    unrecordable journal fault — run_loop parks cannot-certify. The last-resort exception is
    injected through a seam to exercise the loop's fail-closed guard."""
    def boom(*a, **k):
        raise RD.JournalFaultUnrecordable(OSError("journal"), OSError("marker"))
    receipt = RD.run_loop(_seams(reviewer=boom), _cfg())
    assert receipt["verdict"] == "cannot-certify"
    assert receipt["certification"]["shape"] is None
    assert "journal-fault-unrecordable" in receipt["certification"]["reason"]


# --- replayed-terminal receipt-fault re-check (#507) --------------------------------------------
# A REPLAYED terminal `next` (a `next` on a session already at its terminal step) re-emits the stored
# pending WITHOUT re-running _finalize_receipt — so a receipt fault recorded/surfaced AFTER the first
# emission (a fault marker, or a round-receipt.json corrupted/invalidated since) would be masked by
# the replay's ok. Every terminal `next` — first emission AND replays — now re-verifies the on-disk
# receipt and fails LOUD `receipt-fault` (nonzero) on any fault, never terminal-with-ok.

def _drive_to_terminating_submit(session_dir, cfg, respond, max_steps=80):
    """Drive next/submit until a submit's fold SETS the terminal, then STOP — WITHOUT calling the
    terminal `next`. Leaves the session at terminal with the receipt written by the terminating
    submit, so the caller can exercise the FIRST terminal `next` (e.g. after planting a fault)."""
    first = True
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        assert n["action"] != RD.P_TERMINAL, "reached the terminal `next` before a terminating submit"
        art = respond(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
        if s.get("nextStep") == RD.P_TERMINAL:
            return
    raise AssertionError("no terminating submit within %d steps" % max_steps)


def test_terminal_replay_with_intact_receipt_is_idempotent_ok(tmp_path):
    """A replayed terminal `next` with an intact on-disk receipt stays idempotent — same terminal
    payload, ok — the re-check adds no false alarm on a healthy receipt."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(round1_findings=None))  # terminal + valid receipt written
    replay = RD.cmd_next(d)
    assert replay["ok"] is True
    assert replay["action"] == RD.P_TERMINAL
    assert replay["payload"]["verdict"] == "converged"
    assert RD.main(["next", "--session-dir", d] + _guard_argv(d, fresh=False)) == 0


def test_terminal_replay_after_receipt_corrupted_on_disk_is_receipt_fault(tmp_path):
    """A replayed terminal `next` re-reads the receipt FRESH: a round-receipt.json corrupted on disk
    since the first emission is caught (not masked by the replay's ok) → nonzero receipt-fault."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(round1_findings=None))
    with open(os.path.join(d, RD.RECEIPT_FILE), "w", encoding="utf-8") as fh:
        fh.write("{ this is no longer valid json")
    replay = RD.cmd_next(d)
    assert replay["ok"] is False
    assert replay["reason"] == "receipt-fault"
    assert "unreadable" in replay["detail"]
    assert RD.main(["next", "--session-dir", d] + _guard_argv(d, fresh=False)) == 1


def test_terminal_replay_with_fault_marker_is_receipt_fault(tmp_path):
    """A replayed terminal `next` re-checks the durable journal-fault marker too — a fault recorded
    after the first emission is caught → nonzero receipt-fault, never masked by the replay."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(round1_findings=None))
    RD._mark_journal_fault(d, {"cmd": "submit", "phase": "run-verify"}, OSError("disk full"))
    rc = RD.main(["next", "--session-dir", d] + _guard_argv(d, fresh=False))
    assert rc == 1
    out = RD.cmd_next(d)
    assert out["ok"] is False
    assert out["reason"] == "receipt-fault"
    assert "journal" in out["detail"]


def test_first_terminal_emission_with_preexisting_fault_marker_is_receipt_fault(tmp_path):
    """No ordering hole: a fault marker present BEFORE the FIRST terminal `next` (planted after the
    terminating submit finalized) is caught by the terminal `next` re-verify → nonzero receipt-fault,
    not masked by the re-emit."""
    d = str(tmp_path)
    _drive_to_terminating_submit(d, _cfg(), _responder(round1_findings=None))
    RD._mark_journal_fault(d, {"cmd": "submit", "phase": "run-verify"}, OSError("disk full"))
    rc = RD.main(["next", "--session-dir", d] + _guard_argv(d, fresh=False))
    assert rc == 1
    out = RD.cmd_next(d)
    assert out["ok"] is False
    assert out["reason"] == "receipt-fault"
    assert "journal" in out["detail"]


def test_replay_next_after_failed_terminating_submit_stays_receipt_fault(tmp_path):
    """The codex-audit path: a receipt fault produced at the TERMINATING SUBMIT (here the receipt
    write itself fails) must be DURABLE — a later replayed `next` must NOT re-write the receipt from
    state and answer ok. Once finalized-with-fault, every subsequent invocation re-verifies from disk
    and keeps answering receipt-fault (nonzero), even after the transient write condition clears."""
    d = str(tmp_path)
    cfg = _cfg()
    respond = _responder(round1_findings=None)
    term = None
    first = True
    for _ in range(80):
        n = RD.cmd_next(d, cfg if first else None)
        first = False
        assert n["ok"], n
        assert n["action"] != RD.P_TERMINAL
        art = respond(n["phase"], n["payload"], n["round"])
        block = os.path.join(d, RD.RECEIPT_FILE)
        os.mkdir(block)  # os.replace onto a directory fails → the receipt WRITE OSErrors
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        os.rmdir(block)  # transient condition clears — a re-write WOULD now succeed (masking vector)
        if not s["ok"]:
            term = s
            break
    assert term is not None, "no terminating submit reached"
    assert term["reason"] == "receipt-fault"  # the terminating submit failed to write the receipt
    # a replayed `next` must NOT silently re-write the receipt from state and answer ok.
    replay = RD.cmd_next(d)
    assert replay["ok"] is False
    assert replay["reason"] == "receipt-fault"
    assert RD.main(["next", "--session-dir", d] + _guard_argv(d, fresh=False)) == 1
    assert RD.cmd_next(d)["reason"] == "receipt-fault"  # and again


def test_receipt_carries_audit_provenance_per_round(tmp_path):
    """The manifest-keyed audit-provenance boundary (LEDGERS §3) is visible in the receipt: a round
    that ran fix audits records `auditProvenance: collection-manifest`, and validate_receipt accepts
    the field (build_receipt must project it, not leave it recorded in state only)."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(
        round1_findings=[{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]))
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    provs = [r.get("auditProvenance") for r in receipt["rounds"]]
    assert "collection-manifest" in provs, provs
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason


# --- CLASS: every terminal-phase answer routes through the receipt gate (#507, third audit) --------
# The invariant: NO terminal-phase invocation may answer ok without a fresh on-disk receipt
# verification — first-emission next, replayed next, terminating submit, AND duplicate submit replay.

def _drive_capturing_terminating_submit(session_dir, plant_fault, max_steps=80):
    """Drive to the terminating submit and return (submit_args, submit_response). `submit_args` is the
    (phase, attempt, hash, artifact) tuple of the submit that reached terminal — replay it for the
    duplicate-submit path. When `plant_fault`, a durable journal fault marker is planted before every
    submit so the terminal receipt verifies FAULTED (inert on non-terminal submits — no finalize
    runs there; caught by the terminating submit's finalize)."""
    cfg = _cfg()
    respond = _responder(round1_findings=None)
    first = True
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        assert n["action"] != RD.P_TERMINAL
        art = respond(n["phase"], n["payload"], n["round"])
        args = (n["phase"], n["attempt"], n["expectedStateHash"], art)
        if plant_fault:
            RD._mark_journal_fault(session_dir, {"cmd": "submit", "phase": n["phase"]},
                                   OSError("disk full"))
        s = RD.cmd_submit(session_dir, *args)
        terminated = s.get("nextStep") == RD.P_TERMINAL or \
            (not s.get("ok") and s.get("reason") == "receipt-fault")
        if terminated:
            return args, s
    raise AssertionError("no terminating submit reached")


def _path_terminating_submit(d, plant_fault):
    _args, s = _drive_capturing_terminating_submit(d, plant_fault)
    return s


def _path_first_terminal_next(d, plant_fault):
    _drive_capturing_terminating_submit(d, plant_fault)
    return RD.cmd_next(d)


def _path_replayed_next(d, plant_fault):
    _drive_capturing_terminating_submit(d, plant_fault)
    RD.cmd_next(d)             # first terminal `next`
    return RD.cmd_next(d)      # the replay


def _path_duplicate_submit(d, plant_fault):
    args, _s = _drive_capturing_terminating_submit(d, plant_fault)
    return RD.cmd_submit(d, *args)  # re-send the terminating submit → duplicate replay


_TERMINAL_PATHS = [
    pytest.param(_path_terminating_submit, id="terminating-submit"),
    pytest.param(_path_first_terminal_next, id="first-terminal-next"),
    pytest.param(_path_replayed_next, id="replayed-next"),
    pytest.param(_path_duplicate_submit, id="duplicate-submit-replay"),
]


@pytest.mark.parametrize("path", _TERMINAL_PATHS)
def test_terminal_phase_answer_ok_on_intact_receipt(tmp_path, path):
    """Intact receipt → every terminal-phase answer path returns ok (the gate adds no false alarm)."""
    resp = path(str(tmp_path), plant_fault=False)
    assert resp["ok"] is True, resp


@pytest.mark.parametrize("path", _TERMINAL_PATHS)
def test_terminal_phase_answer_receipt_fault_on_persisted_fault(tmp_path, path):
    """Persisted fault → EVERY terminal-phase answer path (including the duplicate-submit replay)
    fails loud receipt-fault, never a masked ok — the CLASS the third audit demanded."""
    resp = path(str(tmp_path), plant_fault=True)
    assert resp["ok"] is False, resp
    assert resp["reason"] == "receipt-fault", resp


def test_duplicate_terminating_submit_fault_preserves_duplicate_flag_and_exits_nonzero(tmp_path):
    """The duplicate-submit replay at a persisted fault answers receipt-fault with the duplicate flag
    preserved (in the response AND the detail for honesty), and the CLI exits nonzero."""
    d = str(tmp_path)
    args, first = _drive_capturing_terminating_submit(d, plant_fault=True)
    assert first["ok"] is False and first["reason"] == "receipt-fault"
    phase, attempt, shash, artifact = args
    dup = RD.cmd_submit(d, *args)
    assert dup["ok"] is False
    assert dup["reason"] == "receipt-fault"
    assert dup["duplicate"] is True
    assert "duplicate" in dup["detail"]
    # nonzero exit through the CLI (submit via main, artifact from a file).
    art_path = os.path.join(d, "artifact.json")
    with open(art_path, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh)
    rc = RD.main(["submit", "--session-dir", d, "--phase", phase, "--attempt", str(attempt),
                  "--state-hash", shash, "--artifact", art_path])
    assert rc == 1


def test_changed_subjects_accumulate_across_delta_rounds_for_crosscut():
    """#507 R2 residual-5: cross-cutting rework accumulates across MULTIPLE post-panel delta fixes.
    Three delta fixes of one subject each cumulate to 3 distinct subjects → cross-cutting, even
    though no single fix is broad (the latest-only read under-fired)."""
    import review_round_policy as RRP
    state = RD.new_state(_cfg())
    RD._fold_panel(state, state["config"], {"seats": {d: {"findings": []} for d in RD.DIMENSIONS}})
    assert state["_changedSubjectsSincePanel"] == []
    for subj in (["Security"], ["Code"], ["Test"]):
        state["round"] = 2
        RD._fold_fixer(state, state["config"], {"fixes": [], "headDiff": HEAD},
                       lambda r, h, a, _s=subj: _s)
    assert sorted(state["_changedSubjectsSincePanel"]) == ["Code", "Security", "Test"]
    assert RRP.is_cross_cutting(state["_changedSubjectsSincePanel"]) is True


def test_panel_resets_accumulator_and_baseline_fix_excluded():
    """A full panel resets the cross-cutting accumulator (a broad fix BEFORE it does not count as the
    panel's rework), and a round-1 BASELINE fix never accumulates (it is not confirmation rework)."""
    # a broad ROUND-1 baseline fix is excluded
    state = RD.new_state(_cfg())
    RD._fold_panel(state, state["config"], {"seats": {d: {"findings": []} for d in RD.DIMENSIONS}})
    state["round"] = 1
    RD._fold_fixer(state, state["config"], {"fixes": [], "headDiff": HEAD},
                   lambda r, h, a: ["Code", "Security", "Test"])
    assert state["_changedSubjectsSincePanel"] == []
    # a broad delta fix accumulates, then a later panel resets it
    state["round"] = 2
    RD._fold_fixer(state, state["config"], {"fixes": [], "headDiff": HEAD},
                   lambda r, h, a: ["Code", "Security", "Test"])
    assert sorted(state["_changedSubjectsSincePanel"]) == ["Code", "Security", "Test"]
    state["round"] = 3
    RD._fold_panel(state, state["config"], {"seats": {d: {"findings": []} for d in RD.DIMENSIONS}})
    assert state["_changedSubjectsSincePanel"] == []


def test_fold_audits_authenticates_against_recorded_auditor(tmp_path):
    """#507 R2 residual-6: _fold_audits passes the DRIVER-recorded auditor map, so a clearing result
    echoing the FIXER vendor (a self-audit) is rejected not-discharged — the claimant echo never
    authenticates, and the recorded auditor is the trusted driver value."""
    state = RD.new_state(_cfg())  # vendors claude+codex, fixer claude → the auditor is codex
    state["round"] = 2
    state["fixBatch"] = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tgt = state["_auditTargets"][0]
    assert tgt["auditorVendor"] == "codex"
    RD._fold_audits(state, state["config"], {"results": [
        {"id": tgt["id"], "ruling": "discharged", "reason": "self-clear",
         "auditorVendor": "claude"}]})  # echoes the FIXER, not the recorded codex
    assert state["_auditOutcome"]["unauthenticated"] == [tgt["id"]]
    assert state["_auditOutcome"]["discharged"] == []


def test_judgment_dispositions_distinct_for_same_title_different_lines():
    """#507 R2 v5: two same-title tradeoff blockers at DIFFERENT lines get DISTINCT disposition ids,
    so a skip for the one never collides onto the other (the line-less id collapsed them)."""
    a = {"title": "same choice", "severity": "Important", "file": "f.py", "line": 10,
         "tradeoff": True}
    b = {"title": "same choice", "severity": "Important", "file": "f.py", "line": 20,
         "tradeoff": True}
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(a), dict(b)])
    step = RD._advance(state, state["config"])
    ids = [f["id"] for f in step["payload"]["findings"]]
    assert len(set(ids)) == 2, ids
    id_a, id_b = ids
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": id_a, "disposition": "fix-as-suggested"},
        {"id": id_b, "disposition": "skip", "reason": "defer the line-20 choice"}]})
    assert state["step"] == RD.P_FIXER
    assert [f["line"] for f in state["_fixBatch"]] == [10]
    assert [s["line"] for s in state["_skippedBlockers"]] == [20]


def test_fixer_vendor_flag_rejects_unknown_and_wires_fresh(tmp_path):
    """#507 R2 v4: --fixer-vendor sets the ACTUAL fixer so the auditor is seated as a DIFFERENT
    vendor. An unknown vendor or a non-fresh state fails loud (nonzero), never a silent default."""
    d = str(tmp_path)
    assert RD.main(["next", "--session-dir", d, "--fixer-vendor", "nope"]) == 1
    assert RD.main(["next", "--session-dir", d, "--fixer-vendor", "codex",
                    "--vendors", "codex,cursor"] + _guard_argv(d)) == 0
    ok, state = RD.load_state(d)
    assert ok and state["config"]["fixerVendor"] == "codex"
    # non-fresh: a later --fixer-vendor cannot take effect → rejected loud
    assert RD.main(["next", "--session-dir", d, "--fixer-vendor", "cursor"]) == 1


def test_receipt_missing_seat_surfaces_unverified(tmp_path):
    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "security-reviewer":
            return {"findings": [{"title": "leak", "severity": "Important",
                                  "file": "f.py", "line": 1}],
                    "receiptMissing": True}
        return []

    receipt = RD.run_loop(_seams(reviewer=reviewer,
                                 verifier=lambda cl, rnd: [{"id": i, "verdict": "PLAUSIBLE"}
                                                           for c in (cl or []) for i in c.get("ids", [])]),
                          _cfg())
    r1 = [x for x in receipt["rounds"] if x["round"] == 1][0]
    assert r1["unverified"], "a receipt-missing seat's findings ride the record as unverified"


# =============================================================================
# author-justification POST-filter
# =============================================================================

def test_author_justification_post_filter():
    findings = [
        {"id": "v0", "file": "f.py", "line": 10, "title": "confirmed", "severity": "Important",
         "verdict": "CONFIRMED", "evidence": "e"},
        {"id": "v1", "file": "f.py", "line": 20, "title": "plausible", "severity": "Minor",
         "verdict": "PLAUSIBLE"},
        {"id": "v2", "file": "f.py", "line": 30, "title": "noverdict", "severity": "Important"},
        {"id": "v3", "file": "f.py", "line": 40, "title": "bare", "severity": "Minor",
         "verdict": "PLAUSIBLE"},
    ]
    prior = [
        {"file": "f.py", "line": 10, "body": "Intentional per the caching ADR-7; see the doc."},
        {"file": "f.py", "line": 20, "body": "Deliberate: linter rule disabled repo-wide by policy."},
        {"file": "f.py", "line": 30, "body": "Known longstanding decision documented in the wiki."},
        {"file": "f.py", "line": 40, "body": "wontfix"},  # too short → not substantive
    ]
    kept, drops = RD.author_justification_filter(findings, prior)
    kept_ids = {f["id"] for f in kept}
    # CONFIRMED survives, stamped author-justified.
    assert "v0" in kept_ids
    assert next(f for f in kept if f["id"] == "v0")["challenge"] == "author-justified"
    # non-CONFIRMED with a substantive justification is dropped, justification quoted.
    assert [d["id"] for d in drops] == ["v1"]
    assert drops[0]["justification"]
    # a no-verdict finding is never dropped.
    assert "v2" in kept_ids
    # a non-substantive justification does not drop.
    assert "v3" in kept_ids


# =============================================================================
# receipt validator
# =============================================================================

def test_validate_receipt_round_trip_and_rejections(tmp_path):
    receipt = RD.run_loop(_seams(), _cfg())
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason
    # missing scriptRan rejected.
    missing_scriptran = dict(receipt)
    del missing_scriptran["scriptRan"]
    ok2, why2 = RD.validate_receipt(missing_scriptran)
    assert ok2 is False and "scriptRan" in why2
    # missing seat map rejected.
    missing_seatmap = dict(receipt)
    del missing_seatmap["seatMap"]
    ok3, why3 = RD.validate_receipt(missing_seatmap)
    assert ok3 is False and "seatMap" in why3
    # a non-dict receipt is rejected, never raises.
    assert RD.validate_receipt(None)[0] is False


# =============================================================================
# verify-gate fail halts; mechanical compile
# =============================================================================

def test_verify_fail_halts(tmp_path):
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "fail"), _cfg())
    assert receipt["verdict"] == "halted"
    assert receipt["certificationShape"] is None


def test_verify_timeout_halts(tmp_path):
    """#507 v10: a verify result that is not `pass`/skip — here `timeout` — fails closed to a halt,
    never advancing into a delta round that could certify."""
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "timeout"), _cfg())
    assert receipt["verdict"] == "halted"
    assert receipt["certificationShape"] is None


def test_omitted_panel_seat_cannot_certify_full_panel(tmp_path):
    """#507 v11: a configured dimension with NO seat in the panel artifact is a silent coverage gap
    → status `missing`, surfaced, and the clean finish can never be full-panel-confirmed."""
    def reviewer(dim, tier, rnd, ctx):
        if dim == "premortem-reviewer":
            return None  # omitted seat
        return []

    receipt = RD.run_loop(_seams(reviewer=reviewer), _cfg())
    assert receipt["certificationShape"] != "full-panel-confirmed"
    r1 = [x for x in receipt["rounds"] if x["round"] == 1][0]
    assert r1["seatStatus"]["premortem-reviewer"] == "missing"


def test_mechanical_compile_drops_uncited_and_out_of_scope():
    findings = [
        {"title": "cited", "severity": "Important", "file": "f.py", "line": 2},   # in diff scope
        {"title": "uncited", "severity": "Important", "file": None, "line": None},  # citation drop
        {"title": "off-scope", "severity": "Important", "file": "f.py", "line": 999},  # scope drop
    ]
    compiled, drops = RD.mechanical_compile(findings, DIFF)
    titles = {f.get("title") for f in compiled}
    assert "cited" in titles
    assert "uncited" not in titles and "off-scope" not in titles
    reasons = {d["reason"] for d in drops}
    assert any("uncited" in r for r in reasons)
    assert any("scope" in r for r in reasons)


def test_mechanical_compile_keeps_distinct_lines_same_title():
    """#507 v5: two findings sharing a title at DIFFERENT lines are distinct blockers and BOTH
    survive — the per-location anchor (file, line, title) no longer collapses them the way the
    line-less file::title identity did (it dropped the second line's blocker)."""
    findings = [
        {"title": "Same bug", "severity": "Important", "file": "f.py", "line": 1},
        {"title": "Same bug", "severity": "Important", "file": "f.py", "line": 2},
    ]
    compiled, _ = RD.mechanical_compile(findings, DIFF)
    assert sorted(f.get("line") for f in compiled) == [1, 2]


def test_mechanical_compile_nit_cap():
    findings = [{"title": "nit%d" % i, "severity": "Nit", "file": "f.py", "line": 1}
                for i in range(9)]
    compiled, _ = RD.mechanical_compile(findings, None)
    nits = [f for f in compiled if f.get("severity") == "Nit"]
    # 5 kept + 1 summary entry.
    assert sum(1 for f in nits if not f.get("summaryEntry")) <= RD._NIT_CAP
    assert any(f.get("summaryEntry") for f in nits)


def test_mechanical_compile_normalizes_list_dimension():
    findings = [
        {"title": "hole", "severity": "Important", "file": "f.py", "line": 2,
         "dimension": ["security", "perf"]},
    ]
    compiled, drops = RD.mechanical_compile(findings, DIFF)
    assert drops == []
    assert len(compiled) == 1
    assert compiled[0]["dimension"] == "security + perf"


def test_settle_delta_list_dimension_via_mechanical_compile(tmp_path):
    """#583: list-valued dimension must not crash _settle_delta's dim_map grouping."""
    raw = [{"title": "hole", "severity": "Important", "file": "f.py", "line": 2,
            "dimension": ["security", "perf"]}]
    compiled, _ = RD.mechanical_compile(raw, DIFF)
    state = _delta_state_ready(confirmations=0, surfaced=[], findings=compiled)
    RD._settle_delta(state, state["config"])
    record = (state.get("_records") or [])[-1]
    dim_map = record.get("dimensions") or {}
    assert dim_map
    assert all(isinstance(k, str) for k in dim_map)
    assert "security + perf" in dim_map


# =============================================================================
# the REDISPATCH_BUDGET single home (code-leg re-dispatch bound)
# =============================================================================

def test_reviewer_redispatch_bounded_by_single_home_budget(tmp_path):
    """A persistently receipt-missing reviewer is re-dispatched exactly REDISPATCH_BUDGET times,
    then recorded terminal `missing` (findings carried unverified). The budget read goes through
    loop_plan_common.REDISPATCH_BUDGET — the single home."""
    assert RD.REDISPATCH_BUDGET == LPC.REDISPATCH_BUDGET
    calls = {"n": 0}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "code-reviewer" and rnd == 1:
            calls["n"] += 1
            return {"findings": [], "receiptMissing": True}
        return []

    RD.run_loop(_seams(reviewer=reviewer), _cfg())
    # 1 initial dispatch + REDISPATCH_BUDGET re-dispatches for the persistently-missing seat.
    assert calls["n"] == 1 + RD.REDISPATCH_BUDGET


# =============================================================================
# #507 WO-D: challenged-coverage breaker + resume/records seam
# =============================================================================

_CHALLENGED_FINDING = {"title": "coverage decision is false", "severity": "Important",
                       "file": "f.py", "line": 1, "dimension": "Test", "taxonomy": "coverage",
                       "classKey": "Test::coverage::x"}


def test_challenged_coverage_recurrence_cannot_certify(tmp_path):
    """A coverage decision recorded on a principle the reviewer keeps raising (challenged) whose
    class RECURS parks (cannot-certify) — never a silent clean (the wrong_principle property)."""
    records = tmp_path / "round-records.json"
    records.write_text("[]")
    coverage = tmp_path / "coverage.json"

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "test-reviewer":
            return {"findings": [dict(_CHALLENGED_FINDING)]}
        if dim == "scoped-finder":
            return [dict(_CHALLENGED_FINDING)]
        return []

    def fix_step(batch, rnd, payload):
        return {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Test"],
                "coverageDecisions": [{"id": "RCD-x", "classKey": "Test::coverage::x"}]}

    receipt = RD.run_loop(
        _seams(reviewer=reviewer, fix_step=fix_step),
        _cfg(dimensions=["test-reviewer"], recordsPath=str(records),
             coveragePath=str(coverage), maxRounds=20))
    assert receipt["verdict"] == "cannot-certify"
    assert receipt["certificationShape"] is None
    assert any(d["kind"] == "cannot-certify" for d in receipt["decisions"])


def test_plain_recurring_finding_without_challenge_is_not_challenged_halt(tmp_path):
    """A recurring finding WITHOUT a challenged coverage decision is NOT parked by the challenged
    breaker (the driver's delta/audit path owns that case) — only the challenged path halts here."""
    records = tmp_path / "round-records.json"
    records.write_text("[]")

    fired = {"scoped": 0}

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "test-reviewer":
            return {"findings": [dict(_CHALLENGED_FINDING)]}
        if dim == "scoped-finder" and fired["scoped"] == 0:
            fired["scoped"] += 1
            return [dict(_CHALLENGED_FINDING)]
        return []

    # No coverageDecisions recorded → the recurring class is never "challenged". The fix's head diff
    # carries a real new surface so the scoped finder legitimately fires and re-raises the finding.
    def fix_step(batch, rnd, payload):
        return {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Test"]}

    receipt = RD.run_loop(
        _seams(reviewer=reviewer, fix_step=fix_step),
        _cfg(dimensions=["test-reviewer"], recordsPath=str(records), maxRounds=20))
    assert receipt["verdict"] != "cannot-certify"
    assert fired["scoped"] == 1, "the scoped finder must fire over the real new surface"


def test_corrupt_resume_records_cannot_certify(tmp_path):
    """A corrupt durable round-records file fails closed in the resume seam — cannot-certify park,
    never a run off unreadable memory."""
    records = tmp_path / "round-records.json"
    records.write_text("{corrupt not-a-list")
    receipt = RD.run_loop(_seams(), _cfg(recordsPath=str(records)))
    assert receipt["verdict"] == "cannot-certify"
    assert receipt["certificationShape"] is None


def test_resume_degraded_confirmation_runs_fresh_panel(tmp_path):
    """Resuming with a seeded DEGRADED (low-confidence) confirmation panel + a pending-confirmation
    marker owes a fresh full confirmation panel — the degraded seed cannot anchor certification."""
    records = tmp_path / "round-records.json"
    seed = [
        {"schemaVersion": 2, "round": 1, "kind": "baseline", "confirmationPending": True,
         "dimensions": {"test-reviewer": {"status": "run", "confidence": "high",
                                          "tier": "reviewer-deep", "findings": []}},
         "findings": [], "coverageDecisions": []},
        {"schemaVersion": 2, "round": 2, "kind": "confirmation", "confirmationPending": True,
         "dimensions": {"test-reviewer": {"status": "run", "confidence": "low",
                                          "tier": "reviewer-deep", "findings": []}},
         "findings": [], "coverageDecisions": []},
    ]
    records.write_text(json.dumps(seed))
    receipt = RD.run_loop(_seams(), _cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert receipt["verdict"] == "converged"
    # A fresh full confirmation panel ran at the resume round (3), certifying as a full panel —
    # NOT anchored on the degraded round-2 seed.
    assert receipt["certificationShape"] == "full-panel-confirmed"
    assert any(r["round"] == 3 for r in receipt["rounds"])
    assert any(d["kind"] == "resume-confirmation" for d in receipt["decisions"])


# =============================================================================
# #720: a `recordsPath` resume restores the per-round DISCLOSURE channels
# =============================================================================

# One populated value per channel in RESUMABLE_DISCLOSURE_CHANNELS, shaped exactly as `_fold_panel`
# records it. Used by the all-channel resume test; NOT a second copy of the channel list — the test
# asserts this map's keys equal the module constant's, so a new channel fails here too.
_ALL_CHANNELS = {
    "fellOpen": [{"seat": "test-reviewer", "configured": "codex", "reason": "forfeit",
                  "ran": "claude"}],
    "fellOpenProvenanceMissing": ["security-reviewer"],
    "seatMapUnavailable": ["codex"],
    "seatMapViolations": [{"constraint": "cross-vendor", "seat": "code-reviewer",
                           "evidence": "alternative-live"}],
    "vacuousSeats": ["architecture-reviewer"],
    "engagedArtifactSeats": ["premortem-reviewer"],
    "canaryUnverified": ["code-reviewer"],
    "canaryFailed": {"seats": ["security-reviewer"], "detail": "engaged not true",
                     "evidence": {"probe": "none"}},
    "canaryVerified": {"codex": {"probe": "engaged"}},
    "adapterProvenance": {"vendorEchoMismatch": [{"seat": "test-reviewer", "echo": "cursor",
                                                  "manifest": "codex"}]},
    "recordOrphansIgnored": ["code-reviewer"],
    "orderVendorProvenanceGaps": [{"seat": "architecture-reviewer",
                                   "storeKey": "architecture-reviewer", "occurrence": 0}],
}


def _seed_record(round_no, disclosures=None, **over):
    rec = {"schemaVersion": 2, "round": round_no, "kind": "baseline",
           "dimensions": {"test-reviewer": {"status": "run", "confidence": "high",
                                            "tier": "reviewer-deep", "findings": []}},
           "findings": [], "coverageDecisions": []}
    if disclosures is not None:
        rec["disclosures"] = disclosures
    rec.update(over)
    return rec


def _round_channels(receipt, round_no):
    """The disclosure channels the receipt's round entry actually carries."""
    entry = next((r for r in receipt["rounds"] if r["round"] == round_no), None)
    assert entry is not None, (
        "the receipt has no round %d entry at all — that round's disclosures were dropped "
        "(rounds present: %s)" % (round_no, [r["round"] for r in receipt["rounds"]]))
    return {k: v for k, v in entry.items() if k in RD.RESUMABLE_DISCLOSURE_CHANNELS}


def _round_disclosures(receipt, round_no):
    return [line for line in receipt["degraded"] if "(round %d)" % round_no in line]


def test_resume_restores_every_disclosure_channel_with_its_prose(tmp_path):
    """A resumed run's terminal receipt carries EVERY per-round disclosure channel the durable
    record holds, with the same disclosure prose an unbroken run emits (#720). Before the fix
    `_seed_resume` restored findings/coverage only, so `state["rounds"]` came back EMPTY and the
    receipt silently under-disclosed every pre-resume round."""
    assert set(_ALL_CHANNELS) == set(RD.RESUMABLE_DISCLOSURE_CHANNELS), \
        "this fixture must cover exactly the restorable channel set"
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1, dict(_ALL_CHANNELS))]))
    receipt = RD.run_loop(_seams(), _cfg(dimensions=["test-reviewer"], recordsPath=str(records)))

    assert _round_channels(receipt, 1) == _ALL_CHANNELS
    prose = "\n".join(_round_disclosures(receipt, 1))
    for marker in ("reviewer-fell-open (round 1): seat test-reviewer",
                     "reviewer-fell-open-provenance-unavailable (round 1): cross-vendor seat(s) "
                     "security-reviewer",
                     "reviewer-fell-open-seatmap-unavailable (round 1): live cross-vendor vendor(s) "
                     "codex",
                     "vacuous-seat (round 1): seat(s) architecture-reviewer",
                     "engaged-artifact-seat (round 1): seat(s) premortem-reviewer",
                     "canary-unverified (round 1): cross-vendor seat(s) code-reviewer",
                     "engaged probe recorded for vendor(s) codex",
                     "canary-failed (round 1): the control probe showed no engagement"):
        assert marker in prose, marker
    assert (
        "record-orphans-ignored (round 1): hand submit folded with durable seat record(s) "
        "code-reviewer still at this slot"
        in "\n".join(_round_disclosures(receipt, 1))
    )
    assert (
        "order-vendor-provenance-gap (round 1): seat(s) architecture-reviewer"
        in "\n".join(_round_disclosures(receipt, 1))
    )
    # adapter-provenance names the phase as `(round N, phase)` — outside the `(round 1)` filter.
    degraded_all = "\n".join(receipt["degraded"])
    assert ("adapter-provenance (round 1, unknown-phase): vendor echo mismatch"
            in degraded_all)
    # seatMapViolations is a BREACH channel: restoring it must reach the receipt's breach
    # disclosure, not just the round entry.
    assert any(line.startswith("seat-map constraint breach:") and "cross-vendor" in line
               for line in receipt["degraded"])


def _vacuous_round1_seams():
    """Round 1: one vacuous seat (a real `vacuousSeats` + `seatMapUnavailable` record) plus a
    blocking finding so the run continues past round 1 to a terminal."""
    finding = {"title": "bug", "severity": "Important", "file": "f.py", "line": 2,
               "dimension": "Code"}

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "test-reviewer":
            return {"vacuous": True, "findings": []}
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [dict(finding)]}
        return []

    def fix_step(batch, rnd, payload):
        return {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Code"]}

    return _seams(reviewer=reviewer, fix_step=fix_step)


def test_resumed_round_discloses_the_same_as_the_unbroken_run(tmp_path):
    """Disclosure EQUIVALENCE (#720): a run whose round 1 ran live and a run that resumes past that
    round off the durable record emit the SAME round-1 channels and the SAME round-1 disclosure
    prose. Not merely "the key exists" — the receipt content is compared line for line."""
    unbroken = RD.run_loop(
        _vacuous_round1_seams(),
        _cfg(dimensions=["test-reviewer", "code-reviewer"], maxRounds=8))
    live_channels = _round_channels(unbroken, 1)
    live_prose = _round_disclosures(unbroken, 1)
    assert live_channels and live_prose, "the unbroken run must actually disclose something"

    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1, dict(live_channels), kind="baseline")]))
    resumed = RD.run_loop(
        _seams(), _cfg(dimensions=["test-reviewer", "code-reviewer"],
                       recordsPath=str(records), maxRounds=8))

    assert _round_channels(resumed, 1) == live_channels
    assert _round_disclosures(resumed, 1) == live_prose


def test_resume_without_a_disclosure_block_adds_no_round_entry(tmp_path):
    """An OLDER records file (no `disclosures`) resumes exactly as before — no crash, and no
    fabricated round entry or empty channel. Absence must never read as "checked and clean"."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1)]))
    state = RD.new_state(_cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert state["rounds"] == {}
    assert state["round"] == 2
    receipt = RD.run_loop(_seams(), _cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert not any(r["round"] == 1 for r in receipt["rounds"])
    assert receipt["verdict"]


def test_resume_drops_a_wrong_typed_channel_and_still_resumes(tmp_path):
    """FAIL-CLOSED edge: a channel whose durable value has the wrong type (a string where a list
    belongs, a list where a dict belongs) is DROPPED — never restored as a truthy channel that
    would emit a false disclosure — while the round's well-shaped channels still resume."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1, {
        "vacuousSeats": "architecture-reviewer",          # str, not a list of str
        "fellOpen": ["not-a-row"],                         # list of str, not list of dict
        "canaryFailed": ["security-reviewer"],             # list, not a dict
        "canaryVerified": ["codex"],                       # list, not a vendor->evidence dict
        "seatMapUnavailable": ["codex"],                   # well-shaped — survives
        "orderVendorProvenanceGaps": [{"seat": 7}],        # int seat — malformed
    })]))
    state = RD.new_state(_cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert state["rounds"] == {"1": {"seatMapUnavailable": ["codex"]}}
    receipt = RD.run_loop(_seams(), _cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert _round_channels(receipt, 1) == {"seatMapUnavailable": ["codex"]}
    prose = "\n".join(_round_disclosures(receipt, 1))
    assert "vacuous-seat" not in prose and "canary-failed" not in prose
    assert "reviewer-fell-open (round 1)" not in prose
    assert "order-vendor-provenance-gap" not in prose


def test_malformed_order_vendor_gap_in_session_does_not_crash_receipt():
    """Malformed gap row recorded in-session is skipped at render; receipt still produced."""
    state = RD.new_state(_cfg(dimensions=["test-reviewer"]))
    state["rounds"] = {"1": {"orderVendorProvenanceGaps": [{"seat": 7}]}}
    receipt = RD.build_receipt(state)
    assert isinstance(receipt["degraded"], list)
    assert not any("order-vendor-provenance-gap" in line for line in receipt["degraded"])


def test_order_vendor_gap_missing_occurrence_still_valid():
    """occurrence is optional on gap rows — well-shaped without it."""
    gaps = [{"seat": "architecture-reviewer"}]
    assert RD.RESUMABLE_DISCLOSURE_CHANNELS["orderVendorProvenanceGaps"](gaps)
    state = RD.new_state(_cfg(dimensions=["test-reviewer"]))
    state["rounds"] = {"1": {"orderVendorProvenanceGaps": gaps}}
    receipt = RD.build_receipt(state)
    ovg_lines = [d for d in receipt["degraded"] if "order-vendor-provenance-gap" in d]
    assert len(ovg_lines) == 1
    assert "architecture-reviewer" in ovg_lines[0]


def test_order_vendor_gap_non_dict_row_rejected_on_resume(tmp_path):
    """A gap list containing a non-dict row is dropped on resume — no raise."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1, {
        "orderVendorProvenanceGaps": ["not-a-dict"],
    })]))
    state = RD.new_state(_cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert state.get("rounds", {}) == {}
    receipt = RD.build_receipt(state)
    assert isinstance(receipt["degraded"], list)


def test_resume_does_not_restore_an_empty_list_channel_as_a_disclosure(tmp_path):
    """FAIL-CLOSED edge: an EMPTY list channel is not a disclosure. `canaryVerified` is the one
    channel whose empty object `{}` still restores on key presence — see G item v21."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1, {
        "vacuousSeats": [], "fellOpen": [], "canaryFailed": {}, "seatMapViolations": [],
    })]))
    state = RD.new_state(_cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert state["rounds"] == {}
    receipt = RD.run_loop(_seams(), _cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert not any(r["round"] == 1 for r in receipt["rounds"])
    assert not any(line.startswith("seat-map constraint breach:") for line in receipt["degraded"])


def test_resume_restores_canary_verified_on_presence_even_when_empty(tmp_path):
    """`canaryVerified` emits on key presence: an empty object still means a control probe ran."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1, {"canaryVerified": {}})]))
    state = RD.new_state(_cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert state["rounds"]["1"]["canaryVerified"] == {}


def test_restored_channel_never_clobbers_a_live_round(tmp_path):
    """Restoration is ADDITIVE: a live post-resume round that records the same channel for the same
    round number wins, and the restore leaves every other key on that round entry untouched."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1, {"vacuousSeats": ["stale-seat"]})]))
    state = RD.new_state(_cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert state["rounds"]["1"] == {"vacuousSeats": ["stale-seat"]}
    state["round"] = 1
    RD._record_round(state, "vacuousSeats", ["live-seat"])
    RD._record_round(state, "blockingCount", 3)
    assert state["rounds"]["1"] == {"vacuousSeats": ["live-seat"], "blockingCount": 3}


def test_corrupt_resume_records_still_park_with_disclosures_present(tmp_path):
    """The corrupt-state fail-closed path is UNCHANGED by the disclosure restore: a mangled records
    file is `_resumeCorrupt` → cannot-certify park, never a partial restore off unreadable memory."""
    records = tmp_path / "round-records.json"
    records.write_text('[{"round": 1, "disclosures": {"vacuousSeats": ["x"]}')  # truncated JSON
    state = RD.new_state(_cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert state["_resumeCorrupt"]
    assert state["rounds"] == {}
    receipt = RD.run_loop(_seams(), _cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert receipt["verdict"] == "cannot-certify"
    assert receipt["certificationShape"] is None
    assert not any(r["round"] == 1 for r in receipt["rounds"])


def test_disclosure_block_survives_the_durable_skeleton(tmp_path):
    """The channels ride the record schema `review_memory` already models — a persisted round record
    keeps its `disclosures` block through skeletonization (which strips evidence bodies), and a
    record without one gains no key."""
    rm = _load("review_memory")
    rec = rm.record_from_dimension_results(
        1, "baseline", {"test-reviewer": {"status": "run", "findings": []}}, None, [], None,
        disclosures={"vacuousSeats": ["architecture-reviewer"]})
    assert rec["disclosures"] == {"vacuousSeats": ["architecture-reviewer"]}
    assert rm.summarize_record(rec)["disclosures"] == {"vacuousSeats": ["architecture-reviewer"]}
    assert "disclosures" not in rm.summarize_record(
        rm.record_from_dimension_results(1, "baseline", {}, None, [], None))


# --- the census: the channel set is closed BY CONSTRUCTION --------------------

def _round_driver_ast():
    import ast
    with open(os.path.join(_LIB, "round_driver.py"), encoding="utf-8") as fh:
        return ast.parse(fh.read()), ast


def _fn_node(tree, ast_mod, name):
    node = next((n for n in ast_mod.walk(tree)
                 if isinstance(n, ast_mod.FunctionDef) and n.name == name), None)
    assert node is not None, "round_driver has no function %r — the census parse is inert" % name
    return node


def test_panel_round_channels_are_all_accounted_for():
    """CENSUS (#720) — closes the set by construction, not by listing sites.

    Every per-round key `_fold_panel` records is enumerated FROM THE SOURCE with `ast` and must have
    exactly one module-level home: `RESUMABLE_DISCLOSURE_CHANNELS` (the channels `build_receipt`
    emits and a `recordsPath` resume restores) or `UNRESTORED_PANEL_ROUND_KEYS` (the deliberate
    not-restored list, each with its reason in the source). A NEW `_record_round` channel that ships
    without a resume path fails HERE — instead of silently under-disclosing every resumed run's
    terminal receipt, which is the defect this test exists to prevent recurring.
    """
    tree, ast_mod = _round_driver_ast()
    fold = _fn_node(tree, ast_mod, "_fold_panel")
    recorded = set()
    for node in ast_mod.walk(fold):
        if not (isinstance(node, ast_mod.Call) and isinstance(node.func, ast_mod.Name)
                and node.func.id == "_record_round"):
            continue
        assert len(node.args) >= 2, "_record_round must be called with (state, key, value)"
        key = node.args[1]
        assert isinstance(key, ast_mod.Constant) and isinstance(key.value, str), (
            "a _record_round key must be a string LITERAL so the census can enumerate it")
        recorded.add(key.value)
    assert len(recorded) >= 9, "the census enumerated %d keys — the parse looks inert" % len(recorded)

    fold_provenance = set(RD.FOLD_PROVENANCE_DISCLOSURE_CHANNELS)
    submit_disclosure = set(RD.SUBMIT_DISCLOSURE_CHANNELS)
    order_emission = set(RD.ORDER_EMISSION_DISCLOSURE_CHANNELS)
    restorable = set(RD.RESUMABLE_DISCLOSURE_CHANNELS)
    unrestored = set(RD.UNRESTORED_PANEL_ROUND_KEYS)
    assert fold_provenance <= restorable, (
        "fold provenance channels must be restorable: %s"
        % sorted(fold_provenance - restorable))
    assert submit_disclosure <= restorable, (
        "submit disclosure channels must be restorable: %s"
        % sorted(submit_disclosure - restorable))
    assert order_emission <= restorable, (
        "order-emission disclosure channels must be restorable: %s"
        % sorted(order_emission - restorable))
    assert not (restorable & unrestored), \
        "a channel cannot be both restorable and not-restored: %s" % sorted(restorable & unrestored)
    accounted = restorable | unrestored
    assert recorded | fold_provenance | submit_disclosure | order_emission == accounted, (
        "every per-round disclosure channel needs exactly one home — unaccounted (no resume path): %s; "
        "stale (named but no longer recorded): %s"
        % (sorted((recorded | fold_provenance | submit_disclosure | order_emission) - accounted),
           sorted(accounted - (recorded | fold_provenance | submit_disclosure | order_emission))))


def test_disclosure_channels_have_one_home_read_by_receipt_and_resume():
    """The census is the whole story only if `build_receipt` and the resume both READ the constant
    rather than a hand-copied literal list — and only if every named channel is really consumed by
    the receipt (a fossil channel would pass the census while disclosing nothing)."""
    tree, ast_mod = _round_driver_ast()
    for fn in ("build_receipt", "_restore_round_disclosures"):
        names = {n.id for n in ast_mod.walk(_fn_node(tree, ast_mod, fn))
                 if isinstance(n, ast_mod.Name)}
        assert "RESUMABLE_DISCLOSURE_CHANNELS" in names, \
            "%s must read the channel set from its one home" % fn
    with open(os.path.join(_LIB, "round_driver.py"), encoding="utf-8") as fh:
        src = fh.read()
    for chan in RD.RESUMABLE_DISCLOSURE_CHANNELS:
        assert source_obj_accesses_key(src, "rec|rrec", chan), \
            "%r is named restorable but no round record read consumes it" % chan


# =============================================================================
# git-derived changed subjects (#507 finding v2) — the confirmation re-arm's
# cross-cutting input is SCRIPT-computed from git, never the fixer's self-report
# =============================================================================

def _file_diff(name, n_lines, idx="1..2"):
    """A single-file unified diff adding `n_lines` right-side lines (parseable header)."""
    return ("diff --git a/{f} b/{f}\nindex {i} 100644\n--- a/{f}\n+++ b/{f}\n"
            "@@ -1 +1,{n} @@\n-old\n".format(f=name, i=idx, n=n_lines)
            + "".join("+l%d\n" % j for j in range(n_lines)))


def test_derive_changed_subjects_crosscutting_three_subjects():
    """Three files' sections differ between the reviewed diff and the head diff; the accumulated
    findings attribute them to three distinct policy subjects → cross-cutting (re-arm)."""
    reviewed = _file_diff("a.py", 2) + _file_diff("b.py", 2) + _file_diff("c.py", 2)
    head = _file_diff("a.py", 3) + _file_diff("b.py", 3) + _file_diff("c.py", 3)
    findings = [
        {"file": "a.py", "dimension": "Security"},
        {"file": "b.py", "dimension": "Code"},
        {"file": "c.py", "dimension": "Test"},
    ]
    subjects = RD.derive_changed_subjects(reviewed, head, findings)
    assert subjects == ["Code", "Security", "Test"]
    assert RD.review_round_policy.is_cross_cutting(subjects) is True


def test_derive_changed_subjects_narrow_single_subject_not_crosscutting():
    """One file changed, one subject → below the cross-cutting threshold (no re-arm)."""
    reviewed = _file_diff("a.py", 2)
    head = _file_diff("a.py", 3)
    findings = [{"file": "a.py", "dimension": "Code"}]
    subjects = RD.derive_changed_subjects(reviewed, head, findings)
    assert subjects == ["Code"]
    assert RD.review_round_policy.is_cross_cutting(subjects) is False


def test_derive_changed_subjects_unparseable_is_unknown_runs_everything():
    """A quoted-path / unparseable diff header → None (unknown surface). Unknown fails toward the
    run-everything rule: is_cross_cutting treats it as cross-cutting (one more confirmation)."""
    garbage = 'diff --git "a/x y.py" "b/x y.py"\n@@ -1 +1 @@\n-a\n+b\n'
    subjects = RD.derive_changed_subjects(garbage, _file_diff("a.py", 3),
                                          [{"file": "a.py", "dimension": "Code"}])
    assert subjects is None
    assert RD.review_round_policy.is_cross_cutting(subjects) is True


def test_fold_fixer_derives_subjects_from_git_not_self_report():
    """The fixer LIES (self-reports one narrow subject); the driver derives the real cross-cutting
    set from the reviewed-vs-head diff through the accumulated findings, ignoring the self-report."""
    state = RD.new_state(_cfg())
    state["reviewedDiff"] = (_file_diff("a.py", 2) + _file_diff("b.py", 2)
                             + _file_diff("c.py", 2))
    state["findings"] = [
        {"file": "a.py", "dimension": "Security"},
        {"file": "b.py", "dimension": "Code"},
        {"file": "c.py", "dimension": "Test"},
    ]
    head = _file_diff("a.py", 3) + _file_diff("b.py", 3) + _file_diff("c.py", 3)
    artifact = {"fixes": [], "headDiff": head, "changedSubjects": ["Code"]}
    RD._fold_fixer(state, state["config"], artifact)
    assert state["_changedSubjects"] == ["Code", "Security", "Test"]


def test_run_loop_uses_injected_changed_subjects_seam(tmp_path):
    """run_loop routes the derivation through the injected `changed_subjects` seam (the eval-harness
    pattern). A seam that returns a cross-cutting set re-arms a confirmation even though the fixer's
    self-report and the synthetic diff are narrow — proving the self-report is never consulted."""
    calls = []

    def changed_subjects(reviewed, head, accumulated):
        calls.append((reviewed, head, accumulated))
        return ["Security", "Code", "Test"]

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [{"title": "bug", "severity": "Important",
                                  "file": "f.py", "line": 1}]}
        return []

    seams = _seams(reviewer=reviewer)
    seams["changed_subjects"] = changed_subjects
    receipt = RD.run_loop(seams, _cfg(maxRounds=20))
    assert calls  # the seam was invoked (the self-report was never consulted)
    assert any(d["kind"] == "confirmation-rearm" for d in receipt["decisions"])


# =============================================================================
# #648 — CLI base guard (`next` only)
# =============================================================================

def _guard_repo_sha(session_dir):
    repo = os.path.join(session_dir, "_gitrepo")
    return subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()


def _cli_next_json(session_dir, extra_argv, capsys):
    rc = RD.main(["next", "--session-dir", session_dir] + list(extra_argv))
    cap = capsys.readouterr()
    lines = [ln for ln in cap.out.strip().splitlines() if ln.strip()]
    out = json.loads(lines[-1]) if lines else {}
    return rc, out


def test_base_guard_fresh_next_threads_pin(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(d)
    pin = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["baseRef"]
    assert ok and state["config"]["baseRef"] == pin


def test_base_guard_no_meta_refuses_no_state(tmp_path, capsys):
    d = str(tmp_path)
    repo = os.path.join(d, "_gitrepo")
    os.makedirs(repo, exist_ok=True)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    diffpath = os.path.join(d, "round-1", "diff.txt")
    os.makedirs(os.path.dirname(diffpath), exist_ok=True)
    with open(diffpath, "w", encoding="utf-8") as fh:
        fh.write(DIFF)
    rc, out = _cli_next_json(d, ["--repo-root", repo, "--diff-path", diffpath], capsys)
    assert rc == 1 and out["reason"] == "base-meta-unreadable"
    ok, state = RD.load_state(d)
    assert ok and state is None


@pytest.mark.parametrize("base_ref", ["", "null", "main"])
def test_base_guard_unpinned_refuses(tmp_path, capsys, base_ref):
    d = str(tmp_path)
    ga = _guard_argv(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta["baseRef"] = base_ref
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "base-not-pinned"


def test_base_guard_unresolved_sha_refuses(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta["baseRef"] = "0" * 40
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "base-unresolved"


def test_base_guard_round_diff_required(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    ga = [x for x in ga if x != "--diff-path" and not x.endswith("diff.txt")]
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-required"


def test_base_guard_round_diff_missing_file(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    ga[-1] = os.path.join(d, "no-such-diff.txt")
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-unreadable"


def test_base_guard_round_diff_empty(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    empty = os.path.join(d, "empty.txt")
    with open(empty, "w", encoding="utf-8") as fh:
        pass
    ga[-1] = empty
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-empty"


def test_base_guard_round_diff_whitespace_only(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    ws = os.path.join(d, "ws.txt")
    with open(ws, "w", encoding="utf-8") as fh:
        fh.write("   \n\t\n")
    ga[-1] = ws
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-empty"


def test_base_guard_pin_moved_refuses(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(d)
    stored = state["config"]["baseRef"]
    repo = os.path.join(d, "_gitrepo")
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "two"], cwd=repo)
    sha2 = _guard_repo_sha(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta["baseRef"] = sha2
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    rc2, out2 = _cli_next_json(d, _guard_argv(d, fresh=False), capsys)
    assert rc2 == 1 and out2["reason"] == "base-pin-moved"
    ok2, state2 = RD.load_state(d)
    assert state2["config"]["baseRef"] == stored


def test_base_guard_diff_path_on_non_fresh_refuses(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    rc, _ = _cli_next_json(d, ga, capsys)
    assert rc == 0
    rc2, out2 = _cli_next_json(d, ga, capsys)
    assert rc2 == 1 and out2["reason"] == "diff-path-not-fresh-state"


def test_base_guard_pr_repo_mismatch(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d, mode="pr")
    repo = os.path.join(d, "_gitrepo")
    subprocess.check_call(["git", "remote", "add", "origin", "git@github.com:acme/widget.git"],
                          cwd=repo)
    with open(os.path.join(d, "pr.json"), "w", encoding="utf-8") as fh:
        json.dump({"url": "https://github.com/otherorg/widget/pull/7"}, fh)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "base-repo-mismatch"


def test_base_guard_pr_repo_match(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d, mode="pr")
    repo = os.path.join(d, "_gitrepo")
    subprocess.check_call(["git", "remote", "add", "origin", "git@github.com:acme/widget.git"],
                          cwd=repo)
    with open(os.path.join(d, "pr.json"), "w", encoding="utf-8") as fh:
        json.dump({"url": "https://github.com/acme/widget/pull/7"}, fh)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(d)
    assert state["config"]["baseRepoCheck"] == "matched"


def test_base_guard_refusal_is_journalled(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta["baseRef"] = ""
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    _cli_next_json(d, ga, capsys)
    journal = RD.read_journal(d)
    assert any(e.get("outcome") == "refused-base-guard" and e.get("reason") == "base-not-pinned"
               for e in journal)


def test_base_guard_receipt_carries_base_block(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    pin = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["baseRef"]
    for _ in range(80):
        n = RD.cmd_next(d)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            break
        art = _responder(round1_findings=None)(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["base"]["baseRef"] == pin
    assert receipt["baseGuard"] == "checked-stat-bound"
    assert receipt["base"]["diffBinding"] == "file-set+line-counts"
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason


def test_base_guard_wrong_base_diff_refuses_no_state(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    repo = os.path.join(d, "_gitrepo")
    pin = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["baseRef"]
    good = subprocess.check_output(["git", "-C", repo, "diff", "%s...HEAD" % pin], text=True)
    bad = os.path.join(d, "wrong-diff.txt")
    extra = (
        "\ndiff --git a/extra b/extra\nnew file mode 100644\n--- /dev/null\n+++ b/extra\n"
        "@@ -0,0 +1 @@\n+contam\n"
    )
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write(good + extra)
    ga = [x if not x.endswith("diff.txt") else bad for x in ga]
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-base-mismatch"
    ok, state = RD.load_state(d)
    assert ok and state is None


def test_base_guard_healthy_next_stat_bound_receipt(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d) + ["--vendors", "codex,cursor"]
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    pin = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["baseRef"]
    for _ in range(80):
        n = RD.cmd_next(d)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            break
        art = _responder(round1_findings=None)(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["baseGuard"] == "checked-stat-bound"
    assert receipt["base"]["diffBinding"] == "file-set+line-counts"
    assert receipt["certification"]["base"] == "fetched"
    assert not receipt["certificationShape"].endswith("-degraded")


def _guard_cli_to_terminal_receipt(d, capsys, guard_kwargs=None, next_extra=None):
    gkw = dict(guard_kwargs or {})
    ga = _guard_argv(d, **gkw)
    if next_extra:
        ga = ga + list(next_extra)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"], out
    for _ in range(80):
        n = RD.cmd_next(d)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            break
        art = _responder(round1_findings=None)(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        return json.load(fh)


def test_base_degraded_fetch_failed_cert_shape(tmp_path, capsys):
    d = str(tmp_path)
    bf = "fetch-failed (offline)"
    # Two-vendor pool is load-bearing: default single-vendor independence degradation
    # would satisfy -degraded even if base degradation were dropped from _cert_shape.
    receipt = _guard_cli_to_terminal_receipt(
        d, capsys, {"base_fetch": bf},
        next_extra=["--vendors", "codex,cursor"],
    )
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"].endswith("-degraded")
    assert receipt["certificationShape"].count("-degraded") == 1
    assert receipt["certification"]["independence"] == "independent"
    assert receipt["certification"]["base"] == "degraded"
    assert any("fetch-failed (offline)" in line for line in receipt["degraded"])


def test_base_degraded_absent_base_fetch(tmp_path, capsys):
    d = str(tmp_path)
    _guard_argv(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta.pop("baseFetch", None)
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    repo = os.path.join(d, "_gitrepo")
    diffpath = os.path.join(d, "round-1", "diff.txt")
    ga = ["--repo-root", repo, "--diff-path", diffpath]
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    for _ in range(80):
        n = RD.cmd_next(d)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            break
        art = _responder(round1_findings=None)(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["certification"]["base"] == "degraded"
    assert any("baseFetch absent" in line for line in receipt["degraded"])


def test_base_and_independence_both_degraded_one_suffix(tmp_path, capsys):
    d = str(tmp_path)
    receipt = _guard_cli_to_terminal_receipt(
        d, capsys, {"base_fetch": "fetch-failed (offline)"})
    assert receipt["certificationShape"].endswith("-degraded")
    assert receipt["certificationShape"].count("-degraded") == 1
    assert receipt["certification"]["independence"] == "degraded"
    assert receipt["certification"]["base"] == "degraded"


def test_base_degraded_does_not_false_claim_independence(tmp_path, capsys):
    d = str(tmp_path)
    receipt = _guard_cli_to_terminal_receipt(
        d, capsys,
        {"base_fetch": "fetch-failed (offline)"},
        next_extra=["--vendors", "codex,cursor"],
    )
    assert receipt["certificationShape"].endswith("-degraded")
    assert receipt["certification"]["independence"] == "independent"
    assert receipt["certification"]["base"] == "degraded"


def _panel_seat_map_with_same_family(seat="code-reviewer"):
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["degradations"] = [{
        "constraint": "same-family",
        "seat": seat,
        "reason": "seat %s seated the maker family claude — no alternative family is live" % seat,
    }]
    return seat_map


def test_same_family_seat_map_degrades_cert_shape():
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    seat_map_clean = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    receipt_clean = RD.run_loop(_seams(io={"seatMap": seat_map_clean}), cfg)
    assert receipt_clean["verdict"] == "converged"
    assert "-degraded" not in receipt_clean["certificationShape"]
    seat_map_deg = _panel_seat_map_with_same_family()
    receipt_deg = RD.run_loop(_seams(io={"seatMap": seat_map_deg}), cfg)
    assert receipt_deg["verdict"] == "converged"
    assert receipt_deg["certificationShape"] == receipt_clean["certificationShape"] + "-degraded"
    assert receipt_deg["certificationShape"].count("-degraded") == 1


def test_same_family_disclosed_in_receipt_degraded_list():
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    state["seatMap"] = _panel_seat_map_with_same_family("security-reviewer")
    state["terminal"] = "converged"
    state["certification"] = {"shape": "full-panel-confirmed-degraded", "independence": "independent",
                              "base": "not-checked"}
    receipt = RD.build_receipt(state)
    sf_lines = [d for d in receipt["degraded"] if d.startswith("panel independence:")]
    assert len(sf_lines) == 1
    assert "security-reviewer" in sf_lines[0]


def test_same_family_malformed_seat_map_is_safe():
    for sm in (None, {}, {"degradations": "not-a-list"},
               {"degradations": [None, 42, {"constraint": "other"}]}):
        state = {"seatMap": sm}
        assert RD._same_family_degraded(state) is False
        assert RD._same_family_seats(state) == []
    state_missing_seat = {"seatMap": {"degradations": [{"constraint": "same-family"}]}}
    assert RD._same_family_degraded(state_missing_seat) is True
    assert RD._same_family_seats(state_missing_seat) == ["unnamed-seat"]
    state_missing_seat["terminal"] = "converged"
    state_missing_seat["config"] = {}
    receipt = RD.build_receipt(state_missing_seat)
    assert any("unnamed-seat" in line for line in receipt["degraded"])


def test_same_family_does_not_clear_other_degradations():
    state = RD.new_state(_cfg(vendors=["claude"]))
    state["independenceDegraded"] = True
    state["seatMap"] = _panel_seat_map_with_same_family()
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-degraded")
    assert state["certification"]["independence"] == "degraded"
    receipt = RD.build_receipt(state)
    indep_lines = [d for d in receipt["degraded"] if d.startswith("independence:")]
    sf_lines = [d for d in receipt["degraded"] if d.startswith("panel independence:")]
    assert len(indep_lines) == 1
    assert len(sf_lines) == 1


def _seat_map_receipt_with_unexcused_maker_family():
    """Hand-built receipt-shaped map: all-claude panel (no canary gap) + unexcused breach."""
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["violations"] = [{"constraint": "maker-family", "seat": "code-reviewer"}]
    seat_map["degradations"] = []
    return seat_map


def test_seat_map_unexcused_violation_constraint_violated_cert_shape():
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    seat_map = _seat_map_receipt_with_unexcused_maker_family()
    SM = _load("seat_map")
    assert SM.unexcused_violations(seat_map)
    receipt = RD.run_loop(_seams(io={"seatMap": seat_map}), cfg)
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"].endswith("-constraint-violated")
    assert "-degraded" not in receipt["certificationShape"]
    assert receipt["certificationShape"].count("-constraint-violated") == 1


def test_seat_map_excused_only_violation_unchanged_cert_shape():
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    state_clean = RD.new_state(cfg)
    RD._terminal_converged(state_clean, cfg, full_panel=True)
    shape_clean = state_clean["certification"]["shape"]
    SM = _load("seat_map")
    m = SM.build(SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", "anthropic", 0)
    seat_map_excused = SM.to_receipt(m, "anthropic")
    state_excused = RD.new_state(cfg)
    state_excused["seatMap"] = seat_map_excused
    RD._terminal_converged(state_excused, cfg, full_panel=True)
    assert state_excused["certification"]["shape"] == shape_clean
    assert "-constraint-violated" not in state_excused["certification"]["shape"]


def test_seat_map_pin_excusal_degraded_shape_and_disclosure():
    SM = _load("seat_map")
    seats = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seats["violations"] = [{"constraint": "strong-tier", "seat": "security-reviewer"}]
    seats["liveVendors"] = ["claude", "codex", "cursor"]
    seats["livenessPinScoped"] = False
    seats["authorFamily"] = "xai"
    seats["seats"]["security-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5",
        "effort": "xhigh",
        "tier": "reviewer",
        "family": "anthropic",
        "source": "pinned",
    }
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    state = RD.new_state(cfg)
    state["seatMap"] = seats
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-degraded")
    assert "seat-pin" in state["certification"]["shapeDrivers"]
    receipt = RD.build_receipt(state)
    pin_lines = [d for d in receipt["degraded"] if d.startswith("seat-map pin excusal:")]
    assert len(pin_lines) == 1
    assert "security-reviewer" in pin_lines[0]
    assert SM.classify_violations(seats)["excusedByPin"]


def test_seat_map_unproven_liveness_shape_driver():
    SM = _load("seat_map")
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["violations"] = [{"constraint": "critical-diversity"}]
    seat_map["liveVendors"] = ["claude", "codex"]
    seat_map["authorFamily"] = "anthropic"
    assert SM.unexcused_violations(seat_map)[0].get("evidence") == "unproven-liveness"
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    state = RD.new_state(cfg)
    state["seatMap"] = seat_map
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert "unproven-liveness" in state["certification"]["shapeDrivers"]
    assert state["certification"]["shape"].endswith("-constraint-violated")


def test_certification_shape_drivers_lists_every_fired_channel():
    seat_map = _seat_map_receipt_with_unexcused_maker_family()
    seat_map = dict(seat_map)
    seat_map["degradations"] = list(seat_map.get("degradations") or []) + [{
        "constraint": "same-family",
        "seat": "code-reviewer",
        "reason": "test",
    }]
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    cfg["baseDegraded"] = True
    state = RD.new_state(cfg)
    state["independenceDegraded"] = True
    state["seatMap"] = seat_map
    RD._terminal_converged(state, state["config"], full_panel=True)
    drivers = state["certification"]["shapeDrivers"]
    assert drivers == ["base", "independence", "same-family", "seat-map-violation"]
    assert state["certification"]["shape"].endswith("-constraint-violated")
    assert state["certification"]["shape"].count("-degraded") == 0


def test_seat_map_violations_round_field_and_degraded_disclosure():
    seat_map = _seat_map_receipt_with_unexcused_maker_family()
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    receipt = RD.run_loop(_seams(io={"seatMap": seat_map}), cfg)
    r1 = receipt["rounds"][0]
    assert r1.get("seatMapViolations")
    viol_lines = [d for d in receipt["degraded"] if "constraint-violated" in d]
    assert len(viol_lines) == 1
    assert "maker-family" in viol_lines[0]


def test_seat_map_violations_e8_sticky_across_round_map_overwrite():
    seat_map_r1 = _seat_map_receipt_with_unexcused_maker_family()
    SM = _load("seat_map")
    clean = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    clean["violations"] = []
    clean["degradations"] = []
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    state["rounds"] = {
        "1": {"seatMapViolations": SM.unexcused_violations(seat_map_r1)},
    }
    state["seatMap"] = clean
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-constraint-violated")


def test_library_receipt_omits_base_not_checked(tmp_path):
    receipt = RD.run_loop(_seams(), _cfg())
    assert "base" not in receipt
    assert receipt["baseGuard"] == "not-checked"
    assert receipt["certification"]["base"] == "not-checked"
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason


def test_library_receipt_mode_without_cli_guard_stays_not_checked(tmp_path):
    """Guard-shaped config keys must not infer baseGuard=checked without the CLI guard."""
    receipt = RD.run_loop(_seams(), _cfg(mode="pr"))
    assert receipt["baseGuard"] == "not-checked"
    if "base" in receipt:
        assert receipt["baseGuard"] == "not-checked"


def test_certification_base_explicit_not_checked_token(tmp_path):
    state = {"config": {"baseGuard": "not-checked", "baseDegraded": False}}
    assert RD._certification_base(state) == "not-checked"


def test_base_guard_round_diff_malformed(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    bad = os.path.join(d, "bad.txt")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("fatal: bad revision 'null'\n")
    ga[-1] = bad
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-malformed"


def test_base_guard_repo_root_mismatch(tmp_path, capsys):
    d = str(tmp_path)
    other = os.path.join(d, "other-checkout")
    os.makedirs(other, exist_ok=True)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=other)
    ga = _guard_argv(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta["repoRoot"] = subprocess.check_output(
        ["git", "-C", other, "rev-parse", "--show-toplevel"], text=True).strip()
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "base-repo-root-mismatch"


def test_base_guard_terminal_replay_still_ok(tmp_path, capsys):
    """Lifecycle: a satisfied guard on replay must not disturb terminal replay."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(round1_findings=None))
    rc, out = _cli_next_json(d, _guard_argv(d, fresh=False), capsys)
    assert rc == 0 and out["ok"] and out["action"] == RD.P_TERMINAL


def test_v1_state_wins_over_base_guard(tmp_path, capsys):
    d = str(tmp_path)
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump({"schemaVersion": 1, "rounds": {}}, fh)
    rc, out = _cli_next_json(d, [], capsys)
    assert rc == 0 and out["ok"] is False and "fresh session dir" in out["reason"]


# =============================================================================
# #507 R1c — `--vendors` must fail LOUD, never fall through to the ["claude"] default
#
# A non-JSON `--vendors` (e.g. `codex,cursor`) used to hit json.loads's ValueError → `pass` → the
# fresh state silently kept the single-vendor default, so every audit selected the fixer's own
# vendor and stamped `degraded` — cross-vendor independence lost silently when two vendors are live.
# =============================================================================

def _run_main(argv, capsys):
    rc = RD.main(argv)
    out = capsys.readouterr().out.strip()
    return rc, (json.loads(out) if out else None)


def test_vendors_comma_form_accepted(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", " codex , cursor "]
                        + _guard_argv(d), capsys)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(d)
    assert ok and state["config"]["vendors"] == ["codex", "cursor"]
    # a two-vendor pool → the audit is independent, NOT the silent single-vendor degrade.
    assert state["independenceDegraded"] is False


def test_vendors_json_form_accepted(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", '["codex","cursor"]']
                        + _guard_argv(d), capsys)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(d)
    assert ok and state["config"]["vendors"] == ["codex", "cursor"]


def test_vendors_garbage_fails_loud_no_state(tmp_path, capsys):
    """Unparseable JSON (bracket form) → nonzero + `vendors-unparseable`, and NO state is written
    (never the old silent fall-through to a fresh single-vendor default)."""
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", '["codex"'], capsys)
    assert rc == 1 and out["ok"] is False and out["reason"] == "vendors-unparseable"
    ok, state = RD.load_state(d)
    assert ok and state is None  # nothing was created


def test_vendors_non_string_member_fails_loud(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", '["codex", 5]'], capsys)
    assert rc == 1 and out["reason"] == "vendors-unparseable"


def test_vendors_empty_result_fails_loud(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", " , "], capsys)
    assert rc == 1 and out["reason"] == "vendors-unparseable"


def test_vendors_unknown_fails_loud(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", "codex,acme"], capsys)
    assert rc == 1 and out["reason"] == "vendors-unknown: acme"


def test_vendors_on_existing_state_rejected(tmp_path, capsys):
    """`--vendors` on non-fresh state cannot take effect (config is read once at new_state) — reject
    loudly rather than silently ignore the flag."""
    d = str(tmp_path)
    rc0, _ = _run_main(["next", "--session-dir", d, "--vendors", "codex,cursor"]
                        + _guard_argv(d), capsys)
    assert rc0 == 0
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", "claude,codex"], capsys)
    assert rc == 1 and out["reason"] == "vendors-not-fresh-state"
    # the original pool is untouched
    ok, state = RD.load_state(d)
    assert state["config"]["vendors"] == ["codex", "cursor"]


def test_auditor_vendor_fixer_in_pool_is_independent():
    """Two-vendor pool, fixerVendor IN the pool → the auditor is the OTHER pool vendor, independent."""
    auditor, independence = RD._auditor_vendor({"vendors": ["claude", "codex"]}, "claude")
    assert auditor == "codex" and independence == "independent"


def test_auditor_vendor_fixer_outside_pool_is_independent():
    """#507 R1c: fixerVendor OUTSIDE the pool still yields an independent auditor — the first pool
    vendor, never the fixer. Pins the outside-pool branch explicitly."""
    auditor, independence = RD._auditor_vendor({"vendors": ["codex", "cursor"]}, "claude")
    assert auditor == "codex" and auditor != "claude" and independence == "independent"


def test_auditor_vendor_family_keyed_two_vendor_cross_family():
    """Family-keyed independence: openai != anthropic preserves cross-vendor selection."""
    assert RD._auditor_vendor({"vendors": ["claude", "codex"]}, "claude") == ("codex", "independent")


def test_auditor_vendor_family_keyed_single_vendor_same_family_degraded():
    """Single live vendor with same fixer/verifier family → degraded, never false independent."""
    assert RD._auditor_vendor({"vendors": ["claude"]}, "claude") == ("claude", "degraded")


# The #510-era `test_auditor_vendor_family_keyed_single_vendor_cross_family_independent` lived here.
# It asserted that a cursor-only env is cross-family (composer='cursor' vs grok='xai') and therefore
# independent. #651 (owner-ratified 2026-07-26) merged both cursor first-party models into the `xai`
# family, so that env is now same-family and DEGRADED. Its replacement —
# `test_cursor_fix_never_gets_an_independent_cursor_auditor`, at the end of this file — asserts the
# new expectation AND the cross-family branches the old test did not cover. One thing did go with
# it: that test was the only one reaching `_auditor_vendor`'s SECOND (same-vendor) loop on its
# `independent` return, and post-#651 no vendor can satisfy that branch — every vendor's
# `code-fixer` and `verifier` roles now resolve to the same family — so it is unreachable, not
# merely untested. #652 rider 4a deleted that loop; the invariant is pinned by
# test_verifier_and_code_fixer_families_match_per_vendor in test_model_registry.py.


def test_auditor_vendor_unknown_fixer_degraded():
    """#608: genuinely-unknown fixer vendor never yields a false-independent auditor stamp."""
    auditor, independence = RD._auditor_vendor({"vendors": ["claude", "codex"]}, None)
    assert auditor == "claude" and independence == "degraded"


def test_auditor_vendor_empty_string_fixer_degraded():
    """#608: empty-string fixer is unknown — same degraded path as None."""
    assert RD._auditor_vendor({"vendors": ["claude", "codex"]}, "")[1] == "degraded"


def test_auditor_vendor_family_keyed_pass1_prefers_different_cli():
    """Pass 1 picks a different CLI vendor for a cursor fix. Post-#651 the same-CLI candidate (grok)
    is same-family too, so codex is the only independent choice — pass 1 and pass 2 now agree here."""
    assert RD._auditor_vendor({"vendors": ["cursor", "codex"]}, "cursor") == ("codex", "independent")


def test_fixer_outside_pool_audits_independent_end_to_end(tmp_path):
    """The outside-pool independence threads through the whole loop to a non-degraded audited chain."""
    captured = {"targets": None}

    def auditor(targets, rnd):
        captured["targets"] = [dict(t) for t in (targets or [])]
        return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor")} for t in (targets or [])]

    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=auditor), _cfg(vendors=["codex", "cursor"], fixerVendor="claude"))
    assert receipt["verdict"] == "converged"
    t = captured["targets"][0]
    assert t["fixerVendor"] == "claude"
    assert t["auditorVendor"] == "codex" and t["auditorVendor"] != t["fixerVendor"]
    assert t["independence"] == "independent"


# =============================================================================
# the judgment gate is an INTERVENTION, not a terminal (#507 R2a)
# =============================================================================

_TRADEOFF = {"title": "widen the API", "severity": "Important",
             "file": "f.py", "line": 1, "tradeoff": True}
# The judgment disposition key is the per-LOCATION id (line-less finding_identity + line) so two
# same-title tradeoff blockers at different lines never collide (#507 R2 v5).
_TRADEOFF_ID = "f.py::widen the api@L1"


def test_judgment_payload_rows_carry_single_classification_literal():
    """Every present-judgment row must use the one classification literal the gate-policy enum assumes."""
    state = RD.new_state(_cfg())
    finding_b = {"title": "narrow the API", "severity": "Minor",
                 "file": "g.py", "line": 2, "tradeoff": True}
    state["_judgmentFindings"] = [dict(_TRADEOFF), finding_b]
    state["step"] = RD.P_JUDGMENT
    step = RD._advance(state, state["config"])
    classifications = {row["classification"] for row in step["payload"]["findings"]}
    assert classifications == {"judgment"}


def test_tradeoff_blocker_routes_to_judgment_not_stall():
    """A tradeoff/product-choice blocker routes to the present-judgment gate — NEVER the terminal
    stall menu (the R2a defect: the stall menu dead-ended it so it could never be fixed)."""
    state = RD.new_state(_cfg())
    took = RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    assert took is True
    assert state["step"] == RD.P_JUDGMENT and state["step"] != RD.P_STALL
    step = RD._advance(state, state["config"])
    assert step["action"] == RD.P_JUDGMENT
    fnd = step["payload"]["findings"]
    assert len(fnd) == 1 and fnd[0]["id"] == _TRADEOFF_ID
    assert fnd[0]["dispositions"] == list(RD.JUDGMENT_DISPOSITIONS)
    kinds = [d["kind"] for d in state["decisions"]]
    assert "judgment-gate" in kinds


def test_fix_as_suggested_folds_to_fixer_batch():
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    RD._fold_judgment(state, state["config"],
                      {"dispositions": [{"id": _TRADEOFF_ID, "disposition": "fix-as-suggested"}]})
    assert state["step"] == RD.P_FIXER
    batch = state["_fixBatch"]
    assert len(batch) == 1 and batch[0]["title"] == "widen the API"
    assert batch[0]["judgmentDisposition"] == "fix-as-suggested"


def test_fix_with_guidance_attaches_guidance():
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "fix-with-guidance",
         "guidance": "keep it backward compatible"}]})
    assert state["step"] == RD.P_FIXER
    b = state["_fixBatch"][0]
    assert b["judgmentDisposition"] == "fix-with-guidance"
    assert b["guidance"] == "keep it backward compatible"


def test_skip_with_reason_records_ledger_and_rides_disclosure():
    """A skip needs a citable reason: it lands in the decision ledger, rides the exit disclosure AND
    the dedicated top-level `skippedBlockers` channel. With nothing left to fix, the run converges —
    but CLEAN EXCEPT FOR SKIPPED, never a plain success (the reason leads with clean-except-skipped)."""
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "shipping v1 narrow on purpose"}]})
    assert state["terminal"] == "converged"
    kinds = [d["kind"] for d in state["decisions"]]
    assert "judgment-skip" in kinds
    # the certification is non-plain: shape unchanged (audited-chain) but the reason leads with
    # the exit_skipped invariant marker.
    cert = state.get("certification") or {}
    assert cert.get("shape") == "audited-chain"
    assert (cert.get("reason") or "").startswith("clean-except-skipped: 1 blocker(s) skipped")
    assert "owner-skipped" in (cert.get("note") or "")
    receipt = RD.build_receipt(state)
    # top-level dedicated channel — id/title/severity/reason
    assert receipt["skippedBlockers"] == [
        {"id": _TRADEOFF_ID, "title": "widen the API", "severity": "Important",
         "reason": "shipping v1 narrow on purpose"}]
    # AND the degraded disclosure prose still names it
    assert any("skipped-blocker" in dd and "shipping v1 narrow" in dd
               for dd in receipt["degraded"])
    ok, _ = RD.validate_receipt(receipt)
    assert ok


def test_receipt_always_carries_skipped_blockers_channel():
    """Every terminal receipt carries the `skippedBlockers` list (empty when no skip) and
    validate_receipt REQUIRES it — the channel can never be omitted (exit_skipped invariant)."""
    receipt = RD.run_loop(_seams(), _cfg())
    assert receipt["verdict"] == "converged"
    assert receipt["skippedBlockers"] == []
    ok, _ = RD.validate_receipt(receipt)
    assert ok
    # a receipt with the channel stripped is rejected
    stripped = dict(receipt)
    del stripped["skippedBlockers"]
    ok2, why = RD.validate_receipt(stripped)
    assert not ok2 and "skippedBlockers" in why
    # a non-list channel is rejected too
    bad = dict(receipt)
    bad["skippedBlockers"] = None
    ok3, why3 = RD.validate_receipt(bad)
    assert not ok3 and "skippedBlockers" in why3


def test_partial_skip_end_to_end_marks_clean_except_skipped(tmp_path):
    """A run that fixes one judgment finding and skips another converges CLEAN EXCEPT FOR SKIPPED:
    the skipped one rides the top-level channel and the certification reason leads with the marker,
    even though real fix-and-audit work ran."""
    trade_a = {"title": "widen the API", "severity": "Important",
               "file": "f.py", "line": 1, "tradeoff": True}
    trade_b = {"title": "drop the flag", "severity": "Important",
               "file": "f.py", "line": 2, "tradeoff": True}

    def judgment_gate(payload):
        out = []
        for f in payload["findings"]:
            if f["id"] == "f.py::widen the api@L1":
                out.append({"id": f["id"], "disposition": "fix-as-suggested"})
            else:
                out.append({"id": f["id"], "disposition": "skip", "reason": "deferred to v2"})
        return {"dispositions": out}

    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [dict(trade_a), dict(trade_b)]}
             if rnd == 1 and dim == "code-reviewer" else []),
        io={"judgment_gate": judgment_gate}), _cfg())
    assert receipt["verdict"] == "converged"
    assert [s["title"] for s in receipt["skippedBlockers"]] == ["drop the flag"]
    reason = (receipt["certification"] or {}).get("reason") or ""
    assert reason.startswith("clean-except-skipped: 1 blocker(s) skipped")
    ok, _ = RD.validate_receipt(receipt)
    assert ok


def test_skip_without_reason_fails_closed_to_fix():
    """A skip with no citable reason is NOT honored — it fails closed to fix-as-suggested (a judgment
    blocker is never silently skipped)."""
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip"}]})
    assert state["step"] == RD.P_FIXER
    assert state["_fixBatch"][0]["judgmentFailClosed"] is True
    assert "judgment-fail-closed" in [d["kind"] for d in state["decisions"]]


def test_missing_or_unknown_disposition_fails_closed_to_fix():
    """A listed judgment finding with a MISSING disposition (or an UNKNOWN one) folds as
    fix-as-suggested, flagged failClosed — never silently skipped."""
    # missing: the artifact lists no disposition at all
    s1 = RD.new_state(_cfg())
    RD._route_judgment_blockers(s1, [dict(_TRADEOFF)])
    RD._fold_judgment(s1, s1["config"], {"dispositions": []})
    assert s1["step"] == RD.P_FIXER
    b1 = s1["_fixBatch"][0]
    assert b1["judgmentDisposition"] == "fix-as-suggested" and b1["judgmentFailClosed"] is True
    # unknown: a disposition string the gate does not recognize
    s2 = RD.new_state(_cfg())
    RD._route_judgment_blockers(s2, [dict(_TRADEOFF)])
    RD._fold_judgment(s2, s2["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "ship-it-anyway"}]})
    assert s2["step"] == RD.P_FIXER
    assert s2["_fixBatch"][0]["judgmentFailClosed"] is True


def test_mechanical_blocker_carried_through_judgment_gate():
    """A mechanical (non-tradeoff) blocker in the SAME batch is carried through the gate and rides
    the fix batch even when the tradeoff finding is skipped — never abandoned at the gate."""
    mech = {"title": "null deref", "severity": "Critical", "file": "f.py", "line": 2}
    state = RD.new_state(_cfg())
    took = RD._route_judgment_blockers(state, [mech, dict(_TRADEOFF)])
    assert took is True and state["step"] == RD.P_JUDGMENT
    # only the tradeoff finding is presented for judgment
    step = RD._advance(state, state["config"])
    assert [x["id"] for x in step["payload"]["findings"]] == [_TRADEOFF_ID]
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "deferred to v2"}]})
    assert state["step"] == RD.P_FIXER
    assert [b["title"] for b in state["_fixBatch"]] == ["null deref"]


def test_judgment_row_ids_occurrence_suffix_same_location():
    """Repeated tradeoff findings at the same location get distinct disposition ids (#1, #2, …)."""
    loc = RD._location_id(_TRADEOFF)
    findings = [dict(_TRADEOFF), dict(_TRADEOFF)]
    assert RD._judgment_row_ids(findings) == [loc, "%s#1" % loc]


def test_judgment_colliding_identity_different_severity_dispositions_not_collapse():
    """Two tradeoff findings at the same location with different severities must each receive their
    disposition — a skip for one must not silently override fix-as-suggested for a Critical."""
    loc_id = RD._location_id({"title": "same choice", "severity": "Critical",
                              "file": "f.py", "line": 10, "tradeoff": True})
    critical = {"title": "same choice", "severity": "Critical", "file": "f.py", "line": 10,
                "tradeoff": True}
    important = {"title": "same choice", "severity": "Important", "file": "f.py", "line": 10,
                 "tradeoff": True}
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(critical), dict(important)])
    step = RD._advance(state, state["config"])
    ids = [f["id"] for f in step["payload"]["findings"]]
    assert ids == [loc_id, "%s#1" % loc_id]
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": ids[0], "disposition": "fix-as-suggested"},
        {"id": ids[1], "disposition": "skip", "reason": "defer the important one"},
    ]})
    assert state["step"] == RD.P_FIXER
    assert [f["severity"] for f in state["_fixBatch"]] == ["Critical"]
    assert [s["severity"] for s in state["_skippedBlockers"]] == ["Important"]


def test_judgment_identical_disposition_same_id_collapses():
    """Two artifact entries with the same id and the same disposition collapse harmlessly."""
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "fix-as-suggested"},
        {"id": _TRADEOFF_ID, "disposition": "fix-as-suggested"},
    ]})
    assert state["step"] == RD.P_FIXER
    assert len(state["_fixBatch"]) == 1


def test_judgment_conflicting_dispositions_same_id_parks():
    """Colliding ids with conflicting dispositions park — never last-wins merge."""
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "fix-as-suggested"},
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "conflict"},
    ]})
    assert state["terminal"] == "cannot-certify"
    assert RD.JUDGMENT_DISPOSITION_COLLISION_CAUSE in (state["certification"]["reason"] or "")


def test_stall_menu_payload_carries_no_judgment_findings():
    """The stall menu is the audit-stall TERMINAL only — its payload never carries judgment
    findings (they route to present-judgment)."""
    state = RD.new_state(_cfg())
    state["findings"] = [{"id": "v0", "verdict": "PLAUSIBLE"}]
    state["selfRecovered"] = True
    RD._handle_stall(state, state["config"], {"reason": "audit-stall", "detail": "x",
                                              "stalledIdentities": ["v0"]})
    assert state["step"] == RD.P_STALL
    step = RD._advance(state, state["config"])
    assert set(step["payload"].keys()) == {"choices", "acceptRiskEligible"}
    assert "judgmentFindings" not in step["payload"]


def test_migrate_old_stall_routed_judgment_state(tmp_path):
    """#507 R2a migration: a state persisted under the OLD routing (a judgment blocker parked at the
    present-stall-menu terminal) is re-pointed to present-judgment on load, and `next` re-emits the
    judgment action from state under the new contract (schemaVersion stays 2)."""
    d = str(tmp_path)
    state = RD.new_state(_cfg())
    state["step"] = RD.P_STALL
    state["_judgmentFindings"] = [dict(_TRADEOFF)]
    state["_stallChoices"] = ["one-more-round", "hold"]
    state["_acceptRiskEligible"] = False
    state["pending"] = {"action": RD.P_STALL, "round": 1, "phase": RD.P_STALL,
                        "attempt": 0, "payload": {"choices": []}}
    RD.save_state(d, state)
    ok, loaded = RD.load_state(d)
    assert ok and loaded["step"] == RD.P_JUDGMENT and loaded["pending"] is None
    out = RD.cmd_next(d)
    assert out["ok"] and out["action"] == RD.P_JUDGMENT
    assert out["payload"]["findings"][0]["dispositions"] == list(RD.JUDGMENT_DISPOSITIONS)


def test_tradeoff_finding_reaches_audited_chain_end_to_end(tmp_path):
    """End-to-end: one tradeoff blocking finding routes to the judgment gate, the owner disposes it
    fix-as-suggested, and the run fixes-and-audits it to an audited-chain certification — the very
    path the R2a defect made unreachable."""
    disposed = []

    def judgment_gate(payload):
        disposed.append(payload)
        return {"dispositions": [{"id": f["id"], "disposition": "fix-as-suggested"}
                                 for f in payload["findings"]]}

    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [dict(_TRADEOFF)]} if rnd == 1 and dim == "code-reviewer" else []),
        io={"judgment_gate": judgment_gate}), _cfg())
    assert len(disposed) == 1 and disposed[0]["findings"][0]["id"] == _TRADEOFF_ID
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"] == "audited-chain"
    assert "judgment-gate" in [d["kind"] for d in receipt["decisions"]]
    ok, _ = RD.validate_receipt(receipt)
    assert ok
    assert receipt["certificationShape"] == "audited-chain"  # NOT -degraded


# =============================================================================
# #563 DoD1 — loud fall-open dispatch provenance (machinery)
# =============================================================================

def _seat_map_vendors(vendors):
    return {"seats": {d: {"vendor": v} for d, v in vendors.items()}}


def _all_run_status(dims=None):
    dims = dims or RD.DIMENSIONS
    return {d: "run" for d in dims}


def test_fell_open_rows_codex_configured_claude_ran():
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    rows, miss = RD._fell_open_rows(
        seat_map, {"code-reviewer": "claude"}, {"code-reviewer": "run"})
    assert rows == [{"seat": "code-reviewer", "configured": "codex", "ran": "claude",
                     "reason": "forfeit-fell-open"}]
    assert miss == []


def test_fell_open_rows_claude_configured_claude_ran_no_row():
    seat_map = _seat_map_vendors({"code-reviewer": "claude"})
    rows, miss = RD._fell_open_rows(
        seat_map, {"code-reviewer": "claude"}, {"code-reviewer": "run"})
    assert rows == [] and miss == []


def test_fell_open_rows_missing_seat_no_row_not_provenance_missing():
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    rows, miss = RD._fell_open_rows(
        seat_map, {"code-reviewer": "claude"}, {"code-reviewer": "missing"})
    assert rows == [] and miss == []


def test_fell_open_rows_cross_vendor_no_manifest_provenance_missing():
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    rows, miss = RD._fell_open_rows(seat_map, None, {"code-reviewer": "run"})
    assert rows == [] and miss == ["code-reviewer"]


def test_fell_open_rows_partial_manifest_missing_seat():
    seat_map = _seat_map_vendors({"code-reviewer": "codex", "security-reviewer": "cursor"})
    status = {"code-reviewer": "run", "security-reviewer": "run"}
    rows, miss = RD._fell_open_rows(seat_map, {"code-reviewer": "codex"}, status)
    assert rows == [] and miss == ["security-reviewer"]


def test_fell_open_rows_malformed_manifest_skipped_no_crash():
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    status = {"code-reviewer": "run"}
    rows, miss = RD._fell_open_rows(seat_map, {"code-reviewer": 123}, status)
    assert rows == [] and miss == ["code-reviewer"]
    rows, miss = RD._fell_open_rows(seat_map, {"code-reviewer": "bogus-vendor"}, status)
    assert rows == [] and miss == ["code-reviewer"]
    rows, miss = RD._fell_open_rows(
        seat_map, {"unknown-dimension": "claude", "code-reviewer": "codex"}, status)
    assert rows == [] and miss == []


def test_fell_open_rows_manifest_governs():
    """ranManifest alone decides fell-open rows — varying manifest entries changes the outcome."""
    # Fold-level in-seat ranVendor echo coverage: test_fell_open_in_seat_ran_vendor_echo_ignored_at_fold
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    status = {"code-reviewer": "run"}
    rows, miss = RD._fell_open_rows(seat_map, {"code-reviewer": "claude"}, status)
    assert rows and miss == []
    rows, miss = RD._fell_open_rows(seat_map, {"code-reviewer": "codex"}, status)
    assert rows == [] and miss == []


def test_fell_open_rows_absent_manifest_claude_only_no_disclosure_inputs():
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    rows, miss = RD._fell_open_rows(seat_map, None, _all_run_status())
    assert rows == [] and miss == []


def test_fell_open_panel_fold_receipt_disclosure():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {"code-reviewer": "claude"},
    })
    assert state["rounds"]["1"]["fellOpen"] == [
        {"seat": "code-reviewer", "configured": "codex", "ran": "claude", "reason": "forfeit-fell-open"}]
    receipt = RD.build_receipt(state)
    fo_lines = [d for d in receipt["degraded"] if "reviewer-fell-open (round 1):" in d]
    assert len(fo_lines) == 1
    assert "code-reviewer" in fo_lines[0]
    assert "codex" in fo_lines[0]
    assert "claude" in fo_lines[0]
    assert receipt["rounds"][0]["fellOpen"]


def test_fell_open_fold_receipt_provenance_unavailable_end_to_end():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {},
    })
    assert state["rounds"]["1"]["fellOpenProvenanceMissing"] == ["code-reviewer"]
    receipt = RD.build_receipt(state)
    prov_lines = [d for d in receipt["degraded"]
                  if d.startswith("reviewer-fell-open-provenance-unavailable")]
    assert len(prov_lines) == 1
    assert "code-reviewer" in prov_lines[0]


def test_fell_open_fold_receipt_seatmap_unavailable():
    state = RD.new_state(_cfg(leg="panel", vendors=["claude", "codex"]))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    RD._fold_panel(state, state["config"], {"seats": seats})
    assert state["rounds"]["1"]["seatMapUnavailable"] == ["codex"]
    receipt = RD.build_receipt(state)
    smu_lines = [d for d in receipt["degraded"]
                 if d.startswith("reviewer-fell-open-seatmap-unavailable")]
    assert len(smu_lines) == 1
    assert "codex" in smu_lines[0]


def test_fell_open_in_seat_ran_vendor_echo_ignored_at_fold():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [], "ranVendor": "claude"}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {"code-reviewer": "codex"},
    })
    assert "fellOpen" not in state["rounds"]["1"]


def test_fell_open_clean_claude_panel_no_manifest_degraded_unchanged(tmp_path):
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    receipt = RD.run_loop(_seams(io={"seatMap": seat_map}), _cfg(leg="panel"))
    assert not any(d.startswith("reviewer-fell-open") for d in receipt["degraded"])
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason


def test_fell_open_multi_seat_deterministic_disclosure_order():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({
        "architecture-reviewer": "claude",
        "code-reviewer": "codex",
        "security-reviewer": "cursor",
        "test-reviewer": "codex",
        "premortem-reviewer": "cursor",
    })
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {
            "code-reviewer": "claude",
            "security-reviewer": "claude",
        },
    })
    assert state["rounds"]["1"]["fellOpen"] == [
        {"seat": "code-reviewer", "configured": "codex", "ran": "claude",
         "reason": "forfeit-fell-open"},
        {"seat": "security-reviewer", "configured": "cursor", "ran": "claude",
         "reason": "forfeit-fell-open"},
    ]
    assert state["rounds"]["1"]["fellOpenProvenanceMissing"] == [
        "premortem-reviewer", "test-reviewer"]
    receipt = RD.build_receipt(state)
    fo_lines = [d for d in receipt["degraded"] if d.startswith("reviewer-fell-open (round")]
    assert len(fo_lines) == 2
    assert "code-reviewer" in fo_lines[0] and "codex" in fo_lines[0] and "claude" in fo_lines[0]
    assert "security-reviewer" in fo_lines[1] and "cursor" in fo_lines[1] and "claude" in fo_lines[1]
    prov_lines = [d for d in receipt["degraded"]
                  if d.startswith("reviewer-fell-open-provenance-unavailable")]
    assert len(prov_lines) == 1
    assert "premortem-reviewer, test-reviewer" in prov_lines[0]


def test_fell_open_two_rounds_deterministic_disclosure_order():
    state = RD.new_state(_cfg(leg="panel"))
    for rnd, dim in [(1, "code-reviewer"), (2, "security-reviewer")]:
        state["round"] = rnd
        seats = {d: {"findings": []} for d in RD.DIMENSIONS}
        seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
        seat_map["seats"][dim] = {"vendor": "codex"}
        RD._fold_panel(state, state["config"], {
            "seats": seats,
            "seatMap": seat_map,
            "ranManifest": {dim: "claude"},
        })
    receipt = RD.build_receipt(state)
    fo_lines = [d for d in receipt["degraded"] if d.startswith("reviewer-fell-open (round")]
    assert len(fo_lines) == 2
    assert "round 1" in fo_lines[0] and "code-reviewer" in fo_lines[0]
    assert "round 2" in fo_lines[1] and "security-reviewer" in fo_lines[1]


# =============================================================================
# #666 / #668 — vacuous seats + cross-vendor canary liveness (#668 cluster WO-4)
# =============================================================================

def _decision_kinds(state):
    return [d["kind"] for d in (state.get("decisions") or [])]


def test_vacuous_seat_vacuous_flag_classed_never_ran():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [], "vacuous": True}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "missing"
    assert state["rounds"]["1"]["vacuousSeats"] == ["code-reviewer"]
    assert state["fullPanelRan"] is False
    assert "seat-vacuous" in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["vacuousSeats"] == ["code-reviewer"]
    vac_lines = [d for d in receipt["degraded"] if d.startswith("vacuous-seat (round 1):")]
    assert len(vac_lines) == 1
    assert "code-reviewer" in vac_lines[0]


def test_forfeited_seat_reason_discriminant_classed_never_ran_not_vacuous():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [], "reason": "forfeited"}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "missing"
    assert "vacuousSeats" not in state["rounds"]["1"]
    assert "seat-vacuous" not in _decision_kinds(state)
    assert state["fullPanelRan"] is False


def test_engaged_artifact_seat_recorded_not_vacuous():
    """axis: seat credit — engaged-artifact seats are not classed vacuous."""
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {
        "findings": [],
        "reason": "forfeit-with-engaged-artifact",
        "disclosure": "not credited",
    }
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "missing"
    assert state["rounds"]["1"]["engagedArtifactSeats"] == ["code-reviewer"]
    assert "vacuousSeats" not in state["rounds"]["1"]
    assert "seat-engaged-artifact" in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["engagedArtifactSeats"] == ["code-reviewer"]
    eng_lines = [d for d in receipt["degraded"] if d.startswith("engaged-artifact-seat (round 1):")]
    assert len(eng_lines) == 1
    assert "code-reviewer" in eng_lines[0]


def test_vacuous_seat_reason_discriminant_classed_never_ran():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [], "reason": "vacuous"}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "missing"
    assert state["rounds"]["1"]["vacuousSeats"] == ["code-reviewer"]
    assert state["fullPanelRan"] is False
    assert "seat-vacuous" in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["vacuousSeats"] == ["code-reviewer"]
    vac_lines = [d for d in receipt["degraded"] if d.startswith("vacuous-seat (round 1):")]
    assert len(vac_lines) == 1


def test_clean_claude_panel_empty_findings_not_vacuous():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert "vacuousSeats" not in state["rounds"]["1"]
    assert "seat-vacuous" not in _decision_kinds(state)
    assert state["fullPanelRan"] is True


def test_canary_unverified_when_cross_vendor_all_empty_no_probe():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["rounds"]["1"]["canaryUnverified"] == ["code-reviewer"]
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"
    assert state["fullPanelRan"] is False
    assert state["_incompletePanel"] is True
    assert "canary-unverified" in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["canaryUnverified"] == ["code-reviewer"]
    cu_lines = [d for d in receipt["degraded"] if d.startswith("canary-unverified (round 1):")]
    assert len(cu_lines) == 1
    assert "code-reviewer" in cu_lines[0]


def test_canary_failed_downgrades_cross_vendor_seats():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
        "evidence": {"tokens": 0}, "detectedPlant": False, "detail": "no engagement",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "missing"
    assert state["fullPanelRan"] is False
    assert "canaryFailed" in state["rounds"]["1"]
    assert "canary-failed" in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    cf_lines = [d for d in receipt["degraded"] if d.startswith("canary-failed (round 1):")]
    assert len(cf_lines) == 1
    assert "code-reviewer" in cf_lines[0]


def test_canary_verified_cross_vendor_empty_stays_run():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 14980}, "detectedPlant": False, "detail": "live",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"
    assert state["fullPanelRan"] is True
    assert state["rounds"]["1"]["canaryVerified"] == {"tokens": 14980}
    assert "canary-verified" not in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["canaryVerified"] == {"tokens": 14980}
    assert not any("canary-" in d for d in receipt["degraded"])


def test_canary_plant_miss_does_not_block_verification():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {}, "detectedPlant": False, "detail": "live but missed plant",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"
    assert state["fullPanelRan"] is True
    assert "canaryVerified" in state["rounds"]["1"]
    receipt = RD.build_receipt(state)
    assert not any("canary-" in d for d in receipt["degraded"])


def test_canary_per_vendor_codex_finding_cursor_empty_still_unverified():
    """Round-3 Critical: panel-wide emptiness must not suppress another vendor's probe."""
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [{"title": "issue", "severity": "Minor"}]}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    r1 = state["rounds"]["1"]
    assert sorted(r1["canaryUnverified"]) == ["security-reviewer"]
    assert "canaryVerified" not in r1
    assert "canaryFailed" not in r1
    assert state["fullPanelRan"] is False
    assert "canary-unverified" in _decision_kinds(state)
    assert "panel-seat-missing" not in _decision_kinds(state)
    assert r1.get("missingSeats") is None or r1.get("missingSeats") == []


def test_canary_not_required_claude_only_empty_panel():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert "canaryUnverified" not in state["rounds"]["1"]
    assert "canary-unverified" not in _decision_kinds(state)


def test_canary_mixed_panel_only_codex_probed_cursor_unverified():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 100}, "detectedPlant": False, "detail": "live",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    r1 = state["rounds"]["1"]
    assert sorted(r1["canaryUnverified"]) == ["security-reviewer"]
    assert r1["canaryVerified"] == {"codex": {"tokens": 100}}
    assert r1["seatStatus"]["code-reviewer"] == "run"
    assert r1["seatStatus"]["security-reviewer"] == "run"
    assert state["fullPanelRan"] is False
    assert state["_incompletePanel"] is True
    assert "canaryFailed" not in r1
    receipt = RD.build_receipt(state)
    rr = receipt["rounds"][0]
    assert "canaryUnverified" in rr and "canaryVerified" in rr
    cu = [d for d in receipt["degraded"] if d.startswith("canary-unverified (round 1):")]
    assert len(cu) == 1
    assert "security-reviewer" in cu[0]
    assert not any(d.startswith("canary-failed") for d in receipt["degraded"])


def test_canary_list_two_engaged_probes_full_panel():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    canary = [
        {
            "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
            "evidence": {"tokens": 1}, "detectedPlant": False, "detail": "live",
        },
        {
            "engine": "cursor", "model": "c", "outcome": "ok", "engaged": True,
            "evidence": {"tokens": 2}, "detectedPlant": False, "detail": "live",
        },
    ]
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    r1 = state["rounds"]["1"]
    assert "canaryUnverified" not in r1
    assert "canaryFailed" not in r1
    assert r1["canaryVerified"] == {"codex": {"tokens": 1}, "cursor": {"tokens": 2}}
    assert state["fullPanelRan"] is True
    assert state["_incompletePanel"] is False
    receipt = RD.build_receipt(state)
    assert not any("canary-" in d for d in receipt["degraded"])


def test_canary_engine_matches_no_panel_vendor_all_unverified():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    canary = {
        "engine": "cursor", "model": "c", "outcome": "ok", "engaged": True,
        "evidence": {}, "detectedPlant": False, "detail": "live",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    assert state["rounds"]["1"]["canaryUnverified"] == ["code-reviewer"]
    assert "canaryVerified" not in state["rounds"]["1"]
    assert state["fullPanelRan"] is False


def test_canary_malformed_result_not_dict_or_list():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    for bad in (None, "oops", 42):
        st = RD.new_state(_cfg(leg="panel"))
        RD._fold_panel(st, st["config"], {
            "seats": seats, "seatMap": seat_map, "canaryResult": bad,
        })
        assert st["rounds"]["1"]["canaryUnverified"] == ["code-reviewer"]
        assert st["fullPanelRan"] is False


def test_canary_list_ignores_non_dict_members():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map,
        "canaryResult": [None, "x", {
            "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
            "evidence": {"tokens": 9}, "detectedPlant": False, "detail": "live",
        }],
    })
    assert state["rounds"]["1"]["canaryVerified"] == {"tokens": 9}
    assert "canaryUnverified" not in state["rounds"]["1"]
    assert state["fullPanelRan"] is True


def test_canary_failed_one_vendor_only_downgrades_that_vendor_seats():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    seat_map["seats"]["test-reviewer"] = {"vendor": "codex"}
    canary = [
        {
            "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
            "evidence": {"tokens": 1}, "detectedPlant": False, "detail": "live",
        },
        {
            "engine": "cursor", "model": "c", "outcome": "vacuous", "engaged": False,
            "evidence": {}, "detectedPlant": False, "detail": "dead",
        },
    ]
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    r1 = state["rounds"]["1"]
    assert r1["seatStatus"]["code-reviewer"] == "run"
    assert r1["seatStatus"]["test-reviewer"] == "run"
    assert r1["seatStatus"]["security-reviewer"] == "missing"
    assert sorted(r1["canaryFailed"]["seats"]) == ["security-reviewer"]
    assert r1["canaryVerified"] == {"codex": {"tokens": 1}}
    assert state["fullPanelRan"] is False


def test_canary_liveness_duplicate_codex_probes_dead_both_orders():
    dims = list(RD.DIMENSIONS)
    seat_map = _seat_map_vendors({d: "claude" for d in dims})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seats = {d: {"findings": []} for d in dims}
    status = {d: "run" for d in dims}
    engaged = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 1}, "detectedPlant": False, "detail": "live",
    }
    failed = {
        "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
        "evidence": {"tokens": 0}, "detectedPlant": False, "detail": "dead",
    }
    for canary in ([engaged, failed], [failed, engaged]):
        out = RD.canary_liveness(dims, status, seats, seat_map, {}, canary)
        assert out["byVendor"]["codex"]["status"] == "dead"
        assert out["byDim"]["code-reviewer"] == "dead"


def test_canary_codex_configured_cursor_ran_needs_cursor_probe():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {"code-reviewer": "cursor"},
    })
    assert state["rounds"]["1"]["canaryUnverified"] == ["code-reviewer"]


def test_canary_failed_record_includes_evidence():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
        "evidence": {"tokens": 0, "toolCalls": 0}, "detectedPlant": False, "detail": "no engagement",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    cf = state["rounds"]["1"]["canaryFailed"]
    assert cf["evidence"] == {"tokens": 0, "toolCalls": 0}
    assert cf["detail"] == "no engagement"


def test_canary_only_unverified_no_panel_seat_missing_decision():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    r1 = state["rounds"]["1"]
    assert "canaryUnverified" in r1
    assert "panel-seat-missing" not in _decision_kinds(state)
    assert r1.get("missingSeats") is None or r1.get("missingSeats") == []


def test_fold_panel_malformed_reason_list_or_dict_classed_missing_no_raise():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    for bad_reason in (["forfeited"], {"code": "forfeited"}):
        st = RD.new_state(_cfg(leg="panel"))
        s = dict(seats)
        s["code-reviewer"] = {"findings": [], "reason": bad_reason}
        RD._fold_panel(st, st["config"], {"seats": s, "seatMap": seat_map})
        assert st["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"


def test_canary_liveness_no_in_scope_vendors_empty_by_vendor():
    dims = list(RD.DIMENSIONS)
    seat_map = _seat_map_vendors({d: "claude" for d in dims})
    out = RD.canary_liveness(dims, {d: "run" for d in dims}, {}, seat_map, {}, None)
    assert out["byVendor"] == {}
    assert all(out["byDim"].get(d) == "n/a" for d in dims)


def test_canary_mixed_panel_receipt_does_not_claim_no_probe_ran():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 100}, "detectedPlant": False, "detail": "live",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    receipt = RD.build_receipt(state)
    cu = [d for d in receipt["degraded"] if d.startswith("canary-unverified (round 1):")]
    assert len(cu) == 1
    line = cu[0].lower()
    assert "security-reviewer" in cu[0]
    assert "no control probe was run" not in line
    assert "every cross-vendor seat" not in line


def test_canary_fell_open_codex_configured_claude_ran_not_subject():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {"code-reviewer": "claude"},
    })
    r1 = state["rounds"]["1"]
    assert "canaryUnverified" not in r1
    assert "canaryVerified" not in r1
    assert "canaryFailed" not in r1
    assert "canary-unverified" not in _decision_kinds(state)
    assert state["fullPanelRan"] is True


def _codex_cross_vendor_canary_inputs(findings):
    dims = list(RD.DIMENSIONS)
    seat_map = _seat_map_vendors({d: "claude" for d in dims})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seats = {d: {"findings": []} for d in dims}
    seats["code-reviewer"] = {"findings": findings}
    status = {d: "run" for d in dims}
    return dims, status, seats, seat_map


@pytest.mark.parametrize("findings,expected_dim_status", [
    ([None], "unproven"),
    ("garbage", "unproven"),
    ([None, {"title": "x"}], "n/a"),
    ([{}], "n/a"),
    ([], "unproven"),
])
def test_canary_liveness_usable_findings_only_dicts_count(findings, expected_dim_status):
    dims, status, seats, seat_map = _codex_cross_vendor_canary_inputs(
        findings if isinstance(findings, list) else [])
    seats["code-reviewer"] = {"findings": findings}
    out = RD.canary_liveness(dims, status, seats, seat_map, {}, None)
    assert out["byDim"]["code-reviewer"] == expected_dim_status


def test_fold_panel_null_finding_cross_vendor_unverified_not_full_panel():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [None]}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    r1 = state["rounds"]["1"]
    assert r1["canaryUnverified"] == ["code-reviewer"]
    assert state["fullPanelRan"] is False
    assert "canary-unverified" in _decision_kinds(state)


def test_fold_panel_null_finding_review_record_dim_findings_match_fold():
    """Per-dimension review record must use _usable_findings, not raw seat.findings."""
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [None]}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    dim_map = state["_records"][-1]["dimensions"]
    assert dim_map["code-reviewer"]["findings"] == []


@pytest.mark.parametrize("dimensions", [
    1,
    [["code-reviewer"]],
    None,
    ["code-reviewer", 42],
])
def test_canary_liveness_malformed_dimensions_no_raise(dimensions):
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    out = RD.canary_liveness(
        dimensions, {"code-reviewer": "run"},
        {"code-reviewer": {"findings": []}}, seat_map, {}, None)
    assert isinstance(out, dict) and "byDim" in out and "byVendor" in out


def test_fold_panel_malformed_config_dimensions_no_raise():
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    for bad_dims in (1, [["code-reviewer"]], None, ["code-reviewer", 42]):
        st = RD.new_state(_cfg(leg="panel", dimensions=bad_dims))
        RD._fold_panel(st, st["config"], {"seats": seats, "seatMap": seat_map})
        assert st["rounds"]["1"]["canaryUnverified"] == ["code-reviewer"]
        assert st["fullPanelRan"] is False


def test_canary_verified_record_stable_two_engaged_probe_orders():
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    probe_a = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 1}, "detectedPlant": False, "detail": "alpha",
    }
    probe_b = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 2}, "detectedPlant": False, "detail": "beta",
    }
    records = []
    for canary in ([probe_a, probe_b], [probe_b, probe_a]):
        st = RD.new_state(_cfg(leg="panel"))
        RD._fold_panel(st, st["config"], {
            "seats": seats, "seatMap": seat_map, "canaryResult": canary,
        })
        records.append(st["rounds"]["1"]["canaryVerified"])
    assert records[0] == records[1]


def test_canary_failed_record_stable_two_failing_probe_orders():
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    probe_a = {
        "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
        "evidence": {"tokens": 0}, "detectedPlant": False, "detail": "alpha",
    }
    probe_b = {
        "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
        "evidence": {"tokens": 9}, "detectedPlant": False, "detail": "beta",
    }
    records = []
    for canary in ([probe_a, probe_b], [probe_b, probe_a]):
        st = RD.new_state(_cfg(leg="panel"))
        RD._fold_panel(st, st["config"], {
            "seats": seats, "seatMap": seat_map, "canaryResult": canary,
        })
        records.append(st["rounds"]["1"]["canaryFailed"])
    assert records[0] == records[1]


_RETIRED_RUN_CONFIG_KEYS = ("docMode", "fixerModel", "fixerEffort")
_ROUND_DRIVER_PATH = os.path.join(_LIB, "round_driver.py")


def test_run_config_retired_keys_census():
    """Unreachable run-config keys must not reappear as config reads in round_driver."""
    cfg_keys = set(RD._default_config().keys())
    retired_in_defaults = cfg_keys & set(_RETIRED_RUN_CONFIG_KEYS)
    assert not retired_in_defaults, (
        "retired keys in _default_config: %s" % sorted(retired_in_defaults))
    with open(_ROUND_DRIVER_PATH, encoding="utf-8") as fh:
        source = fh.read()
    violations = []
    for key in _RETIRED_RUN_CONFIG_KEYS:
        if source_obj_accesses_key(source, "config|cfg", key):
            violations.append(key)
    assert not violations, (
        "retired run-config keys read in round_driver.py: %s" % violations)


def _review_session_marker_setup(tmp_path):
    d = str(tmp_path / "session")
    os.makedirs(d)
    repo = os.path.join(d, "_gitrepo")
    os.makedirs(repo, exist_ok=True)
    subprocess.check_call(["git", "init", "-q", "-b", "review-branch"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    toplevel = subprocess.check_output(
        ["git", "-C", repo, "rev-parse", "--show-toplevel"], text=True).strip()
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump({"repoRoot": toplevel}, fh)
    sc = _load("store_core")
    gitdir = sc.get_worktree_gitdir(repo)
    marker_path = os.path.join(gitdir, RD.SIDECAR_DIRNAME, RD._REVIEW_SESSION_MARKER)
    return d, marker_path


def test_review_session_marker_writes_atomically(tmp_path, monkeypatch):
    d, marker_path = _review_session_marker_setup(tmp_path)
    calls = {"atomic": 0}
    dest_truncates = []

    orig_atomic = RD.round_commit.atomic_write_bytes

    def track_atomic(path, data):
        calls["atomic"] += 1
        return orig_atomic(path, data)

    orig_open = open

    def tracking_open(path, mode="r", *args, **kwargs):
        abspath = os.path.abspath(path)
        if abspath == os.path.abspath(marker_path) and "w" in mode:
            dest_truncates.append(abspath)
        return orig_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(RD.round_commit, "atomic_write_bytes", track_atomic)
    monkeypatch.setattr("builtins.open", tracking_open)
    RD._bootstrap_review_session_marker(d)
    assert calls["atomic"] == 1
    assert not dest_truncates
    assert os.path.isfile(marker_path)


def test_review_session_marker_atomic_replace_preserves_prior_on_failure(tmp_path, monkeypatch):
    d, marker_path = _review_session_marker_setup(tmp_path)
    os.makedirs(os.path.dirname(marker_path), exist_ok=True)
    sentinel = '{"schema":"review-session/1","prior":true}'
    with open(marker_path, "w", encoding="utf-8") as fh:
        fh.write(sentinel)

    def boom(path, data):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(RD.round_commit, "atomic_write_bytes", boom)
    RD._bootstrap_review_session_marker(d)
    with open(marker_path, encoding="utf-8") as fh:
        assert fh.read() == sentinel


def _next_marker_session_setup(tmp_path):
    d = str(tmp_path / "session")
    os.makedirs(d)
    repo = os.path.join(d, "_gitrepo")
    os.makedirs(repo, exist_ok=True)
    subprocess.check_call(["git", "init", "-q", "-b", "review-branch"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    toplevel = subprocess.check_output(
        ["git", "-C", repo, "rev-parse", "--show-toplevel"], text=True).strip()
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump({"repoRoot": toplevel}, fh)
    return d, repo


def test_next_bootstraps_review_session_marker(tmp_path):
    """Public cmd_next path must write the review-session scope marker (#624)."""
    d, repo = _next_marker_session_setup(tmp_path)
    n = RD.cmd_next(d, _cfg())
    assert n["ok"]
    sc = _load("store_core")
    gitdir = sc.get_worktree_gitdir(repo)
    marker_path = os.path.join(gitdir, RD.SIDECAR_DIRNAME, RD._REVIEW_SESSION_MARKER)
    assert os.path.isfile(marker_path)
    with open(marker_path, encoding="utf-8") as fh:
        marker = json.load(fh)
    assert marker["schema"] == RD._REVIEW_SESSION_SCHEMA
    assert marker["branch"] == "review-branch"
    assert marker["sessionDir"] == os.path.realpath(d)


def _legacy_sidecar_setup(tmp_path):
    RR = _load("round_records")
    sc = _load("store_core")
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    base_sha = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "feature"], cwd=repo)
    head_sha = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    session = str(tmp_path / "session")
    os.makedirs(session)
    receipt = {
        "schema": RD.RECEIPT_CERTIFIED_SCHEMA % 3,
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
    receipt_path = os.path.join(session, RD.RECEIPT_FILE)
    receipt_bytes = json.dumps(receipt).encode("utf-8")
    with open(receipt_path, "wb") as fh:
        fh.write(receipt_bytes)
    diff = subprocess.check_output(["git", "-C", repo, "diff", "%s...HEAD" % base_sha])
    sidecar = RR.build_sidecar(
        repoId="github.com/o/r",
        branch="main",
        headSha=head_sha,
        baseRef=base_sha,
        baseSha=base_sha,
        diffSha256=hashlib.sha256(diff).hexdigest(),
        verdict="converged",
        certificationShape="audited-chain",
        receiptPath=receipt_path,
        receiptSha256=hashlib.sha256(receipt_bytes).hexdigest(),
        policySha256="policy",
        sessionDir=session,
    )
    gitdir = sc.get_worktree_gitdir(repo)
    super_dir = os.path.join(gitdir, RD.SIDECAR_DIRNAME)
    os.makedirs(super_dir, exist_ok=True)
    sidecar_path = os.path.join(super_dir, RD.SIDECAR_FILE)
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    state = {
        "terminal": "converged",
        "config": {"repoRoot": repo, "baseRef": base_sha, "baseBranch": "main"},
        "reviewedDiff": "",
        "certification": {"shape": "audited-chain"},
    }
    return session, state, sidecar_path


def test_legacy_sidecar_base_ref_is_republished(tmp_path):
    """A car-4 sidecar with a commit id in baseRef must be rewritten to the branch-name contract."""
    session, state, sidecar_path = _legacy_sidecar_setup(tmp_path)
    with open(sidecar_path, encoding="utf-8") as fh:
        before = json.load(fh)
    assert len(before["baseRef"]) == 40
    prepared = RD._prepare_sidecar(session, state)
    assert prepared["ok"] is True and prepared["needs_write"] is True
    republished = json.loads(prepared["sidecar_bytes"].decode("utf-8"))
    assert republished["baseRef"] == "main"
    assert republished["baseSha"] == before["baseSha"]


def test_hex_named_branch_sidecar_not_republished(tmp_path):
    """A current-contract sidecar whose base branch is legitimately named as 40 lowercase hex must
    stay fresh — shape must not infer legacy semantics from the name alone."""
    RR = _load("round_records")
    sc = _load("store_core")
    hex_branch = "a" * 40
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    init_sha = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    subprocess.check_call(["git", "update-ref", "refs/heads/%s" % hex_branch, init_sha], cwd=repo)
    subprocess.check_call(["git", "checkout", "-q", "refs/heads/%s" % hex_branch], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "on-hex"], cwd=repo)
    head_sha = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    session = str(tmp_path / "session")
    os.makedirs(session)
    receipt = {
        "schema": RD.RECEIPT_CERTIFIED_SCHEMA % 3,
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
    receipt_path = os.path.join(session, RD.RECEIPT_FILE)
    receipt_bytes = json.dumps(receipt).encode("utf-8")
    with open(receipt_path, "wb") as fh:
        fh.write(receipt_bytes)
    diff = subprocess.check_output(["git", "-C", repo, "diff", "%s...HEAD" % init_sha])
    sidecar = RR.build_sidecar(
        repoId="github.com/o/r",
        branch=hex_branch,
        headSha=head_sha,
        baseRef=hex_branch,
        baseSha=head_sha,
        diffSha256=hashlib.sha256(diff).hexdigest(),
        verdict="converged",
        certificationShape="audited-chain",
        receiptPath=receipt_path,
        receiptSha256=hashlib.sha256(receipt_bytes).hexdigest(),
        policySha256="policy",
        sessionDir=session,
    )
    gitdir = sc.get_worktree_gitdir(repo)
    super_dir = os.path.join(gitdir, RD.SIDECAR_DIRNAME)
    os.makedirs(super_dir, exist_ok=True)
    sidecar_path = os.path.join(super_dir, RD.SIDECAR_FILE)
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    state = {
        "terminal": "converged",
        "config": {"repoRoot": repo, "baseBranch": hex_branch},
        "reviewedDiff": "",
        "certification": {"shape": "audited-chain"},
    }
    prepared = RD._prepare_sidecar(session, state)
    assert prepared["ok"] is True and prepared["needs_write"] is False


def test_legacy_sidecar_sha256_base_ref_is_republished(tmp_path):
    """A legacy sidecar whose baseRef holds a 64-hex SHA-256 object id must be repaired."""
    RR = _load("round_records")
    sc = _load("store_core")
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    base_sha = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    base_sha256 = hashlib.sha256(base_sha.encode()).hexdigest()
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "feature"], cwd=repo)
    head_sha = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    session = str(tmp_path / "session")
    os.makedirs(session)
    receipt = {
        "schema": RD.RECEIPT_CERTIFIED_SCHEMA % 3,
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
    receipt_path = os.path.join(session, RD.RECEIPT_FILE)
    receipt_bytes = json.dumps(receipt).encode("utf-8")
    with open(receipt_path, "wb") as fh:
        fh.write(receipt_bytes)
    diff = subprocess.check_output(["git", "-C", repo, "diff", "%s...HEAD" % base_sha])
    sidecar = RR.build_sidecar(
        repoId="github.com/o/r",
        branch="main",
        headSha=head_sha,
        baseRef=base_sha256,
        baseSha=base_sha,
        diffSha256=hashlib.sha256(diff).hexdigest(),
        verdict="converged",
        certificationShape="audited-chain",
        receiptPath=receipt_path,
        receiptSha256=hashlib.sha256(receipt_bytes).hexdigest(),
        policySha256="policy",
        sessionDir=session,
    )
    gitdir = sc.get_worktree_gitdir(repo)
    super_dir = os.path.join(gitdir, RD.SIDECAR_DIRNAME)
    os.makedirs(super_dir, exist_ok=True)
    sidecar_path = os.path.join(super_dir, RD.SIDECAR_FILE)
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    state = {
        "terminal": "converged",
        "config": {"repoRoot": repo, "baseRef": base_sha, "baseBranch": "main"},
        "reviewedDiff": "",
        "certification": {"shape": "audited-chain"},
    }
    prepared = RD._prepare_sidecar(session, state)
    assert prepared["ok"] is True and prepared["needs_write"] is True
    republished = json.loads(prepared["sidecar_bytes"].decode("utf-8"))
    assert republished["baseRef"] == "main"


def test_legacy_sidecar_repair_is_idempotent(tmp_path):
    """A second terminal advance after legacy baseRef repair must find the sidecar fresh."""
    session, state, sidecar_path = _legacy_sidecar_setup(tmp_path)
    prepared = RD._prepare_sidecar(session, state)
    assert prepared["ok"] is True and prepared["needs_write"] is True
    with open(sidecar_path, "wb") as fh:
        fh.write(prepared["sidecar_bytes"])
    again = RD._prepare_sidecar(session, state)
    assert again["ok"] is True and again["needs_write"] is False


def test_cursor_fix_never_gets_an_independent_cursor_auditor():
    """#651: composer and grok are ONE family, so a cursor-only panel auditing a cursor fix is
    DEGRADED, never independent. Under the old registry (composer='cursor', grok='xai') the
    same-vendor fallback loop returned ('cursor', 'independent') — a self-audit labelled
    independent. This pins that lane closed while leaving the real cross-family path intact."""
    vendor, independence = RD._auditor_vendor({"vendors": ["cursor"]}, "cursor")
    assert independence == "degraded"
    assert vendor == "cursor"
    for other in ("claude", "codex"):
        v, ind = RD._auditor_vendor({"vendors": [other, "cursor"]}, "cursor")
        assert ind == "independent", (other, v, ind)
        assert v == other


# =============================================================================
# #1030 — hard round ceiling wired into the live loop
# =============================================================================

CB = _load("circuit_breaker")


def _rearm_forever_seams():
    """Every review round surfaces one fresh Important blocker; audits stay clean."""
    seq = {"n": 0}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "gap-sweep":
            return []
        if dim == "scoped-finder":
            seq["n"] += 1
            return [{"title": "scoped-%d" % seq["n"], "severity": "Important",
                     "file": "newsurf.py", "line": 1}]
        if dim == "code-reviewer":
            seq["n"] += 1
            return {"findings": [{"title": "panel-%d" % seq["n"], "severity": "Important",
                                  "file": "f.py", "line": 1}]}
        return {}

    fix_n = {"n": 0}

    def fix_step(batch, rnd, payload):
        fix_n["n"] += 1
        return {"fixes": [], "headDiff": _headf_ns(fix_n["n"]), "changedSubjects": ["Code"]}

    return _seams(reviewer=reviewer, fix_step=fix_step)


def test_clean_rearm_forever_halts_at_round_ceiling(tmp_path):
    """DoD headline: clean audits + fresh blocker every review round halts at the ceiling."""
    receipt = RD.run_loop(_rearm_forever_seams(), _cfg(maxRoundsAbsolute=10, maxRounds=7))
    assert receipt["verdict"] == "halted"
    assert receipt["certificationShape"] is None
    detail = " ".join(d["detail"] for d in receipt["decisions"] if d["kind"] == "round-ceiling")
    assert CB.ROUND_CEILING_REASON == "round-ceiling"
    assert "round-ceiling" in [d["kind"] for d in receipt["decisions"]]
    assert "10" in detail, detail
    assert "ceiling" in detail.lower(), detail
    assert receipt.get("scriptRan", {}).get("invocations", 999) < RD._RUN_LOOP_GUARD


def test_round_nine_below_ceiling_does_not_halt_on_ceiling():
    """Round 9 with ceiling 11 does not halt on the round-ceiling breaker."""
    state = RD.new_state(_cfg(maxRoundsAbsolute=11))
    state["round"] = 9
    state["findings"] = []
    state["fullPanelRan"] = True
    RD._after_findings_settled(state, state["config"])
    assert state["terminal"] == "converged"
    assert not any(d["kind"] == "round-ceiling" for d in state["decisions"])


def test_delta_settle_at_ceiling_halts_not_routes_to_fixer():
    """A delta settle at the ceiling halts instead of routing to the fixer."""
    state = RD.new_state(_cfg(maxRoundsAbsolute=10, maxRounds=10))
    state["round"] = 10
    state["findings"] = [{"title": "open", "severity": "Important", "file": "f.py", "line": 1}]
    state["auditRounds"] = [{"round": 9, "outcomes": [{"identity": "x", "ruling": "discharged"}]}]
    state["_auditOutcome"] = {"notDischarged": [], "discharged": ["x"]}
    RD._settle_delta(state, state["config"])
    assert state["terminal"] == "halted"
    assert state["step"] != RD.P_FIXER
    assert any(d["kind"] == "round-ceiling" for d in state["decisions"])

def test_clean_below_ceiling_still_certifies_converged(tmp_path):
    """No-regression: a clean run below the ceiling still certifies converged."""
    receipt = RD.run_loop(_seams(), _cfg(maxRoundsAbsolute=10))
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"] is not None


def test_panel_settle_at_ceiling_halts_not_certifies():
    """A clean panel settle at the ceiling halts instead of certifying."""
    state = RD.new_state(_cfg(maxRoundsAbsolute=10))
    state["round"] = 10
    state["findings"] = []
    state["fullPanelRan"] = True
    RD._after_findings_settled(state, state["config"])
    assert state["terminal"] == "halted"
    assert state["certification"]["shape"] is None
    assert any(d["kind"] == "round-ceiling" for d in state["decisions"])
    detail = next(d["detail"] for d in state["decisions"] if d["kind"] == "round-ceiling")
    assert "10" in detail and "ceiling" in detail.lower()


def test_seed_resume_above_ceiling_halts_without_assigning_round(tmp_path):
    """A records-seeded resume above the ceiling halts loud; counter stays below the ceiling."""
    records = tmp_path / "round-records.json"
    seed = [
        {"schemaVersion": 2, "round": 10, "kind": "baseline",
         "dimensions": {"code-reviewer": {"status": "run", "confidence": "high",
                                            "tier": "reviewer-deep", "findings": []}},
         "findings": [], "coverageDecisions": []},
    ]
    records.write_text(json.dumps(seed))
    state = RD.new_state(_cfg(recordsPath=str(records), maxRoundsAbsolute=10))
    assert state["terminal"] == "halted"
    assert state["round"] == 1
    assert any(d["kind"] == "round-ceiling" for d in state["decisions"])
    detail = next(d["detail"] for d in state["decisions"] if d["kind"] == "round-ceiling")
    assert "11" in detail


def test_load_refusal_when_ceiling_below_max_rounds():
    """A ceiling below maxRounds refuses at load with the named token."""
    with pytest.raises(RD.RoundCeilingRefusal) as exc:
        RD._default_config({"maxRounds": 7, "maxRoundsAbsolute": 5})
    assert exc.value.reason == CB.CEILING_BELOW_CAP_REFUSAL


def test_load_accepts_ceiling_at_or_above_max_rounds():
    """A ceiling at or above maxRounds resolves and loads."""
    cfg = RD._default_config({"maxRounds": 7, "maxRoundsAbsolute": 10})
    assert cfg["maxRoundsAbsolute"] == 10
    cfg2 = RD._default_config({"maxRounds": 7, "maxRoundsAbsolute": 7})
    assert cfg2["maxRoundsAbsolute"] == 7


def test_new_state_unnamed_ceiling_below_max_rounds_loads_flat_default():
    """maxRounds=20 with no named ceiling loads; flat default ceiling binds below the cap."""
    state = RD.new_state(_cfg(maxRounds=20))
    assert state["config"]["maxRoundsAbsolute"] == CB.DEFAULT_MAX_ROUNDS_ABSOLUTE


def test_max_rounds_absolute_cli_structured_refusal(tmp_path, capsys):
    """CLI --max-rounds-absolute below maxRounds emits the structured refusal shape."""
    d = str(tmp_path)
    rc = RD.main(["next", "--session-dir", d, "--max-rounds", "7",
                  "--max-rounds-absolute", "5"])
    assert rc == 1
    out = json.loads(capsys.readouterr().out.strip())
    assert out == {"ok": False, "reason": CB.CEILING_BELOW_CAP_REFUSAL, "value": 5}


def test_persisted_config_without_max_rounds_absolute_resolves_default_ceiling():
    """Persisted config predating #1030 resolves the default ceiling — never ceiling-less."""
    cfg = dict(RD.new_state(_cfg())["config"])
    cfg.pop("maxRoundsAbsolute", None)
    assert RD._round_ceiling(cfg) == CB.DEFAULT_MAX_ROUNDS_ABSOLUTE


def _round_counter_mutation_sites():
    """Multiset of (enclosing function, mutation statement) for state['round'] writes."""
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    sites = []
    for i, line in enumerate(lines):
        if not re.search(r'state\["round"\]\s*(=|\+=)', line):
            continue
        func = None
        for j in range(i, -1, -1):
            m = re.match(r"^def (\w+)", lines[j])
            if m:
                func = m.group(1)
                break
        sites.append((func, line.strip()))
    return sites


def test_round_counter_mutation_sites_census():
    """The round counter has exactly three mutation sites — a fourth must reconsider the ceiling."""
    sites = _round_counter_mutation_sites()
    assert sorted(sites) == sorted([
        ("_seed_resume", 'state["round"] = resume_round'),
        ("_fold_verify", 'state["round"] += 1'),
        ("_settle_delta", 'state["round"] += 1'),
    ])
    stmts = [stmt for _func, stmt in sites]
    assert stmts.count('state["round"] = resume_round') == 1
    assert stmts.count('state["round"] += 1') == 2


def _delta_settle_state_for_breaker(monkeypatch, breaker_result):
    state = RD.new_state(_cfg(maxRounds=10, maxRoundsAbsolute=10))
    state["round"] = 3
    state["findings"] = []
    state["auditRounds"] = [{"round": 2, "outcomes": [{"identity": "x", "ruling": "discharged"}]}]
    state["_auditOutcome"] = {"notDischarged": [], "discharged": ["x"]}
    monkeypatch.setattr(RD.circuit_breaker, "check_audit_breaker",
                        lambda *a, **k: dict(breaker_result))
    return state


def _audit_breaker_emitted_reasons():
    source = inspect.getsource(CB.check_audit_breaker)
    return set(re.findall(r'"reason": "([^"]+)"', source))


_SETTLE_DELTA_CLAIMED = frozenset({
    "max-iterations",
    "audit-stall",
    CB.ROUND_CEILING_REASON,
})
_SETTLE_DELTA_UNREACHABLE = frozenset({
    "no-net-progress",
    "recurring-finding",
    "challenged-principle-recurring",
})


def test_settle_delta_breaker_reasons_reachable_and_claimed(monkeypatch):
    """Each BREAKER_REASONS member at _settle_delta is reachable-and-claimed or unreachable."""
    audit_emitted = _audit_breaker_emitted_reasons()
    for reason in _SETTLE_DELTA_UNREACHABLE:
        assert reason not in audit_emitted, reason

    # max-iterations — parks or certifies; never routes to the fixer.
    state = _delta_settle_state_for_breaker(monkeypatch, {
        "halt": True, "reason": "max-iterations", "detail": "cap",
        "stalledIdentities": [],
    })
    RD._settle_delta(state, state["config"])
    assert state["step"] != RD.P_FIXER
    assert state["terminal"] in (
        "converged", "capped-with-open-critical", "capped-with-open-blocker",
    )

    # audit-stall — _handle_stall self-recovery legitimately routes to the fixer.
    state = _delta_settle_state_for_breaker(monkeypatch, {
        "halt": True, "reason": "audit-stall", "detail": "stalled",
        "stalledIdentities": ["x"],
    })
    state["_auditTargets"] = [{"id": "x", "identity": "x", "severity": "Important",
                               "file": "f.py", "line": 1}]
    RD._settle_delta(state, state["config"])
    assert state["step"] == RD.P_FIXER
    assert any(d["kind"] == "self-recovery" for d in state["decisions"])

    # round-ceiling — claimed before the switch by check_round_ceiling.
    state = RD.new_state(_cfg(maxRoundsAbsolute=10))
    state["round"] = 10
    state["findings"] = []
    state["auditRounds"] = []
    state["_auditOutcome"] = {"notDischarged": [], "discharged": []}
    RD._settle_delta(state, state["config"])
    assert state["terminal"] == "halted"
    assert state["step"] != RD.P_FIXER


def test_settle_delta_unregistered_halt_reason_parks_fail_closed(monkeypatch):
    """Unregistered halt reasons park fail-closed; census covers BREAKER_REASONS exactly."""
    assert _SETTLE_DELTA_CLAIMED | _SETTLE_DELTA_UNREACHABLE == CB.BREAKER_REASONS

    state = _delta_settle_state_for_breaker(monkeypatch, {
        "halt": True, "reason": "synthetic-unregistered-reason", "detail": "unhandled",
        "stalledIdentities": [],
    })
    RD._settle_delta(state, state["config"])
    assert state["terminal"] == "cannot-certify"
    assert any(d["kind"] == "cannot-certify" for d in state["decisions"])
    assert state["step"] != RD.P_FIXER
    detail = next(d["detail"] for d in state["decisions"] if d["kind"] == "cannot-certify")
    assert "synthetic-unregistered-reason" in detail
