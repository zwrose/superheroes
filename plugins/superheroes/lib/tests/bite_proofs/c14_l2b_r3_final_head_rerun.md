# C14 layer 2b (r3) — every bite-proof re-run on the post-auto-fix final head `f5e6aabb`

**Who ran this:** the adopting orchestrator (workhorse), not an implementer. Verification authority
does not delegate: every red and green below was produced by the orchestrator applying the
neutralization itself through the host's edit action and reverting it with the inverse edit — never
a git discard, never an ad-hoc shell edit.

**Where:** a dedicated detached probe worktree at `f5e6aabb` under session scratch
(`…/scratchpad/wt-probe`), never the build worktree and never a tree a live seat was reading. The
build worktree was clean and fully pushed before the first probe.

**Why this record exists.** The r2 record
([`c14_l2b_r2_final_head_rerun.md`](c14_l2b_r2_final_head_rerun.md)) proved twenty-seven guarded
elements at `af2ad185`/`e431ab89`. Three review-loop auto-fix commits then landed on top —
`364954c2`, `9f0d9400`, `f5e6aabb` — moving **315 lines of `engine_dispatch.py`**, adding
`background_outcome.py` and its census test, and adding one new guarded element. Detector-narrowing
staleness is exactly what that re-opens: a detector proved before a refactor can stop biting after
it. This record closes that gap by re-running **every** element on the post-fix head, one head, no
production delta between reds.

**Captures.** Full pytest output for each run went to session scratch outside the repository
(`…/scratchpad/caps/`). The decisive assertion lines are quoted verbatim below; the elided remainder
is the standard pytest header, fixture repr and traceback frames. **Nothing redacted** — no capture
carried a secret, token, private URL or PII; platform tmpdir paths appear in the originals and are
elided rather than redacted.

**Restore receipts.** After every restore, `git status --porcelain` over the probe worktree returned
**empty**. Where a line below says "clean", that is that receipt. The final receipt after the last
element: `git status --porcelain` empty at `f5e6aabb`.

---

## What the re-run found

**Twenty-six of twenty-eight guarded elements went red under neutralization and green after
restore.** Nothing needed a repair, and no repair touched product code. The two that are not red-run
are the two the r2 record already retired by design, plus one gate whose unreachability is itself the
recorded finding:

1. **Element 6 (transcript admission gate)** — retired in r2, replaced by the committed detector
   proved as elements 24–26. Not re-run in its recorded form; its replacement is.
2. **Element 16 (`_spawn_attempt` background guard)** — the guard was deleted by design when this
   layer made background mode real. There is no detector left to neutralize.
3. **Element 22's write-path `run-dir-claude-mode-mismatch` gate** stays **unreachable by
   construction** at this head, exactly as WO-R1 recorded: planting `False and` into its condition
   leaves the write suite green. Its coverage is element 27's literal census. This re-run adds a
   receipt the r2 record did not have: with the background-write refusal neutralized, the
   **precedence test goes red showing `run-dir-claude-mode-mismatch`** — proof the gate itself is
   correct, and that only the earlier refusal makes it unreachable.

**Three axes are restated at this head** (drift from the r2 record, all benign, none a repair):

- **Element 2** now reds as `assert None == 'background-launch-failed'` rather than r2's
  `IndexError`. The auto-fix hardened the test's `_bg_attempt_ended` helper, so the absence the
  detector catches now surfaces as a clean assertion instead of an index error. Strictly better.
- **Element 10**'s cursor-bound line exists at **two** sites at this head (the poll loop and the
  session-ended re-read). Both are neutralized together — the element is the cursor bound, and one
  site left intact would prove nothing about the other.
- **Elements 24–26**'s gate was refactored by the auto-fix: `_stdout_delivery_gate`'s stdout and
  transcript branches now share one materialization comparison. The three neutralizations are
  re-aimed at that shared comparison; the detector and its three legs are unchanged.

**One element is new since r2 and had no neutralization recorded** — see element 28.

---

## Elements 1–5, 5a, 7 — `c14_l2_background_flow.md`

### 1. `background-launch-unacknowledged`

