# Package-read audit trail — front-half-sdlc-core-6181ee

FR-32's required record: the weight call, each invocation's cause and ceiling, seats,
lenses per round, parts read with unreviewed-at-entry status, findings declined extension,
and fix verification outcomes.

## Weight call (advisor, 2026-08-08)

**Full.** Measurables: 8 children (9 after the round-1 fold added C9), 8 register entries
(9 after R9). Round ceiling: **3**. No override.

## Voided dispatch (before round 1, recorded as cause of the FR-32 amendment)

The first round-1 dispatch went to two Claude-family subagents — seats sharing the package
author's model family (the advisor authored the package). The owner interrupted and
corrected in-channel: "you should be using codex for these reviews, not claude subagents."
Both agents were torn down; no output from them entered this read. The correction became
the FR-32 seat-composition amendment (spec Amendments log, 2026-08-08) and is memorialized
in the advisor's durable memory.

## Round 1 (2026-08-08, seats independent + cross-family per the amendment)

- **Seats:** three codex `gpt-5.6-sol` @ xhigh dispatches (engine_dispatch dispatch-review,
  read-only; dispatch_guard pass recorded). Seat A: lenses 1–2 (spec contradiction,
  register↔child semantic drift; engaged, 43,892 tok, 411s). Seat B: lens 4 (collisions +
  slice boundaries; engaged, 88,704 tok, 407s). Seat C: lenses 3 + 5 (semantic coverage
  exactness, DoD adequacy; engaged, 60,334 tok, 497s).
- **Parts read:** the whole package (all parts unreviewed at entry — first round) at local
  commit `ed0878e2`, plus the spec.
- **Mechanical pre-checks (advisor, before the round):** register-quote byte-exactness
  8/8 children PASS; coverage token-count exactly-once PASS (after one map-cell reword,
  recorded in the map).
- **Findings: 30** (A1–A10, B1–B4, C1–C16); severities: 17 blocking, 11 important,
  2 minor (seat C's C16 caught the package's own C8 DoD violating the spec's FR-9 bar).
  None refuted; all 30 folded. **Findings declined extension under the unchanged-text
  rule: none** (first round — everything was fresh).
- **Owner decisions inside the round:** (1) FR-32 seat-composition amendment (substantive,
  owner-stamped — cause: the voided dispatch); (2) FR-36 shared-seam amendment
  (substantive, owner-stamped — cause: finding B1's FR-34/FR-36 collision; owner ruled
  option (a) in-channel with the full option spine delivered).
- **Fold (advisor, commit `900974fa`):** register R1/R3/R6/R7/R8 rewritten, R9 added,
  R4 consumers extended; checker extracted to new child C9 (finding B2); map re-allocated
  with four declared splits; every child body repaired per its named findings; all
  register quotes mechanically re-injected. Post-fold mechanical checks: quotes byte-exact
  9/9, coverage clean with declared splits.

## Round 2 (invoked 2026-08-08; cause: round-1 fixes are new authorship + the two
substantive amendments' FR-33 re-entry; ceiling: this is round 2 of the original 3)

- **Seats:** same three codex `gpt-5.6-sol` @ xhigh lens assignments, fresh run-dirs.
- **Scope given:** revised parts are the unreviewed text — verify each fix against its
  named finding, hunt new defects in changed text; unchanged-text findings logged without
  extension per the convergence rule.
- **Result:** _pending — filled when the seats return._

## Verification pass

_Pending — runs after the converging round: each fix checked against its finding plus the
mechanical sync battery (quote exactness, coverage exactly-once)._
