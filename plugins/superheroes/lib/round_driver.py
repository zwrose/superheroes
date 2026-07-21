#!/usr/bin/env python3
"""The one-entrypoint review-loop round driver (#507).

CONTRACT. This module collapses the review-code auto-fix loop's per-round script choreography
(plan → dispatch → compile → verify → synthesis → gate → persist → fix → re-review) into ONE
deterministic entrypoint so the mandated path is the easiest path — ~6/24 corpus runs routed
AROUND the old scripts because the choreography was several separate invocations. It has two
layers over one core:

  - Layer 1 (`run_loop`): the ported control-flow of `review_panel_shell.js::reviewPanel` with
    every effectful step behind an injectable seam (`reviewer`, `synthesis`, `verifier`,
    `auditor`, `fix_step`, `verify_runner`, `io`). Same run-SHAPE, not the JS idioms.
  - Layer 2 (`next`/`submit` CLI): the state machine BETWEEN orchestrator dispatches — `next`
    emits the one action to run, `submit` folds its artifact and advances.

Like its decider siblings (audits / delta_surface / verification): DETERMINISTIC, stdlib-only,
FAIL-CLOSED. Junk in → conservative out + disclosure; never certify on silence; a wrong
`discharged`, a receipt-missing seat, a lost independence, an unknown surface all fail toward
MORE review, a park, or a disclosed downgrade — never toward a silent clean. The judgments live
in the pure deciders this module imports (`audits`, `verification`, `circuit_breaker`,
`review_round_policy`, `delta_surface`, `model_registry`); the driver only SEQUENCES them and
RECORDS what happened, and every terminal writes the driver receipt (`validate_receipt` guards
its shape). The confirmation economics (`review_round_policy.confirmation_followup` /
`is_cross_cutting`, MAX_CONFIRMATIONS=2), the reviewer re-dispatch budget
(`loop_plan_common.REDISPATCH_BUDGET` — the single home), and receipt validation
(`panel_tally._valid_final_receipt`, consumed bit-compatibly, never modified) are all reused,
not re-implemented.
"""
import argparse
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audits  # noqa: E402
import circuit_breaker  # noqa: E402
import delta_surface  # noqa: E402
import loop_plan_common  # noqa: E402
import model_registry  # noqa: E402
import panel_tally  # noqa: E402
import resolve_diff_lines  # noqa: E402
import review_round_policy  # noqa: E402
import verification  # noqa: E402
from finding_identity import finding_identity  # noqa: E402

# --- constants (the DIMENSIONS/AGENT_SUFFIX home, moved off the retired code_loop_plan) --------
# The code leg is the FIVE shared reviewers. `grounding-reviewer` is spec-leg-only (doc
# provenance) — deliberately absent here; test_dispatch_tables pins the per-leg subset.
DIMENSIONS = ["architecture-reviewer", "code-reviewer", "security-reviewer",
              "test-reviewer", "premortem-reviewer"]
AGENT_SUFFIX = {"architecture-reviewer": "architecture", "code-reviewer": "code",
                "security-reviewer": "security", "test-reviewer": "test",
                "premortem-reviewer": "premortem"}
# The cross-cutting lenses always get the WHOLE diff even when a big diff is sharded per-lens —
# architecture and failure-mode reasoning is non-local, so a shard would blind them.
CROSS_CUTTING_LENSES = ("architecture-reviewer", "premortem-reviewer")

DEEP = "reviewer-deep"
CHEAP = "reviewer"
# The reviewer re-dispatch budget rides through its single home (#350/#525): a receipt-missing /
# stale seat is re-dispatched at most this many times before it is recorded terminal `missing`
# with its findings carried as unverified. The code leg's read goes through the constant now.
REDISPATCH_BUDGET = loop_plan_common.REDISPATCH_BUDGET
MAX_CONFIRMATIONS = review_round_policy.MAX_CONFIRMATIONS

SCHEMA_VERSION = 2
STATE_FILE = "loop-state.json"
JOURNAL_FILE = "driver-journal.jsonl"
RECEIPT_FILE = "round-receipt.json"

# Phases (the `action` a `next` emits; each is fulfilled by exactly one orchestrator dispatch).
P_PANEL = "dispatch-panel"
P_VERIFIERS = "dispatch-verifiers"
P_SYNTHESIS = "dispatch-synthesis"
P_AUDITS = "dispatch-audits"
P_SCOPED = "dispatch-scoped-finder"
P_GAPSWEEP = "dispatch-gap-sweep"
P_VERIFY = "run-verify"
P_FIXER = "dispatch-fixer"
P_STALL = "present-stall-menu"
P_TERMINAL = "terminal"

# The four stall-menu choices (never "judge the dispute yourself"). accept-the-risk is offerable
# ONLY for a CONFIRMED-with-receipt finding; the menu payload gates it per-run.
STALL_CHOICES = ("ship-smaller", "spend-more", "accept-the-disclosed-risk", "hold")


# =============================================================================================
# canonical json + hashing + journal
# =============================================================================================

def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def state_hash(state):
    """sha256 over the canonical state JSON. Stable between a `next` (which persists the pending
    step) and the matching `submit`, so a stale/forked submit is caught by an echo mismatch."""
    return _sha256(_canonical(state))


def _journal_append(session_dir, entry):
    """Append one next/submit event to the journal — this is the `scriptRan` evidence. Best-effort
    (a journal miss never derails the run); ts via time.time (runtime code, not a Workflow script)."""
    entry = dict(entry)
    entry.setdefault("ts", time.time())
    try:
        with open(os.path.join(session_dir, JOURNAL_FILE), "a", encoding="utf-8") as fh:
            fh.write(_canonical(entry) + "\n")
    except OSError:
        pass