- **axis:** an unparseable launch acknowledgement refuses with `background-launch-unacknowledged`
- **detector:** `test_engine_dispatch.py::test_claude_background_launch_refusals` (the three
  unacknowledged params)
- **neutralization** (`engine_dispatch.py`, `_run_engine_files_background`):
  `launch_id = launch_id or "bite-proof-plant"` inserted immediately after
  `launch_id = engine_adapter.claude_launch_id(ack_stdout)`
- **raw red:**
  ```
  >       assert ended["refusal"] == refusal
  E       AssertionError: assert 'background-session-unlisted' == 'background-l...nacknowledged'
  E         - background-launch-unacknowledged
  E         + background-session-unlisted
  ```
  All three unacknowledged params red; the fourth (launch-failed) stayed green — the axis holding.
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `4 passed, 757 deselected in 2.46s`

### 2. `background-launch-failed`

- **axis:** a non-zero launch child exit refuses with `background-launch-failed`
- **detector:** the `backgrounded · … / exit 1` param of the same test
- **neutralization:** `exit_code = 0` inserted immediately before `if exit_code not in (0, None):`
- **raw red:**
  ```
  >       assert ended["refusal"] == refusal
  E       AssertionError: assert None == 'background-launch-failed'
  FAILED ...::test_claude_background_launch_refusals[backgrounded \xb7 a1b2c3d4\n-1-background-launch-failed]
  1 failed, 3 passed, 757 deselected in 1.78s
  ```
  On axis — with the non-zero exit neutralized no launch-failed record is written at all. **Axis
  restated:** r2 saw this absence as an `IndexError`; the auto-fix's hardened helper reports it as a
  clean `None` comparison.
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `4 passed, 757 deselected in 1.71s`

### 3. `background-session-unlisted`

- **axis:** a launch with no agents row refuses with `background-session-unlisted`
- **detector:** `test_claude_background_session_unlisted_refused`
- **neutralization:** `session_id = session_id or "bite-proof-plant-session"` inserted after the
  `_resolve_bg_session_id` call
- **raw red:**
  ```
  E       AssertionError: assert 'background-s...ithout-result' == 'background-session-unlisted'
  E         - background-session-unlisted
  E         + background-session-ended-without-result
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 760 deselected in 1.23s`

### 4. `background-transcript-ambiguous`

- **axis:** more than one transcript glob refuses with `background-transcript-ambiguous`
- **detector:** `test_claude_background_transcript_ambiguous_refused`
- **neutralization:** `transcript_paths = transcript_paths[:1]` inserted before
  `if len(transcript_paths) > 1:`
- **raw red:**
  ```
  >       ended = _bg_attempt_ended(run_dir)
  >       return ended[-1]
  E       IndexError: list index out of range
  ```
  On axis — the ambiguity refusal never happens, so no ended record exists.
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 760 deselected in 1.57s`

### 5. `background-session-ended-without-result`

- **axis:** a session the listing reports ended, with no materialized result, refuses with
  `background-session-ended-without-result`
- **detector:** `test_claude_background_session_ended_without_result_refused`
- **neutralization:** `if transcript_result is None:` → `if False:` inside the
  `_background_session_ended(agent_row)` branch
- **raw red:**
  ```
  >       assert ended["refusal"] == "background-session-ended-without-result"
  E       AssertionError: assert None == 'background-session-ended-without-result'
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 760 deselected in 1.01s`

### 5a. `background-agents-unreadable` — **new element, added by auto-fix round 1**

The record entry the fixer wrote carries an axis, a detector and a red/green pair, but **no
neutralization** — its red is the pre-implementation failure of a newly added test, not a
neutralization of the shipped guard. This re-run supplies the missing neutralization.

- **axis:** an unreadable agents listing during the poll refuses with `background-agents-unreadable`
- **detector:** `test_engine_dispatch.py::test_claude_background_agents_unreadable_refused`
- **neutralization:** `if not listing_ok:` → `if False:` at the poll loop's listing read
- **raw red:**
  ```
  >       assert ended["refusal"] == "background-agents-unreadable"
  E       AssertionError: assert 'background-s...ithout-result' == 'background-agents-unreadable'
  E         - background-agents-unreadable
  E         + background-session-ended-without-result
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 760 deselected in 0.98s`

### 6. transcript admission gate — **retired in r2; replaced by elements 24–26**

Not re-run in its recorded form (its r2 detector was an uncommitted `python3 -c` script). Its
committed replacement, `test_stdout_delivery_gate_transcript_branch`, is elements 24–26 below.

### 7. stop-and-confirm

- **axis:** a stop that cannot be confirmed is recorded `stop-unconfirmed`, never `stopped`
- **detector:** `test_claude_background_stop_records_stopped_already_ended_and_stop_failed` (the
  test's name still says `stop_failed`; its body asserts `stop-unconfirmed` — a naming minor
  disclosed in the PR, not a behaviour defect)
- **neutralization:** the final `return "stop-unconfirmed"` of `_background_stop` → `return "stopped"`
- **raw red:**
  ```
  E         - stop-unconfirmed
  E         + stopped
  FAILED ...::test_claude_background_stop_records_stopped_already_ended_and_stop_failed
  1 failed, 760 deselected in 1.00s
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `2 passed, 759 deselected in 0.88s`

