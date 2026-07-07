# configure — permission posture (view & edit)

The permission sub-init, reached from `configure`'s view & tune path. It views and edits the
project's **auto-allow rules** — the owner-curated routine families that let an owner-absent
showrunner run finish without babysitting, sitting strictly *below* the owner-role floor
(merge / release / workflow-run / force-push / push-to-default is never widened).

`ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` is assigned once per bash block below.

## What the rules are

An allow rule turns a would-be permission prompt into an `allow` when a routine command matches
an owner-curated family (FR-6). The rules live in the out-of-repo, config-keyed store
(`projects/<config_key>/permission/rules.json`) — no repo artifact — and are frozen per run, so a
mid-run edit never affects a run already in flight (UFR-9). The floor is never widened: even a rule
that would match a merge is refused at evaluate time (the enforcer re-checks the gated set).

## View (read-only)

The full provenance-valid allow set is already shown on the combined view's **Permission posture**
section (the `configure_view.render` screen). Reading it changes nothing.

## Seed the routine families — the batteries-included first path (FR-6, FR-7)

When the posture is **empty** (the view's Permission posture reads "no auto-allow rules") — or the
owner asks to set the posture up — OFFER seeding the four routine families a full showrunner run
exercises, rather than making the owner add them one at a time below. Owner-gated like every write:
**show the family list first, seed only on the owner's explicit confirm.** The families:

- **test-run** — the repo's test invocations (`pytest`, `python3 -m pytest`, the node smoke runner).
- **validators** — the repo's three CI validators (`validate_marketplace` / `validate_hosts` / `validate_skills`).
- **worktree-vcs** — version control confined to managed build worktrees (staging/read-only verbs plus a
  non-force `superheroes/*` feature-branch push; `main`/force still fall to the floor).
- **draft-pr** — draft-PR create + title/body/label edits + the draft→ready promotion (`--base` excluded).

On the owner's explicit confirm, seed them (idempotent per family — a re-seed refreshes, never duplicates):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys; sys.path.insert(0, '$ROOT_DIR/lib'); import permission_rules
permission_rules.seed_default_rules('.')
"
```

Seeding also writes the **FR-7 audit record** (`audit.json`, alongside `rules.json`) — the observed
prompt-provoking commands and each one's disposition, the grounding for every seeded family (including
the owner-role commands recorded as "keep prompting"). Each family stays **individually removable**
afterward via `remove_rule` (below). View the audit record any time:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys, json; sys.path.insert(0, '$ROOT_DIR/lib'); import permission_rules
print(json.dumps(permission_rules.audit('.'), indent=2))
"
```

## Edit — the only sanctioned change path (FR-9, UFR-9)

Every add/remove goes through `permission_rules`, which stamps the provenance
(`{"source": "configure", "at": <utc>}`) that makes a rule visible to the enforcer. A direct
hand-edit that omits the stamp is ignored at evaluate time — fail-safe *toward prompting* — so
`configure` is the one place a rule ever takes effect.

Add or replace a routine family (replace is by `family` name):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys, json; sys.path.insert(0, '$ROOT_DIR/lib'); import permission_rules
permission_rules.set_rule('.', {'family': 'test-run', 'pattern': r'\bpytest\b'})
"
```

Remove a family:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys; sys.path.insert(0, '$ROOT_DIR/lib'); import permission_rules
permission_rules.remove_rule('.', 'test-run')
"
```

Keep each pattern **narrow** — a routine-command shape, never a catch-all. Any doubt reads as
"keep prompting": leave the command off the allow set and let the normal prompt path handle it.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Hand-editing `rules.json` directly | It is ignored (no provenance stamp) — always go through `set_rule` / `remove_rule`. |
| Writing a broad pattern to cover many commands | Keep each family narrow; a would-be floor match is refused anyway, but broad rules over-allow routine commands. |
| Adding a rule for an owner-role action (merge/release/force-push) | The floor owns those — a rule there never allows; do not try to widen it. |
