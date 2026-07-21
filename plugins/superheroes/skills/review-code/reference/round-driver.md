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
| `dispatch-audits` | Delta round: one auditor per target in `payload.targets` — **never the fixer's vendor**; single-vendor runs stamp `independence: "degraded"`. Submit `{results: [...]}`. |
| `dispatch-scoped-finder` | Delta round: scoped scan over `payload.hunks` at `reviewer-deep`. Submit `{findings: [...]}`. |
| `run-verify` | Run `payload.command` from the working tree (non-interactive, timeout). Submit `{result: "pass" \| "fail"}`. Fail → terminal halt, certification withheld. |
| `dispatch-fixer` | Dispatch fixer over `payload.batch` (blocking findings the driver selected). Submit `{fixes, headDiff, changedSubjects, escalated?}` — head diff and changed subjects come from git, never the fixer's self-report. |
| `present-stall-menu` | Audit-keyed stall after one invisible self-recovery. Present `payload.choices` (four-choice menu; `accept-the-disclosed-risk` only when `payload.acceptRiskEligible` — gated on a CONFIRMED finding with receipt). Submit `{choice}`. |
| `terminal` | Stop looping; read `payload.verdict` and `payload.certification`; surface honestly in the End-of-Loop Summary. |

## Journal and receipt

**Journal (`driver-journal.jsonl`).** One JSON object per line: `{cmd, phase, round, attempt, outcome, ts}`.
The receipt's `scriptRan` field summarizes it: `{invocations, byPhase}` where `byPhase` counts
`next:<phase>` and `submit:<phase>` entries. A terminal on the mandated path has a non-empty journal.

**Receipt (`round-receipt.json`).** Required keys (shape-checked by `validate_receipt`, fail-closed):

- `schemaVersion` (2)
- `verdict` — `converged`, `halted`, `held`, `stalled`, `capped-with-open-critical`, …
- `certificationShape` — e.g. `full-panel-confirmed`, `audited-chain`, or `*-degraded` variants
- `certification` — full block (`shape`, `fullPanel`, `independence`, optional `note`/`reason`)
- `rounds` — per-round `kind`, `seatStatus`, `blockingCount`, `verifyResult`, `audits`, `unverified`, `authorJustifiedDrops`, `compileDrops`, `selfRecovery`, `stallChoice`
- `findings`, `decisions`, `seatMap`, `scriptRan`, `degraded` (disclosure list)

`validate_receipt(receipt)` returns `(ok, reason)` — a missing `scriptRan.byPhase` or non-list
`rounds`/`findings` rejects the receipt.

## Certification shapes

| Shape | Meaning |
| --- | --- |
| `full-panel-confirmed` | A qualifying full `reviewer-deep` confirmation panel ran before exit. |
| `audited-chain` | Scoped certifying finish — fixes discharged via audits + scoped verification; **no** final full panel. Surface this honestly; never imply a pristine fresh pass. |
| `*-degraded` | Appended when `independence` is degraded (single live vendor — auditor is fixer's vendor). |
| `null` / withheld | Verify fail, stall unresolved, capped-with-open-Critical park, owner `hold`, or `ship-smaller`/`spend-more`. |

**Terminals the orchestrator must surface honestly:**

- **Scoped certifying finish** (`audited-chain` / `audited-chain-degraded`) — delta rounds verified the fix chain; say so.
- **One invisible self-recovery** — audit-stall triggers a single fixer escalation (journaled); never offered as an owner menu item.
- **Four-choice stall menu** — `ship-smaller`, `spend-more`, `accept-the-disclosed-risk` (CONFIRMED-only), `hold`.
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

Layer 1 (`run_loop`) is the one-entrypoint loop orchestration with injectable seams;
Layer 2 (`next`/`submit`) is the state machine between orchestrator dispatches. Parity is locked
by the goldens in `test_round_driver.py` and the PARITY receipt in `test_retry_budget_parity.py`.
Treat `round_driver.py` as the contract of record.
