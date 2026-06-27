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

## 5 — Secrets stay out of shared calibration (NFR)

Any hero credential (such as test-pilot's sign-in) records **only non-secret references — the names
of environment variables, never their values** — into committed or collaborator-visible
calibration. This is test-pilot's existing rule; preserve it.

## Recovering an interrupted set-up (UFR-7)

If `route` reported "incomplete set-up" — the storage mode was recorded but not every light layer
was written (a prior run was interrupted) — do **not** present the project as healthy. Offer to
finish the remaining layers, then re-render the view.
