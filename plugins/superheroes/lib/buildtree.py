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


def _record_add_safe(rec_file, entry):
    """Never-raises record write for the effectful shell: a failed write (OSError) is
    swallowed — the record is an accountability sidecar that self-heals on the next
    sweep, and the worktree is already git-registered. A forward-version record
    (RecordSchemaError) returns False so the caller fails closed (GATE_FAILCLOSED)."""
    try:
        record_add(rec_file, entry)
        return True
    except RecordSchemaError:
        return False
    except OSError:
        return True


def _record_remove_safe(rec_file, path):
    """Never-raises record cleanup: swallow OSError (self-heals next sweep) and
    RecordSchemaError (forward-version record; the teardown already succeeded)."""
    try:
        record_remove(rec_file, path)
    except (OSError, RecordSchemaError):
        pass


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


# append to plugins/superheroes/lib/buildtree.py
def plan_reconcile(disk_entries, record_entries):
    """Pure bidirectional reconcile (FR-5). `disk_entries`: recognized worktrees found
    on disk (git-registered at a deterministic path). `record_entries`: the durable
    record. Returns {to_record, candidates}: disk entries absent from the record (the
    caller records them — accountability), and the union-by-path of disk and record (the
    recognized set to evaluate for reaping, so a branch-less recorded worktree is
    included)."""
    rec_paths = {e.get("path") for e in record_entries if e.get("path")}
    seen, to_record = set(), []
    for e in disk_entries:
        p = e.get("path")
        if p and p not in rec_paths and p not in seen:
            to_record.append(e)
            seen.add(p)
    by_path = {}
    for e in list(record_entries) + list(disk_entries):
        p = e.get("path")
        if p and p not in by_path:
            by_path[p] = e
    return {"to_record": to_record, "candidates": list(by_path.values())}


