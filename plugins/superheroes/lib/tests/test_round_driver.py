"""Tests for `round_driver` — the ONE-entrypoint review-loop round driver (#507).

The driver collapses review-code's per-round script choreography into ONE entrypoint so the
mandated path is the easiest path. These pin BOTH layers over the shared core:

  - Layer 2 (next/submit CLI): the state-machine protocol — echo validation (stale attempt /
    hash mismatch rejected, exact-duplicate idempotent), v1-state refusal, per-call journalling.
  - Layer 1 (run_loop): the ported run-shape driven end-to-end with scripted seams.

Ported invariants from the retired test_code_loop_plan.py (round-1 full-deep baseline; rounds 2 and
later run no panel; a fix surface the driver cannot work out hands the PR back; exits only off a
qualifying round — now also expressible as an audited-chain certification), plus
the new #507 mechanics: audit-keyed stall + self-recovery + hand-back, delta rounds, degraded
independence, receipt-missing seats carried unverified, the author-justification POST-filter, and
the driver receipt + its validator.
"""
import ast
import importlib.util
import hashlib
import inspect
import json
import os
import re
import subprocess
import sys

import pytest

from source_access_scan import source_obj_accesses_key

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from session_checkout import enter_checkout, seed_session_meta  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RD_DISCLOSURES = _load("receipt_disclosures")
LPC = _load("loop_plan_common")
FI = _load("finding_identity")
LC = _load("liveness_cache")
model_registry = _load("model_registry")

_CONSEQUENCE = "a reviewer-found defect stays in the change"


def _seat_map_receipts(seat_map, round_id="1"):
    return [{"round": round_id, "map": dict(seat_map)}]


def _set_seat_map(state, seat_map, round_id="1"):
    state["seatMapReceipts"] = _seat_map_receipts(seat_map, round_id)


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

def audit_checks(**answers):
    """The fix auditor's three answers (`right`, `brokeNothing`, `testWouldFail`) as an audit result
    carries them in `checks`: every one `yes` unless a check is named with another answer."""
    return {name: {"answer": answers.get(name, "yes"), "why": "checked: %s" % name}
            for name in ("right", "brokeNothing", "testWouldFail")}


def audit_test_match(target, answer="matches"):
    """The `testMatch` an audit result owes for `target`: `{"testMatch": ...}` when the target's committed
    break-it test was changed and explained, else nothing."""
    if (target.get("breakIt") or {}).get("match") != "changed-explained":
        return {}
    return {"testMatch": {"answer": answer, "why": "compared the committed test with the test role's"}}


def _seams(reviewer=None, verifier=None, synthesis=None, auditor=None, fix_step=None,
           verify_runner=None, io=None, vendors=None, fixer_vendor="claude"):
    def default_reviewer(dim, tier, rnd, ctx):
        return []

    def default_verifier(clusters, rnd):
        # Report the vendor it ran on: with the default fixer `claude` the independent selection is
        # `codex`, and an unreported verdict does not count once the selection replaced the engine.
        return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran", "reason": "ran"}
                             for c in (clusters or []) for i in (c.get("ids") or [])],
                "vendor": "codex"}

    def default_synthesis(findings, rnd):
        return None

    def default_auditor(targets, rnd):
        # Echo the selected independent auditor vendor so the discharge passes the provenance gate.
        return [dict({"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                      "evidence": "tests pass", "auditorVendor": t.get("auditorVendor"),
                      "checks": audit_checks()}, **audit_test_match(t))
                for t in (targets or [])]

    def default_fix(batch, rnd, payload):
        return {"fixes": [], "headDiff": HEAD, "changedSubjects": ["Code"]}

    def default_verify(command, rnd):
        return "pass"

    io_out = dict(io or {})
    if vendors is not None:
        io_out.setdefault("seatMap", _assertable_seat_map(vendors, fixer_vendor))

    base_reviewer = reviewer or default_reviewer

    def finder_reporting_reviewer(dim, tier, rnd, ctx):
        # Like the verifier above: the gap-sweep / scoped-finder callbacks report the vendor they ran
        # on ({"findings": [...], "vendor": v}); with the default fixer `claude` the independent
        # selection is `codex`, and an unreported finder result does not count once it replaced the
        # reviewer engine (#1851 L4 K).
        result = base_reviewer(dim, tier, rnd, ctx)
        if dim not in ("gap-sweep", "scoped-finder"):
            return result
        if isinstance(result, list):
            return {"findings": result, "vendor": "codex"}
        if isinstance(result, dict):
            return dict(result, vendor=result.get("vendor", "codex"))
        return result

    return {
        "reviewer": finder_reporting_reviewer,
        "verifier": verifier or default_verifier,
        "synthesis": synthesis or default_synthesis,
        "auditor": auditor or default_auditor,
        "fix_step": fix_step or default_fix,
        "verify_runner": verify_runner or default_verify,
        "io": io_out,
    }


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude"}
    base.update(over)
    return base


def _cfg_cert(**over):
    """Config with checked base guard — prerequisite for run_loop to return a writer receipt."""
    return _cfg(baseGuard=RD.BASE_GUARD_CHECKED, **over)


def _run_loop_capturing_state(seams, config=None):
    """run_loop plus the state it ran on (captured by wrapping build_receipt for the call)."""
    box = {}
    orig = RD.build_receipt

    def _capture(state, *args, **kwargs):
        box.setdefault("state", state)
        return orig(state, *args, **kwargs)

    RD.build_receipt = _capture
    try:
        result = RD.run_loop(seams, config)
    finally:
        RD.build_receipt = orig
    return result, box.get("state")


def _run_loop_with_loop_receipt(seams, config=None):
    """run_loop plus a receipt built from the state it ran on."""
    result, state = _run_loop_capturing_state(seams, config)
    loop_receipt = RD.build_receipt(state) if state is not None else {}
    return result, loop_receipt


def _state_verifier_faults(state):
    """The verifierArtifactFault records run_loop appended to the state's round records."""
    faults = []
    for key in sorted(state["rounds"], key=lambda k: int(k) if str(k).isdigit() else 0):
        faults.extend(state["rounds"][key].get("verifierArtifactFault") or [])
    return faults


def _loop_rounds(result):
    return result.get("rounds") or []


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
    # foldLanded marks a landed fold; duplicate replay is one of the two honest fold returns.
    assert dup["ok"] is True and dup.get("duplicate") is True and dup.get("foldLanded") is True


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
    narrow = ["code-reviewer", "test-role"]
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
    assert "configured dimensions: code-reviewer, test-role" in out2["reason"]


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

def _seed_repo_root_if_missing(session_dir, checkout_path):
    """When meta.json lacks repoRoot, record the fixture checkout (never overwrite)."""
    meta_path = os.path.join(session_dir, "meta.json")
    meta = {}
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
    if meta.get("repoRoot"):
        return
    seed_session_meta(session_dir, checkout_path)


def _claim_reviewer(session_dir, phase, art):
    """A hand-submitting orchestrator names the vendor it dispatched the single-seat reviewer on
    (`reviewerVendor`), which the driver requires when independence replaced the reviewer engine."""
    if phase in (RD.P_GAPSWEEP, RD.P_SCOPED) and isinstance(art, dict) and "reviewerVendor" not in art:
        ok, state = RD.load_state(session_dir)
        vendor = RD._nonpanel_selection(state, session_dir, phase)[0] if ok else None
        if vendor:
            return dict(art, reviewerVendor=vendor)
    return art


def _drive_cli(session_dir, cfg, respond, max_steps=80):
    """Drive next/submit to a terminal using `respond(phase, payload, round) -> artifact`.

    The driven session runs inside a real checkout (`<session_dir>/checkout`), as it does in
    production, so the driver's cwd-discovered repository read resolves a HEAD."""
    checkout = os.path.join(session_dir, "checkout")
    enter_checkout(checkout)
    _seed_repo_root_if_missing(session_dir, checkout)
    first = True
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            return n["payload"]
        art = _claim_reviewer(session_dir, n["phase"], respond(n["phase"], n["payload"], n["round"]))
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    raise AssertionError("driver did not reach a terminal within %d steps" % max_steps)


def _responder(round1_findings=None, scoped=None, audit="discharged", verify="pass",
               head=HEAD, verdict="CONFIRMED", seat_map=None, vendors=None,
               fixer_vendor="claude"):
    scoped_state = {"fired": False}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {d: {"findings": []} for d in RD.DIMENSIONS}
            if rnd == 1 and round1_findings:
                seats["code-reviewer"] = {"findings": list(round1_findings)}
            art = {"seats": seats}
            if seat_map is not None:
                art["seatMap"] = seat_map
            elif vendors is not None:
                art["seatMap"] = _assertable_seat_map(vendors, fixer_vendor)
            return art
        if phase == RD.P_VERIFIERS:
            out = []
            for c in payload.get("clusters", []):
                for i in c.get("ids", []):
                    v = {"id": i, "verdict": verdict, "reason": "checked"}
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
            return {"results": [dict({"id": t["id"], "ruling": audit, "reason": "r", "evidence": "e",
                                      "auditorVendor": t.get("auditorVendor"),
                                      "checks": audit_checks()}, **audit_test_match(t))
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            if scoped and not scoped_state["fired"]:
                scoped_state["fired"] = True
                return {"findings": list(scoped)}
            return {"findings": []}
        if phase == RD.P_APPLY_FIXES:
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

_A_FINDING = [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]
_GOOD_VERIFY = {"result": "pass"}


def _drive_to_phase(session_dir, cfg, respond, target_phase, max_steps=80):
    """Drive next/submit with `respond` until the PENDING step is `target_phase`; return that
    `next`. Asserts the loop did not reach a terminal first, so a routing change that stops
    reaching the phase fails loudly instead of silently skipping the test's body. The driven
    session runs inside a real checkout (`<session_dir>/checkout`), as it does in production."""
    checkout = os.path.join(session_dir, "checkout")
    enter_checkout(checkout)
    _seed_repo_root_if_missing(session_dir, checkout)
    first = True
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        if n.get("phase") == target_phase:
            return n
        assert n["action"] != RD.P_TERMINAL, "reached terminal before %s" % target_phase
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                          _claim_reviewer(session_dir, n["phase"],
                                          respond(n["phase"], n["payload"], n["round"])))
        assert s["ok"], s
    raise AssertionError("never reached %s within %d steps" % (target_phase, max_steps))


def _synthesis_seatable_map(vendors, fixer_vendor):
    """An assertable seat map whose host family is known and outside the makers', so the synthesis
    seat can stand on `claude` (needs a fixer other than `claude`, so that the makers exclude anthropic)."""
    return dict(_assertable_seat_map(vendors, fixer_vendor), hostFamily="anthropic")


def _at(tmp_path, target_phase, cfg=None):
    """Drive a fresh session to `target_phase`. `cfg` overrides the default profile so a test can
    pin real config the guard must stay blind to (e.g. a configured `verifyCommand`). A walk through
    synthesis defaults to a profile that seats it: a `codex` fixer and a known, non-maker host family."""
    d = str(tmp_path)
    if cfg is None and target_phase == RD.P_SYNTHESIS:
        respond = _responder(round1_findings=_A_FINDING,
                             seat_map=_synthesis_seatable_map(["claude", "codex"], "codex"))
        n = _drive_to_phase(d, _cfg(fixerVendor="codex"), respond, target_phase)
        return d, n
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
    if token == "fail":
        # the first `fail` does not halt: the gate is pending again (UFR-3), the second result decides
        assert not state.get("terminal"), state.get("terminal")
        assert state["step"] == RD.P_VERIFY
        assert "verify-rerun" in kinds, kinds
        assert decision_kind not in kinds, kinds
        again = RD.cmd_next(d)
        assert (again["phase"], again["attempt"]) == (RD.P_VERIFY, n["attempt"] + 1), again
        out = RD.cmd_submit(d, again["phase"], again["attempt"], again["expectedStateHash"],
                            {"result": token})
        assert out["ok"] is True, out
        ok, state = RD.load_state(d)
        assert ok
        assert state.get("terminal") == "halted", state.get("terminal")
        kinds = [dec.get("kind") for dec in state.get("decisions", [])]
        assert decision_kind in kinds, kinds
    elif decision_kind is None:
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


def test_run_verify_payload_binds_base_ref_token_to_the_pinned_base(tmp_path):
    """`{baseRef}` in the calibrated verify command is bound to the session's pinned base commit
    at `run-verify`, so a touched-tests gate on a stacked branch diffs against the PR base rather
    than main (vet 244, @244-3).

    Bites on: `_verify_command` substituting the token from `config["baseRef"]`."""
    pin = "a" * 40
    d, n = _at(tmp_path, RD.P_VERIFY,
               cfg=_cfg(verifyCommand="gate.py --base {baseRef} && pytest -q", baseRef=pin))
    assert n["payload"]["command"] == "gate.py --base %s && pytest -q" % pin, n["payload"]


def test_run_verify_payload_leaves_base_ref_token_verbatim_without_a_full_hex_pin(tmp_path):
    """No pin, or a pin that is not a full hex object id, leaves the token in the command so the
    gate refuses loudly on an unresolvable ref — never a silent substitution of main or of ``.

    Bites on: the full-hex guard in `_verify_command` (a `""`/short/None pin does not substitute)."""
    for i, pin in enumerate((None, "", "abc1234", "not-a-sha", "x" * 40)):
        cfg = _cfg(verifyCommand="gate.py --base {baseRef}")
        if pin is not None:
            cfg["baseRef"] = pin
        d, n = _at(str(tmp_path / ("case-%d" % i)), RD.P_VERIFY, cfg=cfg)   # one fresh session per case
        assert n["payload"]["command"] == "gate.py --base {baseRef}", (pin, n["payload"])


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
              "auditorVendor": targets[0].get("auditorVendor"), "checks": audit_checks()}
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
    one_ruling_each = [{"id": "f.py::unchecked return value", "ruling": "discharged", "reason": "r",
                        "checks": audit_checks()},
                       {"id": "f.py::unchecked return value", "ruling": "discharged", "reason": "r",
                        "checks": audit_checks()}]
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
     "newIssues": [{"title": "new", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]},
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
    good = [{"id": "a1", "ruling": "not-discharged", "checks": audit_checks()}]
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
    assert RD.audit_results_fault(
        {"results": [{"id": "zz", "ruling": "not-discharged", "checks": audit_checks()}]}, []) is None
    assert "not an audit target" in RD.audit_results_fault({"results": good}, [{"id": "other"}])
    # a ruling with no binding id is refused even with NO targets to key against — the id branch
    # stands on its own, so its bite-proof reddens on the refusal axis rather than on a message
    assert "no usable `id`" in RD.audit_results_fault(
        {"results": [{"id": None, "ruling": "not-discharged"}]}, [])
    assert "results[0] is str" in RD.audit_results_fault({"results": ["discharged"]}, [])
    # the entry index is named so a multi-result artifact says WHICH ruling is wrong
    two = [{"id": "a1", "ruling": "not-discharged", "checks": audit_checks()},
           {"id": "a2", "ruling": "nope"}]
    assert "results[1]" in RD.audit_results_fault({"results": two}, [{"id": "a1"}, {"id": "a2"}])


def test_collection_manifest_fault_pure():
    # axis: absent manifest — accepted (no fault).
    assert RD.collection_manifest_fault({}, [{"id": "a1"}]) is None
    assert RD.collection_manifest_fault({"results": []}, [{"id": "a1"}]) is None
    # axis: non-dict manifest — refused, type named.
    assert "list" in RD.collection_manifest_fault({"collectionManifest": []}, [{"id": "a1"}])
    assert "NoneType" in RD.collection_manifest_fault({"collectionManifest": None}, [{"id": "a1"}])
    assert "str" in RD.collection_manifest_fault({"collectionManifest": "x"}, [{"id": "a1"}])
    # axis: empty dict manifest — accepted; fold's unauthenticated path still governs.
    assert RD.collection_manifest_fault({"collectionManifest": {}}, [{"id": "a1"}]) is None
    # axis: strict subset of target ids — accepted.
    assert RD.collection_manifest_fault({"collectionManifest": {"a1": "claude"}},
                                        [{"id": "a1"}, {"id": "a2"}]) is None
    # axis: unavailable targets (None) — no key judged, accepted.
    assert RD.collection_manifest_fault({"collectionManifest": {"zz": "claude"}}, None) is None
    # axis: known-empty targets + nonempty manifest — refused.
    fault = RD.collection_manifest_fault({"collectionManifest": {"zz": "claude"}}, [])
    assert fault is not None and "zz" in fault
    # axis: identity key — refused with identity-vs-id hint.
    targets = [{"id": "f.py::x@L1", "identity": "f.py::x"}]
    fault = RD.collection_manifest_fault({"collectionManifest": {"f.py::x": "claude"}}, targets)
    assert fault is not None
    assert "identity" in fault and "f.py::x@L1" in fault
    # axis: unknown key — refused, valid target ids listed.
    fault = RD.collection_manifest_fault({"collectionManifest": {"nope": "claude"}},
                                         [{"id": "a2"}, {"id": "a1"}])
    assert fault is not None
    assert "nope" in fault and "a1" in fault and "a2" in fault
    # axis: determinism — first bad key is sorted.
    fault = RD.collection_manifest_fault({"collectionManifest": {"z": "x", "a": "x"}},
                                         [{"id": "a1"}])
    assert fault is not None and "collectionManifest key 'a'" in fault
    # axis: malformed target entries — no crash, do not widen the accepted set.
    assert RD.collection_manifest_fault({"collectionManifest": {"a1": "x"}},
                                        [{"id": "a1"}, "bad", {"id": 1}, {}]) is None
    assert RD.collection_manifest_fault({"collectionManifest": {"bad": "x"}},
                                        [{"id": "a1"}, "bad", {"id": 1}, {}]) is not None
    # axis: non-dict artifact — accepted; envelope refusal is the sibling's job.
    assert RD.collection_manifest_fault(None, [{"id": "a1"}]) is None


def test_collection_manifest_fault_non_string_key_refused():
    """A non-string manifest key is refused with the key and type named — no TypeError."""
    targets = [{"id": "a1"}]
    fault = RD.collection_manifest_fault(
        {"collectionManifest": {"z": "claude", 1: "codex"}},
        targets,
    )
    assert fault is not None
    assert "1" in fault
    assert "int" in fault
    assert "resubmit the same phase/attempt/state-hash with a corrected artifact" in fault


def test_collection_manifest_fault_non_string_key_mixed_with_valid_id():
    """A manifest mixing a valid string id and a non-string key refuses the non-string key."""
    fault = RD.collection_manifest_fault(
        {"collectionManifest": {"a1": "claude", 1: "codex"}},
        [{"id": "a1"}],
    )
    assert fault is not None
    assert "1" in fault
    assert "int" in fault


def _collection_manifest_rekey_clause(fault):
    """Isolate the recovery-id portion of an identity-confusion refusal."""
    lead = "re-key to a per-location target id for each location: "
    start = fault.index(lead) + len(lead)
    end = fault.index("; valid target ids:", start)
    return fault[start:end]


def test_collection_manifest_fault_colliding_identity_names_all_ids():
    """When several targets share one identity, the refusal names every carrying id."""
    targets = [
        {"id": "f.py::x@L1", "identity": "f.py::x"},
        {"id": "f.py::x@L9", "identity": "f.py::x"},
    ]
    fault = RD.collection_manifest_fault(
        {"collectionManifest": {"f.py::x": "claude"}},
        targets,
    )
    assert fault is not None
    assert "identity" in fault
    assert "f.py::x@L1" in fault
    assert "f.py::x@L9" in fault
    assert "per-location" in fault
    rekey_clause = _collection_manifest_rekey_clause(fault)
    assert "'f.py::x@L1'" in rekey_clause
    assert "'f.py::x@L9'" in rekey_clause


def test_collection_manifest_fault_duplicate_same_id_single_wording():
    """Duplicate rows sharing one identity and one id use single-id wording."""
    legacy_id = "legacy-id"
    targets = [
        {"id": legacy_id, "identity": "f.py::x"},
        {"id": legacy_id, "identity": "f.py::x"},
    ]
    fault = RD.collection_manifest_fault(
        {"collectionManifest": {"f.py::x": "claude"}},
        targets,
    )
    assert fault is not None
    assert "identity" in fault
    assert "per-location" not in fault
    assert ("re-key to %r; valid target ids:" % legacy_id) in fault


def test_collection_manifest_fault_single_identity_wording_preserved():
    """Exactly one target carries the identity — preserve the single-id re-key wording."""
    targets = [{"id": "f.py::x@L1", "identity": "f.py::x"}]
    fault = RD.collection_manifest_fault(
        {"collectionManifest": {"f.py::x": "claude"}},
        targets,
    )
    assert fault is not None
    assert "re-key to 'f.py::x@L1'" in fault
    assert "per-location" not in fault


def test_collection_manifest_fault_determinism_repeated_calls():
    """Repeated calls name the same bad key when several bad keys exist."""
    artifact = {"collectionManifest": {"z": "x", "a": "x"}}
    targets = [{"id": "a1"}]
    first = RD.collection_manifest_fault(artifact, targets)
    for _ in range(5):
        assert RD.collection_manifest_fault(artifact, targets) == first
    assert first is not None and "collectionManifest key 'a'" in first


def test_submit_audits_collection_manifest_key_refused(tmp_path):
    """A mis-keyed collectionManifest is refused at the submit chokepoint with the mistake named,
    the pending step intact, and a corrected resubmit on the same phase/attempt/state-hash accepted."""
    d, n = _at(tmp_path, RD.P_AUDITS)
    good, targets = _audit_artifact(n)
    bad = dict(good)
    bad["collectionManifest"] = {targets[0]["identity"]: targets[0].get("auditorVendor")}
    _assert_shape_refused(d, n, bad, "collection-manifest-key",
                          ["identity", "re-key to", targets[0]["id"]], good)


def test_submit_audits_collection_manifest_refusal_no_fold(tmp_path):
    """A refused manifest key does not run the fold — no auditRounds entry, no _auditOutcome, no
    decisions recorded."""
    d = str(tmp_path)
    n = _drive_to_phase(d, _cfg(fixerVendor="codex"), _responder(
        round1_findings=_A_FINDING, seat_map=_synthesis_seatable_map(["claude", "codex"], "codex")),
        RD.P_AUDITS)
    good, _targets = _audit_artifact(n)
    bad = dict(good)
    bad["collectionManifest"] = {"no-such-key": "claude"}
    before = _state_bytes(d)
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], bad)
    assert out["ok"] is False, out
    assert _state_bytes(d) == before, "a refused manifest submit mutated loop-state"
    ok, state = RD.load_state(d)
    assert ok
    assert not state.get("auditRounds"), state.get("auditRounds")
    assert not state.get("_auditOutcome"), state.get("_auditOutcome")
    assert not state.get("decisions"), state.get("decisions")


def test_verifier_results_fault_pure():
    assert RD.verifier_results_fault({"verdicts": []}) is None
    fault = RD.verifier_results_fault({"verdicts": [{"id": "x", "verdict": "CONFIRMED"}]})
    assert fault is not None
    assert "reason" in fault
    assert RD.verifier_results_fault(None) is not None
    assert RD.verifier_results_fault({}) is not None
    assert "missing `verdicts`" in RD.verifier_results_fault({}) or \
        "no `verdicts` key" in RD.verifier_results_fault({})
    fault = RD.verifier_results_fault({"findings": []})
    assert fault is not None and "`findings`" in fault
    assert RD.verifier_results_fault({"verdicts": {}}) is not None


def test_hand_submit_verifier_reasonless_verdict_refused():
    fault = RD.verifier_results_fault({"verdicts": [{"id": "f-1", "verdict": "CONFIRMED"}]})
    assert fault is not None
    assert "reason" in fault
    assert RD.verifier_results_fault(
        {"verdicts": [{"id": "f-1", "verdict": "CONFIRMED", "reason": "checked"}]}
    ) is None
    assert RD.verifier_results_fault(None) is not None
    assert RD.verifier_results_fault({}) is not None
    assert "missing `verdicts`" in RD.verifier_results_fault({}) or \
        "no `verdicts` key" in RD.verifier_results_fault({})
    fault_findings = RD.verifier_results_fault({"findings": []})
    assert fault_findings is not None and "`findings`" in fault_findings
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
              "newIssues": candidates, "checks": audit_checks()}])
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
    cfg = _cfg()
    payload = _drive_cli(d, cfg, _responder(
        round1_findings=[{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}],
        vendors=cfg["vendors"]))
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
    cfg = _cfg()
    payload = _drive_cli(d, cfg, _responder(round1_findings=None, vendors=cfg["vendors"]))
    assert payload["verdict"] == "converged"
    assert payload["certification"]["shape"] == "full-panel-confirmed"


