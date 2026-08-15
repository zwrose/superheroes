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

The command enumeration below originated verbatim from the retired `lib/enforcer.py`
`GATED_COMMANDS` (git history, pre-#478). The tool-to-subcommand matching was re-derived under
owner ratification 2026-08-13 (issue #989) to close a silent classification bypass.

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

# LIFTED VERBATIM from the retired lib/enforcer.py GATED_COMMANDS (pre-#478). The tool-to-
# subcommand junction was re-derived under owner ratification 2026-08-13 (issue #989) to close
# a silent classification bypass. First hit wins (see owner_authority_action).
#
# Owner ratification 2026-08-14 (issue #1000): this gate is a best-effort text matcher over shell
# syntax that errs closed. No shell lexer will be built; quoting semantics are declined — skipping
# quoted text would choose fail-open in a security gate. Known silent-bypass shapes are closed as
# they are found; over-matching is an accepted cost.
#
# No row states its own end anchor; a row selects one of the two named shared anchors (`_WORD_END`
# or `_TOKEN_END`), decided by whether the row matches a shell word or a payload identifier.
# Every matcher row is built through `_gated` and must not carry its own end anchor — so a row
# added later is boundary-aware by construction.
#
# Shell segment boundaries. Splitting first, then searching within a segment, replaces the old
# tool-to-subcommand span: it removes BOTH the length cap (which fell through to None past 256
# chars — an approval bypass) and the unbounded `.*` wildcards (quadratic in a PreToolUse hook:
# 26.1s on a 35KB input, vs 0.002s here). Re-derived under owner ratification 2026-08-13 (#989).
_SEGMENT_SPLIT = re.compile(r"[;&|\n]+")

# A shell redirection is not part of the command's word structure — NEITHER the operator NOR its
# operand. Two distinct failures motivated each half. (a) Operators that CONTAIN a `;&|` character
# (`2>&1`, `&>`, `>|`, `<&`) were split as separators, tearing `gh 2>&1 pr merge 123` into `gh 2>`
# and `1 pr merge 123`. (b) Operators WITHOUT one (`>`, `>>`, `<`, `<<`) never split anything, but
# glued to a token they defeat the rows' OWN anchors: `gh pr merge>/dev/null` failed
# `(?<!\S)pr\s+merge(?!\S)` and classified None — a silent merge. And the operand matters on its
# own: substituting only the operator leaves `gh pr 2>&1 merge 123` as `gh pr  1 merge 123`, whose
# surviving `1` still breaks `pr`/`merge` adjacency.
# `&&`, `||`, `|&` and a bare background `&` match NOTHING here and stay separators.
# The fd is bounded (`\d{0,9}`, and shell fds are small): an unbounded `\d*` before a tail that
# fails on digit input backtracks quadratically — measured 46.64s end-to-end on a 100,000-digit
# run, in a gate that runs on EVERY Bash call. This is the same hazard `_short_flag` documents.
_REDIRECTION_OP_SRC = r"(?:&>>?|\d{0,9}(?:>>?|<<?)[&|]?)"
_REDIRECTION_OPERATOR = re.compile(_REDIRECTION_OP_SRC)
_REDIRECTION_WITH_OPERAND = re.compile(_REDIRECTION_OP_SRC + r"\s*[^\s;&|]*")

# The shell removes a backslash-newline before parsing, so it is not a segment boundary.
_LINE_CONTINUATION = re.compile(r"\\\r?\n")


def _segments(command):
    """Every segment the row matcher searches, line-continuations already removed.

    Returns the raw split PLUS splits of operator-only and operator-and-operand neutralizations,
    and is therefore strictly ADDITIVE: every segment the matcher saw before this helper existed is
    still in the list, so no classification can be LOST here — only gained. (An in-place strip would
    risk the opposite: an over-matching pattern could merge two genuine segments and drop a live
    hit.)

    Operand-consuming neutralization is what closes `gh pr 2>&1 merge 123`, but it can also swallow
    a gated word (`gh 2>&pr merge 1` → `gh  merge 1`), which the operator-only copy still catches.
    On shapes like `gh >pr merge 1` (stdout redirected to a file named `pr`, then `gh merge 1`),
    the operator-only copy's contribution is over-matching — an extra prompt on a command that is
    not actually the gated one — which is the accepted direction under the ratified posture.
    Keeping both neutralizations, on top of the raw split, is the fail-closed choice: more segments
    can only mean more matching, never less."""
    command_nc = _LINE_CONTINUATION.sub("", command)
    out = list(_SEGMENT_SPLIT.split(command_nc))
    seen = {command_nc}
    for pattern in (_REDIRECTION_OPERATOR, _REDIRECTION_WITH_OPERAND):
        neutral = pattern.sub(" ", command_nc)
        if neutral not in seen:
            seen.add(neutral)
            out.extend(_SEGMENT_SPLIT.split(neutral))
    return out


# Subcommand words are matched as WHITESPACE-DELIMITED TOKENS, not with \b: `\bpush\b` also matches
# inside `push.default`, which classified `git config push.default main` as push-to-default.
# Tool words keep \b so an absolute path (`/usr/bin/gh pr merge`) still classifies.
_GH = re.compile(r"\bgh\b", re.I)
_GIT = re.compile(r"\bgit\b", re.I)

# A gated word that is a SHELL WORD ends at a shell word-terminator. `.` and `-` continue a
# word here (`git config push.default main`, `git push origin main-feature`).
_WORD_END = r"(?=[^\w.-]|$)"

# A gated PAYLOAD IDENTIFIER is not a shell word — it lives INSIDE an argument (a GraphQL field
# name, a REST path segment), where `.` and `-` are ordinary terminators, not continuations
# (`--jq .data.mergePullRequest.number`, `pulls/42/merge-async`). This restores exactly the
# breadth the `\b` these rows used to carry: after a word character, `\b` == `(?=\W|$)`.
_TOKEN_END = r"(?=\W|$)"

# Leading boundary for push-to-default's ref operand only — treats quote, backtick, `(`, `/` as
# boundaries before `main`/`master`. Subcommand rows keep `(?<!\S)`; widening those would admit
# `gh pr create -t "pr merge"` as a false merge-pr, and every real wrapped shape has a space before
# the gated word with only its end quoted.
_WORD_START = r"(?<![\w.-])"

# Identity registries — structural census proves rows were built here, not by string-shape guessing.
_GATED_REGISTRY = set()
_SHORT_FLAG_REGISTRY = set()


_FORBIDDEN_BODY_ANCHORS = (
    r"(?!\S)", r"(?=\s", r"\b", r"\B", "$", r"\Z", r"\z",
)


# The ONLY end anchors a gated row may carry — a closed selector, not an open regex string. A row
# that passes any other `ending` re-opens the word-terminator class with every test green (PR #1022
# round-4 confirmation finding, three seats), so the builder refuses it by name rather than
# trusting the author.
_ALLOWED_ENDINGS = (_WORD_END, _TOKEN_END)


def _gated(body, leading=r"(?<!\S)", ending=_WORD_END):
    for token in _FORBIDDEN_BODY_ANCHORS:
        if token in body:
            raise ValueError(
                "gated body must not contain end-anchor %r — use _WORD_END or _TOKEN_END"
                % token)
    if ending not in _ALLOWED_ENDINGS:
        raise ValueError(
            "gated ending must be _WORD_END or _TOKEN_END, not %r" % (ending,))
    compiled = re.compile(leading + body + ending, re.I)
    _GATED_REGISTRY.add(id(compiled))
    return compiled


# A short-option flag can arrive standalone (`-f`) or CLUSTERED (`-qf`, `-fq`, `-uvf`, `-4f`).
# `_short_flag(letter)` is the builder every row's short-flag requirement must be composed from,
# so a row added later is cluster-aware by construction rather than by the author remembering.
# The construction is deliberately LINEAR: one unbounded class then the literal letter. Do NOT
# write `[A-Za-z0-9]*f[A-Za-z0-9]*` — two unbounded repetitions around the letter backtrack
# quadratically (measured 5.97s on a 30,000-character token; this gate runs on EVERY Bash call).
# `(?<![\w-])` — not `(?<!\S)` — keeps the shipped behaviour of matching a QUOTED flag
# (`git push "-f" origin feature` classifies force-push today and must keep doing so) while still
# refusing a match inside `--force` or inside a word like `feature-fast`.
def _short_flag(letter):
    return r"(?<![\w-])-(?!-)[A-Za-z0-9]*" + letter


def _force_push_flag_trailing():
    compiled = re.compile(r"(--force\b|-f\b|--force-with-lease|"
                          + _short_flag("f") + r")", re.I)
    _SHORT_FLAG_REGISTRY.add(id(compiled))
    return compiled


# (action, tool-word, subcommand-token, trailing-requirement-or-None)
# The trailing requirement is searched AFTER the subcommand match, within the same segment.
OWNER_AUTHORITY_COMMANDS = [
    ("merge-pr",        _GH,  _gated(r"pr\s+merge"), None),
    ("merge-api",       _GH,  _gated(r"api"),
                              _gated(r"pulls/[^/\s]+/merge", leading=r"\b",
                                     ending=_TOKEN_END)),
    ("merge-graphql",   None, _gated(r"mergePullRequest", leading=r"\b",
                                     ending=_TOKEN_END), None),
    ("release",         _GH,  _gated(r"release\s+create"), None),
    ("run-workflow",    _GH,  _gated(r"workflow\s+(run|enable|disable)"), None),
    ("force-push",      _GIT, _gated(r"push"),
                              # `-f\b` is retained deliberately: no `(?<![\w-])` lookbehind, so it
                              # still matches a trailing `-f` in `git push origin my-f` that the
                              # builder deliberately refuses — removing it would narrow a security
                              # matcher. Built from `_short_flag`, not `_gated` — flags, not words.
                              _force_push_flag_trailing()),
    ("push-to-default", _GIT, _gated(r"push"),
                              _gated(r"(?:refs/heads/)?(main|master)", leading=_WORD_START)),
]

ALLOW_FILENAME = "owner-authority-allow.json"
ALLOW_SCHEMA_VERSIONS = (1, 2)
_REF_KEY_VERSIONS = frozenset((2,))
# Entries can only match actions in this tuple — structural exclusions (NEVER_ALLOWLISTABLE) are
# enforced by omission from here, not by a separate filter. NEVER_ALLOWLISTABLE exists so
# ignored entries are loud (stderr + ask reason), not to perform the exclusion itself.
ALLOWLISTABLE_ACTIONS = ("run-workflow",)
NEVER_ALLOWLISTABLE = ("merge-pr", "merge-api", "merge-graphql", "release", "force-push")

_KNOWN_GATE_ACTIONS = frozenset(a for a, *_ in OWNER_AUTHORITY_COMMANDS)

# Informational only — has no authority over the allow decision (workflow_run_dispatch does).
# Segment-scoped: gh before a workflow run token (tracks classifier shapes including repo flags).
_WORKFLOW_RUN_POINTER = re.compile(r"(?<!\S)workflow\s+run(?!\S)", re.I)

# bite-proof axis: refuses shell-expandable text, so an allow entry can never match
# a name the shell will substitute. Replaces an enumerated blacklist of expansion forms.
# Uses fullmatch (not $-anchored match) because $ exempts a trailing newline in Python.
_LITERAL_SAFE_COMMAND = re.compile(r"[A-Za-z0-9 _\-./:=,'\"@+]+")

# Repo flags change *where* the dispatch lands; ref flags change *which* ref's definition
# runs. The allow file is project-scoped, but only the command text is classified — ambient gh
# env overrides (e.g. GH_REPO) are invisible here (see reference doc). Input flags
# (-F/--field, -f/--raw-field, --json) are accepted as a deliberate v1 scope decision; an
# allow entry does not pin inputs — a pre-authorized workflow is pre-authorized with any
# inputs, which matters when a workflow's inputs influence what it checks out or runs.
_REPO_FLAGS = frozenset(("-R", "--repo"))
_REF_FLAGS = frozenset(("-r", "--ref"))
_REF_ANY_SENTINEL = "any"

_VALUE_FLAG_LONG = frozenset(("--field", "--raw-field"))
_VALUE_FLAGS = frozenset(("-F", "--field", "-f", "--raw-field"))


def owner_authority_action(command):
    """The action name (str) an owner-authority command performs, or None.

    Returns None for a non-string. Iterates OWNER_AUTHORITY_COMMANDS in order; the first hit
    wins. Matching is segment-scoped (split on ``;``, ``&``, ``|``, newline); within a segment
    the subcommand token must follow the tool word when a tool word is required."""
    if not isinstance(command, str):
        return None
    segments = _segments(command)
    # Rows OUTER, segments INNER — this preserves the shipped first-hit-wins precedence across the
    # whole command. Iterating segments first would let a later row in an earlier segment win.
    for action, tool, sub, trailing in OWNER_AUTHORITY_COMMANDS:
        for segment in segments:
            start = 0
            if tool is not None:
                m_tool = tool.search(segment)
                if not m_tool:
                    continue
                start = m_tool.end()
            m_sub = sub.search(segment, start)
            if not m_sub:
                continue
            if trailing is not None and not trailing.search(segment, m_sub.end()):
                continue
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

    entries: list of {"action": str, "workflow": str, "allows_refs": bool (optional)}
        allows_refs is True only when derived from a validated ref sentinel under a schema version
        in _REF_KEY_VERSIONS — never copied from file input.
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
    if not isinstance(ver, int) or isinstance(ver, bool) or ver not in ALLOW_SCHEMA_VERSIONS:
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

        allows_refs = False
        if "ref" in item:
            if ver not in _REF_KEY_VERSIONS:
                bump_hint = "schemaVersion " + " or ".join(
                    str(v) for v in sorted(_REF_KEY_VERSIONS))
                notes.append(("malformed", action,
                                "ignored entry with ref key under schemaVersion %s — "
                                "bump owner-authority-allow.json to %s"
                                % (ver, bump_hint)))
                continue
            ref_val = item.get("ref")
            if not isinstance(ref_val, str) or ref_val != _REF_ANY_SENTINEL:
                ref_hint = "schemaVersion " + " or ".join(
                    str(v) for v in sorted(_REF_KEY_VERSIONS))
                notes.append(("malformed", action,
                                "ignored entry with invalid ref %r — only ref: %r "
                                "is supported under %s"
                                % (ref_val, _REF_ANY_SENTINEL, ref_hint)))
                continue
            allows_refs = True

        entry = {"action": action, "workflow": workflow}
        if allows_refs:
            entry["allows_refs"] = True
        entries.append(entry)

    return entries, notes


def workflow_run_dispatch(command):
    """Parse a `gh workflow run` command into workflow name and optional ref, or None."""
    if not isinstance(command, str) or not command or len(command) > 4096:
        return None

    if not _LITERAL_SAFE_COMMAND.fullmatch(command):
        return None

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None

    if not tokens or tokens[0] != "gh":
        return None

    positionals = []
    ref = None
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        before_run = len(positionals) < 2
        if tok == "--":
            if before_run:
                return None
            positionals.extend(tokens[i + 1:])
            break
        if tok.startswith("-"):
            if "=" in tok:
                flag, value = tok.split("=", 1)
                # Defence-in-depth (currently redundant): repo flags are disjoint from _REF_FLAGS,
                # _VALUE_FLAG_LONG, and _VALUE_FLAGS, so later branches already return None — but this
                # guard must stay so a future repo-flag alias added to _VALUE_FLAGS cannot silently
                # open a scope change.
                if flag in _REPO_FLAGS:
                    return None
                if flag in _REF_FLAGS:
                    if not value or ref is not None:
                        return None
                    ref = value
                    i += 1
                    continue
                if before_run:
                    return None
                # bite-proof axis: flag values must not be misread as the workflow name.
                if flag not in _VALUE_FLAG_LONG:
                    return None
                i += 1
                continue
            # Same defence-in-depth repo-flag guard as the `flag=value` branch above.
            if tok in _REPO_FLAGS:
                return None
            if tok in _REF_FLAGS:
                if i + 1 >= len(tokens) or ref is not None:
                    return None
                ref = tokens[i + 1]
                if not ref:
                    return None
                i += 2
                continue
            if before_run:
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

    if (len(positionals) != 3 or positionals[0] != "workflow" or positionals[1] != "run"
            or not positionals[2]):
        return None
    return {"workflow": positionals[2], "ref": ref}


def allowlisted(command, action, entries):
    """True when entries pre-authorize this exact command/action pair. Pure — no I/O."""
    # bite-proof axis: only ALLOWLISTABLE_ACTIONS can ever match — structural exclusions
    # cannot reach silence via file content.
    if action not in ALLOWLISTABLE_ACTIONS:
        return False
    # Fail closed: this function resolves targets only via workflow_run_dispatch. A future
    # ALLOWLISTABLE_ACTIONS entry must ship its own extractor — do not fall through here.
    if action != "run-workflow":
        return False
    parsed = workflow_run_dispatch(command)
    if parsed is None:
        return False
    for entry in entries:
        if entry["action"] != action or entry["workflow"] != parsed["workflow"]:
            continue
        if parsed["ref"] is None or entry.get("allows_refs"):
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
    # Informational pointer only — segment-scoped gh/workflow-run shape, not workflow_run_dispatch.
    pointer_hit = False
    for segment in _segments(command):
        m_tool = _GH.search(segment)
        if m_tool and _WORKFLOW_RUN_POINTER.search(segment, m_tool.end()):
            pointer_hit = True
            break
    if pointer_hit:
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
