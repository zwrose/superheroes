# C14 layer 2b (r2) — every bite-proof re-run on the final head

**Who ran this:** the orchestrator (workhorse), not an implementer. Verification authority does not
delegate: every red and green below was produced by the orchestrator applying the neutralization
itself through the host's edit action and reverting it with the inverse edit — never a git discard.

**Where:** a dedicated detached probe worktree under session scratch, never the build worktree and
never a tree a live review seat was reading. The build worktree's landed work was committed before
the first probe.

**Why this record exists.** The four records this branch carries — `c14_l2_background_flow.md`
(WO-1), `c14_l2b_mode_home.md` (WO-3), `c14_l2b_background_safety.md` (WO-2) and layer 2a's
`c14_l2_claude_mode.md`, whose surfaces this layer changes — were each proved **by their own order,
on that order's own head**. None had been proved at one final head. Detector-narrowing staleness is
exactly what that leaves open: a detector that bit on its author's head can stop biting once a later
order narrows the path it reached through. This record closes that gap by re-running all of them
together.

**Two heads, and why that is honest.** Elements 1–23 were re-run at `af2ad185`. The re-run itself
found two holes (below), whose repair landed as WO-R1 at `e431ab89`; elements 24–27 were re-run
there. The production delta between the two heads is **one comment line** in `engine_dispatch.py`
and nothing else — `git diff af2ad185 e431ab89 -- plugins/superheroes/lib/*.py` is a single
`+` line, the axis comment at the write-path mismatch gate. No production behaviour the first
twenty-three proofs exercised changed between them.

**Captures.** Full pytest output for each run went to session scratch outside the repository. The
decisive assertion lines are quoted here verbatim; the elided remainder is the standard pytest
header, fixture repr and traceback frames. Nothing redacted — no capture carried a secret, token,
private URL or PII; tmp paths under the platform pytest tmpdir appear in the originals and are
elided rather than redacted.

**Restore receipts.** After every restore, `git status --porcelain` over the probe worktree
returned **empty** — no residue, on every one of the twenty-seven. Where the line below says
"clean", that is that receipt.

---

## What the re-run found

**Twenty-five of twenty-seven guarded elements went red under neutralization and green after
restore.** The two that did not are real, and both are repaired on this branch:

1. **`_stdout_delivery_gate`'s transcript branch had no committed detector.** Its entry in
   `c14_l2_background_flow.md` names its detector as `inline gate assert` — a throwaway
   `python3 -c` script. That is a session artifact, not a durable detector (CONVENTIONS §12.1).
   Repaired by WO-R1: `test_stdout_delivery_gate_transcript_branch`, proved as E1–E3 in
   `c14_l2b_r2_gate_coverage.md` and re-run below.

2. **The write-path `run-dir-claude-mode-mismatch` gate was uncovered, and the test whose name
   claimed it did not cover it.** Planting `False and` into the condition inside
   `_dispatch_write_impl` left `test_run_dir_claude_mode_mismatch_refused_write` **passing** — the
   green-where-it-should-be-red tell. Reading it back: WO-2 put the background-write refusal in
   front of that gate, so the test asserts the background-write token and never reaches the
   mismatch comparison. With the declared modes exactly `print` and `background` the gate is
   unreachable by construction. Repaired by WO-R1 — the guard **stays** (a fail-closed branch
   deleted for being momentarily unreachable is how it falls open when a third mode arrives), the
   unreachability is stated at the site, the test is renamed to what it asserts, and a literal
   census (E4) fails the moment the mode set grows.

---

