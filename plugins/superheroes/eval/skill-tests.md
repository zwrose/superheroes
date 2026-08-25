# review-crew skill-test state matrix

A documented, re-runnable **state matrix** of orchestrator behavior across the
dimensions the review skills branch on: **profile presence × profile status ×
verify-mode × review-init branches × strict fallback**. For each cell it records
the **trigger**, the **expected behavior**, and the **skill:section that
implements it** — then a **verification pass** confirms the cited prose actually
produces that behavior.

This is the **lightweight skill-testing** the design spec calls for
(the 2026-06-06 code-review-marketplace design, an out-of-repo doc, § "Skill
testing": "cover the verify-mode × provisional × missing-profile state matrix").
It pairs with the finding-quality side of the eval — `eval/score.py` + the
`eval/fixtures/` golden diffs (`eval/README.md`) — which covers agent
recall/precision rather than orchestrator branching.

The frozen v1 matrix (including the retired `review-plan` live-run procedure) is
preserved in `eval/skill-tests-v1-frozen.md`.

## Live-execution gate

The cells below are **verified against skill prose**, not by running the plugin.
Re-read each cited `file:section` after any skill edit and confirm the row still
holds.

## How to re-run this verification (prose level)

For each cell: open the cited file at the named section and confirm the prose
states the expected behavior. The "Verified" column records the result of the last
such pass; the "Fix" column flags cells whose prose had to be amended to match the
intended behavior (see **Prose fixes applied**, end of file).

Shared abbreviations: **R-CODE** = `skills/review-code/SKILL.md`, **R-DEBT** =
`skills/audit-debt/SKILL.md`, **R-INIT** = `skills/review-init/SKILL.md`,
**CONFIGURE** = `skills/configure/SKILL.md`, **BASE** = `rubric/review-base.md`,
**LOOP** = `reference/review-loop.md`, **DOCTOR** = `lib/repo_doctor.py`.

---

## 1. Profile presence

| # | Trigger | Expected behavior | Implements (file:section) | Verified | Fix |
|---|---------|-------------------|----------------------------|----------|-----|
| P1 | A review skill runs and the resolver returns **LOCATION == none** (profile absent at the resolved path) | Setup runs review-init's **create procedure inline** (review-init Steps 1–4: detect → provisional defaults → seed patterns → write the profile), skipping the retired interview. Does NOT invoke another skill mid-run; does NOT run staleness/reconcile/learning-loop. | review-code reference/setup.md § Profile bootstrap; R-DEBT §1 Sweep Prep "Profile bootstrap"; R-INIT §3 "Create: detection + defaults (no interview)" | yes | rewritten for shipped flow |
| P2 | A review skill runs and the profile is **present** | The deterministic **staleness self-check** (`repo_doctor.py`) runs as the first action, captured into `DOCTOR_JSON`; the bootstrap is skipped. The check is guarded on the resolver's **EXISTS == true** so it runs **only** when a profile exists at the resolved location. | review-code reference/setup.md § Staleness self-check; R-DEBT §1 Sweep Prep "Staleness self-check" | yes | already correct |
| P3 | Profile present but the **staleness check itself can't read it** (`readable: false`) | Tell the user the profile is unreadable — re-run `/superheroes:configure` — and **continue** (do not crash, do not block). `repo_doctor.py` fails soft (always exit 0). | review-code reference/setup.md § Staleness self-check; R-DEBT §1; DOCTOR module docstring ("FAIL SOFT … NEVER crash") | yes | citation updated at re-verify |

## 2. Profile status

| # | Trigger | Expected behavior | Implements (file:section) | Verified | Fix |
|---|---------|-------------------|----------------------------|----------|-----|
| S1 | Profile `status: stable` (or `confirmed` on the core/layer path) | Normal operation. Calibration is read from the profile/core fields; no status-driven posture change. | BASE "Where calibration comes from"; review-code reference/setup.md § "Read the verify story from core calibration" | yes | already correct |
| S2 | Profile `status: provisional` | The review **proceeds normally** off the profile's recorded fields. Strictness is **not** keyed off the `status` flag — it follows the profile's **threat-model field**. On the create path, `status: provisional` is always written with a **strict** threat-model provisional default when unknown. | R-INIT §3 (threat model strict provisional default); BASE "Calibration comes from the profile" | yes | rewritten for shipped flow |
| S3 | Profile is **stale** — material drift detected (`rubric-version` advanced, `schema` outdated, ≥ DEP_THRESHOLD added deps, new top-level src dir, or verify-command / default-branch no longer resolves) | The review **runs to completion normally** (drift is informational only at Setup — "Do NOT act on `drift` here"). **After** the review output, a **single non-blocking nudge** line is printed — only when `message` is non-null. | review-code reference/setup.md § Staleness self-check; LOOP "Staleness nudge (end of run)"; R-DEBT §"Learning Loop & Staleness Nudge" → "Staleness nudge (end of run)"; DOCTOR "Material drift is ANY of" | yes | already correct |
| S4 | Stale profile, but the same drift signal was already dismissed (`nudge-ack` contains its `signal_hash`) | The nudge is **suppressed** — printed only when `nudge_acked` is false. Re-fires only once the signal changes (a new `signal_hash`). | LOOP "Staleness nudge (end of run)"; DOCTOR (`nudge_acked = signal_hash in nudge-ack`); R-DEBT §"Staleness nudge (end of run)" | yes | already correct |
| S5 | User dismisses / ignores the staleness nudge | Record the dismissal by writing the doctor's `signal_hash` into the profile's `nudge-ack` map (the only profile write the nudge makes, and only on dismissal). | LOOP "Recording a dismissal (shared)"; R-DEBT §"Recording a dismissal (shared)" | yes | already correct |
| S6 | Profile `status: provisional` during a review run | The end-of-run **provisional-profile confirmation** step is **not run** — the profile stays `provisional`. Confirmation happens only when the owner explicitly confirms via `/superheroes:configure` fix path (FR-18). | R-CODE §"Learning Loop & Staleness Nudge" (via LOOP "Provisional-profile confirmation"); R-DEBT §"Provisional-profile confirmation"; CONFIGURE FR-18; configure/reference/fix.md §4 | yes | reframed for shipped flow |

## 3. Verify-mode (review-code)

| # | Trigger | Expected behavior | Implements (file:section) | Verified | Fix |
|---|---------|-------------------|----------------------------|----------|-----|
| V1 | Profile `## Verify` has `command: <cmd>` | `VERIFY_CMD="<cmd>"`. The orchestrator's **verify gate** AND the **fixer** both run `VERIFY_CMD` from the user's working tree, non-interactively, with a timeout. **Non-zero exit = HALT / `CHECK_FAILED`** — surface failing output, do not re-review on a broken tree. | review-code reference/setup.md § "Read the verify story from core calibration"; R-CODE §"The verify command" (`command:` branch); auto-fix-loop.md fixer prompt step 3 | yes | already correct |
| V2 | Profile `## Verify` has `mode: unverified` | No verify command. The **verify gate is SKIPPED**; the fixer is told the verify command is `"none"` and runs no checks (cannot return `CHECK_FAILED`); commits proceed **ungated**. The dispatch summary AND the End-of-Loop summary both **warn** that fixes were committed without a verify gate. | R-CODE §Dispatch Summary ("Verify: … unverified") + §End-of-Loop Summary + §"The verify command" (`unverified` branch) | yes | already correct |
| V3 | Profile `## Verify` has `mode: review-only`, default invocation (no `--review-only`) | The default auto-fix path **degrades up front** to a **single review pass + the `--review-only` presentation** (no triage, no fixer, no commits, no loop). The degrade is **stated in the dispatch summary**, not buried. | R-CODE §Dispatch Summary ("Verify: … review-only — auto-fix disabled — this run degrades to a single pass + presentation") + §Auto-Fix Loop (gating: "verify story is not `mode: review-only`") + §Read-Only Path (profile `mode: review-only` degrades into this presentation) + §"The verify command" (`review-only` branch) | yes | already correct |
| V4 | `mode: unverified` AND a fixer escalation/verify path | Because there is no command, the fixer's step-3 check is skipped and `CHECK_FAILED` cannot arise from a verify failure on this path. | R-CODE §"The verify command" (`unverified` branch); auto-fix-loop.md fixer prompt step 3 ("verify command is \"none\" … skip this check entirely") | yes | already correct |

Note: `audit-debt` does not have an auto-fix verify gate (audit files issues), so
the verify-mode cells V1–V4 are review-code-specific. `audit-debt` does read
`## Verify` once — as a **doc-drift check** (does the command's binary resolve),
cell D4 below.

## 4. review-init branches

| # | Trigger | Expected behavior | Implements (file:section) | Verified | Fix |
|---|---------|-------------------|----------------------------|----------|-----|
| I1 | `review-init`, no profile (`LOCATION == none`) | **Create** mode: detect (Step 1) → provisional defaults without interview (Step 3) → seed canonical patterns and write (Step 4). Always writes `status: provisional`; `confirmed` is reached only via `/superheroes:configure`. | R-INIT §2 "Choose mode" → §3 "Create: detection + defaults (no interview)" → §4 | yes | rewritten for shipped flow |
| I3 | Create mode, **no `CLAUDE.md`** present | Record a minimal conventions pointer in `## Conventions` (point at `CLAUDE.md` once the owner adds one); do not generate or commit `CLAUDE.md` here. | R-INIT §3 (no `CLAUDE.md` branch) | yes | rewritten for shipped flow |
| I4 | Create mode, **no verify command detected** | Apply provisional default `mode: review-only` when detection + `CLAUDE.md` did not answer. | R-INIT §3 defaults (#2 Verify command) | yes | rewritten for shipped flow |
| I5 | `review-init`, **profile exists** | **Reconcile** mode: re-read CLAUDE.md + re-detect → apply migration steps → diff → preserve hand-edits. **Do not apply by default** — write proposed-changes diff as disclosure; profile written only when owner applies via `/superheroes:configure`. `status` stays `provisional` until configure confirms with a real verify story. | R-INIT §5 Reconcile (steps 6–7) | yes | rewritten for shipped flow |
| I6 | Reconcile, profile's `rubric-version` < engine's | Flag **rubric-version drift** in the proposed-changes diff ("rubric-version M→N: the review rubric has advanced; recalibrating") and update it on write. This is the same signal `repo_doctor.py` surfaces as a staleness nudge; reconcile is where it gets cleared. | R-INIT §5 step 4 ("Detect `rubric-version` drift") + step 7 (refresh rubric-version, clearing drift) | yes | already correct |
| I7 | Reconcile, profile has a `nudge-ack` map | **Preserve `nudge-ack` verbatim** across the reconcile (don't reset acks the user already dismissed); add the field as empty `{}` only if an older profile predates it. | R-INIT §5 step 5 + step 7 ("Preserve the `nudge-ack` map") | yes | already correct |
| I8 | Reconcile, profile `schema` **higher** than the plugin supports | **Read-side guard:** STOP with a loud message ("profile schema N is newer than this review-crew; upgrade the plugin"); do not rewrite it; degrade conservatively (strict posture) rather than misread newer fields. | R-INIT §5 step 2 "Read-side guard" | yes | already correct |
| I9 | Reconcile, unknown `## ` sections/keys present | **Preserve verbatim** (forward-compat); missing fields filled per create defaults only when safe; never silently delete user calibration. | R-INIT §5 step 5 "Migration rules" | yes | already correct |
| I10 | Reconcile, schema migration needed (`N→N+1`) | Apply each ordered migration step between the profile's `schema` and the plugin's. (Schema 1 is current; no migration steps yet — the contract is documented so the first one isn't a cross-file edit.) | R-INIT §5 step 3 | yes | already correct |

## 5. Strict fallback (missing field)

| # | Trigger | Expected behavior | Implements (file:section) | Verified | Fix |
|---|---------|-------------------|----------------------------|----------|-----|
| F1 | A needed field is absent in **both** the profile and `CLAUDE.md` (e.g. no threat model anywhere; a "present but empty" section counts as absent) | **STRICT posture**: assume a multi-user threat model and err toward flagging (safer to over-flag than miss an access-control bug). Minor/Nit never change the verdict regardless of strictness. | BASE "Calibration comes from the profile" + "Where calibration comes from" step 3 (strict fallback) | yes | already correct |
| F2 | The threat-model field specifically is absent everywhere | Strict threat-model fallback (multi-user). review-init **always writes** the threat model on the create path, so absence is rare — but the base rubric guarantees the fallback when it does happen. | BASE "Calibration comes from the profile"; R-INIT §3 (#1 Threat model strict provisional default) | yes | citation updated at re-verify |
| F3 | Reviewer strictness with the **whole profile** absent (the bootstrap is the primary handler, but if a subagent reads before/without one) | Subagent prompts state the precedence "Base rubric (binding) > CLAUDE.md > profile (adder) > **strict fallback when a needed field is absent in all of them**", so a subagent with no profile field still defaults strict. | rubric/orders/dispatch-panel.md "Calibration precedence"; R-DEBT §"Calibration precedence"; BASE strict fallback | yes | citation updated at re-verify |

## 6. audit-debt-specific verify-mode read

| # | Trigger | Expected behavior | Implements (file:section) | Verified | Fix |
|---|---------|-------------------|----------------------------|----------|-----|
| D4 | `audit-debt` reads `## Verify` for the doc-drift dimension | If `command:` is set, confirm its binary resolves on PATH (missing → Minor "verify command does not resolve"). If `mode: unverified` or `mode: review-only`, there is no command — **skip this check**. | R-DEBT §4 "Documentation drift" ("The profile's verify command resolves") | yes | already correct |

---

## Coverage summary

- **Cells:** **25 prose-verified** — Profile presence (3: P1–P3) + Profile status (6:
  S1–S6) + Verify-mode/review-code (4: V1–V4) + review-init branches (9: I1,
  I3–I10) + Strict fallback (3: F1–F3) + audit-debt verify read (1: D4) = 3 + 6 +
  4 + 9 + 3 + 1 = **25**.
- **Verified against prose:** 25 of 25 (each cited section opened and read on
  2026-08-25).
- **Rewritten for shipped flow:** 7 (P1, S2, S6, I1, I3, I4, I5).
- **Citation updated at re-verify:** 3 (P3, F2, F3).
- **Already correct (carried forward):** 15 (P2, S1, S3–S5, V1–V4, I6–I10, F1,
  D4).

Every required dimension from the spec is covered: profile-presence (P1–P3) ×
status (S1–S6) × verify-mode (V1–V4, D4) × review-init-branches (I1, I3–I10) ×
strict-fallback (F1–F3). Each cell cites the implementing `file:section`.

Dropped from this matrix (named in implementer report): **P4** (retired
headless presence branch), **old I1** (retired interactive create with
interview), **old I2** (retired headless create branch — both unified in current
**I1**), **M1** (v1 `review-plan` live-run — see `skill-tests-v1-frozen.md` §7
and `eval/RESULTS.md`).

## Prose fixes applied

**Seven rows rewritten** in this file to match shipped flow (see Coverage
summary). The two review skills (`review-code`, `audit-debt`) are uniform on
the shared mechanisms (profile bootstrap, staleness self-check, end-of-run
nudge/learning-loop, calibration precedence via `reference/review-loop.md`),
and `review-init` covers create (detection + defaults, no interview),
reconcile (diff disclosure, apply only via configure), migration, read-side
guard, and `nudge-ack` preservation.

## Concerns / open behavior questions

**C1 — provisional-profile confirmation (spec line ~195). — CLOSED
(implemented).** The design spec's confirmation need routes to
`/superheroes:configure` on the fix path (FR-18): review skills no longer run an
end-of-run provisional-profile confirmation (cell **S6**). A `status: provisional`
profile **stays provisional** through review runs until the owner explicitly
confirms via configure. `review-init` reconcile does **not** flip provisional →
stable on its own — it discloses a diff and writes only when configure applies
(cell **I5**).
