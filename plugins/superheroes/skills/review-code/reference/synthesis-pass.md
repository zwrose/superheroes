## Contents

Fail-closed synthesis fold (`loop_synthesis.py`) for the doc-loop acceptance path.

- [Where it runs](#where-it-runs)
- [The pass](#the-pass)
- [Fallback — fail toward keeping everything](#fallback--fail-toward-keeping-everything)
- [Surfacing — a dropped or demoted blocker is never silently gone](#surfacing--a-dropped-or-demoted-blocker-is-never-silently-gone)
- [Repeats](#repeats)
- [Cross-surface identity methodology + the interactive-doc exception (#430)](#cross-surface-identity-methodology--the-interactive-doc-exception-430)

`loop_synthesis.py` is the fail-closed judgment fold that turns a synthesis judge's per-finding
keep/drop verdicts into a deterministic survivor set. It survives for **one** consumer: the
**doc-loop acceptance path** (`acceptance_rereview.py --acceptance-only`, drop/downgrade-stripped).
`round_driver.py` does **not** call `loop_synthesis` — it runs the #506 verification path across
TWO folds: `_fold_verifiers` stages ids and applies verdicts (`verification.stage_ids` +
`verification.apply_verdicts`), then `_fold_synthesis` groups same-root-cause survivors
(`verification.merge_and_rank`) plus the author-justification post-filter. Any future eval surface
that calls `loop_synthesis.consume` directly documents itself as such; it is never a `round_driver`
callee. The [Repeats](#repeats) section governs the code loop's synthesis step (`_fold_synthesis`).

**Neither standalone `review-code` nor the native code panel runs this fold.** As of #506 the
code auto-fix loop's keep/drop realness check — standalone `review-code` **and** the native
eval/convergence panel driven by `round_driver.run_loop` — moved to **per-finding verification**;
that path's contract is `verification-pass.md`,
and this document does not govern it. Do not wire `loop_synthesis` into the round-driver path.

The **fail-closed rules live only in `lib/loop_synthesis.py`** — do not judge keep/drop
yourself and do not reimplement them here or in a second script. `$ROOT_DIR` is
`${CLAUDE_PLUGIN_ROOT}` and `$SYNTH_MODEL` / `$RUBRIC` are resolved in Setup.

## Where it runs

One surviving surface runs this fold over its **merged** findings, after the mechanical
filters and **before** the verdict — so the verdict counts only the survivors:

- the **doc-loop acceptance path** — the deterministic acceptance-suppression fold
  (`acceptance_rereview.py --acceptance-only`, drop/downgrade-stripped).

The native code auto-fix loop — standalone `review-code` **and** the native eval/convergence panel
driven by `round_driver.run_loop` — uses per-finding verification instead (`verification-pass.md`:
`round_driver.py::_fold_verifiers` runs `verification.stage_ids` + `verification.apply_verdicts`,
then `_fold_synthesis` runs `verification.merge_and_rank`), and the interactive doc reviews run no
general keep/drop judge at all — see the Cross-surface section below.

## The pass

The steps below are the reference shape of the fold (the doc-loop acceptance path runs this same
`loop_synthesis` contract through `acceptance_rereview.py --acceptance-only`):

1. **Write the merged findings.** Persist the round's deduped, verified array to the panel's
   round working dir (e.g. `merged.json`). Each finding keeps its `id` (the recomputed
   `file::normalized-title` identity is what the consumer matches on; the agent id is a fallback).

2. **Dispatch the synthesis judge** — ONE subagent, `model: $SYNTH_MODEL` (the **synthesis
   tier**, resolved via `--role synthesis`; never the session model). Same judge as the spine's
   panel synthesis (`eval/synthesis-leaf.md`). It reads the merged findings and verifies each
   against the artifact under the **verification root** — the
   working tree — then **writes a bare JSON array** to
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
   python3 -B "$ROOT_DIR/lib/loop_synthesis.py" \
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

## Repeats

On the code review loop, synthesis groups findings that share a root cause, and each group gets
one fix. A group, or a finding the verifier refuted this round, may also be marked a repeat of one
of the PR's earlier findings. The earlier findings are the ones this session decided in earlier
rounds and the ones in the PR's latest earlier review record (the build session supplies the
record with `--earlier-findings`; see
[round-driver.md § next / submit protocol](round-driver.md#next--submit-protocol)). Exact identity
always marks: a finding whose identity key matches an earlier finding's key is a repeat of that
finding, whatever the seat said. The mark names the earlier finding in the record (`repeatOf`).

A repeat is kept or treated as a new finding. A kept repeat takes the earlier finding's outcome,
whatever this round's verdict was. The rules, in order:

1. **A repeat of a fixed finding.** The verifier's grade of the repeat on the current code decides
   whether the fix still holds. Graded `wrong`: the fix holds, and the repeat keeps `fixed`.
   Any other grade, or none: it is a new finding.
2. **A repeat of a finding closed as wrong.** When the code has changed since it was judged, the
   verifier's fresh grade rules: `wrong` keeps the earlier outcome, anything else makes it a new
   finding. When nothing has changed, it keeps the earlier outcome and the grade is not read.
3. **Any other repeat** (`craft`, `left-for-owner`, `ruling`; a ledger `out-of-scope` row counts
   as `ruling`) keeps its earlier outcome.
4. **A repeat of a finding still open** (not yet decided) is a new finding.

| Earlier outcome | Condition | Result | `fixHolds` |
| --- | --- | --- | --- |
| `fixed` | new grade `wrong` (the fix holds) | kept, outcome `fixed` | `true` |
| `fixed` | any other grade, or none | new finding | `false` |
| `shown-wrong` | code changed (or unknown) and new grade `wrong` | kept, outcome `shown-wrong` | `null` |
| `shown-wrong` | code changed (or unknown) and any other grade, or none | new finding | `null` |
| `shown-wrong` | code unchanged (the new grade is not read) | kept, outcome `shown-wrong` | `null` |
| `craft`, `left-for-owner`, `ruling` | any | kept, that outcome | `null` |
| none (the earlier finding is open) | any | new finding | `null` |

The grade is the new finding's own verifier grade from this round: `confirmed`, `plausible`,
`wrong`, or none. The code has changed when the git tree at the head the earlier finding was
judged on differs from the tree at the head this round's verifier judged on; a head that cannot be
read, or a comparison that cannot run, counts as changed. The earlier head is the review record's
`finalCommit.sha` for a record finding, and the head the verifier orders of the round it was
decided in cite for a session finding.

A repeat that is not kept is a new finding. A survivor routes as usual, to the fix batch when it
blocks. A finding the verifier refuted this round stays refuted with its own `wrong` grade, never
goes to the fix, and gains only its `repeatOf` mark.

A kept repeat never goes to the fix, never becomes an owner card, and is never dropped from the
record. Its record entry shows the earlier outcome with a "repeat of …" reason. A kept
`left-for-owner` repeat adds no second owner card: the earlier finding holds it. A refuted repeat
of a fixed finding whose fix holds ends `fixed` and keeps its `wrong` grade.

This section is the rule's one prose home; the module `repeat_marks` is its code home. Other docs
link here.

## Cross-surface identity methodology + the interactive-doc exception (#430)

As of #506, the code auto-fix loop's keep/drop realness check — standalone `review-code` and the
native eval/convergence panel (`round_driver.run_loop`) alike — moved to **per-finding
verification** (`verification.apply_verdicts`; contract in `verification-pass.md`); this
document's `loop_synthesis` fold remains only for the doc-loop acceptance-only path.

The verdict fold matches a judge verdict to a merged finding by an **exact string `id`**, not by
asking the model to reproduce the `file::normalized-title` normalization. Every surface that runs
a judge/consumer split must **stage a precomputed id and have the judge echo it verbatim**:

| Surface | Where the id is staged | Fold |
| --- | --- | --- |
| Standalone `review-code` | `stage_ids` assigns `v0..vN`; verifier echoes staged ids; synthesis groups survivors | `verification.apply_verdicts` + `verification.merge_and_rank` (contract: `verification-pass.md`); `loop_synthesis` remains only for the doc acceptance path |
| Native code panel (`round_driver.run_loop`) | `round_driver.py::_fold_verifiers` stages ids (`verification.stage_ids`) | `verification.apply_verdicts` (in `_fold_verifiers`) + `verification.merge_and_rank` (in `_fold_synthesis`) — NOT `loop_synthesis` |
| Doc-loop acceptance | id copied verbatim from `acceptance-candidates.json` | `lib/loop_synthesis.py::consume` via `acceptance_rereview.py --acceptance-only` |

A verdict whose id matches no finding is **kept fail-closed AND disclosed loudly** in `unmatched`
(the round record, the readout's "matched NO finding" scrutiny section, and a runtime log) — a
mis-keyed judge is never a silent no-op (the #397 round-5 defect: drifted ids voided 4 real drops
and the run false-parked on no-net-progress).

**Named exceptions (no silent divergence):**
- **Single-reviewer legs** (per-task review, final-review deep leg) run no synthesis fold at all —
  one reviewer, nothing to reconcile (stated in `loop_synthesis.py`).