---

## Elements 8–10 — `c14_l2b_background_safety.md`

### 8. BP-1 — write-mode background refusal

- **axis:** a claude `dispatch-write` with `claude_mode="background"` refuses
  `claude-mode-background-write` before anything spawns
- **detector:** `test_engine_dispatch_write.py::test_claude_mode_background_write_refused`
- **neutralization:** `return False` prepended to `_is_background_claude_mode`
- **raw red:**
  ```
  E         - claude-mode-background-write
  E         + internal-AssertionError
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 203 deselected in 0.36s`

### 9. BP-2 — listing blindness is not already-ended

- **axis:** an unreadable agents listing yields `stop-unconfirmed`, never `already-ended`
- **detector:** `test_claude_background_stop_listing_blind_not_already_ended`
- **neutralization:** the `if not ok_before:` branch of `_background_stop` → `return "already-ended"`
- **raw red:**
  ```
  E         - stop-unconfirmed
  E         + already-ended
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 760 deselected in 0.79s`

### 10. BP-3 — the resumed read cursor bounds the turn-end signal

- **axis:** after a suspension, stale pre-cursor `toolEndsTurn` rows must not end the attempt early
- **detector:** `test_claude_background_resume_ignores_stale_turn_end_signal`
- **neutralization:** `rows_after_cursor = rows[cursor:] if cursor else rows` → `rows_after_cursor = rows`,
  at **both** sites (the poll loop and the session-ended re-read). **Axis restated at this head:** r2
  recorded one site; the refactor gives the bound two, and the element is the bound, not a line.
- **raw red:**
  ```
  >       assert not any(r.get("kind") == "attempt-ended" for r in records_mid)
  E       assert not True
  ```
- **restore:** two inverse edits, one per site. **Restore receipt:** clean. **raw green:** `1 passed, 760 deselected in 0.81s`

---

## Elements 11–12 — `c14_l2b_mode_home.md`

The record declares one element (bidirectional lockstep); it is re-run as two, one per direction,
matching r2.

### 11. missing-delivery direction

- **axis:** a non-print claude mode declared in the adapter with no delivery entry must fail closed
- **detector:** `test_engine_result_channel.py::test_non_print_claude_mode_capability_delivery_agree`
- **neutralization:** `"c14-biteproof-orphan-mode": frozenset({"claude"})` added to
  `engine_adapter._NON_PRINT_CLAUDE_MODE_ENGINES`
