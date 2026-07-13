## Contents

- §1 — Decide the storage mode (FR-2), with disclosure
- §2 — Seed the core + the light hero layers (FR-16)
- §3 — Verify command first (UFR-5)
- §4 — Offer the heavier heroes (FR-3), decline still completes
- §4.5 — Offer an external engine per role (FR-11/12/13/14), decline still completes
- §4.6 — Offer the review-discipline CLAUDE.md section (in-repo only), decline still completes
- §5 — Secrets stay out of shared calibration (NFR)
- Recovering an interrupted set-up (UFR-7)

# configure — set-up path

Reached from `configure` when a project has nothing configured yet (FR-1). Sets the project up
end to end: storage mode, the shared core, the light hero layers, and an offer of the heavier
heroes. Conducted as plain one-question-at-a-time prompts with recommended defaults.

`ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` is assigned once per bash block below.

## 1 — Decide the storage mode (FR-2), with disclosure

A project keeps its calibration either **repo-shared** (committed with the repo, **visible to
collaborators**) or **out-of-repo** (kept on the local machine, the repo stays pristine). Present
both with that consequence **before** the owner picks — repo-shared publishes the calibration to
anyone with the repo. Resolve the band-wide decision (it is decided once and is sticky, FR-11):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys; sys.path.insert(0,'$ROOT_DIR/lib'); import mode_registry
print(mode_registry.decide_mode('.', None, True))"   # 'in-repo' | 'global' | 'ask'
```

`ask` → present the choice and record the owner's pick; an already-decided mode is reported, not
re-asked. A **headless** run (no human) takes `global` (out-of-repo) provisionally and never asks
(FR-14).

## 2 — Seed the core + the light hero layers (FR-16)

Once the mode is set, seed the shared **core** (the project's stack, verify command, threat model)
and the two light layers — the-architect's doc-policy and review-crew's threat model — in the same
pass. Drive each hero's calibration logic through its now-internal `*-init` skill (reached from
here, not advertised separately). Detect facts from the repo first; ask only what detection leaves
open. Write the core confirmed when the owner answered, provisional on a headless run.

## 3 — Verify command first (UFR-5)

If no verify command is detectable, **lead with helping the owner set one up**: propose a concrete
command for them to add to their build config — **never edit their build config yourself**. Only if
they decline, offer the fallbacks of marking the project *unverified* or *review-only*, and record
their choice. Never guess a command.

## 4 — Offer the heavier heroes (FR-3), decline still completes

Where a heavier or optional hero applies (test-pilot, or any hero needing extra tooling such as a
connected browser), **offer** to set it up now or leave it for later. If the owner declines, set-up
still **completes** and the project is usable without it. If they opt into test-pilot but no browser
tool is connected, guide them to connect one (or set it aside) rather than fail (UFR-4).

When the owner **explicitly declines** an optional hero (not merely "later"), record it so the
view tune-menu does not re-offer it on every run (FR-6 / #121):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/hero_setup.py" decline --cwd . --hero test-pilot
```

## 4.5 — Offer an external engine per role (FR-11/12/13/14), decline still completes

After the verify command (§3) is set — external implementers are verify-gated, so this must follow it —
offer to bring **Codex** and/or **Cursor** into the loop, per role (reviewer engine, implementation
engine), each independent, default **Claude**. A decline leaves both roles on Claude and set-up still
completes.

1. **Availability (FR-11).** Probe both engines and show a readiness matrix — installed + signed in, or
   what to fix:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   python3 "$ROOT_DIR/lib/engine_detect.py"   # JSON verdict per engine: installed/authed + remediation
   ```
   A not-ready engine is shown with its next-command remediation; it is never offered as ready.

2. **Per-role preference (FR-12).** Ask, one at a time, which engine to use for the reviewer role and
   for the implementation role (only ready engines are selectable). Record the pick into `core.md`'s
   machine block `enginePreferences: {reviewer, implementation}` via `core_md` (schemaVersion 2). An
   absent block reads as both `claude`. (A third key, `planAuthor`, routes the showrunner's
   plan-author leaf; it is a tune-level knob — offer it only when the owner asks, per
   `reference/view-and-tune.md`.)
   When Codex is selected and no concrete model pin exists, explain the effective GPT-5.6 defaults.
   Codex tier map: haiku=gpt-5.6-luna, sonnet=gpt-5.6-terra, opus=gpt-5.6-sol,
   fable=gpt-5.6-sol.
   `gpt-5.5` remains available later as a per-role tune-level compatibility pin; `gpt-5.5` +
   `max` is rejected, and `max` is opt-in on GPT-5.6 only.

3. **Show the build authorization — never apply it (FR-13).** If an external **implementation** engine
   is chosen, an external autonomous write needs a one-time owner grant. Show the exact snippet and where
   it goes; do **not** write it:

   ```bash
   python3 "$ROOT_DIR/lib/engine_authz.py" snippet --host claude --engine <codex|cursor>
   # prints the autoMode.allow block + its location (.claude/settings.local.json). SHOW it; never write it.
   ```

4. **Test dispatch (FR-14), bounded by the stall limit (UFR-5).** After the owner grants the
   authorization, run one throwaway external write and report success / failure / no-response — the
   no-response case is bounded by the same finite limit as UFR-5 (`engine_pref.resolve_timeout`):

   ```bash
   python3 "$ROOT_DIR/lib/engine_authz.py" test-dispatch --engine <codex|cursor> --cwd .
   # -> {"engine":E,"ok":true}  (ready)
   # -> {"engine":E,"ok":false} (denied or no-response bounded by the UFR-5 limit -> falls open to
   #    Claude; tell the owner how to enable, leave the engine not-ready with a retry instruction)
   ```
   For Codex, this probes the GPT-5.6 Sol capability explicitly as well as the host write grant, so
   an authenticated CLI that is too old for GPT-5.6 remains not-ready.
   A failed or timed-out test dispatch leaves the engine **not-ready** — builds and mechanical fixes fall
   open to Claude until it works. Never present a not-working engine as ready.

**Headless (`INTERACTIVE=false`).** Take the strict/provisional posture: probe and record what is
detectable, but never block and never apply the authorization — leave any external implementation engine
not-ready until an interactive run can grant + test it.

## 4.6 — Offer the review-discipline CLAUDE.md section (in-repo mode only), decline still completes

When the storage mode decided in §1 is **in-repo**, offer to append the band's review-discipline
section to the project's `CLAUDE.md` (source of truth:
`$ROOT_DIR/rubric/review-discipline.md`) — a durable copy visible to
human collaborators and non-superheroes tooling. Owner-gated; show the text before writing;
idempotent (an existing `Review discipline` heading means report-and-skip). **Never offer this in
out-of-repo mode** — that mode exists to keep the repo free of superheroes traces; there the
SessionStart bootstrap note is the sole carrier. A decline still completes set-up; it is not
persisted (this is not a hero), so the offer simply remains available on the view-and-tune menu
rather than being re-pushed. Headless: never write; note the offer as un-made.

## 5 — Secrets stay out of shared calibration (NFR)

Any hero credential (such as test-pilot's sign-in) records **only non-secret references — the names
of environment variables, never their values** — into committed or collaborator-visible
calibration. This is test-pilot's existing rule; preserve it.

## Recovering an interrupted set-up (UFR-7)

If `route` reported "incomplete set-up" — the storage mode was recorded but not every light layer
was written (a prior run was interrupted) — do **not** present the project as healthy. Offer to
finish the remaining layers, then re-render the view.
