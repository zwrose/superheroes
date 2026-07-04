# review-code round scheduler (`code_loop_plan.py`)

Per-round dispatch is **script-owned** — the deliberate, owner-approved reversal of the old
"coverage uniformity" rule (all five specialists at fixed tiers every round). `lib/code_loop_plan.py`
(the twin of review-spec's `spec_loop_plan.py`, #167) emits `{action, dims_to_run, skipped}`,
delegating **all policy** to the parity-locked `review_round_policy.plan_round` + `loop_state.decide`
twins (the same policy the showrunner spine runs). Obey the emitted schedule verbatim — never add,
drop, or re-tier a dimension by eye. `$ROOT_DIR` is `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`, resolved in Setup.

## Tier → model

`dims_to_run` entries carry a `tier`: `reviewer-deep` → dispatch with `model: $DEEP_MODEL`,
`reviewer` → `model: $REVIEWER_MODEL`. An empty model value means "inherit the session model" —
omit the `model` arg. Tiers are roles, never raw model names.

## plan — the round's schedule

At the start of round N:

    python3 "$ROOT_DIR/lib/code_loop_plan.py" plan --session-dir "$SESSION_DIR" --round <N>

Round 1 is always the full `reviewer-deep` baseline panel (all five, deep). Round N>1 re-emits
exactly the schedule the round-(N-1) `decide` persisted (re-emittable after compaction). Dispatch
**exactly** `dims_to_run` — each at its tier's model — and for each `skipped` dimension copy its
last-run findings file into `round-<N>/` so the compile step sees a complete five-dimension panel:

    cp "$SESSION_DIR/round-<lastRun>/findings-<agent>.json" "$SESSION_DIR/round-<N>/findings-<agent>.json"

A skipped dimension carried a prior high-confidence clean result whose subject the fix did not touch —
it contributes an (empty) findings file, not a fresh dispatch.

## record — the executed evidence

Every round (round 1 included), once the findings files land:

    python3 "$ROOT_DIR/lib/code_loop_plan.py" record --session-dir "$SESSION_DIR" --round <N>

If its `escalate` list is non-empty (a missing/malformed findings file, or a low-confidence
`reviewer`-tier result), re-dispatch **just those dimensions once** at `reviewer-deep`
(`model: $DEEP_MODEL`) and run `record` again — it never asks twice. Confidence is derived from the
findings JSON shape (the spine's legacy-array rule), never a prose claim; a prompt-dropped agent that
wrote no file leaves no fresh evidence, so its stale result can never license a skip.

## decide — the continuation gate + next schedule

After the circuit breaker (loop step 13), regenerate the post-fix diff so the scheduler derives the
changed surface from what **actually changed** (#157/#158) — the FILES whose hunks differ between what
the reviewers saw (`round-<N>/diff.txt`) and the post-fix tree — mapped to policy subjects through the
compiled findings, **never** the fixer's self-report:

    git diff "$BASE_REF"...HEAD > "$SESSION_DIR/round-<N>/head-diff.txt"
    python3 "$ROOT_DIR/lib/code_loop_plan.py" decide --session-dir "$SESSION_DIR" --round <N> \
      --max-rounds 7 --breaker-halt "$BREAKER_HALT" \
      --fix-batch "$SESSION_DIR/round-<N>/fix-batch.json" \
      --resolutions "$SESSION_DIR/round-<N>/resolutions.json"

(Omit `--resolutions` only when no skip occurred at all this round.) The gate wraps `loop_state.py`'s
continuation decision — it derives blocking-fixed from `fix-batch` and skipped-blocking from
`resolutions` (review-code's existing `arch-r2-001` contract, unchanged) — plus the shared round
policy, and fails toward run-all on any corrupt/unknown input. Obey its `action`:

- **`review`** → `round += 1`; dispatch its `dims_to_run` **exactly** (the next round's plan is
  already persisted). MANDATORY — a blocking fix must be re-verified, or a reduced round must be
  followed by the full `reviewer-deep` confirmation round (`roundKind: confirmation`) before any exit.
- **`exit_clean` / `exit_skipped`** → EXIT (see `## End-of-Loop Summary`). The `certification` block
  states how many full confirmation panels ran and whether the last panel's findings were resolved
  with scoped verification — surface it honestly; never imply a pristine fresh pass that did not occur.
- **`halt`** → HALT: surface the reason, the still-open findings, and the commit range.

## Invariants (pinned by `test_code_loop_plan.py`)

- Round 1 = full `reviewer-deep` panel. `exit_clean`/`exit_skipped` are honored only off a round whose
  every dimension ran fresh at `reviewer-deep` with high confidence, or off the #174 economics after a
  qualifying confirmation panel — otherwise a full-deep confirmation round is scheduled first.
- Confirmation-bar economics (#174 PR 1): a confirmation surfacing new findings does not forfeit
  certification once they are fixed + scope-verified; only a **Critical** since the last qualifying
  panel, or **cross-cutting** rework (≥3 of the 5 policy subjects), re-arms one more full panel; at
  most **two** panels per loop; a Critical still owed at the cap **parks** (certification withheld).
- The verify gate (loop step 12) is unchanged — the scheduler decides who reviews, never whether
  verify runs; the certification claim sits on top of a passing verify, never replaces it.
- Fail toward run-all: corrupt scheduler state, unreadable inputs, or an unknown changed surface all
  schedule a full `reviewer-deep` panel rather than risk a premature skip or exit.
