"""Workhorse action-boundary enforcer — the deterministic, non-bypassable floor.

Two surfaces:
  * Bash commands — refuse hard-floor actions by the ACTUAL command (an enumerated
    deny-list covering this repo's gh-based flow incl. the REST/GraphQL merge paths
    F5's git-only classify_floor never had), AND refuse Bash WRITES to safety-
    machinery (`sed -i`/redirection). A non-listed command is allowed — the producer
    must run build/test/git/gh commands. We do NOT defer to classify_floor for
    commands: its bare `git push` pattern would deny the producer's own required
    pushes.
  * Edit/Write/MultiEdit — refuse edits to band safety-machinery files (via F5's
    is_safety_machinery guard), so the ⑧ CI fixer can't disable the floor.

Fail-CLOSED: a non-string command, an unparseable hook payload, or any internal
error in the path guard DENIES. PROCESS-level fail-closed (the enforcer can't start
at all — missing python, import error) is handled by the hook-command wrapper in
§Task 6, which emits a deny when the enforcer exits non-zero. Run as a PreToolUse
hook: `enforcer.py hook` reads the hook JSON on stdin and emits a hookSpecificOutput
deny (or stays silent to allow).
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import band_lib  # noqa: E402

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ESC = ("the-architect", "lib", "escalation.py")
_RC = ("review-crew", "lib", "escalation_resolve.py")
_TOOLS_PATH = {"Edit", "Write", "MultiEdit"}

# Concrete hard-floor command deny-list — the AUTHORITATIVE floor for Bash
# commands. NOTE (resolved finding): we deliberately do NOT consult F5's
# classify_floor for command classification — its patterns include a bare
# `git push` (escalation.py FLOOR_PATTERNS), which would deny the producer's OWN
# required ③ branch push and ⑧ CI-fix pushes and wedge the core job. classify_floor
# stays the cooperative-layer signal (escalation prose); the deterministic command
# floor is this enumerated list. Covering the gh-based flow comprehensively
# (including the REST/GraphQL merge paths classify_floor never had) is what makes
# the floor real. A command not on this list is ALLOWED — the producer must run
# arbitrary build/test/git/gh commands; the floor is the enumerated set, and
# process-level fail-closed (the hook wrapper, §Task 6) covers "enforcer can't run".
DENY_COMMANDS = [
    ("merge-pr",     re.compile(r"\bgh\s+pr\s+merge\b", re.I)),
    ("merge-api",    re.compile(r"\bgh\s+api\b.*\bpulls/[^/\s]+/merge\b", re.I)),
    ("merge-graphql", re.compile(r"\bmergePullRequest\b", re.I)),
    ("release",      re.compile(r"\bgh\s+release\s+create\b", re.I)),
    ("run-workflow", re.compile(r"\bgh\s+workflow\s+(run|enable|disable)\b", re.I)),
    ("force-push",      re.compile(r"\bgit\s+push\b.*(--force\b|-f\b|--force-with-lease)", re.I)),
    # Deny pushes whose destination ref is the default branch (main/master). This
    # covers `git push origin main`, `git push origin HEAD:main`, and
    # `git push origin <src>:main` — while still allowing the producer's own
    # superheroes/* and other feature-branch pushes (those have no `:main`/` main`
    # destination). The pattern anchors on the destination ref, not the source.
    ("push-to-default", re.compile(r"\bgit\s+push\b[^;&|\n]*(?::|[ \t])(?:refs/heads/)?(main|master)(?:\s|$)", re.I)),
    ("deploy",          re.compile(r"\b(deploy|kubectl\s+apply|terraform\s+apply)|(?:^|\s)--prod\b", re.I)),
    ("destructive",     re.compile(r"\b(DROP\s+(TABLE|DATABASE|INDEX)|TRUNCATE|DELETE\s+FROM)\b", re.I)),
    ("rm-rf",           re.compile(r"\brm\s+-[a-z]*[rf][a-z]*[rf]", re.I)),
    # Self-check canary: a harmless shell no-op the ⓪ startup probe runs through
    # Bash to prove the hook is actually firing end-to-end (see §Task 6 / SKILL ⓪).
    ("canary",       re.compile(r"workhorse-enforcer-canary", re.I)),
]

# Safety-machinery basenames the Bash-write guard screens for. MUST be a superset
# of escalation.SAFETY_MACHINERY (asserted by a lock-step test, Task 6) so every file
# the Edit/Write surface protects is also screened on the Bash surface. This list is
# only a CHEAP PRE-FILTER: a token matching one of these is then confirmed through the
# SAME band-root-anchored guard the Edit surface uses (classify_path) before denying —
# so a like-named file in an arbitrary target repo (outside the band plugin tree) is
# NOT falsely refused, and `sed -i`/redirection at a real band file IS refused
# regardless of spacing (`>enforcer.py` and `> enforcer.py` alike).
_SAFETY_BASENAMES = (
    "escalation.py", "escalation_resolve.py", "loop_state.py", "circuit_breaker.py",
    "gate_write.py", "architect_lib.py", "definition_doc.py", "enforcer.py",
    "model_tier.py", "band_lib.py", "hooks.json", "escalation-base.md", "review-base.md",
)
_WRITE_OPS = re.compile(
    r"(>>?|\btee\b|\bsed\s+-i|\bcp\b|\bmv\b|\bdd\b|\btruncate\b|\bchmod\b|\bln\b)", re.I)
# Path-ish tokens, split on shell metacharacters so `>enforcer.py` yields `enforcer.py`.
_TOKENS = re.compile(r"[^\s'\"<>|;&()]+")


def _bash_writes_to_safety_machinery(command):
    """True iff a Bash command carries a mutating operator AND a token that RESOLVES
    to a real band safety-machinery file. The basename set is a pre-filter; the actual
    deny decision reuses classify_path (band-root anchored, fail-closed) so the spacing
    bypass and the target-repo false-positive both close. (A read-with-redirect like
    `cat <band>/enforcer.py > backup` is a fail-SAFE false positive — it denies a
    harmless command rather than risk a write; acceptable under the threat model.)

    Residual (accepted): a token that hides the literal basename — a glob
    (`enforc*.py`) or a shell variable (`$F`) — slips the pre-filter. Out of scope
    under the single-user honest-agent threat model (the threat is an honest-but-
    mistaken agent, which writes the literal path — caught here — not an adversary
    deliberately obfuscating). The Edit/Write tool surface (classify_path, fully
    anchored) remains the primary guard for the common, literal case."""
    if not _WRITE_OPS.search(command):
        return False
    for tok in _TOKENS.findall(command):
        if os.path.basename(tok) in _SAFETY_BASENAMES and classify_path(tok)[0] == "deny":
            return True
    return False


def classify_command(command):
    """('deny'|'allow', reason). Deny iff the command matches the concrete floor
    deny-list OR is a Bash write to safety-machinery. A non-listed command is
    ALLOWED (the producer must run build/test/git/gh commands); the floor is the
    enumerated set, and process-level failure is handled by the hook wrapper.
    Non-string input fails CLOSED (deny)."""
    if not isinstance(command, str):
        return ("deny", "non-string command (fail-closed)")
    for name, rx in DENY_COMMANDS:
        if rx.search(command):
            return ("deny", "hard-floor action '%s' is the owner's, not the producer's" % name)
    if _bash_writes_to_safety_machinery(command):
        return ("deny", "Bash write to band safety-machinery is refused")
    return ("allow", "")


def classify_path(path):
    """('deny'|'allow', reason) for an Edit/Write target. Deny iff the path is
    band safety-machinery. Resolution failure / error fails CLOSED (deny)."""
    if not isinstance(path, str) or not path:
        return ("deny", "missing path (fail-closed)")
    try:
        lib = band_lib.resolve_target(_ESC, plugin_root=_PLUGIN_ROOT)
        if lib is None:
            return ("deny", "escalation lib unresolvable (fail-closed)")
        band_roots = [_PLUGIN_ROOT, os.path.dirname(os.path.dirname(lib))]
        rc = band_lib.resolve_target(_RC, plugin_root=_PLUGIN_ROOT)
        if rc:
            band_roots.append(os.path.dirname(os.path.dirname(rc)))
        cli = [sys.executable, lib, "guard", "--path", path]
        for r in band_roots:
            cli += ["--band-root", r]
        p = subprocess.run(cli, capture_output=True, text=True, timeout=10)
        if p.returncode != 0:
            return ("deny", "guard error (fail-closed)")
        res = json.loads(p.stdout.strip())
        if res.get("allow") is True:
            return ("allow", "")
        return ("deny", "edit to band safety-machinery is refused")
    except Exception:
        return ("deny", "guard exception (fail-closed)")


def _deny(reason):
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "workhorse enforcer: " + reason,
        }
    }) + "\n")


def hook(stdin_text):
    """Read a PreToolUse payload; emit a deny on a floor violation, else allow
    (silent). Fail-CLOSED: an unparseable payload denies."""
    try:
        payload = json.loads(stdin_text)
    except (ValueError, json.JSONDecodeError):
        _deny("unparseable hook payload (fail-closed)")
        return 0
    tool = payload.get("tool_name")
    ti = payload.get("tool_input") or {}
    if tool == "Bash":
        decision, reason = classify_command(ti.get("command"))
    elif tool in _TOOLS_PATH:
        decision, reason = classify_path(ti.get("file_path"))
    else:
        decision, reason = ("allow", "")
    if decision == "deny":
        _deny(reason)
    return 0


def selfcheck():
    """Deterministic startup self-check: the classifier behaves, the escalation lib
    the Edit guard depends on RESOLVES, and the hook config exists. Exit 0 iff armed;
    the producer refuses to run on non-zero."""
    ok = (classify_command("gh pr merge 1")[0] == "deny"
          and classify_command("git commit -m x")[0] == "allow")
    # The Edit guard (classify_path) needs escalation.py. If it's unresolvable, the
    # guard fail-closes to deny EVERYTHING — which would still PASS the ⓪ canaries
    # (deny is their expected outcome) yet wedge ① Build with misdirecting per-edit
    # denials. Surface the broken install HERE, at startup, with the right diagnosis.
    esc_ok = band_lib.resolve_target(_ESC, plugin_root=_PLUGIN_ROOT) is not None
    hook_cfg = os.path.join(_PLUGIN_ROOT, "hooks", "hooks.json")
    has_cfg = os.path.isfile(hook_cfg)
    armed = ok and esc_ok and has_cfg
    sys.stdout.write(json.dumps({"armed": bool(armed), "classifier_ok": bool(ok),
                                 "escalation_resolved": bool(esc_ok),
                                 "hook_config": has_cfg}) + "\n")
    return 0 if armed else 1


def main(argv):
    cmd = argv[1] if len(argv) > 1 else None
    if cmd == "hook":
        return hook(sys.stdin.read())
    if cmd == "selfcheck":
        return selfcheck()
    if cmd == "check":
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--command")
        ap.add_argument("--path")
        args = ap.parse_args(argv[2:])
        if args.command is not None:
            decision, reason = classify_command(args.command)
        elif args.path is not None:
            decision, reason = classify_path(args.path)
        else:
            sys.stderr.write("check needs --command or --path\n")
            return 2
        sys.stdout.write(json.dumps({"decision": decision, "reason": reason}) + "\n")
        return 0
    sys.stderr.write("Usage: enforcer.py hook|selfcheck|check [...]\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
