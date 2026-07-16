# plugins/superheroes/lib/journal.py
"""events.jsonl (the append-only audit log) + resume-brief.md — the two §7-deferred
schemas this slice AUTHORS — plus the step 8 CI-bound replay.

Durable-write contract (design §4.2): every free-text field (detail, world facts)
passes through readout.scrub FAIL-CLOSED before it is written; a structured `payload`
(CI check signatures — not secrets) is written as-is. Appends are single O_APPEND
writes of one small line under the §4.5 single-writer model; a tolerant reader skips
a torn trailing line. The CI round count is reconstructed by replaying ci_fix_attempt
events (written write-ahead, so a crash over-counts — fail-safe — never under-counts).
"""
import json
import os
import time

import control_plane
import readout   # the band scrub seam

EVENT_TYPES = {
    "run_started", "step_entered", "step_completed", "notify", "gate", "error",
    "resumed", "lease_acquired", "lease_reclaimed", "ci_fix_attempt", "parked",
    "run_completed", "phase_record", "external_dispatch",
    # #130 token telemetry: per-phase cost accounting (dispatches + output tokens). Additive to the
    # §4.6 vocabulary (no schemaVersion bump); the structured `payload` is non-secret and written
    # as-is, kept SEPARATE from phase_record (whose payloads are equality-deduped for idempotency).
    "phase_cost",
    # #25 quick discovery: the front-half phases a quick-route run skips (plan/review-plan/tasks/
    # review-tasks), recorded ONCE at intake so they are never silently absent from the audit trail.
    # Structured non-secret `payload` ({route, skipped, entryPhase}), written as-is; run_watch renders it.
    "phases_skipped",
    # #149 permission posture: a bounded ask that timed out and degraded (UFR-3) — non-secret
    # structured payload, disclosed in the readout.
    "permission_denied",
    # #149 auditability NFR ("every automatic allowance or timeout denial made during a run is
    # visible in that run's records"): an AUTO-ALLOWANCE the below-the-floor allowance layer
    # fired (denials already ride permission_denied). Structured non-secret `payload`
    # ({reason, command_sha256, cwd, session_id, run_id}), written as-is — the command HASH
    # (first 16 hex of sha256), never the raw command text (which may embed tokens/secrets).
    # #379: `session_id` (the triggering session) + `run_id` make attribution auditable, and an
    # event that belongs to no live run's session is written to the checkout-level
    # `allowances.jsonl` trail (same event shape) instead of a run's events.jsonl.
    "allowance_fired",
    # #381 whole-branch final review: auditable handoff to review-code when the one-pass cap surfaces
    # blockers, the fix batch lands, and post-fix verify is green. Structured non-secret `payload`
    # ({branch, open_findings, fix_dispatched, ...}), written as-is; run_watch may render it.
    "final_review_handoff",
    # #397 doc-review legibility: a tasks-review non-blocking finding routed to the journal
    # (FR-4), never into build instructions (FR-5). Structured non-secret payload, written as-is.
    "routed_forward",
    # #397 FR-15: the per-review convergence record — rounds used, per-round blocking vs
    # routed-forward counts, and the outcome — at every doc-review terminal.
    "review_convergence",
    # #397 FR-3 receipt: the tasks phase journaled that it was handed the plan review's
    # hand-off list (or, per UFR-5, that it could not be read).
    "handoff_provided",
    # #402 Part B: a courier/exec dispatch whose answer carried a classifier-denial signature — the
    # bytes are declined TERMINALLY (never re-dispatched identically), and the caller's fail-closed
    # path (park/disclose) takes over. Recorded next to the enforcer's allowance_fired so the run's
    # audit trail shows the decline. `detail` = {"reason": <scrubbed>} — the reason is already
    # base64-redacted + length-clamped by courier_exec.denialReason and is scrubbed again here.
    "courier_declined",
    # #450 manual-completion receipt: a PARKED run that was finished BY HAND (native gate, PR,
    # review, ready-flip) outside the spine records this TERMINAL event so the record stops
    # reading "parked, never resumed" when the truth is "manually completed to PR #N" (epic #327).
    # Structured non-secret `payload` ({pr, headSha?, note?}) written as-is — the free-text note is
    # scrubbed by its writer (manual_completion_entry) BEFORE it reaches the payload. Additive to
    # the vocabulary (no schemaVersion bump); manual_completion.py is its sole writer.
    "manual_completion",
    # #350 Part B (the silent re-execution disclosure): a re-execute-and-discard decision — the spine
    # re-runs an expensive, non-idempotent dispatch and DISCARDS a completed answer — records this
    # LOUD event so a finding raised then dropped is never silent (the 2026-07-11 #219 round-4
    # signature). Structured non-secret `payload` carries the CAUSE (why the re-dispatch fired) and
    # the discarded result's summary/hash (findings count + a sha256 of the discarded answer); written
    # as-is. Additive to the vocabulary (no schemaVersion bump).
    "dispatch_retried",
}