def read_journal(session_dir):
    out = []
    path = os.path.join(session_dir, JOURNAL_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def _scriptran_summary(session_dir):
    """The scriptRan evidence for the receipt: per-phase counts from the journal, plus the raw
    invocation total. A terminal with an empty journal is impossible on the mandated path — the
    summary is how the orchestrator's vet proves the driver actually ran."""
    counts = {}
    invocations = 0
    for e in read_journal(session_dir):
        invocations += 1
        key = "%s:%s" % (e.get("cmd"), e.get("phase"))
        counts[key] = counts.get(key, 0) + 1
    return {"invocations": invocations, "byPhase": counts}


# =============================================================================================
# mechanical compile (SKILL §4 steps 1-4 + 6 — deterministic, main-context)
# =============================================================================================

_NIT_CAP = 5


def _diff_scope_ok(finding, valid):
    """A finding is in diff scope iff its (file, line) is an anchorable RIGHT-side line of the
    round diff — the same hunk-walking `resolve_diff_lines.parse_diff_lines` uses. `valid` is None
    when no diff was supplied (scope check skipped)."""
    if valid is None:
        return True
    file_lines = valid.get(finding.get("file"))
    if not file_lines:
        return False
    return finding.get("line") in file_lines


def _nit_cap(findings):
    """After dedupe, keep at most 5 Nits; the overflow collapses to ONE summary entry so the
    readout isn't buried (the base rubric's severity cap)."""
    kept = []
    nits = []
    for f in findings:
        if isinstance(f, dict) and f.get("severity") == "Nit":
            nits.append(f)
        else:
            kept.append(f)
    if len(nits) <= _NIT_CAP:
        kept.extend(nits)
        return kept
    kept.extend(nits[:_NIT_CAP])
    overflow = len(nits) - _NIT_CAP
    kept.append({
        "title": "+ %d more Nits — see findings-*.json for details" % overflow,
        "severity": "Nit", "file": None, "line": None, "summaryEntry": True,
    })
    return kept


def mechanical_compile(findings, diff_text=None):
    """Port of SKILL §4 steps 1-4 + 6, deterministic and fail-closed:
      1. citation check — drop file/line-less findings;
      2. diff-scope check — drop findings whose (file,line) is not an anchor of the round diff;
      4. dedupe by identity (file::normalized-title) via panel_tally.compile_findings (higher
         severity wins, dimensions unioned — bit-compatible, panel_tally untouched);
      6. nit cap.
    Returns (compiled, drops) where each drop names WHY (never silently dropped)."""
    if not isinstance(findings, list):
        findings = []
    valid = resolve_diff_lines.parse_diff_lines(diff_text) if diff_text is not None else None
    kept, drops = [], []
    for f in findings:
        if not isinstance(f, dict):
            continue
        if f.get("file") is None or f.get("line") is None:
            drops.append({"file": f.get("file"), "title": f.get("title"),
                          "reason": "uncited — no file:line"})
            continue
        if not _diff_scope_ok(f, valid):
            drops.append({"file": f.get("file"), "line": f.get("line"),
                          "title": f.get("title"), "reason": "outside the round diff scope"})
            continue
        kept.append(f)
    compiled = panel_tally.compile_findings(kept)
    compiled = _nit_cap(compiled)
    return compiled, drops


# =============================================================================================
# author-justification POST-filter (#230-consistent NEW ordering: after merge_and_rank)
# =============================================================================================

_SUBSTANTIVE_MIN = 15


def _prior_justification(finding, prior_comments):
    """The substantive prior-author justification on this finding's (file,line), or None. A thread
    body under the length floor is not substantive (a bare '+1'/'wontfix' is not a justification)."""
    if not isinstance(prior_comments, list):
        return None
    for c in prior_comments:
        if not isinstance(c, dict):
            continue
        file = c.get("file") if c.get("file") is not None else c.get("path")
        if file != finding.get("file") or c.get("line") != finding.get("line"):
            continue
        body = c.get("body")
        if isinstance(body, str) and len(body.strip()) >= _SUBSTANTIVE_MIN:
            return body.strip()
    return None


def author_justification_filter(findings, prior_comments):
    """POST-filter (runs AFTER merge_and_rank, #230-consistent). May drop ONLY a finding whose
    verdict is present and != CONFIRMED, and only for a substantive prior justification, recording
    the justification quoted. A CONFIRMED finding with a prior justification SURVIVES, stamped
    `challenge: "author-justified"`. A finding with NO verdict is never dropped (silence never
    certifies a drop)."""
    if not isinstance(findings, list):
        return [], []
    kept, drops = [], []
    for f in findings:
        if not isinstance(f, dict):
            kept.append(f)
            continue
        just = _prior_justification(f, prior_comments)
        if not just:
            kept.append(f)
            continue
        verdict = f.get("verdict")
        if verdict == "CONFIRMED":
            g = dict(f)
            g["challenge"] = "author-justified"
            kept.append(g)
        elif verdict is None:
            # no verdict → never dropped (a finding that got no verdict this round must not be
            # certified away by a prior comment).
            kept.append(f)
        else:
            drops.append({"id": f.get("id"), "file": f.get("file"), "title": f.get("title"),
                          "reason": "author-justified (verdict %s, not CONFIRMED)" % verdict,
                          "justification": just})
    return kept, drops


# =============================================================================================
# independence + certification shape
# =============================================================================================

def _live_vendors(config):
    vendors = config.get("vendors") if isinstance(config, dict) else None
    if not isinstance(vendors, list) or not vendors:
        return ["claude"]
    return [v for v in vendors if isinstance(v, str) and v]


def _auditor_vendor(config, fixer_vendor):
    """The auditor of a fix is NEVER the fixer's vendor. When only one vendor is live (cloud
    sandbox) the audit still RUNS but is stamped degraded — never silently counted as independent."""
    live = _live_vendors(config)
    others = [v for v in live if v != fixer_vendor]
    if others:
        return others[0], "independent"
    # single vendor live: audit runs, independence degraded (the lost independence is named).
    return (live[0] if live else fixer_vendor), "degraded"


def _degraded(state):
    return bool(state.get("independenceDegraded"))


def _cert_shape(state, base):
    return base + "-degraded" if _degraded(state) else base


# =============================================================================================
# state lifecycle
# =============================================================================================

def _default_config(overrides=None):
    cfg = {
        "leg": "code",
        "panel": False,
        "code": True,
        "docMode": False,
        "vendors": ["claude"],
        "fixerVendor": "claude",
        "verifyCommand": "none",
        "maxRounds": 7,
        "dimensions": list(DIMENSIONS),
    }
    if isinstance(overrides, dict):
        cfg.update({k: v for k, v in overrides.items() if v is not None})
    cfg["panel"] = cfg.get("leg") == "panel"
    cfg["code"] = cfg.get("leg") != "panel"
    if not isinstance(cfg.get("dimensions"), list) or not cfg["dimensions"]:
        cfg["dimensions"] = list(DIMENSIONS)
    return cfg


def new_state(config=None):
    cfg = _default_config(config)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "config": cfg,
        "round": 1,
        "step": P_PANEL,
        "pending": None,
        "lastAccepted": None,
        "rounds": {},
        "findings": [],
        "decisions": [],
        "auditRounds": [],
        "confirmations": 0,
        "selfRecovered": False,
        "independenceDegraded": len(_live_vendors(cfg)) < 2,
        "seatMap": {},
        "reviewedDiff": cfg.get("diff"),
        "headDiff": None,
        "fixBatch": [],
        "fullPanelRan": False,
        "terminal": None,
        "certification": None,
    }


