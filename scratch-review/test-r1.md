# Test review — #430 synthesis-fold fix (branch fix/superheroes-430-synthesis-fold)

**Verdict: no blocking findings.** The new/changed tests genuinely pin the live #397
round-5 failure, would fail on `origin/main` (pre-fix), and pass after. Claim/test
alignment is sound and the integration seam (verdict → durable terminal record →
readout) is intact. One low-value Nit below.

## Assessment answers

**Do the tests pin the LIVE failure? Fail-before / pass-after?**
Yes.
- `test_loop_synthesis.py:90 test_unmatched_verdicts_are_reported_loudly` feeds a
  drifted-id drop verdict (`a.py::claim/test mismatch: routed_forward`) that matches no
  finding; asserts the finding is KEPT, `drops==[]`, and `unmatched==["a.py::claim/test
  mismatch: routed_forward"]`. On `origin/main` `consume` returned no `unmatched` key →
  `KeyError` → fails pre-fix; passes post-fix. This is exactly the round-5 mechanism.
- The staging half of the fix (shell hands the judge a precomputed `id ==
  findingIdentity`) is pinned by `showrunner_panel_shell_smoke.js:711`
  (`sawStagedId === stagedId`) plus the drop-folds-clean assertion at :713. Pre-fix
  `synthesizeRound` did not stage `f.id`, so `merged[0].id` is undefined → both
  assertions fail. This smoke IS run in CI (`test_showrunner_node_smokes.py:66`), despite
  the file header's stale "Local gate" note.
- The drifted-id smoke block (`:717-743`) proves fail-closed end to end: the kept blocker
  routes to the fixer (`fixCalls>=1`), the run never terminates clean, and
  `v.unmatched.includes(driftedId)`. Pre-fix `v.unmatched` is undefined → fails.

No test passes with the bug present. `test_staged_id_echoed_verbatim_folds_the_drop`
(`:111`) is the weakest of the set — `consume` matches on `finding_identity(f)` regardless
of the staged `id` field, so the fold itself already worked on `origin/main`; only its new
`unmatched==[]` assertion distinguishes pre/post. It is not a false pass (it asserts the
matched-but-folded verdict is not falsely reported unmatched), just partly redundant with
existing identity-match coverage. The staging contract's real pin is the JS smoke.

**Claim/test alignment.** Every asserted behavior matches its claim. The loud-disclosure,
fail-closed-keep, and matched-but-kept-≠-unmatched semantics are each tested against the
behavior the unit computes, not implementation trivia. `test_loop_readout.py:95` renders
the record and asserts on the visible "matched NO finding" scrutiny section + the ids in
it — user-perceivable output, not internal shape.

**Fixture 13 staged id (hand-computed normalization).** Verified correct.
`finding_identity` = `file::normalize_title(clamp_title(label))`; `normalize_title`
lowercases, strips `[^\w\s]` (ASCII, so `_` is kept), collapses whitespace.
`"claim/test mismatch: routed_forward secret-leak"` →
`"claimtest mismatch routed_forward secretleak"`, id
`"a.py::claimtest mismatch routed_forward secretleak"` — exactly the fixture's staged id
in both the finding and the verdict (`13_staged_id_echo_folds_drop.json`). `clamp_title`
cap is 160 (`review_memory.py:24`), no truncation. Fixture is exercised against both the
Python oracle and the JS twin via the parity harness (`test_parity.py`, auto-discovered).

**Coverage of premortem vectors.**
- *echo-of-unexamined-finding*: mitigated by DROP-WITH-REASON (a reasonless drop is kept),
  pinned by `test_drop_without_reason_is_kept_uncertain` + fixture 04. Not otherwise
  detectable at the `consume` layer (deterministic accounting can't know if the judge
  examined a finding). Adequately handled.
- *id collision*: `test_id_collision_across_findings_no_false_unmatched:125` covers the
  false-unmatched facet. The deeper "one drop verdict silently drops two distinct
  findings" facet is NOT reachable live — `compile_dimension_results` →
  `compile_findings` (`panel_tally.py:202,115`) merges by identity BEFORE `consume`, so
  two identity-colliding findings never reach the fold as separate entries. No gap.
- *mixed legacy/staged rounds*: the identity-match path (fixtures 13, 03) and the
  `f["id"]`-fallback path (fixtures 08, short-id `test_clear_drop_can_match_reviewer_short_id`)
  are each covered; `synthesizeRound` stages `id` uniformly across all findings in a round
  (`review_panel_shell.js:794`), so a single-round mix isn't produced by the native
  pipeline. See Nit below.

**Integration seam (verified, no gap).** `unmatched` survives to the readout:
`writeTerminalRecord` strips only a denylist (findings/carried/fixes/deferred/coverage —
`fenced_json.js:83-88`) and `compose_terminal_record` keeps every non-denylisted verdict
key (`review_memory.py:559`, `_TERMINAL_STRIP` excludes only findings/carriedFindings/
runId/lease). So `unmatched` rides into the durable terminal record and
`loop_readout.render` (unit-tested at `test_loop_readout.py:95`) surfaces it. (`unmatched`
is absent from `VERDICT_SCHEMA` at `review_panel_shell.js:1091` while `downgrades` is
present, but that schema validates rather than strips, so it is non-load-bearing — and a
production-code consistency point, not a test issue.)

**Flakiness / behavior-vs-implementation in the smoke additions.** No flakiness — each
block uses a unique `mkdtempSync` dir, resets `global.synthesisLeaf` at `:745`, and has no
timing/async races. Assertions are on the shell's verdict outputs (`v.terminal`,
`v.unmatched`), observable call counts (`fixCalls`), and the staged-id contract
(`merged[0].id`) — the last is the fix's actual contract, so pinning it is load-bearing,
not implementation-detail coupling.
