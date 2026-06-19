# plugins/workhorse/lib/journal.py
"""events.jsonl (the append-only audit log) + resume-brief.md — the two §7-deferred
schemas this slice AUTHORS — plus the ⑧ CI-bound replay.

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
    "run_completed",
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
    n = 0
    try:
        with open(events_path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    n += 1
    except OSError:
        pass
    return n + 1


def append(events_path, event_type, *, step=None, detail=None, world=None,
           payload=None, root=None, ts=None):
    os.makedirs(os.path.dirname(os.path.abspath(events_path)), exist_ok=True)
    ev = {"ts": _stamp(ts), "seq": _next_seq(events_path), "type": event_type}
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
    fd = os.open(events_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line)
        os.fsync(fd)          # durable: the write-ahead ci_fix_attempt must survive a crash
    except OSError as exc:
        # A failed durable write (e.g. ENOSPC) must NOT crash the orchestrator mid-step.
        # append is write-ahead (before the ⑧ push), so surfacing it -> the orchestrator
        # PARKS before the push -> no under-count. Caller catches this (Task 11).
        raise DurableWriteError("event append failed: %s" % exc) from exc
    finally:
        os.close(fd)


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


def ci_attempts(events_path):
    """Replay the write-ahead ci_fix_attempt events. CONSERVATIVE TAIL (design §2/§9): a
    torn trailing line MIGHT be a ci_fix_attempt, so it counts as +1 (over-count,
    fail-safe — the ⑧ bound trips EARLIER, never bypassed by a crash-loop)."""
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
        "- PR: %s" % (w.get("pr") if not isinstance(w.get("pr"), dict)
                      else ("ready" if not w["pr"].get("isDraft") else "draft")),
        "- CI: %s" % w.get("ci", "not detected"),
        "- dev server: %s" % w.get("dev_server", "—"),
        "- seeded baseline empty: %s" % w.get("seeded_empty", "—"), "",
        "## Next",
        "- resume from step after **%s**" % c.get("lastGoodStep"), "",
        "## Notices",
    ]
    lines += (["- %s: %s" % (e.get("type"), _scrub(e.get("detail", ""), root))
               for e in notices] or ["- none"])
    control_plane.atomic_write(brief_path, "\n".join(lines) + "\n")