def load_state(session_dir):
    """(ok, state_or_reason). A missing file → (True, None) fresh. A v1 file is REFUSED — session
    dirs are per-invocation, there is no migration; the caller must start fresh."""
    path = os.path.join(session_dir, STATE_FILE)
    if not os.path.exists(path):
        return True, None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False, "loop-state.json is unreadable — start a fresh session dir"
    if not isinstance(data, dict) or data.get("schemaVersion") != SCHEMA_VERSION:
        return False, ("loop-state.json is schemaVersion %r, not %d — session dirs are "
                       "per-invocation with no migration; start a fresh session dir"
                       % (data.get("schemaVersion") if isinstance(data, dict) else None,
                          SCHEMA_VERSION))
    return True, data


def save_state(session_dir, state):
    path = os.path.join(session_dir, STATE_FILE)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(_canonical(state))
    os.replace(tmp, path)


# =============================================================================================
# the round flow — planner + fold (shared by run_loop and the CLI)
# =============================================================================================

def _blocking(findings):
    return [f for f in findings if isinstance(f, dict)
            and circuit_breaker.is_blocking(f.get("severity"))]


def _open_critical(findings):
    return [f for f in findings if isinstance(f, dict)
            and circuit_breaker.is_critical(f.get("severity"))]


def _shard_payload(diff_text, dimensions):
    """The panel dispatch payload: dims + tiers, and — when shard_plan says big — per-lens shards.
    The cross-cutting lenses always carry the whole diff."""
    plan = delta_surface.shard_plan(diff_text or "")
    tier = DEEP  # round 1 / full panels are always reviewer-deep
    payload = {"dimensions": list(dimensions), "tier": tier, "big": bool(plan.get("big"))}
    if plan.get("big"):
        lens_shards = {}
        for d in dimensions:
            if d in CROSS_CUTTING_LENSES:
                lens_shards[d] = {"wholeDiff": True}
            else:
                lens_shards[d] = {"shards": plan.get("shards", [])}
        payload["shards"] = lens_shards
    return payload


def _panel_dimensions(config):
    dims = config.get("dimensions")
    return list(dims) if isinstance(dims, list) and dims else list(DIMENSIONS)


def _advance(state, config):
    """Given the state, return the next step to dispatch (or the terminal). Pure read — never
    mutates. `next` and run_loop both call this."""
    if state.get("terminal"):
        return {"action": P_TERMINAL, "round": state["round"], "phase": P_TERMINAL,
                "payload": {"verdict": state["terminal"], "certification": state.get("certification")}}
    step = state["step"]
    rnd = state["round"]
    payload = {}
    dims = _panel_dimensions(config)
    if step == P_PANEL:
        payload = _shard_payload(state.get("reviewedDiff"), dims)
    elif step == P_VERIFIERS:
        staged = verification.stage_ids(state.get("_toVerify") or [])
        payload = {"clusters": verification.cluster_findings(staged)}
    elif step == P_SYNTHESIS:
        payload = {"findings": state.get("_verified") or []}
    elif step == P_GAPSWEEP:
        payload = {"verifiedFindings": state.get("findings") or [],
                   "fullDiff": True}
    elif step == P_AUDITS:
        payload = {"targets": state.get("_auditTargets") or []}
    elif step == P_SCOPED:
        payload = {"hunks": state.get("_newSurface") or {}, "tier": DEEP}
    elif step == P_VERIFY:
        payload = {"command": config.get("verifyCommand", "none")}
    elif step == P_FIXER:
        payload = {"batch": state.get("_fixBatch") or []}
        if state.get("_escalatedRung"):
            payload["escalatedRung"] = state["_escalatedRung"]
    elif step == P_STALL:
        payload = {"choices": list(state.get("_stallChoices") or STALL_CHOICES),
                   "acceptRiskEligible": bool(state.get("_acceptRiskEligible"))}
    return {"action": step, "round": rnd, "phase": step, "payload": payload}


def _record_round(state, key, value):
    rec = state["rounds"].setdefault(str(state["round"]), {})
    rec[key] = value


def _decision(state, kind, detail):
    state["decisions"].append({"round": state["round"], "kind": kind, "detail": detail})


def _fold(state, config, phase, artifact):
    """Fold one submitted artifact and advance state. Big switch on phase; each arm delegates the
    JUDGMENT to a pure decider and only records/sequences here. Returns the mutated state."""
    artifact = artifact if isinstance(artifact, dict) else {}
    if phase == P_PANEL:
        _fold_panel(state, config, artifact)
    elif phase == P_VERIFIERS:
        _fold_verifiers(state, config, artifact)
    elif phase == P_SYNTHESIS:
        _fold_synthesis(state, config, artifact)
    elif phase == P_GAPSWEEP:
        _fold_gapsweep(state, config, artifact)
    elif phase == P_AUDITS:
        _fold_audits(state, config, artifact)
    elif phase == P_SCOPED:
        _fold_scoped(state, config, artifact)
    elif phase == P_VERIFY:
        _fold_verify(state, config, artifact)
    elif phase == P_FIXER:
        _fold_fixer(state, config, artifact)
    elif phase == P_STALL:
        _fold_stall(state, config, artifact)
    return state


# ---- round-1 / full-panel legs --------------------------------------------------------------

def _fold_panel(state, config, artifact):
    """Fold a full reviewer-deep panel. `artifact` maps dimension → {findings, receiptMissing?,
    receiptStale?}. A persistently receipt-missing/stale seat is terminal `missing` (shell
    :823-827 parity) but its findings ride the round record as UNVERIFIED/provisional — surfaced,
    never silently dropped (coordination note 2)."""
    seats = artifact.get("seats") if isinstance(artifact.get("seats"), dict) else artifact
    seat_map = artifact.get("seatMap") if isinstance(artifact.get("seatMap"), dict) else {}
    if seat_map:
        state["seatMap"].update(seat_map)
    # A full reviewer-deep panel that runs in a DELTA round (round ≥ 2) is a qualifying
    # confirmation panel: it consumes one of the two-panel budget and resets the surfaced-since
    # tracker (the #174 bar — a qualifying panel is a fresh full deep round).
    if state["round"] >= 2:
        state["confirmations"] = state.get("confirmations", 0) + 1
        state["surfacedSinceLastPanel"] = []
    raw = []
    seat_status = {}
    unverified = []
    for dim in _panel_dimensions(config):
        seat = seats.get(dim) if isinstance(seats, dict) else None
        findings = []
        status = "run"
        if isinstance(seat, dict):
            findings = seat.get("findings") or []
            if seat.get("receiptMissing") or seat.get("receiptStale"):
                status = "missing"
        elif isinstance(seat, list):
            findings = seat
        seat_status[dim] = status
        for f in findings:
            if not isinstance(f, dict):
                continue
            g = dict(f)
            g.setdefault("dimension", dim)
            if status == "missing":
                g["unverified"] = True
                unverified.append({"dimension": dim, "title": g.get("title"),
                                   "file": g.get("file"), "line": g.get("line")})
            raw.append(g)
    compiled, drops = mechanical_compile(raw, state.get("reviewedDiff"))
    _record_round(state, "seatStatus", seat_status)
    _record_round(state, "compileDrops", drops)
    if unverified:
        _record_round(state, "unverified", unverified)
        _decision(state, "receipt-missing-seat",
                  "%d finding(s) carried unverified from receipt-missing seat(s)" % len(unverified))
    state["fullPanelRan"] = True
    state["_toVerify"] = compiled
    state["step"] = P_VERIFIERS