def test_unknown_delta_surface_hands_the_pr_back_and_runs_no_panel(tmp_path, monkeypatch):
    """A malformed/quoted-path head diff → unknown surface → the PR is handed back
    (`fix-surface-unknown`), not a scoped audit and not a panel. Git's answer is the malformed text
    too, so the supplied diff cross-checks as a match and the split meets the malformed diff."""
    from test_round_driver_round_economy_1272 import _commit_in_repo, _init_ceiling_git_repo

    repo, init_head = _init_ceiling_git_repo(tmp_path)
    _commit_in_repo(repo, "unknown-surface-head")
    d = str(tmp_path)
    seed_session_meta(d, repo)
    bad_head = 'diff --git "a/x y.py" "b/x y.py"\n@@ -1 +1 @@\n-a\n+b\n'
    seen = {"panel_r2": False}
    real_derive = RD._derive_panel_diff_at_head
    derive_calls = []

    def derive_once_malformed(config, head_sha):
        derive_calls.append(head_sha)
        if len(derive_calls) == 1:
            return bad_head, None
        return real_derive(config, head_sha)

    monkeypatch.setattr(RD, "_derive_panel_diff_at_head", derive_once_malformed)

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            if rnd >= 2:
                seen["panel_r2"] = True
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
            return {"seats": seats, "seatMap": _assertable_seat_map(["claude", "codex"])}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "PLAUSIBLE", "reason": "checked"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_APPLY_FIXES:
            return {"fixes": [], "headDiff": bad_head, "changedSubjects": []}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        if phase in (RD.P_AUDITS, RD.P_SCOPED, RD.P_GAPSWEEP):
            return {"results": [], "findings": []}
        return {}

    payload = _drive_cli(d, _cfg(repoRoot=repo, baseRef=init_head), respond)
    assert seen["panel_r2"] is False
    assert payload["verdict"] == "handed-back"
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["decisions"][-1]["kind"] == "fix-surface-unknown", receipt["decisions"]
    first = receipt["rounds"][0]
    assert first["headDiffSource"] == "git", first
    assert first["headDiffCheck"] == "match", first


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

# The head-file lines the fix changed between _R2B_REVIEWED and _R2B_HEAD_MF: f.py line 2 (`+more` became
# `+fixed`) and the new hunk at 50-51, and the three lines of the new file g.py.
_R2B_FIX_LINES = {"f.py": [(2, 2), (50, 51)], "g.py": [(1, 3)]}


def _line_ranges(hunks):
    return {file: [(h["start"], h["end"]) for h in entries] for file, entries in hunks.items()}


def test_scoped_finder_payload_carries_computed_new_surface(tmp_path):
    """The dispatch-scoped-finder payload carries the fixes' own surface (file → the head lines the fixes
    changed + the delta text) — a multi-file surface must arrive intact, not empty (#507 WO-R2b:
    the field-found defect was an empty `hunks: {}` payload despite a real computed surface)."""
    d = str(tmp_path)
    captured = {"payload": None}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
            return {"seats": seats, "seatMap": _assertable_seat_map(["claude", "codex"])}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran", "reason": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_AUDITS:
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r",
                                 "evidence": "e", "auditorVendor": t.get("auditorVendor"),
                                 "checks": audit_checks()}
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            captured["payload"] = payload
            return {"findings": []}
        if phase == RD.P_APPLY_FIXES:
            return {"fixes": [], "headDiff": _R2B_HEAD_MF, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        return {}

    payload = _drive_cli(d, _cfg(diff=_R2B_REVIEWED), respond)
    assert payload["verdict"] == "converged"
    assert captured["payload"] is not None, "the scoped finder was never dispatched"
    hunks = captured["payload"]["hunks"]
    # the fixes' own surface — a non-empty, multi-file map, the fixed line of the audited hunk included.
    assert set(hunks) == {"f.py", "g.py"}, hunks
    assert _line_ranges(hunks) == _R2B_FIX_LINES


# =============================================================================
# apply-fixes head diff: inline OR absolute headDiffPath; unreadable → full panel (#507)
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
                    {"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
            return {"seats": seats, "seatMap": _assertable_seat_map(["claude", "codex"])}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran", "reason": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_AUDITS:
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r",
                                 "evidence": "e", "auditorVendor": t.get("auditorVendor"),
                                 "checks": audit_checks()}
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            captured["payload"] = payload
            return {"findings": []}
        if phase == RD.P_APPLY_FIXES:
            return dict(fixer_artifact)
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        return {}
    return respond


def test_fixer_head_diff_path_form_end_to_end(tmp_path):
    """An `apply-fixes` report may carry the post-fix head diff as an ABSOLUTE `headDiffPath` the
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
    assert _line_ranges(captured["payload"]["hunks"]) == _R2B_FIX_LINES
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert any(r.get("headDiffSource") == "path" for r in receipt["rounds"]), receipt["rounds"]


def test_fixer_unreadable_head_diff_path_with_repository_derives_git(tmp_path):
    """An unreadable `headDiffPath` (no inline diff) is never an empty surface. In a run with a
    repository the path is recorded `supplied-unreadable` and git governs the post-fix diff, so the
    delta round audits the fixes instead of running a full panel."""
    from test_round_driver_round_economy_1272 import _commit_in_repo, _init_ceiling_git_repo

    repo, init_head = _init_ceiling_git_repo(tmp_path)
    _commit_in_repo(repo, "panel-head")
    d = str(tmp_path)
    seed_session_meta(d, repo)
    missing = str(tmp_path / "does-not-exist.txt")
    seen = {"panel_r2": False, "scoped": False}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            if rnd >= 2:
                seen["panel_r2"] = True
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
            return {"seats": seats, "seatMap": _assertable_seat_map(["claude", "codex"])}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran", "reason": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_APPLY_FIXES:
            return {"fixes": [], "headDiffPath": missing, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        if phase == RD.P_SCOPED:
            seen["scoped"] = True
            return {"findings": []}
        if phase == RD.P_AUDITS:
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r", "evidence": "e",
                                 "auditorVendor": t.get("auditorVendor"), "checks": audit_checks()}
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_GAPSWEEP:
            return {"findings": []}
        return {}

    payload = _drive_cli(d, _cfg(repoRoot=repo, baseRef=init_head), respond)
    assert seen["panel_r2"] is False, "git governs an unreadable head diff path: no full panel"
    assert payload["verdict"] == "converged"
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert any(r.get("headDiffSource") == "git" and r.get("headDiffCheck") == "supplied-unreadable"
               for r in receipt["rounds"]), receipt["rounds"]
    assert not any(dc["kind"] == "unknown-surface" for dc in receipt["decisions"]), receipt["decisions"]


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
    assert _line_ranges(captured["payload"]["hunks"]) == _R2B_FIX_LINES
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert any(r.get("headDiffSource") == "inline" for r in receipt["rounds"]), receipt["rounds"]


# =============================================================================
# Layer 1 — run_loop (library) on each leg shape
# =============================================================================

def test_run_loop_code_leg_end_to_end(tmp_path):
    receipt = RD.run_loop(_seams(reviewer=lambda dim, tier, rnd, ctx:
                                 ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE,
                                                 "file": "f.py", "line": 1}]}
                                  if rnd == 1 and dim == "code-reviewer" else []),
                                 vendors=["claude", "codex"]),
                          _cfg_cert())
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"] is not None


def test_run_loop_returns_the_driver_receipt():
    result = RD.run_loop(_seams(), _cfg_cert())
    ok, reason = RD.validate_receipt(result)
    assert ok, reason
    assert result["verdict"] == "converged"
    for key in ("class", "loopTerminal", "loopRounds", "loopCertificationShape"):
        assert key not in result


def test_run_loop_invalid_max_rounds_returns_a_parked_receipt():
    result = RD.run_loop(_seams(), _cfg_cert(maxRounds=-1))
    assert result["verdict"] == "cannot-certify"
    assert result["certification"]["shape"] is None
    assert "class" not in result


def test_run_loop_unrecordable_journal_fault_returns_a_parked_receipt():
    def boom(*_a, **_k):
        raise RD.JournalFaultUnrecordable(OSError("journal"), OSError("marker"))
    result = RD.run_loop(_seams(reviewer=boom), _cfg_cert())
    assert result["verdict"] == "cannot-certify"
    assert "journal-fault-unrecordable" in result["certification"]["reason"]
    assert "class" not in result


def test_run_loop_panel_leg_shape(tmp_path):
    """The panel leg-shape config also drives run_loop end-to-end (a clean panel certifies)."""
    receipt = RD.run_loop(_seams(), _cfg_cert(leg="panel"))
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"] is not None


def _panel_finding_reviewer():
    finding = {"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [finding]}
        return []

    return reviewer


def test_run_seam_verifier_reason_less_verdict_returns_fault_directly():
    """axis: a reason-less verifier verdict is converted into _verifierArtifactFault, not a ruling."""
    def bad_verifier(clusters, rnd):
        return [{"id": i, "verdict": "CONFIRMED"}
                for c in (clusters or []) for i in (c.get("ids") or [])]

    state = RD.new_state(_cfg())
    result = RD._run_seam(
        _seams(verifier=bad_verifier),
        RD.P_VERIFIERS,
        {"clusters": [{"ids": ["f-1"]}]},
        state,
        state["config"],
    )
    fault = RD.verifier_results_fault({"verdicts": [{"id": "f-1", "verdict": "CONFIRMED"}]})
    assert result == {"verdicts": [], "_verifierArtifactFault": fault}
    assert "reason" in fault


def test_two_verifier_faults_in_one_round_are_both_recorded():
    wave = {"n": 0}

    def wave_verifier(clusters, rnd):
        wave["n"] += 1
        ids = [i for c in (clusters or []) for i in (c.get("ids") or [])]
        if wave["n"] == 1:
            return [{"id": i, "verdict": "CONFIRMED"} for i in ids]
        return [{"verdict": "CONFIRMED", "reason": "checked"} for _i in ids]

    finding = {"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f0.py", "line": 1}
    gap_finding = {"title": "gap", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f1.py", "line": 1}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "gap-sweep":
            return {"findings": [gap_finding]}
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [finding]}
        return []

    _result, state = _run_loop_capturing_state(
        _seams(reviewer=reviewer, verifier=wave_verifier, vendors=["claude", "codex"]),
        _cfg_cert(diff=_big_diff(25)),
    )
    faults = _state_verifier_faults(state)
    assert len(faults) == 2
    assert faults[0]["round"] == 1
    assert faults[1]["round"] == 1
    assert "reason" in faults[0]["fault"]
    assert "id" in faults[1]["fault"]
    assert faults[0]["fault"] != faults[1]["fault"]


def test_run_loop_verifier_reasonless_verdict_keeps_findings_plausible():
    def bad_verifier(clusters, rnd):
        return [{"id": i, "verdict": "CONFIRMED"}
                for c in (clusters or []) for i in (c.get("ids") or [])]

    result, state = _run_loop_capturing_state(
        _seams(reviewer=_panel_finding_reviewer(), verifier=bad_verifier, vendors=["claude", "codex"]),
        _cfg_cert(),
    )
    assert result["verdict"] != "cannot-certify"
    faults = _state_verifier_faults(state)
    assert faults
    assert any("reason" in entry["fault"] for entry in faults)
    r1 = [r for r in result["rounds"] if r["round"] == 1][0]
    assert r1["verifyPasses"][0]["PLAUSIBLE"] >= 1
    assert r1["verifyPasses"][0]["CONFIRMED"] == 0


def test_run_loop_verifier_valid_reason_control():
    def good_verifier(clusters, rnd):
        return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "reason": "checked", "evidence": "ran"}
                             for c in (clusters or []) for i in (c.get("ids") or [])],
                "vendor": "codex"}

    result, state = _run_loop_capturing_state(
        _seams(reviewer=_panel_finding_reviewer(), verifier=good_verifier, vendors=["claude", "codex"]),
        _cfg_cert(),
    )
    assert not _state_verifier_faults(state)
    r1 = [r for r in result["rounds"] if r["round"] == 1][0]
    assert r1["verifyPasses"][0]["CONFIRMED"] >= 1
    assert r1["verifyPasses"][0]["PLAUSIBLE"] == 0


def test_run_loop_certification_refusal_not_legacy_receipt():
    """Without a checked base guard the loop still terminates; run_loop never mints a legacy receipt."""
    result = RD.run_loop(_seams(), _cfg(leg="panel"))
    assert isinstance(result, dict)
    assert "terminalState" not in result
    assert result["verdict"] == "converged"


def test_run_loop_certification_success_carries_writer_fields():
    """With a checked base guard the loop converges; loop observables mirror build_receipt."""
    refusal, loop_receipt = _run_loop_with_loop_receipt(
        _seams(), _cfg(leg="panel", baseGuard=RD.BASE_GUARD_CHECKED))
    assert refusal["verdict"] == "converged"
    assert loop_receipt["verdict"] == "converged"
    assert refusal["certificationShape"] == loop_receipt["certificationShape"]
    assert "terminalState" not in refusal

# =============================================================================
# audit-keyed stall → self-recovery once → hand back
# =============================================================================

def _persistent_not_discharged_seams(io=None):
    counter = {"n": 0}

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [], "headDiff": _headf(counter["n"]), "changedSubjects": ["Code"]}

    def plaus_verifier(clusters, rnd):
        return [{"id": i, "verdict": "PLAUSIBLE", "reason": "checked"}
                for c in (clusters or []) for i in (c.get("ids") or [])]

    return _seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verifier=plaus_verifier,
        auditor=lambda targets, rnd: [{"id": t["id"], "ruling": "not-discharged", "reason": "broken",
                                       "checks": audit_checks(right="no")}
                                      for t in (targets or [])],
        fix_step=fix_step, io=io, vendors=["claude", "codex"])


def test_not_discharged_twice_self_recovers_once_then_is_handed_back(tmp_path):
    receipt = RD.run_loop(_persistent_not_discharged_seams(), _cfg_cert(maxRounds=20))
    recoveries = [r for r in receipt["rounds"] if r.get("selfRecovery")]
    assert len(recoveries) == 1
    assert receipt["verdict"] == "handed-back"
    assert receipt["decisions"][-1]["kind"] == "fix-keeps-failing"


_STALL_BREAKER = {"reason": "audit-stall", "detail": "stalled", "stalledIdentities": ["v0"]}


def test_a_stall_after_the_recovery_attempt_is_handed_back_not_put_to_the_owner():
    """A stall with selfRecovered already true hands the PR back (fix-keeps-failing) — no menu."""
    state = RD.new_state(_cfg())
    state["selfRecovered"] = True
    RD._handle_stall(state, state["config"], _STALL_BREAKER)
    assert state["terminal"] == "handed-back"
    assert state["step"] == RD.P_TERMINAL
    assert state["decisions"][-1] == {"round": state["round"], "kind": "fix-keeps-failing",
                                      "detail": "stalled"}
    assert state["certification"] == {"shape": None, "reason": "stalled"}


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
                 "auditorVendor": t.get("auditorVendor"), "checks": audit_checks()}
                for t in (targets or [])]

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [], "headDiff": _headf(counter["n"]), "changedSubjects": ["Code"]}

    def plaus_verifier(clusters, rnd):
        return [{"id": i, "verdict": "PLAUSIBLE", "reason": "checked"}
                for c in (clusters or []) for i in (c.get("ids") or [])]

    seams = _seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verifier=plaus_verifier,
        auditor=auditor,
        fix_step=fix_step,
        io=io or {}, vendors=["claude", "codex"])
    seams["_audit_calls"] = audit_calls
    seams["_fix_calls"] = counter
    return seams


def test_audit_stall_clears_on_clean_round_then_certifies_converged():
    """#960: stall on audit round 2, clean fold on round 3, converged certification on round 4.

    Historical stall pairs must not permanently block certification once a later audit round
  folds clean."""
    seams = _stall_then_clean_auditor_seams(clean_after=2)
    receipt = RD.run_loop(seams, _cfg_cert(maxRounds=20))
    assert receipt["verdict"] == "converged"
    assert receipt.get("certificationShape") is not None
    audit_rounds = [r for r in receipt["rounds"] if r.get("audits")]
    assert len(audit_rounds) >= 3
    assert any(r["round"] == 4 and r.get("audits") for r in receipt["rounds"])
    recoveries = [r for r in receipt["rounds"] if r.get("selfRecovery")]
    assert len(recoveries) == 1


# =============================================================================
# a delta round ends on its audit and scoped finder, never on a further panel
# =============================================================================

def _delta_state_ready(findings=None, not_discharged=None):
    state = RD.new_state(_cfg(maxRounds=20))
    state["round"] = 3
    state["findings"] = list(findings or [])
    state["fullPanelRan"] = False
    nd = not_discharged or []
    state["auditRounds"] = [{"round": 2, "outcomes": [{"identity": "x", "ruling": "discharged"}]}]
    state["_auditOutcome"] = {"notDischarged": nd, "discharged": ["x"]}
    state["_changedSubjects"] = ["Code"]
    state["seatMapReceipts"] = _seat_map_receipts(
        _assertable_seat_map(state["config"]["vendors"], state["config"].get("fixerVendor")))
    return state


def test_a_delta_settle_with_every_audit_discharged_certifies_audited_chain(tmp_path):
    """Re-pinned from the confirmation-cap tests: a delta round whose audits discharged and whose scoped
    finder raised nothing certifies `audited-chain`, with no panel step and no confirmation follow-up."""
    state = _delta_state_ready()
    RD._settle_delta(state, state["config"])
    assert state["terminal"] == "converged"
    assert state["certification"]["shape"] == "audited-chain"
    assert state["step"] != RD.P_PANEL
    assert not any(d["kind"] == "confirmation-rearm" for d in state["decisions"])


def test_a_critical_the_audit_did_not_discharge_never_schedules_a_panel(tmp_path):
    """Re-pinned from the Critical re-arm test: an audit that discharged nothing for a Critical target
    no longer owes a confirmation panel; the settle never steps to the panel."""
    state = _delta_state_ready(not_discharged=["x"])
    state["fixBatch"] = [{"file": "f.py", "line": 1, "title": "x", "severity": "Critical"}]
    RD._settle_delta(state, state["config"])
    assert state["step"] != RD.P_PANEL
    assert not any(d["kind"] == "confirmation-rearm" for d in state["decisions"])


def test_a_scoped_critical_is_fixed_and_audited_in_the_next_round_not_confirmed_by_a_panel(tmp_path):
    """Re-pinned from the confirmation-budget test: a Critical the scoped finder raises in round 2 is
    fixed and audited in a later round, and the review ends `audited-chain` with no panel after round 1."""
    scoped_state = {"fired": False}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "scoped-finder" and not scoped_state["fired"]:
            scoped_state["fired"] = True
            return [{"title": "hole", "severity": "Critical", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
        return []

    counter = {"n": 0}
    fixed, audited = {}, {}

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        fixed[rnd] = [b.get("title") for b in batch]
        return {"fixes": [], "headDiff": _headf_ns(counter["n"]), "changedSubjects": ["Code"]}

    def auditor(targets, rnd):
        audited[rnd] = [t.get("title") for t in (targets or [])]
        return [dict({"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                      "evidence": "tests pass", "auditorVendor": t.get("auditorVendor"),
                      "checks": audit_checks()}, **audit_test_match(t))
                for t in (targets or [])]

    receipt = RD.run_loop(_seams(reviewer=reviewer, fix_step=fix_step, auditor=auditor),
                          _cfg_cert(maxRounds=20, seatMap=_nonpanel_cell_proof(["claude", "codex"])))
    assert receipt["verdict"] == "converged"
    assert counter["n"] == 2
    assert "bug" in fixed[1] and "hole" in fixed[2]
    assert "hole" in audited[3]
    assert receipt["certificationShape"] == "audited-chain-degraded"
    assert not any(x["kind"] in ("confirmation", "full-panel-unknown-surface")
                   for x in receipt["rounds"])


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


def test_single_vendor_fix_is_never_audited_and_the_lost_independence_is_named(tmp_path):
    """A single live vendor that is the fixer's own: no auditor is seated, the audit counts as not
    run (the fix is never certified as audited) and the receipt names the lost independence."""
    seen = []

    def auditor(targets, rnd):
        seen.extend(dict(t) for t in (targets or []))
        return [{"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                 "evidence": "tests pass", "auditorVendor": "claude", "checks": audit_checks()}
                for t in (targets or [])]

    refusal, state = _run_loop_capturing_state(
        _seams(reviewer=lambda dim, tier, rnd, ctx:
               ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE,
                               "file": "f.py", "line": 1}]}
                if rnd == 1 and dim == "code-reviewer" else []), auditor=auditor),
        _cfg_cert(vendors=["claude"], fixerVendor="claude"))
    loop_receipt = RD.build_receipt(state)
    # The scoped finder, like the auditor, cannot be seated outside the fixer's family: the fixes' own
    # diff has no reviewer, so the review is not certified (re-pinned: it used to hand back before it).
    assert refusal["verdict"] == "cannot-certify" and refusal["certificationShape"] is None
    assert seen and all(t.get("auditorVendor") is None and t["independence"] == "unseatable"
                        for t in seen)
    assert state["independenceDegraded"] is True
    assert state["_auditOutcome"]["discharged"] == [] and state["_auditOutcome"]["unaudited"]
    assert loop_receipt["degraded"], "the lost independence must be named in the receipt"


def test_independent_auditor_selection_two_vendor(tmp_path):
    """#507 v8: with two live vendors the fix's auditor is the NON-fixer vendor (independent). The
    auditor seam captures its targets so the selection is asserted directly — a mutation that
    returns the fixer vendor as `auditorVendor` (losing independence) fails this test."""
    captured = {"targets": None}

    def auditor(targets, rnd):
        captured["targets"] = [dict(t) for t in (targets or [])]
        return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor"), "checks": audit_checks()}
                for t in (targets or [])]

    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=auditor), _cfg_cert(vendors=["claude", "codex"], fixerVendor="claude",
                                    seatMap=_nonpanel_cell_proof(["claude", "codex"])))
    assert receipt["verdict"] == "converged"
    assert captured["targets"], "the auditor must have received the fix's audit targets"
    t = captured["targets"][0]
    assert t["fixerVendor"] == "claude"
    assert t["auditorVendor"] == "codex"
    assert t["independence"] == "independent"
    assert receipt["certificationShape"] == "audited-chain-degraded"


def test_unknown_fixer_vendor_audit_does_not_run_end_to_end_two_vendor(tmp_path):
    """#608: omitting fixerVendor must not assume claude — an unknown fixer seats no auditor, so the
    audit does not run and nothing is certified as audited."""
    captured = {"targets": None}

    def auditor(targets, rnd):
        captured["targets"] = [dict(t) for t in (targets or [])]
        return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor"), "checks": audit_checks()}
                for t in (targets or [])]

    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
           "baseGuard": RD.BASE_GUARD_CHECKED}
    result = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=auditor), cfg)
    # re-pinned: the scoped finder over the fixes' own diff cannot be seated either, so the review parks
    assert result["verdict"] == "cannot-certify" and result["certificationShape"] is None
    t = captured["targets"][0]
    assert t["independence"] == "unseatable" and "auditorVendor" not in t


def test_explicit_cross_family_fixer_still_independent_two_vendor(tmp_path):
    """#608 contrast: known codex fixer with two vendors still yields independent audit."""
    captured = {"targets": None}

    def auditor(targets, rnd):
        captured["targets"] = [dict(t) for t in (targets or [])]
        return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor"), "checks": audit_checks()}
                for t in (targets or [])]

    # the build session (claude) and the codex fixer are both makers, so the scoped finder, which sits
    # outside every maker's family, is seated on a third vendor and reports that one
    cfg = {"leg": "code", "vendors": ["claude", "codex", "cursor"], "diff": DIFF, "fixerVendor": "codex",
           "baseGuard": RD.BASE_GUARD_CHECKED,
           "seatMap": _nonpanel_cell_proof(["claude", "codex", "cursor"])}
    receipt = RD.run_loop(_seams(
            reviewer=lambda dim, tier, rnd, ctx:
                ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
                 if rnd == 1 and dim == "code-reviewer"
                 else {"findings": [], "vendor": "cursor"} if dim == "scoped-finder" else []),
            auditor=auditor, fixer_vendor="codex"), cfg)
    assert receipt["verdict"] == "converged"
    t = captured["targets"][0]
    assert t["independence"] == "independent"
    assert receipt["certificationShape"] == "audited-chain-degraded"


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
                    "auditorVendor": "claude", "checks": audit_checks()}])
    assert out["discharged"] == []
    assert out["notDischarged"] == ["v0"]
    assert out["unauthenticated"] == ["v0"]
    # the orchestrator's manifest authenticates the codex dispatch → discharged, trusted vendor recorded
    ok = audits.apply_audit_results(
        [target], [{"id": "v0", "ruling": "discharged", "reason": "fix verified",
                    "auditorVendor": "codex", "checks": audit_checks()}],
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
    f = {"title": "leaks memory", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1,
         "dimension": "Security", "taxonomy": "CWE-401", "classKey": "Security::CWE-401::orig"}
    state["fixBatch"] = [f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tgt = state["_auditTargets"][0]
    assert tgt["classKey"] == "Security::CWE-401::orig"
    RD._fold_audits(state, state["config"], {"results": [
        {"id": tgt["id"], "ruling": "not-discharged", "reason": "still broken",
         "checks": audit_checks(right="no")}]})
    round1 = state["auditRounds"][-1]
    assert round1["outcomes"][0]["classKey"] == "Security::CWE-401::orig"
    # a SECOND round: the finding is retitled (a different identity) but keeps its classKey.
    retitled = {"round": state["round"] + 1, "outcomes": [
        {"identity": "f.py::memory not freed", "ruling": "not-discharged",
         "classKey": "Security::CWE-401::orig", "dimension": "Security", "taxonomy": "CWE-401"}]}
    brk = CB.check_audit_breaker([round1, retitled])
    assert brk["halt"] and brk["reason"] == "audit-stall", brk


def test_audit_outcome_carries_title_so_distinct_classkeys_dont_false_stall(tmp_path):
    """#507 R2 v2: two DISTINCT classKeys that share dimension+taxonomy must NOT collide into a
    false audit-stall. The live outcome now carries `title`, so the breaker's canonical class key is
    the full `dim::tax::title`, not the title-less `dim::tax::` alias that merged unrelated findings."""
    import circuit_breaker as CB

    def fold(title, classkey):
        state = RD.new_state(_cfg())
        state["fixBatch"] = [{"title": title, "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1,
                              "dimension": "Security", "taxonomy": "CWE-401", "classKey": classkey}]
        state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
        tgt = state["_auditTargets"][0]
        RD._fold_audits(state, state["config"], {"results": [
            {"id": tgt["id"], "ruling": "not-discharged", "reason": "still broken",
             "checks": audit_checks(right="no")}]})
        return state["auditRounds"][-1]

    r1 = fold("secret a", "Security::CWE-401::secret a")
    assert r1["outcomes"][0]["title"] == "secret a"
    r2 = {"round": 2, "outcomes": fold("secret b", "Security::CWE-401::secret b")["outcomes"]}
    brk = CB.check_audit_breaker([r1, r2])
    assert not brk["halt"], brk  # two distinct classKeys → NOT a stall


def test_omitted_seat_zero_finding_withholds_certification(tmp_path):
    """#507 R2 residual-1: an omitted panel seat with ZERO findings must WITHHOLD certification — an
    incomplete panel is 'we did not look', never a clean audited-chain. The converge parks."""
    def reviewer(dim, tier, rnd, ctx):
        return None if dim == "premortem-reviewer" else []

    receipt = RD.run_loop(_seams(reviewer=reviewer), _cfg_cert())
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
    result = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "skipped"), _cfg_cert(verifyCommand="pytest -q"))
    assert result["verdict"] == "halted"


