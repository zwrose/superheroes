# plugins/superheroes/lib/buildtree.py
"""Managed build-worktree lifecycle for Workhorse: the deterministic path under the
managed root, reuse/reclaim of a clean worktree, a durable record of outstanding
worktrees, and tiered teardown gated by pure fail-closed decisions. Modeled on
devserver.py (pure helpers + idempotent, never-raising effectful ops). All destructive
logic lives in the pure decision functions; the effectful shell only executes a
pre-computed decision.
"""
import json
import os
import subprocess

import control_plane


def managed_root(root=None):
    """The managed-worktree root: ~/.superheroes-worktrees by default, overridable via
    SUPERHEROES_WORKTREES_ROOT (the store_root() pattern) or an explicit root."""
    if root is not None:
        return os.path.realpath(os.path.expanduser(root))
    return os.path.realpath(os.path.expanduser(
        os.environ.get("SUPERHEROES_WORKTREES_ROOT", "~/.superheroes-worktrees")))


def branch_name(work_item, content_hash):
    """The content-addressed build branch (unchanged identity — never recomputed)."""
    return "superheroes/%s-%s" % (work_item, content_hash)


def worktree_path(cwd, work_item, content_hash, *, root=None):
    """The deterministic FR-1 path: <managed_root>/<checkout-key>/<work-item>-<hash>.
    The checkout-key (control_plane.checkout_key — the --absolute-git-dir hash) makes
    two distinct checkouts of one repo resolve to distinct paths (FR-1 no-collision).
    Total — never raises (checkout_key falls back to realpath(cwd))."""
    key = control_plane.checkout_key(cwd)
    return os.path.join(managed_root(root), key, "%s-%s" % (work_item, content_hash))


# append to plugins/superheroes/lib/buildtree.py
RECORD_SCHEMA = 1


class RecordSchemaError(RuntimeError):
    """Raised by record_read on an unknown (future) record schemaVersion — fail closed
    loudly (the engine.py/state.py precedent); never silently drop a forward-version
    record."""


def record_path(cwd, *, store_root=None):
    """The durable record's location: <checkout control-plane dir>/worktrees.json."""
    return os.path.join(control_plane.checkout_dir(cwd, store_root), "worktrees.json")


def record_read(record_file):
    """Fail-closed read. Missing/garbled -> [] (degrades to git-registry recognition,
    self-heals on the next reconcile). An explicit unknown schemaVersion -> raise."""
    try:
        with open(record_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    ver = data.get("schemaVersion")
    if ver is not None and ver != RECORD_SCHEMA:
        raise RecordSchemaError("unknown worktrees.json schemaVersion: %r" % (ver,))
    wts = data.get("worktrees")
    return [w for w in wts if isinstance(w, dict)] if isinstance(wts, list) else []


def record_write(record_file, worktrees):
    """Atomic write of the full record."""
    control_plane.atomic_write(record_file, json.dumps(
        {"schemaVersion": RECORD_SCHEMA, "worktrees": worktrees}))


def record_add(record_file, entry):
    """Idempotent add, deduped by path."""
    kept = [w for w in record_read(record_file) if w.get("path") != entry.get("path")]
    kept.append(entry)
    record_write(record_file, kept)


def record_remove(record_file, path):
    """Idempotent remove by path."""
    record_write(record_file,
                 [w for w in record_read(record_file) if w.get("path") != path])


# append to plugins/superheroes/lib/buildtree.py
def recognize(*, registered, on_record):
    """UFR-7: a directory is an actionable build worktree iff it is structurally
    recognized (git-registered at a deterministic FR-1 path) OR present on the durable
    record. Pure — the caller pre-computes `registered`/`on_record`; the record admits
    only structurally-recognized worktrees, so it never lets an arbitrary directory in."""
    return bool(registered) or bool(on_record)


# append to plugins/superheroes/lib/buildtree.py
PRESERVE_NOTIFY = "preserve_notify"
GATE_FAILCLOSED = "gate_failclosed"
SKIP_OPEN = "skip_open"
REMOVE_KEEP_BRANCH = "remove_keep_branch"
REMOVE_AND_DELETE = "remove_and_delete"


def reap_decision(pr_state, *, dirty, branch_deletable):
    """Pure tiered/guard gate. Precedence: the dirty guard (UFR-1) wins over every tier
    — never reap a dirty-or-undeterminable worktree, even on merge. Then the PR-state
    tiers: merged -> full reap (FR-6) unless the branch must be preserved (UFR-6);
    closed-unmerged -> remove the worktree, keep the branch (FR-7); open/parked -> skip
    (UFR-3); unknown/indeterminate -> gate (UFR-2)."""
    if dirty:
        return PRESERVE_NOTIFY
    if pr_state == "merged":
        return REMOVE_AND_DELETE if branch_deletable else REMOVE_KEEP_BRANCH
    if pr_state == "closed":
        return REMOVE_KEEP_BRANCH
    if pr_state == "open":
        return SKIP_OPEN
    return GATE_FAILCLOSED


# append to plugins/superheroes/lib/buildtree.py
def branch_deletable(local_tip, pr_head_oid, *, determinable):
    """UFR-6, squash-safe, fail-closed. Deletable only when the comparison is
    determinable AND the local branch tip is exactly the merged PR head — i.e. the
    branch introduces no commits beyond what the PR merged. (Comparing to the PR head,
    not default-branch ancestry, is what makes this squash-safe.) Any uncertainty or
    divergence -> not deletable (preserve)."""
    if not determinable:
        return False
    return bool(local_tip) and bool(pr_head_oid) and local_tip == pr_head_oid
