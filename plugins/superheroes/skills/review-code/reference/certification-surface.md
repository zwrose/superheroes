# Contents

- [Artifacts](#artifacts)
- [Receipt required keys](#receipt-required-keys)
- [Refusal classes](#refusal-classes)
- [Execution-evidence field set](#execution-evidence-field-set)
- [Seat provenance and certification shape](#seat-provenance-and-certification-shape)
- [Import boundary](#import-boundary)

# Certification writer surface

Live declaration of `round_certification.certify` — the journal-backed writer that produces the
certification artifact at terminal. The writer's only input is on-disk session state; it does not
import the round driver.

## Artifacts

The driver calls `certify(session_dir)` and atomically writes one file beside `round-receipt.json`
in the session directory:

| Outcome | Filename | Producer |
| --- | --- | --- |
| Success | `certification-receipt.json` | `certify` returns `(receipt, None)` |
| Refusal | `certification-refusal.json` | `certify` returns `(None, refusal)` |

If `certify` raises or returns neither shape, the driver still writes `certification-refusal.json`,
mapping internal faults to `unfetched-findings` with `bindingFailure: "writer-exception"` or
`"writer-empty"` — never a success artifact the writer did not return.

On the library `run_loop` path, the same `certify` call is the return value. When certification
refuses, `run_loop` also attaches `loopTerminal`, `loopCertificationShape`, and `loopRounds` for
loop observability. Those fields are not written to `certification-refusal.json` on the CLI path.

## Receipt required keys

A successful certification receipt (`_build_receipt`) carries at minimum:

| Key | Carries |
| --- | --- |
| `schemaVersion` | State schema version (2–5 supported; defaults to 2 when absent or invalid) |
| `verdict` | Loop terminal verdict (`converged`, `halted`, `held`, `stalled`, `cannot-certify`, `capped-with-open-critical`, `capped-with-open-blocker`, `uncertified-manual`) |
| `certificationShape` | Writer override — see certification-shape rule below |
| `certification` | Loop state's `certification` block |
| `rounds` | Per-round projection with disclosure channels via `receipt_disclosures` |
| `findings` | Projected findings with dispositions and disposition proofs |
| `decisions` | Loop decision log |
| `seatMap` | Union projection from seat-map receipts |
| `scriptRan` | Journal summary (`invocations`, `byPhase`) |
| `degraded` | Degraded-prose lines from `build_degraded_prose` |
| `skippedBlockers` | Owner-skipped judgment blockers (required, possibly empty) |
| `baseGuard` | `"checked-stat-bound"` or `"not-checked"` |
| `terminalState` | `certified`, `cap`, or `cannot-certify` |
| `terminalCause` | `null` when certified; otherwise `{kind, reason}` from the terminal-cause table |
| `seats` | Per collected seat: `seat`, `phase`, `round`, `attempt`, `provenance` |
| `disclosures` | `{importantOutOfScope: [...]}` — Important findings with valid out-of-scope follow-up |
| `provenanceLabels` | `{derived: [...], makerAuthored: [...]}` naming which keys are journal-derived |

Optional keys when present in state: `base` (pinned-base metadata), `policyApplied`.

Fields added at terminal relative to `round-receipt.json`: `terminalState`, `terminalCause`,
`seats`, `disclosures`, `provenanceLabels`. The writer receipt is otherwise a superset of the
driver receipt except `certificationShape` when any seat is hand-landed.

## Refusal classes

Four escape classes (`REFUSAL_CLASSES`). Each refusal is `{class, artifact, detail, bindingFailure?}`.

| Class | Refuses on | Artifact names |
| --- | --- | --- |
| `unrun-review` | A dispatch-observed or hand-landed seat lacks qualifying execution telemetry on the certified head | Seat key or envelope path |
| `same-family-seat` | The seat map records same-family degradation, or registry lookup finds an undeclared seat in the maker's model family | First offending seat key |
| `unfetched-findings` | Journal seat never closed; envelope missing or unreadable; journal/envelope hash disagreement; unreadable session/journal/state; orchestrator-fulfilled provenance on receipt | Path, seat key, or state file |
| `disposition-without-receipt` | Base guard did not run; finding lacks disposition; fixed/refuted/out-of-scope disposition lacks required proof on certified head; Critical out-of-scope | Finding id or `loop-state.json` |

### Writer fault (non-escape)

`writer-fault` is **not** an escape class. It appears only on the `run_loop` return path when
`certify` raises or returns neither receipt nor refusal. Shape:
`{class: "writer-fault", artifact, detail, bindingFailure, loopTerminal?, ...}`. It is kept apart
from the four escape classes so misses-log escape accounting stays trustworthy.

## Execution-evidence field set

Declared once in this module:

**Binding fields** (`EXECUTION_EVIDENCE_BINDING_FIELDS`): `source`, `runnerNonce`, `recordDigest`,
`resultDigest`, `resultKind`.

**Observation fields** (`EXECUTION_EVIDENCE_OBSERVATION_FIELDS`): `tokens`, `toolCalls`,
`stdoutBytes`, `wallSeconds`, `source`, `read`, `telemetry`.

**Closed value sets:**

- `read`: `engaged`, `unknown` (`EXECUTION_EVIDENCE_READ_VALUES`)
- `telemetry`: `tool-calls`, `none` (`EXECUTION_EVIDENCE_TELEMETRY_VALUES`)

Journal `recorded` rows and landed `seat-result/2` envelopes both carry an `executionEvidence`
block validated against these same constants — `_journal_execution_binding` reads binding fields
from the journal row; `_observation_qualifies` and `_hand_landed_evidence_qualifies` validate
envelope evidence against the same binding and observation rules.

## Seat provenance and certification shape

**Provenance values** a seat may carry (`SEAT_PROVENANCE`):

| Value | On certification receipt |
| --- | --- |
| `dispatch-observed` | Yes — requires qualifying execution telemetry |
| `hand-landed` | Yes — requires envelope `executionEvidence` binding |
| `orchestrator-fulfilled` | Collected internally; refused as unmappable on the receipt |

**Certification-shape rule** (`_certification_shape`): if **any** collected seat has
`provenance: hand-landed`, the receipt's `certificationShape` is `audited-chain` — never
`full-panel-confirmed`, and any `full-panel*` shape in loop state is downgraded the same way.
Otherwise the shape follows loop state's `certification.shape`.

## Import boundary

**Must not import:** `round_driver` (or any driver state-machine module). The writer reads only
`loop-state.json`, `driver-journal.jsonl`, `driver-journal-fault.jsonl`, `meta.json`, and per-seat
envelope files under `round-N/seats/`.

**Imports instead:**

| Module | Role |
| --- | --- |
| `receipt_disclosures` | Disclosure vocabulary, degraded prose, certification-shape inputs |
| `record_paths` | `storage_key`, `store_path` for envelope paths |
| `seat_map_receipts` | Seat-map union projection on the receipt |
| `model_registry` | Maker/seat family resolution |
| `session_mode` | Mode resolution for optional `base.mode` |
