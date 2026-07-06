# plugins/superheroes/lib/permission_rules.py
"""Project-level courier allow-rules (issue #255 classifier-block mitigation).

Generates and applies the Bash permission rules that authorize the showrunner
spine's own courier transport at the PROJECT level, so the runtime safety
classifier's sanctioned override path — explicit user authorization in settings —
covers the pipeline without any user-wide changes.

Two settings keys are written (the auto-mode permission system is two gates):
  - ``permissions.allow``  — skips the ordinary permission prompt for the rules;
  - ``autoMode.allow``     — the documented exception list the auto-mode safety
    classifier honors (allow rules alone do NOT pre-empt the classifier: it is
    "a second gate that runs after the permissions system", auto-mode-config docs).

Two storage modes (owner decision, mirrors CONVENTIONS §7.4):
  - ``in-repo`` → ``.claude/settings.json``       (committed, team-shared; NOTE the
    generated rules embed this checkout's absolute paths — collaborators on other
    machines re-run configure, which merges their paths in additively);
  - ``local``   → ``.claude/settings.local.json`` (machine-local; Claude Code
    gitignores this file when IT creates it — when this CLI creates it fresh, the
    caller/skill must ensure it is ignored — zero committed traces).

Rule design (matches the courier command shapes the classifier blocked live,
runs 2026-07-06, journal wf_4341ae7b + child sessions 028b4143/3dd3c3ed):
  - rooted compounds keep their `cd '<root>' && ` scoping in ONE full-compound
    rule (Claude Code splits compounds on && for per-atom matching, but a rule
    may also match the full compound string);
  - the io-seam write anchors on the spine's own heredoc marker __SR_EOF__ —
    distinctive, so the rule authorizes ONLY the spine's write protocol;
  - un-rooted variants cover normal (non-eval) runs where __SR_ROOT is unset;
  - the plugin-cache prefix is version-agnostic (covers upgrades without regen).

Pure decider + injectable IO, house style: `generate()`/`merge()` are pure;
`apply()` does the read-modify-write with a read-back verify and never clobbers
unrelated keys. Fail-closed: unparseable existing settings -> {"ok": false}.
"""
import argparse
import json
import os
import sys

SCHEMA_KEYS = ("permissions", "autoMode")


def _wt_root():
    return os.path.abspath(os.path.expanduser(
        os.environ.get("SUPERHEROES_WORKTREES_ROOT", "~/.superheroes-worktrees")))


def _cache_base():
    # Version-agnostic plugin-cache prefix: covers every installed plugin version.
    return os.path.abspath(os.path.expanduser("~/.claude/plugins/cache/superheroes/superheroes/"))


def generate(root, worktrees_root=None, cache_base=None):
    """The project's courier allow-rule list (deterministic, sorted for stable diffs).

    Every rule is either rooted at THIS project (`cd '<root>' && ...`), scoped to
    the managed-worktree base, anchored on the spine's own protocol marker, or
    prefixed by the plugin-cache lib path — never a blanket verb grant.
    """
    root = os.path.abspath(os.path.expanduser(str(root)))
    wt = worktrees_root or _wt_root()
    cache = cache_base or _cache_base()
    rules = [
        # Rooted eval/live-run couriers: python3 lib CLIs, io heredoc writes, probes.
        "Bash(cd '%s' && python3 *)" % root,
        "Bash(cd '%s' && test *)" % root,
        "Bash(cd '%s' && mkdir *)" % root,
        "Bash(cd '%s' && cat *)" % root,
        # Managed build worktrees (git/build/test ops inside the spine's own trees;
        # the enforcer hooks still deny gated verbs — merge/release/force-push —
        # regardless of any allow rule, so breadth here stays floor-bounded).
        "Bash(cd '%s/'*)" % wt,
        # Un-rooted normal-run shapes (__SR_ROOT unset): lib CLIs from the plugin
        # cache (any version), the spine's own heredoc write protocol, io tmp ops.
        "Bash(python3 %s*)" % cache,
        "Bash(python3 - <<'__SR_EOF__'*)",
        "Bash(mkdir -p /tmp/showrunner-*)",
        "Bash(cat /tmp/showrunner-*)",
    ]
    return sorted(rules)