def test_verify_skip_with_no_command_still_advances(tmp_path):
    """A skip result with NO verify command configured is a legitimate unverified advance."""
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "none"),
        _cfg_cert(verifyCommand="none", seatMap=_nonpanel_cell_proof(["claude", "codex"])))
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
    state["findings"] = [{"title": "same bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 2}]
    RD._settle_delta(state, state["config"])
    assert state["step"] == RD.P_APPLY_FIXES
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
    refusal, loop_receipt = _run_loop_with_loop_receipt(_seams(reviewer=boom), _cfg_cert())
    assert refusal["verdict"] == "cannot-certify"
    assert loop_receipt["certification"]["shape"] is None
    assert "journal-fault-unrecordable" in loop_receipt["certification"]["reason"]


# --- replayed-terminal receipt-fault re-check (#507) --------------------------------------------
# A REPLAYED terminal `next` (a `next` on a session already at its terminal step) re-emits the stored
# pending WITHOUT re-running _finalize_receipt — so a receipt fault recorded/surfaced AFTER the first
# emission (a fault marker, or a round-receipt.json corrupted/invalidated since) would be masked by
# the replay's ok. Every terminal `next` — first emission AND replays — now re-verifies the on-disk
# receipt and fails LOUD `receipt-fault` (nonzero) on any fault, never terminal-with-ok.

def test_terminal_finish_writes_no_certification_artifact(tmp_path):
    """The terminal finish writes round-receipt.json and nothing else beside it for certification."""
    d = str(tmp_path)
    payload = _drive_cli(d, _cfg(), _responder(round1_findings=None))
    assert payload["verdict"] == "converged"
    names = os.listdir(d)
    assert RD.RECEIPT_FILE in names
    assert "certification-receipt.json" not in names
    assert "certification-refusal.json" not in names
    replay = RD.cmd_next(d)
    assert replay["ok"] is True
    assert replay["action"] == RD.P_TERMINAL


def test_old_certification_files_are_left_alone(tmp_path):
    """A certification file left in the session directory by an older driver is neither read,
    rewritten nor deleted by the terminal finish."""
    d = str(tmp_path)
    old = os.path.join(d, "certification-refusal.json")
    with open(old, "wb") as fh:
        fh.write(b'{"class": "old"}')
    payload = _drive_cli(d, _cfg(), _responder(round1_findings=None))
    assert payload["verdict"] == "converged"
    with open(old, "rb") as fh:
        assert fh.read() == b'{"class": "old"}'
    replay = RD.cmd_next(d)
    assert replay["ok"] is True
    assert replay["action"] == RD.P_TERMINAL


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
    _drive_cli(d, _cfg(seatMap=_nonpanel_cell_proof(["claude", "codex"])), _responder(
        round1_findings=[{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]))
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    provs =[r.get("auditProvenance") for r in receipt["rounds"]]
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


def test_terminating_submit_receipt_fault_after_fold_lands_carries_foldLanded(tmp_path):
    """A fold that commits then fails the terminal receipt gate must still answer foldLanded."""
    _args, s = _drive_capturing_terminating_submit(str(tmp_path), plant_fault=True)
    assert s["ok"] is False
    assert s["reason"] == "receipt-fault"
    assert s.get("foldLanded") is True


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


def test_duplicate_terminating_submit_fault_carries_foldLanded(tmp_path):
    """The fold landed before the gate faulted, so the duplicate replay must still mark foldLanded —
    deleting the assignment must go red here."""
    d = str(tmp_path)
    args, first = _drive_capturing_terminating_submit(d, plant_fault=True)
    assert first["ok"] is False and first["reason"] == "receipt-fault"
    dup = RD.cmd_submit(d, *args)
    assert dup["ok"] is False
    assert dup["duplicate"] is True
    assert dup.get("foldLanded") is True


def test_fold_audits_authenticates_against_recorded_auditor(tmp_path):
    """#507 R2 residual-6: _fold_audits passes the DRIVER-recorded auditor map, so a clearing result
    echoing the FIXER vendor (a self-audit) is rejected not-discharged — the claimant echo never
    authenticates, and the recorded auditor is the trusted driver value."""
    state = RD.new_state(_cfg())  # vendors claude+codex, fixer claude → the auditor is codex
    state["round"] = 2
    state["fixBatch"] = [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tgt = state["_auditTargets"][0]
    assert tgt["auditorVendor"] == "codex"
    RD._fold_audits(state, state["config"], {"results": [
        {"id": tgt["id"], "ruling": "discharged", "reason": "self-clear",
         "auditorVendor": "claude", "checks": audit_checks()}]})  # echoes the FIXER, not the recorded codex
    assert state["_auditOutcome"]["unauthenticated"] == [tgt["id"]]
    assert state["_auditOutcome"]["discharged"] == []


def test_owner_choice_holds_are_distinct_for_same_title_different_lines():
    """#507 R2 v5: two same-title tradeoff blockers at DIFFERENT lines are held under DISTINCT keys,
    so a ruling on the one never settles the other (the line-less id collapsed them)."""
    a = {"title": "same choice", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 10,
         "tradeoff": True}
    b = {"title": "same choice", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 20,
         "tradeoff": True}
    state = RD.new_state(_cfg())
    assert RD._hold_owner_choice(state, [dict(a), dict(b)]) == []
    assert len(set(state["ownerChoiceHeld"])) == 2, state["ownerChoiceHeld"]
    assert state["ownerChoiceHeld"] == [RD._finding_key_of(a), RD._finding_key_of(b)]


def test_receipt_missing_seat_surfaces_unverified(tmp_path):
    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "security-reviewer":
            return {"findings": [{"title": "leak", "severity": "Important", "consequence": _CONSEQUENCE,
                                  "file": "f.py", "line": 1}],
                    "receiptMissing": True}
        return []

    receipt = RD.run_loop(_seams(reviewer=reviewer,
                                 verifier=lambda cl, rnd: [{"id": i, "verdict": "PLAUSIBLE",
                                                            "reason": "checked"}
                                                           for c in (cl or []) for i in c.get("ids", [])]),
                          _cfg_cert())
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
    _refusal, receipt = _run_loop_with_loop_receipt(_seams(), _cfg_cert())
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason
    missing_scriptran = dict(receipt)
    del missing_scriptran["scriptRan"]
    ok2, why2 = RD.validate_receipt(missing_scriptran)
    assert ok2 is False and "scriptRan" in why2
    missing_seatmap = dict(receipt)
    del missing_seatmap["seatMap"]
    ok3, why3 = RD.validate_receipt(missing_seatmap)
    assert ok3 is False and "seatMap" in why3
    assert RD.validate_receipt(None)[0] is False


# =============================================================================
# verify-gate fail halts; mechanical compile
# =============================================================================

def test_verify_fail_halts(tmp_path):
    result = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "fail"), _cfg_cert())
    assert result["verdict"] == "halted"


def test_verify_timeout_halts(tmp_path):
    """#507 v10: a verify result that is not `pass`/skip — here `timeout` — fails closed to a halt,
    never advancing into a delta round that could certify."""
    result = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "timeout"), _cfg_cert())
    assert result["verdict"] == "halted"


def test_omitted_panel_seat_cannot_certify_full_panel(tmp_path):
    """#507 v11: a configured dimension with NO seat in the panel artifact is a silent coverage gap
    → status `missing`, surfaced, and the clean finish can never be full-panel-confirmed."""
    def reviewer(dim, tier, rnd, ctx):
        if dim == "premortem-reviewer":
            return None  # omitted seat
        return []

    receipt = RD.run_loop(_seams(reviewer=reviewer), _cfg_cert())
    assert receipt["certificationShape"] != "full-panel-confirmed"
    r1 = [x for x in receipt["rounds"] if x["round"] == 1][0]
    assert r1["seatStatus"]["premortem-reviewer"] == "missing"


def test_mechanical_compile_drops_uncited_and_out_of_scope():
    findings = [
        {"title": "cited", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 2},   # in diff scope
        {"title": "uncited", "severity": "Important", "consequence": _CONSEQUENCE, "file": None, "line": None},  # citation drop
        {"title": "off-scope", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 999},  # scope drop
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
        {"title": "Same bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1},
        {"title": "Same bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 2},
    ]
    compiled, _ = RD.mechanical_compile(findings, DIFF)
    assert sorted(f.get("line") for f in compiled) == [1, 2]


def test_mechanical_compile_nit_cap():
    findings = [{"title": "nit%d" % i, "severity": "Nit", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1,
                 "consequenceKind": "code-quality"}
                for i in range(9)]
    compiled, _ = RD.mechanical_compile(findings, None)
    nits = [f for f in compiled if f.get("severity") == "Nit"]
    # 5 kept + 1 summary entry.
    assert sum(1 for f in nits if not f.get("summaryEntry")) <= RD._NIT_CAP
    assert any(f.get("summaryEntry") for f in nits)


def test_mechanical_compile_nit_cap_lowercase_equivalent_to_exact_case():
    """Lowercase 'nit' severity variants count toward the Nit cap like exact-case 'Nit'."""
    def _findings(severity):
        # a stated consequence and the code-quality kind: the finding survives compile and reaches the cap
        return [
            {"title": "nit%d" % i, "severity": severity, "consequence": _CONSEQUENCE, "file": "f.py",
             "line": i + 1, "consequenceKind": "code-quality"}
            for i in range(9)
        ]

    def _post_cap_counts(compiled):
        nits = [
            f for f in compiled
            if RD.circuit_breaker.canonical_severity(f.get("severity")) == "Nit"
        ]
        return (
            sum(1 for f in nits if not f.get("summaryEntry")),
            sum(1 for f in nits if f.get("summaryEntry")),
            len(compiled),
        )

    compiled_lower, _ = RD.mechanical_compile(_findings("nit"), None)
    compiled_exact, _ = RD.mechanical_compile(_findings("Nit"), None)
    assert _post_cap_counts(compiled_exact) == (RD._NIT_CAP, 1, RD._NIT_CAP + 1)  # the cap really acted
    assert _post_cap_counts(compiled_lower) == _post_cap_counts(compiled_exact)
    # compile canonicalizes severity before the cap, so only a direct call puts "nit" in front of the cap itself
    capped_lower = RD._nit_cap(_findings("nit"))
    capped_exact = RD._nit_cap(_findings("Nit"))
    assert _post_cap_counts(capped_exact) == (RD._NIT_CAP, 1, RD._NIT_CAP + 1)
    assert _post_cap_counts(capped_lower) == _post_cap_counts(capped_exact)


def test_mechanical_compile_normalizes_list_dimension():
    findings = [
        {"title": "hole", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 2,
         "dimension": ["security", "perf"]},
    ]
    compiled, drops = RD.mechanical_compile(findings, DIFF)
    assert drops == []
    assert len(compiled) == 1
    assert compiled[0]["dimension"] == "security + perf"


def test_settle_delta_list_dimension_via_mechanical_compile(tmp_path):
    """#583: list-valued dimension must not crash _settle_delta's dim_map grouping."""
    raw = [{"title": "hole", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 2,
            "dimension": ["security", "perf"]}]
    compiled, _ = RD.mechanical_compile(raw, DIFF)
    state = _delta_state_ready(findings=compiled)
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

_CHALLENGED_FINDING = {"title": "coverage decision is false", "severity": "Important", "consequence": _CONSEQUENCE,
                       "file": "f.py", "line": 1, "dimension": "Test", "taxonomy": "coverage",
                       "classKey": "Test::coverage::x"}


def test_challenged_coverage_recurrence_cannot_certify(tmp_path):
    """A coverage decision recorded on a principle the reviewer keeps raising (challenged) whose
    class RECURS parks (cannot-certify) — never a silent clean (the wrong_principle property)."""
    records = tmp_path / "round-records.json"
    records.write_text("[]")

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "test-role":
            return {"findings": [dict(_CHALLENGED_FINDING)]}
        if dim == "scoped-finder":
            return [dict(_CHALLENGED_FINDING)]
        return []

    def fix_step(batch, rnd, payload):
        return {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Test"],
                "coverageDecisions": [{"id": "RCD-x", "classKey": "Test::coverage::x"}]}

    result = RD.run_loop(
        _seams(reviewer=reviewer, fix_step=fix_step),
        _cfg_cert(dimensions=["test-role"], recordsPath=str(records), maxRounds=20))
    assert result["verdict"] == "cannot-certify"
    assert result["certificationShape"] is None


def test_plain_recurring_finding_without_challenge_is_not_challenged_halt(tmp_path):
    """A recurring finding WITHOUT a challenged coverage decision is NOT parked by the challenged
    breaker (the driver's delta/audit path owns that case) — only the challenged path halts here."""
    records = tmp_path / "round-records.json"
    records.write_text("[]")

    fired = {"scoped": 0}

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "test-role":
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
        _seams(reviewer=reviewer, fix_step=fix_step, vendors=["claude", "codex"]),
        _cfg_cert(dimensions=["test-role"], recordsPath=str(records), maxRounds=20))
    assert receipt["verdict"] != "cannot-certify"
    assert fired["scoped"] == 1, "the scoped finder must fire over the real new surface"


# =============================================================================
# #720: the per-round DISCLOSURE channels the records writer persists
# =============================================================================

# One populated value per channel in CARRIED_DISCLOSURE_CHANNELS, shaped exactly as `_fold_panel`
# records it. Used by the all-channel producer test; NOT a second copy of the channel list — the test
# asserts this map's keys equal the module constant's, so a new channel fails here too.
_ALL_CHANNELS = {
    "fellOpen": [{"seat": "test-role", "configured": "codex", "reason": "forfeit",
                  "ran": "claude"}],
    "fellOpenProvenanceMissing": ["security-reviewer"],
    "seatMapUnavailable": ["codex"],
    "seatMapViolations": [{"constraint": "cross-vendor", "seat": "code-reviewer",
                           "evidence": "alternative-live"}],
    "vacuousSeats": ["architecture-reviewer"],
    "engagedArtifactSeats": ["premortem-reviewer"],
    "adapterProvenance": {"vendorEchoMismatch": [{"seat": "test-role", "echo": "cursor",
                                                  "manifest": "codex"}]},
    "recordOrphansIgnored": ["code-reviewer"],
    "orderVendorProvenanceGaps": [{"seat": "architecture-reviewer",
                                   "storeKey": "architecture-reviewer", "occurrence": 0}],
    "priorCommentsUnavailable": True,
    "verifyPasses": [{"CONFIRMED": 1, "PLAUSIBLE": 0, "REFUTED": 0, "drops": 0,
                      "downgrades": 0, "unverified": 0, "ambiguous": 0}],
    "verifierProvenance": [{"expected": "codex", "ran": "claude", "outcome": "verdicts-ignored"}],
    "synthesisUnseatable": [{"makerFamilies": ["anthropic"], "fixerVendor": "claude"}],
    "secondTestUnseatable": [{"makerFamilies": ["anthropic"], "fixerVendor": "claude",
                              "held": ["f.py::bug@L1"]}],
    "seatMapUnjudgeable": [_load("seat_map").VIOLATION_BASIS_NO_AUTHOR_FAMILY],
    "judgmentDispositions": [{"id": "f.py::tradeoff@L1", "title": "tradeoff",
                              "disposition": "fix-with-guidance",
                              "userGuidance": "keep narrow"}],
    "gateGuidanceRowCarried": [{"index": 0, "title": "orphan row"}],
    "breakItRuns": [{"role": "test-role", "path": "tests/test_x.py", "outcome": "failed",
                     "findingKey": "k"}],
    "breakItKept": [{"findingKey": "k", "path": "tests/test_x.py", "outcome": "kept"}],
    "verifyVia": {"via": "local", "command": "make test"},
}


def _seed_record(round_no, disclosures=None, **over):
    rec = {"schemaVersion": 2, "round": round_no, "kind": "baseline",
           "dimensions": {"test-role": {"status": "run", "confidence": "high",
                                            "tier": "reviewer-deep", "findings": []}},
           "findings": [], "coverageDecisions": []}
    if disclosures is not None:
        rec["disclosures"] = disclosures
    rec.update(over)
    return rec


def _round_channels(receipt, round_no, loop_receipt=None):
    """The disclosure channels the receipt's round entry actually carries."""
    rounds = _loop_rounds(receipt)
    entry = next((r for r in rounds if r["round"] == round_no), None)
    assert entry is not None, (
        "the receipt has no round %d entry at all — that round's disclosures were dropped "
        "(rounds present: %s)" % (round_no, [r["round"] for r in rounds]))
    return {k: v for k, v in entry.items() if k in RD.CARRIED_DISCLOSURE_CHANNELS}


def _round_disclosures(receipt, round_no, loop_receipt=None):
    degraded = (loop_receipt or receipt).get("degraded") or []
    return [line for line in degraded if "(round %d)" % round_no in line]


def test_driver_persists_round_disclosures(tmp_path):
    """The driver writes per-round disclosure channels to round-records.json after each fold."""
    records = tmp_path / "round-records.json"
    records.write_text("[]")
    cfg = _cfg_cert(dimensions=["test-role", "code-reviewer"], recordsPath=str(records),
               maxRounds=8)
    RD.run_loop(_vacuous_round1_seams(), cfg)

    on_disk = json.loads(records.read_text())
    round1 = next(r for r in on_disk if r.get("round") == 1)
    assert round1.get("disclosures", {}).get("vacuousSeats") == ["test-role"]


def test_producer_emits_the_whole_declared_channel_set(tmp_path):
    assert set(_ALL_CHANNELS) == set(RD.CARRIED_DISCLOSURE_CHANNELS), \
        "this fixture must cover exactly the restorable channel set"
    records = tmp_path / "round-records.json"
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    state["rounds"]["1"] = dict(_ALL_CHANNELS)
    state["_records"] = [_seed_record(1)]
    RD._persist_round_records(state, state["config"])
    on_disk = json.loads(records.read_text())
    rec = next(r for r in on_disk if r.get("round") == 1)
    assert rec["disclosures"] == _ALL_CHANNELS


def test_producer_normalizes_non_int_round_key_like_the_restorer(tmp_path):
    """A ledger record carrying round `1.0` must persist round 1's disclosures — the producer keys
    the rounds map through the shared `_round_disclosure_key` (int-normalized), never `str(1.0)`."""
    records = tmp_path / "round-records.json"
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    state["rounds"]["1"] = {"vacuousSeats": ["test-role"]}
    rec = _seed_record(1)
    rec["round"] = 1.0
    state["_records"] = [rec]
    RD._persist_round_records(state, state["config"])
    on_disk = json.loads(records.read_text())
    out = next(r for r in on_disk if int(r.get("round")) == 1)
    assert out.get("disclosures", {}).get("vacuousSeats") == ["test-role"]


def test_round_disclosure_key_rejects_junk_and_never_aliases():
    """One home for the round key: ints/integral floats/int-strings normalize; a non-integral
    float must NOT truncate onto a real round's evidence; junk returns None, never raises."""
    assert RD._round_disclosure_key(1) == "1"
    assert RD._round_disclosure_key(1.0) == "1"
    assert RD._round_disclosure_key("1") == "1"
    assert RD._round_disclosure_key(1.5) is None
    assert RD._round_disclosure_key(float("inf")) is None
    assert RD._round_disclosure_key(True) is None
    assert RD._round_disclosure_key(None) is None
    assert RD._round_disclosure_key("junk") is None


def test_producer_skips_block_for_non_integral_round_without_aliasing(tmp_path):
    """A `1.5` ledger record persists NO disclosure block (and does not crash on `inf`) —
    round 1's evidence must never be duplicated onto a junk-round record."""
    records = tmp_path / "round-records.json"
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    state["rounds"]["1"] = {"vacuousSeats": ["test-role"]}
    rec_half = _seed_record(1)
    rec_half["round"] = 1.5
    rec_inf = _seed_record(2)
    rec_inf["round"] = float("inf")
    state["_records"] = [rec_half, rec_inf]
    RD._persist_round_records(state, state["config"])
    assert state.get("terminal") is None
    on_disk = json.loads(records.read_text())
    assert all("disclosures" not in r for r in on_disk)


def test_producer_omits_the_disclosures_key_when_no_channel_survives(tmp_path):
    records = tmp_path / "round-records.json"
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    state["rounds"]["1"] = {"seatStatus": {"test-role": "run"}, "roundKind": "baseline"}
    state["_records"] = [_seed_record(1)]
    RD._persist_round_records(state, state["config"])
    rec = next(r for r in json.loads(records.read_text()) if r.get("round") == 1)
    assert "disclosures" not in rec


def test_producer_writes_skeletons_not_evidence_bodies(tmp_path):
    big = "evidence-body-" + ("X" * 400)
    finding = {"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1,
               "dimension": "Code", "body": big, "evidence": big}
    records = tmp_path / "round-records.json"
    record = _seed_record(1, {"vacuousSeats": ["test-role"]})
    record["findings"] = [finding]
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    state["_records"] = [record]
    state["rounds"]["1"] = {"vacuousSeats": ["test-role"]}
    RD._persist_round_records(state, state["config"])
    raw = records.read_text()
    assert big not in raw
    persisted = next(r for r in json.loads(raw) if r.get("round") == 1)
    assert persisted["findings"][0]["title"] == "bug"
    assert persisted["findings"][0]["file"] == "f.py"


def test_producer_replaces_a_preexisting_records_file_with_this_sessions_ledger(tmp_path):
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1, {"vacuousSeats": ["x"]}),
                                   _seed_record(7, {"vacuousSeats": ["stale-seat"]})]))
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    state["_records"] = [_seed_record(1)]
    state["rounds"]["1"] = {"vacuousSeats": ["live-seat"]}
    RD._persist_round_records(state, state["config"])
    expected = RD.review_memory.summarize_record(_seed_record(1))
    expected["disclosures"] = {"vacuousSeats": ["live-seat"]}
    assert records.read_bytes() == RD.review_memory.records_bytes([expected])
    assert not any(r.get("round") == 7 for r in json.loads(records.read_text()))


def test_producer_parks_when_the_durable_write_fails(tmp_path, monkeypatch):
    records = tmp_path / "round-records.json"
    initial_text = json.dumps(
        [_seed_record(1, {"vacuousSeats": ["x"]}), _seed_record(7, {"vacuousSeats": ["y"]})],
        indent=2) + "\n"
    records.write_text(initial_text)
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    state["_records"] = [
        _seed_record(1, {"vacuousSeats": ["a"]}),
        _seed_record(2, {"vacuousSeats": ["b"]}),
    ]
    state["rounds"]["1"] = {"vacuousSeats": ["a"]}
    state["rounds"]["2"] = {"vacuousSeats": ["b"]}

    def _fail_write(path, data):
        raise OSError(5, "write-failed")

    monkeypatch.setattr(RD.round_commit, "atomic_write_bytes", _fail_write)
    RD._persist_round_records(state, state["config"])
    assert state["terminal"] == "cannot-certify"
    detail = next(d["detail"] for d in state["decisions"] if d["kind"] == "cannot-certify")
    assert "could not be persisted" in detail
    assert "write-failed" in detail
    assert records.read_text() == initial_text


def test_producer_parks_when_the_atomic_write_raises_oserror(tmp_path, monkeypatch):
    records = tmp_path / "round-records.json"
    records.write_text("[]")
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    state["_records"] = [_seed_record(1)]
    state["rounds"]["1"] = {"vacuousSeats": ["test-role"]}

    def _raise_oserror(path, data):
        raise OSError(13, "permission denied")

    monkeypatch.setattr(RD.round_commit, "atomic_write_bytes", _raise_oserror)
    RD._persist_round_records(state, state["config"])
    assert state["terminal"] == "cannot-certify"
    assert "permission denied" in next(
        d["detail"] for d in state["decisions"] if d["kind"] == "cannot-certify")


def test_producer_park_after_panel_fold_carries_toverify_findings(tmp_path, monkeypatch):
    records = tmp_path / "round-records.json"
    records.write_text("[]")
    finding = {"title": "panel-bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1,
               "dimension": "Code"}
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    state["findings"] = []
    state["_toVerify"] = [finding]
    state["_records"] = [_seed_record(1)]
    state["rounds"]["1"] = {"vacuousSeats": ["test-role"]}

    def _raise_oserror(path, data):
        raise OSError(5, "write-failed")

    monkeypatch.setattr(RD.round_commit, "atomic_write_bytes", _raise_oserror)
    RD._persist_round_records(state, state["config"])
    receipt = RD.build_receipt(state)
    assert receipt["findings"]
    assert any(f.get("title") == "panel-bug" for f in receipt["findings"])


