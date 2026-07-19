#!/usr/bin/env python3
"""The minimal owner-authority gate — the never-merge floor, restored at v2 size (issue #482).

This is a MINIMAL, config-free classifier. It recognises an enumerated set of owner-authority
commands (merge a PR, cut a release, run a workflow, force-push, push to a default branch) and
tells the PreToolUse(Bash) hook to emit `permissionDecision: "ask"` so the owner approves them
live. There are NO roles, NO allowances, NO worktree-confinement, and NO config — all of the v1
enforcer machinery stays retired (#478).

The command enumeration below is LIFTED VERBATIM from the deleted `lib/enforcer.py`
`GATED_COMMANDS` (git history, pre-#478); it is not re-derived or widened here.

Scope of the decision:

- The gate only ever emits `ask` (never `deny`) for the enumerated set. `deny` is solely the
  hooks.json process-failure backstop (a `|| printf ...deny...` wrapper for a gate that cannot
  start). The classifier itself never denies.
- The calibration probe is strictly READ-ONLY. It mirrors `lib/session_context.py`'s covenant
  probe but is TRI-STATE, because a safety floor must distinguish an absent calibration from a
  corrupt/errored one. It NEVER calls `mode_registry.resolve()` (which can backfill-WRITE the
  registry); a probe must not mutate project state.

Stdlib-only.
"""
import os
import re

# LIFTED VERBATIM from the retired lib/enforcer.py GATED_COMMANDS (pre-#478). Do NOT re-derive
# or widen these regexes. First .search hit wins (see owner_authority_action).
OWNER_AUTHORITY_COMMANDS = [
    ("merge-pr",       re.compile(r"\bgh\s+pr\s+merge\b", re.I)),
    ("merge-api",      re.compile(r"\bgh\s+api\b.*\bpulls/[^/\s]+/merge\b", re.I)),
    ("merge-graphql",  re.compile(r"\bmergePullRequest\b", re.I)),
    ("release",        re.compile(r"\bgh\s+release\s+create\b", re.I)),
    ("run-workflow",   re.compile(r"\bgh\s+workflow\s+(run|enable|disable)\b", re.I)),
    ("force-push",     re.compile(r"\bgit\s+push\b.*(--force\b|-f\b|--force-with-lease)", re.I)),
    ("push-to-default", re.compile(r"\bgit\s+push\b[^;&|\n]*(?::|[ \t])(?:refs/heads/)?(main|master)(?:\s|$)", re.I)),
]


def owner_authority_action(command):
    """The action name (str) an owner-authority command performs, or None.

    Returns None for a non-string. Iterates OWNER_AUTHORITY_COMMANDS in order; the first
    regex `.search` hit wins."""
    if not isinstance(command, str):
        return None
    for action, pattern in OWNER_AUTHORITY_COMMANDS:
        if pattern.search(command):
            return action
    return None


def calibration_state(cwd):
    """Tri-state, strictly READ-ONLY calibration probe: 'calibrated' / 'uncalibrated' /
    'indeterminate'.

    Mirrors lib/session_context.py's covenant probe but is TRI-STATE: a safety floor must tell an
    ABSENT calibration (a plain non-superheroes project) apart from a corrupt/errored one, so it
    can fail closed (→ ask) on the latter without silencing the floor on the former.

    NEVER calls mode_registry.resolve() — that can backfill-WRITE the registry, and a probe must
    not mutate project state. The mode_registry import is lazy (inside this function) so a
    probe-time import error is caught and reported as 'indeterminate'."""
    try:
        import mode_registry
    except Exception:
        return "indeterminate"

    # A returned dict → calibrated. A RAISE (e.g. UnknownSchemaVersion on a newer schema) or any
    # other exception → indeterminate (fail-closed).
    try:
        rec = mode_registry.read_registry(cwd)
    except Exception:
        return "indeterminate"
    if rec is not None:
        return "calibrated"

    # read_registry returned None: either no file, or a file that yielded None
    # (corrupt/invalid/inaccessible). Distinguish the two by whether the registry FILE exists —
    # via os.lstat, NOT os.path.exists. os.path.exists follows symlinks and swallows permission/
    # loop errors, so a dangling or inaccessible registry.json would read as "absent" and could
    # silently drop the floor to uncalibrated on a calibrated project. os.lstat raises
    # FileNotFoundError ONLY for a genuinely absent path; a dangling symlink lstat-SUCCEEDS
    # (present → indeterminate), and any other error (permission, loop) → indeterminate.
    try:
        os.lstat(mode_registry.registry_path(cwd))
        file_present = True
    except FileNotFoundError:
        file_present = False
    except Exception:
        return "indeterminate"
    if file_present:
        # File present but read_registry could not validate it → corrupt/invalid/inaccessible.
        return "indeterminate"

    # No registry file: fall back to hero-evidence.
    try:
        verdict = mode_registry.evidence_verdict(mode_registry.hero_evidence(cwd))
    except Exception:
        return "indeterminate"
    return "uncalibrated" if verdict == "none" else "calibrated"


def classify(command, cwd):
    """('ask'|'allow', reason) for a candidate Bash command.

    Only an enumerated owner-authority command ever reaches the calibration probe: a non-matching
    command short-circuits to ('allow', ''). For a matching command the probe's tri-state decides:

    - 'calibrated' OR 'indeterminate' → ('ask', ...): fail CLOSED. Because only an enumerated
      owner-authority command reaches the probe, an 'indeterminate' fail-closed-to-ask costs at
      most a rare extra prompt — never a silently-disabled floor.
    - 'uncalibrated' → ('allow', ''): a plain non-superheroes project gets no gate."""
    action = owner_authority_action(command)
    if not action:
        return ("allow", "")
    state = calibration_state(cwd)
    if state in ("calibrated", "indeterminate"):
        return ("ask", "owner-authority action '%s' needs your live approval" % action)
    return ("allow", "")
