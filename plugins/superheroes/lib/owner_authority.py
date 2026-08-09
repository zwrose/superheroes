#!/usr/bin/env python3
"""The minimal owner-authority gate — the never-merge floor, restored at v2 size (issue #482).

This is a MINIMAL classifier. It recognises an enumerated set of owner-authority
commands (merge a PR, cut a release, run a workflow, force-push, push to a default branch) and
tells the PreToolUse(Bash) hook to emit `permissionDecision: "ask"` so the owner approves them
live. There are NO roles, NO allowances, and NO worktree-confinement — all of the v1
enforcer machinery stays retired (#478).

On a positively-calibrated project, an owner may narrow asking via a hand-edited allow file
(`owner-authority-allow.json` in the project store). The allowlist can only ever *narrow*
asking — it never widens silence. Invalid or hostile file content yields no entries (fail
closed to ask exactly as today).

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
- The allow-file probe is strictly READ-ONLY. It never creates the store directory, the file,
  or anything else.

Stdlib-only.
"""
import json
import os
import re
import shlex
import sys

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

ALLOW_FILENAME = "owner-authority-allow.json"
ALLOW_SCHEMA_VERSION = 1
# Entries can only match actions in this tuple — structural exclusions (NEVER_ALLOWLISTABLE) are
# enforced by omission from here, not by a separate filter. NEVER_ALLOWLISTABLE exists so
# ignored entries are loud (stderr + ask reason), not to perform the exclusion itself.
ALLOWLISTABLE_ACTIONS = ("run-workflow",)
NEVER_ALLOWLISTABLE = ("merge-pr", "merge-api", "merge-graphql", "release", "force-push")

_KNOWN_GATE_ACTIONS = frozenset(a for a, _ in OWNER_AUTHORITY_COMMANDS)

# Informational only — has no authority over the allow decision (workflow_run_target does).
_WORKFLOW_RUN_POINTER = re.compile(r"\bgh\s+workflow\s+run\b", re.I)

# bite-proof axis: refuses shell-expandable text, so an allow entry can never match
# a name the shell will substitute. Replaces an enumerated blacklist of expansion forms.
# Uses fullmatch (not $-anchored match) because $ exempts a trailing newline in Python.
_LITERAL_SAFE_COMMAND = re.compile(r"[A-Za-z0-9 _\-./:=,'\"@+]+")

# Repo/ref flags change *which* workflow code runs or *where* — not workflow inputs.
# The allow file is project-scoped, so another repo is never pre-authorized; a ref selects
# the workflow definition (and secrets) on that branch. Inputs (-F/--field, -f/--raw-field,
# --json) stay accepted — they parameterize the dispatch, not the code location.
_SCOPE_CHANGING_FLAGS = frozenset(("-R", "--repo", "-r", "--ref"))

_VALUE_FLAG_LONG = frozenset(("--field", "--raw-field"))
_VALUE_FLAGS = frozenset(("-F", "--field", "-f", "--raw-field"))


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


def allow_file_path(cwd, root=None):
    import mode_registry
    return os.path.join(mode_registry.project_store_dir(cwd, root), ALLOW_FILENAME)


def _rejected_file_note(defect):
    return ("rejected-file", None,
            "owner-authority-allow.json was rejected (%s) — the gate is asking as if it were absent"
            % defect)


def read_allow_file(cwd, root=None):
    """(entries, notes) from the allow file. PURE — never writes, never raises.

    entries: list of {"action": str, "workflow": str}
    notes:   list of (kind, action_or_None, text)"""
    entries = []
    notes = []
    # bite-proof axis: probe is read-only — never creates the store directory or file.
    try:
        path = allow_file_path(cwd, root)
    except Exception:
        notes.append(_rejected_file_note("path resolution failed"))
        return entries, notes

    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        return entries, notes
    except json.JSONDecodeError:
        notes.append(_rejected_file_note("invalid JSON"))
        return entries, notes
    except Exception:
        notes.append(_rejected_file_note("unreadable"))
        return entries, notes

    if not isinstance(raw, dict):
        notes.append(_rejected_file_note("top level is not an object"))
        return entries, notes

    ver = raw.get("schemaVersion")
    # bite-proof axis: a wrong-schema file must not yield entries (bool-int trap included).
    if not isinstance(ver, int) or isinstance(ver, bool) or ver != ALLOW_SCHEMA_VERSION:
        notes.append(_rejected_file_note("bad schemaVersion"))
        return entries, notes

    allow = raw.get("allow")
    if not isinstance(allow, list):
        notes.append(_rejected_file_note("allow is not a list"))
        return entries, notes

    for item in allow:
        if not isinstance(item, dict):
            notes.append(("malformed", None, "ignored malformed allow entry (not a dict)"))
            continue

        action = item.get("action")
        workflow = item.get("workflow")

        if isinstance(action, str) and action in NEVER_ALLOWLISTABLE:
            notes.append(("structural", action,
                            "ignored structurally-excluded action %r" % action))
            continue

        if isinstance(action, str) and action in _KNOWN_GATE_ACTIONS \
                and action not in ALLOWLISTABLE_ACTIONS:
            notes.append(("not-allowlistable", action,
                            "ignored not-allowlistable action %r" % action))
            continue

        # bite-proof axis: malformed entries must be dropped, never honoured wholesale.
        if not isinstance(action, str) or not action:
            notes.append(("malformed", None, "ignored malformed allow entry (bad action)"))
            continue
        if not isinstance(workflow, str) or not workflow:
            notes.append(("malformed", action, "ignored malformed allow entry (bad workflow)"))
            continue
        if action not in ALLOWLISTABLE_ACTIONS:
            notes.append(("malformed", action,
                            "ignored malformed allow entry (unknown action %r)" % action))
            continue

        entries.append({"action": action, "workflow": workflow})

    return entries, notes