def _fold_verifiers(state, config, artifact):
    """Apply per-finding verification verdicts deterministically (verification.apply_verdicts)."""
    verdicts = artifact.get("verdicts") if isinstance(artifact.get("verdicts"), list) else []
    staged = verification.stage_ids(state.get("_toVerify") or [])
    applied = verification.apply_verdicts(staged, verdicts)
    state["_verified"] = applied["findings"]
    _record_round(state, "verify", {"drops": applied["drops"], "downgrades": applied["downgrades"],
                                    "unverified": applied["unverified"], "ambiguous": applied["ambiguous"]})
    for d in applied["drops"]:
        _decision(state, "verifier-refuted", d.get("reason"))
    # round-1 findings and delta scoped candidates both route to synthesis; the delta settle is
    # armed on the delta path (see _fold_scoped) so _after_findings_settled re-settles the delta.
    state["step"] = P_SYNTHESIS


def _fold_synthesis(state, config, artifact):
    """Merge same-root-cause survivors (verification.merge_and_rank, coverage-guaranteed), then the
    author-justification POST-filter, then decide gap-sweep / fix / terminal."""
    grouping = artifact.get("grouping") if isinstance(artifact.get("grouping"), list) else None
    merged = verification.merge_and_rank(state.get("_verified") or [], grouping)
    findings = merged["findings"]
    kept, aj_drops = author_justification_filter(findings, config.get("priorComments"))
    for d in aj_drops:
        _decision(state, "author-justified-drop", d.get("justification"))
    _record_round(state, "authorJustifiedDrops", aj_drops)
    _record_round(state, "merges", merged["merges"])
    state["findings"] = kept
    # big diff → a gap-sweep over verified findings + the whole diff, before the fix leg. (Not on
    # a delta settle — the delta round has its own scoped scan + audit breaker.)
    plan = delta_surface.shard_plan(state.get("reviewedDiff") or "")
    if plan.get("big") and not state.get("_settleDelta") \
            and not state.get("_gapSweptRound") == state["round"]:
        state["_gapSweptRound"] = state["round"]
        state["step"] = P_GAPSWEEP
        return
    _after_findings_settled(state, config)


def _fold_gapsweep(state, config, artifact):
    """Big-diff gap sweep: candidate findings from the full-diff pass fold through the same
    stage/cluster/verify path, then re-settle."""
    candidates = artifact.get("findings") if isinstance(artifact.get("findings"), list) else []
    compiled, _drops = mechanical_compile(candidates, state.get("reviewedDiff"))
    if compiled:
        # route candidates through verification like any other findings.
        state["_toVerify"] = compiled
        state["_gapMerge"] = True
        state["step"] = P_VERIFIERS
        # after verifiers → synthesis will merge with the already-settled findings.
        state["_verifiedCarry"] = state.get("findings") or []
        return
    _after_findings_settled(state, config)


def _after_findings_settled(state, config):
    """After the round's findings are verified + merged + justification-filtered: route to the fix
    leg when there is a blocking finding, else to the terminal decision (round 1 clean = certify)."""
    # merge any gap-sweep carry back in.
    if state.get("_verifiedCarry") is not None:
        carry = state.pop("_verifiedCarry")
        state["findings"] = (carry or []) + (state.get("findings") or [])
        state.pop("_gapMerge", None)
    blocking = _blocking(state.get("findings") or [])
    _record_round(state, "blockingCount", len(blocking))
    if blocking:
        state["_fixBatch"] = [dict(f) for f in blocking]
        state["step"] = P_FIXER
    else:
        _terminal_converged(state, config, full_panel=state.get("fullPanelRan"))


# ---- fix + verify legs ----------------------------------------------------------------------

def _fold_fixer(state, config, artifact):
    """Record the fixer's result; the fix-batch COMPOSITION stays orchestrator-side (the artifact),
    the driver sequences + records. The post-fix head diff + changed subjects ride the artifact so
    the next delta round can split_fix_surface against git, never the fixer's self-report."""
    state["fixBatch"] = state.get("_fixBatch") or []
    state["headDiff"] = artifact.get("headDiff")
    state["_changedSubjects"] = artifact.get("changedSubjects")
    _record_round(state, "fix", {"fixes": artifact.get("fixes") or [],
                                 "escalated": bool(artifact.get("escalated") or state.get("_escalatedRung"))})
    state.pop("_escalatedRung", None)
    state["step"] = P_VERIFY


def _fold_verify(state, config, artifact):
    """Fold the verify result. A fail halts (verify-gate fail = halt as today). A pass advances to
    the next round — a DELTA round (the new normal)."""
    result = artifact.get("result")
    _record_round(state, "verifyResult", result)
    if result == "fail":
        state["terminal"] = "halted"
        state["certification"] = {"shape": None, "reason": "verify gate failed"}
        _decision(state, "verify-fail", "verify gate failed — halt, certification withheld")
        state["step"] = P_TERMINAL
        return
    # advance to the next (delta) round. The diff the just-finished round's panel/audit saw is the
    # `reviewed` side of the next split_fix_surface; the fixer's head diff is the `head` side.
    state["_priorReviewedDiff"] = state.get("reviewedDiff")
    state["round"] += 1
    state["reviewedDiff"] = state.get("headDiff") or state.get("reviewedDiff")
    _enter_delta_round(state, config)


# ---- delta rounds (2+) ----------------------------------------------------------------------

def _enter_delta_round(state, config):
    """Rounds 2+: split_fix_surface(reviewed, head, fixBatch). unknown → schedule a FULL panel
    (the existing unknown→run-everything rule). Else audit the fixed findings + scoped-find the new
    surface."""
    split = delta_surface.split_fix_surface(
        state.get("_priorReviewedDiff") or state.get("reviewedDiff"),
        state.get("headDiff"), state.get("fixBatch") or [])
    if split.get("unknown"):
        _decision(state, "unknown-surface", "delta surface unknown — full reviewer-deep panel")
        _record_round(state, "roundKind", "full-panel-unknown-surface")
        state["fullPanelRan"] = False
        state["step"] = P_PANEL
        return
    # a delta (scoped) round is NOT a full panel — reset the flag so a scoped certifying finish is
    # `audited-chain`, not `full-panel-confirmed`. A re-armed confirmation panel re-sets it True.
    state["fullPanelRan"] = False
    state["_auditTargets"] = _audit_targets(state, config, split.get("auditTargets") or {})
    state["_newSurface"] = split.get("newSurface") or {}
    _record_round(state, "roundKind", "delta")
    state["step"] = P_AUDITS