- **raw red** (collection error — the derivation raises at import, before the drift test runs):
  ```
  E   ValueError: non-print claude mode 'c14-biteproof-orphan-mode' declared in engine_adapter has no result delivery entry in _RESULT_DELIVERY_BY_MODE
  1 error in 0.25s
  ```
  **Disclosed limitation, unchanged from r2:** in this direction the construction-time raise fires
  first, so the red proves the **derivation** fails closed, not the drift test's own first assertion.
  Element 12 is what exercises the test's assertions.
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 87 deselected in 0.18s`

### 12. ghost-delivery direction

- **axis:** a derived delivery pair the adapter does not declare must fail the drift test
- **detector:** the same test's ghost-delivery assertion
- **neutralization** (`engine_result_channel._derive_result_delivery_by_engine_mode`):
  `derived[("claude", "c14-biteproof-ghost-mode")] = RESULT_DELIVERY_TRANSCRIPT` before `return derived`
- **raw red:**
  ```
  E       assert not {('claude', 'c14-biteproof-ghost-mode')}
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 87 deselected in 0.23s`

---

## Elements 13–23 — layer 2a's `c14_l2_claude_mode.md`

This layer changes `engine_dispatch.py`, `engine_adapter.py` and `engine_result_channel.py` — the
three files 2a's detectors guard — so 2a's record is re-run here rather than taken on trust.

### 13. BP-1 / 20. BP-8 — `claude-mode-unknown` (review entry and write entry)

- **axis:** a garbage `claude_mode` refuses before open with detail `claude-mode-unknown:<value>`
- **detectors:** `test_engine_dispatch.py::test_claude_mode_unknown_refused_before_open` and
  `test_engine_dispatch_write.py::test_claude_mode_unknown_refused_before_open_write`
- **neutralization:** `_claude_mode_unknown_detail` body → `return "wrong-claude-mode-detail"`
- **raw red** (both detectors, one plant — the shared production site is why they are proved together):
  ```
  E       assert 'wrong-claude-mode-detail' == "claude-mode-unknown:'bogus'"
  FAILED ...test_engine_dispatch.py::test_claude_mode_unknown_refused_before_open
  FAILED ...test_engine_dispatch_write.py::test_claude_mode_unknown_refused_before_open_write
  2 failed, 963 deselected in 2.05s
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `2 passed, 963 deselected in 1.21s`

### 14. BP-2 / 21. BP-9 — `claude-mode-unsupported` (review entry and write entry)

- **axis:** `background` on a codex seat refuses with detail `claude-mode-unsupported:codex`
- **detectors:** `test_claude_mode_unsupported_codex_background_refused` and its `_write` sibling
- **neutralization:** `_claude_mode_unsupported_detail` body → `return "wrong-unsupported-detail"`
- **raw red:**
  ```
  E       AssertionError: assert 'wrong-unsupported-detail' == 'claude-mode-...pported:codex'
  2 failed, 963 deselected in 1.45s
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `2 passed, 963 deselected in 1.20s`

### 15. BP-3 — review continuation `run-dir-claude-mode-mismatch`

- **axis:** a continuation whose `--claude-mode` disagrees with the journal refuses
  `run-dir-claude-mode-mismatch` with `attempts: 0`
- **detector:** `test_run_dir_claude_mode_mismatch_refused`
- **neutralization:** `False and` inserted into the condition in `_dispatch_review_impl`
- **raw red:** `E       KeyError: 'detail'` — the refusal is not produced at all
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 760 deselected in 1.09s`

### 16. BP-4 — the `_spawn_attempt` background guard — **retired, guard deleted by design**

2a shipped `claude-mode-not-dispatchable:background` as a declared temporary. This layer makes
background mode real, so the guard is gone and there is no detector left to neutralize. 2a's record
stands as the receipt for the layer that shipped it; element 8 plus the whole flow record replace it
here.

### 17. BP-5 — `result_delivery` undeclared-mode raise

- **axis:** an unknown claude mode on a registered engine raises rather than returning a delivery
- **detector:** `test_engine_result_channel.py::test_result_delivery_undeclared_mode_refuses`
- **neutralization:** the `mode not in CLAUDE_MODES` raise → `return RESULT_DELIVERY_ARGV`
- **raw red:** `E           Failed: DID NOT RAISE <class 'ValueError'>`
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 87 deselected in 0.18s`

### 18. BP-6 — adapter `unknown-claude-mode` reason token

- **axis:** a non-string or unknown `claudeMode` in `build_argv_result` refuses with the literal
  token `unknown-claude-mode`
- **detector:** `test_engine_adapter.py::test_build_argv_unknown_claude_mode_refuses`
- **neutralization:** **both** `unknown-claude-mode` refusal sites (the not-a-string site and the
  not-in-`CLAUDE_MODES` site) → `"wrong-unknown-claude-mode"`. Both, not one: the element is the
  token contract, and one site left intact would prove nothing about the other.
- **raw red:** `E       AssertionError` (`1 failed, 581 deselected in 0.37s`)
- **restore:** inverse edit over both sites. **Restore receipt:** clean. **raw green:** `1 passed, 581 deselected in 0.31s`

### 19. BP-7 — adapter `claude-mode-unsupported` reason token

- **axis:** `background` on a codex vendor refuses with the literal token `claude-mode-unsupported`
- **detector:** `test_engine_adapter.py::test_build_argv_claude_mode_unsupported_on_codex`
- **neutralization:** that refusal site's token → `"wrong-claude-mode-unsupported"`
- **raw red:** `E       AssertionError` (`1 failed, 581 deselected in 0.44s`)
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 581 deselected in 0.32s`