## Elements 1–7 — `c14_l2_background_flow.md` (WO-1), re-run at `af2ad185`

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
  FAILED ...test_claude_background_launch_refusals[-0-background-launch-unacknowledged]
  FAILED ...test_claude_background_launch_refusals[error: failed\n-0-background-launch-unacknowledged]
  FAILED ...test_claude_background_launch_refusals[backgrounded \xb7 abcdefg\n-0-background-launch-unacknowledged]
  ```
  All three unacknowledged params red; the fourth (launch-failed) stayed green, which is the axis
  holding.
- **restore:** the inserted line removed by the inverse edit. **Restore receipt:** clean.
- **raw green:** `4 passed in 0.82s`

### 2. `background-launch-failed`

- **axis:** a non-zero launch child exit refuses with `background-launch-failed`
- **detector:** the `backgrounded · … / exit 1` param of the same test
- **neutralization:** `exit_code = 0` inserted immediately before `if exit_code not in (0, None):`
- **raw red:**
  ```
  >       ended = _bg_attempt_ended(run_dir)
  E       IndexError: list index out of range
  1 failed, 3 passed
  ```
  On axis — with the non-zero exit neutralized no launch-failed record is written at all, which is
  the absence the detector exists to catch; the red arrives as the empty-record IndexError rather
  than a token mismatch.
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `4 passed in 0.81s`

### 3. `background-session-unlisted`

- **axis:** a launch with no agents row refuses with `background-session-unlisted`
- **detector:** `test_claude_background_session_unlisted_refused`
- **neutralization:** `session_id = session_id or "bite-proof-plant-session"` inserted after
  `_resolve_bg_session_id`
- **raw red:**
  ```
  E       AssertionError: assert 'background-s...ithout-result' == 'background-session-unlisted'
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.80s`

### 4. `background-transcript-ambiguous`

- **axis:** more than one transcript glob refuses with `background-transcript-ambiguous`
- **detector:** `test_claude_background_transcript_ambiguous_refused`
- **neutralization:** `transcript_paths = transcript_paths[:1]` inserted before
  `if len(transcript_paths) > 1:`
- **raw red:** `E       IndexError: list index out of range` (no ended record — the ambiguity
  refusal never happens; on axis, same absence shape as element 2)
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.73s`

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
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.86s`

### 6. transcript admission gate — **proof upgraded, see elements 24–26**

The record's entry names its detector as `inline gate assert`, and its red is
`File "<string>", line 9, in <module>` — an uncommitted one-off. **This element is not re-run in
its recorded form.** It is replaced on this branch by a committed detector
(`test_stdout_delivery_gate_transcript_branch`) whose three legs are elements 24–26 below.

### 7. stop-and-confirm — **axis restated at this head**

- **recorded axis (stale):** "stop failure surfaces `stop-failed` not `stopped`". `stop-failed` is
  not an outcome of `_background_stop` at this head; WO-2 settled the outcome set at
  `stopped` / `already-ended` / `stop-unconfirmed`.
- **axis as re-run:** a stop that cannot be confirmed is recorded `stop-unconfirmed`, never
  `stopped`
- **detector:** `test_claude_background_stop_records_stopped_already_ended_and_stop_failed` (the
  test's name still says `stop_failed`; its body asserts `stop-unconfirmed` — a naming minor
  disclosed in the PR, not a behaviour defect)
- **neutralization:** the final `return "stop-unconfirmed"` of `_background_stop` → `return "stopped"`
- **raw red:**
  ```
  >       assert ED._background_stop(launch_id, cfg, cwd) == "stop-unconfirmed"
  E       AssertionError: assert 'stopped' == 'stop-unconfirmed'
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `2 passed in 0.72s`

---

## Elements 8–10 — `c14_l2b_background_safety.md` (WO-2), re-run at `af2ad185`

### 8. BP-1 — write-mode background refusal

- **axis:** a claude `dispatch-write` with `claude_mode="background"` refuses
  `claude-mode-background-write` before anything spawns
- **detector:** `test_engine_dispatch_write.py::test_claude_mode_background_write_refused`
- **neutralization:** `return False` prepended to `_is_background_claude_mode`
- **raw red:**
  ```
  >       assert res["detail"] == ED.MODE_REFUSAL_CLAUDE_MODE_BACKGROUND_WRITE
  E       AssertionError: assert 'internal-AssertionError' == 'claude-mode-background-write'
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.35s`

### 9. BP-2 — listing blindness is not already-ended

- **axis:** an unreadable agents listing yields `stop-unconfirmed`, never `already-ended`
- **detector:** `test_claude_background_stop_listing_blind_not_already_ended`
- **neutralization:** the `if not ok_before:` branch of `_background_stop` → `return "already-ended"`
- **raw red:**
  ```
  E       AssertionError: assert 'already-ended' == 'stop-unconfirmed'
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.83s`

### 10. BP-3 — the resumed read cursor bounds the turn-end signal

- **axis:** after a suspension, stale pre-cursor `toolEndsTurn` rows must not end the attempt early
- **detector:** `test_claude_background_resume_ignores_stale_turn_end_signal`
- **neutralization:** `rows_after_cursor = rows[cursor:] if cursor else rows` → `rows_after_cursor = rows`
- **raw red:**
  ```
  >       assert not any(r.get("kind") == "attempt-ended" for r in records_mid)
  E       assert not True
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 1.21s`

---

## Elements 11–12 — `c14_l2b_mode_home.md` (WO-3), re-run at `af2ad185`

The record declares one element (bidirectional lockstep). **It is re-run as two**, one per
direction, because each direction is independently neutralizable and they fail in different places
— the finer reading is recorded here as a signal for the advisor, not a rework demand.

### 11. missing-delivery direction

- **axis:** a non-print claude mode declared in the adapter with no delivery entry must fail closed
- **detector:** `test_engine_result_channel.py::test_non_print_claude_mode_capability_delivery_agree`
- **neutralization:** `"c14-biteproof-orphan-mode": frozenset({"claude"})` added to
  `engine_adapter._NON_PRINT_CLAUDE_MODE_ENGINES`
