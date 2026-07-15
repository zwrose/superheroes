# Failure-Mode review — #430 synthesis-fold staged-id + unmatched disclosure

Branch `fix/superheroes-430-synthesis-fold` vs origin/main @ 515e0c1.
Dimension: Failure-Mode. Single pass.

## Verdict: NO BLOCKING FINDINGS (0 Critical, 0 Important).

The change is fail-closed across every attack vector named in the task. Details of
what I verified, per vector, below. One non-blocking observation is recorded at the end.

---

## Attack-vector walkthrough (all cleared)

### 1. Fabricated echo — a judge that echoes an id for a finding it never examined
Cleared. Staging `f.id = findingIdentity(f)` (review_panel_shell.js:794-796;
bundle:1791) makes the id trivially copyable, so a judge *can* echo without examining.
But a drop still requires `action=="drop"` AND a non-empty `reason`
(loop_synthesis.py:93; .js:33), and every dropped blocker rides out flagged
`was_blocking_tagged` via the fail-closed `circuit_breaker.is_blocking` predicate
(loop_synthesis.py:96; .js:35), surfaced in the readout's drop section. A fabricated
drop of a real blocker is therefore never silent — it lands in `drops` with the
scrutiny flag. Keep-on-uncertain governs everything else. This is the documented
FR-12 contract; the change does not weaken it.

### 2. ID collisions in one round (two findings, same file::normalized-title)
Not reachable in production, and safe if it were. `merged` fed to `consume` always
comes from `panel_tally.compile_findings`, which dedupes by the *same* `finding_identity`
(panel_tally.py:119-141) before `synthesizeRound` stages ids — so the merged set has
unique identities by construction. Python and JS agree bit-for-bit: `by_id` is
last-wins in both; `matched_ids`/`matchedIds` records the primary identity key (or the
literal-id fallback only when the primary misses) in both; `unmatched` is computed as
"by_id keys not in matched" in insertion order in both. JS uses `Object.create(null)`
for both maps explicitly for Python-dict parity (guards `__proto__`-shaped ids). The
`!v` (JS) vs `v is None` (Python) check is equivalent because `by_id` only ever holds
truthy objects. Parity is also machine-enforced: `loop_synthesis.consume` is a
registered parity twin (test_parity.py:38) with shared goldens including the collision
and unmatched cases; the bundle copy (showrunner.bundle.js:540-574) is regenerated and
identical. The dedicated `test_id_collision_across_findings_no_false_unmatched`
(test_loop_synthesis.py:125) pins the behavior.
- Residual note (not a defect): *if* a collision ever reached `consume` with a `drop`
  verdict, both colliding findings would drop on the one verdict. Unreachable because
  compile_findings runs first; documented here only because the task asked.

### 3. Mixed rounds on resume — legacy drifted verdict ids meeting a new staged-id merged set
Cleared, degrades fail-closed. `consume` matches by *recomputing* `finding_identity(f)`
at fold time (loop_synthesis.py:81; .js:26) — it never trusts a persisted verdict's
key. A legacy/drifted verdict id simply matches no finding → lands in `unmatched`
(surfaced loudly) → the finding is KEPT (keep-on-uncertain). No corruption, no silent
drop. Additionally, leaf verdicts are computed in-process each round
(synthesizeRound → synthesisLeaf → consume) and consumed immediately; they are not
persisted-then-reread, so the "in-flight verdict file meets new merged set" window does
not actually exist on the native path. The standalone CLI seam
(`loop_synthesis.py --merged --leaf`) has the identical recompute-and-match behavior.

### 4. Partial failure of the synthesis leaf
Cleared, never raises. `consume` guards every shape: non-list `leaf_verdicts` →
`by_id` empty → `unmatched=[]` (test_malformed_leaf_output_keeps_everything). Leaf
throws → `synthesizeRound` is wrapped (review_panel_shell.js:596-604), logs and falls
back to `synthesized=null` → `tallyRound` takes the raw-compile branch with
`unmatched=[]` (shell:1003-1007). The `tallyRound` catch and the empty-roster early
return both emit `findings:[]` WITHOUT an `unmatched` key (shell:981-983, 1041-1043),
and both `compose_terminal_record` and `loop_readout.render` treat an absent
`unmatched` as empty. `unmatched` is only attached when non-empty (shell:1028), so the
healthy terminal record and its inline scalars are byte-unchanged in the common case.

### 5. Transit of a non-empty `unmatched` → writeTerminalRecord → compose_terminal_record → readout
Cleared, no drop point, fidelity verified. `unmatched` survives `writeTerminalRecord`'s
slim strip (fenced_json.js:83-89 deletes findings/carriedFindings/fixes/deferred/
coverageDecisions — not `unmatched`), so it is inside `verdictJson` and therefore
covered by `verdictHash = contentHash(verdictJson)` (fenced_json.js:89-90). Python
`compose_terminal_record` self-verifies that hash (`_sent_hash_ok`, review_memory.py:536)
and `_TERMINAL_STRIP` (review_memory.py:492) does not include `unmatched`, so it lands
in the record. A courier that mangles it fails closed (`verdict-corrupt` → one retry →
hard fail) rather than persisting altered content. `loop_readout.render`
(loop_readout.py:127-133) filters to strings and renders the loud section. The
`_should_preserve_clean_terminal` early-return (review_memory.py:552) only discards an
incoming non-clean record when a newer prior *clean* terminal exists (stale/out-of-order
resume or a transport-failure reason) — a correct preservation; the discarded
`unmatched` belonged to a superseded round.

---

## Non-blocking observation (recorded, not a finding)

`unmatched` is a new field that rides *inline* through the terminal-record courier
(fenced_json.js:89 → review_memory.py compose-terminal), whereas the module's own
docstrings (fenced_json.js:70-75; review_memory.py:530-532) state that only "small
verdict scalars" ride inline and that unbounded synthesis outputs
(fixes/deferred/coverageDecisions) are deliberately re-derived from disk to avoid the
courier. `unmatched` is bounded by the round's leaf-verdict count (≈ one per merged
finding — inherently modest for a review panel) and each id is `clamp_title`-bounded,
so this is not a realistic resource/transport risk, and fidelity is hash-verified. It
is called out only because it is a new inline field on a boundary whose contract is
documented as scalars-only; if finding counts ever grow, prefer re-deriving `unmatched`
from the round record rather than couriering it. No action required for this change.

## Findings JSON

```json
[]
```
