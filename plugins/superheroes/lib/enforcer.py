"""Workhorse action-boundary enforcer — the deterministic live owner-approval GATE.

Two surfaces:
  * Bash commands — the OWNER-AUTHORITY / irreversible set (an enumerated list covering
    this repo's gh-based flow incl. the REST/GraphQL merge paths) is GATED, not floored:
    it needs the owner's live, in-turn approval. The mechanism is host-aware (issue #14):
      - Claude Code (`--host claude`, ask honored): emit `permissionDecision: ask` — a
        native human prompt the agent cannot answer itself.
      - Codex / any other host (ask NOT honored — fail-safe default): emit `deny` and run
        the two-part single-use ALLOWANCE flow (lib/allowance.py): a hook-issued nonce →
        the owner approves → the next matching call is allowed once.
    The gate is SCOPED to superheroes repos (cwd resolves under a `docs/superheroes/`
    tree); outside one, the gated set is ALLOWED (the gate is meaningful only where the
    producer operates). Two things stay an UNCONDITIONAL hard deny (host- and
    scope-independent): a Bash WRITE to safety-machinery (`sed -i`/redirection), and the
    self-check canary sentinel.
  * Edit/Write/MultiEdit — refuse edits to band safety-machinery files (via F5's
    is_safety_machinery guard), so the step 8 CI fixer can't disable the gate. UNCONDITIONAL.

Fail-CLOSED on the safety surfaces (non-string command, unparseable payload, path-guard
error → deny). Fail-SAFE on the gate scope (cwd undetectable → allow only the gated set;
the producer always runs in a detected repo, so its park guarantee is preserved). The
host signal is passed by the hook wiring (`hook --host claude`); an unknown/missing host
takes the deny path, so an un-honored `ask` can never become an unsupervised action.
PROCESS-level fail-closed (the enforcer can't start at all) is handled by the
hook-command wrapper, which emits a deny when the enforcer exits non-zero.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allowance  # noqa: E402
import escalation  # noqa: E402  (same-tree sibling core; no band_lib, no subprocess)
import permission_rules  # noqa: E402  (pure below-the-floor allowance layer; non-gated branch only)

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Tool-name surfaces, HOST-AGNOSTIC: Claude names Bash / Edit|Write|MultiEdit; Codex names
# shell / apply_patch (the patch carries the target path in its body). Accepting both makes
# the single enforcer.py genuinely host-agnostic — without the `shell`/`apply_patch` aliases
# the Codex gate and edit-guard would silently fall through to allow.
_CMD_TOOLS = {"Bash", "shell"}
_TOOLS_PATH = {"Edit", "Write", "MultiEdit"}
_PATCH_TOOLS = {"apply_patch"}
_SUPERHEROES_MARKER = ("docs", "superheroes")
# apply_patch file headers: `*** Add|Update|Delete File: <path>` and `*** Move to: <path>`.
_PATCH_TARGET = re.compile(
    r"^\*\*\*\s+(?:(?:Add|Update|Delete)\s+File|Move\s+to):\s*(.+?)\s*$", re.M)

# The owner-authority action set — GATED (live owner approval), not floored. Matched by the
# ACTUAL command (enumerated; covers the gh REST/GraphQL merge paths F5's git-only
# classify_floor never had). A command not on this list is ALLOWED — the producer must run
# build/test/git/gh commands. We deliberately do NOT consult F5's classify_floor for command
# classification: its bare `git push` pattern would deny the producer's OWN required steps 3/8
# pushes and wedge the core job.
#
# SCOPE PRINCIPLE (deliberate — see SKILL.md "Scope of the deterministic gate"): this set is
# only the actions that encode an OWNER-ROLE / repo-shaping invariant the host harness cannot
# express — "the producer never merges / publishes / pushes to the default branch / rewrites
# shared history." A hook `ask` is worth its keep here precisely because it OVERRIDES an
# allowlist-allow and fires even under bypassPermissions (the one thing the harness's own
# prompt can't guarantee). It deliberately does NOT re-implement GENERIC dangerous-command
# detection (`rm -rf`, destructive SQL, `deploy`/`kubectl apply`/`--prod`): those are already
# contemplated by the harness (its permission prompt in prompting modes + its built-in
# `rm -rf /|~` circuit breaker in bypass), they are broad and false-positive-prone on a build
# agent (a routine `rm -rf node_modules` is not an owner action), and they remain covered by
# the COOPERATIVE F5 layer (escalation.FLOOR_PATTERNS still lists deploy/destructive/delete →
# the model GATEs them). This mirrors the earlier choice to keep F5's spend/egress heuristics
# off the deterministic hook.
GATED_COMMANDS = [
    ("merge-pr",     re.compile(r"\bgh\s+pr\s+merge\b", re.I)),
    ("merge-api",    re.compile(r"\bgh\s+api\b.*\bpulls/[^/\s]+/merge\b", re.I)),
    ("merge-graphql", re.compile(r"\bmergePullRequest\b", re.I)),
    ("release",      re.compile(r"\bgh\s+release\s+create\b", re.I)),
    ("run-workflow", re.compile(r"\bgh\s+workflow\s+(run|enable|disable)\b", re.I)),
    ("force-push",      re.compile(r"\bgit\s+push\b.*(--force\b|-f\b|--force-with-lease)", re.I)),
    # Deny pushes whose destination ref is the default branch (main/master). Covers
    # `git push origin main`, `git push origin HEAD:main`, and `git push origin
    # <src>:main` — while still allowing the producer's own superheroes/* feature-branch
    # pushes (no `:main`/` main` destination). Anchors on the destination ref.
    ("push-to-default", re.compile(r"\bgit\s+push\b[^;&|\n]*(?::|[ \t])(?:refs/heads/)?(main|master)(?:\s|$)", re.I)),
]

# Self-check canary: a harmless shell no-op the step 0 startup probe runs through Bash to
# prove the hook is firing end-to-end. UNCONDITIONAL deny (its expected outcome is deny;
# it is not an owner action and must never be gateable / scope-dependent).
_CANARY = re.compile(r"workhorse-enforcer-canary", re.I)

# Safety-machinery basenames the Bash-write guard screens for. MUST be a superset of
# escalation.SAFETY_MACHINERY (asserted by a lock-step test) so every file the Edit/Write
# surface protects is also screened on the Bash surface. CHEAP PRE-FILTER only: a token
# matching one of these is confirmed through the SAME band-root-anchored guard
# (classify_path) before denying — so a like-named file in an arbitrary target repo is NOT
# falsely refused, and `sed -i`/redirection at a real band file IS refused regardless of
# spacing.
# Derived from the single source (escalation.SAFETY_MACHINERY) so the two can't drift.
# Contract: SAFETY_MACHINERY ⊆ _SAFETY_BASENAMES — the enforcer's edit-guard may protect a
# SUPERSET of the escalation floor; append any enforcer-only basenames to the tuple below
# (none today).
_SAFETY_BASENAMES = tuple(escalation.SAFETY_MACHINERY)
# File-mutating commands whose write DESTINATION is a file ARGUMENT (not a redirection),
# defined ONCE so the early-out gate (`_WRITE_OPS`) and the per-segment matcher
# (`_FILE_WRITE_CMD`) can never drift apart (they encode the same "this command mutates a
# file by argument" decision). `sed` in-place covers both the short `-i`/`-i.bak` and the
# GNU long `--in-place`/`--in-place=SUFFIX` forms.
_FILE_CMD_ALT = r"sed\s+(?:-i|--in-place)|tee|cp|mv|dd|truncate|chmod|ln"
# Any write operator at all — the cheap pre-filter. Redirections (`>`/`>>`) plus the
# file-mutating commands above. A command matching none of these can't write anything.
_WRITE_OPS = re.compile(r"(>>?|\b(?:" + _FILE_CMD_ALT + r")\b)", re.I)
# A safety file must appear in the SAME command segment as one of these keywords to count
# as a write — so a band CLI run as an EXECUTION target (`python3 definition_doc.py …`) in
# another segment is never mistaken for writing it.
_FILE_WRITE_CMD = re.compile(r"\b(?:" + _FILE_CMD_ALT + r")\b", re.I)
# Path-ish tokens, split on shell metacharacters so `>enforcer.py` yields `enforcer.py`.
_TOKENS = re.compile(r"[^\s'\"<>|;&()]+")
# A redirection's WRITE TARGET: optional fd digits, `>`/`>>`, an optional `&` or `|`
# (the `>&word` both-streams form and the `>|` noclobber override), optional spaces, then
# the target — a single/double-quoted literal OR a bare token. The `&` is consumed so
# `>&enforcer.py` (redirect BOTH stdout+stderr into the file — a real write) captures
# `enforcer.py`; the fd-duplication forms `2>&1` / `>&2` / `>&-` also match but capture a
# digit / `-`, which fails the basename check harmlessly. The quoted alternatives restore
# the coverage the pre-rewrite whole-command tokenizer had (quotes stripped via _unquote),
# so `> "enforcer.py"` is not a bypass.
_REDIRECT_TARGET = re.compile(
    r"\d*>>?[&|]?\s*(\"[^\"]*\"|'[^']*'|[^\s'\"<>|;&()]+)")
# `dd` names its write destination with the `of=<path>` keyword operand (not a bare arg),
# so a band file there is invisible to the basename token walk (`of=enforcer.py`'s basename
# is the whole token). Capture the of= value explicitly. `if=` (the READ input) is NOT
# captured — reading a band file is not a write.
_DD_OF = re.compile(r"\bof=([^\s'\"<>|;&()]+)", re.I)
# Split a compound command into segments on shell control operators, so a mutating keyword
# in one segment is not associated with a safety token in another.
_SEGMENT_SPLIT = re.compile(r"&&|\|\||[;&|\n]")


def _unquote(tok):
    """Strip a single matched surrounding quote pair, so a quoted redirect target
    (`"enforcer.py"`) resolves to its bare path. Bare tokens pass through unchanged."""
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'":
        return tok[1:-1]
    return tok


def _resolves_to_band(tok):
    """True iff `tok`'s basename is a safety basename AND it resolves (band-root anchored)
    to a real band file. The cheap basename test short-circuits so non-safety targets
    (`/dev/null`, an ordinary out path) never pay the classify_path guard call."""
    return os.path.basename(tok) in _SAFETY_BASENAMES and classify_path(tok)[0] == "deny"


def _bash_writes_to_safety_machinery(command):
    """True iff a Bash command's WRITE TARGET resolves to a real band safety-machinery
    file — either a redirection (`> f` / `>> f` / `>| f`, quoted or bare) AT the file, or a
    file-mutating command (`sed -i`/`--in-place`, `tee`/`cp`/`mv`/`dd`/`truncate`/`chmod`/
    `ln`) with the file as an argument (incl. `dd`'s `of=` operand).

    The guard keys off the operator's TARGET, not mere co-occurrence: an unrelated
    `>/dev/null` / `2>&1` redirect, or a band CLI passed as an EXECUTION arg
    (`python3 definition_doc.py …`), is NOT a write to the band file. (A read-redirect AT
    a band file is a fail-SAFE false positive — acceptable under the threat model.)"""
    if not _WRITE_OPS.search(command):
        return False
    # Redirection writes: the deny requires the redirect's TARGET to be a band file.
    for target in _REDIRECT_TARGET.findall(command):
        if _resolves_to_band(_unquote(target)):
            return True
    # File-mutating commands: the band file must share the segment with the keyword (so an
    # exec target / unrelated redirect in a neighbouring segment doesn't trip the match).
    for segment in _SEGMENT_SPLIT.split(command):
        if not _FILE_WRITE_CMD.search(segment):
            continue
        for tok in _TOKENS.findall(segment) + _DD_OF.findall(segment):
            if _resolves_to_band(tok):
                return True
    return False


def gated_action(command):
    """The owner-authority action name this command performs, or None. Used both by the
    classifier (gate decision) and by the hook (whether to run the Codex allowance
    overlay). Canary / safety-writes are NOT gated actions — they are unconditional
    denies, handled separately."""
    if not isinstance(command, str):
        return None
    for name, rx in GATED_COMMANDS:
        if rx.search(command):
            return name
    return None


def _in_superheroes_repo(cwd):
    """True iff `cwd` (or an ancestor) contains a `docs/superheroes/` tree — the canonical
    superheroes pipeline artifact dir. Bounded walk to the filesystem root. Undetectable
    (no cwd / error) → False (the gate fail-SAFEs to 'not scoped' → the gated set is
    allowed; the producer always runs in a detected repo, preserving its park guarantee)."""
    if not cwd or not isinstance(cwd, str):
        return False
    try:
        d = os.path.abspath(cwd)
        while True:
            if os.path.isdir(os.path.join(d, *_SUPERHEROES_MARKER)):
                return True
            parent = os.path.dirname(d)
            if parent == d:
                return False
            d = parent
    except Exception:
        return False


def classify_command(command, host="codex", in_scope=True, cwd=None, run_id=None):
    """('allow'|'ask'|'deny', reason). Decision order:

      1. non-string                         → deny (fail-closed)
      2. canary sentinel                    → deny (unconditional)
      3. Bash write to safety-machinery     → deny (unconditional)
      4. owner-authority (gated) action:
           - outside a superheroes repo     → allow (not gated here)
           - in-scope, host honors `ask`    → ask  (live owner prompt)
           - in-scope, deny-only host       → deny (the hook runs the allowance overlay)
      5. non-gated (today = allow): consult the below-the-floor allowance layer
         (permission_rules.evaluate). A matching owner-curated routine family / managed-
         worktree-confined / composed-exact command turns a would-be prompt into `allow`;
         anything else falls through to today's default allow.
      6. default                            → allow

    `host`/`in_scope` affect ONLY the gated set. Default host=`codex` (deny-only) is the
    fail-safe: only an explicit host that honors `ask` unlocks the prompt. `cwd`/`run_id`
    thread the hook's context into the allowance layer; both default to `None` (no active
    run → the layer's composed/freeze machinery is inert). The allowance layer is reached
    ONLY here, on the non-gated branch: the canary/safety-write/owner-role arms all `return`
    above it, so it can never widen the floor (UFR-1). Any allowance error is swallowed and
    falls through to today's default allow (fail-safe toward the existing outcome, UFR-2)."""
    if not isinstance(command, str):
        return ("deny", "non-string command (fail-closed)")
    if _CANARY.search(command):
        return ("deny", "enforcer canary (self-check sentinel)")
    if _bash_writes_to_safety_machinery(command):
        return ("deny", "Bash write to band safety-machinery is refused")
    action = gated_action(command)
    if action:
        if not in_scope:
            return ("allow", "")
        if host == "claude":
            return ("ask", "owner-authority action '%s' needs your live approval" % action)
        return ("deny", "owner-authority action '%s' needs the owner's live approval" % action)
    # Non-gated branch (today: unconditional allow). Consult the allowance layer; it can only
    # turn a would-be prompt into an allow, never flip an allow to a deny.
    try:
        verdict, why = permission_rules.evaluate(command, cwd, run_id)
        if verdict == "allow":
            return ("allow", "auto-allowed (%s)" % why)
    except Exception:
        pass
    return ("allow", "")


def classify_path(path):
    """('deny'|'allow', reason) for an Edit/Write target. Deny iff the path is band
    safety-machinery. UNCONDITIONAL (host- and scope-independent). Any error fails CLOSED
    (deny). In the consolidated tree the escalation core is a same-tree sibling, so this
    calls `escalation.is_safety_machinery` DIRECTLY (no resolver, no subprocess), anchored on
    the single merged plugin root — the three per-plugin band roots collapsed into one."""
    if not isinstance(path, str) or not path:
        return ("deny", "missing path (fail-closed)")
    try:
        if escalation.is_safety_machinery(path, [_PLUGIN_ROOT]):
            return ("deny", "edit to band safety-machinery is refused")
        return ("allow", "")
    except Exception:
        return ("deny", "guard exception (fail-closed)")


def _strings(obj):
    """Every string leaf in a JSON-ish value (robust to the host's tool_input key names)."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)


def _command_text(ti):
    """The shell command from a Bash/Codex-shell payload. `command` may be a string
    (Claude Bash) or an argv list (Codex shell); otherwise fall back to all string leaves
    so a gated-pattern match can still fire (fail-SAFE — extra text can only over-deny,
    never falsely allow a gated action)."""
    c = ti.get("command")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(str(x) for x in c)
    return "\n".join(_strings(ti))


def _classify_patch(ti):
    """apply_patch edit guard (Codex): deny iff any target path resolves to band
    safety-machinery. Targets are parsed from the patch body's file headers, scanning
    every string value. No safety target found (incl. an unparseable patch) → allow —
    don't wedge the producer's ordinary Codex edits; this mirrors the Bash-write guard's
    literal-path posture under the honest-agent threat model."""
    text = "\n".join(_strings(ti))
    for path in _PATCH_TARGET.findall(text):
        p = path.strip()
        # Cheap basename pre-filter (mirrors the Bash-write guard), then confirm through
        # the band-root-anchored classify_path so an ordinary edit costs no guard call and
        # a target-repo lookalike isn't false-refused.
        if os.path.basename(p) in _SAFETY_BASENAMES and classify_path(p)[0] == "deny":
            return ("deny", "apply_patch to band safety-machinery is refused")
    return ("allow", "")


def _emit(decision, reason):
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": "workhorse enforcer: " + reason,
        }
    }) + "\n")


def _codex_gate_reason(command, action, cwd):
    """Deny reason for a Codex gated action: issue a fresh challenge (in this checkout)
    and tell the agent how to mint the single-use allowance AFTER the owner approves this
    turn. `approve` takes the command-HASH (not the literal command) so the approve
    invocation does not itself contain the gated substring (which would re-trip the
    classifier)."""
    nonce = allowance.challenge(command, action, cwd)
    h = allowance.command_hash(command)
    return (
        "owner-authority action '%s' needs the owner's live approval, and this host "
        "cannot prompt. Stop and ask the owner (escalation GATE). With NO approver "
        "(unattended/autonomous) → leave it denied; the loop parks here. On the owner's "
        "explicit in-turn approval, mint a single-use %ds allowance: "
        "`python3 \"%s/lib/enforcer.py\" approve --command-hash %s --nonce %s`, then "
        "re-run the SAME command once." % (
            action, allowance.DEFAULT_TTL, _PLUGIN_ROOT, h, nonce)
    )


def _active_run_id(cwd):
    """The `run_id` of the currently-active run for `cwd`'s work-item, or None.

    "A run is active" is the existing `ref_lock` lease on the work-item's lock ref; its
    `generation` field is the `run_id` the spine freezes/composes under. This threads that
    signal into the allowance layer so the composed/freeze machinery is inert outside an
    active run (FR-3) — an interactive session with no lease sees `run_id=None`.

    Fail-SAFE (UFR-2): any error — no store, no current work-item, an absent/None lease
    (`read_lease` returns a `(blob_sha, lease_dict)` TUPLE; a missing ref or unreadable blob
    yields a `None` lease), or a stale lease — resolves to None, never to a spurious run_id.
    A None run_id only makes the layer MORE conservative (composed/freeze cannot fire), so
    the fail-safe direction is always toward prompting. Deps are imported here (not at module
    load) to keep the enforcer's hot classify path free of the control-plane import chain."""
    try:
        import control_plane
        import ref_lock
        store = control_plane.checkout_dir(cwd)
        work_item = control_plane.get_current(cwd)
        if not work_item:
            return None
        _sha, lease = ref_lock.read_lease(store, work_item)
        if not isinstance(lease, dict):
            return None
        if ref_lock.is_stale(lease, ref_lock.DEFAULT_TTL):
            return None
        return lease.get("generation")
    except Exception:
        return None


def hook(stdin_text, host="codex"):
    """Read a PreToolUse payload; emit allow (silent) / ask / deny. Fail-CLOSED: an
    unparseable payload denies. The gated set is host- and scope-aware; on the deny-only
    (Codex) path it runs the single-use allowance overlay (consume → allow, else issue a
    challenge and deny)."""
    try:
        payload = json.loads(stdin_text)
    except (ValueError, json.JSONDecodeError):
        _emit("deny", "unparseable hook payload (fail-closed)")
        return 0
    tool = payload.get("tool_name")
    ti = payload.get("tool_input") or {}
    cwd = payload.get("cwd")
    in_scope = _in_superheroes_repo(cwd)
    if tool in _CMD_TOOLS:
        command = _command_text(ti)
        # Resolve the active run's run_id ONCE per hook invocation (a single Bash call), then
        # thread it + the payload cwd into the allowance layer via classify_command.
        run_id = _active_run_id(cwd)
        decision, reason = classify_command(command, host=host, in_scope=in_scope,
                                            cwd=cwd, run_id=run_id)
        action = gated_action(command)
        # Codex (deny-only host) gated overlay: the deny is the BACKSTOP that forces the
        # ask; a live owner-minted allowance lets the next matching call through once.
        # Guard on the deny ORIGIN — a command that ALSO trips the unconditional canary /
        # safety-write surfaces must never enter the allowance flow (else an owner could
        # approve a compound `cp x <band>/enforcer.py && gh pr merge` and the safety-write
        # would ride through). Re-checking those surfaces here keeps them unconditional.
        if (decision == "deny" and host != "claude" and in_scope and action
                and not _CANARY.search(command)
                and not _bash_writes_to_safety_machinery(command)):
            if allowance.consume(command, cwd):
                decision, reason = ("allow", "")
            else:
                reason = _codex_gate_reason(command, action, cwd)
    elif tool in _TOOLS_PATH:
        decision, reason = classify_path(ti.get("file_path"))
    elif tool in _PATCH_TOOLS:
        decision, reason = _classify_patch(ti)
    else:
        decision, reason = ("allow", "")
    if decision in ("deny", "ask"):
        _emit(decision, reason)
    return 0


def selfcheck():
    """Deterministic startup self-check: the gate classifies the full matrix correctly,
    the escalation lib the Edit guard depends on RESOLVES, and the hook config exists.
    Exit 0 iff armed; the producer refuses to run on non-zero."""
    # The classifier matrix, including the below-the-floor allowance layer. A broken
    # allowance layer that RAISES must be reported here (armed=0), not crash selfcheck — so
    # the whole matrix is evaluated inside a try/except that fail-closes `ok` to False.
    try:
        ok = (
            # gated merge: ask on Claude, deny on a deny-only host (both in-scope)...
            classify_command("gh pr merge 1", host="claude", in_scope=True)[0] == "ask"
            and classify_command("gh pr merge 1", host="codex", in_scope=True)[0] == "deny"
            # ...and NOT gated outside a superheroes repo (flaw #1)...
            and classify_command("gh pr merge 1", host="claude", in_scope=False)[0] == "allow"
            # ...unconditional surfaces hold regardless of host/scope...
            and classify_command(": workhorse-enforcer-canary")[0] == "deny"
            # ...and the producer's own commands stay allowed.
            and classify_command("git commit -m x")[0] == "allow"
            # Task 6 (UFR-1): the allowance layer NEVER widens the owner-role floor. Even the
            # broadest hypothetical rule cannot flip a gated action — Task 4's defensive
            # gated_action re-check inside evaluate guarantees it — so the gated outcomes above
            # hold WITH the layer live. Re-assert against an owner-role command that also
            # threads a cwd/run_id (the exact shape the hook now passes), proving the layer's
            # presence on the non-gated branch did not leak into the gated arms.
            and classify_command("gh pr merge 1", host="claude", in_scope=True,
                                 cwd=None, run_id=None)[0] == "ask"
            and classify_command("gh release create v1", host="codex", in_scope=True,
                                 cwd=None, run_id=None)[0] == "deny"
            # Task 6 (observability): a would-be routine command with NO rules store present
            # stays allow-by-default — the layer can only turn a would-be prompt INTO an allow,
            # it never DENIES. (No active run / no store → evaluate falls through → default allow.)
            and classify_command("python3 -m pytest", host="claude", in_scope=True,
                                 cwd=None, run_id=None)[0] == "allow"
        )
    except Exception:
        ok = False
    # The Edit guard (classify_path) needs the escalation core. If it can't be imported, the
    # guard fail-closes to deny EVERYTHING — which would still PASS the step 0 canaries yet wedge
    # step 1 Build with misdirecting per-edit denials. Surface the broken install HERE. Direct
    # in-tree probe (the core is a same-tree sibling now; no cross-plugin resolution).
    try:
        import escalation  # noqa: F401  (probe: importability == armed-ness signal)
        esc_ok = True
    except Exception:
        esc_ok = False
    hook_cfg = os.path.join(_PLUGIN_ROOT, "hooks", "hooks.json")
    has_cfg = os.path.isfile(hook_cfg)
    armed = ok and esc_ok and has_cfg
    sys.stdout.write(json.dumps({"armed": bool(armed), "classifier_ok": bool(ok),
                                 "escalation_resolved": bool(esc_ok),
                                 "hook_config": has_cfg}) + "\n")
    return 0 if armed else 1


def _host_from(argv):
    """Parse `--host X` (default 'codex' — the fail-safe deny-only behavior; only an
    explicit `--host claude` unlocks the native `ask` prompt)."""
    if "--host" in argv:
        i = argv.index("--host")
        if i + 1 < len(argv):
            return argv[i + 1]
    return "codex"


def main(argv):
    cmd = argv[1] if len(argv) > 1 else None
    if cmd == "hook":
        return hook(sys.stdin.read(), host=_host_from(argv[2:]))
    if cmd == "selfcheck":
        return selfcheck()
    if cmd == "approve":
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--command-hash", required=True)
        ap.add_argument("--nonce", required=True)
        args = ap.parse_args(argv[2:])
        # The agent runs `approve` from within the worktree, so os.getcwd() is the same
        # checkout the hook challenged — the per-checkout namespace lines up.
        ok = allowance.approve(args.command_hash, args.nonce, cwd=os.getcwd())
        sys.stdout.write(json.dumps({"approved": bool(ok)}) + "\n")
        return 0 if ok else 1
    if cmd == "check":
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--command")
        ap.add_argument("--path")
        ap.add_argument("--host", default="codex")
        # in_scope defaults True (store_false's implicit default); pass --out-of-scope to flip it.
        ap.add_argument("--out-of-scope", dest="in_scope", action="store_false")
        args = ap.parse_args(argv[2:])
        if args.command is not None:
            decision, reason = classify_command(args.command, host=args.host,
                                                in_scope=args.in_scope)
        elif args.path is not None:
            decision, reason = classify_path(args.path)
        else:
            sys.stderr.write("check needs --command or --path\n")
            return 2
        sys.stdout.write(json.dumps({"decision": decision, "reason": reason}) + "\n")
        return 0
    sys.stderr.write("Usage: enforcer.py hook|selfcheck|approve|check [...]\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
