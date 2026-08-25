---
name: architect-init
description: "Internal helper reached from `superheroes:configure` to refresh the-architect's doc-policy layer — where definition-docs live, in-repo committed vs gitignored. Not a front door; owners run `superheroes:configure` instead."
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# architect-init

Configure the-architect's **doc-policy** — where the `spec` definition-doc
will be written and whether it is committed or gitignored
(CONVENTIONS `§2.3` / `§3.3`). This is the one-time (idempotent)
setup step that `architect-discovery` and the rest of the band depend on.

## Step 1 — Resolve the storage mode

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B -c "
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
python3 -B -c "
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
python3 -B -c "
import sys, json, os; sys.path.insert(0, '$ROOT_DIR/lib')
import architect_config
print(json.dumps(architect_config.analyze_repo(os.getcwd())))
"
```

Apply the analysis-informed default directly with `confirmed: false` (provisional). Every run takes
this path — no branch on human presence:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B -c "
import sys, os; sys.path.insert(0, '$ROOT_DIR/lib')
import architect_config
rec = architect_config.analyze_repo(os.getcwd())
architect_config.write_policy(os.getcwd(),
    {'location': rec['location'], 'visibility': rec['visibility'], 'confirmed': False})
"
```

**Disclosure (write into the run output and Step 4 report):** state the recommendation applied
(location + visibility), that `confirmed: false` means provisional, and that `/superheroes:configure`
confirms or changes it. Include the trade-offs — committed shares definition-docs with collaborators;
gitignored keeps the repo pristine — so the owner reading the artifact learns what they would have
been told interactively.

If `write_policy` returns `None` (config lock contended), surface a notice
and exit without writing — the caller retries (CONVENTIONS `§4.4`).

## Step 4 — Report

Tell the owner what was written (or preserved): location, visibility, confirmed
or provisional, and the disclosure above when `confirmed` is false. Remind the owner that
`architect-discovery` picks up the policy from here and that `/superheroes:configure` confirms
or changes it.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Re-deciding the policy when one is already confirmed | Honor FR-11: report and exit; only proceed on an explicit owner reset. |
| Running Step 3 in `global` mode | `global` mode keeps docs in the project store — no in-repo policy to set. Exit after Step 1. |
| Blocking on a contended config lock | Return `None` is the signal — surface a notice; never spin-wait. |
| Setting `confirmed: true` without owner confirmation via configure | Every init run is provisional (`confirmed: false`); the owner confirms through `/superheroes:configure`. |
