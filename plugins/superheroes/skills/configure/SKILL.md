---
name: configure
description: "Use to set up, fix, view, or tune a project's superheroes calibration — the single front door for superheroes configuration. It senses what a project needs and either sets it up, repairs it, or lets you see the whole project's calibration on one screen and change a setting. Also use to move a project between in-repo and out-of-repo storage. Not for code review, technical planning, or running the build loop."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# configure

The single owner-facing front door for a project's **superheroes calibration**. Run it and it
**senses the project's state** and routes into one of three paths — **set up** (nothing
configured yet), **fix** (configured but needing repair), or **see & tune** (configured and
healthy). It is the one calibration command an owner is told to run; the per-hero `*-init`
skills are now reached only from within it (CONVENTIONS `§2.4` / `§3.3`).

This skill is a thin **conductor** over tested libs — it never moves a file or computes a key
itself. The destructive in-repo↔global storage-mode **flip** and first-push **rebind** (and
their crash recovery) live entirely in `lib/mode_migrate.py`.

## Step 1 — Recover first (every run)

Before sensing or rendering anything, settle any flip or rebind interrupted by an earlier crash —
this is what makes the storage switch safe (UFR-1/UFR-10). `route`/`render` are read-only and can
never be the recovery trigger.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/mode_migrate.py" recover --cwd .
```

A `recovered` result means an interrupted switch was finished or backed out — note it for the
owner. While a migration is recovering, the passive drift nudge stays quiet (it is recovery in
progress, not drift).

## Step 2 — Sense the state and route

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys, json; sys.path.insert(0, '$ROOT_DIR/lib')
import configure_route
print(json.dumps(configure_route.route('.', interactive=True)))
"
```

Read the `path` and surface the plain-language `reasons`. `INTERACTIVE` is `false` on a headless
run (no human to answer) — pass it through so the libs take the provisional / out-of-repo / strict
posture and never switch storage unattended (FR-14/FR-17). Then run the matching path:

- **`set-up`** → follow `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/configure/reference/set-up.md`.
- **`fix`** → follow `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/configure/reference/fix.md`.
- **`view`** → follow `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/configure/reference/view-and-tune.md`.

A run that only views an up-to-date project changes nothing (FR-12). Viewing never confirms a
provisional calibration (FR-18) — that only happens when the owner explicitly confirms it on the
fix path.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Skipping the Step-1 recover | A crashed switch is invisible until recover runs first — run it every time. |
| Re-deciding a recorded storage mode during set-up/fix | The mode is sticky (FR-11); only the explicit, confirmed switch on the tune menu changes it. |
| Switching storage unattended | A headless run never switches (FR-14); it records the owner-choice fix un-applied and continues. |
| Editing the owner's build config to add a verify command | Propose it for the owner to add — `configure` never edits their build config (UFR-5). |