def workflow_run_target(command):
    """The exact workflow id/name from a `gh workflow run` command, or None."""
    if not isinstance(command, str) or not command or len(command) > 4096:
        return None

    if not _LITERAL_SAFE_COMMAND.fullmatch(command):
        return None

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None

    if len(tokens) < 3 or tokens[0] != "gh" or tokens[1] != "workflow" or tokens[2] != "run":
        return None

    positionals = []
    i = 3
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            positionals.extend(tokens[i + 1:])
            break
        if tok.startswith("-"):
            if "=" in tok:
                flag = tok.split("=", 1)[0]
                # bite-proof axis: repo/ref flags must never be skipped — they change scope.
                if flag in _SCOPE_CHANGING_FLAGS:
                    return None
                # bite-proof axis: flag values must not be misread as the workflow name.
                if flag not in _VALUE_FLAG_LONG:
                    return None
                i += 1
                continue
            if tok in _SCOPE_CHANGING_FLAGS:
                return None
            if tok in _VALUE_FLAGS:
                if i + 1 >= len(tokens):
                    return None
                i += 2
                continue
            if tok == "--json":
                i += 1
                continue
            return None
        positionals.append(tok)
        i += 1

    if len(positionals) != 1 or not positionals[0]:
        return None
    return positionals[0]


def allowlisted(command, action, entries):
    """True when entries pre-authorize this exact command/action pair. Pure — no I/O."""
    # bite-proof axis: only ALLOWLISTABLE_ACTIONS can ever match — structural exclusions
    # cannot reach silence via file content.
    if action not in ALLOWLISTABLE_ACTIONS:
        return False
    # Fail closed: this function resolves targets only via workflow_run_target. A future
    # ALLOWLISTABLE_ACTIONS entry must ship its own extractor — do not fall through here.
    if action != "run-workflow":
        return False
    target = workflow_run_target(command)
    if target is None:
        return False
    for entry in entries:
        if entry["action"] == action and entry["workflow"] == target:
            return True
    return False


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


def _ask_reason(action, command, notes):
    reason = "owner-authority action '%s' needs your live approval" % action
    # Informational pointer only — driven by cheap regex, not workflow_run_target.
    if _WORKFLOW_RUN_POINTER.search(command):
        reason += (" — to pre-authorize this workflow, see the superheroes plugin's "
                   "reference/owner-authority-allowlist.md")
    structural = sorted({a for kind, a, _ in notes if kind == "structural" and a})
    if structural:
        reason += (" [owner-authority-allow.json names %s, which can never be allowlisted; "
                   "ignored]" % ", ".join(structural))
    rejected = [text for kind, _, text in notes if kind == "rejected-file"]
    if rejected:
        reason += " [%s]" % rejected[0]
    return reason


def classify(command, cwd, root=None):
    """('ask'|'allow', reason) for a candidate Bash command.

    Only an enumerated owner-authority command ever reaches the calibration probe: a non-matching
    command short-circuits to ('allow', ''). For a matching command the probe's tri-state decides:

    - 'uncalibrated' → ('allow', ''): a plain non-superheroes project gets no gate.
    - 'indeterminate' → ('ask', ...): fail CLOSED. The allow file is NOT consulted — narrowing
      applies only where calibration is positively known.
    - 'calibrated' → read the allow file; allow iff allowlisted, else ask.

    `root` is a test seam for the allow-file read only; the calibration probe always uses the
    ambient store. Production callers (the hook) never pass it."""
    action = owner_authority_action(command)
    if not action:
        return ("allow", "")
    state = calibration_state(cwd)
    if state == "uncalibrated":
        return ("allow", "")
    if state == "indeterminate":
        # bite-proof axis: indeterminate must not consult the allow file.
        return ("ask", _ask_reason(action, command, []))
    entries, notes = read_allow_file(cwd, root)
    for kind, _action, text in notes:
        print(text, file=sys.stderr)
    if allowlisted(command, action, entries):
        return ("allow", "")
    return ("ask", _ask_reason(action, command, notes))
