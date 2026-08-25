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
  (analysis + provisional default). Confirmation or change happens only through
  `/superheroes:configure`.
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

Apply the analysis-informed default directly with `confirmed: false` (provisional). Every
non-interactive CLI invocation takes this path — no branch on an unanswered gate:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B -c "
import sys, json, os; sys.path.insert(0, '$ROOT_DIR/lib')
import architect_config
rec = architect_config.analyze_repo(os.getcwd())
disclosure = (
    'Recommended location: %s; visibility: %s; confirmed: false (provisional). '
    '/superheroes:configure confirms or changes it. '
    'Committed shares definition-docs with collaborators; gitignored keeps the repo pristine.'
) % (rec['location'], rec['visibility'])
result = architect_config.write_policy(os.getcwd(), {
    'location': rec['location'],
    'visibility': rec['visibility'],
    'confirmed': False,
    'disclosures': [disclosure],
})
if result is None:
    print('WRITE_POLICY_REFUSED')
else:
    print(json.dumps(result))
"
```

<!-- decision-point: id=architect-doc-policy-default mode=proceed kind=owner-gate default="analysis-informed provisional policy" carrier=doc-policy-disclosures -->
**Disclosure (doc-policy `disclosures` via `write_policy`).** When the shell block above succeeds,
it persists the recommendation applied (location + visibility), that `confirmed: false` means
provisional, and that `/superheroes:configure` confirms or changes it — plus the trade-offs
(committed shares definition-docs with collaborators; gitignored keeps the repo pristine) — in the
`disclosures` field of `doc-policy.json`. The run continues after a successful write.
<!-- /decision-point: id=architect-doc-policy-default -->

**`write_policy` refusal.** The block prints `WRITE_POLICY_REFUSED` when `write_policy` returns
`None`; otherwise it prints the written record as JSON. `read_policy` returns only the four known
fields and cannot distinguish which refusal cause applied — branch on the block's output, not on
`read_policy`. `write_policy` returns `None` for four reasons (see its docstring in
`lib/architect_config.py`):

1. **Config lock contended** — surface a notice and exit; the caller retries (CONVENTIONS `§4.4`).
2. **Project store cannot be ensured** — surface a notice and exit; the caller retries once the
   store is available.
3. **Repository root unavailable** — surface a notice and exit; the caller retries once the repo
   root can be resolved.
4. **Persisted record declares a `schemaVersion` newer than this module supports** — surface a
   notice that the plugin must be upgraded; retrying cannot succeed (a newer plugin wrote that
   record, and this one refuses to overwrite what it cannot read in full).

## Step 4 — Report

Tell the owner what was written (or preserved): location, visibility, confirmed
or provisional, and the disclosure strings in `doc-policy.json`'s `disclosures` field when
`confirmed` is false. Remind the owner that
`architect-discovery` picks up the policy from here and that `/superheroes:configure` confirms
or changes it.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Re-deciding the policy when one is already confirmed | Honor FR-11: report and exit; only proceed on an explicit owner reset. |
| Running Step 3 in `global` mode | `global` mode keeps docs in the project store — no in-repo policy to set. Exit after Step 1. |
| Blocking on a contended config lock | `WRITE_POLICY_REFUSED` is the signal — surface a notice; never spin-wait. |
| Setting `confirmed: true` without owner confirmation via configure | Every init run is provisional (`confirmed: false`); the owner confirms through `/superheroes:configure`. |