# append to plugins/superheroes/lib/buildtree.py
def _git(cwd, *args):
    """Run a git command; return (returncode, stdout). Never raises."""
    try:
        r = subprocess.run(["git", "-C", cwd, *args],
                           capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def list_worktrees(cwd):
    """Parse `git worktree list --porcelain`. Returns a list of {path, branch, prunable}
    on success (possibly empty), or **None** on a failed/garbled read (the fail-closed
    signal: the sweep then reaps nothing and retains the record)."""
    rc, out = _git(cwd, "worktree", "list", "--porcelain")
    if rc != 0:
        return None
    entries, cur = [], None
    for line in out.splitlines():
        if line.startswith("worktree "):
            if cur is not None:
                entries.append(cur)
            cur = {"path": os.path.realpath(line[9:]), "branch": None, "prunable": False}
        elif cur is None:
            continue
        elif line.startswith("branch "):
            ref = line[7:]
            cur["branch"] = ref[11:] if ref.startswith("refs/heads/") else ref
        elif line.startswith("prunable"):
            cur["prunable"] = True
    if cur is not None:
        entries.append(cur)
    return entries


def is_dirty(path):
    """True if the worktree has uncommitted changes, OR if cleanliness cannot be
    determined (fail-closed — an unreadable `git status` reads as dirty, so UFR-1
    preserves it)."""
    rc, out = _git(path, "status", "--porcelain")
    if rc != 0:
        return True
    return out.strip() != ""


def branch_exists(cwd, branch):
    if not branch:
        return False
    rc, _ = _git(cwd, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch)
    return rc == 0


def rev_parse(cwd, branch):
    if not branch:
        return None
    rc, out = _git(cwd, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch)
    return out.strip() if rc == 0 and out.strip() else None


def leaf_empty_or_absent(path):
    """True iff the path is absent or an empty directory (so `git worktree add` accepts
    it). Fail-closed: an unreadable leaf is treated as non-empty (False) — never deleted,
    never built over."""
    if not os.path.exists(path):
        return True
    try:
        return os.path.isdir(path) and not os.listdir(path)
    except OSError:
        return False


def split_leaf(path):
    """Parse (work_item, content_hash) from a deterministic leaf '<work-item>-<hash>'.
    The content-hash is the final hyphen-delimited segment; the work-item slug (which
    itself contains hyphens) is everything before it."""
    leaf = os.path.basename(path.rstrip(os.sep))
    if "-" in leaf:
        wi, ch = leaf.rsplit("-", 1)
        return wi, ch
    return leaf, ""


# append to plugins/superheroes/lib/buildtree.py
REUSED = "reused"
CREATED = "created"


def create(cwd, path, branch, rec_file, work_item, content_hash, *, existing_branch):
    """Effectful, internal to reclaim_or_create (kept separate for direct testing —
    the devserver.start split). `git worktree add` onto an absent/empty leaf, then
    record (FR-9). Never raises: an uncreatable parent, a failed `git worktree add`, or
    a forward-version record (RecordSchemaError) all return GATE_FAILCLOSED; a failed
    record write (OSError) is swallowed (the worktree is git-registered; the record
    self-heals)."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        return {"outcome": GATE_FAILCLOSED, "path": path, "branch": branch}
    if existing_branch:
        rc, _ = _git(cwd, "worktree", "add", path, branch)
    else:
        rc, _ = _git(cwd, "worktree", "add", "-b", branch, path)
    if rc != 0:
        return {"outcome": GATE_FAILCLOSED, "path": path, "branch": branch}
    if not _record_add_safe(rec_file, {"workItem": work_item, "contentHash": content_hash,
                                       "branch": branch, "path": path}):
        return {"outcome": GATE_FAILCLOSED, "path": path, "branch": branch}
    return {"outcome": CREATED, "path": path, "branch": branch}


def reclaim_or_create(cwd, work_item, content_hash, *, root=None, store_root=None):
    """FR-1/FR-2 reuse/create partition (never raises; adds no destructive primitive):
      - recognized worktree, leaf present & healthy, clean -> REUSED
      - leaf present, dirty/unreadable -> PRESERVE_NOTIFY (UFR-1, never clobber)
      - registered-but-leaf-missing (prunable) -> prune + re-create on the surviving
        branch (non-destructive — the tree is already gone, the branch ref is untouched)
      - absent/empty leaf -> git worktree add (CREATED); the add itself failing -> GATE
      - non-empty, not a recognized worktree -> PRESERVE_NOTIFY (surface, never delete)"""
    path = worktree_path(cwd, work_item, content_hash, root=root)
    branch = branch_name(work_item, content_hash)
    rec_file = record_path(cwd, store_root=store_root)
    wts = list_worktrees(cwd)
    rows = [w for w in (wts or []) if w.get("path") == path]
    registered = bool(rows)
    prunable = any(w.get("prunable") for w in rows)
    leaf_present = os.path.isdir(path)

    if registered and leaf_present and not prunable:
        if is_dirty(path):
            return {"outcome": PRESERVE_NOTIFY, "path": path, "branch": branch}
        if not _record_add_safe(rec_file, {"workItem": work_item, "contentHash": content_hash,
                                           "branch": branch, "path": path}):
            return {"outcome": GATE_FAILCLOSED, "path": path, "branch": branch}
        return {"outcome": REUSED, "path": path, "branch": branch}

    if registered and (prunable or not leaf_present):
        # the owner hand-deleted the leaf: prune the dangling registration, re-create on
        # the surviving branch. Non-destructive; not a UFR-1 case.
        _git(cwd, "worktree", "prune")
        return create(cwd, path, branch, rec_file, work_item, content_hash,
                      existing_branch=branch_exists(cwd, branch))

    if leaf_empty_or_absent(path):
        return create(cwd, path, branch, rec_file, work_item, content_hash,
                      existing_branch=branch_exists(cwd, branch))

    # non-empty, not a recognized worktree -> never touch; surface for the owner.
    return {"outcome": PRESERVE_NOTIFY, "path": path, "branch": branch}


# append to plugins/superheroes/lib/buildtree.py
def teardown(cwd, path, branch, decision):
    """Execute a reap decision. Removes the worktree checkout BEFORE deleting the branch
    (so a partial failure leaves a still-recognized worktree, never a branch-less one).
    Never `--force` (UFR-1 is enforced upstream by reap_decision). Idempotent and never
    raises (the devserver.teardown contract). Returns {ok, removed, branch_deleted,
    incomplete}; `incomplete` (UFR-5) means the worktree went but the branch delete
    failed — the caller keeps it on the record and notifies."""
    if decision not in (REMOVE_KEEP_BRANCH, REMOVE_AND_DELETE):
        return {"ok": True, "removed": False, "branch_deleted": False, "incomplete": False}
    rc, _ = _git(cwd, "worktree", "remove", path)
    if rc != 0:
        _git(cwd, "worktree", "prune")               # tolerate an already-gone leaf
    removed = not os.path.exists(path)
    if not removed:
        return {"ok": False, "removed": False, "branch_deleted": False, "incomplete": True}
    if decision == REMOVE_KEEP_BRANCH:
        return {"ok": True, "removed": True, "branch_deleted": False, "incomplete": False}
    rc, _ = _git(cwd, "branch", "-D", branch)
    deleted = rc == 0 or not branch_exists(cwd, branch)
    return {"ok": deleted, "removed": True, "branch_deleted": deleted,
            "incomplete": not deleted}


# append to plugins/superheroes/lib/buildtree.py
def plan_sweep(cwd, pr_info, *, active_work_item, active_path=None,
               root=None, store_root=None):
    """FR-5/FR-10: build the reap-candidate list to present for owner confirmation.
    Fail-closed: an unreadable `git worktree list` -> [] (no candidates, record left
    untouched). Records disk-found-but-unrecorded worktrees (FR-9 accountability) and
    excludes the active run's worktree (FR-11 / the live-worktree invariant) — by its
    path (`active_path`, structural) and by its work-item slug (belt-and-suspenders)."""
    wts = list_worktrees(cwd)
    if wts is None:
        return []
    rec_file = record_path(cwd, store_root=store_root)
    try:
        record = record_read(rec_file)
    except RecordSchemaError:
        return []   # forward-version record -> fail closed (no sweep)
    rec_paths = {e.get("path") for e in record if e.get("path")}
    disk_paths = {w.get("path") for w in wts}
    mroot = managed_root(root)
    disk = [{"path": w["path"], "branch": w.get("branch")}
            for w in wts if w.get("path", "").startswith(mroot + os.sep)]
    rec = plan_reconcile(disk, record)
    for e in rec["to_record"]:
        wi, ch = split_leaf(e["path"])
        _record_add_safe(rec_file, {"workItem": wi, "contentHash": ch,
                                    "branch": e.get("branch"), "path": e["path"]})
    candidates = []
    for c in rec["candidates"]:
        path, branch = c.get("path"), c.get("branch")
        wi, ch = split_leaf(path)
        # UFR-7 gate: act only on a recognized worktree (git-registered OR on-record).
        if not recognize(registered=path in disk_paths, on_record=path in rec_paths):
            continue
        if path == active_path or wi == active_work_item:   # live-worktree invariant
            continue
        if not branch:
            continue   # branch-less/detached managed worktree -> can't reap-evaluate; preserve
        info = pr_info.get(branch, {})
        pr_state, pr_head = info.get("pr_state", "unknown"), info.get("pr_head_oid")
        dirty = is_dirty(path) if os.path.isdir(path) else False
        deletable = branch_deletable(rev_parse(cwd, branch), pr_head,
                                     determinable=pr_head is not None)
        decision = reap_decision(pr_state, dirty=dirty, branch_deletable=deletable)
        if decision in (REMOVE_KEEP_BRANCH, REMOVE_AND_DELETE):
            candidates.append({"path": path, "branch": branch, "workItem": wi,
                               "contentHash": ch, "decision": decision,
                               "pr_state": pr_state, "pr_head_oid": pr_head})
    return candidates


def reap_one(cwd, path, branch, pr_state, pr_head_oid, *, store_root=None):
    """Execute one approved reap, RE-VALIDATING against current state at reap time
    (FR-11): re-read dirty, recompute branch_deletable, re-decide, then teardown. Clears
    the record on a confirmed full reap (worktree gone, branch deleted-or-intentionally-
    kept); keeps it on preserve/skip/gate/incomplete (UFR-5). Returns {decision, result}."""
    dirty = is_dirty(path) if os.path.isdir(path) else False
    deletable = branch_deletable(rev_parse(cwd, branch), pr_head_oid,
                                 determinable=pr_head_oid is not None)
    decision = reap_decision(pr_state, dirty=dirty, branch_deletable=deletable)
    result = teardown(cwd, path, branch, decision)
    if result.get("removed") and not result.get("incomplete"):
        _record_remove_safe(record_path(cwd, store_root=store_root), path)
    return {"decision": decision, "result": result}
