# Contents

- [The one entrypoint](#the-one-entrypoint)
- [next / submit protocol](#next--submit-protocol)
- [Actions and payloads](#actions-and-payloads)
- [Journal and receipt](#journal-and-receipt)
- [Certification shapes](#certification-shapes)
- [Invariants](#invariants)
- [Port note](#port-note)

`lib/round_driver.py` is the **one entrypoint** for the review-code auto-fix loop (#507). It
collapses the old `code_loop_plan.py` plan/record/decide choreography, the manual circuit-breaker
call, and the head-diff derivation into a single `next`/`submit` state machine the orchestrator
obeys. `$ROOT_DIR` is `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`.

## The one entrypoint

Round 1 is always a full `reviewer-deep` baseline panel. Rounds 2+ are **delta rounds**: fix
audits over the just-fixed findings plus a scoped finder over the fix's new surface — a full panel
runs again only on the #174 re-arm triggers (Critical surfaced since the last qualifying panel, or
cross-cutting rework) or when the changed surface is **unknown** (fail toward run-everything). The
orchestrator never plans, records, or decides continuation by eye — it calls `next`, dispatches
exactly one action, and `submit`s the artifact.

Degraded / single-vendor environments stay **on** the mandated path: the same driver, the same
journal, and `independence: "degraded"` stamps on audit targets and the terminal certification
shape — never a silent off-ramp.

## next / submit protocol

Fresh state (first `next` of a session):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/round_driver.py" next \
  --session-dir "$SESSION_DIR" \
  --diff-path "$SESSION_DIR/round-1/diff.txt" \
  --verify-command "${VERIFY_CMD:-none}" \
  --max-rounds 7
```

Every step thereafter:

```bash
python3 "$ROOT_DIR/lib/round_driver.py" next --session-dir "$SESSION_DIR"
```

After fulfilling the emitted action, fold the artifact:

```bash
python3 "$ROOT_DIR/lib/round_driver.py" submit \
  --session-dir "$SESSION_DIR" \
  --phase "<phase from next>" \
  --attempt <attempt from next> \
  --state-hash "<expectedStateHash from next>" \
  --artifact "$SESSION_DIR/round-<N>/<phase>-artifact.json"
```

**Freshness / idempotence echo.** Each `next` returns `expectedStateHash` (a SHA-256 over canonical
`loop-state.json`). `submit` must echo `phase`, `attempt`, and `state-hash` exactly — a stale or
forked submit is rejected `{ok: false}`. A second `next` before `submit` re-emits the same pending
step and hash. An exact duplicate `submit` (same phase/attempt/artifact) returns
`{ok: true, duplicate: true}`.

Persist state under `$SESSION_DIR/loop-state.json`. Append every `next`/`submit` to
`$SESSION_DIR/driver-journal.jsonl` (the `scriptRan` evidence). On `terminal`, the driver writes
`$SESSION_DIR/round-receipt.json` — validate with `round_driver.validate_receipt`.

## Actions and payloads

| `action` / `phase` | Orchestrator fulfills |
| --- | --- |
| `dispatch-panel` | Dispatch the round's `reviewer-deep` panel per `payload.dimensions`, `payload.tier`, and optional `payload.shards` (big-diff sharding; cross-cutting lenses always get the whole diff). Submit `{seats: {<dim>: {findings, receiptMissing?, receiptStale?}}, seatMap?}`. Receipt-missing seats re-dispatch at most `REDISPATCH_BUDGET` times (`loop_plan_common.REDISPATCH_BUDGET` — the single home) before terminal `missing` with findings carried unverified. |
| `dispatch-verifiers` | One verifier per cluster in `payload.clusters` (`model: $VERIFIER_MODEL`, reviewer engine). Submit `{verdicts: [...]}`. |
| `dispatch-synthesis` | One synthesis judge over `payload.findings` (`model: $SYNTH_MODEL`). Submit `{grouping: [{group_id, member_ids}, ...]}`. Mechanical compile (citation, diff-scope, dedupe, nit cap) and `verification.merge_and_rank` run inside the driver; the **author-justification post-filter** runs here too (may drop only non-CONFIRMED findings; CONFIRMED survives stamped `challenge: "author-justified"`). |
| `dispatch-gap-sweep` | Big-diff only: one full-diff finder pass. Submit `{findings: [...]}`. |
| `dispatch-audits` | Delta round: one auditor per target in `payload.targets` — **never the fixer's vendor**; single-vendor runs stamp `independence: "degraded"`. Submit `{results: [...], collectionManifest: {<result-id>: <vendor>}}`. **Provenance rests on the orchestrator's dispatch manifest, not the result's echo:** you (the dispatching orchestrator) are the trusted collector — build `collectionManifest` from your OWN dispatch records (which vendor you seated per target, out-of-band from the results you got back), never copied from a result's `auditorVendor`. A clearing ruling (`discharged` / `discharged-but-new-issue`) is authenticated **iff `collectionManifest[id]` exists AND equals the driver-recorded selected auditor**; a missing manifest entry or a manifest vendor ≠ the selection → **not-discharged + `unauthenticated`**. The in-result `auditorVendor` is **advisory only** (a claimant-controlled echo authenticates nothing — a fixer can echo the expected value); an echo that disagrees with the manifest is disclosed as `echoMismatch` but the manifest governs and the discharge stands. Recorded per round as `auditProvenance: "collection-manifest"`. The driver **cannot cryptographically verify engine identity and does not pretend to** — the guarantee is exactly as strong as your dispatch manifest. |
| `dispatch-scoped-finder` | Delta round: scoped scan over `payload.hunks` (the split's computed new surface — file → hunk ranges + text) at `reviewer-deep`. Submit `{findings: [...]}`. Emitted **only when the computed new surface is non-empty**; a genuinely empty new surface (the split returned `unknown: False` with no new hunks) skips this dispatch and records `scopedFinder: skipped-empty-surface` on the round (receipt-visible) — never a vacuous scan over nothing. |
| `run-verify` | Run `payload.command` from the working tree (non-interactive, timeout). Submit `{result: "pass" \| "fail"}`. Fail → terminal halt, certification withheld. |
| `dispatch-fixer` | Dispatch fixer over `payload.batch` (blocking findings the driver selected). Submit `{fixes, headDiff \| headDiffPath, escalated?}` — the post-fix head diff comes from git (`git diff "$BASE_REF"...HEAD`), never the fixer's self-report. Provide it **inline** (`headDiff`) or, since a real head diff can be hundreds of KB and cannot reasonably inline into a JSON submit artifact, as an **absolute** file path (`headDiffPath`) the driver reads itself (**inline wins if both are present**). A missing / non-absolute / unreadable `headDiffPath` or empty content is treated as an **unknown surface** → the next round runs a full reviewer-deep panel (the unknown→run-everything rule), never an empty diff and never a silent scoped skip; the source used is recorded on the round as `headDiffSource: inline\|path\|unknown`. The changed policy subjects the #174 confirmation re-arm consumes are **derived by the driver itself** from the reviewed-vs-head diff through the accumulated findings (the injectable `changed_subjects` seam — library default + CLI wire the real git derivation, #157/#158); a self-reported `changedSubjects` is ignored on the live path. |
| `present-judgment` | A tradeoff/product-choice blocker is an **owner-judgment** call routed here — an **intervention gate, not a terminal**. Present each `payload.findings[]` (id, file, line, title, severity) with `payload.findings[].dispositions` (`fix-as-suggested`, `fix-with-guidance`, `skip`). Submit `{dispositions: [{id, disposition, guidance?, reason?}, ...]}` — `skip` needs a citable `reason`. Fixes fold into the round's fix batch and the loop proceeds into the fix leg; skips ride the exit disclosure. Fail-closed: a missing/unknown disposition (or a reasonless skip) folds as `fix-as-suggested` — a judgment blocker is never silently skipped. Never judge the dispute yourself. |
| `present-stall-menu` | The **audit-stall terminal** — reached only after one invisible self-recovery (never for a judgment blocker; those go to `present-judgment`). Present `payload.choices` (four-choice menu; `accept-the-disclosed-risk` only when `payload.acceptRiskEligible` — gated on a CONFIRMED finding with receipt). Submit `{choice}`. |
| `terminal` | Stop looping; read `payload.verdict` and `payload.certification`; surface honestly in the End-of-Loop Summary. |

## Journal and receipt

**Journal (`driver-journal.jsonl`).** One JSON object per line: `{cmd, phase, round, attempt, outcome, ts}`.
The receipt's `scriptRan` field summarizes it: `{invocations, byPhase}` where `byPhase` counts
`next:<phase>` and `submit:<phase>` entries. A terminal on the mandated path has a non-empty journal.

**Journal-fault detectability (no silent tier).** A failed journal append is never swallowed: the
driver records a durable fault marker (`driver-journal-fault.jsonl`) that `_finalize_receipt` fails
closed on (a partial-journal gap must never quietly certify). The **last resort** is fail-loud — if
the fault marker ALSO cannot be written, there is **no silent tier below this**: the CLI invocation
itself fails (`{"ok": false, "reason": "journal-fault-unrecordable"}` to stdout, the underlying
errors to stderr, **nonzero exit**), and the library `run_loop` parks **cannot-certify** (reason
`journal-fault-unrecordable`) rather than continuing as though the ran-evidence were intact.

**Terminal receipt re-check (every terminal `next`).** A **replayed** terminal `next` — a `next` on a
session already at its terminal step — re-emits the stored terminal pending WITHOUT re-running
`_finalize_receipt`, so a receipt fault recorded/surfaced *after* the receipt was first written (the
`driver-journal-fault.jsonl` marker, or a `round-receipt.json` that has become unreadable/invalid
since) would be masked by the replay's `ok`. So **every** terminal `next` — the first emission and
every replay — re-verifies receipt integrity before answering: the fault-marker's presence and
`validate_receipt` over the on-disk `round-receipt.json` **re-read fresh from disk** (never a cached
copy). Any fault → the CLI answers `{"ok": false, "reason": "receipt-fault", "detail": …}` with a
**nonzero exit** (never `terminal`-with-ok), the same fail-loud family as `journal-fault-unrecordable`.

**Receipt (`round-receipt.json`).** Required keys (shape-checked by `validate_receipt`, fail-closed):

- `schemaVersion` (2)
- `verdict` — `converged`, `halted`, `held`, `stalled`, `capped-with-open-critical`, …
- `certificationShape` — e.g. `full-panel-confirmed`, `audited-chain`, or `*-degraded` variants
- `certification` — full block (`shape`, `fullPanel`, `independence`, optional `note`/`reason`)
- `rounds` — per-round `kind`, `seatStatus`, `blockingCount`, `verifyResult`, `audits`, `auditProvenance` (`collection-manifest` when the round ran fix audits — the manifest-keyed provenance boundary, visible at vet), `unverified`, `authorJustifiedDrops`, `compileDrops`, `selfRecovery`, `stallChoice`
- `findings`, `decisions`, `seatMap`, `scriptRan`, `degraded` (disclosure list)
- `skippedBlockers` — the dedicated skipped-blocking channel (`{id, title, severity, reason}` per owner-skipped judgment blocker; possibly empty). **Required** (possibly empty) so a receipt can never omit the channel — a converge over any skip is CLEAN EXCEPT FOR SKIPPED, never a plain success, and its certification `reason` leads with `clean-except-skipped: N blocker(s) skipped with citable reasons`.

`validate_receipt(receipt)` returns `(ok, reason)` — a missing `scriptRan.byPhase` or non-list
`rounds`/`findings`/`skippedBlockers` rejects the receipt.

## Certification shapes

| Shape | Meaning |
| --- | --- |
| `full-panel-confirmed` | A qualifying full `reviewer-deep` confirmation panel ran before exit. |
| `audited-chain` | Scoped certifying finish — fixes discharged via audits + scoped verification; **no** final full panel. Surface this honestly; never imply a pristine fresh pass. |
| `*-degraded` | Appended when `independence` is degraded (single live vendor — auditor is fixer's vendor). |
| `null` / withheld | Verify fail, stall unresolved, capped-with-open-Critical park, owner `hold`, or `ship-smaller`/`spend-more`. |

**Terminals the orchestrator must surface honestly:**

- **Scoped certifying finish** (`audited-chain` / `audited-chain-degraded`) — delta rounds verified the fix chain; say so.
- **Judgment gate is an intervention, not a terminal** — a tradeoff blocker routes to `present-judgment` (fix-as-suggested / fix-with-guidance / skip-with-reason) and folds back into the fix leg; a skipped blocker rides the exit disclosure. It never dead-ends in the stall menu.
- **One invisible self-recovery** — audit-stall triggers a single fixer escalation (journaled); never offered as an owner menu item.
- **Four-choice stall menu** — `ship-smaller`, `spend-more`, `accept-the-disclosed-risk` (CONFIRMED-only), `hold`. Reached only from the audit-stall path.
- **Capped-with-open-Critical park** — confirmation budget exhausted with a Critical still owed.

## Invariants

Pinned by `test_round_driver.py` (ported from the retired `test_code_loop_plan.py`):

- Round 1 = full `reviewer-deep` baseline. Unknown changed surface → full panel (never risk a blind skip).
- #174 confirmation economics kept: at most two full confirmation panels; a Critical since the last
  qualifying panel or cross-cutting rework (≥3 subjects) re-arms one more; Critical still owed at
  the cap → `capped-with-open-critical` park.
- Audit-keyed stall breaker (`circuit_breaker.check_audit_breaker`) — not the old per-finding
  `circuit_breaker.py "$SESSION_DIR" 7` call inside the loop; the driver owns stall/self-recovery.
- `REDISPATCH_BUDGET` reads `loop_plan_common.REDISPATCH_BUDGET` only — never a local literal.
- Fail-closed everywhere: junk in → conservative out; never certify on silence.

## Port note

Layer 1 (`run_loop`) is the one-entrypoint loop orchestration with injectable seams (`reviewer`,
`synthesis`, `verifier`, `auditor`, `fix_step`, `verify_runner`, `changed_subjects`, `io`);
Layer 2 (`next`/`submit`) is the state machine between orchestrator dispatches. Parity is locked
by the goldens in `test_round_driver.py` and the PARITY receipt in `test_retry_budget_parity.py`.
Treat `round_driver.py` as the contract of record.