def _audit_targets(state, config, audit_targets_map):
    """Location-grouped audit targets, each carrying the fixer's vendor so the orchestrator seats a
    DIFFERENT auditor vendor. Grounded in the fix batch (the fixed findings), attributed to the
    hunks that sit over their lines."""
    fixer_vendor = config.get("fixerVendor", "claude")
    auditor_vendor, independence = _auditor_vendor(config, fixer_vendor)
    if independence == "degraded":
        state["independenceDegraded"] = True
    targets = []
    for f in state.get("fixBatch") or []:
        if not isinstance(f, dict):
            continue
        targets.append({
            "id": finding_identity(f),
            "file": f.get("file"), "line": f.get("line"), "title": f.get("title"),
            "severity": f.get("severity"),
            "fixerVendor": fixer_vendor,
            "auditorVendor": auditor_vendor,
            "independence": independence,
        })
    return targets


def _fold_audits(state, config, artifact):
    """Consume the fix-audit rulings deterministically (audits.apply_audit_results). Record the
    audit round for the audit-keyed breaker; new-issue candidates join the scoped-finder scan."""
    results = artifact.get("results") if isinstance(artifact.get("results"), list) else []
    targets = state.get("_auditTargets") or []
    outcome = audits.apply_audit_results(targets, results)
    state["_auditOutcome"] = outcome
    # the audit round for check_audit_breaker: identity + effective ruling.
    audit_round = {"round": state["round"], "outcomes": [
        {"identity": a.get("id"), "ruling": a.get("ruling")} for a in outcome["audits"]]}
    state["auditRounds"].append(audit_round)
    _record_round(state, "audits", outcome["audits"])
    _record_round(state, "auditIndependence",
                  targets[0]["independence"] if targets else "n/a")
    state["_newIssues"] = outcome["newIssues"]
    for aid in outcome["notDischarged"]:
        _decision(state, "not-discharged", aid)
    state["step"] = P_SCOPED


def _fold_scoped(state, config, artifact):
    """Fold the scoped new-finding scan over the fix's new surface; its candidates + the audits'
    new-issue candidates route through the same stage/cluster/verify fold."""
    candidates = artifact.get("findings") if isinstance(artifact.get("findings"), list) else []
    new_issues = state.get("_newIssues") or []
    combined = list(candidates) + [ni for ni in new_issues if isinstance(ni, dict)]
    compiled, _drops = mechanical_compile(combined, state.get("reviewedDiff"))
    state["_postAudit"] = True
    if compiled:
        state["_toVerify"] = compiled
        state["step"] = P_VERIFIERS
        # after verify+synthesis, _after_findings_settled runs; but for delta rounds we need the
        # audit-breaker + confirmation re-arm, handled in _settle_delta.
        state["_settleDelta"] = True
        return
    state["findings"] = []
    _settle_delta(state, config)


def _settle_delta(state, config):
    """Delta-round terminal logic: audit-keyed breaker → self-recovery → stall menu; open-work →
    fix leg; else the converged decision (with the #174 confirmation re-arm)."""
    state.pop("_settleDelta", None)
    state.pop("_postAudit", None)
    outcome = state.get("_auditOutcome") or {"notDischarged": [], "discharged": []}
    max_rounds = config.get("maxRounds", 7)
    breaker = circuit_breaker.check_audit_breaker(state["auditRounds"], max_rounds)
    new_blocking = _blocking(state.get("findings") or [])

    # track the severities surfaced THIS delta round since the last qualifying panel (for the #174
    # re-arm). Derived from the compiled findings, never the fixer's self-report.
    if new_blocking:
        state.setdefault("surfacedSinceLastPanel", []).extend(
            "Critical" if circuit_breaker.is_critical(f.get("severity")) else "Important"
            for f in new_blocking)
    for aid in outcome.get("notDischarged", []):
        if _batch_severity_is_critical(state, aid):
            state.setdefault("surfacedSinceLastPanel", []).append("Critical")

    if breaker.get("halt") and breaker.get("reason") == "audit-stall":
        _handle_stall(state, config, breaker)
        return
    if breaker.get("halt") and breaker.get("reason") == "max-iterations":
        crit = _open_critical(state.get("findings") or []) or _stalled_critical(state, config, breaker)
        if crit:
            _park_capped(state, breaker.get("detail"))
            return
        _terminal_converged(state, config, full_panel=False, note=breaker.get("detail"))
        return

    # a scoped-finder / new-issue blocking finding OR a not-discharged audit means the round still
    # has work — fix it. A not-discharged fix batch is rebuilt from the audit TARGETS (which carry
    # file/line/severity) so the next round's split_fix_surface can re-derive its surface.
    if bool(outcome.get("notDischarged")) or bool(new_blocking):
        if new_blocking:
            state["_fixBatch"] = [dict(f) for f in new_blocking]
        else:
            nd = set(outcome.get("notDischarged", []))
            state["_fixBatch"] = [dict(t) for t in (state.get("_auditTargets") or [])
                                  if t.get("id") in nd]
        state["step"] = P_FIXER
        return

    # converged candidate: last round's fixes all discharged + verify pass. Apply the #174
    # confirmation economics before certifying — a Critical surfaced since the last qualifying
    # panel, or cross-cutting rework, owes one more full confirmation panel (budget 2).
    surfaced = list(state.get("surfacedSinceLastPanel") or [])
    cross = review_round_policy.is_cross_cutting(state.get("_changedSubjects"))
    followup = review_round_policy.confirmation_followup(
        surfaced, state.get("confirmations", 0), cross,
        max_confirmations=MAX_CONFIRMATIONS, doc_mode=config.get("docMode", False))
    _record_round(state, "confirmationFollowup", followup)
    if followup.get("park"):
        _park_capped(state, followup.get("reason"))
        return
    if followup.get("rearm"):
        _decision(state, "confirmation-rearm", followup.get("reason"))
        state["round"] += 1
        state["fullPanelRan"] = False
        _record_round(state, "roundKind", "confirmation")
        state["reviewedDiff"] = state.get("headDiff") or state.get("reviewedDiff")
        state["step"] = P_PANEL
        return
    _terminal_converged(state, config, full_panel=state.get("fullPanelRan"))