def test_producer_empty_ledger_leaves_destination_unchanged(tmp_path):
    records = tmp_path / "round-records.json"
    initial_text = RD.review_memory.records_bytes([_seed_record(1)]).decode("utf-8")
    records.write_text(initial_text)
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    state["_records"] = []
    RD._persist_round_records(state, state["config"])
    assert records.read_text() == initial_text
    assert state.get("terminal") is None


def test_producer_is_inert_without_a_records_path(tmp_path, monkeypatch):
    state = RD.new_state(_cfg(dimensions=["test-role"]))
    state["_records"] = [_seed_record(1)]
    state["rounds"]["1"] = {"vacuousSeats": ["test-role"]}
    persisted = []
    monkeypatch.setattr(RD.review_memory, "persist_record",
                        lambda *a, **k: persisted.append(a) or {"ok": True})
    RD._persist_round_records(state, state["config"])
    assert state.get("terminal") is None
    assert persisted == []


def _vacuous_round1_seams():
    """Round 1: one vacuous seat (a real `vacuousSeats` + `seatMapUnavailable` record) plus a
    blocking finding so the run continues past round 1 to a terminal."""
    finding = {"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 2,
               "dimension": "Code"}

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "test-role":
            return {"vacuous": True, "findings": []}
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [dict(finding)]}
        return []

    def fix_step(batch, rnd, payload):
        return {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Code"]}

    return _seams(reviewer=reviewer, fix_step=fix_step)


def test_prior_comments_unavailable_discloses_on_receipt(tmp_path):
    """PR-mode absence of prior-comments.json is a provenance gap that must ride the receipt —
    not only live in state where build_receipt drops it."""
    session_dir = str(tmp_path / "pr-session")
    os.makedirs(session_dir)
    os.makedirs(os.path.join(session_dir, "repo"))
    state = RD.new_state(_cfg())
    RD._resolve_prior_comments_path(session_dir, state)
    assert state["rounds"]["1"]["priorCommentsUnavailable"] is True
    receipt = RD.build_receipt(state)
    assert _round_channels(receipt, 1).get("priorCommentsUnavailable") is True


def test_prior_comments_unavailable_degraded_prose_on_receipt():
    """Round-recorded priorCommentsUnavailable must name the round and the missing prior comments."""
    state = RD.new_state(_cfg(dimensions=["test-role"]))
    state["rounds"] = {"1": {"priorCommentsUnavailable": True}}
    receipt = RD.build_receipt(state)
    prose = "\n".join(_round_disclosures(receipt, 1))
    assert (
        "prior-comments-unavailable (round 1): orchestrator did not supply prior-comments.json "
        "in PR mode — panel ran without prior PR comments; any claim that prior comments were "
        "considered is not supported for this round"
        in prose
    )


def test_judgment_fail_closed_dispositions_degraded_on_receipt():
    """Fail-closed judgment folds disclose round and count on the receipt degraded list."""
    state = RD.new_state(_cfg(dimensions=["test-role"]))
    state["rounds"] = {"1": {"judgmentDispositions": [
        {"id": "f.py::widen the api@L1", "title": "widen the API",
         "disposition": "fix-as-suggested", "failClosed": True},
        {"id": "f.py::other@L2", "title": "other tradeoff",
         "disposition": "fix-as-suggested", "failClosed": True},
    ]}}
    receipt = RD.build_receipt(state)
    lines = [d for d in receipt["degraded"] if "judgment-fail-closed" in d]
    assert len(lines) == 1
    assert "round 1" in lines[0]
    assert "2 judgment blocker(s)" in lines[0]


def test_judgment_valid_dispositions_not_degraded_on_receipt():
    """All-valid judgment dispositions must not add a fail-closed degradation line."""
    state = RD.new_state(_cfg(dimensions=["test-role"]))
    state["rounds"] = {"1": {"judgmentDispositions": [
        {"id": "f.py::widen the api@L1", "title": "widen the API",
         "disposition": "fix-as-suggested"},
        {"id": "f.py::narrow@L2", "title": "narrow the API",
         "disposition": "fix-with-guidance", RD.GATE_GUIDANCE_RECORD_KEY: "keep compatible"},
    ]}}
    receipt = RD.build_receipt(state)
    assert not any("judgment-fail-closed" in d for d in receipt["degraded"])


def test_judgment_fail_closed_degraded_omits_guidance_and_title():
    """Fail-closed degradation names only round and count — never guidance text or finding titles."""
    distinctive_guidance = "ZQ_DISCLOSURE_MUST_NOT_LEAK_THIS_GUIDANCE"
    distinctive_title = "ZQ_DISCLOSURE_MUST_NOT_LEAK_THIS_TITLE"
    state = RD.new_state(_cfg(dimensions=["test-role"]))
    state["rounds"] = {"1": {"judgmentDispositions": [
        {"id": "f.py::widen the api@L1", "title": distinctive_title,
         "disposition": "fix-as-suggested", "failClosed": True,
         RD.GATE_GUIDANCE_RECORD_KEY: distinctive_guidance},
    ]}}
    receipt = RD.build_receipt(state)
    lines = [d for d in receipt["degraded"] if "judgment-fail-closed" in d]
    assert len(lines) == 1
    assert distinctive_guidance not in lines[0]
    assert distinctive_title not in lines[0]


def test_judgment_fail_closed_degraded_per_round():
    """Fail-closed entries across multiple rounds each get their own degradation line."""
    state = RD.new_state(_cfg(dimensions=["test-role"]))
    state["rounds"] = {
        "1": {"judgmentDispositions": [
            {"id": "a", "disposition": "fix-as-suggested", "failClosed": True}]},
        "2": {"judgmentDispositions": [
            {"id": "b", "disposition": "fix-as-suggested", "failClosed": True},
            {"id": "c", "disposition": "fix-as-suggested", "failClosed": True}]},
    }
    receipt = RD.build_receipt(state)
    lines = [d for d in receipt["degraded"] if "judgment-fail-closed" in d]
    assert len(lines) == 2
    assert any("round 1" in line and "1 judgment blocker(s)" in line for line in lines)
    assert any("round 2" in line and "2 judgment blocker(s)" in line for line in lines)


def test_malformed_order_vendor_gap_in_session_does_not_crash_receipt():
    """Malformed gap row recorded in-session is skipped at render; receipt still produced."""
    state = RD.new_state(_cfg(dimensions=["test-role"]))
    state["rounds"] = {"1": {"orderVendorProvenanceGaps": [{"seat": 7}]}}
    receipt = RD.build_receipt(state)
    assert isinstance(receipt["degraded"], list)
    assert not any("order-vendor-provenance-gap" in line for line in receipt["degraded"])


def test_order_vendor_gap_missing_occurrence_still_valid():
    """occurrence is optional on gap rows — well-shaped without it."""
    gaps = [{"seat": "architecture-reviewer"}]
    assert RD.CARRIED_DISCLOSURE_CHANNELS["orderVendorProvenanceGaps"](gaps)
    state = RD.new_state(_cfg(dimensions=["test-role"]))
    state["rounds"] = {"1": {"orderVendorProvenanceGaps": gaps}}
    receipt = RD.build_receipt(state)
    ovg_lines = [d for d in receipt["degraded"] if "order-vendor-provenance-gap" in d]
    assert len(ovg_lines) == 1
    assert "architecture-reviewer" in ovg_lines[0]


def test_disclosure_block_survives_the_durable_skeleton(tmp_path):
    """The channels ride the record schema `review_memory` already models — a persisted round record
    keeps its `disclosures` block through skeletonization (which strips evidence bodies), and a
    record without one gains no key."""
    rm = _load("review_memory")
    rec = rm.record_from_dimension_results(
        1, "baseline", {"test-role": {"status": "run", "findings": []}}, None, [], None,
        disclosures={"vacuousSeats": ["architecture-reviewer"]})
    assert rec["disclosures"] == {"vacuousSeats": ["architecture-reviewer"]}
    assert rm.summarize_record(rec)["disclosures"] == {"vacuousSeats": ["architecture-reviewer"]}
    assert "disclosures" not in rm.summarize_record(
        rm.record_from_dimension_results(1, "baseline", {}, None, [], None))


# --- the census: the channel set is closed BY CONSTRUCTION --------------------

def _symbol_label(obj):
    return getattr(obj, "__qualname__", repr(obj))


def _module_source(mod):
    path = getattr(mod, "__file__", None)
    if not path:
        pytest.fail("cannot resolve source file for module %r" % getattr(mod, "__name__", mod))
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        pytest.fail("cannot read source for module %s (%s): %s" % (
            getattr(mod, "__name__", mod), path, exc))


def _disclosure_channel_consumer_source():
    channel_home = _module_source(RD_DISCLOSURES)
    consumer_modules = {RD.build_receipt.__module__, RD_DISCLOSURES.build_degraded_prose.__module__}
    parts = [channel_home]
    for mod_name in sorted(consumer_modules):
        mod = sys.modules.get(mod_name)
        if mod is None:
            pytest.fail("cannot import module %r for disclosure channel consumer scan" % mod_name)
        if mod is RD_DISCLOSURES:
            continue
        parts.append(_module_source(mod))
    return "\n".join(parts)


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

    Every per-round key `_fold_panel` or `_fold_verifiers` records is enumerated FROM THE SOURCE
    with `ast` and must have exactly one module-level home: `CARRIED_DISCLOSURE_CHANNELS` (the
    channels `build_receipt` emits and a `recordsPath` resume restores) or `UNRESTORED_PANEL_ROUND_KEYS`
    (the deliberate not-restored list, each with its reason in the source). A NEW `_record_round`
    channel that ships without a resume path fails HERE — instead of silently under-disclosing every
    resumed run's terminal receipt, which is the defect this test exists to prevent recurring.
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

    fold_verifiers = _fn_node(tree, ast_mod, "_fold_verifiers")
    verifier_recorded = set()
    verifier_appended = set()
    for node in ast_mod.walk(fold_verifiers):
        if not (isinstance(node, ast_mod.Call) and isinstance(node.func, ast_mod.Name)):
            continue
        if node.func.id == "_record_round":
            assert len(node.args) >= 2, "_record_round must be called with (state, key, value)"
            key = node.args[1]
            assert isinstance(key, ast_mod.Constant) and isinstance(key.value, str), (
                "a _record_round key must be a string LITERAL so the census can enumerate it")
            verifier_recorded.add(key.value)
        elif node.func.id == "_record_round_append":
            assert len(node.args) >= 2, "_record_round_append must be called with (state, key, value)"
            key = node.args[1]
            assert isinstance(key, ast_mod.Constant) and isinstance(key.value, str), (
                "a _record_round_append key must be a string LITERAL so the census can enumerate it")
            verifier_appended.add(key.value)

    fold_provenance = set(RD.FOLD_PROVENANCE_DISCLOSURE_CHANNELS)
    judgment_fold = set(RD.JUDGMENT_FOLD_DISCLOSURE_CHANNELS)
    submit_disclosure = set(RD.SUBMIT_DISCLOSURE_CHANNELS)
    terminal_gate = set(RD.TERMINAL_DISCLOSURE_CHANNELS)
    order_emission = set(RD.ORDER_EMISSION_DISCLOSURE_CHANNELS)
    verifier_fold = set(RD.VERIFIER_FOLD_DISCLOSURE_CHANNELS)
    verify_fold = set(RD.VERIFY_FOLD_DISCLOSURE_CHANNELS)
    restorable = set(RD.CARRIED_DISCLOSURE_CHANNELS)
    unrestored = set(RD.UNRESTORED_PANEL_ROUND_KEYS)
    assert fold_provenance <= restorable, (
        "fold provenance channels must be restorable: %s"
        % sorted(fold_provenance - restorable))
    assert terminal_gate <= restorable, (
        "terminal-gate disclosure channels must be restorable: %s"
        % sorted(terminal_gate - restorable))
    assert submit_disclosure <= restorable, (
        "submit disclosure channels must be restorable: %s"
        % sorted(submit_disclosure - restorable))
    assert order_emission <= restorable, (
        "order-emission disclosure channels must be restorable: %s"
        % sorted(order_emission - restorable))
    assert verifier_fold <= restorable, (
        "verifier-fold disclosure channels must be restorable: %s"
        % sorted(verifier_fold - restorable))
    assert judgment_fold <= restorable, (
        "judgment-fold disclosure channels must be restorable: %s"
        % sorted(judgment_fold - restorable))
    assert verify_fold <= restorable, (
        "verify-fold disclosure channels must be restorable: %s"
        % sorted(verify_fold - restorable))
    assert not (restorable & unrestored), \
        "a channel cannot be both restorable and not-restored: %s" % sorted(restorable & unrestored)
    accounted = restorable | unrestored
    all_recorded = (recorded | fold_provenance | judgment_fold | submit_disclosure | order_emission
                    | terminal_gate | verifier_recorded | verifier_appended | verifier_fold | verify_fold)
    assert all_recorded == accounted, (
        "every per-round disclosure channel needs exactly one home — unaccounted (no resume path): %s; "
        "stale (named but no longer recorded): %s"
        % (sorted(all_recorded - accounted),
           sorted(accounted - all_recorded)))


def test_disclosure_channels_have_one_home_read_by_receipt_and_resume():
    """The census is the whole story only if `build_receipt` and the resume both READ the constant
    rather than a hand-copied literal list — and only if every named channel is really consumed by
    the receipt (a fossil channel would pass the census while disclosing nothing)."""
    tree, ast_mod = _round_driver_ast()
    for fn in ("build_receipt",):
        names = {n.id for n in ast_mod.walk(_fn_node(tree, ast_mod, fn))
                 if isinstance(n, ast_mod.Name)}
        assert "CARRIED_DISCLOSURE_CHANNELS" in names, \
            "%s must read the channel set from its one home" % fn
    src = _disclosure_channel_consumer_source()
    for chan in RD.CARRIED_DISCLOSURE_CHANNELS:
        assert source_obj_accesses_key(src, "rec|rrec|declared", chan), \
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
    RD._fold_apply_fixes(state, state["config"], artifact)
    assert state["_changedSubjects"] == ["Code", "Security", "Test"]


def test_run_loop_uses_injected_changed_subjects_seam(tmp_path):
    """run_loop routes the derivation through the injected `changed_subjects` seam (the eval-harness
    pattern). The seam is consulted although the fixer's self-report is narrow, and a cross-cutting
    set no longer re-arms a confirmation panel — none runs after round 1."""
    calls = []

    def changed_subjects(reviewed, head, accumulated):
        calls.append((reviewed, head, accumulated))
        return ["Security", "Code", "Test"]

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE,
                                  "file": "f.py", "line": 1}]}
        return []

    seams = _seams(reviewer=reviewer)
    seams["changed_subjects"] = changed_subjects
    receipt = RD.run_loop(seams, _cfg_cert(maxRounds=20, seatMap=_nonpanel_cell_proof(["claude", "codex"])))
    assert calls  # the seam was invoked (the self-report was never consulted)
    assert not any(r.get("kind") == "confirmation" for r in receipt["rounds"])
    assert receipt["verdict"] == "converged"


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
        art = _responder(round1_findings=None, vendors=["codex", "cursor"])(n["phase"], n["payload"], n["round"])
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
    # the build session's own family (openai) is the fixer, so the audits are seated on another vendor
    seat_map = dict(_nonpanel_cell_proof(["codex", "cursor"]), hostFamily="openai")
    seat_map_path = os.path.join(d, "seat-map.json")
    with open(seat_map_path, "w", encoding="utf-8") as fh:
        json.dump(seat_map, fh)
    ga = _guard_argv(d) + ["--vendors", "codex,cursor", "--seat-map", seat_map_path]
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"], out
    pin = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["baseRef"]
    for _ in range(80):
        n = RD.cmd_next(d)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            break
        art = _responder(round1_findings=None, vendors=["codex", "cursor"])(n["phase"], n["payload"], n["round"])
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
        art = _responder(round1_findings=None, vendors=["codex", "cursor"])(n["phase"], n["payload"], n["round"])
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
        art = _responder(round1_findings=None, vendors=["codex", "cursor"])(n["phase"], n["payload"], n["round"])
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
    seat_map = _assertable_seat_map(["codex", "cursor"])
    seat_map["degradations"] = [{
        "constraint": "same-family",
        "seat": seat,
        "reason": "seat %s seated the maker family claude — no alternative family is live" % seat,
    }]
    return seat_map


def test_same_family_seat_map_degrades_cert_shape():
    cfg = _cfg_cert(leg="panel", vendors=["codex", "cursor"])
    seat_map_clean = _assertable_seat_map(cfg["vendors"])
    io_clean = {"seatMap": seat_map_clean}
    result_clean = RD.run_loop(_seams(io=io_clean), cfg)
    assert result_clean["verdict"] == "converged"
    assert result_clean["certificationShape"] == "full-panel-confirmed"
    seat_map_deg = _panel_seat_map_with_same_family()
    io_deg = {"seatMap": seat_map_deg}
    result_deg = RD.run_loop(_seams(io=io_deg), cfg)
    assert result_deg["verdict"] == "converged"
    assert result_deg["certificationShape"].endswith("-degraded")


def test_same_family_disclosed_in_receipt_degraded_list():
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    _set_seat_map(state, _panel_seat_map_with_same_family("security-reviewer"))
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
    _set_seat_map(state, _panel_seat_map_with_same_family())
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-degraded")
    assert state["certification"]["independence"] == "degraded"
    receipt = RD.build_receipt(state)
    indep_lines = [d for d in receipt["degraded"] if d.startswith("independence:")]
    sf_lines = [d for d in receipt["degraded"] if d.startswith("panel independence:")]
    assert len(indep_lines) == 1
    assert len(sf_lines) == 1


def _seat_map_receipt_with_unexcused_maker_family():
    """Hand-built receipt-shaped map: all-claude panel + unexcused breach."""
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["violations"] = [{"constraint": "maker-family", "seat": "code-reviewer"}]
    seat_map["degradations"] = []
    return seat_map


def test_seat_map_unexcused_violation_constraint_violated_cert_shape():
    cfg = _cfg_cert(leg="panel", vendors=["codex", "cursor"])
    seat_map = _seat_map_receipt_with_unexcused_maker_family()
    SM = _load("seat_map")
    assert SM.unexcused_violations(seat_map)
    result = RD.run_loop(_seams(io={"seatMap": seat_map}), cfg)
    assert result["verdict"] == "converged"
    assert "-constraint-violated" in result["certificationShape"]


def test_seat_map_excused_only_violation_unchanged_cert_shape():
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    state_clean = RD.new_state(cfg)
    state_clean["seatMap"] = _assertable_seat_map(cfg["vendors"], cfg.get("fixerVendor"))
    RD._terminal_converged(state_clean, cfg, full_panel=True)
    shape_clean = state_clean["certification"]["shape"]
    SM = _load("seat_map")
    m = SM.build(SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", 0)
    seat_map_excused = SM.to_receipt(m, "anthropic")
    state_excused = RD.new_state(cfg)
    state_excused["seatMap"] = seat_map_excused
    RD._terminal_converged(state_excused, cfg, full_panel=True)
    assert state_excused["certification"]["shape"] == shape_clean
    assert "-constraint-violated" not in state_excused["certification"]["shape"]


def test_seat_map_pin_excusal_degraded_shape_and_disclosure():
    SM = _load("seat_map")
    seats = _assertable_seat_map(["codex", "cursor"])
    seats["violations"] = [{"constraint": "strong-tier", "seat": "security-reviewer"}]
    seats["livenessPinScoped"] = False
    sr = dict(seats["seats"]["security-reviewer"])
    sr["source"] = "pinned"
    seats["seats"] = dict(seats["seats"])
    seats["seats"]["security-reviewer"] = sr
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    state = RD.new_state(cfg)
    _set_seat_map(state, seats)
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-degraded")
    assert "seat-pin" in state["certification"]["shapeDrivers"]
    receipt = RD.build_receipt(state)
    pin_lines = [d for d in receipt["degraded"] if d.startswith("seat-map pin excusal:")]
    assert len(pin_lines) == 1
    assert "security-reviewer" in pin_lines[0]
    assert SM.classify_violations(seats, model_registry.family_for("implementer", "claude"))["excusedByPin"]


def test_seat_map_unproven_liveness_shape_driver():
    SM = _load("seat_map")
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["violations"] = [{"constraint": "critical-diversity"}]
    seat_map["liveVendors"] = ["claude", "codex"]
    seat_map["authorFamily"] = "anthropic"
    assert SM.unexcused_violations(seat_map)[0].get("evidence") == "unproven-liveness"
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    state = RD.new_state(cfg)
    _set_seat_map(state, seat_map)
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert "unproven-liveness" in state["certification"]["shapeDrivers"]
    assert state["certification"]["shape"].endswith("-constraint-violated")


def test_certification_shape_drivers_lists_every_fired_channel():
    seat_map = _seat_map_receipt_with_unexcused_maker_family()
    seat_map = dict(seat_map)
    # same-family and unexcused maker-family on one seat are mutually exclusive in projections.
    seat_map["degradations"] = list(seat_map.get("degradations") or []) + [{
        "constraint": "same-family",
        "seat": "security-reviewer",
        "reason": "test",
    }]
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"], fixerVendor="codex")
    cfg["baseDegraded"] = True
    state = RD.new_state(cfg)
    state["independenceDegraded"] = True
    _set_seat_map(state, seat_map)
    RD._terminal_converged(state, state["config"], full_panel=True)
    drivers = state["certification"]["shapeDrivers"]
    assert drivers == ["base", "independence", "same-family", "seat-map-violation"]
    assert state["certification"]["shape"].endswith("-constraint-violated")
    assert state["certification"]["shape"].count("-degraded") == 0


def test_same_family_seats_suppresses_when_maker_family_on_same_seat():
    """Pin: same-family projection drops seats with unexcused maker-family on that seat (#1190)."""
    SMR = _load("seat_map_receipts")
    base = _seat_map_receipt_with_unexcused_maker_family()
    collided = dict(base)
    collided["degradations"] = [{
        "constraint": "same-family",
        "seat": "code-reviewer",
        "reason": "test",
    }]
    state_collided = {"seatMapReceipts": _seat_map_receipts(collided)}
    assert "code-reviewer" not in SMR.same_family_seats(state_collided)
    separated = dict(base)
    separated["degradations"] = [{
        "constraint": "same-family",
        "seat": "security-reviewer",
        "reason": "test",
    }]
    state_separated = {"seatMapReceipts": _seat_map_receipts(separated)}
    assert "security-reviewer" in SMR.same_family_seats(state_separated)


def _write_meta_json(session_dir, payload):
    os.makedirs(session_dir, exist_ok=True)
    with open(os.path.join(session_dir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def test_receipt_base_mode_routes_through_session_mode_meta_wins(tmp_path):
    """I2 (#1107 WO-rc1): the receipt's base.mode is the DRIVER-RESOLVED mode, never a raw
    cfg echo. Under meta-wins precedence, session metadata overrides a disagreeing driver
    config value in the receipt too — the same precedence `session_mode.resolve` already
    applies everywhere else."""
    session_dir = str(tmp_path / "sess")
    _write_meta_json(session_dir, {"mode": "branch"})
    state = RD.new_state(_cfg(mode="pr"))
    receipt = RD.build_receipt(state, session_dir)
    assert receipt["base"]["mode"] == "branch"


def test_receipt_base_mode_edge_no_session_dir_grounds_from_config(tmp_path):
    """Fail-closed edge 1: session_dir is None (the run_loop receipt paths) — no metadata
    exists; resolve({}, cfg) is grounded iff cfg carried a valid mode."""
    state = RD.new_state(_cfg(mode="pr"))
    receipt = RD.build_receipt(state)
    assert receipt["base"]["mode"] == "pr"


def test_receipt_base_mode_edge_missing_meta_file_does_not_raise(tmp_path):
    """Fail-closed edge 2: session_dir set but meta.json missing — _session_meta already
    returns {}; must not raise, and (with no cfg mode either) base.mode is simply absent."""
    session_dir = str(tmp_path / "sess-no-meta")
    os.makedirs(session_dir)
    state = RD.new_state(_cfg())
    receipt = RD.build_receipt(state, session_dir)
    assert "base" not in receipt or "mode" not in receipt.get("base", {})


def test_receipt_base_mode_edge_invalid_meta_is_absent_not_config_fallthrough(tmp_path):
    """Fail-closed edge 3: meta carries a present-but-invalid mode — resolve is unresolved,
    so base.mode is ABSENT — it must not fall through to cfg's disagreeing valid value
    (I1's whole point, now reaching the receipt)."""
    session_dir = str(tmp_path / "sess-invalid")
    _write_meta_json(session_dir, {"mode": "bogus"})
    state = RD.new_state(_cfg(mode="pr"))
    receipt = RD.build_receipt(state, session_dir)
    assert "mode" not in receipt.get("base", {})


def test_receipt_base_mode_edge_neither_source_has_mode_is_absent(tmp_path):
    """Fail-closed edge 4: neither meta nor cfg carries a mode — base.mode absent."""
    session_dir = str(tmp_path / "sess-empty")
    os.makedirs(session_dir)
    state = RD.new_state(_cfg())
    receipt = RD.build_receipt(state, session_dir)
    assert "base" not in receipt or "mode" not in receipt.get("base", {})


def test_run_loop_seat_map_bool_round_not_coerced_to_one():
    """seat_map_receipts preserves receipt round labels — bools are not coerced to int 1."""
    SMR = _load("seat_map_receipts")
    state = {
        "seatMapReceipts": [{"round": True, "map": {"seats": {"code-reviewer": {}}}}],
    }
    assert SMR.receipts(state)[0]["round"] is True


def test_run_loop_seat_map_normalizes_digit_string_round():
    """seat_map_receipts preserves digit-string round labels from seatMapReceipts."""
    SMR = _load("seat_map_receipts")
    state = {
        "seatMapReceipts": [{"round": "2", "map": {"seats": {"code-reviewer": {}}}}],
    }
    assert SMR.receipts(state)[0]["round"] == "2"


def test_seat_map_violations_round_field_and_degraded_disclosure():
    seat_map = _seat_map_receipt_with_unexcused_maker_family()
    cfg = _cfg_cert(leg="panel", vendors=["codex", "cursor"])
    result = RD.run_loop(_seams(io={"seatMap": seat_map}), cfg)
    assert result["verdict"] == "converged"
    assert "-constraint-violated" in result["certificationShape"]


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
    _set_seat_map(state, clean)
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-constraint-violated")


def test_library_receipt_omits_base_not_checked(tmp_path):
    """Without a checked base guard the loop still runs; run_loop never mints a legacy receipt."""
    # base-guard binding assertion no longer reachable through run_loop.
    result = RD.run_loop(_seams(), _cfg())
    assert isinstance(result, dict)
    assert result["verdict"] == "converged"


def test_library_receipt_mode_without_cli_guard_stays_not_checked(tmp_path):
    """Guard-shaped config keys must not infer baseGuard=checked without the CLI guard."""
    result = RD.run_loop(_seams(), _cfg(mode="pr"))
    assert isinstance(result, dict)
    assert result["verdict"] == "converged"


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


def test_auditor_vendor_family_keyed_single_vendor_same_family_unseatable():
    """Single live vendor with the fixer's own family → no auditor, never the fixer standing in."""
    assert RD._auditor_vendor({"vendors": ["claude"]}, "claude") == (None, "unseatable")


# The #510-era `test_auditor_vendor_family_keyed_single_vendor_cross_family_independent` lived here.
# It asserted that a cursor-only env is cross-family (composer='cursor' vs grok='xai') and therefore
# independent. #651 (owner-ratified 2026-07-26) merged both cursor first-party models into the `xai`
# family, so that env is now same-family and DEGRADED. Its replacement —
# `test_cursor_fix_never_gets_an_independent_cursor_auditor`, at the end of this file — asserts the
# new expectation AND the cross-family branches the old test did not cover. One thing did go with
# it: that test was the only one reaching `_auditor_vendor`'s SECOND (same-vendor) loop on its
# `independent` return, and post-#651 no vendor can satisfy that branch — every vendor's
# `implementer` and `verifier` roles now resolve to the same family — so it is unreachable, not
# merely untested. #652 rider 4a deleted that loop; the invariant is pinned by
# test_auditor_and_implementer_families_match_per_vendor in test_model_registry.py.


# axis: _auditor_vendor independence follows the auditor role family, not verifier
def test_auditor_vendor_reads_auditor_role(monkeypatch):
    real_family_for = RD.model_registry.family_for

    def fake_family_for(role, vendor):
        if role == "auditor" and vendor == "codex":
            return "openai"
        if role == "verifier" and vendor == "codex":
            return "xai"
        return real_family_for(role, vendor)

    monkeypatch.setattr(RD.model_registry, "family_for", fake_family_for)
    auditor, independence = RD._auditor_vendor({"vendors": ["cursor", "codex"]}, "cursor")
    assert independence == "independent"
    assert auditor == "codex"


def test_auditor_vendor_unknown_fixer_unseatable():
    """#608: a genuinely-unknown fixer vendor has no family to be independent of, so no vendor is
    seated as its auditor."""
    assert RD._auditor_vendor({"vendors": ["claude", "codex"]}, None) == (None, "unseatable")


def test_auditor_vendor_empty_string_fixer_unseatable():
    """#608: empty-string fixer is unknown — same no-auditor path as None."""
    assert RD._auditor_vendor({"vendors": ["claude", "codex"]}, "") == (None, "unseatable")


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
                 "auditorVendor": t.get("auditorVendor"), "checks": audit_checks()}
                for t in (targets or [])]

    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=auditor), _cfg_cert(vendors=["codex", "cursor"], fixerVendor="claude",
                                    seatMap=_nonpanel_cell_proof(["codex", "cursor"])))
    assert receipt["verdict"] == "converged"
    t = captured["targets"][0]
    assert t["fixerVendor"] == "claude"
    assert t["auditorVendor"] == "codex" and t["auditorVendor"] != t["fixerVendor"]
    assert t["independence"] == "independent"