### 22. BP-10 — the write-path mismatch gate and its precedence

Two findings, both re-confirming what WO-R1 recorded, plus one receipt r2 did not have.

- **The gate stays unreachable by construction.** Planting `False and` into the
  `run-dir-claude-mode-mismatch` condition inside `_dispatch_write_impl` leaves the write suite
  **green** (`1 passed, 203 deselected in 0.77s`) — the same non-bite r2 found. The guard stays (a
  fail-closed branch deleted for being momentarily unreachable is how it falls open when a third mode
  arrives); the unreachability is stated at the site; element 27's census fails the moment the mode
  set grows.
- **The precedence that makes it unreachable is itself covered, and bites.**
  - **axis:** with a background journal, the background-write refusal precedes the mismatch gate
  - **detector:** `test_background_journal_refuses_claude_mode_background_write_before_run_dir_mismatch`
  - **neutralization:** `return False` prepended to `_is_background_claude_mode`
  - **raw red:**
    ```
    E       AssertionError: assert 'run-dir-claude-mode-mismatch' == 'claude-mode-background-write'
    E         - claude-mode-background-write
    E         + run-dir-claude-mode-mismatch
    ```
    **This is the receipt r2 lacked:** the mismatch gate *does* fire correctly once the earlier
    refusal is removed. The gate is unreachable, not broken.
  - **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 203 deselected in 0.39s`

### 23. BP-11 — `engine_adapter.claude_mode_supported`

- **axis:** codex + `background` is refused before open because `claude_mode_supported` returns
  False for that pair
- **detectors:** `test_claude_mode_unsupported_codex_background_refused` and
  `test_build_argv_claude_mode_unsupported_on_codex`
- **neutralization:** `return True` prepended to `claude_mode_supported`
- **raw red** (both detectors):
  ```
  E       AssertionError: assert 'internal-AssertionError' == 'claude-mode-...pported:codex'
  E       AssertionError: assert None == 'claude-mode-unsupported'
  2 failed, 1341 deselected in 1.24s
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `2 passed, 1341 deselected in 1.05s`

### BP-12 — `_stdout_delivery_gate` unresolved-delivery refusal

- **axis:** when `result_delivery` raises, the gate forfeits `result-delivery-unresolved` rather
  than falling open