def _batch_severity_is_critical(state, ident):
    for f in state.get("fixBatch") or []:
        if isinstance(f, dict) and finding_identity(f) == ident \
                and circuit_breaker.is_critical(f.get("severity")):
            return True
    return False


def _park_capped(state, detail):
    state["terminal"] = "capped-with-open-critical"
    state["certification"] = {"shape": None, "reason": detail or "capped with an open Critical — park"}
    _decision(state, "capped-with-open-critical", detail)
    state["step"] = P_TERMINAL


def _stalled_critical(state, config, breaker):
    """A stalled identity whose fix batch carried a Critical still counts as an open Critical at the
    cap (fail toward park)."""
    stalled = set(breaker.get("stalledIdentities") or [])
    for f in state.get("fixBatch") or []:
        if isinstance(f, dict) and circuit_breaker.is_critical(f.get("severity")) \
                and finding_identity(f) in stalled:
            return [f]
    return []


# ---- stall self-recovery + menu -------------------------------------------------------------

def _handle_stall(state, config, breaker):
    """audit-stall → ONE invisible self-recovery (fixer re-dispatched one rung up via
    model_registry.escalate and/or another vendor, once, journaled). Still stalled → the stall
    menu."""
    if not state.get("selfRecovered"):
        state["selfRecovered"] = True
        fixer_vendor = config.get("fixerVendor", "claude")
        rung = model_registry.escalate(
            fixer_vendor, config.get("fixerModel", "sonnet-5"), config.get("fixerEffort", "high"))
        state["_escalatedRung"] = {"rung": rung, "vendor": fixer_vendor}
        _decision(state, "self-recovery",
                  "audit-stall — one invisible self-recovery (fixer escalated to %r)" % (rung,))
        _record_round(state, "selfRecovery", {"rung": rung, "reason": breaker.get("detail")})
        stalled = set(breaker.get("stalledIdentities") or [])
        batch = [dict(t) for t in (state.get("_auditTargets") or []) if t.get("id") in stalled]
        state["_fixBatch"] = batch or [dict(f) for f in (state.get("fixBatch") or [])]
        state["step"] = P_FIXER
        return
    # already self-recovered and still stalled → present the stall menu (never judge the dispute).
    accept_eligible = _accept_risk_eligible(state)
    choices = list(STALL_CHOICES) if accept_eligible else \
        [c for c in STALL_CHOICES if c != "accept-the-disclosed-risk"]
    state["_stallChoices"] = choices
    state["_acceptRiskEligible"] = accept_eligible
    _decision(state, "stall-menu", "audit-stall persists after self-recovery — owner choice")
    state["step"] = P_STALL


def _accept_risk_eligible(state):
    """accept-the-disclosed-risk is offerable ONLY when the stalled finding is CONFIRMED with a
    receipt (an owner may knowingly accept a proven, disclosed risk — never an unproven one)."""
    for f in state.get("findings") or []:
        if isinstance(f, dict) and f.get("verdict") == "CONFIRMED" and f.get("evidence"):
            return True
    return False


def _fold_stall(state, config, artifact):
    """Fold the owner's stall choice; journal it. hold → park; the others record the disposition and
    terminate accordingly."""
    choice = artifact.get("choice")
    _record_round(state, "stallChoice", choice)
    _decision(state, "stall-choice", choice)
    if choice == "hold":
        state["terminal"] = "held"
        state["certification"] = {"shape": None, "reason": "owner chose to hold"}
    elif choice == "accept-the-disclosed-risk" and state.get("_acceptRiskEligible"):
        _terminal_converged(state, config, full_panel=False,
                            note="owner accepted the disclosed (CONFIRMED) risk")
        return
    elif choice in ("ship-smaller", "spend-more"):
        state["terminal"] = "stalled"
        state["certification"] = {"shape": None,
                                  "reason": "owner chose %s — certification withheld" % choice}
    else:
        # an ineligible accept-the-risk or an unknown choice fails closed to a park.
        state["terminal"] = "stalled"
        state["certification"] = {"shape": None,
                                  "reason": "stall unresolved — certification withheld"}
    state["step"] = P_TERMINAL


# ---- terminal certification -----------------------------------------------------------------

def _terminal_converged(state, config, full_panel, note=None):
    """Certify: last round's fixes all discharged + verify pass. Shape is full-panel-confirmed (a
    qualifying full confirmation panel ran) or audited-chain (scoped certifying finish, no final
    full panel — say so). Degraded independence appends -degraded."""
    base = "full-panel-confirmed" if full_panel else "audited-chain"
    shape = _cert_shape(state, base)
    state["terminal"] = "converged"
    cert = {"shape": shape, "fullPanel": bool(full_panel),
            "independence": "degraded" if _degraded(state) else "independent"}
    if note:
        cert["note"] = note
    state["certification"] = cert
    _decision(state, "converged", "certified as %s" % shape)
    state["step"] = P_TERMINAL


# =============================================================================================
# the driver receipt + its validator
# =============================================================================================

def build_receipt(state, session_dir=None):
    """The terminal driver receipt. Per-round schedule (planned vs executed), every finding's
    outcome, the decision ledger, the seat map, the scriptRan summary from the journal, and the
    degraded disclosures. Written to round-receipt.json at the terminal."""
    rounds = []
    for key in sorted(state.get("rounds") or {}, key=lambda k: int(k) if str(k).isdigit() else 0):
        rec = state["rounds"][key]
        rounds.append({"round": int(key) if str(key).isdigit() else key,
                       "kind": rec.get("roundKind"),
                       "seatStatus": rec.get("seatStatus"),
                       "blockingCount": rec.get("blockingCount"),
                       "verifyResult": rec.get("verifyResult"),
                       "audits": rec.get("audits"),
                       "unverified": rec.get("unverified"),
                       "authorJustifiedDrops": rec.get("authorJustifiedDrops"),
                       "compileDrops": rec.get("compileDrops"),
                       "selfRecovery": rec.get("selfRecovery"),
                       "stallChoice": rec.get("stallChoice")})
    findings = [{"id": f.get("id"), "file": f.get("file"), "line": f.get("line"),
                 "title": f.get("title"), "severity": f.get("severity"),
                 "verdict": f.get("verdict"), "challenge": f.get("challenge"),
                 "unverified": f.get("unverified")}
                for f in (state.get("findings") or []) if isinstance(f, dict)]
    degraded = []
    if _degraded(state):
        degraded.append("independence: a single live vendor — the fix's auditor is the fixer's "
                        "vendor; independence degraded and named in the certification shape")
    scriptran = _scriptran_summary(session_dir) if session_dir else state.get("_scriptRan") or \
        {"invocations": 0, "byPhase": {}}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "verdict": state.get("terminal"),
        "certificationShape": (state.get("certification") or {}).get("shape"),
        "certification": state.get("certification"),
        "rounds": rounds,
        "findings": findings,
        "decisions": list(state.get("decisions") or []),
        "seatMap": dict(state.get("seatMap") or {}),
        "scriptRan": scriptran,
        "degraded": degraded,
    }