# =============================================================================
# an owner-choice blocker is held out of the fix batch and handed back open (C1-L4)
# =============================================================================

_TRADEOFF = {"title": "widen the API", "severity": "Important", "consequence": _CONSEQUENCE,
             "file": "f.py", "line": 1, "tradeoff": True}
# The held-finding key is the per-LOCATION id (line-less finding_identity + line) so two
# same-title tradeoff blockers at different lines never collide (#507 R2 v5).
_TRADEOFF_ID = "f.py::widen the api@L1"
_RESUME_IDENTITY_TRADEOFF = {"title": "resume identity fields", "severity": "Important", "consequence": _CONSEQUENCE,
                             "file": "pkg/resume_identity.py", "line": 42, "tradeoff": True}
_RESUME_IDENTITY_TRADEOFF_ID = "pkg/resume_identity.py::resume identity fields@L42"


def test_tradeoff_blocker_is_held_out_of_the_fix_batch_not_put_to_the_owner():
    """A tradeoff/product-choice blocker is held out of the fixer's batch and journaled — no phase
    puts it to the owner, and the step does not move."""
    state = RD.new_state(_cfg())
    step_before = state["step"]
    assert RD._hold_owner_choice(state, [dict(_TRADEOFF)]) == []
    assert state["step"] == step_before
    assert state["ownerChoiceHeld"] == [_TRADEOFF_ID]
    kinds = [d["kind"] for d in state["decisions"]]
    assert kinds == ["owner-choice-held"]


def test_mechanical_blocker_is_not_held_with_the_tradeoff():
    """A mechanical (non-tradeoff) blocker in the SAME batch stays in the batch — never abandoned."""
    mech = {"title": "null deref", "severity": "Critical", "consequence": _CONSEQUENCE, "file": "f.py", "line": 2}
    state = RD.new_state(_cfg())
    rest = RD._hold_owner_choice(state, [dict(mech), dict(_TRADEOFF)])
    assert [r["title"] for r in rest] == ["null deref"]
    assert state["ownerChoiceHeld"] == [_TRADEOFF_ID]


def test_a_purely_mechanical_batch_holds_nothing_and_journals_nothing():
    state = RD.new_state(_cfg())
    mech = {"title": "null deref", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 2}
    assert RD._hold_owner_choice(state, [dict(mech)]) == [mech]
    assert "ownerChoiceHeld" not in state and state["decisions"] == []


def test_held_keys_are_deduped_append_only_and_journaled_once_per_call():
    state = RD.new_state(_cfg())
    other = dict(_TRADEOFF, title="drop the flag", line=2)
    RD._hold_owner_choice(state, [dict(_TRADEOFF)])
    RD._hold_owner_choice(state, [dict(_TRADEOFF), dict(other)])
    assert state["ownerChoiceHeld"] == [_TRADEOFF_ID, "f.py::drop the flag@L2"]
    assert [d["kind"] for d in state["decisions"]].count("owner-choice-held") == 2
    RD._hold_owner_choice(state, [])  # a call that holds nothing leaves the list and journal alone
    assert len(state["ownerChoiceHeld"]) == 2 and len(state["decisions"]) == 2


def test_recorded_skipped_blocker_still_rides_the_certification_and_disclosure():
    """A skipped blocker an earlier version recorded is still read at the converge: the run converges
    CLEAN EXCEPT FOR SKIPPED, never a plain success (the reason leads with clean-except-skipped)."""
    state = RD.new_state(_cfg())
    state["seatMapReceipts"] = _seat_map_receipts(
        _assertable_seat_map(state["config"]["vendors"], state["config"].get("fixerVendor")))
    state["_skippedBlockers"] = [{"id": _TRADEOFF_ID, "file": "f.py", "line": 1,
                                  "title": "widen the API", "severity": "Important",
                                  "reason": "shipping v1 narrow on purpose"}]
    state["rounds"].setdefault("1", {})["skippedBlockers"] = list(state["_skippedBlockers"])
    RD._terminal_converged(state, state["config"], full_panel=False)
    assert state["terminal"] == "converged"
    cert = state.get("certification") or {}
    assert cert.get("shape") == "audited-chain"
    assert (cert.get("reason") or "").startswith("clean-except-skipped: 1 blocker(s) skipped")
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
    _refusal, receipt = _run_loop_with_loop_receipt(_seams(), _cfg_cert())
    assert _refusal["verdict"] == "converged"
    assert receipt["skippedBlockers"] == []
    ok, _ = RD.validate_receipt(receipt)
    assert ok
    stripped = dict(receipt)
    del stripped["skippedBlockers"]
    ok2, why = RD.validate_receipt(stripped)
    assert not ok2 and "skippedBlockers" in why
    bad = dict(receipt)
    bad["skippedBlockers"] = None
    ok3, why3 = RD.validate_receipt(bad)
    assert not ok3 and "skippedBlockers" in why3


def _record_gate_decision(state, finding, disposition, guidance=None):
    """Write the `judgmentDispositions` row an earlier version's judgment fold recorded for `finding`
    (the readers of that recorded state are what these tests pin)."""
    key = RD._finding_key_of(finding)
    entry = {"id": key, RD.session_contract.FINDING_KEY_FIELD: key, "title": finding["title"],
             "file": finding["file"], "line": finding["line"], "disposition": disposition}
    if guidance is not None:
        entry[RD.GATE_GUIDANCE_RECORD_KEY] = guidance
    RD._stamp_ruling_seq(state, entry)
    RD._record_round_append(state, "judgmentDispositions", entry)
    return entry


def test_receipt_projects_judgment_dispositions_when_recorded():
    """G4 axis: build_receipt carries judgmentDispositions when the round recorded one."""
    state = RD.new_state(_cfg())
    _record_gate_decision(state, _TRADEOFF, "fix-with-guidance", "narrow only")
    state["terminal"] = "converged"
    receipt = RD.build_receipt(state)
    rd = receipt["rounds"][0]
    assert rd["judgmentDispositions"][0][RD.GATE_GUIDANCE_RECORD_KEY] == "narrow only"


def test_judgment_dispositions_guidance_reaches_the_export_the_receipt_and_the_fixer_order(tmp_path):
    """E6: fold guidance reaches the export, the receipt and the apply-fixes guidance file in one session."""
    records = tmp_path / "round-records.json"
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    _record_gate_decision(state, _TRADEOFF, "fix-with-guidance", "narrow only")
    state["_records"] = [_seed_record(1)]
    RD._persist_round_records(state, state["config"])
    on_disk = json.loads(records.read_text())
    rec = next(r for r in on_disk if r.get("round") == 1)
    assert rec["disclosures"]["judgmentDispositions"][0][RD.GATE_GUIDANCE_RECORD_KEY] == "narrow only"
    assert state["rounds"]["1"]["judgmentDispositions"][0][RD.GATE_GUIDANCE_RECORD_KEY] == "narrow only"
    state["terminal"] = "converged"
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["judgmentDispositions"][0][RD.GATE_GUIDANCE_RECORD_KEY] == "narrow only"
    state["reviewedDiff"] = "diff --git a/f b/f\n"
    state["_fixBatch"] = [{"title": "widen the API", "file": "f.py", "line": 1,
                           "judgmentDisposition": "fix-with-guidance"}]
    session_dir = str(tmp_path / "resume-render")
    os.makedirs(session_dir)
    fields = RD._apply_fixes_payload_fields(session_dir, state, 1, 0)
    assert fields["guidancePath"] is not None
    with open(fields["guidancePath"], encoding="utf-8") as fh:
        guidance = fh.read()
    assert "narrow only" in guidance
    assert guidance.strip() != RD._GATE_GUIDANCE_NO_GUIDANCE


def test_judgment_dispositions_identity_fields_reach_the_export_the_receipt_and_the_fixer_order(tmp_path):
    """E6b: fold identity fields (id, file, line) reach the export, the receipt and the apply-fixes guidance file in one session."""
    records = tmp_path / "round-records.json"
    tradeoff = dict(_RESUME_IDENTITY_TRADEOFF)
    guidance_text = "keep the resume identity intact"
    state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    _record_gate_decision(state, tradeoff, "fix-with-guidance", guidance_text)
    state["_records"] = [_seed_record(1)]
    RD._persist_round_records(state, state["config"])
    on_disk = json.loads(records.read_text())
    rec = next(r for r in on_disk if r.get("round") == 1)
    disk_entry = rec["disclosures"]["judgmentDispositions"][0]
    assert disk_entry["file"] == tradeoff["file"]
    assert disk_entry["line"] == tradeoff["line"]
    assert disk_entry["id"] == _RESUME_IDENTITY_TRADEOFF_ID
    state_entry = state["rounds"]["1"]["judgmentDispositions"][0]
    assert state_entry["file"] == tradeoff["file"]
    assert state_entry["line"] == tradeoff["line"]
    assert state_entry["id"] == _RESUME_IDENTITY_TRADEOFF_ID
    state["terminal"] = "converged"
    receipt = RD.build_receipt(state)
    receipt_entry = receipt["rounds"][0]["judgmentDispositions"][0]
    assert receipt_entry["file"] == tradeoff["file"]
    assert receipt_entry["line"] == tradeoff["line"]
    assert receipt_entry["id"] == _RESUME_IDENTITY_TRADEOFF_ID
    state["reviewedDiff"] = (
        "diff --git a/pkg/resume_identity.py b/pkg/resume_identity.py\n")
    state["_fixBatch"] = [{"title": tradeoff["title"], "file": tradeoff["file"],
                           "line": tradeoff["line"],
                           "judgmentDisposition": "fix-with-guidance"}]
    session_dir = str(tmp_path / "resume-identity-render")
    os.makedirs(session_dir)
    fields = RD._apply_fixes_payload_fields(session_dir, state, 1, 0)
    assert fields["guidancePath"] is not None
    with open(fields["guidancePath"], encoding="utf-8") as fh:
        block = fh.read()
    assert "### %s:%s — %s" % (tradeoff["file"], tradeoff["line"], tradeoff["title"]) in block
    assert _gate_guidance_record_id_line(block) == _RESUME_IDENTITY_TRADEOFF_ID


def _gate_guidance_record_id_line(block):
    import re
    m = re.search(
        r"^Record id \(auditing only, not for matching\): (.+)$", block, re.MULTILINE)
    return m.group(1) if m else None


def test_tradeoff_finding_alone_is_handed_back_open_end_to_end():
    """End-to-end: one tradeoff blocking finding is held out of the fix batch, nothing is put to the
    owner mid-review, and the run ends handed back with the finding open — never converged."""
    refusal, loop_receipt = _run_loop_with_loop_receipt(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [dict(_TRADEOFF)]} if rnd == 1 and dim == "code-reviewer" else [])),
        _cfg_cert())
    assert refusal["verdict"] == "handed-back"
    assert refusal["certificationShape"] is None
    kinds = [d["kind"] for d in loop_receipt["decisions"]]
    assert kinds[-2:] == ["owner-choice-held", "owner-choice-open"]
    ok, _ = RD.validate_receipt(loop_receipt)
    assert ok


# =============================================================================
# #563 DoD1 — loud fall-open dispatch provenance (machinery)
# =============================================================================

def _seat_map_vendors(vendors):
    return {"seats": {d: {"vendor": v} for d, v in vendors.items()}}


def _verified_clean_seat_map(vendors):
    """Build a seat map through seat_map's API; assert it verifies clean for vendors."""
    SM = _load("seat_map")
    live = sorted({v for v in (vendors or []) if isinstance(v, str) and v})
    if not live:
        live = ["claude"]
    for author in ("xai", "anthropic", "openai"):
        m = SM.build(SM.PANEL_ROSTER, live, author, 0)
        violations = SM.verify(m, author)
        if violations == []:
            return SM.to_receipt(m, author)
    raise AssertionError("no verify-clean seat map for vendors %r" % vendors)


def _nonpanel_cell_proof(vendors):
    """The seat-map keys proving each vendor's dispatched non-panel cells (`verifier`,
    `reviewer-deep`) live: the non-panel selector seats a non-claude reviewer only on proven cells."""
    cells = []
    for role in ("verifier", "reviewer-deep"):
        for vendor in vendors:
            cell = model_registry.matrix_config(role, vendor)
            if cell is not None:
                cells.append([vendor, cell[0], cell[1]])
    return {"nonPanelLiveCells": cells, "nonPanelLiveCellsSource": "synthesized"}


def _assertable_seat_map(vendors, fixer_vendor="claude"):
    """Receipt-shaped seat map — ``unexcused_violations`` empty at construction (#1190)."""
    SM = _load("seat_map")
    live = sorted({v for v in (vendors or []) if isinstance(v, str) and v})
    if not live:
        live = ["claude"]
    driver_author_family = model_registry.family_for("implementer", fixer_vendor)
    for author in ("xai", "anthropic", "openai"):
        m = SM.build(SM.PANEL_ROSTER, live, author, 0)
        receipt = SM.to_receipt(m, author)
        if SM.unexcused_violations(receipt, driver_author_family) == []:
            receipt.update(_nonpanel_cell_proof(live))
            return receipt
    raise AssertionError(
        "no assertable seat map for vendors %r driver_author_family=%r"
        % (vendors, driver_author_family))


def test_assertable_seat_map_allows_excused_derived_violations():
    """INV-13 pin: baseline bar is unexcused violations, not raw derived ones (#1190)."""
    SM = _load("seat_map")
    m = _assertable_seat_map(["claude", "codex"], "codex")
    assert SM.unexcused_violations(m, "openai") == []
    assert SM.derived_violations(m, "openai") != []


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
    assert state["rounds"]["1"]["seatMapUnavailable"] == ["claude", "codex"]
    receipt = RD.build_receipt(state)
    smu_lines = [d for d in receipt["degraded"]
                 if d.startswith("reviewer-fell-open-seatmap-unavailable")]
    assert len(smu_lines) == 1
    assert "claude" in smu_lines[0] and "codex" in smu_lines[0]


# =============================================================================
# #681 — seatMapUnavailable backstop widened + certification wiring
# =============================================================================

def test_seat_map_unavailable_claude_only_fold_and_certification():
    """Collapsed-family claude-only run with no seat map: backstop, -degraded, driver, prose (#681)."""
    state = RD.new_state(_cfg(leg="panel", vendors=["claude"]))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    RD._fold_panel(state, state["config"], {"seats": seats})
    # bite-axis: widened record predicate — claude-only pool, never silent (#681).
    assert state["rounds"]["1"]["seatMapUnavailable"] == ["claude"]
    RD._terminal_converged(state, state["config"], full_panel=True)
    # bite-axis: -degraded shape projection when map absent (#681).
    assert state["certification"]["shape"] == "full-panel-confirmed-degraded"
    # bite-axis: shapeDrivers projection (#681).
    assert "seat-map-unavailable" in state["certification"]["shapeDrivers"]
    receipt = RD.build_receipt(state)
    smu_lines = [d for d in receipt["degraded"]
                 if d.startswith("reviewer-fell-open-seatmap-unavailable")]
    assert len(smu_lines) == 1
    # bite-axis: honest prose — never claims cross-vendor when pool is claude-only (#681).
    assert smu_lines[0] == (
        "reviewer-fell-open-seatmap-unavailable (round 1): live panel vendor(s) claude "
        "but no seat map submitted — fall-open provenance unverified for the panel")
    assert "live cross-vendor" not in smu_lines[0]


def test_seat_map_unavailable_terminal_arm_without_round_record():
    """Terminal merged map with no seats degrades even when no round recorded unavailable (#681)."""
    state = RD.new_state(_cfg(leg="panel", vendors=["claude", "codex"]))
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-degraded")
    assert "seat-map-unavailable" in state["certification"]["shapeDrivers"]


def test_seat_map_unavailable_round1_map_round2_absent():
    """Round 1 submitted a map; round 2 did not — receipt list preserves seats (#681)."""
    state = RD.new_state(_cfg(leg="panel", vendors=["claude", "codex"]))
    seat_map = _verified_clean_seat_map(["claude", "codex"])
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert "seatMapUnavailable" not in state["rounds"]["1"]
    state["round"] = 2
    RD._fold_panel(state, state["config"], {"seats": seats})
    assert "seatMapUnavailable" not in state["rounds"]["2"]
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert "seat-map-unavailable" not in state["certification"]["shapeDrivers"]


def test_seat_map_round2_no_map_panel_still_complete():
    """Round 2 with no seat map leaves the panel complete."""
    state = RD.new_state(_cfg(leg="panel", vendors=["claude", "codex"]))
    seat_map = _verified_clean_seat_map(["claude", "codex"])
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert "seatMapUnavailable" not in state["rounds"]["1"]
    state["round"] = 2
    RD._fold_panel(state, state["config"], {"seats": seats})
    assert "seatMapUnavailable" not in state["rounds"]["2"]
    assert state["_incompletePanel"] is False
    assert state["fullPanelRan"] is True


def test_seat_map_unavailable_rounds_arm_with_seats_present():
    """Rounds arm alone: round record carries seatMapUnavailable while receipts have seats."""
    state = RD.new_state(_cfg(leg="panel", vendors=["claude", "codex"]))
    seat_map = _verified_clean_seat_map(["claude", "codex"])
    _set_seat_map(state, seat_map)
    state["rounds"] = {"1": {"seatMapUnavailable": ["claude", "codex"]}}
    assert RD._seat_map_unavailable(state) is True


def test_seat_map_unavailable_existence_arm_no_rounds_no_seats():
    """Existence arm alone: no round records and no receipt carries seats."""
    state = RD.new_state(_cfg(leg="panel", vendors=["claude", "codex"]))
    assert state["rounds"] == {}
    assert state["seatMapReceipts"] == []
    assert RD._seat_map_unavailable(state) is True


def test_seat_map_unavailable_degenerate_vendor_configs():
    """Degenerate vendor configs still record a non-empty sorted de-duplicated value (#681)."""
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    for vendors, expected in (
        ([], ["unknown"]),
        ([""], ["unknown"]),
        ([None], ["unknown"]),
        (["claude", "claude"], ["claude"]),
    ):
        state = RD.new_state(_cfg(leg="panel", vendors=vendors))
        RD._fold_panel(state, state["config"], {"seats": seats})
        assert state["rounds"]["1"]["seatMapUnavailable"] == expected


def test_seat_map_unavailable_constraint_violated_supersedes_shape():
    """-constraint-violated still wins when both violation and unavailable apply (#681)."""
    seat_map = _seat_map_receipt_with_unexcused_maker_family()
    state = RD.new_state(_cfg(leg="panel", vendors=["claude", "codex"]))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    RD._fold_panel(state, state["config"], {"seats": seats})
    _set_seat_map(state, seat_map)
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-constraint-violated")
    assert not state["certification"]["shape"].endswith("-degraded")


# =============================================================================
# #1190 — seatMapUnjudgeable backstop + assert-library wiring
# =============================================================================

def test_seat_map_unjudgeable_rounds_ledger_has_reader():
    """NR-A: rounds ledger arms only when receipts are judgeable — not via receipts alone (#1190)."""
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg["fixerVendor"] = "cursor"
    state = RD.new_state(cfg)
    seat_map = _assertable_seat_map(["claude", "codex"], fixer_vendor="cursor")
    _set_seat_map(state, seat_map)
    assert RD._seat_map_unjudgeable(state) is False
    state["rounds"] = {"1": {"seatMapUnjudgeable": ["no-author-family"]}}
    assert RD._seat_map_unjudgeable(state) is True


def test_seat_map_unjudgeable_rounds_arm_with_judgeable_receipts():
    """NR-B rounds arm: judgeable multi-round receipts stay clean until a round record arms (#1190)."""
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg["fixerVendor"] = "cursor"
    state = RD.new_state(cfg)
    round1 = _assertable_seat_map(["claude", "codex"], fixer_vendor="cursor")
    round2 = _assertable_seat_map(["claude", "codex"], fixer_vendor="cursor")
    state["seatMapReceipts"] = [
        {"round": "1", "map": round1},
        {"round": "2", "map": round2},
    ]
    state["rounds"] = {}
    assert RD._seat_map_unjudgeable(state) is False
    state["rounds"] = {"2": {"seatMapUnjudgeable": ["no-author-family"]}}
    assert RD._seat_map_unjudgeable(state) is True


def test_seat_map_unjudgeable_receipts_arm_without_round_record():
    """NR-B receipts arm: unjudgeable receipt alone arms the backstop (#1190)."""
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg.pop("fixerVendor")
    state = RD.new_state(cfg)
    _set_seat_map(state, _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS}))
    assert RD._seat_map_unjudgeable(state) is True
    assert "seatMapUnjudgeable" not in (state.get("rounds") or {}).get("1", {})


def test_seat_map_unjudgeable_disclosure_not_unavailable_prose():
    """NR-C: present-but-unjudgeable map discloses unjudgeable, not unavailable (#1190)."""
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg.pop("fixerVendor")
    state = RD.new_state(cfg)
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    RD._terminal_converged(state, state["config"], full_panel=True)
    receipt = RD.build_receipt(state)
    unj_lines = [d for d in receipt["degraded"] if d.startswith("seat-map-unjudgeable")]
    unav_lines = [d for d in receipt["degraded"]
                  if d.startswith("reviewer-fell-open-seatmap-unavailable")]
    assert len(unj_lines) == 1
    assert "no-author-family" in unj_lines[0]
    assert unav_lines == []


