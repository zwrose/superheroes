# plugins/superheroes/lib/control_plane.py
"""Per-clone control-plane store (CONVENTIONS §4.2): a machine-local git repo, keyed by
<common-dir-key> (§6.2) — SHARED identically across a clone's main checkout and every
linked worktree — holding each work-item's runtime (checkpoint, resume-brief, events).
Dependency-free.

Keying note (§4.2): we derive from the git COMMON dir (`--git-common-dir`), NOT the
per-worktree `--absolute-git-dir`. Coordination MUST be shared across a clone's worktrees:
the one-live-run-per-work-item lease refs live in this store, and a per-worktree store
would let the same work item launch twice from two worktrees (split-brain on one
branch/PR). State isolation is per-work-item WITHIN the store (issues/<work-item>/…), not
per-worktree — mirrors mode_registry.config_key's common-dir keying (§6.2).
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

DEFAULT_STORE_ROOT = "~/.claude/superheroes"
LEGACY_STORE_ROOT = "~/.claude/workhorse"  # pre-#121 name; auto-migrated, still resolvable
SCHEMA_VERSION = 1


def _store_env():
    """The store-root override, new var preferred, legacy var honored for back-compat (#121)."""
    return os.environ.get("SUPERHEROES_STORE_ROOT") or os.environ.get("WORKHORSE_STORE_ROOT")


def _holds_store(path):
    """True when `path` actually holds a store — keyed on the `projects/` tree, not mere existence.
    An empty directory created by something other than the rename (a manual mkdir, a restore, an
    interrupted op) must NOT be mistaken for the store, or store_root() would resolve to it and
    strand the populated legacy (/code-review #6). Single source of truth for store_root() and
    migrate_store_root() so their precedence can never diverge (/code-review #14)."""
    return os.path.isdir(os.path.join(os.path.expanduser(path), "projects"))


def store_root():
    """The band-wide per-project store root. Precedence: env override → the new default if it holds
    a store → the legacy default if IT holds a store (back-compat, never strand an existing store
    behind an empty new root) → the new default. Pure (no side effects); the physical rename is
    migrate_store_root()."""
    env = _store_env()
    if env:
        return os.path.realpath(os.path.expanduser(env))
    if _holds_store(DEFAULT_STORE_ROOT):
        return os.path.realpath(os.path.expanduser(DEFAULT_STORE_ROOT))
    if _holds_store(LEGACY_STORE_ROOT):
        return os.path.realpath(os.path.expanduser(LEGACY_STORE_ROOT))
    return os.path.realpath(os.path.expanduser(DEFAULT_STORE_ROOT))


def migrate_store_root():
    """One-time atomic rename of the legacy store root (~/.claude/workhorse) to the new name
    (~/.claude/superheroes) — #121 Part B. No-op when an env override is set (the owner pinned a
    location), the new root already holds a store, or the legacy root holds no store. The two share
    a parent (~/.claude), so os.rename is atomic + instant (no copy) and replaces an empty new dir.
    Race/partial-failure safe between concurrent MIGRATORS: one wins, the other re-checks and reports
    `raced`. Never raises.

    CAVEAT (/code-review #2): this is a one-time event (after the first migration the new root holds
    a store, so it no-ops forever). It is NOT locked against a CONCURRENT store CONSUMER — if a
    parallel showrunner/workhorse loop is mid-operation during this single window, the rename can move
    the store out from under its absolute paths. The blast is bounded (open fds survive the rename;
    an allowance consume fails closed → a safe re-challenge) and the back-compat fallback keeps reads
    working, so a consumer-safe live rename (the owner-deferred redesign) is intentionally not done."""
    if _store_env():
        return {"migrated": False, "reason": "env-override"}
    new = os.path.expanduser(DEFAULT_STORE_ROOT)
    old = os.path.expanduser(LEGACY_STORE_ROOT)
    if _holds_store(DEFAULT_STORE_ROOT) or not _holds_store(LEGACY_STORE_ROOT):
        return {"migrated": False, "reason": "nothing-to-migrate"}
    try:
        os.makedirs(os.path.dirname(new), exist_ok=True)
        os.rename(old, new)  # replaces an empty new dir; raises on a non-empty (store-holding) new
    except OSError as exc:
        if _holds_store(DEFAULT_STORE_ROOT):
            return {"migrated": False, "reason": "raced"}
        return {"migrated": False, "reason": "failed", "detail": str(exc)}
    sys.stderr.write("superheroes: migrated store root %s -> %s\n" % (old, new))
    return {"migrated": True, "from": old, "to": new}


def _run_git(cwd, *args):
    try:
        r = subprocess.run(["git", "-C", cwd, *args],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _short_hash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _common_git_dir(cwd):
    """realpath of the git COMMON dir — identical from the main checkout and every linked
    worktree of a clone, so all of them resolve to ONE control-plane store.

    `--path-format=absolute` (git >= 2.31) is REQUIRED: a bare `--git-common-dir` returns a
    RELATIVE ".git" from the main checkout, which os.path.realpath would then resolve against
    the PYTHON process cwd (not the repo) and mis-key the store. Fallback chain preserved:
    common-dir → absolute-git-dir → realpath(cwd). On git < 2.31 (no --path-format) we re-run
    the bare `--git-common-dir` and join a relative result onto `cwd` before realpath, so
    worktrees still converge; only a total git failure drops to --absolute-git-dir / cwd.

    Zero-migration invariant: for the main checkout the common dir IS the absolute git dir, so
    this returns the exact same realpath the old `--absolute-git-dir` derivation did — every
    existing lease/journal/checkpoint keeps its key (pinned by a test)."""
    out = _run_git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if out is None:
        rel = _run_git(cwd, "rev-parse", "--git-common-dir")
        if rel is not None:
            out = rel if os.path.isabs(rel) else os.path.join(cwd, rel)
        else:
            out = _run_git(cwd, "rev-parse", "--absolute-git-dir")
    return os.path.realpath(out if out is not None else cwd)


def checkout_key(cwd):
    return _short_hash(_common_git_dir(cwd))


def checkout_dir(cwd, root=None):
    return os.path.join(root or store_root(), "checkouts", checkout_key(cwd))


def issue_dir(cwd, work_item, root=None):
    return os.path.join(checkout_dir(cwd, root), "issues", work_item)


def paths(cwd, work_item, root=None):
    d = issue_dir(cwd, work_item, root)
    return {"issue_dir": d,
            "checkpoint": os.path.join(d, "checkpoint.json"),
            "resume_brief": os.path.join(d, "resume-brief.md"),
            "events": os.path.join(d, "events.jsonl"),
            "patterns_pin": os.path.join(d, "patterns-pin.md"),
            "devserver": os.path.join(d, "devserver.json"),
            "review_result": os.path.join(d, "review-result.json"),
            "provenance": os.path.join(d, "provenance.json")}


def atomic_write(path, text):
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".wh-cp.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def ensure_store(cwd, root=None):
    """Create the per-checkout store as a git repo (idempotent) + meta.json. The git
    repo hosts the §4.4 lock refs. Returns the checkout dir, or None if the store
    can't be created/initialized (wedged → the caller fails closed per design §2)."""
    d = checkout_dir(cwd, root)
    try:
        os.makedirs(d, exist_ok=True)
        if not os.path.isdir(os.path.join(d, ".git")):
            r = subprocess.run(["git", "-C", d, "init", "-q"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                return None
        meta = os.path.join(d, "meta.json")
        if not os.path.isfile(meta):
            # sourcePath = mint-time provenance (the checkout key is a one-way hash);
            # never rewritten — a missing sourcePath means "unknown provenance".
            atomic_write(meta, json.dumps(
                {"schemaVersion": SCHEMA_VERSION, "sourcePath": os.path.realpath(cwd)}))
        return d
    except (OSError, subprocess.SubprocessError):
        return None
