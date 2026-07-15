## Contents

review-code fail-closed synthesis pass (`loop_synthesis.py`).

- [Where it runs](#where-it-runs)
- [The pass](#the-pass)
- [Fallback — fail toward keeping everything](#fallback--fail-toward-keeping-everything)
- [Surfacing — a dropped or demoted blocker is never silently gone](#surfacing--a-dropped-or-demoted-blocker-is-never-silently-gone)
- [Cross-surface identity methodology + the interactive-doc exception (#430)](#cross-surface-identity-methodology--the-interactive-doc-exception-430)

Ports the showrunner spine's panel **synthesis** stage into standalone review-code's
compile step. review-code's mechanical compile (dedupe/citation/diff-scope) never judged
whether a merged finding actually *holds* — so the standalone path shipped every mechanically
valid finding, false positives included. The spine already runs a judgment pass over its
merged findings with fail-closed guarantees; this is the same pass, wired into the prose path.
The **fail-closed rules live only in `lib/loop_synthesis.py`** — do not judge keep/drop
yourself and do not reimplement them here or in a second script. `$ROOT_DIR` is
`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}` and `$SYNTH_MODEL` / `$RUBRIC` are resolved in Setup.

## Where it runs

Inside `## Compile + Dedupe`, **every round**, after the mechanical filters (steps 1–6) and
**before** the verdict — so the verdict counts only the survivors. The read-only paths reuse
the same compile, so they get it too. The orchestrator dispatches one subagent and reads only
its small JSON file; it never loads the diff or the transcript.

## The pass

1. **Write the merged findings.** Persist the deduped, verified array from steps 1–6 to
   `$SESSION_DIR/round-<N>/merged.json`. Each finding keeps its `id` (the recomputed
   `file::normalized-title` identity is what the consumer matches on; the agent id is a fallback).

2. **Dispatch the synthesis judge** — ONE subagent, `model: $SYNTH_MODEL` (the **synthesis
   tier**, resolved via `--role synthesis`; never the session model). Same judge as the spine's
   panel synthesis (`eval/synthesis-leaf.md`). It reads the merged findings and verifies each
   against the artifact under the **verification root** — `$SESSION_DIR/repo` on `--post`, the
   working tree otherwise — then **writes a bare JSON array** to
   `$SESSION_DIR/round-<N>/synthesis-verdicts.json`. Prompt (embed the absolute paths):

   ```
   You are the synthesis judge for one round of a review panel. You are given the round's
   MERGED findings (duplicates already collapsed) and the code change under review. For EACH
   finding decide whether it holds up against the artifact and the project's severity rubric.

   ## Input
   - Merged findings: <absolute merged.json path> — an array; each has id, file, line, title,
     severity, body/evidence.
   - Verification root (read cited files here ONLY): <absolute verification root>
   - Severity rubric (the only tiers; calibration): <absolute $RUBRIC path>
   - Project conventions: CLAUDE.md and the project profile.

   ## One verdict per finding
   - id: the finding's id, unchanged.
   - action: "keep" or "drop". "drop" ONLY when the finding clearly does NOT hold up (it is
     wrong, not in the changed material, or already handled) and a non-empty reason is given.
     If you are UNCERTAIN it holds, you MUST keep it — never drop on a hunch.
   - reason: one sentence. Required for a drop and for a blocking→non-blocking downgrade.
   - severity: the single rubric tier the finding's EVIDENCE justifies (Critical/Important/
     Minor/Nit) — raise or lower the merged tag as warranted; invent no tiers.

   ## Hard rules
   - Judge only keep/drop + severity, per finding. Do NOT decide the run's outcome, merge or
     re-split findings, or add new findings. Keep-on-uncertain is mandatory — a real blocker
     wrongly dropped is the worst failure.

   ## Output
   Write a JSON array to <absolute synthesis-verdicts.json path>:
   [{ "id", "action", "reason", "severity" }] — exactly one entry per input finding.
   ```

3. **Apply the verdicts deterministically** through the shared script:

   ```bash
   python3 "$ROOT_DIR/lib/loop_synthesis.py" \
     --merged "$SESSION_DIR/round-<N>/merged.json" \
     --leaf   "$SESSION_DIR/round-<N>/synthesis-verdicts.json" \
     > "$SESSION_DIR/round-<N>/synthesized.json"
   ```

   It emits `{"findings":[survivors], "drops":[{id,file,title,reason,was_blocking_tagged}], "downgrades":[{id,file,title,from,to,reason?}]}`
   under the fail-closed contract: **KEEP-ON-UNCERTAIN** (a finding with no verdict, or a
   malformed/ambiguous one, is kept at its pre-synthesis severity — a model's silence never
   drops a finding); **DROP-WITH-REASON** (a finding is dropped only on a clear `drop` carrying
   a non-empty reason, which is recorded); **`was_blocking_tagged`** (a dropped finding any
   reviewer tagged Critical/Important is flagged, so an all-drop or confidently-wrong judge can
   never make a silent clean); and **`downgrades`** (a survivor the judge re-tiered from blocking
   down to non-blocking — a silent downgrade is a silent-drop equivalent, so it is recorded too).

4. **Use the survivors.** `synthesized.findings` become `compiled.findings` — compute the verdict
   on THEM. Carry `synthesized.drops` and `synthesized.downgrades` into `compiled.json`.

## Fallback — fail toward keeping everything

If the judge wrote no usable verdict file (missing, unreadable, threw, or the subagent never
returned), run `loop_synthesis.py` anyway: with a missing or empty `--leaf` it keeps every
finding and drops nothing — i.e. the raw mechanical compile. **A synthesis failure never drops
a finding and never aborts the review.** (This mirrors the spine's rule: synthesis threw /
produced no result → raw compile, no findings dropped.)

## Surfacing — a dropped or demoted blocker is never silently gone

Drops ride into `compiled.json.drops`, blocking→non-blocking downgrades into
`compiled.json.downgrades`; both reach the **End-of-Loop Summary**: list the findings dropped as
unsubstantiated (each with its reason) and — **distinctly, flagged for the owner's scrutiny** —
any `was_blocking_tagged` drop AND any `downgrades` entry (a reviewer had tagged it Critical/
Important; synthesis then dropped it or demoted it below blocking). The loop may filter false
positives or re-tier; it may never silently discard OR quietly demote a blocker.

## Cross-surface identity methodology + the interactive-doc exception (#430)

The verdict fold matches a judge verdict to a merged finding by an **exact string `id`**, not by
asking the model to reproduce the `file::normalized-title` normalization. Every surface that runs
a judge/consumer split must **stage a precomputed id and have the judge echo it verbatim**:

| Surface | Where the id is staged | Fold |
| --- | --- | --- |
| Standalone `review-code` (this doc) | `merged.json` carries each finding's `id`; the judge is told "id unchanged" | `loop_synthesis.py --merged --leaf` |
| Native code panel (`review_panel_shell.js::synthesizeRound`) | `synthesizeRound` stages `id = findingIdentity(f)` on each merged finding before the leaf; the judge echoes it verbatim | `loop_synthesis.consume` |
| Native doc panels (`showrunner.js::docSynthesisLeaf`) | same `synthesizeRound` staging path | `acceptance_rereview.consumeWithAcceptance` → `loop_synthesis.consume` |

A verdict whose id matches no finding is **kept fail-closed AND disclosed loudly** in `unmatched`
(the round record, the readout's "matched NO finding" scrutiny section, and a runtime log) — a
mis-keyed judge is never a silent no-op (the #397 round-5 defect: drifted ids voided 4 real drops
and the run false-parked on no-net-progress).

**Named exceptions (no silent divergence):**
- **Single-reviewer legs** (per-task review, final-review deep leg) run no synthesis fold at all —
  one reviewer, nothing to reconcile (FR-11; stated in `loop_synthesis.py`).
- **Interactive doc reviews** (`review-plan` / `review-tasks` / `review-spec` / `audit-debt`) run
  **no general keep/drop synthesis judge**: the orchestrator dedupes/compiles/verifies findings
  **in-context**, with the owner present, so there is no judge→consumer split whose verdict-fold
  could silently no-op. The one deterministic fold they do run — acceptance suppression
  (`acceptance_rereview.py --acceptance-only`, #397 FR-14, deliberately drop/downgrade-stripped) —
  already keys on an identity **copied verbatim** from `acceptance-candidates.json`, i.e. the same
  staged-id/echo discipline, not a model-recomputed normalization. So the interactive surface is a
  **documented exception**, not a silent divergence.