def test_seat_map_unavailable_disclosure_not_unjudgeable_prose():
    """NR-C: absent map discloses unavailable, not unjudgeable (#1190)."""
    state = RD.new_state(_cfg(leg="panel", vendors=["claude", "codex"]))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    RD._fold_panel(state, state["config"], {"seats": seats})
    RD._terminal_converged(state, state["config"], full_panel=True)
    receipt = RD.build_receipt(state)
    unj_lines = [d for d in receipt["degraded"] if d.startswith("seat-map-unjudgeable")]
    unav_lines = [d for d in receipt["degraded"]
                  if d.startswith("reviewer-fell-open-seatmap-unavailable")]
    assert len(unav_lines) == 1
    assert unj_lines == []


def test_unattested_cross_vendor_map_refuses_unrun_review_not_probe_parked():
    """NR-D: unattested cross-vendor map refuses unrun-review; probe gap no longer parks (#1272)."""
    cfg = _cfg_cert(leg="panel", vendors=["codex", "cursor"])
    seat_map = _seat_map_vendors({
        "code-reviewer": "codex",
        "security-reviewer": "cursor",
        "architecture-reviewer": "claude",
        "test-role": "codex",
        "premortem-reviewer": "cursor",
    })
    result = RD.run_loop(_seams(io={"seatMap": seat_map}), cfg)
    assert result["verdict"] == "converged"
    assert result["certificationShape"] == "full-panel-confirmed-constraint-violated"


def test_unattested_map_still_drives_fell_open_and_effective_seat_map():
    """NR-E: basis-incomplete map still feeds Contract B reveal consumers (#1190)."""
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    _set_seat_map(state, seat_map)
    rows, miss = RD._fell_open_rows(
        seat_map, {"code-reviewer": "claude"}, {"code-reviewer": "run"})
    assert rows == [{"seat": "code-reviewer", "configured": "codex", "ran": "claude",
                     "reason": "forfeit-fell-open"}]
    effective = RD.effective_seat_map(state)
    assert effective["seats"]["code-reviewer"]["vendor"] == "codex"


def test_seat_map_unjudgeable_quantifier_later_unjudgeable_arms():
    """INV-9 receipts arm: judgeable round 1 then ``no-seats`` round 2 arms — ledger empty (#714)."""
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg["fixerVendor"] = "cursor"
    state = RD.new_state(cfg)
    round1 = _assertable_seat_map(["claude", "codex"], fixer_vendor="cursor")
    round2 = {"seats": {}}
    state["seatMapReceipts"] = [
        {"round": "1", "map": round1},
        {"round": "2", "map": round2},
    ]
    state["rounds"] = {}
    assert state["rounds"] == {}
    assert RD._seat_map_unjudgeable(state) is True


def test_seat_map_unjudgeable_quantifier_earlier_unjudgeable_arms():
    """INV-9 receipts arm: ``no-seats`` round 1 then judgeable round 2 still arms — not existential."""
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg["fixerVendor"] = "cursor"
    state = RD.new_state(cfg)
    round1 = {"seats": {}}
    round2 = _assertable_seat_map(["claude", "codex"], fixer_vendor="cursor")
    state["seatMapReceipts"] = [
        {"round": "1", "map": round1},
        {"round": "2", "map": round2},
    ]
    state["rounds"] = {}
    assert state["rounds"] == {}
    assert RD._seat_map_unjudgeable(state) is True


def test_seat_map_unjudgeable_terminal_converged_shape_drivers_consumer():
    """No driver family: authorFamily-stripped map arms shapeDrivers; cursor control stays clean (#1190)."""
    SM = _load("seat_map")
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg.pop("fixerVendor")
    seat_map = _assertable_seat_map(["claude", "codex"], fixer_vendor=None)
    unjudgeable_map = dict(seat_map)
    unjudgeable_map.pop("authorFamily", None)
    driver_fam = model_registry.family_for("implementer", cfg.get("fixerVendor"))
    assert SM.derived_violations(unjudgeable_map, driver_fam) == []
    state = RD.new_state(cfg)
    _set_seat_map(state, unjudgeable_map)
    assert RD._seat_map_unavailable(state) is False
    assert RD._seat_map_unjudgeable(state) is True
    RD._terminal_converged(state, cfg, full_panel=True)
    assert "seat-map-unavailable" in state["certification"]["shapeDrivers"]
    control_cfg = dict(cfg)
    control_cfg["fixerVendor"] = "cursor"
    control_state = RD.new_state(control_cfg)
    _set_seat_map(control_state, unjudgeable_map)
    RD._terminal_converged(control_state, control_cfg, full_panel=True)
    assert RD._seat_map_unjudgeable(control_state) is False
    assert RD._seat_map_unavailable(control_state) is False
    assert control_state["certification"]["shapeDrivers"] == []
    assert "seat-map-unavailable" not in control_state["certification"]["shapeDrivers"]


def test_seat_map_unjudgeable_cert_shape_degraded_consumer():
    """No driver family: authorFamily-stripped map degrades shape; cursor control stays ``full-panel-confirmed`` (#1190)."""
    SM = _load("seat_map")
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg.pop("fixerVendor")
    seat_map = _assertable_seat_map(["claude", "codex"], fixer_vendor=None)
    unjudgeable_map = dict(seat_map)
    unjudgeable_map.pop("authorFamily", None)
    driver_fam = model_registry.family_for("implementer", cfg.get("fixerVendor"))
    assert SM.derived_violations(unjudgeable_map, driver_fam) == []
    state = RD.new_state(cfg)
    _set_seat_map(state, unjudgeable_map)
    assert RD._seat_map_unavailable(state) is False
    assert RD._seat_map_unjudgeable(state) is True
    RD._terminal_converged(state, cfg, full_panel=True)
    assert state["certification"]["shape"].endswith("-degraded")
    control_cfg = dict(cfg)
    control_cfg["fixerVendor"] = "cursor"
    control_state = RD.new_state(control_cfg)
    _set_seat_map(control_state, unjudgeable_map)
    RD._terminal_converged(control_state, control_cfg, full_panel=True)
    assert RD._seat_map_unjudgeable(control_state) is False
    assert control_state["certification"]["shape"] == "full-panel-confirmed"


# =============================================================================
# #1204 — per-round seatMapUnjudgeable reflects governing map for that round
# =============================================================================

def test_seat_map_unjudgeable_per_round_unjudgeable_then_judgeable():
    """#1204: round 1 unjudgeable then round 2 judgeable — per-round record clears, terminal stays."""
    SM = _load("seat_map")
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg["fixerVendor"] = "cursor"
    state = RD.new_state(cfg)
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    round1 = {"seats": {}}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": round1})
    assert state["rounds"]["1"]["seatMapUnjudgeable"] == [SM.VIOLATION_BASIS_NO_SEATS]
    state["round"] = 2
    round2 = _assertable_seat_map(["claude", "codex"], fixer_vendor="cursor")
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": round2})
    assert "seatMapUnjudgeable" not in state["rounds"]["2"]
    assert RD._seat_map_unjudgeable(state) is True


def test_seat_map_unjudgeable_per_round_judgeable_then_unjudgeable():
    """#1204 mirror: round 1 judgeable then round 2 unjudgeable — per-round basis on round 2 only."""
    SM = _load("seat_map")
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg["fixerVendor"] = "cursor"
    state = RD.new_state(cfg)
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    round1 = _assertable_seat_map(["claude", "codex"], fixer_vendor="cursor")
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": round1})
    assert "seatMapUnjudgeable" not in state["rounds"]["1"]
    state["round"] = 2
    round2 = {"seats": {}}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": round2})
    assert state["rounds"]["2"]["seatMapUnjudgeable"] == [SM.VIOLATION_BASIS_NO_SEATS]
    assert RD._seat_map_unjudgeable(state) is True


def test_seat_map_unjudgeable_double_fold_bad_then_good_clears_record():
    """#1204: double fold in one round — bad then good clears ``seatMapUnjudgeable`` (#1204 / A3)."""
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg["fixerVendor"] = "cursor"
    state = RD.new_state(cfg)
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    bad = {"seats": {}}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": bad})
    assert state["rounds"]["1"]["seatMapUnjudgeable"] == [_load("seat_map").VIOLATION_BASIS_NO_SEATS]
    good = _assertable_seat_map(["claude", "codex"], fixer_vendor="cursor")
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": good})
    assert "seatMapUnjudgeable" not in state["rounds"]["1"]
    assert RD._seat_map_unjudgeable(state) is True


def test_seat_map_unjudgeable_bad_good_round1_then_bad_round2_discloses_both():
    """#1204: bad→good round 1 plus unjudgeable round 2 — receipt must disclose both receipt rounds."""
    SM = _load("seat_map")
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg["fixerVendor"] = "cursor"
    state = RD.new_state(cfg)
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    bad = {"seats": {}}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": bad})
    good = _assertable_seat_map(["claude", "codex"], fixer_vendor="cursor")
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": good})
    assert "seatMapUnjudgeable" not in state["rounds"]["1"]
    state["round"] = 2
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": bad})
    assert state["rounds"]["2"]["seatMapUnjudgeable"] == [SM.VIOLATION_BASIS_NO_SEATS]
    assert RD._seat_map_unjudgeable(state) is True
    RD._terminal_converged(state, cfg, full_panel=True)
    receipt = RD.build_receipt(state)
    unj_lines = [d for d in receipt["degraded"] if d.startswith("seat-map-unjudgeable")]
    degraded_text = " ".join(unj_lines)
    assert "rounds 1" in degraded_text or "(round 1)" in degraded_text, unj_lines
    assert "(round 2)" in degraded_text, unj_lines
    assert SM.VIOLATION_BASIS_NO_SEATS in degraded_text


def test_seat_map_unjudgeable_double_fold_bad_then_good_receipt_disclosure_fallback():
    """#714 NR-C / #1204: bad→good re-fold clears per-round record but receipt still discloses basis."""
    SM = _load("seat_map")
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg["fixerVendor"] = "cursor"
    state = RD.new_state(cfg)
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    bad = {"seats": {}}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": bad})
    good = _assertable_seat_map(["claude", "codex"], fixer_vendor="cursor")
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": good})
    assert "seatMapUnjudgeable" not in state["rounds"]["1"]
    assert RD._seat_map_unjudgeable(state) is True
    RD._terminal_converged(state, cfg, full_panel=True)
    assert state["certification"]["shape"].endswith("-degraded")
    receipt = RD.build_receipt(state)
    unj_lines = [d for d in receipt["degraded"] if d.startswith("seat-map-unjudgeable")]
    assert len(unj_lines) == 1
    assert SM.VIOLATION_BASIS_NO_SEATS in unj_lines[0]


def test_seat_map_unjudgeable_double_fold_good_then_bad_records_basis():
    """#1204: double fold in one round — good then bad records basis on the round."""
    SM = _load("seat_map")
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg["fixerVendor"] = "cursor"
    state = RD.new_state(cfg)
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    good = _assertable_seat_map(["claude", "codex"], fixer_vendor="cursor")
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": good})
    assert "seatMapUnjudgeable" not in state["rounds"]["1"]
    bad = {"seats": {}}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": bad})
    assert state["rounds"]["1"]["seatMapUnjudgeable"] == [SM.VIOLATION_BASIS_NO_SEATS]
    assert RD._seat_map_unjudgeable(state) is True


def test_seat_map_unjudgeable_no_submission_judged_on_effective_map():
    """#1204: round with no ``seatMap`` submission is judged on ``effective_seat_map``."""
    SM = _load("seat_map")
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    cfg.pop("fixerVendor")
    state = RD.new_state(cfg)
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    round1 = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": round1})
    state["round"] = 2
    RD._fold_panel(state, state["config"], {"seats": seats})
    assert state["rounds"]["2"]["seatMapUnjudgeable"] == [SM.VIOLATION_BASIS_NO_AUTHOR_FAMILY]
    assert RD._seat_map_unjudgeable(state) is True


def test_emit_receipt_seat_map_derived_violations_replay_no_breach_lost():
    """INV-11: emitted ``seatMap`` carries derived violations — replay cannot read clean."""
    SM = _load("seat_map")
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    cfg.pop("fixerVendor")
    state = RD.new_state(cfg)
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    _set_seat_map(state, seat_map)
    state["terminal"] = "converged"
    state["certification"] = {"shape": "full-panel-confirmed-degraded"}
    receipt = RD.build_receipt(state)
    emitted = receipt["seatMap"]
    driver_fam = model_registry.family_for("implementer", cfg.get("fixerVendor"))
    replayed = SM.derived_violations(emitted, driver_fam)
    emitted_violations = emitted.get("violations") or []
    emitted_keys = {(str(v.get("constraint", "")), str(v.get("seat") or ""))
                    for v in emitted_violations if isinstance(v, dict)}
    replayed_keys = {(str(v.get("constraint", "")), str(v.get("seat") or ""))
                     for v in replayed if isinstance(v, dict)}
    # Replay must not discover a breach the emitted artifact omitted — subset runs the wrong way.
    assert replayed_keys <= emitted_keys
    assert replayed_keys


# =============================================================================
# #681 — seat-map receipt list (append-only, projection family)
# =============================================================================

def test_fold_appends_seat_map_receipt_not_merge():
    """axis: each fold appends a receipt; later partial maps do not overwrite earlier seats."""
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    round1_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    round1_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": round1_map})
    state["round"] = 2
    partial_map = {"seats": {"security-reviewer": {"vendor": "claude"}}}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": partial_map})
    assert len(state["seatMapReceipts"]) == 2
    assert state["seatMapReceipts"][0]["map"]["seats"]["code-reviewer"] == {"vendor": "codex"}
    assert RD._sm_latest_with_seats(state)["seats"] == partial_map["seats"]


def test_seat_map_receipts_legacy_prepend_with_receipt_list():
    """axis: legacy state[\"seatMap\"] prepended whenever present alongside receipts."""
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    state = RD.new_state(_cfg(leg="panel"))
    state["seatMap"] = {"seats": {"code-reviewer": {"vendor": "codex"}}}
    state["seatMapReceipts"] = [{"round": "1", "map": seat_map}]
    receipts = RD._seat_map_receipts(state)
    assert receipts[0]["round"] == "legacy"
    assert receipts[0]["map"]["seats"]["code-reviewer"]["vendor"] == "codex"
    assert receipts[1]["round"] == "1"


def test_later_pin_cannot_excuse_earlier_breach():
    """axis: per-receipt classify — later pin does not excuse earlier round's breach."""
    SM = _load("seat_map")
    breach_map = _seat_map_receipt_with_unexcused_maker_family()
    pin_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    pin_map["livenessPinScoped"] = True
    pin_map["violations"] = []
    pin_map["degradations"] = []
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    state["seatMapReceipts"] = [
        {"round": "1", "map": breach_map},
        {"round": "2", "map": pin_map},
    ]
    violations = RD._seat_map_violations(state)
    assert any(v.get("constraint") == "maker-family" for v in violations)


def test_emit_receipt_seat_map_provenance_live_cells_source_conservative():
    """axis: disagreeing liveCellsSource resolves to least-trusted source, not latest receipt."""
    map1 = _seat_map_vendors({d: "codex" for d in RD.DIMENSIONS})
    map1["liveCellsSource"] = LC.LIVE_CELLS_SOURCE_SYNTHESIZED
    map2 = _seat_map_vendors({d: "codex" for d in RD.DIMENSIONS})
    map2["liveCellsSource"] = LC.LIVE_CELLS_SOURCE_PROBED
    state = RD.new_state(_cfg(leg="panel"))
    state["seatMapReceipts"] = [
        {"round": "1", "map": map1},
        {"round": "2", "map": map2},
    ]
    emitted = RD._emit_receipt_seat_map(state)
    assert emitted.get("liveCellsSource") == LC.LIVE_CELLS_SOURCE_SYNTHESIZED
    single_state = RD.new_state(_cfg(leg="panel"))
    single_state["seatMapReceipts"] = [{"round": "1", "map": map1}]
    single_emitted = RD._emit_receipt_seat_map(single_state)
    assert single_emitted.get("liveCellsSource") == LC.LIVE_CELLS_SOURCE_SYNTHESIZED


def test_emit_receipt_seat_map_non_evidence_scalar_last_wins():
    """axis: scalars outside the evidence key set still follow last-wins across receipts."""
    map1 = _seat_map_vendors({d: "codex" for d in RD.DIMENSIONS})
    map1["roundNote"] = "FIRST"
    map2 = {"roundNote": "SECOND"}
    state = RD.new_state(_cfg(leg="panel"))
    state["seatMapReceipts"] = [
        {"round": "1", "map": map1},
        {"round": "2", "map": map2},
    ]
    emitted = RD._emit_receipt_seat_map(state)
    assert emitted.get("roundNote") == "SECOND"
    single_state = RD.new_state(_cfg(leg="panel"))
    single_state["seatMapReceipts"] = [{"round": "1", "map": map1}]
    single_emitted = RD._emit_receipt_seat_map(single_state)
    assert single_emitted.get("roundNote") == "FIRST"


def test_emit_receipt_seat_map_distinct_degradation_rows_survive():
    """axis: emitted map dedupes identical rows but distinct degradation rows survive."""
    row_a = {"constraint": "same-family", "seat": "security-reviewer", "reason": "alpha"}
    row_b = {"constraint": "same-family", "seat": "test-role", "reason": "beta"}
    map1 = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    map1["degradations"] = [row_a]
    map2 = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    map2["degradations"] = [row_b]
    state = RD.new_state(_cfg(leg="panel"))
    state["seatMapReceipts"] = [
        {"round": "1", "map": map1},
        {"round": "2", "map": map2},
    ]
    emitted = RD.build_receipt(state)["seatMap"]
    degs = emitted.get("degradations") or []
    assert row_a in degs and row_b in degs


def test_round_adapters_resolves_seat_maps_through_leaf_module():
    """axis: round_adapters resolves seat maps through seat_map_receipts (#681, #1185)."""
    adapters_path = os.path.join(_LIB, "round_adapters.py")
    with open(adapters_path, encoding="utf-8") as fh:
        source = fh.read()
    assert "seat_map_receipts" in source
    assert "import round_driver" not in source
    assert "round_driver.effective_seat_map" not in source
    if "effective_seat_map" in source:
        assert "seat_map_receipts.effective_seat_map" in source
        assert not re.search(r"(?<!seat_map_receipts\.)effective_seat_map", source)


def test_dead_seat_map_predicate_census_removed():
    """axis: dead seats-predicate helper is gone from round_driver."""
    dead_name = "_seat_map" + "_has_seats"
    driver_path = os.path.join(_LIB, "round_driver.py")
    with open(driver_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=driver_path)
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert dead_name not in names


_SEAT_MAP_RECEIPTS_CALLERS = frozenset({
    "latest_with_seats",
    "any_seats",
    "same_family_seats",
    "unexcused_violations",
    "pin_excused_records",
    "unjudgeable_receipts",
    "round_governing_map",
    "emit_receipt_seat_map",
})


def _seat_map_receipts_call_sites():
    """Return enclosing function names for every ``receipts(`` call in seat_map_receipts.py."""
    path = os.path.join(_LIB, "seat_map_receipts.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    sites = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name) and func.id == "receipts":
                    sites.add(node.name)
    return sites


def _seat_map_receipts_external_call_sites():
    """``round_driver`` functions that call ``receipts`` directly — must be none (#681)."""
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    sites = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if isinstance(func, ast.Name) and func.id == "_seat_map_receipts":
                sites.add(node.name)
            elif isinstance(func, ast.Attribute) and func.attr == "receipts":
                if isinstance(func.value, ast.Name) and func.value.id == "seat_map_receipts":
                    sites.add(node.name)
    return sites


def test_seat_map_receipts_projection_family_census_positive():
    """Every ``receipts`` caller is a projection-family member (#681)."""
    callers = _seat_map_receipts_call_sites()
    assert callers == set(_SEAT_MAP_RECEIPTS_CALLERS)
    external = _seat_map_receipts_external_call_sites()
    assert external == set()


_SEAT_MAP_STATE_READ_PATHS = (
    os.path.join(_LIB, "seat_map_receipts.py"),
    os.path.join(_LIB, "round_driver.py"),
    os.path.join(_LIB, "round_adapters.py"),
)
_ALLOWED_SEAT_MAP_STATE_READ_FN = "receipts"


def _ast_string_constant(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _state_names_in_function(func_node):
    """Names in *func_node* bound to the driver's ``state`` parameter."""
    param_names = {a.arg for a in (
        list(func_node.args.posonlyargs) + list(func_node.args.args)
        + list(func_node.args.kwonlyargs))}
    if "state" not in param_names:
        return set()
    names = {"state"}
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Name):
                    if node.value.id in names:
                        names.add(target.id)
    return names


def _seat_map_state_read_sites(paths=_SEAT_MAP_STATE_READ_PATHS):
    """Executable ``state[...]`` / ``state.get(...)`` reads of ``seatMap``, by enclosing function."""
    sites = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                sites.extend(_seat_map_reads_in_function(node, path))
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        sites.extend(_seat_map_reads_in_function(item, path))
    return sites


def _seat_map_reads_in_function(func_node, path):
    reads = []
    state_names = _state_names_in_function(func_node)
    if not state_names:
        return reads
    for node in ast.walk(func_node):
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name) and node.value.id in state_names:
                if _ast_string_constant(node.slice) == "seatMap":
                    reads.append((path, func_node.name))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr != "get":
                continue
            if not isinstance(node.func.value, ast.Name):
                continue
            if node.func.value.id not in state_names or not node.args:
                continue
            if _ast_string_constant(node.args[0]) == "seatMap":
                reads.append((path, func_node.name))
    return reads


def test_seat_map_blob_read_sites_census_negative():
    """No executable ``state[\"seatMap\"]`` read outside ``receipts`` (#681)."""
    sites = _seat_map_state_read_sites()
    by_fn = {fn for _path, fn in sites}
    assert _ALLOWED_SEAT_MAP_STATE_READ_FN in by_fn, (
        "allowed site %r not found in census %r" % (_ALLOWED_SEAT_MAP_STATE_READ_FN, sites))
    unexpected = sorted({(p, f) for p, f in sites if f != _ALLOWED_SEAT_MAP_STATE_READ_FN})
    assert not unexpected, "unexpected seatMap reads: %r" % unexpected


def test_partial_round2_degradations_preserves_same_family_shape():
    """axis: later shorter degradations list must not drop same-family disclosure."""
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    round1_map = _panel_seat_map_with_same_family("security-reviewer")
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": round1_map})
    assert RD._same_family_degraded(state) is True
    state["round"] = 2
    round2_map = _assertable_seat_map(state["config"]["vendors"])
    round2_map["degradations"] = []
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": round2_map})
    assert RD._same_family_degraded(state) is True
    assert "security-reviewer" in RD._same_family_seats(state)
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-degraded")
    assert "same-family" in state["certification"]["shapeDrivers"]


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
    result = RD.run_loop(_seams(io={"seatMap": seat_map}), _cfg_cert(leg="panel"))
    assert result["verdict"] == "converged"
    assert result["certificationShape"].endswith("-constraint-violated")


def test_fell_open_multi_seat_deterministic_disclosure_order():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({
        "architecture-reviewer": "claude",
        "code-reviewer": "codex",
        "security-reviewer": "cursor",
        "test-role": "codex",
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
        "premortem-reviewer", "test-role"]
    receipt = RD.build_receipt(state)
    fo_lines = [d for d in receipt["degraded"] if d.startswith("reviewer-fell-open (round")]
    assert len(fo_lines) == 2
    assert "code-reviewer" in fo_lines[0] and "codex" in fo_lines[0] and "claude" in fo_lines[0]
    assert "security-reviewer" in fo_lines[1] and "cursor" in fo_lines[1] and "claude" in fo_lines[1]
    prov_lines = [d for d in receipt["degraded"]
                  if d.startswith("reviewer-fell-open-provenance-unavailable")]
    assert len(prov_lines) == 1
    assert "premortem-reviewer, test-role" in prov_lines[0]


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
# #666 / #668 — vacuous seats + cross-vendor seats (#668 cluster WO-4)
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


def test_cross_vendor_all_empty_seat_stays_run_panel_complete():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"
    assert state["fullPanelRan"] is True
    assert state["_incompletePanel"] is False


def test_cross_vendor_codex_finding_cursor_empty_panel_complete():
    """A codex seat with a finding and an empty cursor seat leave the panel complete."""
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [{"title": "issue", "severity": "Minor"}]}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    r1 = state["rounds"]["1"]
    assert state["fullPanelRan"] is True
    assert "panel-seat-missing" not in _decision_kinds(state)
    assert r1.get("missingSeats") is None or r1.get("missingSeats") == []


def test_cross_vendor_mixed_empty_panel_stays_run_panel_complete():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    r1 = state["rounds"]["1"]
    assert r1["seatStatus"]["code-reviewer"] == "run"
    assert r1["seatStatus"]["security-reviewer"] == "run"
    assert state["fullPanelRan"] is True
    assert state["_incompletePanel"] is False


def test_io_seam_two_cross_vendor_seats_converge():
    """A seat map with two cross-vendor seats and no further evidence still converges."""
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    seams = _seams(io={"seatMap": seat_map})
    result = RD.run_loop(seams, _cfg_cert(leg="panel", vendors=["codex", "cursor"]))
    assert result["verdict"] == "converged"
    assert result["certificationShape"] is not None