- **raw red** (collection error — the derivation raises at import, before the drift test can run):
  ```
  E   ValueError: non-print claude mode 'c14-biteproof-orphan-mode' declared in engine_adapter has no result delivery entry in _RESULT_DELIVERY_BY_MODE
  1 error in 0.31s
  ```
  Disclosed limitation, unchanged from the original record: in this direction the construction-time
  raise fires first, so the red proves the **derivation** fails closed and not the drift test's own
  first assertion. The second direction (element 12) is what exercises the test's assertions.
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.25s`

### 12. ghost-delivery direction

- **axis:** a derived delivery pair the adapter does not declare must fail the drift test
- **detector:** the same test's `ghost_delivery` assertion
- **neutralization** (`engine_result_channel._derive_result_delivery_by_engine_mode`):
  `derived[("claude", "c14-biteproof-ghost-mode")] = RESULT_DELIVERY_TRANSCRIPT` before `return derived`
- **raw red:**
  ```
  E       AssertionError: derived delivery map has (engine, mode) pairs adapter does not declare: [('claude', 'c14-biteproof-ghost-mode')]
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.25s`

---

## Elements 13–23 — layer 2a's `c14_l2_claude_mode.md`, re-run at `af2ad185`

This layer changes `engine_dispatch.py`, `engine_adapter.py` and `engine_result_channel.py` — the
three files 2a's detectors guard — so 2a's record is re-run here rather than taken on trust from
2a's own head.

### 13. BP-1 / 20. BP-8 — `claude-mode-unknown` (review entry and write entry)

- **axis:** a garbage `claude_mode` refuses before open with detail `claude-mode-unknown:<value>`
- **detectors:** `test_engine_dispatch.py::test_claude_mode_unknown_refused_before_open` and
  `test_engine_dispatch_write.py::test_claude_mode_unknown_refused_before_open_write`
- **neutralization:** `_claude_mode_unknown_detail` body → `return "wrong-claude-mode-detail"`
- **raw red** (both, one plant, two detectors — the shared production site is why they are proved
  together):
  ```
  E       assert 'wrong-claude-mode-detail' == "claude-mode-unknown:'bogus'"
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `2 passed in 6.00s`

### 14. BP-2 / 21. BP-9 — `claude-mode-unsupported` (review entry and write entry)

- **axis:** `background` on a codex seat refuses with detail `claude-mode-unsupported:codex`
- **detectors:** `test_claude_mode_unsupported_codex_background_refused` and its `_write` sibling
- **neutralization:** `_claude_mode_unsupported_detail` body → `return "wrong-unsupported-detail"`
- **raw red:**
  ```
  E       AssertionError: assert 'wrong-unsupported-detail' == 'claude-mode-...pported:codex'
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `2 passed in 5.83s`

### 15. BP-3 — review continuation `run-dir-claude-mode-mismatch`

- **axis:** a continuation whose `--claude-mode` disagrees with the journal refuses
  `run-dir-claude-mode-mismatch` with `attempts: 0`
- **detector:** `test_run_dir_claude_mode_mismatch_refused`
- **neutralization:** `False and` inserted into the condition in `_dispatch_review_impl`
- **raw red:** `E       KeyError: 'detail'` — the refusal is not produced at all
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.90s`

### 16. BP-4 — the `_spawn_attempt` background guard — **proof retired, guard deleted by design**

2a shipped `claude-mode-not-dispatchable:background` as a **declared temporary** whose whole job was
to make a declared-but-unreachable mode unreachable by construction. This layer makes background
mode real, so the guard is gone and the proof cannot be re-run: there is no detector left to
neutralize. 2a's record stands as the receipt for the layer that shipped it. What replaces it here
is element 8 (a background **write** still refuses before spawn) plus the whole of the flow record —
background is now reachable only through the transcript delivery path, under its own refusals.

### 17. BP-5 — `result_delivery` undeclared-mode raise

- **axis:** an unknown claude mode on a registered engine raises rather than returning a delivery
- **detector:** `test_engine_result_channel.py::test_result_delivery_undeclared_mode_refuses`
- **neutralization:** the `mode not in CLAUDE_MODES` raise → `return RESULT_DELIVERY_ARGV`
- **raw red:** `E           Failed: DID NOT RAISE <class 'ValueError'>`
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.18s`

### 18. BP-6 — adapter `unknown-claude-mode` reason token

- **axis:** a non-string or unknown `claudeMode` in `build_argv_result` refuses with the literal
  token `unknown-claude-mode`
- **detector:** `test_engine_adapter.py::test_build_argv_unknown_claude_mode_refuses`
- **neutralization:** **both** `unknown-claude-mode` refusal sites (the not-a-string site and the
  not-in-`CLAUDE_MODES` site) → `"wrong-unknown-claude-mode"`. Both, not one: the element is the
  token contract, and one site left intact would prove nothing about the other.
- **raw red:** `E       AssertionError`
- **restore:** inverse edit over both sites. **Restore receipt:** clean. **raw green:** `1 passed in 0.52s`

### 19. BP-7 — adapter `claude-mode-unsupported` reason token

- **axis:** `background` on a codex vendor refuses with the literal token `claude-mode-unsupported`
- **detector:** `test_engine_adapter.py::test_build_argv_claude_mode_unsupported_on_codex`
- **neutralization:** that refusal site's token → `"wrong-claude-mode-unsupported"`
- **raw red:** `E       AssertionError`
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.31s`