# The headless tier: what a DEFAULT-MODE headless child additionally needs. In default
# mode nothing is auto-approved beyond explicit rules, and run-5's command inventory
# showed leaves emit free-form shapes (bare find/grep/ls, unquoted cd, python3 -c) the
# scoped tier cannot anchor. These are read-mostly verbs plus the spine's git/gh surface;
# the enforcer PreToolUse floor still denies gated verbs (merge/release/force-push/
# push-to-default) regardless of any allow rule, so the tier stays floor-bounded. Offered
# ONLY for headless spine children (the harness), never in the configure tune offer.
_HEADLESS_VERBS = ("cat", "cd", "diff", "echo", "find", "grep", "gh issue view",
                   "gh pr", "git", "head", "ls", "mkdir", "node", "python3", "sed -n",
                   "sort", "tail", "test", "wc")


def generate_headless(root, worktrees_root=None, cache_base=None):
    """Scoped tier + the headless verb tier (deduped, sorted)."""
    scoped = generate(root, worktrees_root, cache_base)
    verbs = ["Bash(%s *)" % v for v in _HEADLESS_VERBS]
    return sorted(set(scoped + verbs))


def merge(settings, rules):
    """Pure merge: add rules to permissions.allow AND autoMode.allow, deduped,
    preserving every unrelated key and any pre-existing rule order (new rules
    append sorted). Returns (merged, added_count)."""
    out = dict(settings or {})
    added = 0
    for key in SCHEMA_KEYS:
        block = dict(out.get(key) or {})
        existing = list(block.get("allow") or [])
        fresh = [r for r in rules if r not in existing]
        if fresh:
            block["allow"] = existing + fresh
            out[key] = block
            added += len(fresh)
    return out, added


def settings_path(root, mode):
    name = "settings.json" if mode == "in-repo" else "settings.local.json"
    return os.path.join(os.path.abspath(os.path.expanduser(str(root))), ".claude", name)


def apply(root, mode, worktrees_root=None, cache_base=None, tier="scoped", _read=None, _write=None):
    """Read-modify-write the chosen settings file; read-back verify. Fail-closed on
    unparseable existing JSON (never clobber a file we cannot faithfully merge)."""
    path = settings_path(root, mode)
    read = _read or (lambda p: open(p).read() if os.path.exists(p) else None)
    raw = read(path)
    if raw is None or not str(raw).strip():
        existing = {}
    else:
        try:
            existing = json.loads(raw)
        except Exception:
            return {"ok": False, "path": path, "reason": "existing settings unparseable — not clobbering"}
        if not isinstance(existing, dict):
            return {"ok": False, "path": path, "reason": "existing settings not an object — not clobbering"}
    gen = generate_headless if tier == "headless" else generate
    rules = gen(root, worktrees_root, cache_base)
    merged, added = merge(existing, rules)
    if added == 0:
        return {"ok": True, "path": path, "added": 0, "already": True}
    text = json.dumps(merged, indent=2, sort_keys=False) + "\n"
    if _write is not None:
        _write(path, text)
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
    back = read(path)
    try:
        verified = json.loads(back)
    except Exception:
        return {"ok": False, "path": path, "reason": "read-back failed after write"}
    ok = all(r in (verified.get(k) or {}).get("allow", []) for k in SCHEMA_KEYS for r in rules)
    return {"ok": ok, "path": path, "added": added, "already": False,
            **({} if ok else {"reason": "read-back missing rules"})}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["emit", "apply"])
    ap.add_argument("--root", required=True)
    ap.add_argument("--mode", choices=["in-repo", "local"], default="local")
    ap.add_argument("--tier", choices=["scoped", "headless"], default="scoped")
    args = ap.parse_args(argv)
    if args.step == "emit":
        gen = generate_headless if args.tier == "headless" else generate
        print(json.dumps({"ok": True, "rules": gen(args.root)}))
        return 0
    out = apply(args.root, args.mode, tier=args.tier)
    print(json.dumps(out))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