class DurableWriteError(RuntimeError):
    """A durable write (event append) failed — likely a disk problem. The orchestrator
    parks (fail-closed) rather than continue without durable state."""


def _stamp(ts=None):
    return ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _scrub(text, root):
    if text in (None, ""):
        return ""
    out, _ok = readout.scrub(str(text), root=root)   # fail-closed: out is a note on failure
    return out


def _next_seq(events_path):
    # Dense, monotonic seq = (successfully-parsed events) + 1. Counting via read_events
    # (which skips a torn trailing line) keeps the sequence GAPLESS after a crash, rather
    # than consuming a number for the discarded torn partial.
    return len(read_events(events_path)) + 1


def append(events_path, event_type, *, step=None, detail=None, world=None,
           payload=None, root=None, ts=None, dense_seq=True, idem=None):
    # Fail closed on an unknown event type: a typo'd "ci_fix_attempt" would be silently
    # ignored by ci_attempts() and UNDER-count the step 8 bound (inverting the over-count
    # fail-safe). Parking on it (the orchestrator catches DurableWriteError) is safe.
    if event_type not in EVENT_TYPES:
        raise DurableWriteError("unknown event type: %r" % event_type)
    # #350 Part A (the doubled-line signature): a journal append is NOT idempotent, so a courier-chain
    # retry (_execJson re-runs journal_entry.py after a stdout-drop, even though the first append
    # landed) doubles the line. An `idem` key makes the repeated append a NO-OP: if an event already
    # carries this key, return without writing. Only the SINGLE-writer run journal passes idem (never
    # the #379 multi-writer trail), so no concurrent writer can interleave between this read and the
    # O_APPEND below (§4.5). The key is a per-dispatch nonce (never content-derived), so two
    # genuinely-distinct events with byte-identical payloads still each write under distinct nonces.
    if idem is not None:
        for e in read_events(events_path):
            if isinstance(e, dict) and e.get("idem") == idem:
                return
    ev = {"ts": _stamp(ts)}
    if dense_seq:
        # Dense, monotonic seq for a SINGLE-writer run journal. Skipped (dense_seq=False) for a
        # MULTI-writer file — the #379 checkout-level allowance trail: a read-derived seq is
        # unreliable under concurrent writers anyway, and computing it re-reads the whole file on
        # every append (_next_seq → read_events), an O(n^2) cost on the synchronous PreToolUse
        # hook path as the trail grows over the checkout's life (premortem-001). A seq-less event
        # orders by `ts`; consumers that read seq use `.get("seq")` and tolerate its absence.
        ev["seq"] = _next_seq(events_path)
    ev["type"] = event_type
    # #350 Part A: the idempotence key rides top-level (like `seq`) so the `payload` stays byte-
    # identical for consumers; written right after `type` so a hand-read line shows it early.
    if idem is not None:
        ev["idem"] = idem
    if step is not None:
        ev["step"] = step
    if detail is not None:
        ev["detail"] = _scrub(detail, root)
    if world is not None:
        ev["world"] = {k: (_scrub(v, root) if isinstance(v, str) else v)
                       for k, v in world.items()}
    if payload is not None:
        ev["payload"] = payload
    line = (json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")
    # The ENTIRE durable write — makedirs, open, write, fsync — is fail-closed: ANY OSError
    # (ENOSPC during inode/dir allocation, EACCES, a vanished dir) surfaces as
    # DurableWriteError so the orchestrator PARKS (Task 11) instead of crashing uncaught
    # mid-step. append is write-ahead (before the step 8 push), so parking -> no under-count.
    try:
        os.makedirs(os.path.dirname(os.path.abspath(events_path)), exist_ok=True)
        fd = os.open(events_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
            os.fsync(fd)          # durable: the write-ahead ci_fix_attempt must survive a crash
        finally:
            try:
                os.close(fd)      # don't let a close error mask the original write/fsync OSError
            except OSError:
                pass
    except OSError as exc:
        raise DurableWriteError("event append failed: %s" % exc) from exc


def read_events(events_path, *, want_torn_tail=False):
    """Parse events. Only the LAST line may legitimately be torn (a crash mid-append
    under the single-writer model); interior unparseable lines are skipped. With
    `want_torn_tail`, also return whether the trailing line was torn."""
    evs, torn_tail = [], False
    try:
        with open(events_path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return ([], False) if want_torn_tail else []
    last = len(lines) - 1
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        try:
            evs.append(json.loads(s))
        except ValueError:
            if i == last:
                torn_tail = True      # a torn TRAILING line — counted conservatively below
    return (evs, torn_tail) if want_torn_tail else evs


def permission_denied_events(events_path):
    """The parsed `permission_denied` journal events — the SINGLE reader of that literal type
    (architecture-001). Fail-safe to `[]` on any read error (a denial carrier that could clear a
    real denial on an I/O hiccup would be worse than useless). Callers each apply their own
    secondary filter/shape: ship_gate.journal_build_denials keeps only `build:` steps as the gate
    carrier; run_readout._permission_denials projects every one as a disclosure entry."""
    try:
        evs = read_events(events_path)
    except Exception:
        return []
    return [ev for ev in evs
            if isinstance(ev, dict) and ev.get("type") == "permission_denied"]


def ci_attempts(events_path):
    """Replay the write-ahead ci_fix_attempt events. CONSERVATIVE TAIL (design §2/§9): a
    torn trailing line MIGHT be a ci_fix_attempt, so it counts as +1 (over-count,
    fail-safe — the step 8 bound trips EARLIER, never bypassed by a crash-loop)."""
    evs, torn = read_events(events_path, want_torn_tail=True)
    rounds, history = 0, []
    for ev in evs:
        if ev.get("type") == "ci_fix_attempt":
            rounds += 1
            failing = (ev.get("payload") or {}).get("failing")
            if isinstance(failing, list):
                history.append(failing)
    if torn:
        rounds += 1   # conservative over-count for an indeterminate trailing line
    return rounds, history


def render_brief(brief_path, checkpoint, world, events_path, *, root=None):
    c, w = checkpoint or {}, world or {}
    evs = read_events(events_path)
    started = next((e["ts"] for e in evs if e.get("type") == "run_started"), "?")
    resumes = sum(1 for e in evs if e.get("type") == "resumed")
    notices = [e for e in evs if e.get("type") in ("notify", "gate", "parked")]
    pr = c.get("pr") or {}

    def _wf(v, default):
        # World facts are a durable free-text field (design §4.2/§8.1): scrub string
        # values fail-closed before they land in the brief; None -> the absent sentinel.
        if v is None:
            return default
        if isinstance(v, str):
            return _scrub(v, root) or default
        return v

    lines = [
        "# Workhorse resume brief", "",
        "## Run",
        "- work-item: %s" % c.get("workItem", "?"),
        "- branch: %s" % c.get("branch", "?"),
        "- PR: %s" % (pr.get("url") or "—"),
        "- started: %s · resumes: %d" % (started, resumes), "",
        "## Where it was",
        "- phase **%s**, last good step **%s**" % (c.get("phase", "?"), c.get("lastGoodStep")), "",
        "## Confirmed done",
        "- PR: %s" % (("ready" if w["pr"].get("isDraft") is False else "draft")
                      if isinstance(w.get("pr"), dict) else _wf(w.get("pr"), "—")),
        "- CI: %s" % _wf(w.get("ci"), "not detected"),
        "- dev server: %s" % _wf(w.get("dev_server"), "—"),
        "- seeded baseline empty: %s" % _wf(w.get("seeded_empty"), "—"), "",
        "## Next",
        "- resume from step after **%s**" % c.get("lastGoodStep"), "",
        "## Notices",
    ]
    lines += (["- %s: %s" % (e.get("type"), _scrub(e.get("detail", ""), root))
               for e in notices] or ["- none"])
    control_plane.atomic_write(brief_path, "\n".join(lines) + "\n")