### 22. BP-10 — write continuation `run-dir-claude-mode-mismatch` — **did not bite; repaired**

- **axis claimed:** a write continuation whose `--claude-mode` disagrees with the journal refuses
  `run-dir-claude-mode-mismatch` with `attempts: 0`
- **neutralization:** `False and` inserted into the condition in `_dispatch_write_impl`
- **result: the detector stayed GREEN** — `1 passed in 0.39s`.
- **Why:** `test_run_dir_claude_mode_mismatch_refused_write` asserts
  `res["detail"] == ED.MODE_REFUSAL_CLAUDE_MODE_BACKGROUND_WRITE`. WO-2 put
  `_claude_mode_background_write_refusal` in front of the mismatch gate, so a background journal
  refuses earlier and the mismatch comparison is never reached. The gate is unreachable by
  construction while `CLAUDE_MODES == ("print", "background")`.
- **Disposition:** repaired by WO-R1 at `e431ab89` — the guard stays, the unreachability is stated
  at the site, the test is renamed to
  `test_background_journal_refuses_claude_mode_background_write_before_run_dir_mismatch` with the
  precedence asserted explicitly, and element 27 pins the mode literals so a third mode fails and
  re-opens the gate's coverage.
- **restore:** inverse edit. **Restore receipt:** clean.

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
  2 failed in 1.89s
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `2 passed in 1.76s`

### BP-12 — `_stdout_delivery_gate` unresolved-delivery refusal

- **axis:** when `result_delivery` raises, the gate forfeits `result-delivery-unresolved` rather
  than falling open
- **detector:** `test_stdout_delivery_gate_unresolved_delivery_forfeits`
- **neutralization:** `return None` prepended to `_result_delivery_gate_refusal`
- **raw red:** `E       assert None is not None`
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.79s`

### BP-13 — `_NATIVE_MATERIALIZER_DELIVERIES` census

- **axis:** the materializer's delivery set stays in lockstep with `RESULT_DELIVERY_MEMBERS`
  (stdout + transcript)
- **detector:** `test_native_materializer_delivery_census`
- **neutralization:** `RESULT_DELIVERY_TRANSCRIPT` removed from the frozenset
- **raw red:**
  ```
  E       AssertionError: assert frozenset({'stdout'}) == frozenset({'s...'transcript'})
  E         Extra items in the right set: 'transcript'
  ```
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.86s`

---

## Elements 24–27 — `c14_l2b_r2_gate_coverage.md` (WO-R1), re-run at `e431ab89`

The implementer produced these four proofs. They are re-run here by the orchestrator, against the
same production sites, with the orchestrator's own neutralizations and its own reds.

### 24. E1 — transcript branch, missing result

- **axis:** a missing `transcriptResult` on the transcript delivery branch forfeits
  `native-result-missing`
- **neutralization:** `if materialized is None: return None` inserted into the transcript branch of
  `_stdout_delivery_gate`
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
- **restore:** inverse edit. **Restore receipt:** clean. **raw green (24–26 together):** `1 passed in 1.45s`

### 27. E4 — the claude-mode literal census

- **axis:** the declared mode literals `"print"` and `"background"` are pinned as literals, so a
  third mode fails and re-opens the write-path mismatch gate's coverage
- **neutralization:** `CLAUDE_MODES = (MODE_PRINT, MODE_BACKGROUND, "c14-biteproof-third-mode")`
- **raw red:**
  ```
  E       AssertionError: a new claude mode makes the write-path run-dir-claude-mode-mismatch gate reachable; the gate now needs a real test
  E       assert ('print', 'ba...f-third-mode') == ('print', 'background')
  E         Left contains one more item: 'c14-biteproof-third-mode'
  ```
  The assertion is written against the **literals**, not the `MODE_PRINT` / `MODE_BACKGROUND`
  symbols, per the external-contract-constant rule — a symbol-spelled assertion stays green under
  any value.
- **restore:** inverse edit. **Restore receipt:** clean. **raw green:** `1 passed in 0.35s`