def test_cross_vendor_empty_seat_no_panel_seat_missing_decision():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    r1 = state["rounds"]["1"]
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


def test_fell_open_codex_configured_claude_ran_panel_complete():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {"code-reviewer": "claude"},
    })
    assert state["fullPanelRan"] is True


def test_fold_panel_null_finding_cross_vendor_panel_still_complete():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [None]}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["fullPanelRan"] is True


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


def test_fold_panel_malformed_config_dimensions_no_raise():
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    for bad_dims in (1, [["code-reviewer"]], None, ["code-reviewer", 42]):
        st = RD.new_state(_cfg(leg="panel", dimensions=bad_dims))
        RD._fold_panel(st, st["config"], {"seats": seats, "seatMap": seat_map})
        assert st["fullPanelRan"] is True


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
    """#651: composer and grok are ONE family, so a cursor-only panel auditing a cursor fix has no
    auditor at all. Under the old registry (composer='cursor', grok='xai') the same-vendor fallback
    loop returned ('cursor', 'independent') — a self-audit labelled independent. This pins that
    lane closed while leaving the real cross-family path intact."""
    vendor, independence = RD._auditor_vendor({"vendors": ["cursor"]}, "cursor")
    assert independence == "unseatable"
    assert vendor is None
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
    leg_rnds = {"fix": [], "verify": []}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "gap-sweep":
            return []
        if dim == "scoped-finder":
            seq["n"] += 1
            return [{"title": "scoped-%d" % seq["n"], "severity": "Important", "consequence": _CONSEQUENCE,
                     "file": "newsurf.py", "line": 1}]
        if dim == "code-reviewer":
            seq["n"] += 1
            return {"findings": [{"title": "panel-%d" % seq["n"], "severity": "Important", "consequence": _CONSEQUENCE,
                                  "file": "f.py", "line": 1}]}
        return {}

    fix_n = {"n": 0}

    def fix_step(batch, rnd, payload):
        fix_n["n"] += 1
        leg_rnds["fix"].append(rnd)
        return {"fixes": [], "headDiff": _headf_ns(fix_n["n"]), "changedSubjects": ["Code"]}

    def verify_runner(cmd, rnd):
        leg_rnds["verify"].append(rnd)
        return "pass"

    seams = _seams(reviewer=reviewer, fix_step=fix_step, verify_runner=verify_runner, vendors=["claude", "codex"])
    seams["_legRnds"] = leg_rnds
    return seams


def test_clean_rearm_forever_halts_at_round_cap(tmp_path):
    """DoD headline: clean audits + fresh blocker every review round hands back at the cap."""
    # axis: the ROUND BOUNDARY — a round above the cap never begins (not: the cap round's findings)
    cap = 4
    seams = _rearm_forever_seams()
    result = RD.run_loop(seams, _cfg_cert(maxRounds=cap))
    assert result["verdict"] == "handed-back"
    leg_rnds = seams["_legRnds"]
    # axis: the cap round runs to completion — fixer and verify both ran at the cap before the hand-back
    assert cap in leg_rnds["fix"]
    assert cap in leg_rnds["verify"]


def test_clean_rearm_forever_hands_back_at_a_cap_below_the_default(tmp_path):
    """A library-path cap below the default binds: no round past it begins."""
    # axis: the ROUND BOUNDARY — rounds reached N and round N+1 not begun are separate facts
    seams = _rearm_forever_seams()
    result = RD.run_loop(seams, _cfg_cert(maxRounds=3))
    assert result["verdict"] == "handed-back"
    assert max(seams["_legRnds"]["verify"]) == 3


def test_delta_at_cap_records_ledger_then_converges_with_no_round_past_the_cap():
    """Re-pinned: a delta round at the cap whose audits discharged appends its ledger record and ends the
    review on that round (no confirmation panel is owed, so no round past the cap is asked for)."""
    # axis: the cap round completes (delta ledger append) and nothing asks for the round after it
    state = RD.new_state(_cfg(maxRounds=4))
    state["round"] = 4
    state["findings"] = []
    state["fullPanelRan"] = False
    state["auditRounds"] = [{"round": 3, "outcomes": [{"identity": "x", "ruling": "discharged"}]}]
    state["_auditOutcome"] = {"notDischarged": [], "discharged": ["x"]}
    RD._settle_delta(state, state["config"])
    assert any(r.get("kind") == "delta" and r.get("round") == 4 for r in state["_records"])
    assert state["terminal"] == "converged"
    assert state["certification"]["shape"].startswith("audited-chain")
    assert not any(d["kind"] == "round-cap" for d in state["decisions"])
    assert state["round"] == 4


def test_delta_at_cap_challenged_principle_parks_without_the_cap():
    """Challenged-principle park at the cap round terminates; the cap boundary never runs."""
    # axis: challenged-principle-recurring parks inside _settle_delta — round-cap is advance-only
    finding = {"title": "recurs", "file": "a.js", "severity": "Critical", "consequence": _CONSEQUENCE, "dimension": "code-reviewer",
               "classKey": "Code::x::recurs"}
    prior = {
        "schemaVersion": 2, "round": 3, "kind": "delta",
        "dimensions": {"code-reviewer": {"dimension": "code-reviewer", "status": "run",
                                         "confidence": "high", "tier": RD.DEEP, "findings": [finding]}},
        "findings": [finding], "coverageDecisions": [],
    }
    state = RD.new_state(_cfg(maxRounds=4))
    state["round"] = 4
    state["findings"] = [finding]
    state["_records"] = [prior]
    state["_coverage"] = [{"id": "RCD-1", "classKey": "Code::x::recurs"}]
    state["auditRounds"] = [{"round": 3, "outcomes": [{"identity": "x", "ruling": "discharged"}]}]
    state["_auditOutcome"] = {"notDischarged": [], "discharged": ["x"]}
    RD._settle_delta(state, state["config"])
    assert state["terminal"] == "cannot-certify"
    assert not any(d["kind"] == "round-cap" for d in state["decisions"])


def _rearm_until_converge_seams(converge_at):
    """Like _rearm_forever_seams but stops surfacing blockers at converge_at so the run converges."""
    seq = {"n": 0}

    def reviewer(dim, tier, rnd, ctx):
        if rnd >= converge_at:
            return []
        if dim == "gap-sweep":
            return []
        if dim == "scoped-finder":
            seq["n"] += 1
            return [{"title": "scoped-%d" % seq["n"], "severity": "Important", "consequence": _CONSEQUENCE,
                     "file": "newsurf.py", "line": 1}]
        if dim == "code-reviewer":
            seq["n"] += 1
            return {"findings": [{"title": "panel-%d" % seq["n"], "severity": "Important", "consequence": _CONSEQUENCE,
                                  "file": "f.py", "line": 1}]}
        return {}

    fix_n = {"n": 0}

    def fix_step(batch, rnd, payload):
        fix_n["n"] += 1
        return {"fixes": [], "headDiff": _headf_ns(fix_n["n"]), "changedSubjects": ["Code"]}

    return _seams(reviewer=reviewer, fix_step=fix_step, vendors=["claude", "codex"])


def test_round_three_below_the_cap_does_not_hand_back(tmp_path):
    """Below the cap the advance path converges normally — no round-cap decision."""
    # axis: the cap does not fire below it — driven through the real advance path, not settle
    receipt = RD.run_loop(_rearm_until_converge_seams(3), _cfg_cert(maxRounds=4))
    reached = max(r["round"] for r in receipt["rounds"])
    assert reached == 3
    assert receipt["verdict"] == "converged"
    assert not any(r.get("stallChoice") for r in receipt["rounds"])


def test_clean_below_the_cap_still_certifies_converged(tmp_path):
    """No-regression: a clean run below the cap still certifies converged."""
    receipt = RD.run_loop(_seams(), _cfg_cert())
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"] is not None


def test_loaded_state_above_cap_hands_back_on_cmd_next(tmp_path):
    """A persisted non-terminal state above the cap hands back on cmd_next — no certification."""
    # axis: persisted state at round cap+1 hands back on cmd_next with round-cap, no certification
    d = str(tmp_path)
    state = RD.new_state(_cfg(maxRounds=4))
    state["round"] = 5
    state["findings"] = []
    state["fullPanelRan"] = True
    state["step"] = RD.P_VERIFY
    RD.save_state(d, state)
    n = RD.cmd_next(d)
    assert n["ok"]
    assert n["phase"] == RD.P_TERMINAL
    ok, reloaded = RD.load_state(d)
    assert ok
    assert reloaded["terminal"] == "handed-back"
    assert reloaded["certification"]["shape"] is None
    assert any(dec["kind"] == "round-cap" for dec in reloaded["decisions"])
    detail = next(dec["detail"] for dec in reloaded["decisions"] if dec["kind"] == "round-cap")
    # axis: loaded-state hand-back detail names the cap and the round reached separately — not boundary "not begun" wording
    assert "Round cap 4 reached" in detail
    assert "round 5 had already begun" in detail
    assert "not begun" not in detail


def test_loaded_state_above_cap_hands_back_on_cmd_submit(tmp_path):
    """A persisted non-terminal state above the cap hands back on cmd_submit — no certification."""
    # axis: persisted state at round cap+1 hands back on cmd_submit with round-cap, no certification
    d = str(tmp_path)
    state = RD.new_state(_cfg(maxRounds=4))
    state["round"] = 5
    state["findings"] = []
    state["fullPanelRan"] = True
    state["step"] = RD.P_VERIFY
    state["pending"] = {"action": RD.P_VERIFY, "round": 5, "phase": RD.P_VERIFY, "attempt": 0,
                        "payload": {}}
    RD.save_state(d, state)
    h = RD.state_hash(state)
    out = RD.cmd_submit(d, RD.P_VERIFY, 0, h, {"result": "pass"})
    assert out["ok"] is True
    assert out["nextStep"] == RD.P_TERMINAL
    ok, reloaded = RD.load_state(d)
    assert ok
    assert reloaded["terminal"] == "handed-back"
    assert reloaded["certification"]["shape"] is None
    assert any(dec["kind"] == "round-cap" for dec in reloaded["decisions"])
    detail = next(dec["detail"] for dec in reloaded["decisions"] if dec["kind"] == "round-cap")
    # axis: loaded-state hand-back detail names the cap and the round reached separately — not boundary "not begun" wording
    assert "Round cap 4 reached" in detail
    assert "round 5 had already begun" in detail
    assert "not begun" not in detail


def test_loaded_state_at_cap_runs_on_cmd_next(tmp_path):
    """A persisted state at round == cap is not handed back on cmd_next entry."""
    # axis: persisted state at round == cap runs — equality is allowed
    d = str(tmp_path)
    state = RD.new_state(_cfg(maxRounds=4))
    state["round"] = 4
    state["findings"] = []
    state["fullPanelRan"] = True
    state["step"] = RD.P_VERIFY
    RD.save_state(d, state)
    n = RD.cmd_next(d)
    assert n["ok"]
    assert n["phase"] != RD.P_TERMINAL
    ok, reloaded = RD.load_state(d)
    assert ok
    assert reloaded.get("terminal") is None
    assert not any(dec["kind"] == "round-cap" for dec in reloaded["decisions"])


def test_loaded_terminal_above_cap_re_emits_unchanged(tmp_path):
    """A stored terminal above the cap re-emits unchanged — the loaded-state guard does not clobber."""
    # axis: already-terminal persisted state above the cap re-emits its stored terminal unchanged
    d = str(tmp_path)
    state = RD.new_state(_cfg(maxRounds=4))
    state["round"] = 5
    state["terminal"] = "converged"
    state["certification"] = {"shape": "full-panel-confirmed-degraded", "reason": "stored"}
    state["step"] = RD.P_TERMINAL
    state["pending"] = {"action": RD.P_TERMINAL, "round": 5, "phase": RD.P_TERMINAL, "attempt": 0,
                        "payload": {"verdict": "converged", "certification": state["certification"]}}
    state["decisions"] = [{"kind": "converged", "detail": "stored"}]
    RD.save_state(d, state)
    n = RD.cmd_next(d)
    assert n["ok"]
    assert n["phase"] == RD.P_TERMINAL
    ok, reloaded = RD.load_state(d)
    assert ok
    assert reloaded["terminal"] == "converged"
    assert reloaded["certification"]["shape"] == "full-panel-confirmed-degraded"
    assert not any(dec["kind"] == "round-cap" for dec in reloaded["decisions"])


def test_run_loop_parks_on_max_rounds_refusal():
    """B2: run_loop with a non-positive maxRounds parks cannot-certify; never raises."""
    result = RD.run_loop(_seams(), _cfg_cert(maxRounds=0))
    assert result["verdict"] == "cannot-certify"
    assert result["certificationShape"] is None


def test_persisted_config_without_max_rounds_resolves_the_round_cap():
    """A persisted config with no usable maxRounds resolves ROUND_CAP — never cap-less."""
    cfg = dict(RD.new_state(_cfg())["config"])
    cfg.pop("maxRounds", None)
    assert RD._round_cap(cfg) == RD.round_phases.ROUND_CAP


def _round_slice_is_round_key(node):
    """True when node is state['round'] or state[\"round\"]."""
    return (isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == "round")


_MODULE_SCOPE = "<module>"


def _round_counter_mutation_sites():
    """Return (enclosing function name, lineno) for every state['round'] write in round_driver."""
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    sites = []

    def record_write(assign_node, enclosing):
        if isinstance(assign_node, ast.Assign):
            targets = assign_node.targets
        elif isinstance(assign_node, (ast.AugAssign, ast.AnnAssign)):
            targets = [assign_node.target]
        else:
            return
        for target in targets:
            if isinstance(target, ast.Subscript) and _round_slice_is_round_key(target):
                sites.append((enclosing, assign_node.lineno))
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    if isinstance(elt, ast.Subscript) and _round_slice_is_round_key(elt):
                        sites.append((enclosing, assign_node.lineno))

    def visit(node, enclosing):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in node.body:
                visit(child, node.name)
            return
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            record_write(node, enclosing)
        for child in ast.iter_child_nodes(node):
            visit(child, enclosing)

    for child in tree.body:
        visit(child, _MODULE_SCOPE)
    return sites


def test_round_counter_mutation_sites_census():
    """state['round'] is written only by _advance_round on the advance path and by
    _begin_extra_audit_round for the one extra audit round."""
    # axis: only the two writers, the advance path and the extra audit round, may mutate state['round'] — dict literals in new_state are construction
    sites = _round_counter_mutation_sites()
    assert len(sites) >= 1, "expected at least one state['round'] mutation site"
    writers = {func for func, _lineno in sites}
    expected = {"_advance_round", "_begin_extra_audit_round"}
    extra = writers - expected
    missing = expected - writers
    assert writers == expected, (
        "unexpected state['round'] writer(s): %s; missing: %s" % (sorted(extra), sorted(missing))
    )


def _delta_settle_state_for_breaker(monkeypatch, breaker_result):
    state = RD.new_state(_cfg(maxRounds=10))
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
    "audit-stall",
})
_SETTLE_DELTA_UNREACHABLE = frozenset({
    "max-iterations",
    "no-net-progress",
    "recurring-finding",
    "challenged-principle-recurring",
    CB.ROUND_CEILING_REASON,
})


def test_settle_delta_breaker_reasons_reachable_and_claimed(monkeypatch):
    """Each BREAKER_REASONS member at _settle_delta is reachable-and-claimed or unreachable."""
    audit_emitted = _audit_breaker_emitted_reasons()
    for reason in _SETTLE_DELTA_UNREACHABLE:
        assert reason not in audit_emitted, reason

    # max-iterations — the audit breaker no longer emits it: the round cap is the driver's boundary.
    # audit-stall — discharged targets leave no open work; self-recovery settles on this round's audit.
    state = _delta_settle_state_for_breaker(monkeypatch, {
        "halt": True, "reason": "audit-stall", "detail": "stalled",
        "stalledIdentities": ["x"],
    })
    state["_auditTargets"] = [{"id": "x", "identity": "x", "severity": "Important",
                               "file": "f.py", "line": 1}]
    RD._settle_delta(state, state["config"])
    # re-pinned: it used to step to a confirmation panel; no later round runs a panel now
    assert state["step"] == RD.P_TERMINAL
    assert any(d["kind"] == "self-recovery" for d in state["decisions"])
    assert not any(d["kind"] == "confirmation-rearm" for d in state["decisions"])

    # round-ceiling — unreachable at _settle_delta; enforced on the round-advance boundary only.
    assert CB.ROUND_CEILING_REASON not in audit_emitted


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
    assert state["step"] != RD.P_APPLY_FIXES
    detail = next(d["detail"] for d in state["decisions"] if d["kind"] == "cannot-certify")
    assert "synthetic-unregistered-reason" in detail


# --- on-disk receipt trust (#1107 WO-c4A A1) -----------------------------------------------


def test_on_disk_receipt_class_rejects_invalid_known_schema(tmp_path):
    # axis: receipt_kind match without validate_receipt must classify as untrusted
    d = str(tmp_path / "invalid-interim")
    os.makedirs(d)
    with open(os.path.join(d, RD.RECEIPT_FILE), "w", encoding="utf-8") as fh:
        json.dump({"schema": RD.RECEIPT_INTERIM_SCHEMA}, fh)
    assert RD._on_disk_receipt_class(d) == "untrusted"
    assert RD._receipt_write_refusal(
        d, terminal_reason="terminal-receipt-exists",
        untrusted_reason="terminal-receipt-unreadable") == "terminal-receipt-unreadable"


def test_owner_provenance_every_declared_shape_has_a_predicate():
    """#1194 FU7: every shape string in OWNER_PROVENANCE_FIELD_SHAPES resolves to a validator.

    An unrecognized shape fails closed (owner-supplied becomes unreachable) — safe but SILENT.
    This pin turns adding a shape string without its predicate into a red test instead."""
    predicates = RD._owner_provenance_shape_predicates()
    missing = sorted(set(RD.OWNER_PROVENANCE_FIELD_SHAPES.values()) - set(predicates))
    assert not missing, "declared shapes with no predicate (owner-supplied unreachable): %s" % missing
    for shape, predicate in predicates.items():
        assert callable(predicate), "predicate for %r is not callable" % shape


# --- certification artifact materialization (#1271) ---------------------------

def _certification_refusal_session(tmp_path):
    fixtures_dir = _HERE
    if fixtures_dir not in sys.path:
        sys.path.insert(0, fixtures_dir)
    from session_fixture_support import DEFAULT_PANEL_PAYLOAD_SHA, write_session

    return write_session(
        tmp_path,
        name="cert-refusal",
        state={
            "config": {
                "baseGuard": "not-checked",
                "fixerVendor": "claude",
                "headSha": "a" * 40,
            }
        },
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )


# --- the verify head is an input to the next panel's diff, never a stored fact --------------

def _verify_fold_state(**cfg_over):
    state = RD.new_state(_cfg(**cfg_over))
    state["round"] = 1
    state["rounds"] = {"1": {}}
    return state


def _git_repo_with_head(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(
        ["git", "-c", "user.email=t@t.local", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    return str(repo), head


def _head_lookup_session(base, repo, **meta_over):
    session_dir = base / "session"
    session_dir.mkdir(parents=True)
    meta = {"headSha": "0" * 40, "repoRoot": repo}
    meta.update(meta_over)
    (session_dir / RD.round_records.META_FILE).write_text(
        json.dumps(meta, sort_keys=True) + "\n", encoding="utf-8")
    return str(session_dir)


def test_verify_fold_records_no_head():
    head_key = "verified" + "Head"
    for resolution in (("a" * 40, None), (None, "head unresolved")):
        state = _verify_fold_state()
        state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
        state["_newSurface"] = {"f.py": [1]}
        RD._fold_verify(state, state["config"], {"result": "pass"}, resolution=resolution)
        rec = state["rounds"]["1"]
        assert rec["verifyResult"] == "pass"
        assert head_key not in rec
        assert head_key + "Refused" not in rec


def test_verify_fold_without_a_resolution_raises():
    state = _verify_fold_state()
    with pytest.raises(ValueError):
        RD._fold_verify(state, state["config"], {"result": "pass"}, resolution=None)
    assert "verifyResult" not in state["rounds"]["1"]


def test_verify_fold_unresolved_head_post_audits_advances():
    state = _verify_fold_state()
    state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
    state["_newSurface"] = {"f.py": [1]}
    state["_fixDeltaDiff"] = "diff --git a/f.py b/f.py\n"
    RD._fold_verify(state, state["config"], {"result": "pass"},
                    resolution=(None, "fix-fold head: repo root unresolvable"))
    assert not state.get("terminal")
    assert state["step"] == RD.P_SCOPED
    assert "_verifyThen" not in state


def test_after_audits_with_no_fix_delta_hands_back_and_never_rebuilds():
    # axis: a delta round with no string `_fixDeltaDiff` hands back even when a baseline and head diff could rebuild one
    state = _verify_fold_state()
    state["_newSurface"] = {"f.py": [1]}
    state["deltaBaseline"] = {"round": 1, "diff": _R2B_REVIEWED}
    state["headDiff"] = _R2B_HEAD_MF
    RD._after_audits(state, state["config"])
    assert state["terminal"] == "handed-back"
    assert state["step"] != RD.P_SCOPED
    assert "_fixDeltaDiff" not in state
    assert state["decisions"][-1]["kind"] == "fix-surface-unknown"


def _saved_delta_session(tmp_path, *, step, pending, surface, baseline=True, **over):
    """A real session directory holding a delta round's state saved by the previous release (session
    generation 6): round 2 at ``step``, a scoped surface, no `_fixDeltaDiff`."""
    over.setdefault("sessionGeneration", 6)
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout = str(tmp_path / "checkout")
    enter_checkout(checkout)
    _seed_repo_root_if_missing(d, checkout)
    first = RD.cmd_next(d, _cfg(maxRounds=4))
    assert first["ok"] and first["action"] == RD.P_PANEL, first
    ok, state = RD.load_state(d)
    assert ok and isinstance(state, dict), state
    state.update(round=2, step=step, _newSurface=surface, **over)
    state["rounds"].setdefault("2", {})
    state.pop("_fixDeltaDiff", None)
    if baseline:
        state["deltaBaseline"] = {"round": 2, "diff": _R2B_REVIEWED}
        state["headDiff"] = _R2B_HEAD_MF
    else:
        state["deltaBaseline"] = None
    state["pending"] = ({"action": step, "round": 2, "phase": step, "attempt": 1,
                         "payload": {"hunks": surface, "tier": RD.DEEP}} if pending else None)
    RD.save_state(d, state)
    return d


_STRETCH_STEPS = [
    pytest.param({"step": RD.P_AUDITS}, id="audits"),
    pytest.param({"step": RD.P_VERIFY, "_verifyThen": RD.VERIFY_THEN_POST_AUDITS}, id="post-audits-verify"),
    pytest.param({"step": RD.P_SCOPED}, id="scoped"),
]


@pytest.mark.parametrize("pending", [False, True], ids=["step-only", "pending"])
@pytest.mark.parametrize("held", _STRETCH_STEPS)
def test_a_generation_6_session_saved_in_the_delta_stretch_is_handed_back_before_any_order(tmp_path, held, pending):
    # axis: each step of the audit / post-audits verify / scoped stretch of a generation-6 session hands back on the next command
    held = dict(held)
    d = _saved_delta_session(tmp_path, step=held.pop("step"), pending=pending,
                             surface={"f.py": [{"start": 50, "end": 51, "text": "x"}]}, **held)
    answer = RD.cmd_next(d)
    assert answer["ok"] and answer["action"] == RD.P_TERMINAL, answer
    ok, state = RD.load_state(d)
    assert state["terminal"] == "handed-back" and state["pending"]["action"] == RD.P_TERMINAL
    assert state["decisions"][-1]["kind"] == "fix-surface-unknown"
    assert "_fixDeltaDiff" not in state
    assert [row["outcome"] for row in RD.read_journal(d)
            if row.get("outcome") == "previous-release-hand-back"] == ["previous-release-hand-back"]


def _changed_test_finding(*, kept):
    finding = {"title": "Retry charges twice", "file": "tests/test_charge.py", "line": 1,
               "severity": "Important", "taxonomy": "break-it-test",
               "suggestion": RD._break_it_block_text({"path": "tests/test_charge.py", "run": "pytest"},
                                                     "def test_x():\n    assert True\n"),
               RD.break_it.RUNS_FIELD: [{"test": "tests/test_charge.py",
                                         "changedWhy": "the draft missed an import"}]}
    if kept:
        finding[RD.REVIEWER_TEST_FIELD] = "def test_x():\n    assert False\n"
    return finding


def test_a_generation_6_session_holding_a_changed_test_with_no_kept_original_is_handed_back():
    # axis: a recorded change with no kept REVIEWER_TEST_FIELD hands back at any step, outside the delta stretch too
    state = _verify_fold_state()
    state.update(sessionGeneration=6, round=1, step=RD.P_APPLY_FIXES, pending=None,
                 findings=[_changed_test_finding(kept=False)])
    assert RD._finish_saved_previous_release(state) is True
    assert state["terminal"] == "handed-back" and state["pending"] is None
    assert state["decisions"][-1]["kind"] == "fix-surface-unknown"


def test_a_generation_6_session_whose_changed_test_keeps_its_original_is_left_alone():
    # axis: a generation-6 session outside the stretch with every changed test's original kept is not handed back
    state = _verify_fold_state()
    state.update(sessionGeneration=6, round=1, step=RD.P_APPLY_FIXES, pending=None,
                 findings=[_changed_test_finding(kept=True)])
    before = json.dumps(state, sort_keys=True)
    assert RD._finish_saved_previous_release(state) is False
    assert json.dumps(state, sort_keys=True) == before


def test_a_generation_6_session_whose_only_changed_test_sits_in_to_verify_is_handed_back():
    # axis: the guard reads the staged `_toVerify` copies and the ledger, the copies break-it-change rewrites
    for fields in ({"_toVerify": [_changed_test_finding(kept=False)]},
                   {"dispositionLedger": [_changed_test_finding(kept=False)]}):
        state = _verify_fold_state()
        state.update(sessionGeneration=6, round=1, step=RD.P_VERIFIERS, pending=None,
                     findings=[], fixBatch=[], _auditTargets=[], **fields)
        assert RD._finish_saved_previous_release(state) is True, fields
        assert state["terminal"] == "handed-back"
        assert state["decisions"][-1]["kind"] == "fix-surface-unknown"


def test_a_generation_6_stretch_session_that_holds_its_fix_delta_and_test_facts_is_left_alone():
    # axis: a stretch step is handed back only for missing evidence, never for the generation alone
    target = dict(_changed_test_finding(kept=True), breakIt={"original": "x"})
    state = _verify_fold_state()
    state.update(sessionGeneration=6, round=2, step=RD.P_SCOPED, pending=None,
                 _newSurface={"f.py": [{"start": 3, "end": 3, "text": "x"}]},
                 _fixDeltaDiff="diff --git a/f.py b/f.py\n", _auditTargets=[target])
    before = json.dumps(state, sort_keys=True)
    assert RD._finish_saved_previous_release(state) is False
    assert json.dumps(state, sort_keys=True) == before
    state["_auditTargets"] = [_changed_test_finding(kept=True)]
    assert RD._finish_saved_previous_release(state) is True
    assert state["decisions"][-1]["kind"] == "fix-surface-unknown"


def test_a_generation_6_hand_back_tells_the_reader_to_start_a_fresh_review():
    # axis: the previous-release hand-back message names the way out — a fresh review
    state = _verify_fold_state()
    state.update(sessionGeneration=6, round=1, step=RD.P_APPLY_FIXES, pending=None,
                 findings=[_changed_test_finding(kept=False)])
    assert RD._finish_saved_previous_release(state) is True
    assert "start a fresh review" in state["decisions"][-1]["detail"]


def test_a_generation_6_session_outside_both_hand_back_cases_still_finishes():
    # axis: a round-1 step, and a round-2 step outside audit / post-audits verify / scoped, are never handed back
    for fields in ({"round": 1, "step": RD.P_AUDITS},
                   {"round": 2, "step": RD.P_VERIFIERS},
                   {"round": 2, "step": RD.P_VERIFY, "_verifyThen": None}):
        state = _verify_fold_state()
        state.update(sessionGeneration=6, pending=None, findings=[], fixBatch=[], _auditTargets=[], **fields)
        before = json.dumps(state, sort_keys=True)
        assert RD._finish_saved_previous_release(state) is False, fields
        assert json.dumps(state, sort_keys=True) == before


def test_a_current_generation_session_with_the_fields_is_untouched_by_the_hand_back():
    # axis: a current-generation stretch whose fields are all present is never touched
    for fields in ({"step": RD.P_SCOPED, "_fixDeltaDiff": "diff --git a/f.py b/f.py\n",
                    "findings": [_changed_test_finding(kept=True)]},
                   {"step": RD.P_AUDITS, "_fixDeltaDiff": "diff --git a/f.py b/f.py\n",
                    "findings": [_changed_test_finding(kept=True)]}):
        state = _verify_fold_state()
        state.update(round=2, pending=None, _newSurface={"f.py": [{"start": 3, "end": 3, "text": "x"}]},
                     **fields)
        assert state["sessionGeneration"] == RD.SESSION_GENERATION
        before = json.dumps(state, sort_keys=True)
        assert RD._finish_saved_previous_release(state) is False
        assert json.dumps(state, sort_keys=True) == before


def test_a_generation_7_session_saved_without_the_kept_original_is_handed_back():
    # axis: a pre-change generation-7 session holding a changed test with no kept original is handed back, never certified
    state = _verify_fold_state()
    state.update(round=2, step=RD.P_AUDITS, pending=None, findings=[_changed_test_finding(kept=False)])
    assert state["sessionGeneration"] == RD.SESSION_GENERATION
    assert RD._finish_saved_previous_release(state) is True
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == "fix-surface-unknown"


def test_a_generation_7_extra_audit_whose_target_lacks_break_it_facts_is_handed_back():
    # axis: an extra audit round's target that carries a test but no breakIt facts is handed back, not settled
    target = _changed_test_finding(kept=True)
    state = _verify_fold_state()
    state.update(round=3, step=RD.P_AUDITS, pending=None, extraAudit={"round": 3}, _auditTargets=[target])
    assert RD._finish_saved_previous_release(state) is True
    assert state["terminal"] == "handed-back"
    state = _verify_fold_state()
    state.update(round=3, step=RD.P_AUDITS, pending=None, extraAudit={"round": 3},
                 _auditTargets=[dict(target, breakIt={"match": "same"})])
    assert RD._finish_saved_previous_release(state) is False


# A PR hunk whose `+b` the fix deleted: the deletion anchors on the `+a` of its own hunk, not on the second hunk.
_DELETION_REVIEWED = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
                      "@@ -10,0 +10,2 @@\n+a\n+b\n"
                      "@@ -100,1 +102,1 @@\n-x\n+y\n")
_DELETION_HEAD = ("diff --git a/f.py b/f.py\nindex 1..3 100644\n--- a/f.py\n+++ b/f.py\n"
                  "@@ -10,0 +10,1 @@\n+a\n"
                  "@@ -100,1 +101,1 @@\n-x\n+y\n")
# A hunk at the end of the file: the fix deleted `+guard`, so the surviving file ends at line 9.
_EOF_REVIEWED = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
                 "@@ -7,4 +7,4 @@\n c7\n c8\n c9\n-x\n+guard\n")
_EOF_HEAD = ("diff --git a/f.py b/f.py\nindex 1..3 100644\n--- a/f.py\n+++ b/f.py\n"
             "@@ -7,4 +7,3 @@\n c7\n c8\n c9\n-x\n")
# A hunk with nothing left but removals once the fix deleted its additions; a second hunk has citable lines.
_REMOVALS_ONLY_REVIEWED = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
                           "@@ -10,2 +10,2 @@\n-x\n-y\n+a\n+b\n"
                           "@@ -100,1 +98,1 @@\n-p\n+q\n")
