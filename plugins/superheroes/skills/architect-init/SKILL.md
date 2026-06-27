---
name: architect-init
description: "Internal helper reached from `superheroes:configure` to refresh the-architect's doc-policy layer — where definition-docs live, in-repo committed vs gitignored. Not a front door; owners run `superheroes:configure` to set up, fix, view, or tune calibration."
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# architect-init

Configure the-architect's **doc-policy** — where definition-docs (`spec`,
`plan`, `tasks`) will be written and whether they are committed or gitignored
(CONVENTIONS `§2.3` / `§3.3` / `§4.2`). This is the one-time (idempotent)
setup step that `architect-discovery` and the rest of the band depend on.

## Step 1 — Resolve the storage mode

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys; sys.path.insert(0, '$ROOT_DIR/lib')
import mode_registry, os
result = mode_registry.resolve(os.getcwd())
print(result['mode'])
"
```

If the mode is `global`: report "nothing to configure — global mode keeps
docs in the project store" and exit. The storage mode is decided once by the
band-wide init, not by this skill (CONVENTIONS `§2.3`).

## Step 2 — Check for an existing policy (idempotency gate)

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys, json, os; sys.path.insert(0, '$ROOT_DIR/lib')
import architect_config
p = architect_config.read_policy(os.getcwd())
print(json.dumps(p) if p else 'null')
"
```

**FR-11 idempotency (CONVENTIONS `§2.3`):**

- Policy is absent or `"confirmed": false` (provisional) → proceed to Step 3
  (run the analysis + interview).
- Policy is `"confirmed": true` → report the current policy (location +
  visibility) and exit unchanged. To change it the owner must explicitly request
  a policy reset.

## Step 3 — Analyze the repo and set the policy

Run `architect_config.analyze_repo` to get the recommended location and
visibility (committed vs gitignored) from the repo's existing doc layout:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys, json, os; sys.path.insert(0, '$ROOT_DIR/lib')
import architect_config
print(json.dumps(architect_config.analyze_repo(os.getcwd())))
"
```

**Interactive run** (`INTERACTIVE=true`, a human is present): present the
recommendation (location + visibility) via `AskUserQuestion`. Explain the
trade-offs — committed shares definition-docs with collaborators; gitignored
keeps the repo pristine. Apply the owner's choice with `confirmed: true`:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys, os; sys.path.insert(0, '$ROOT_DIR/lib')
import architect_config
# Replace LOCATION and VISIBILITY with the owner's confirmed answers.
architect_config.write_policy(os.getcwd(),
    {'location': 'LOCATION', 'visibility': 'VISIBILITY', 'confirmed': True})
"
```

**Headless run** (`INTERACTIVE=false`, no human to answer): apply the
analysis-informed default directly with `confirmed: false` (provisional):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys, os; sys.path.insert(0, '$ROOT_DIR/lib')
import architect_config
rec = architect_config.analyze_repo(os.getcwd())
architect_config.write_policy(os.getcwd(),
    {'location': rec['location'], 'visibility': rec['visibility'], 'confirmed': False})
"
```

If `write_policy` returns `None` (config lock contended), surface a notice
and exit without writing — the caller retries (CONVENTIONS `§4.2`).

## Step 4 — Report

Tell the owner what was written (or preserved): location, visibility, confirmed
or provisional. On an interactive run with `visibility: committed`, offer to
commit the policy file (`doc-policy.json` lives in the machine-local project
store — nothing to commit in the repo itself). Remind the owner that
`architect-discovery` picks up the policy from here.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Re-deciding the policy when one is already confirmed | Honor FR-11: report and exit; only proceed on an explicit owner reset. |
| Running Step 3 in `global` mode | `global` mode keeps docs in the project store — no in-repo policy to set. Exit after Step 1. |
| Blocking on a contended config lock | Return `None` is the signal — surface a notice; never spin-wait. |
| Setting `confirmed: true` on a headless run | Headless runs are provisional (`confirmed: false`); the owner confirms interactively. |