- **detector:** `test_stdout_delivery_gate_unresolved_delivery_forfeits`
- **neutralization:** `return None` prepended to `_result_delivery_gate_refusal`
- **raw red:** `E       assert None is not None`
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 760 deselected in 0.76s`

### BP-13 — `_NATIVE_MATERIALIZER_DELIVERIES` census

- **axis:** the materializer's delivery set stays in lockstep with the delivery members
  (stdout + transcript)
- **detector:** `test_native_materializer_delivery_census`
- **neutralization:** `RESULT_DELIVERY_TRANSCRIPT` removed from the frozenset
- **raw red:**
  ```
  E       AssertionError: assert frozenset({'stdout'}) == frozenset({'s...'transcript'})
  E         Extra items in the right set:
  E         'transcript'
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 760 deselected in 0.78s`

---

## Elements 24–27 — `c14_l2b_r2_gate_coverage.md`

**Axis restated at this head.** Auto-fix round 3 refactored `_stdout_delivery_gate` so the stdout and
transcript branches share one materialization comparison (`materialized = ended.get("transcriptResult")`
or `ended.get("stdoutResult")`, then one set of outcome branches). The three neutralizations below are
re-aimed at that shared comparison; the detector and its three legs are unchanged, and each leg still
reds on its own plant.

### 24. E1 — transcript branch, missing result

- **axis:** a missing `transcriptResult` on the transcript delivery branch forfeits
  `native-result-missing`
- **detector:** `test_stdout_delivery_gate_transcript_branch`
- **neutralization:** the gate's terminal `native-result-missing` forfeit dict → `return None`
- **raw red:**
  ```
  E       AssertionError: assert None == {'detail': 'native-result-missing', 'forfeit': True, 'reason': 'forfeited'}
  ```
- **restore:** inverse edit. **Restore receipt:** clean.

### 25. E2 — transcript branch, occupied path

- **axis:** `transcriptResult == "occupied"` forfeits `native-result-path-occupied`
- **neutralization:** the occupied branch's forfeit dict → `return None`
- **raw red:**
  ```
  E       AssertionError: assert None == {'detail': 'native-result-path-occupied', 'forfeit': True, 'reason': 'forfeited'}
  ```
- **restore:** inverse edit. **Restore receipt:** clean.

### 26. E3 — transcript branch, materialized admission

- **axis:** `transcriptResult == "materialized"` admits (`None`)
- **neutralization:** the materialized branch's `return None` → a `native-result-missing` forfeit dict
- **raw red:**
  ```
  >       assert _gate_for_transcript_result(transcript_result="materialized") is None
  E       AssertionError: assert {'detail': 'native-result-missing', 'forfeit': True, 'reason': 'forfeited'} is None
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green (24–26 together):** `1 passed, 760 deselected in 1.00s`

### 27. E4 — the claude-mode literal census

- **axis:** the declared mode literals `"print"` and `"background"` are pinned as literals, so a
  third mode fails and re-opens the write-path mismatch gate's coverage
- **detector:** `test_engine_dispatch_write.py::test_claude_mode_literal_census_pins_write_path_mismatch_gate_reachability`
- **neutralization:** `CLAUDE_MODES = (MODE_PRINT, MODE_BACKGROUND, "c14-biteproof-third-mode")`
- **raw red:**
  ```
  E       AssertionError: a new claude mode makes the write-path run-dir-claude-mode-mismatch gate reachable; the gate now needs a real test
  E       assert ('print', 'ba...f-third-mode') == ('print', 'background')
  E         Left contains one more item: 'c14-biteproof-third-mode'
  ```
  The assertion is written against the **literals**, not the `MODE_PRINT` / `MODE_BACKGROUND`
  symbols, per the external-contract-constant rule — a symbol-spelled assertion stays green under any
  value.
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed, 203 deselected in 0.31s`

---

## Element 28 — the background-refusal literal census (new detector, no prior record)

Auto-fix round 2 added `background_outcome.py` (the single home for the six background refusal
tokens) and `test_background_outcome_census.py`, a static AST census asserting those literals appear
nowhere else in `engine_dispatch.py`. **It shipped without a bite-proof record.** This element
supplies one; it is records-and-tests only and touches no product code.

- **axis:** a background refusal token spelled as a literal outside `background_outcome.py` fails
  the census
- **detector:** `test_background_outcome_census.py::test_background_refusal_literals_only_in_home[engine_dispatch.py]`
- **neutralization:** in `engine_dispatch.py`, `refusal = background_outcome.REFUSAL_TRANSCRIPT_AMBIGUOUS`
  → `refusal = "background-transcript-ambiguous"` (the exact drift the census exists to catch)
- **raw red:**
  ```
  E       AssertionError: [('background-transcript-ambiguous', 1419)]
  E       assert [('background...guous', 1419)] == []
  1 failed in 0.11s
  ```
  The census names the offending token **and its line** — it locates the drift, it does not merely
  detect it.
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.14s`

---

## Closing receipt

Probe worktree at `f5e6aabb`, after the final restore:

```
$ git rev-parse HEAD
f5e6aabb7c09bf1e2a0b88d98df6f110a3347a4a
$ git status --porcelain
(empty)
```

No repair was needed and **no probe touched product code as a landed change** — every mutation was
planted and reverted by its inverse edit. Nothing on this branch changed as a result of this re-run
except this record.