_RECEIPT_REQUIRED = ("schemaVersion", "verdict", "certificationShape", "rounds", "findings",
                     "decisions", "seatMap", "scriptRan", "degraded")


def validate_receipt(receipt):
    """Validate a driver receipt's SHAPE (NOT grafted onto panel_tally._valid_final_receipt — that
    is the reviewer-seat receipt; this is the loop's terminal receipt). Fail-closed: a receipt
    missing scriptRan or the seat map, or with a non-list rounds/findings/decisions/degraded, is
    rejected with a reason. Returns (ok, reason)."""
    if not isinstance(receipt, dict):
        return False, "receipt is not an object"
    for key in _RECEIPT_REQUIRED:
        if key not in receipt:
            return False, "receipt missing required key %r" % key
    if receipt.get("schemaVersion") != SCHEMA_VERSION:
        return False, "receipt schemaVersion must be %d" % SCHEMA_VERSION
    if not isinstance(receipt.get("scriptRan"), dict):
        return False, "receipt scriptRan must be an object (the journal-derived evidence)"
    if "byPhase" not in receipt["scriptRan"]:
        return False, "receipt scriptRan must carry byPhase (the per-phase journal counts)"
    if not isinstance(receipt.get("seatMap"), dict):
        return False, "receipt seatMap must be an object"
    for key in ("rounds", "findings", "decisions", "degraded"):
        if not isinstance(receipt.get(key), list):
            return False, "receipt %s must be a list" % key
    if not receipt.get("verdict"):
        return False, "receipt verdict is empty"
    return True, None


# =============================================================================================
# Layer 1 — library loop
# =============================================================================================

_RUN_LOOP_GUARD = 200


