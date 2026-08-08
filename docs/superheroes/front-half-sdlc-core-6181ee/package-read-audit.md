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
- **Result: 22 findings** (A1r2–A5r2, B1r2–B5r2, C1r2–C12r2; 12 blocking) — all against
  round-1's revised text (new authorship), none against unchanged text, so no
  declined-extension log this round. Seats engaged: A 104,831 tok / 619s; B 73,446 / 426s;
  C 63,681 / 538s.
- **The one finding that parks to the owner (A1r2 + A2r2 + B1r2, one family):** round 1's
  R6 first-match precedence was register-authored PRODUCT OPINION — FR-5 defines
  overlapping route cases and authorizes no precedence, and the exactly-one
  disambiguation (including the detective pre-ship transition) is an owner FR-5
  amendment. Disposition per FR-33: neither a package fix nor a refutation — an
  owner-stamped spec amendment is required. **R6 is now an OPEN register entry parked to
  the owner (R7's park duty discharged: full note in the advisor's next delivery message
  + durable copy on PR #922); C3 cannot file until ruled. Round 3 is HELD until that
  ruling** — its invocation cause will be the ruling + the round-2 fixes.
- **Fold (advisor, this commit):** R1 cursor → ordered amendment number; R3/FR-31
  consolidated whole into C9 with the disclosed advisor bootstrap; R4 + FR-22 + UFR-4
  consolidated into C6; FR-11 bypass-routing wholly C3; NFR vet row moved to C1; all nine
  anchors carry the as-of cursor (`as-of amendment #3`); five DoDs upgraded to
  recorded-artifact evidence (C7r2/C8r2/C9r2/C10r2 classes); C4 gained FR-14's
  per-dimension probing + stopping rule (C12r2) and C5 the unhappy-path seed areas
  (C11r2). Post-fold mechanical checks: quotes byte-exact 9/9; coverage clean (two
  remaining declared splits: FR-1, FR-11, plus UFR-10's spec-defined split).

## Round 3 (HELD — awaiting the owner's FR-5 precedence ruling)

Cause at invocation: the owner ruling + round-2 fixes (new authorship). Scope: the
round-2-revised parts + R6/C3 once ruled. Ceiling: round 3 of the original 3 — if it
returns more than mechanical items, the package parks under UFR-7.

## Verification pass

_Runs with round 3: each fix checked against its finding plus the mechanical sync battery
(quote exactness, coverage exactly-once — both already passing at this commit)._