_REMOVALS_ONLY_HEAD = ("diff --git a/f.py b/f.py\nindex 1..3 100644\n--- a/f.py\n+++ b/f.py\n"
                       "@@ -10,2 +10,0 @@\n-x\n-y\n"
                       "@@ -100,1 +98,1 @@\n-p\n+q\n")
_DELETION_CASES = [(_DELETION_REVIEWED, _DELETION_HEAD), (_EOF_REVIEWED, _EOF_HEAD),
                   (_REMOVALS_ONLY_REVIEWED, _REMOVALS_ONLY_HEAD)]


def _deletion_surface(reviewed, head):
    surface, _text = RD._fix_delta_surface(RD.new_state(_cfg()), reviewed, head)
    return surface


def test_a_fix_that_only_removes_a_pr_addition_keeps_a_head_anchor_for_the_deletion():
    surface = _deletion_surface(_DELETION_REVIEWED, _DELETION_HEAD)
    assert _line_ranges(surface) == {"f.py": [(10, 10)]}, surface
    assert 10 in RD.diff_scope.parse_diff_lines(_DELETION_HEAD)["f.py"]


def test_a_deletion_at_the_end_of_the_file_anchors_on_a_line_the_head_diff_registers():
    surface = _deletion_surface(_EOF_REVIEWED, _EOF_HEAD)
    registered = RD.diff_scope.parse_diff_lines(_EOF_HEAD)["f.py"]
    assert registered == {7, 8, 9}
    anchors = {n for h in surface["f.py"] for n in (h["start"], h["end"])}
    assert anchors and anchors <= registered, surface


def test_a_deletion_in_a_hunk_with_no_citable_line_is_marked_not_numbered():
    surface = _deletion_surface(_REMOVALS_ONLY_REVIEWED, _REMOVALS_ONLY_HEAD)
    assert [(h["start"], h["end"], h.get("removedOnly")) for h in surface["f.py"]] == [(0, 0, True)], surface
    assert "-+a" in surface["f.py"][0]["text"] and "-+b" in surface["f.py"][0]["text"]


def test_every_line_number_a_fix_delta_surface_carries_is_one_the_head_diff_registers():
    for reviewed, head in _DELETION_CASES:
        registered = RD.diff_scope.parse_diff_lines(head)
        for file, entries in _deletion_surface(reviewed, head).items():
            for h in entries:
                assert h["start"] == h["end"] == 0 or {h["start"], h["end"]} <= registered[file], (file, h)


def test_verify_fold_at_cap_hands_back_round_cap():
    for resolution in (("a" * 40, None), (None, "fix-fold head: repo root unresolvable")):
        state = _verify_fold_state(maxRounds=2)
        state["round"] = 2
        state["rounds"] = {"2": {}}
        state["_verifyThen"] = RD.VERIFY_THEN_CAP
        RD._fold_verify(state, state["config"], {"result": "pass"}, resolution=resolution)
        assert state["terminal"] == "handed-back"
        assert state["step"] == RD.P_TERMINAL
        assert any(dec["kind"] == "round-cap" for dec in state["decisions"])


def test_verify_fold_legacy_position_unresolved_head_unknown_surface_hands_back():
    """Re-pinned: no continuation flag and no head: the delta round has no baseline, so its fix surface
    is unknown; the PR is handed back (`fix-surface-unknown`), never a panel over the head diff."""
    state = _verify_fold_state(repoRoot="/nonexistent-repo", baseRef="main")
    assert "_verifyThen" not in state
    RD._fold_verify(state, state["config"], {"result": "pass"},
                    resolution=(None, "fix-fold head: repo root unresolvable"))
    assert state["terminal"] == "handed-back"
    assert state["step"] != RD.P_PANEL
    assert state["decisions"][-1]["kind"] == "fix-surface-unknown"


def test_verify_head_lookup_persists_the_session_head(tmp_path):
    repo, head = _git_repo_with_head(tmp_path)
    persisted = "c" * 40
    cases = (
        ("plain", {}, [], head),
        ("fix-batch", {}, [{"file": "a.py"}], head),
        ("meta-persisted", {RD.FIX_FOLD_HEAD_KEY: persisted}, [], persisted),
    )
    for label, meta_over, batch, expected in cases:
        session_dir = _head_lookup_session(tmp_path / label, repo, **meta_over)
        meta_path = os.path.join(session_dir, RD.round_records.META_FILE)
        state = RD.new_state(_cfg())
        if batch:
            state["_fixBatch"] = batch
        resolved, error = RD._verified_head_at_fold(session_dir, state)
        assert (resolved, error) == (expected, None), label
        assert RD._session_certified_head(session_dir, state) == expected, label
        with open(meta_path, encoding="utf-8") as fh:
            assert json.load(fh)[RD.FIX_FOLD_HEAD_KEY] == expected, label


def test_verify_head_lookup_follows_a_moved_repo_head(tmp_path):
    repo, h1 = _git_repo_with_head(tmp_path)
    session_dir = _head_lookup_session(tmp_path, repo, **{RD.FIX_FOLD_HEAD_KEY: h1})
    subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "--allow-empty", "-q", "-m", "moved"], check=True)
    h2 = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], check=True,
                        capture_output=True, text=True).stdout.strip()
    assert h2 != h1
    state = RD.new_state(_cfg())
    state["_fixBatch"] = [{"file": "a.py"}]
    assert RD._verified_head_at_fold(session_dir, state) == (h2, None)
    assert RD._session_certified_head(session_dir, state) == h2
    with open(os.path.join(session_dir, RD.round_records.META_FILE), encoding="utf-8") as fh:
        assert json.load(fh)[RD.FIX_FOLD_HEAD_KEY] == h2


def test_verify_head_lookup_without_session_dir_resolves_nothing():
    state = RD.new_state(_cfg(headSha="a" * 40))
    config_before = json.dumps(state["config"], sort_keys=True)
    head, error = RD._verified_head_at_fold(None, state)
    assert head is None
    assert error
    assert json.dumps(state["config"], sort_keys=True) == config_before


def test_fixer_fold_still_persists_fix_fold_head(tmp_path):
    repo, head = _git_repo_with_head(tmp_path)
    session_dir = _head_lookup_session(tmp_path, repo)
    state = RD.new_state(_cfg())
    assert RD._resolve_fix_fold_head_sha(session_dir, state) == (head, None)
    assert state["config"][RD.FIX_FOLD_HEAD_KEY] == head
    with open(os.path.join(session_dir, RD.round_records.META_FILE), encoding="utf-8") as fh:
        assert json.load(fh)[RD.FIX_FOLD_HEAD_KEY] == head


def test_fixer_fold_records_refusal_when_head_unresolvable(tmp_path, monkeypatch):
    repo, _head = _git_repo_with_head(tmp_path)
    session_dir = _head_lookup_session(tmp_path, repo)
    state = RD.new_state(_cfg(repoRoot=repo))
    state["round"] = 1
    state["_fixBatch"] = [{"id": "F1", "file": "a.py", "line": 1, "severity": "Important"}]
    monkeypatch.setattr(RD.store_core, "run_git", lambda _repo_root, *_args, **_kwargs: None)
    RD._fold_apply_fixes(state, state["config"], {"fixes": [{"file": "a.py"}], "headDiff": "diff"},
                   session_dir=session_dir)
    assert "git rev-parse HEAD failed" in state["rounds"]["1"]["fixFoldHeadRefused"]
    assert "fixFoldHead" not in state["rounds"]["1"]


def test_cap_round_always_runs_the_verify_gate():
    state = RD.new_state(_cfg(maxRounds=2))
    state["round"] = 2
    state["rounds"] = {"2": {"verifyResult": "pass"}}
    RD._enter_post_fix(state, state["config"], session_dir=None)
    assert state["step"] == RD.P_VERIFY
    assert state["_verifyThen"] == RD.VERIFY_THEN_CAP
    assert not state.get("terminal")
    assert "ceilingGateReused" not in state["rounds"]["2"]


def test_verify_submit_with_unresolvable_head_is_not_refused(tmp_path):
    fixtures_dir = _HERE
    if fixtures_dir not in sys.path:
        sys.path.insert(0, fixtures_dir)
    from session_fixture_support import write_session

    not_a_repo = tmp_path / "not-git"
    not_a_repo.mkdir()
    state = RD.new_state({"fixerVendor": "claude", "baseGuard": RD.BASE_GUARD_CHECKED})
    state["round"] = 1
    state["step"] = RD.P_VERIFY
    state["pending"] = {"action": RD.P_VERIFY, "round": 1, "phase": RD.P_VERIFY, "attempt": 0,
                        "payload": {"command": "none"}}
    session_dir = write_session(
        tmp_path, name="verify", state=state, journal_lines=[],
        meta={"repoRoot": str(not_a_repo)})
    echo = RD.cmd_next(session_dir)
    assert echo["ok"], echo
    answer = RD.cmd_submit(session_dir, echo["phase"], echo["attempt"],
                           echo["expectedStateHash"], {"result": "pass"})
    assert answer["ok"] is True, answer
    assert answer.get("foldLanded") is True
    assert answer.get("reason") != "verified-head-unresolved"
    assert all(row.get("outcome") != "verified-head-unresolved"
               for row in RD.read_journal(session_dir))
    ok, loaded = RD.load_state(session_dir)
    assert ok and loaded["rounds"]["1"]["verifyResult"] == "pass"


def test_fixed_disposition_receipt_carries_only_the_fix_fold_head():
    head = "d" * 40
    state = RD.new_state(_cfg())
    state["rounds"] = {"1": {"verifyResult": "pass", "fixFoldHead": head}}
    assert RD._fixed_disposition_receipt(state, None, "k@L1") == {}
    state["config"][RD.FIX_FOLD_HEAD_KEY] = head
    assert RD._fixed_disposition_receipt(state, None, "k@L1") == {"headSha": head}
    state["config"][RD.FIX_FOLD_HEAD_KEY] = ""
    assert RD._fixed_disposition_receipt(state, None, "k@L1") == {}


# =============================================================================
# an unfilled seat is never dispatched; no maker's family audits a fix
# =============================================================================

UNFILLED_SEAT = {"vendor": None, "model": None, "effort": None, "tier": "deep", "family": None,
                 "source": "unfilled"}


def _integration():
    spec = importlib.util.spec_from_file_location(
        "test_round_driver_integration", os.path.join(_HERE, "test_round_driver_integration.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _map_with_unfilled(tdi, seat):
    seats = {dim: dict(entry) for dim, entry in tdi.SEAT_MAP["seats"].items()}
    seats[seat] = dict(UNFILLED_SEAT)
    return {"seats": seats}


def test_unfilled_seat_gets_no_order_a_missing_envelope_and_advance_completes(tmp_path):
    """E1: the panel's unfilled slot is not rendered, the driver records it missing (reason
    `unfilled`) itself, and `advance` folds the panel without `incomplete-roster`."""
    tdi = _integration()
    rd, rr = tdi.round_driver, tdi.round_records
    seat = rd.DIMENSIONS[1]
    session_dir, gitdir, head_path = tdi._bootstrap(tmp_path, seatMap=_map_with_unfilled(tdi, seat))
    state = tdi._state(session_dir)
    pend = state["pending"]
    manifest, err = rr.read_json(rd._orders_manifest_path(session_dir, 1, pend["phase"], 0))
    assert err is None
    assert seat not in manifest["seats"]
    assert sorted(manifest["seats"]) == sorted(
        rr.storage_key(d, 0) for d in rd.DIMENSIONS if d != seat)
    assert not os.path.exists(rr.order_prompt_path(
        session_dir, 1, pend["phase"], rr.storage_key(seat, 0), 0))
    stored, err = rr.read_json(rr.store_path(
        session_dir, 1, pend["phase"], rr.storage_key(seat, 0), 0))
    assert err is None
    assert stored["schema"] == rr.SEAT_MISSING_SCHEMA and stored["reason"] == "unfilled"
    assert stored["seat"] == seat and stored["vendor"] is None and stored["model"] is None
    ran = [d for d in rd.DIMENSIONS if d != seat]
    tdi._write_dispatch_manifest(session_dir, pend, [(d, 0) for d in ran], lambda _s: "claude")
    for dim in ran:
        tdi._land(session_dir, state, pend, dim,
                  tdi._payload_for(session_dir, state, pend, dim, [], head_path))
        assert tdi._record(session_dir, dim)["ok"] is True
    out = rd.cmd_advance(session_dir, git=tdi._fake_git(gitdir))
    assert out["ok"] is True, out
    after = tdi._state(session_dir)
    rec = after["rounds"]["1"]
    assert rec["seatStatus"][seat] == "missing"
    assert all(rec["seatStatus"][d] == "run" for d in ran)
    assert rec["missingSeats"] == [seat]


def test_hand_submitted_payload_for_an_unfilled_seat_is_folded_missing_and_not_credited(tmp_path):
    """E2: on the hand path a payload submitted for an unfilled seat is never credited, and the
    driver's own missing envelope for it does not trip the record/submit interleave fence."""
    d = str(tmp_path)
    seat, ran = RD.DIMENSIONS[1], RD.DIMENSIONS[0]
    seats = {dim: {"vendor": "claude", "model": "sonnet-5.5", "source": "default"}
             for dim in RD.DIMENSIONS}
    seats[seat] = dict(UNFILLED_SEAT)
    n = _first_next(d, _cfg(seatMap={"seats": seats}))
    finding = {"title": "ghost bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}
    art = {"seats": {dim: {"findings": [dict(finding)] if dim in (seat, ran) else []}
                     for dim in RD.DIMENSIONS}}
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
    assert out["ok"] is True, out
    ok, state = RD.load_state(d)
    assert ok
    rec = state["rounds"]["1"]
    assert rec["seatStatus"][seat] == "missing" and rec["seatStatus"][ran] == "run"
    assert rec["missingSeats"] == [seat]
    assert [f.get("dimension") for f in state["_toVerify"]] == [ran]


def test_fold_panel_never_credits_an_unfilled_seats_findings_when_no_receipt_is_stored():
    """E2, unit: `_fold_panel` reads the governing map off the artifact's own seat map."""
    state = RD.new_state(_cfg())
    seats = {dim: {"vendor": "claude", "model": "m", "source": "default"} for dim in RD.DIMENSIONS}
    seats["security-reviewer"] = dict(UNFILLED_SEAT)
    finding = {"title": "ghost bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}
    RD._fold_panel(state, state["config"], {
        "seats": {dim: {"findings": [dict(finding)]} for dim in RD.DIMENSIONS},
        "seatMap": {"seats": seats}})
    assert state["rounds"]["1"]["seatStatus"]["security-reviewer"] == "missing"
    assert state["rounds"]["1"]["missingSeats"] == ["security-reviewer"]
    assert "security-reviewer" not in {f.get("dimension") for f in state["_toVerify"]}
    assert state["fullPanelRan"] is False


def test_fold_panel_keeps_a_seeded_unfilled_seat_when_the_submitted_map_has_no_seats():
    """An incomplete submitted map (no `seats`) does not release a seat the seeded map left unfilled."""
    seats = {dim: {"vendor": "codex", "model": "m", "source": "default"} for dim in RD.DIMENSIONS}
    seats["code-reviewer"] = dict(UNFILLED_SEAT)
    state = RD.new_state(_cfg(seatMap={"seats": seats}))
    RD._fold_panel(state, state["config"], {
        "seats": {dim: {"findings": []} for dim in RD.DIMENSIONS},
        "seatMap": {"makerFamilies": ["anthropic"]}})
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "missing"
    assert state["fullPanelRan"] is False


def _fix_state(config):
    state = RD.new_state(config)
    state["fixBatch"] = [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1}]
    return state


def _pinned_map(vendor, **over):
    seats = {dim: {"vendor": vendor, "model": "m", "source": "pinned"} for dim in RD.DIMENSIONS}
    return {"seats": seats, **over}


def test_auditor_vendor_excludes_every_makers_family():
    """E5: fixer claude, vendors claude+codex, the map lists openai as a maker → no auditor."""
    cfg = {"vendors": ["claude", "codex"]}
    assert RD._auditor_vendor(cfg, "claude") == ("codex", "independent")
    assert RD._auditor_vendor(cfg, "claude", maker_families=frozenset({"openai"})) == (
        None, "unseatable")
    state = _fix_state(_cfg(seatMap=_pinned_map("claude", makerFamilies=["openai"])))
    targets = RD._audit_targets(state, state["config"], {})
    assert [t["independence"] for t in targets] == ["unseatable"]
    assert "auditorVendor" not in targets[0]
    assert state["independenceDegraded"] is True


def test_pinned_roster_restricts_the_auditor_to_the_pinned_vendors():
    """E6: every filled seat pinned to codex → codex audits; with codex not live, never cursor."""
    live = _fix_state(_cfg(vendors=["claude", "codex", "cursor"], seatMap=_pinned_map("codex")))
    assert RD._audit_targets(live, live["config"], {})[0]["auditorVendor"] == "codex"
    gone = _fix_state(_cfg(vendors=["claude", "cursor"], seatMap=_pinned_map("codex")))
    targets = RD._audit_targets(gone, gone["config"], {})
    assert "auditorVendor" not in targets[0] and targets[0]["independence"] == "unseatable"
    assert gone["independenceDegraded"] is True


def test_pinned_auditor_vendors_need_every_filled_seat_pinned():
    pinned = {"vendor": "codex", "source": "pinned"}
    assert RD_DISCLOSURES.pinned_auditor_vendors(
        {"seats": {"a": pinned, "b": dict(UNFILLED_SEAT)}}) == {"codex"}
    assert RD_DISCLOSURES.pinned_auditor_vendors(
        {"seats": {"a": pinned, "b": {"vendor": "claude", "source": "default"}}}) is None
    assert RD_DISCLOSURES.pinned_auditor_vendors({"seats": {"a": {"vendor": "codex"}}}) is None
    assert RD_DISCLOSURES.pinned_auditor_vendors({}) is None


def test_old_seat_map_without_maker_families_or_source_keeps_todays_selection():
    """E8: no `makerFamilies`, no `source` → the plain family rule, minus the removed fallback."""
    seats = {dim: {"vendor": "claude", "model": "m"} for dim in RD.DIMENSIONS}
    two = _fix_state(_cfg(seatMap={"seats": seats}))
    assert RD._audit_targets(two, two["config"], {})[0]["auditorVendor"] == "codex"
    one = _fix_state(_cfg(vendors=["claude"], seatMap={"seats": seats}))
    assert "auditorVendor" not in RD._audit_targets(one, one["config"], {})[0]
    assert RD_DISCLOSURES.maker_families({"seats": seats}) == frozenset()
    assert RD_DISCLOSURES.unfilled_seats({"seats": seats}) == frozenset()


def test_a_result_submitted_for_a_target_with_no_auditor_is_ignored_and_the_target_is_unaudited():
    """The fold treats a no-auditor target as an audit that did not run, whatever was submitted."""
    state = _fix_state(_cfg(vendors=["claude"]))
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tid = state["_auditTargets"][0]["id"]
    RD._fold_audits(state, state["config"], {"results": [
        {"id": tid, "ruling": "not-discharged", "reason": "looks fine to me", "auditorVendor": "claude",
         "checks": audit_checks()}]})
    outcome = state["_auditOutcome"]
    assert outcome["unaudited"] == [tid] and outcome["discharged"] == []
    assert outcome["notDischarged"] == [tid]
