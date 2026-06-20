# plugins/superheroes/lib/control_plane.py
"""Per-checkout control-plane store (CONVENTIONS §4.2): a machine-local git repo,
keyed by <absolute-git-dir-key> (§6.2) — DISTINCT per worktree/clone — holding one
work-item's runtime (checkpoint, resume-brief, events). Dependency-free.

Keying note (§4.2): we derive from raw `--absolute-git-dir`, NOT `--git-common-dir`
(which is shared across a clone's linked worktrees, correct for config but WRONG
for the control plane — it would funnel two parallel loops onto one store).
"""
import hashlib
import json
import os
import subprocess
import tempfile

DEFAULT_STORE_ROOT = "~/.claude/workhorse"
SCHEMA_VERSION = 1


def store_root():
    return os.path.realpath(os.path.expanduser(
        os.environ.get("WORKHORSE_STORE_ROOT", DEFAULT_STORE_ROOT)))


def _run_git(cwd, *args):
    try:
        r = subprocess.run(["git", "-C", cwd, *args],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _short_hash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def checkout_key(cwd):
    out = _run_git(cwd, "rev-parse", "--absolute-git-dir")
    base = os.path.realpath(out) if out else os.path.realpath(cwd)
    return _short_hash(base)


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
            atomic_write(meta, json.dumps({"schemaVersion": SCHEMA_VERSION}))
        return d
    except (OSError, subprocess.SubprocessError):
        return None


def _current_path(cwd, root=None):
    return os.path.join(checkout_dir(cwd, root), "current.json")


def set_current(cwd, work_item, root=None):
    atomic_write(_current_path(cwd, root), json.dumps({"workItem": work_item}))


def get_current(cwd, root=None):
    try:
        with open(_current_path(cwd, root), encoding="utf-8") as fh:
            return json.load(fh).get("workItem")
    except (OSError, ValueError):
        return None