def _reviewer_findings(result):
    """Normalize a reviewer-seam return into a findings list.

    Panel seats return a full seat dict ``{findings, confidence, verificationReceipt, ...}``
    (the JS ``reviewerAgent`` shape). Scoped-finder / gap-sweep reuse the same seam; unwrap
    the dict so ``_fold_scoped`` / ``_fold_gapsweep`` see a list — a bare list remains valid
    (the library tests' compact form)."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        findings = result.get("findings")
        return findings if isinstance(findings, list) else []
    return []


def _run_seam(seams, action, payload, state, config):
    """Call the seam for one action and return its artifact in the shape `_fold` expects. Seams are
    injectable; a missing seam is a hard fail (the loop cannot proceed without the effect)."""
    io = seams.get("io") or {}
    if action == P_PANEL:
        seats = {}
        for dim in _panel_dimensions(config):
            tier = payload.get("tier", DEEP)
            result = seams["reviewer"](dim, tier, state["round"], payload)
            # bounded re-dispatch on a receipt-missing/stale seat (REDISPATCH_BUDGET), then missing.
            attempts = 0
            while attempts < REDISPATCH_BUDGET and isinstance(result, dict) \
                    and (result.get("receiptMissing") or result.get("receiptStale")):
                attempts += 1
                result = seams["reviewer"](dim, tier, state["round"], payload)
            seats[dim] = result
        return {"seats": seats, "seatMap": io.get("seatMap") if isinstance(io, dict) else {}}
    if action == P_VERIFIERS:
        return {"verdicts": seams["verifier"](payload.get("clusters"), state["round"])}
    if action == P_SYNTHESIS:
        return {"grouping": seams["synthesis"](payload.get("findings"), state["round"])}
    if action == P_GAPSWEEP:
        return {"findings": _reviewer_findings(
            seams["reviewer"]("gap-sweep", DEEP, state["round"], payload))}
    if action == P_AUDITS:
        return {"results": seams["auditor"](payload.get("targets"), state["round"])}
    if action == P_SCOPED:
        return {"findings": _reviewer_findings(
            seams["reviewer"]("scoped-finder", DEEP, state["round"], payload))}
    if action == P_VERIFY:
        return {"result": seams["verify_runner"](payload.get("command"), state["round"])}
    if action == P_FIXER:
        return seams["fix_step"](payload.get("batch"), state["round"], payload)
    if action == P_STALL:
        menu = io.get("stall_menu") if isinstance(io, dict) else None
        return {"choice": menu(payload) if callable(menu) else "hold"}
    return {}


def run_loop(seams, config=None):
    """Layer 1: drive the whole loop end-to-end with scripted seams. Ports the run-SHAPE of
    review_panel_shell.reviewPanel. Returns the driver receipt (validate_receipt-shaped)."""
    if not isinstance(seams, dict):
        raise ValueError("run_loop requires a seams dict")
    state = new_state(config)
    guard = 0
    while not state.get("terminal") and guard < _RUN_LOOP_GUARD:
        guard += 1
        step = _advance(state, state["config"])
        action = step["action"]
        if action == P_TERMINAL:
            break
        # handle the gap-sweep re-entry (verifiers → synthesis carries the merge back).
        artifact = _run_seam(seams, action, step["payload"], state, state["config"])
        _fold(state, state["config"], action, artifact)
        # a delta round routes scoped candidates through verifiers; when that path is armed the
        # synthesis fold must re-settle the delta rather than the round-1 path.
        if state.pop("_settleDeltaAfterSynthesis", False):
            pass
    if guard >= _RUN_LOOP_GUARD and not state.get("terminal"):
        state["terminal"] = "halted"
        state["certification"] = {"shape": None, "reason": "run_loop guard tripped — fail closed"}
    state["_scriptRan"] = {"invocations": guard, "byPhase": {}}
    return build_receipt(state)


# The synthesis fold, on a delta round, must re-settle the delta (breaker + confirmation) rather
# than the round-1 fix/terminal path. Wire that by overriding _after_findings_settled routing when
# a delta settle is armed.
_orig_after = _after_findings_settled


def _after_findings_settled(state, config):  # noqa: F811 — intentional post-def override
    if state.get("_settleDelta"):
        # merge gap/verify carry then settle the delta round.
        if state.get("_verifiedCarry") is not None:
            carry = state.pop("_verifiedCarry")
            state["findings"] = (carry or []) + (state.get("findings") or [])
        _settle_delta(state, config)
        return
    _orig_after(state, config)


# =============================================================================================
# Layer 2 — the stepwise CLI (next / submit)
# =============================================================================================

def _pending_step(state):
    return state.get("pending")


def cmd_next(session_dir, config_overrides=None):
    """Emit the ONE next action. Idempotent: a second `next` before a `submit` returns the same
    pending step + hash. A v1 state file is refused with a fresh-start message."""
    ok, loaded = load_state(session_dir)
    if not ok:
        _journal_append(session_dir, {"cmd": "next", "phase": None, "round": None,
                                      "attempt": None, "outcome": "refused-v1"})
        return {"ok": False, "reason": loaded}
    if loaded is None:
        state = new_state(config_overrides)
    else:
        state = loaded
    if state.get("pending"):
        # idempotent re-emit: the state is unchanged since the pending was persisted, so the hash
        # recomputed here equals the one the first `next` returned (the hash is NEVER stored in the
        # pending — that would make it un-reproducible on re-emit).
        pend = state["pending"]
        _journal_append(session_dir, {"cmd": "next", "phase": pend.get("phase"),
                                      "round": pend.get("round"), "attempt": pend.get("attempt"),
                                      "outcome": "re-emit"})
        return _next_response(pend, state_hash(state))
    step = _advance(state, state["config"])
    attempt = 0
    prior = state.get("lastAccepted")
    if prior and prior.get("phase") == step["phase"] and prior.get("round") == step["round"]:
        attempt = prior.get("attempt", 0) + 1
    pending = {"action": step["action"], "round": step["round"], "phase": step["phase"],
               "attempt": attempt, "payload": step["payload"]}
    state["pending"] = pending
    save_state(session_dir, state)
    _journal_append(session_dir, {"cmd": "next", "phase": pending["phase"],
                                  "round": pending["round"], "attempt": attempt,
                                  "outcome": "emitted"})
    if step["action"] == P_TERMINAL:
        _write_receipt(session_dir, state)
    return _next_response(pending, state_hash(state))


def _next_response(pending, expected_hash):
    return {
        "ok": True,
        "action": pending["action"],
        "round": pending["round"],
        "phase": pending["phase"],
        "attempt": pending["attempt"],
        "expectedStateHash": expected_hash,
        "payload": pending.get("payload"),
    }


def cmd_submit(session_dir, phase, attempt, state_hash_arg, artifact):
    """Validate the echo (phase/attempt/hash must match the pending step), fold the artifact, and
    advance. Stale/mismatched → rejected {ok: false} (exit 0). An exact duplicate of an
    already-accepted submit → idempotent {ok: true, duplicate: true}."""
    ok, loaded = load_state(session_dir)
    if not ok:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": None,
                                      "attempt": attempt, "outcome": "refused-v1"})
        return {"ok": False, "reason": loaded}
    if loaded is None:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": None,
                                      "attempt": attempt, "outcome": "no-state"})
        return {"ok": False, "reason": "no loop-state.json — call next first"}
    state = loaded
    art_hash = _sha256(_canonical(artifact if artifact is not None else {}))

    # duplicate detection FIRST (an already-accepted submit re-sent — its state hash is now stale,
    # but the phase/attempt/artifact triple identifies it as an exact replay).
    prior = state.get("lastAccepted")
    if prior and prior.get("phase") == phase and prior.get("attempt") == attempt \
            and prior.get("artifactHash") == art_hash:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": prior.get("round"), "attempt": attempt,
                                      "outcome": "duplicate"})
        return {"ok": True, "duplicate": True}

    pending = state.get("pending")
    if not pending:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": None,
                                      "attempt": attempt, "outcome": "no-pending"})
        return {"ok": False, "reason": "no pending step — call next first"}
    if phase != pending.get("phase") or attempt != pending.get("attempt"):
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": pending.get("round"), "attempt": attempt,
                                      "outcome": "echo-mismatch"})
        return {"ok": False, "reason": "phase/attempt echo does not match the pending step"}
    current_hash = state_hash(state)
    if state_hash_arg is not None and state_hash_arg != current_hash:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": pending.get("round"), "attempt": attempt,
                                      "outcome": "hash-mismatch"})
        return {"ok": False, "reason": "state-hash mismatch — the state moved under a stale submit"}

    # accept: clear the pending, fold, record lastAccepted, advance.
    round_no = pending.get("round")
    state["pending"] = None
    _fold(state, state["config"], phase, artifact)
    state["lastAccepted"] = {"phase": phase, "attempt": attempt, "round": round_no,
                             "artifactHash": art_hash}
    save_state(session_dir, state)
    _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": round_no,
                                  "attempt": attempt, "outcome": "accepted"})
    if state.get("terminal"):
        _write_receipt(session_dir, state)
    return {"ok": True, "round": round_no, "phase": phase, "nextStep": state.get("step")}


def _write_receipt(session_dir, state):
    receipt = build_receipt(state, session_dir)
    path = os.path.join(session_dir, RECEIPT_FILE)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    except OSError:
        pass
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description="the one-entrypoint review-loop round driver (#507)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pn = sub.add_parser("next")
    pn.add_argument("--session-dir", required=True)
    pn.add_argument("--leg", default=None)
    pn.add_argument("--vendors", default=None, help="JSON list of live vendors (fresh state only)")
    pn.add_argument("--verify-command", default=None)
    pn.add_argument("--max-rounds", type=int, default=None)
    pn.add_argument("--diff-path", default=None, help="round-1 reviewed diff (fresh state only)")

    ps = sub.add_parser("submit")
    ps.add_argument("--session-dir", required=True)
    ps.add_argument("--phase", required=True)
    ps.add_argument("--attempt", type=int, required=True)
    ps.add_argument("--state-hash", default=None)
    ps.add_argument("--artifact", required=True, help="path to the artifact JSON")

    args = parser.parse_args(argv)
    if args.cmd == "next":
        overrides = {}
        if args.leg:
            overrides["leg"] = args.leg
        if args.vendors:
            try:
                overrides["vendors"] = json.loads(args.vendors)
            except ValueError:
                pass
        if args.verify_command is not None:
            overrides["verifyCommand"] = args.verify_command
        if args.max_rounds is not None:
            overrides["maxRounds"] = args.max_rounds
        if args.diff_path:
            try:
                with open(args.diff_path, encoding="utf-8") as fh:
                    overrides["diff"] = fh.read()
            except OSError:
                pass
        out = cmd_next(args.session_dir, overrides or None)
    else:
        try:
            with open(args.artifact, encoding="utf-8") as fh:
                artifact = json.load(fh)
        except (OSError, ValueError) as exc:
            out = {"ok": False, "reason": "unreadable artifact: %s" % exc}
            sys.stdout.write(json.dumps(out) + "\n")
            return 0
        out = cmd_submit(args.session_dir, args.phase, args.attempt, args.state_hash, artifact)
    sys.stdout.write(json.dumps(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
