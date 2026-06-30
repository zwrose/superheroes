# plugins/superheroes/lib/allowance.py
"""Codex single-use approval allowance (issue #14, the gate's deny-only host).

`permissionDecision: "ask"` (a live human prompt the agent cannot answer itself) is
honored only on Claude Code. Codex hooks honor only `deny`, so the live owner-approval
gate there is two-part:

  1. On a gated `deny`, the enforcer hook — deterministic and HARNESS-RUN, not agent-run
     — issues a fresh `challenge`: a nonce bound to the exact command's hash, written to a
     short-lived record. The nonce proves a real gate-deny fired THIS turn (an agent
     cannot mint an allowance for an action that was never challenged).
  2. The skill's cooperative GATE asks the owner. On approval the agent runs `approve`
     with the command-hash + that nonce, flipping the record to approved.
  3. The very next matching call `consume`s it — single-use (deleted on use), TTL-bounded
     (DEFAULT_TTL), command-scoped. `clear_all` (PreCompact) wipes anything pending so no
     approval survives a context compaction.

Records are namespaced PER CHECKOUT (control_plane.checkout_key, the realpath'd
`--absolute-git-dir` hash — distinct per worktree/clone), so two concurrent producer
loops can never cross-consume each other's owner approval (a global, command-string-only
key would funnel parallel loops onto one record — exactly what control_plane is keyed to
avoid). `consume` claims the record with an atomic `os.rename` so two racing calls can
never both honor one approval (the single-use invariant under concurrency).

Threat model (carried from the enforcer): an honest-but-mistaken agent, not a deliberate
adversary. The deterministic mitigations here (hook-issued nonce + single-use + TTL +
PreCompact-wipe + command-hash binding + per-checkout namespace) close replay / staleness
/ compaction-survival / cross-loop cross-talk / approve-an-unchallenged-action; the
human-approval itself rests on the cooperative layer, which is the best a deny-only hook
surface allows.
"""
import hashlib
import json
import os
import secrets
import sys
import tempfile
import time

import control_plane  # store-root single source of truth (#121 Part B)

# seconds — owner-chosen (issue #14). Applied independently to each transition:
# challenge→approve (owner deliberation window) and approve→consume (the "act now"
# window), so the worst-case challenge→action lifetime is up to 2×TTL. Intentional —
# the approve→consume freshness is what bounds "approved means now"; single-use +
# per-checkout namespace + PreCompact-wipe bound the rest.
DEFAULT_TTL = 90


def store_root():
    # Single source of truth (#121 Part B): control_plane owns the new default + env back-compat
    # (SUPERHEROES_STORE_ROOT, then the legacy WORKHORSE_STORE_ROOT) so approvals never land in a
    # different root than the rest of the store.
    return control_plane.store_root()


def _dir():
    return os.path.join(store_root(), "approvals")


def _ckey(cwd):
    """Per-checkout namespace. Reuse control_plane.checkout_key (the realpath'd
    --absolute-git-dir hash, distinct per worktree); fall back to a realpath hash, or a
    fixed 'global' bucket when no cwd is known."""
    if not cwd:
        return "global"
    try:
        import control_plane
        return control_plane.checkout_key(cwd)
    except Exception:
        return hashlib.sha256(os.path.realpath(cwd).encode("utf-8")).hexdigest()[:16]


def command_hash(command):
    return hashlib.sha256((command or "").encode("utf-8")).hexdigest()


def _path(command_hash_, cwd):
    return os.path.join(_dir(), _ckey(cwd), command_hash_ + ".json")


def _now(now):
    return time.time() if now is None else now


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _atomic_write(path, obj):
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".wh-allow.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(obj))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def challenge(command, action, cwd=None, now=None):
    """Issue (or refresh) a challenge for `command` in this checkout; return a fresh
    nonce. Resets any prior approval — a new gate-deny means an earlier approval is
    stale."""
    ts = _now(now)
    nonce = secrets.token_hex(16)
    h = command_hash(command)
    _atomic_write(_path(h, cwd), {
        "action": action, "command_hash": h, "nonce": nonce,
        "challenge_ts": ts, "approved": False, "approved_ts": None,
    })
    return nonce


def approve(command_hash_, nonce, cwd=None, now=None, ttl=DEFAULT_TTL):
    """Promote a pending challenge to approved iff a matching, unexpired challenge with
    this exact nonce exists in this checkout. Returns True on success. Fail-safe: any
    mismatch / missing record / stale challenge / I/O error → False (the deny stands)."""
    ts = _now(now)
    path = _path(command_hash_, cwd)
    rec = _read(path)
    if not rec or rec.get("nonce") != nonce:
        return False
    if not isinstance(rec.get("challenge_ts"), (int, float)):
        return False
    if ts - rec["challenge_ts"] > ttl:
        return False
    rec["approved"] = True
    rec["approved_ts"] = ts
    try:
        _atomic_write(path, rec)
    except OSError:
        return False
    return True


def consume(command, cwd=None, now=None, ttl=DEFAULT_TTL):
    """Single-use: consume an approved, unexpired allowance for `command` in this
    checkout. A pending (challenged-but-not-approved) record is LEFT in place. The claim
    is atomic — `os.rename` of the record to a unique name — so two racing consumers can
    never both honor one approval (exactly one wins the rename; the loser gets OSError →
    False). Fail-safe: missing / unapproved / stale / lost-race → False."""
    ts = _now(now)
    path = _path(command_hash(command), cwd)
    rec = _read(path)
    if not rec or not rec.get("approved"):
        return False
    at = rec.get("approved_ts")
    if not isinstance(at, (int, float)) or ts - at > ttl:
        _unlink(path)  # approved but stale → clean up, do not honor
        # Breadcrumb so a confusing "approve again" (a TTL-expired approval) is
        # diagnosable in the hook log, distinct from "never approved".
        sys.stderr.write(
            "workhorse allowance: a prior approval expired (>%ds) — re-approval required\n" % ttl)
        return False
    claim = path + ".claim." + secrets.token_hex(8)
    try:
        os.rename(path, claim)   # atomic exclusive claim — only one consumer wins
    except OSError:
        return False             # missing or lost the race → do not honor
    _unlink(claim)
    return True


def clear_all(cwd=None):
    """Wipe pending allowances (the PreCompact hook). Scoped to this checkout when `cwd`
    is given (so one loop's compaction can't revoke another loop's approval); wipes every
    checkout's records when `cwd` is None. Best-effort, never raises."""
    roots = [os.path.join(_dir(), _ckey(cwd))] if cwd else _all_checkout_dirs()
    for d in roots:
        try:
            for name in os.listdir(d):
                # `.json` records AND any orphaned `.claim.*` files (a process killed
                # between consume's rename and unlink leaves one behind — reclaim it).
                if name.endswith(".json") or ".claim." in name:
                    _unlink(os.path.join(d, name))
        except OSError:
            pass


def _all_checkout_dirs():
    base = _dir()
    try:
        return [os.path.join(base, n) for n in os.listdir(base)
                if os.path.isdir(os.path.join(base, n))]
    except OSError:
        return []
