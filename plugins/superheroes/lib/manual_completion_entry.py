# plugins/superheroes/lib/manual_completion_entry.py
"""#450 manual-completion receipt — IO leaf. Invoked by a session at HAND-FINISH, after it took
over a PARKED run and drove it to a reviewed, ready PR outside the spine:

    python3 manual_completion_entry.py --work-item <slug> --pr N [--head-sha SHA] [--note "..."]

Records the two durable facts that stop the record from reading "parked, never resumed": a
terminal `manual_completion` journal event AND the checkpoint's `phase` advanced to
`shipped-manual` (with the shipped PR). Idempotent (a second call on an already-terminal record is
a no-op) and fail-closed on an incompatible durable checkpoint (never overwrite a shape this code
doesn't understand). Emits a single JSON line on stdout (the courier/exec dumb-pipe contract)."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkpoint as ckpt_lib
import control_plane
import journal
import manual_completion as mc
import readout


def _journal_receipt(events_path):
    """The last `manual_completion` receipt already in the journal, or None. Fail-safe to None on
    any read error. This is the SECOND idempotency carrier (besides the checkpoint marker): the
    checkpoint write happens AFTER the journal append, so a retry following a checkpoint-write
    failure would otherwise re-append a duplicate receipt (the checkpoint is still non-terminal).
    Keying idempotency on the durable append itself closes that gap."""
    try:
        evs = journal.read_events(events_path)
    except Exception:   # noqa: BLE001 — a missing/unreadable journal simply means "no receipt yet"
        return None
    receipts = [e for e in evs if isinstance(e, dict) and e.get("type") == mc.EVENT_TYPE]
    return receipts[-1] if receipts else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-item", required=True)
    ap.add_argument("--pr", required=True, help="the shipped PR number (or URL)")
    ap.add_argument("--url", default=None, help="the PR URL, when --pr is a bare number")
    ap.add_argument("--head-sha", default=None, help="the shipped HEAD sha (audit provenance)")
    ap.add_argument("--note", default=None, help="free-text hand-finish note (scrubbed before it is written)")
    a = ap.parse_args(argv)

    root = os.getcwd()
    paths = control_plane.paths(root, a.work_item)

    cp = ckpt_lib.read(paths["checkpoint"])
    if isinstance(cp, dict) and cp.get("_incompatible"):
        # Fail closed: an unknown/newer durable checkpoint must never be overwritten blindly, and
        # NO receipt is journaled over a record this code can't read.
        print(json.dumps({"ok": False,
                          "error": "checkpoint incompatible: %s" % cp.get("reason", "unknown reason")}))
        return 0

    # A fully-terminal checkpoint means a prior invocation converged completely — a genuine no-op.
    if mc.is_manually_completed(cp):
        print(json.dumps({"ok": True, "already": True, "checkpointWritten": True,
                          "pr": (cp or {}).get("pr")}))
        return 0

    # A PR number is stored/rendered as an int when it is one (truthful, and the record readers key
    # on pr.number); a URL or non-numeric ref is passed through as-given.
    pr = a.pr
    if isinstance(pr, str) and pr.strip().isdigit():
        pr = int(pr.strip())
    url = a.url

    # Idempotency across a partial-failure retry: the checkpoint write happens AFTER the journal
    # append, so a retry following a checkpoint-write failure finds a receipt ALREADY in the journal
    # while the checkpoint is still non-terminal. In that case do NOT append a second receipt — but
    # DO retry the checkpoint advance so the record fully converges. The durable receipt is the
    # source of truth for the PR, so reuse it (a retry with different args never rewrites history).
    prior = _journal_receipt(paths["events"])
    if prior is not None:
        already = True
        pr = (prior.get("payload") or {}).get("pr", pr)
    else:
        already = False
        # The free-text note is a durable field → scrub it FAIL-CLOSED before it reaches the payload
        # (journal writes `payload` as-is, so the scrub can't happen inside append for a payload).
        note = None
        if a.note:
            note, _ok = readout.scrub(a.note, root=root)
        payload = mc.build_payload(pr, head_sha=a.head_sha, note=note)
        # Durable journal event first (the terminal receipt). A failed durable write is fail-closed —
        # surface it and change nothing (the record stays as it was, honestly parked).
        try:
            journal.append(paths["events"], mc.EVENT_TYPE, payload=payload, root=root)
        except journal.DurableWriteError as e:
            print(json.dumps({"ok": False, "error": "durable journal write failed: %s" % e}))
            return 0

    # Advance the checkpoint to the terminal phase. Read-or-mint (fail-soft #327: a missing
    # checkpoint still yields a truthful terminal record rather than a crash). The event is already
    # journaled, so even a checkpoint-write failure leaves the run reading "completed".
    base = cp if isinstance(cp, dict) else ckpt_lib.new(a.work_item, "")
    terminal = mc.advance_checkpoint(base, pr, url=url)
    try:
        ckpt_lib.write(paths["checkpoint"], terminal)
    except OSError as e:
        print(json.dumps({"ok": True, "already": already, "checkpointWritten": False,
                          "error": "checkpoint write failed: %s" % e, "pr": terminal.get("pr")}))
        return 0

    print(json.dumps({"ok": True, "already": already, "checkpointWritten": True,
                      "pr": terminal.get("pr")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
