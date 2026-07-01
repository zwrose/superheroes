# plugins/superheroes/lib/ship_reconcile.py
"""Pure push-reconcile decider (UFR-6 call-site 1): given the local integrated HEAD, the remote PR
head (or None if unreadable), the branch, and an injected push_fn, route through the generic
idempotency primitive — already-in-sync is a no-op, local-ahead applies the push, an unreadable
remote fails closed. The gh/git IO stays in the ship_phase leaf; this only decides."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import idempotent_write


def reconcile_head(local, remote, branch, push_fn):
    """local: the worktree's local HEAD (the integrated head the remote must match).
    remote: the PR's current remote head SHA, or None (unreadable -> fail closed).
    branch: the work-item's branch ("" -> cannot push).
    push_fn: () -> bool — performs the non-force push + read-back-confirm; called only when local-ahead.
    Returns the idempotent_apply result dict {key, already, applied, ok, reason, detail}."""
    def _reader():
        if remote is None:
            return (None, "remote PR head unreadable")
        return (remote == local, "remote=%s local=%s" % (remote, local))

    def _apply():
        if not branch:
            return (False, "no branch recorded — cannot push")
        return (bool(push_fn()), "pushed")

    return idempotent_write.idempotent_apply("head=%s" % local, _reader, _apply)
