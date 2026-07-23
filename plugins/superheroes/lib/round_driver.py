#!/usr/bin/env python3
"""The one-entrypoint review-loop round driver (#507).

CONTRACT. This module collapses the review-code auto-fix loop's per-round script choreography
(plan → dispatch → compile → verify → synthesis → gate → persist → fix → re-review) into ONE
deterministic entrypoint so the mandated path is the easiest path — ~6/24 corpus runs routed
AROUND the old scripts because the choreography was several separate invocations. It has two
layers over one core:

  - Layer 1 (`run_loop`): the ported control-flow of `review_panel_shell.js::reviewPanel` with
    every effectful step behind an injectable seam (`reviewer`, `synthesis`, `verifier`,
    `auditor`, `fix_step`, `verify_runner`, `changed_subjects`, `io`). Same run-SHAPE, not the JS
    idioms. `changed_subjects` derives the fix's changed policy subjects from git (the reviewed vs
    head diff), NEVER the fixer's self-report (#157/#158) — the library default + the CLI path wire
    the real derivation; the eval harness injects a scripted replay.
  - Layer 2 (`next`/`submit` CLI): the state machine BETWEEN orchestrator dispatches — `next`
    emits the one action to run, `submit` folds its artifact and advances.

A tradeoff/product-choice blocker is an OWNER-JUDGMENT call: it routes to the `present-judgment`
INTERVENTION gate (fix-as-suggested / fix-with-guidance / skip-with-reason), whose fixes fold back
into the round's fix leg — it is NOT a terminal (#507 R2a; the `present-stall-menu` terminal is
reachable only from the audit-stall path). `load_state` migrates a state persisted under the OLD
routing (a judgment blocker dead-ended at `present-stall-menu`) onto the judgment gate in place;
`schemaVersion` stays 2 (session dirs are per-invocation — this only rescues a run parked mid-cut).

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
import re
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
import review_loop_plan  # noqa: E402
import review_memory  # noqa: E402
import review_round_policy  # noqa: E402
import verification  # noqa: E402
from finding_identity import finding_identity, normalize_title  # noqa: E402

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
JOURNAL_FAULT_FILE = "driver-journal-fault.jsonl"
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
P_JUDGMENT = "present-judgment"
P_STALL = "present-stall-menu"
P_TERMINAL = "terminal"

# The four stall-menu choices (never "judge the dispute yourself"). accept-the-risk is offerable
# ONLY for a CONFIRMED-with-receipt finding; the menu payload gates it per-run.
STALL_CHOICES = ("ship-smaller", "spend-more", "accept-the-disclosed-risk", "hold")

# The three per-finding judgment dispositions the judgment gate offers (never "judge the dispute
# yourself"): fix the finding as the reviewer suggested, fix it with owner free-text guidance, or
# skip it with a citable reason (a skipped blocker rides the exit disclosure — the skipped-blocking
# channel). The judgment gate is an INTERVENTION that folds back into the fix leg, NOT a terminal
# (#507 R2a) — the stall menu is the ONLY terminal, reachable solely from the audit-stall path.
JUDGMENT_DISPOSITIONS = ("fix-as-suggested", "fix-with-guidance", "skip")


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


class JournalFaultUnrecordable(Exception):
    """Last-resort fail-loud (#507 WO-FIX-RECOVERY): the journal append failed AND the durable fault
    marker that would have made finalization park ALSO could not be written. There is NO silent tier
    below this — the run must fail LOUDLY (the CLI exits nonzero) or PARK cannot-certify (a library
    driver), never continue as though the ran-evidence were intact. Carries both underlying OSErrors
    so the CLI can print them to stderr."""

    def __init__(self, journal_error, marker_error):
        self.journal_error = journal_error
        self.marker_error = marker_error
        super().__init__("journal write failed (%s) and the fault marker was also unwritable (%s)"
                         % (journal_error, marker_error))


def _journal_append(session_dir, entry):
    """Append one next/submit event to the journal — this is the `scriptRan` evidence. A journal miss
    never derails the run mid-flight, but it is NOT swallowed: a failed append is a LOST piece of the
    driver's ran-evidence, so it records a durable fault marker that `_finalize_receipt` fails closed
    on (a partial-journal gap must never quietly certify — #507 R2 residual-4). If BOTH the journal
    and the marker are unwritable, `_mark_journal_fault` raises `JournalFaultUnrecordable` — the
    last-resort fail-loud, propagated here (never swallowed). ts via time.time."""
    entry = dict(entry)
    entry.setdefault("ts", time.time())
    try:
        with open(os.path.join(session_dir, JOURNAL_FILE), "a", encoding="utf-8") as fh:
            fh.write(_canonical(entry) + "\n")
    except OSError as exc:
        _mark_journal_fault(session_dir, entry, exc)


def _mark_journal_fault(session_dir, entry, exc):
    """Record a durable journal-write fault so finalization fails closed. This is the LAST recordable
    tier: if the marker ALSO cannot be written, there is NO silent tier below it — raise
    `JournalFaultUnrecordable` so the run fails loud (CLI nonzero) or parks cannot-certify (library),
    never swallowing the fault (the R2 detectability gap, one level down: `except OSError: pass` here
    let a doubly-unwritable dir go silent). The exception carries both OSErrors for the stderr
    report. #507 WO-FIX-RECOVERY."""
    try:
        with open(os.path.join(session_dir, JOURNAL_FAULT_FILE), "a", encoding="utf-8") as fh:
            fh.write(_canonical({"ts": time.time(), "error": str(exc),
                                 "cmd": entry.get("cmd"), "phase": entry.get("phase")}) + "\n")
    except OSError as marker_exc:
        raise JournalFaultUnrecordable(exc, marker_exc) from marker_exc


def _journal_faulted(session_dir):
    return os.path.exists(os.path.join(session_dir, JOURNAL_FAULT_FILE))


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


def _compile_by_anchor(findings):
    """Dedupe by the binding review workflow's per-LOCATION anchor — (file, line, normalized-title)
    — NOT panel_tally's line-less `file::normalized-title` identity. The line was the DROPPED key:
    two distinct findings that share a title at DIFFERENT lines are distinct blockers and BOTH must
    survive (else a blocker at a second line is silently collapsed away). For the SAME anchor,
    higher severity wins, dimensions are unioned, and tradeoff is OR-ed; FR-4 classification is
    stamped from the surviving tradeoff state. All inputs are already cited (file+line present)."""
    by_anchor = {}
    order = []
    for f in findings:
        key = (f.get("file"), f.get("line"), normalize_title(str(f.get("title") or "")))
        if key in by_anchor:
            ex = by_anchor[key]
            dims = panel_tally._merge_dims(ex, f)
            if panel_tally.SEV_RANK.get(f.get("severity"), 99) \
                    < panel_tally.SEV_RANK.get(ex.get("severity"), 99):
                merged = dict(f)
            else:
                merged = dict(ex)
            merged["dimension"] = dims
            merged["tradeoff"] = bool(ex.get("tradeoff") or f.get("tradeoff"))
            by_anchor[key] = merged
        else:
            by_anchor[key] = dict(f)
            order.append(key)
    out = [by_anchor[k] for k in order]
    for f in out:  # FR-4: deterministic mechanical/judgment classification (no action taken)
        f["classification"] = "judgment" if f.get("tradeoff") else "mechanical"
    return out


def mechanical_compile(findings, diff_text=None):
    """Port of SKILL §4 steps 1-4 + 6, deterministic and fail-closed:
      1. citation check — drop file/line-less findings;
      2. diff-scope check — drop findings whose (file,line) is not an anchor of the round diff;
      4. dedupe by the per-LOCATION anchor (file, line, normalized-title) — higher severity wins,
         dimensions unioned, tradeoff OR-ed. NOT the line-less file::title identity, which collapses
         two distinct-line findings that share a title (a dropped blocker);
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
        fc = dict(f)
        if "dimension" in fc:
            norm = panel_tally.normalize_dimension(fc["dimension"])
            if norm:
                fc["dimension"] = norm
            else:
                fc.pop("dimension", None)
        kept.append(fc)
    compiled = _compile_by_anchor(kept)
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
        # Optional resume/records seam (#507 WO-D). When `recordsPath` is set the driver reads it
        # ONCE at new_state to resume at round N+1 from the durable seeds (review_loop_plan's
        # entry-bootstrap / _resume_round twins); a corrupt/mangled record state fails closed to a
        # cannot-certify park. `coveragePath` seeds the accumulated coverage decisions the
        # challenged-coverage breaker reads. Absent → a fresh round-1 run (the library-test shape).
        "recordsPath": None,
        "coveragePath": None,
        # PR-mode prior review comments (a list) for the author-justification post-filter. Wired from
        # the CLI's `--prior-comments` (#507 v7); None → the filter never fires.
        "priorComments": None,
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
    state = {
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
        # A configured lens that never ran is an OUTSTANDING coverage gap: set when a panel is
        # incomplete, cleared only when a COMPLETE panel re-establishes coverage. A converge resting
        # on it is withheld (silence never certifies — #507 R2 residual-1).
        "_incompletePanel": False,
        # The UNION of policy subjects the fix touched since the last full panel — the cross-cutting
        # re-arm reads THIS accumulation, not a single round's delta, so rework that spreads across
        # MULTIPLE post-confirmation fixes still trips the bar (#507 R2 residual-5). None = an unknown
        # surface since the panel (fail toward one more confirmation).
        "_changedSubjectsSincePanel": [],
        "terminal": None,
        "certification": None,
        # #507 WO-D: the in-memory review-record ledger (one record per REVIEW round) the
        # challenged-coverage / recurrence breaker reads, plus the accumulated coverage decisions.
        "_records": [],
        "_coverage": [],
        "_resumeCorrupt": None,
    }
    _seed_resume(state, cfg)
    return state


def _seed_resume(state, cfg):
    """Resume seam (#507 WO-D): when `recordsPath` names a durable round-records file, read it ONCE
    and resume at round N+1 the way review_panel_shell's entry-bootstrap did. A corrupt/mangled
    record state fails closed (flagged so run_loop parks cannot-certify). Reuses the review_loop_plan
    twins (`entry_bootstrap`/`_resume_round`) and `review_memory.load_records_state` — no re-impl."""
    records_path = cfg.get("recordsPath")
    if not records_path:
        return
    dims = _panel_dimensions(cfg)
    loaded = review_memory.load_records_state(records_path, dims)
    if not loaded.get("ok"):
        state["_resumeCorrupt"] = (
            "resume state %s (%s) — cannot certify; a fresh full reviewer-deep round is owed"
            % (loaded.get("state") or "unreadable", loaded.get("reason") or "unreadable"))
        return
    records = [r for r in (loaded.get("records") or []) if isinstance(r, dict)]
    # Seed the accumulated coverage decisions the challenged-coverage breaker reads: prefer the
    # explicit coveragePath, else fold the records' own coverage decisions.
    coverage = []
    cov_path = cfg.get("coveragePath")
    if cov_path and os.path.exists(cov_path):
        try:
            with open(cov_path, encoding="utf-8") as fh:
                loaded_cov = json.load(fh)
            if isinstance(loaded_cov, list):
                coverage = [d for d in loaded_cov if isinstance(d, dict)]
        except (OSError, ValueError):
            coverage = []
    if not coverage:
        for rec in records:
            for d in rec.get("coverageDecisions") or []:
                if isinstance(d, dict):
                    coverage.append(d)
    state["_records"] = records
    state["_coverage"] = coverage
    if not records:
        return
    resume_round = review_loop_plan._resume_round(records)
    if resume_round <= 1:
        return
    # A qualifying full confirmation panel among the seeds counts toward the confirmation budget; a
    # degraded (not-all-fresh-deep-high-confidence) confirmation does NOT — _confirmation_qualifies
    # is the #167 bar, so a seeded degraded panel cannot anchor certification (a proper panel is owed).
    qualifying = sum(1 for r in records
                     if r.get("kind") == "confirmation" and review_loop_plan._confirmation_qualifies(r))
    state["confirmations"] = qualifying
    state["round"] = resume_round
    state["step"] = P_PANEL
    state["fullPanelRan"] = False
    eb = review_loop_plan.entry_bootstrap(records_path, dims)
    owed = review_loop_plan._further_confirmation_owed(records, doc_mode=cfg.get("docMode", False))
    if eb.get("ok") and eb.get("confirmationPending") and owed.get("owed"):
        # The loop stopped mid-confirmation and a further FULL confirmation panel is still owed (the
        # seeded panel was degraded / no qualifying panel has run) — resume by running that panel.
        _decision(state, "resume-confirmation",
                  "resumed with a pending confirmation and no qualifying panel — running a full "
                  "confirmation panel (a degraded seed cannot anchor certification)")


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
    _migrate_judgment_step(data)
    return True, data


def _migrate_judgment_step(state):
    """#507 R2a step migration (schemaVersion stays 2). A state persisted under the OLD routing —
    tradeoff/judgment blockers dead-ended at the `present-stall-menu` terminal — is re-pointed to
    the `present-judgment` gate so `next` re-emits the judgment action under the new contract. The
    tell is a state parked at `present-stall-menu` that still carries `_judgmentFindings` (only the
    old judgment→stall routing set both together; the audit-stall path never sets judgment findings).
    The stale stall `pending` is dropped so `next` recomputes the action from state. In-place."""
    if not isinstance(state, dict):
        return state
    if state.get("step") == P_STALL and state.get("_judgmentFindings"):
        state["step"] = P_JUDGMENT
        state.pop("_stallChoices", None)
        state.pop("_acceptRiskEligible", None)
        pend = state.get("pending")
        if isinstance(pend, dict) and pend.get("phase") == P_STALL:
            state["pending"] = None
    return state


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


# ---- challenged-coverage + the in-memory review-record ledger (#507 WO-D) --------------------

def _annotate_challenged(coverage, findings):
    """Port of review_panel_shell.annotateChallengedCoverage — a blocking finding whose class key
    matches an ALREADY-RECORDED coverage decision stamps that decision `challengedBy` (the fix's
    coverage rationale was recorded on a principle the reviewer is still raising). The challenged
    decision then feeds circuit_breaker's `challenged-principle-recurring` halt when the class
    recurs. Returns a fresh (copied) coverage list so the accumulator is never mutated in place."""
    out = [dict(d) for d in (coverage or []) if isinstance(d, dict)]
    known = {d.get("classKey") for d in out if d.get("classKey")}
    by_class = {d.get("classKey"): d for d in out if d.get("classKey")}
    for f in findings or []:
        if not isinstance(f, dict) or not circuit_breaker.is_blocking(f.get("severity")):
            continue
        key = f.get("classKey") or review_memory.class_key(f)
        if key in known and key in by_class:
            by_class[key]["challengedBy"] = f.get("dimension") or "reviewer"
    return out


def _append_review_record(state, rnd, kind, dim_map, findings):
    """Append (or replace) this round's in-memory review record for the challenged-coverage /
    recurrence breaker. The record carries the round's compiled findings, a per-dimension run map
    (so `_round_reviewed` / `_confirmation_qualifies` read it), the challenged-annotated coverage
    accumulated so far, and the recurrence-derived generalize grace (recurrent_classes over PRIOR
    records + coverage — the same current=compiled / prior=record split tally_round_decider uses)."""
    findings = [f for f in (findings or []) if isinstance(f, dict)]
    coverage = _annotate_challenged(state.get("_coverage") or [], findings)
    prior = [r for r in (state.get("_records") or []) if r.get("round") != rnd]
    record = {
        "schemaVersion": 2,
        "round": rnd,
        "kind": kind,
        "dimensions": dim_map or {},
        "findings": findings,
        "changedSubjects": state.get("_changedSubjects"),
        "coverageDecisions": coverage,
        "generalizeRequired": review_memory.recurrent_classes(prior, coverage),
        "confirmationPending": False,
    }
    records = [r for r in (state.get("_records") or []) if r.get("round") != rnd]
    records.append(record)
    records.sort(key=lambda r: r.get("round") if isinstance(r.get("round"), int) else 0)
    state["_records"] = records


def _challenged_recurring_halt(state, config):
    """Run circuit_breaker over the in-memory ledger; act ONLY on `challenged-principle-recurring`
    (a coverage decision recorded on a WRONG principle whose class recurs). The plain
    recurring-finding / no-net-progress halts are the JS in-panel schedule's job — the #507 driver
    replaces them with the audit-keyed breaker + generalize grace — so they are NOT acted on here;
    the challenged path is the one safety property the delta schedule would otherwise drop. Returns
    the breaker dict when it fires a challenged halt, else None."""
    records = state.get("_records") or []
    if len(records) < 2:
        return None
    brk = circuit_breaker.check_circuit_breaker(records, config.get("maxRounds", 7))
    if brk.get("halt") and brk.get("reason") == "challenged-principle-recurring":
        return brk
    return None


def _park_cannot_certify(state, detail):
    """A fail-closed park with certification withheld (challenged principle / corrupt resume). Maps
    to a `halted` terminal — never a silent clean."""
    state["terminal"] = "cannot-certify"
    state["certification"] = {"shape": None, "reason": detail or "cannot certify — park"}
    _decision(state, "cannot-certify", detail)
    state["step"] = P_TERMINAL


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
    elif step == P_JUDGMENT:
        payload = {"findings": [
            {"id": _judgment_finding_id(f), "file": f.get("file"), "line": f.get("line"),
             "title": f.get("title"), "severity": f.get("severity"),
             "classification": "judgment", "dispositions": list(JUDGMENT_DISPOSITIONS)}
            for f in (state.get("_judgmentFindings") or []) if isinstance(f, dict)]}
    elif step == P_STALL:
        # The stall menu is the audit-stall TERMINAL only (a tradeoff/judgment blocker routes to
        # present-judgment, never here — #507 R2a). No judgment findings ride this payload.
        payload = {"choices": list(state.get("_stallChoices") or STALL_CHOICES),
                   "acceptRiskEligible": bool(state.get("_acceptRiskEligible"))}
    return {"action": step, "round": rnd, "phase": step, "payload": payload}


def _record_round(state, key, value):
    rec = state["rounds"].setdefault(str(state["round"]), {})
    rec[key] = value


def _decision(state, kind, detail):
    state["decisions"].append({"round": state["round"], "kind": kind, "detail": detail})


def _fold(state, config, phase, artifact, changed_subjects_seam=None):
    """Fold one submitted artifact and advance state. Big switch on phase; each arm delegates the
    JUDGMENT to a pure decider and only records/sequences here. Returns the mutated state.

    `changed_subjects_seam` is threaded to the fixer fold: run_loop passes the injected seam (the
    eval harness replays the fixture's subjects); the CLI submit path passes None so the fixer fold
    wires the real git derivation. It is inert for every other phase."""
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
        _fold_fixer(state, config, artifact, changed_subjects_seam)
    elif phase == P_JUDGMENT:
        _fold_judgment(state, config, artifact)
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
    raw = []
    seat_status = {}
    unverified = []
    missing_dims = []
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
        else:
            # A configured dimension with NO dict/list seat did not run: an omitted / null / mangled
            # seat is a silent coverage gap. Fail closed — status `missing`, never a clean `run`, so
            # it cannot count toward a full-panel certification (silence never certifies).
            status = "missing"
        if status == "missing":
            missing_dims.append(dim)
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
    incomplete = bool(missing_dims)
    compiled, drops = mechanical_compile(raw, state.get("reviewedDiff"))
    # A full reviewer-deep panel that runs COMPLETE in a DELTA round (round ≥ 2) is a qualifying
    # confirmation panel: it consumes one of the two-panel budget (the #174 bar). An INCOMPLETE panel
    # (a missing seat) does NOT qualify — it neither counts a confirmation nor resets/reseeds the
    # surfaced-since tracker, so the owed confirmation stays owed rather than being discharged on a
    # coverage gap. A complete panel resets the tracker and reseeds it from its OWN blocking findings
    # so a Critical it surfaces re-arms another confirmation (#174 requirement 2).
    if state["round"] >= 2 and not incomplete:
        state["confirmations"] = state.get("confirmations", 0) + 1
        state["surfacedSinceLastPanel"] = [
            "Critical" if circuit_breaker.is_critical(f.get("severity")) else "Important"
            for f in _blocking(compiled)]
    _record_round(state, "seatStatus", seat_status)
    _record_round(state, "compileDrops", drops)
    if unverified:
        _record_round(state, "unverified", unverified)
        _decision(state, "receipt-missing-seat",
                  "%d finding(s) carried unverified from receipt-missing seat(s)" % len(unverified))
    if incomplete:
        _record_round(state, "missingSeats", list(missing_dims))
        _decision(state, "panel-seat-missing",
                  "panel incomplete — %d configured lens(es) did not run (%s); certification cannot "
                  "be full-panel-confirmed" % (len(missing_dims), ", ".join(missing_dims)))
    # Only a COMPLETE panel can anchor a full-panel-confirmed certification. A missing seat leaves
    # fullPanelRan False so a clean finish downgrades to audited-chain and names the gap.
    state["fullPanelRan"] = not incomplete
    # Track the OUTSTANDING coverage gap across the loop: an incomplete panel arms it (a converge
    # resting on it is withheld — a lens never ran); a COMPLETE panel recovers coverage and clears it
    # (#507 R2 residual-1). A scoped delta round leaves it untouched, so a round-1 gap never silently
    # clears on a delta finish.
    state["_incompletePanel"] = incomplete
    # A full panel re-establishes the review baseline: reset the cross-cutting-rework accumulator so a
    # broad fix BEFORE this panel does not count as the panel's rework, and the union runs from this
    # panel forward across every later fix (#507 R2 residual-5).
    state["_changedSubjectsSincePanel"] = []
    # In-memory review record for the challenged-coverage / recurrence breaker: a round-1 panel is
    # `baseline`, a re-armed / resumed full panel (round ≥ 2) is a `confirmation` (its per-dim run
    # map lets _confirmation_qualifies judge whether it can anchor certification).
    kind = "baseline" if state["round"] <= 1 else "confirmation"
    dim_map = {}
    for dim in _panel_dimensions(config):
        seat = seats.get(dim) if isinstance(seats, dict) else None
        s_findings = []
        # A missing seat defaults to LOW confidence, never high — an absent lens must never lend a
        # high-confidence run to `_confirmation_qualifies`.
        confidence = "low" if seat_status.get(dim) == "missing" else "high"
        tier = DEEP
        if isinstance(seat, dict):
            s_findings = seat.get("findings") or []
            if seat_status.get(dim) != "missing":
                confidence = seat.get("confidence") or "high"
            tier = seat.get("tier") or DEEP
        elif isinstance(seat, list):
            s_findings = seat
        dim_map[dim] = {"dimension": dim, "status": seat_status.get(dim, "run"),
                        "confidence": confidence, "tier": tier, "findings": s_findings}
    _append_review_record(state, state["round"], kind, dim_map, compiled)
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


def _judgment_finding_id(finding):
    """The per-LOCATION disposition key for a judgment finding — the line-less `finding_identity`
    PLUS the line. Two same-title tradeoff blockers at DIFFERENT lines get DISTINCT ids, so the
    owner's disposition for one never collides onto the other (the line-less identity did — #507 R2
    v5). The present-judgment payload emits this id and the fold keys the dispositions on it."""
    return "%s@L%s" % (finding_identity(finding), finding.get("line"))


def _route_judgment_blockers(state, blocking):
    """Triage before composing an autonomous fix batch. A blocking finding carrying `tradeoff: true`
    is a PRODUCT-CHOICE / judgment call — the review-code contract routes it to the OWNER, never to
    the fixer for autonomous change. But the judgment gate is an INTERVENTION, not a terminal (#507
    R2a — the old routing dead-ended these in the stall menu, so a tradeoff blocker could never be
    fixed-and-audited): the owner disposes EACH judgment finding (fix-as-suggested /
    fix-with-guidance / skip) at the `present-judgment` phase, and the loop then folds the fixes into
    the round's fix batch and proceeds into the fix leg — the skips ride the exit disclosure. Any
    mechanical (non-tradeoff) blockers in the SAME batch are carried through the gate and ride
    straight into the fix batch alongside the fix-disposed judgment findings (never abandoned).
    Returns True when it took over routing (the caller must return); False when the batch is purely
    mechanical (the caller composes the fix batch as before)."""
    judgment = [f for f in blocking if isinstance(f, dict) and f.get("tradeoff")]
    if not judgment:
        return False
    mechanical = [f for f in blocking if isinstance(f, dict) and not f.get("tradeoff")]
    state["_judgmentFindings"] = [dict(f) for f in judgment]
    state["_judgmentMechanical"] = [dict(f) for f in mechanical]
    _record_round(state, "judgmentBlockers", [
        {"id": _judgment_finding_id(f), "file": f.get("file"), "line": f.get("line"),
         "title": f.get("title"), "severity": f.get("severity"), "classification": "judgment"}
        for f in judgment])
    _decision(state, "judgment-gate",
              "%d tradeoff/product-choice blocker(s) routed to owner judgment — never auto-fixed; "
              "each offered fix-as-suggested / fix-with-guidance / skip: %s"
              % (len(judgment), "; ".join(f.get("title") or "?" for f in judgment)))
    state["step"] = P_JUDGMENT
    return True


def _skipped_note(state):
    """The certification note for a run whose ONLY blocking work was owner-skipped judgment
    findings — they are disclosed product-choice tradeoffs, cited in the ledger, not fixed."""
    skipped = state.get("_skippedBlockers") or []
    if not skipped:
        return None
    return ("%d blocking finding(s) owner-skipped as product-choice tradeoffs — disclosed, not "
            "fixed: %s" % (len(skipped), "; ".join(s.get("title") or "?" for s in skipped)))


def _fold_judgment(state, config, artifact):
    """Fold the owner's per-finding judgment dispositions (#507 R2a — the judgment gate is an
    INTERVENTION, not a terminal). The artifact is `{dispositions: [{id, disposition, guidance?,
    reason?}, ...]}`, keyed to each `present-judgment` finding's identity. Each judgment finding is
    disposed:

      - `fix-as-suggested`  → folds into the round's fix batch;
      - `fix-with-guidance` → folds into the fix batch with the owner's free-text `guidance` attached;
      - `skip`              → requires a citable `reason` (recorded in the decision ledger); the
                              skipped blocker rides the exit disclosure (the skipped-blocking channel).

    FAIL-CLOSED: a listed judgment finding with a MISSING or UNKNOWN disposition — or a `skip` with
    no citable reason — folds as `fix-as-suggested`. A judgment blocker is NEVER silently skipped.
    The fixes join the round's fix batch alongside the mechanical (non-tradeoff) blockers carried
    through the gate, and the loop proceeds to `dispatch-fixer`; when the WHOLE fix batch is empty
    (every judgment finding skipped and no mechanical blocker) the loop settles into a converged
    terminal with the skips disclosed."""
    raw = artifact.get("dispositions") if isinstance(artifact.get("dispositions"), list) else []
    by_id = {}
    for d in raw:
        if isinstance(d, dict) and d.get("id") is not None:
            by_id[d.get("id")] = d
    judgment = [f for f in (state.get("_judgmentFindings") or []) if isinstance(f, dict)]
    fix_batch = [dict(f) for f in (state.get("_judgmentMechanical") or []) if isinstance(f, dict)]
    skipped = []
    disposition_log = []
    for f in judgment:
        fid = _judgment_finding_id(f)
        d = by_id.get(fid) if isinstance(by_id.get(fid), dict) else {}
        disposition = d.get("disposition")
        reason = d.get("reason")
        if disposition == "skip" and isinstance(reason, str) and reason.strip():
            skipped.append({"id": fid, "file": f.get("file"), "line": f.get("line"),
                            "title": f.get("title"), "severity": f.get("severity"),
                            "reason": reason.strip()})
            disposition_log.append({"id": fid, "title": f.get("title"), "disposition": "skip",
                                    "reason": reason.strip()})
            _decision(state, "judgment-skip",
                      "owner skipped judgment blocker %r — reason: %s"
                      % (f.get("title") or fid, reason.strip()))
            continue
        g = dict(f)
        if disposition == "fix-with-guidance":
            g["judgmentDisposition"] = "fix-with-guidance"
            guidance = d.get("guidance")
            if isinstance(guidance, str) and guidance.strip():
                g["guidance"] = guidance.strip()
            disposition_log.append({"id": fid, "title": f.get("title"),
                                    "disposition": "fix-with-guidance"})
        elif disposition == "fix-as-suggested":
            g["judgmentDisposition"] = "fix-as-suggested"
            disposition_log.append({"id": fid, "title": f.get("title"),
                                    "disposition": "fix-as-suggested"})
        else:
            # missing / unknown disposition, or a skip with no citable reason → fail closed to fix.
            g["judgmentDisposition"] = "fix-as-suggested"
            g["judgmentFailClosed"] = True
            disposition_log.append({"id": fid, "title": f.get("title"),
                                    "disposition": "fix-as-suggested", "failClosed": True})
            _decision(state, "judgment-fail-closed",
                      "judgment blocker %r had no valid disposition (%r) — folded as "
                      "fix-as-suggested (a judgment blocker is never silently skipped)"
                      % (f.get("title") or fid, disposition))
        fix_batch.append(g)
    if skipped:
        state["_skippedBlockers"] = (state.get("_skippedBlockers") or []) + skipped
        _record_round(state, "skippedBlockers", skipped)
    _record_round(state, "judgmentDispositions", disposition_log)
    state.pop("_judgmentFindings", None)
    state.pop("_judgmentMechanical", None)
    if fix_batch:
        state["_fixBatch"] = fix_batch
        state["step"] = P_FIXER
        return
    # Everything skipped and no mechanical blocker: settle. The skipped blockers are owner-accepted
    # product-choice tradeoffs (cited in the ledger) — converge, naming them on the exit disclosure.
    _terminal_converged(state, config, full_panel=state.get("fullPanelRan"),
                        note=_skipped_note(state))


def _after_findings_settled(state, config):
    """After the round's findings are verified + merged + justification-filtered: route to the fix
    leg when there is a blocking finding, else to the terminal decision (round 1 clean = certify).

    ONE definition (no post-def override): a delta round routes its scoped/gap candidates through
    verify+synthesis, so when the delta settle is armed it must re-settle the delta (audit breaker +
    #174 confirmation re-arm) rather than the round-1 fix/terminal path. Either way the gap/verify
    carry is merged back first."""
    # merge any gap-sweep / verify carry back in.
    if state.get("_verifiedCarry") is not None:
        carry = state.pop("_verifiedCarry")
        state["findings"] = (carry or []) + (state.get("findings") or [])
        state.pop("_gapMerge", None)
    if state.get("_settleDelta"):
        _settle_delta(state, config)
        return
    blocking = _blocking(state.get("findings") or [])
    _record_round(state, "blockingCount", len(blocking))
    if blocking:
        if _route_judgment_blockers(state, blocking):
            return
        state["_fixBatch"] = [dict(f) for f in blocking]
        state["step"] = P_FIXER
    else:
        _terminal_converged(state, config, full_panel=state.get("fullPanelRan"))


# ---- fix + verify legs ----------------------------------------------------------------------

def _subjects_for_dimension(dimension):
    """Policy subjects mentioned by a compiled finding's dimension label — a single label
    ('Security') or a merged one ('Security + Code'). Reuses review_round_policy's mapping so the
    driver derives subjects the one way the confirmation economics read them (never a second
    mapping)."""
    out = set()
    if not isinstance(dimension, str):
        return out
    for token in re.split(r"[^A-Za-z-]+", dimension):
        subject = review_round_policy._policy_subject(token)
        if subject:
            out.add(subject)
    return out


def derive_changed_subjects(reviewed_diff_text, head_diff_text, accumulated_findings):
    """The REAL #157/#158 derivation: the policy subjects the fix TOUCHED, script-computed from git
    and NEVER the fixer's self-report. The files whose unified-diff sections differ between the
    reviewed diff and the post-fix head diff (`delta_surface.changed_files`), mapped to policy
    subjects through the accumulated compiled findings — a changed file is attributed to a subject
    when ANY reviewer cited it. Returns a KNOWN list (possibly empty) or None (unknown surface →
    the caller's existing run-everything rule). Any unreadable / unparseable diff → None."""
    changed = delta_surface.changed_files(reviewed_diff_text, head_diff_text)
    if changed is None:
        return None
    subjects = set()
    for f in accumulated_findings or []:
        if isinstance(f, dict) and f.get("file") in changed:
            subjects |= _subjects_for_dimension(f.get("dimension"))
    return sorted(subjects)


def _accumulated_findings(state):
    """The attribution surface the git-derived changed-subjects mapping reads: the UNION of every
    round's compiled findings (the in-memory record ledger) plus this round's settled findings.
    Attributing rework through the accumulated history — not only the deciding round — is what lets
    a confirmation panel's own surfaced findings attribute the post-panel rework files, so the
    cross-cutting-rework re-arm is not structurally inert."""
    out = []
    for rec in state.get("_records") or []:
        for f in rec.get("findings") or []:
            if isinstance(f, dict):
                out.append(f)
    for f in state.get("findings") or []:
        if isinstance(f, dict):
            out.append(f)
    return out


def _resolve_head_diff(artifact):
    """Resolve the post-fix head diff the delta split reads. The `dispatch-fixer` artifact may carry
    it INLINE (`headDiff`) or, since a real `git diff BASE...HEAD` can be hundreds of KB and cannot
    reasonably inline into a JSON submit artifact, as an ABSOLUTE file path (`headDiffPath`) the
    driver reads itself (#507). Inline WINS when present. A missing / non-absolute / unreadable path,
    or empty file content, is NOT an empty diff — it is an UNKNOWN surface, so the caller escalates
    to a full panel (the fail-closed unknown→run-everything rule) rather than silently computing an
    empty scoped surface. Returns (head_or_None, source) where source is 'inline'|'path'|'unknown'."""
    inline = artifact.get("headDiff")
    if inline is not None:
        return inline, "inline"
    path = artifact.get("headDiffPath")
    if isinstance(path, str) and path and os.path.isabs(path):
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            content = None
        if content:
            return content, "path"
    return None, "unknown"


def _fold_fixer(state, config, artifact, changed_subjects_seam=None):
    """Record the fixer's result; the fix-batch COMPOSITION stays orchestrator-side (the artifact),
    the driver sequences + records. The post-fix head diff rides the artifact (git, per the
    dispatch-fixer contract) so the next delta round can split_fix_surface against git — INLINE
    (`headDiff`) or as an absolute `headDiffPath` the driver reads (`_resolve_head_diff`); an
    unresolvable path fails to an unknown surface (full panel), never a silent empty scoped skip. The
    changed policy subjects the #174 confirmation re-arm consumes are SCRIPT-DERIVED here — from the
    reviewed-vs-head diff through the accumulated findings (#157/#158), NEVER the fixer's
    self-report. The derivation is an injectable seam symmetrical with reviewer/fixer/verify:
    run_loop may inject a scripted replay (the eval harness); the library default + the CLI path
    wire the real git derivation. Unknown/unparseable surface → None → the run-everything rule."""
    state["fixBatch"] = state.get("_fixBatch") or []
    head, head_source = _resolve_head_diff(artifact)
    state["headDiff"] = head
    state["_headDiffSource"] = head_source
    state["_headDiffUnknown"] = head_source == "unknown"
    _record_round(state, "headDiffSource", head_source)
    derive = changed_subjects_seam or derive_changed_subjects
    state["_changedSubjects"] = derive(
        state.get("reviewedDiff"), state.get("headDiff"), _accumulated_findings(state))
    # Accumulate the changed subjects since the last full panel so the #174 cross-cutting re-arm sees
    # rework that spreads across MULTIPLE post-confirmation fixes, not just this round's single-pair
    # delta (#507 R2 residual-5). ONLY delta/confirmation-round fixes (round ≥ 2) count as the
    # confirmation's rework — the round-1 BASELINE fix that resolves the initial review is not "rework
    # since the panel" (a broad baseline fix must not force a confirmation). An unknown surface (None)
    # makes the accumulation sticky-unknown (fail toward one more confirmation) until a panel resets it.
    subjects = state.get("_changedSubjects")
    if state["round"] >= 2:
        if subjects is None:
            state["_changedSubjectsSincePanel"] = None
        elif state.get("_changedSubjectsSincePanel") is not None:
            acc = set(state.get("_changedSubjectsSincePanel") or [])
            acc |= {s for s in subjects if isinstance(s, str)}
            state["_changedSubjectsSincePanel"] = sorted(acc)
    # Accumulate the fix's coverage decisions so the challenged-coverage breaker can see a decision
    # recorded on a principle a later round re-raises (annotateChallengedCoverage input).
    cds = artifact.get("coverageDecisions")
    if isinstance(cds, list):
        state.setdefault("_coverage", []).extend(d for d in cds if isinstance(d, dict))
    _record_round(state, "fix", {"fixes": artifact.get("fixes") or [],
                                 "escalated": bool(artifact.get("escalated") or state.get("_escalatedRung"))})
    state.pop("_escalatedRung", None)
    state["step"] = P_VERIFY


_VERIFY_SKIP = ("skipped", "none", "unverified")


def _verify_command_configured(config):
    """True when the profile configures a REAL verify command (not absent / `none`). A configured
    command must actually PASS — a skip result then means the run did not execute, so it fails closed
    rather than advancing unverified (#507 R2 residual-2)."""
    cmd = config.get("verifyCommand")
    if not isinstance(cmd, str):
        return False
    return cmd.strip().lower() not in ("", "none")


def _fold_verify(state, config, artifact):
    """Fold the verify result. FAIL-CLOSED (#507 v10): advance ONLY on an explicit `pass` or — WHEN NO
    verify command is configured — an explicit unverified skip (`skipped`/`none`/`unverified`). A
    `fail`, a `timeout`, a missing/None result, any unrecognized value, OR a skip result while a real
    verify command IS configured (the command did not actually run) HALTS with an honest reason that
    names the class — never advances into a delta round that could later certify."""
    result = artifact.get("result")
    _record_round(state, "verifyResult", result)
    if result == "fail":
        state["terminal"] = "halted"
        state["certification"] = {"shape": None, "reason": "verify gate failed"}
        _decision(state, "verify-fail", "verify gate failed — halt, certification withheld")
        state["step"] = P_TERMINAL
        return
    if result in _VERIFY_SKIP:
        if _verify_command_configured(config):
            # A configured verify command reported a skip — it did NOT actually run its checks. Fail
            # closed: a configured verification must PASS, never advance on a skip (#507 R2 residual-2).
            state["terminal"] = "halted"
            state["certification"] = {
                "shape": None,
                "reason": ("verify gate reported %r but a verify command is configured (%r) — the "
                           "gate did not run; halt, certification withheld"
                           % (result, config.get("verifyCommand")))}
            _decision(state, "verify-skip-but-configured",
                      "verify result %r with a configured verify command — fail closed, the gate "
                      "did not actually run" % result)
            state["step"] = P_TERMINAL
            return
        _decision(state, "verify-skipped",
                  "verify gate skipped (%s) — advancing unverified (no verify command)" % result)
    elif result != "pass":
        # timeout / missing / unknown → the gate did NOT pass; fail closed.
        state["terminal"] = "halted"
        state["certification"] = {
            "shape": None,
            "reason": "verify gate did not pass (result %r) — halt, certification withheld" % (result,)}
        _decision(state, "verify-unresolved",
                  "verify result %r is not pass/skip — fail closed, certification withheld" % (result,))
        state["step"] = P_TERMINAL
        return
    # advance to the next (delta) round. The diff the just-finished round's panel/audit saw is the
    # `reviewed` side of the next split_fix_surface; the fixer's head diff is the `head` side.
    state["_priorReviewedDiff"] = state.get("reviewedDiff")
    state["round"] += 1
    state["reviewedDiff"] = state.get("headDiff") or state.get("reviewedDiff")
    _enter_delta_round(state, config)


# ---- delta rounds (2+) ----------------------------------------------------------------------

def _schedule_full_panel_unknown(state, detail):
    """The fail-closed unknown→run-everything rule: an unresolvable delta surface schedules a FULL
    reviewer-deep panel, never a silently-scoped (or silently-skipped) round."""
    _decision(state, "unknown-surface", detail)
    _record_round(state, "roundKind", "full-panel-unknown-surface")
    state["fullPanelRan"] = False
    state["step"] = P_PANEL


def _enter_delta_round(state, config):
    """Rounds 2+: split_fix_surface(reviewed, head, fixBatch). unknown → schedule a FULL panel
    (the existing unknown→run-everything rule). Else audit the fixed findings + scoped-find the new
    surface."""
    # An unresolvable post-fix head diff (a missing/unreadable `headDiffPath`, no inline diff) is an
    # unknown surface BEFORE the split runs — never fold it through as an empty diff (#507). This is
    # the honest recovery for the field defect: a lost head diff now runs a full panel, not a vacuous
    # scoped scan over nothing.
    if state.pop("_headDiffUnknown", False):
        _schedule_full_panel_unknown(
            state, "post-fix head diff unresolvable (source %r) — full reviewer-deep panel"
            % state.get("_headDiffSource"))
        return
    split = delta_surface.split_fix_surface(
        state.get("_priorReviewedDiff") or state.get("reviewedDiff"),
        state.get("headDiff"), state.get("fixBatch") or [])
    if split.get("unknown"):
        _schedule_full_panel_unknown(state, "delta surface unknown — full reviewer-deep panel")
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
            # Carry the recurrence class keys so the audit-stall breaker's alias-tolerant match
            # (circuit_breaker._audit_outcome_aliases) sees them: a retitled-but-same-class finding
            # must still stall across consecutive not-discharged rounds (#507 v0).
            "classKey": f.get("classKey") or review_memory.class_key(f),
            "dimension": f.get("dimension"),
            "taxonomy": f.get("taxonomy"),
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
    # The DRIVER records the SELECTED independent auditor per target (its own seating decision).
    expected_auditors = {t.get("id"): t.get("auditorVendor")
                         for t in targets if isinstance(t, dict) and t.get("id") is not None}
    # Provenance rests on the ORCHESTRATOR's out-of-band dispatch manifest — {result-id: vendor} the
    # orchestrator recorded from its OWN dispatch records and carried in the submit artifact's
    # `collectionManifest`, NEVER derived from the result contents. The fold authenticates a clearing
    # ruling against THIS manifest (must exist AND equal the recorded selection); the in-result
    # `auditorVendor` echo is advisory only. The driver cannot cryptographically verify engine
    # identity and does not pretend to — the guarantee is exactly as strong as the orchestrator's
    # dispatch manifest (#507 WO-FIX-RECOVERY).
    collection_manifest = artifact.get("collectionManifest")
    if not isinstance(collection_manifest, dict):
        collection_manifest = None
    outcome = audits.apply_audit_results(targets, results, expected_auditors=expected_auditors,
                                         collection_manifest=collection_manifest)
    state["_auditOutcome"] = outcome
    # the audit round for check_audit_breaker: identity + effective ruling PLUS the recurrence class
    # keys the alias-tolerant stall match consumes (#507 v0) — carried straight off each audit entry
    # (audits.apply_audit_results threads them from the target). The `title` MUST ride too: without it
    # the breaker's canonical class key collapses to a title-less `dim::tax::` alias that merges two
    # DISTINCT classKeys sharing dimension/taxonomy into a false stall (#507 R2 v2).
    audit_round = {"round": state["round"], "outcomes": [
        {"identity": a.get("id"), "ruling": a.get("ruling"), "title": a.get("title"),
         "classKey": a.get("classKey"), "dimension": a.get("dimension"),
         "taxonomy": a.get("taxonomy")} for a in outcome["audits"]]}
    state["auditRounds"].append(audit_round)
    for pid in outcome.get("unauthenticated", []):
        _decision(state, "audit-provenance-fail",
                  "audit result for %s could not be authenticated against the orchestrator's "
                  "dispatch manifest (missing entry or wrong vendor) — not-discharged" % pid)
    for pid in outcome.get("echoMismatch", []):
        _decision(state, "audit-echo-mismatch",
                  "audit result for %s echoed a vendor other than the orchestrator's dispatch "
                  "manifest — advisory only; the manifest governed and the discharge stands" % pid)
    # Provenance rests on the orchestrator's dispatch manifest (never the result echo) — recorded
    # per round so the receipt discloses the trust basis (#507 WO-FIX-RECOVERY).
    _record_round(state, "auditProvenance", "collection-manifest")
    _record_round(state, "audits", outcome["audits"])
    _record_round(state, "auditIndependence",
                  targets[0]["independence"] if targets else "n/a")
    state["_newIssues"] = outcome["newIssues"]
    for aid in outcome["notDischarged"]:
        _decision(state, "not-discharged", aid)
    # Scoped-finder routing (#507 WO-R2b). Dispatch the scoped new-finding scan ONLY when the delta
    # split computed a NON-EMPTY new surface (`_newSurface`, set by `_enter_delta_round`). A
    # genuinely empty new surface (`unknown` was False — an unknown surface never reaches audits, it
    # routes to a full panel) SKIPS the scoped dispatch with a receipt-visible note, rather than
    # dispatching a vacuous scan that reviews nothing while looking conformant. The audits' own
    # new-issue candidates still route through the same fold (an empty-artifact `_fold_scoped`).
    if state.get("_newSurface"):
        state["step"] = P_SCOPED
        return
    _record_round(state, "scopedFinder", "skipped-empty-surface")
    _decision(state, "scoped-finder-skipped",
              "scopedFinder: skipped-empty-surface — the delta split computed an empty new "
              "surface; the scoped new-finding scan was skipped (audit new-issues still routed)")
    _fold_scoped(state, config, {})


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
    # Record this delta round in the in-memory ledger and run the challenged-coverage breaker BEFORE
    # any terminal routing: a coverage decision recorded on a wrong principle whose class recurs must
    # park (cannot-certify), never certify as clean (the wrong_principle safety property).
    delta_findings = [f for f in (state.get("findings") or []) if isinstance(f, dict)]
    dim_map = {}
    for f in delta_findings:
        dname = f.get("dimension") or "scoped-finder"
        seat = dim_map.setdefault(dname, {"dimension": dname, "status": "run",
                                          "confidence": "high", "tier": DEEP, "findings": []})
        seat["findings"].append(f)
    if not dim_map:
        dim_map = {"scoped-finder": {"dimension": "scoped-finder", "status": "run",
                                     "confidence": "high", "tier": DEEP, "findings": []}}
    _append_review_record(state, state["round"], "delta", dim_map, delta_findings)
    challenged = _challenged_recurring_halt(state, config)
    if challenged:
        _park_cannot_certify(state, challenged.get("detail"))
        return
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
        # #507 v12: at the audit-round cap, ONLY a latest round with zero not-discharged outcomes and
        # no open blocking finding may certify. An Important still not-discharged (or a new blocker)
        # parks — never certify clean over an unresolved blocker. Owner-accepted residual risk must
        # route through the stall menu's accept-the-disclosed-risk, not this auto-certify.
        if outcome.get("notDischarged") or new_blocking:
            _park_capped_open(state, (breaker.get("detail") or "reached the audit-round cap")
                              + " — blocking finding(s) remain not-discharged; certification withheld")
            return
        _terminal_converged(state, config, full_panel=False, note=breaker.get("detail"))
        return

    # a scoped-finder / new-issue blocking finding OR a not-discharged audit means the round still
    # has work — fix it. #507 v4: the next fix batch is the UNION of the unresolved audit targets and
    # the new blocking findings (deduped by finding identity), so a not-discharged target is NEVER
    # dropped when a new blocker arrives in the same round. Targets carry file/line/severity so the
    # next round's split_fix_surface can re-derive its surface.
    if bool(outcome.get("notDischarged")) or bool(new_blocking):
        nd = set(outcome.get("notDischarged", []))
        nd_targets = [dict(t) for t in (state.get("_auditTargets") or []) if t.get("id") in nd]
        batch = [dict(f) for f in new_blocking]
        # Dedupe on the per-LOCATION key (line-less identity + line), NOT the line-less identity alone:
        # a new blocker sharing a target's file+title at a DIFFERENT line is a DISTINCT finding, so
        # keying on identity alone would silently drop the unresolved audit target (#507 R2 residual-3).
        seen = {(finding_identity(f), f.get("line")) for f in batch}
        for t in nd_targets:
            tid = t.get("id")
            key = (tid, t.get("line"))
            if tid is not None and key not in seen:
                batch.append(t)
                seen.add(key)
        if _route_judgment_blockers(state, batch):
            return
        state["_fixBatch"] = batch
        state["step"] = P_FIXER
        return

    # converged candidate: last round's fixes all discharged + verify pass. Apply the #174
    # confirmation economics before certifying — a Critical surfaced since the last qualifying
    # panel, or cross-cutting rework, owes one more full confirmation panel (budget 2).
    surfaced = list(state.get("surfacedSinceLastPanel") or [])
    # Cross-cutting fires when EITHER the round's own resolving fix is cross-cutting (the single-round
    # signal) OR the UNION of delta rework since the last full panel is (reset in _fold_panel,
    # accumulated in _fold_fixer). The union disjunct is additive — it catches rework that spreads
    # across MULTIPLE post-confirmation fixes where no single fix is broad (#507 R2 residual-5),
    # without ever suppressing a re-arm the single-round signal already earns.
    cross = (review_round_policy.is_cross_cutting(state.get("_changedSubjects"))
             or review_round_policy.is_cross_cutting(state.get("_changedSubjectsSincePanel")))
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


def _park_capped_open(state, detail):
    """The audit-round cap reached with a non-Critical blocker still not-discharged: park, withhold
    certification — never certify clean over an unresolved Important (#507 v12)."""
    state["terminal"] = "capped-with-open-blocker"
    state["certification"] = {"shape": None,
                              "reason": detail or "capped with open blocking findings — park"}
    _decision(state, "capped-with-open-blocker", detail)
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
    full panel — say so). Degraded independence appends -degraded.

    A converge over ANY owner-skipped judgment blocker is CLEAN EXCEPT FOR SKIPPED — never a plain
    success (the exit_skipped invariant): the certification `reason` leads with
    `clean-except-skipped: N blocker(s) skipped with citable reasons` (shape unchanged) so the
    terminal reads unmistakably non-plain, and the skips also ride the top-level receipt channel."""
    # An OUTSTANDING incomplete panel (a configured lens never ran, never recovered by a later
    # complete panel) cannot certify clean — a zero-finding finish over a coverage gap is "we did not
    # look", not "audited-chain". Silence never certifies: withhold + park (#507 R2 residual-1).
    if state.get("_incompletePanel"):
        _park_cannot_certify(
            state, "panel incomplete — a configured lens never ran and no complete panel has since "
            "recovered the coverage; certification withheld")
        return
    base = "full-panel-confirmed" if full_panel else "audited-chain"
    shape = _cert_shape(state, base)
    state["terminal"] = "converged"
    cert = {"shape": shape, "fullPanel": bool(full_panel),
            "independence": "degraded" if _degraded(state) else "independent"}
    if note:
        cert["note"] = note
    skipped = state.get("_skippedBlockers") or []
    if skipped:
        cert["reason"] = ("clean-except-skipped: %d blocker(s) skipped with citable reasons"
                          % len(skipped))
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
                       # The manifest-keyed audit-provenance boundary (LEDGERS §3): a round that ran
                       # fix audits records `collection-manifest` here so the boundary — attestation,
                       # not cryptographic executor identity — is visible at vet, matching the ledger.
                       "auditProvenance": rec.get("auditProvenance"),
                       "scopedFinder": rec.get("scopedFinder"),
                       "headDiffSource": rec.get("headDiffSource"),
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
    # The skipped-blocking channel (#507 R2a): an owner-skipped judgment blocker rides the exit
    # disclosure — a product-choice tradeoff shipped un-fixed, cited by its owner reason. It appears
    # BOTH in the degraded disclosure prose AND as the dedicated top-level `skippedBlockers` list
    # (required by validate_receipt, possibly empty) so the channel can never be omitted.
    skipped_blockers = []
    for s in state.get("_skippedBlockers") or []:
        if not isinstance(s, dict):
            continue
        skipped_blockers.append({"id": s.get("id"), "title": s.get("title"),
                                 "severity": s.get("severity"), "reason": s.get("reason")})
        degraded.append("skipped-blocker: %r (%s:%s) owner-skipped as a product-choice tradeoff — "
                        "reason: %s" % (s.get("title"), s.get("file"), s.get("line"), s.get("reason")))
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
        "skippedBlockers": skipped_blockers,
    }


_RECEIPT_REQUIRED = ("schemaVersion", "verdict", "certificationShape", "rounds", "findings",
                     "decisions", "seatMap", "scriptRan", "degraded", "skippedBlockers")


def validate_receipt(receipt):
    """Validate a driver receipt's SHAPE (NOT grafted onto panel_tally._valid_final_receipt — that
    is the reviewer-seat receipt; this is the loop's terminal receipt). Fail-closed: a receipt
    missing scriptRan or the seat map, or with a non-list rounds/findings/decisions/degraded/
    skippedBlockers, is rejected with a reason. `skippedBlockers` is REQUIRED (possibly empty) so a
    receipt can never omit the skipped-blocking channel (the exit_skipped invariant). Per-round entries
    may carry an `auditProvenance` field (`collection-manifest` when the round ran fix audits) — it is
    ACCEPTED, not required. Returns (ok, reason)."""
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
    for key in ("rounds", "findings", "decisions", "degraded", "skippedBlockers"):
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
        # This library layer IS the orchestrator here: it records its OWN dispatch manifest
        # out-of-band from the auditor's results — {target-id: the vendor it seated}, read straight
        # off the dispatch payload (which the driver stamped), NEVER derived from what the auditor
        # returns. The CLI path carries the real orchestrator's `collectionManifest` in the submit
        # artifact instead (see round-driver.md dispatch-audits). #507 WO-FIX-RECOVERY.
        targets = payload.get("targets") or []
        manifest = {t.get("id"): t.get("auditorVendor")
                    for t in targets if isinstance(t, dict) and t.get("id") is not None}
        return {"results": seams["auditor"](payload.get("targets"), state["round"]),
                "collectionManifest": manifest}
    if action == P_SCOPED:
        return {"findings": _reviewer_findings(
            seams["reviewer"]("scoped-finder", DEEP, state["round"], payload))}
    if action == P_VERIFY:
        return {"result": seams["verify_runner"](payload.get("command"), state["round"])}
    if action == P_FIXER:
        return seams["fix_step"](payload.get("batch"), state["round"], payload)
    if action == P_JUDGMENT:
        gate = io.get("judgment_gate") if isinstance(io, dict) else None
        if callable(gate):
            return gate(payload)
        # No gate wired → fail closed, fix every judgment finding as suggested (never auto-skip).
        return {"dispositions": [{"id": f.get("id"), "disposition": "fix-as-suggested"}
                                 for f in (payload.get("findings") or [])]}
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
    if state.get("_resumeCorrupt"):
        # A corrupt/mangled resume state fails closed — never certify off unreadable memory.
        _park_cannot_certify(state, state["_resumeCorrupt"])
        state["_scriptRan"] = {"invocations": 0, "byPhase": {}}
        return build_receipt(state)
    guard = 0
    try:
        while not state.get("terminal") and guard < _RUN_LOOP_GUARD:
            guard += 1
            step = _advance(state, state["config"])
            action = step["action"]
            if action == P_TERMINAL:
                break
            # handle the gap-sweep re-entry (verifiers → synthesis carries the merge back).
            artifact = _run_seam(seams, action, step["payload"], state, state["config"])
            _fold(state, state["config"], action, artifact, seams.get("changed_subjects"))
            # a delta round routes scoped candidates through verifiers; when that path is armed the
            # synthesis fold must re-settle the delta rather than the round-1 path.
            if state.pop("_settleDeltaAfterSynthesis", False):
                pass
    except JournalFaultUnrecordable as jf:
        # Last-resort fail-closed: a journal fault the driver could not even record parks
        # cannot-certify — the library layer NEVER continues (or crashes the caller) as though the
        # ran-evidence were intact. #507 WO-FIX-RECOVERY.
        _park_cannot_certify(state, "journal-fault-unrecordable: %s" % jf)
        state["_scriptRan"] = {"invocations": guard, "byPhase": {}}
        return build_receipt(state)
    if guard >= _RUN_LOOP_GUARD and not state.get("terminal"):
        state["terminal"] = "halted"
        state["certification"] = {"shape": None, "reason": "run_loop guard tripped — fail closed"}
    state["_scriptRan"] = {"invocations": guard, "byPhase": {}}
    return build_receipt(state)


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
        # A REPLAYED terminal `next` re-emits the stored terminal pending WITHOUT re-running
        # _finalize_receipt — so re-verify the on-disk receipt (fault marker + fresh re-read +
        # validate_receipt) here, else a fault recorded/surfaced since the first emission is masked
        # by the replay's ok (#507). Any fault → fail-loud receipt-fault, never terminal-with-ok. The
        # gate re-verifies from disk (never re-writes) so a fault stays durable across invocations.
        if pend.get("phase") == P_TERMINAL:
            fault = _terminal_receipt_gate(session_dir, state)
            if fault:
                return _receipt_fault_response(fault)
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
        fail = _terminal_receipt_gate(session_dir, state)
        if fail:
            return _receipt_fault_response(fail)
    return _next_response(pending, state_hash(state))


def _receipt_fault_response(detail):
    """A terminal receipt integrity fault — the fail-loud `receipt-fault` family (the same family as
    `journal-fault-unrecordable`). Answered on the terminal `next` (first emission or a replay) and
    the terminating `submit`; the CLI surfaces it NONZERO and it is NEVER a `terminal`-with-ok."""
    return {"ok": False, "reason": "receipt-fault", "detail": detail}


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
    prior = state.get("lastAccepted")
    is_duplicate = bool(prior and prior.get("phase") == phase and prior.get("attempt") == attempt
                        and prior.get("artifactHash") == art_hash)

    # CLASS invariant (#507, third audit): while the session is ALREADY at its terminal phase on
    # entry, NO submit answer — including a duplicate/replayed submit — may return ok without a FRESH
    # on-disk receipt verification. Route every terminal-phase submit through the gate before any
    # answer; a persisted or freshly-detected fault answers receipt-fault nonzero (the duplicate flag
    # preserved in the detail for honesty), never a masked ok. (The terminating submit itself reaches
    # terminal via THIS call's fold below, gated at its own site.)
    if state.get("terminal"):
        fault = _terminal_receipt_gate(session_dir, state)
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": prior.get("round") if prior else None,
                                          "attempt": attempt,
                                          "outcome": "duplicate-receipt-fault" if is_duplicate
                                          else "terminal-receipt-fault"})
            resp = _receipt_fault_response(
                ("duplicate submit replay; %s" % fault) if is_duplicate else fault)
            if is_duplicate:
                resp["duplicate"] = True
            return resp

    # duplicate detection (an already-accepted submit re-sent — its state hash is now stale, but the
    # phase/attempt/artifact triple identifies it as an exact replay). At a terminal phase the gate
    # above already re-verified the receipt, so this only answers ok when the receipt is intact.
    if is_duplicate:
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
    # The state-hash echo is the anti-stale/fork fence — REQUIRED (#507 v13). A first-time fold with
    # no hash is refused (a missing hash must never fold fail-open); exact replays are already
    # returned as duplicates above, before this point.
    if state_hash_arg is None:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": pending.get("round"), "attempt": attempt,
                                      "outcome": "missing-hash"})
        return {"ok": False, "reason": "state-hash is required — refusing a fold without the "
                                       "expected hash echo (the anti-stale/fork fence)"}
    current_hash = state_hash(state)
    if state_hash_arg != current_hash:
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
        fail = _terminal_receipt_gate(session_dir, state)
        if fail:
            return _receipt_fault_response(fail)
    return {"ok": True, "round": round_no, "phase": phase, "nextStep": state.get("step")}


def _write_receipt(session_dir, state):
    """Write the terminal receipt atomically. OSError PROPAGATES — a receipt-write failure is itself
    a receipt defect the CLI must surface (see _finalize_receipt), never a silent swallow (#507
    v14)."""
    receipt = build_receipt(state, session_dir)
    path = os.path.join(session_dir, RECEIPT_FILE)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)
    return receipt


def _verify_terminal_receipt(session_dir):
    """Re-read the on-disk terminal receipt (FRESH from disk, never a cached copy) and re-check its
    integrity: readable, `validate_receipt`-shaped, non-empty scriptRan, and NO durable journal
    fault marker. Returns a reason string on ANY fault, else None.

    Shared by `_finalize_receipt` (the post-write check on the terminating fold / first emission) and
    the terminal-`next` re-check (below). A REPLAYED terminal `next` — a `next` on a session already
    at its terminal step — re-emits the stored pending WITHOUT re-running `_finalize_receipt`, so a
    receipt fault recorded or surfaced AFTER the receipt was first written (a fault-marker file, or a
    round-receipt.json that has become unreadable/invalid since) would otherwise be masked by the
    replay's `ok`. Re-checking here on every terminal `next` closes that hole (#507)."""
    try:
        with open(os.path.join(session_dir, RECEIPT_FILE), encoding="utf-8") as fh:
            on_disk = json.load(fh)
    except (OSError, ValueError) as exc:
        return "terminal receipt unreadable (%s) — cannot certify; treat as park" % exc
    ok, why = validate_receipt(on_disk)
    if not ok:
        return "terminal receipt invalid (%s) — cannot certify; treat as park" % why
    if not (on_disk.get("scriptRan") or {}).get("invocations"):
        return ("terminal receipt scriptRan is empty — the journal (the driver's ran evidence) did "
                "not persist; cannot certify; treat as park")
    if _journal_faulted(session_dir):
        return ("driver journal recorded a write fault — the scriptRan evidence is incomplete "
                "(a next/submit event was lost); cannot certify; treat as park")
    return None


def _finalize_receipt(session_dir, state):
    """At a terminal, write + read back + validate the on-disk receipt. A write failure, an
    unreadable readback, an invalid shape, or an EMPTY scriptRan (the journal — the driver's `ran`
    evidence — did not persist) is a RECEIPT DEFECT: return a reason so the CLI fails closed (the
    orchestrator must treat it as a park), never certifying on a missing/short receipt (#507 v14).
    Returns None on success."""
    try:
        _write_receipt(session_dir, state)
    except OSError as exc:
        return "terminal receipt write failed (%s) — cannot certify; treat as park" % exc
    return _verify_terminal_receipt(session_dir)


def _terminal_receipt_gate(session_dir, state):
    """The single terminal-answer gate — WRITE-ONCE, then RE-VERIFY-FROM-DISK forever. The FIRST
    terminal answer (whichever fires first: the terminating `submit` fold or the first terminal
    `next`) writes + verifies the receipt via `_finalize_receipt` and marks it finalized. EVERY later
    terminal invocation re-verifies the ON-DISK receipt via `_verify_terminal_receipt` and NEVER
    re-writes it.

    So a receipt fault detected at ANY terminal answer is DURABLE across invocations: a re-write from
    in-memory state can never overwrite a faulted receipt into an ok one — the auditor's path was a
    fault produced at the terminating `submit` (e.g. the receipt write failed) being masked by a
    later replayed `next` that re-wrote the receipt from state and answered ok. Once finalized, only a
    genuinely valid ON-DISK receipt (re-read fresh each call) clears the fault; a state overwrite
    cannot. Returns a fault detail string or None, persisting the finalized mark and the durable
    `_receiptFault` detail so the durability survives across separate CLI processes (#507).

    INVARIANT (#507, third audit): no terminal-phase invocation — first-emission next, replayed next,
    terminating submit, or a duplicate/replayed submit — may answer ok without a fresh on-disk receipt
    verification through this gate, no exceptions."""
    if state.get("_receiptFinalized"):
        fault = _verify_terminal_receipt(session_dir)
    else:
        fault = _finalize_receipt(session_dir, state)
        state["_receiptFinalized"] = True
    state["_receiptFault"] = fault or None
    save_state(session_dir, state)
    return fault


def _parse_vendors(raw):
    """Parse the `--vendors` CLI value. Accepts BOTH a JSON list ('["codex","cursor"]') and a
    comma-separated string ('codex,cursor'). Returns (vendors, None) on success or (None, reason)
    on ANY failure — an unparseable JSON, an empty result, non-string members, or an unknown vendor
    all fail loud so the CLI can exit nonzero. NEVER falls through to the ["claude"] default
    silently: a silent fall-through drops cross-vendor independence and stamps every audit degraded
    when other vendors are actually live (same fail-open class as the v14 journal-swallow, #507)."""
    stripped = raw.strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except ValueError:
            return None, "vendors-unparseable"
        if not isinstance(parsed, list):
            return None, "vendors-unparseable"
        members = parsed
    else:
        members = stripped.split(",")
    cleaned = []
    for member in members:
        if not isinstance(member, str):
            return None, "vendors-unparseable"
        member = member.strip()
        if member:
            cleaned.append(member)
    if not cleaned:
        return None, "vendors-unparseable"
    for member in cleaned:
        if member not in model_registry.VENDORS:
            return None, "vendors-unknown: %s" % member
    return cleaned, None


def main(argv=None):
    parser = argparse.ArgumentParser(description="the one-entrypoint review-loop round driver (#507)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pn = sub.add_parser("next")
    pn.add_argument("--session-dir", required=True)
    pn.add_argument("--leg", default=None)
    pn.add_argument("--vendors", default=None,
                    help="live vendors (fresh state only): a JSON list ('[\"codex\",\"cursor\"]') "
                         "OR a comma-separated string ('codex,cursor'). Unparseable / unknown / "
                         "on non-fresh state → fails loud (nonzero), never a silent default")
    pn.add_argument("--fixer-vendor", default=None,
                    help="the ACTUAL fix-implementer vendor (fresh state only): the auditor is seated "
                         "as a DIFFERENT vendor, so a wrong value labels a self-audit independent. "
                         "Unknown vendor / on non-fresh state → fails loud (nonzero), never a silent "
                         "default")
    pn.add_argument("--verify-command", default=None)
    pn.add_argument("--max-rounds", type=int, default=None)
    pn.add_argument("--diff-path", default=None, help="round-1 reviewed diff (fresh state only)")
    pn.add_argument("--prior-comments", default=None,
                    help="PR-mode prior review comments JSON (a list) for the author-justification "
                         "post-filter (fresh state only)")

    ps = sub.add_parser("submit")
    ps.add_argument("--session-dir", required=True)
    ps.add_argument("--phase", required=True)
    ps.add_argument("--attempt", type=int, required=True)
    ps.add_argument("--state-hash", default=None)
    ps.add_argument("--artifact", required=True, help="path to the artifact JSON")

    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except JournalFaultUnrecordable as jf:
        # Last-resort fail-loud: the journal AND its fault marker were both unwritable — there is no
        # silent tier below this. The CLI invocation itself FAILS: the reason to stdout, the
        # underlying errors to stderr, nonzero exit. #507 WO-FIX-RECOVERY.
        sys.stdout.write(json.dumps({"ok": False, "reason": "journal-fault-unrecordable",
                                     "detail": str(jf)}) + "\n")
        sys.stderr.write("journal write error: %s\nfault-marker write error: %s\n"
                         % (jf.journal_error, jf.marker_error))
        return 1


def _dispatch(args):
    if args.cmd == "next":
        overrides = {}
        if args.leg:
            overrides["leg"] = args.leg
        if args.vendors is not None:
            vendors, reason = _parse_vendors(args.vendors)
            if reason is not None:
                sys.stdout.write(json.dumps({"ok": False, "reason": reason,
                                             "value": args.vendors}) + "\n")
                return 1
            # `--vendors` can only take effect on FRESH state — the config is read ONCE at
            # new_state; a later `next` on existing state would silently ignore it. Reject loudly
            # rather than accept a flag that cannot take effect (#507).
            st_ok, st = load_state(args.session_dir)
            if not (st_ok and st is None):
                sys.stdout.write(json.dumps({"ok": False, "reason": "vendors-not-fresh-state",
                                             "value": args.vendors}) + "\n")
                return 1
            overrides["vendors"] = vendors
        if args.fixer_vendor is not None:
            # The fixer vendor is read ONCE at new_state and drives the independent-auditor seating —
            # an unknown vendor or a later `next` on existing state that silently ignored it would
            # mislabel a self-audit independent. Reject loudly, same discipline as `--vendors` (#507).
            fixer = args.fixer_vendor.strip()
            if fixer not in model_registry.VENDORS:
                sys.stdout.write(json.dumps({"ok": False, "reason": "fixer-vendor-unknown",
                                             "value": args.fixer_vendor}) + "\n")
                return 1
            st_ok, st = load_state(args.session_dir)
            if not (st_ok and st is None):
                sys.stdout.write(json.dumps({"ok": False, "reason": "fixer-vendor-not-fresh-state",
                                             "value": args.fixer_vendor}) + "\n")
                return 1
            overrides["fixerVendor"] = fixer
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
        if args.prior_comments:
            # Load + validate the PR-mode prior comments into `priorComments` so the
            # author-justification post-filter is actually reachable (#507 v7). A missing / unreadable
            # / non-list file leaves priorComments unset (the filter simply does not fire) — never a
            # crash and never a silent drop.
            try:
                with open(args.prior_comments, encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, list):
                    overrides["priorComments"] = loaded
            except (OSError, ValueError):
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
    # A terminal receipt integrity fault fails LOUD: nonzero exit, the same fail-loud family as
    # journal-fault-unrecordable (a masked-by-replay receipt fault must never look like a clean exit).
    return 1 if out.get("reason") == "receipt-fault" else 0


if __name__ == "__main__":
    sys.exit(main())
