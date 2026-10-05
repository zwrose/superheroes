# Gate receipt — gate-receipt/1

A gate receipt is an optional, structured record that a project's verify command (its local gate) writes about one run. It records what source the run checked, which lanes ran or were skipped and why, the result, and the run's attempt, timing, and machine. Emitting one is optional. A project that emits one uses this format. This file is the format's one home.

# Contents

- [Serialization](#serialization)
- [Fields](#fields)
- [Reading rules](#reading-rules)
- [Versions](#versions)
- [Conformance is not sufficiency](#conformance-is-not-sufficiency)
- [Emitter and reader obligations](#emitter-and-reader-obligations)
- [Example](#example)

## Serialization

A receipt is one JSON object, encoded as UTF-8. Every field is a named top-level field. There is no extensions map. The project chooses where it stores or carries the receipt, such as a file or a pull-request body.

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema` | string | Required | Always `"gate-receipt/1"`. |
| `runId` | string | Required | Identifies the run's own log. It must resolve to that log without reading the receipt, for example a CI run URL or a local run-log path. Opaque to readers. |
| `source` | object | Required | The exact source state the run checked, in one of three shapes. `{"kind": "commit", "id": <commit id>}` when the working tree was clean at that commit. `{"kind": "tree", "id": <tree identity>}` when the tree had uncommitted changes, where the tree identity must never equal a commit id. `{"kind": "unavailable", "reason": <string>}` when the gate could not identify the source. |
| `lanesRun` | array of strings | Required | The lanes that ran. Lane names are opaque strings each project defines. |
| `lanesSkipped` | array of `{"lane": string, "reason": string}` | Required, may be empty | Each lane that did not run, with why. |
| `result` | string | Required | `"pass"`, `"fail"`, or `"error"` (the gate itself could not complete). A project may emit other values. See the reading rules. |
| `attempt` | integer ≥ 1 | Optional | Which run this is for the same source state, counting from 1. |
| `priorRed` | `true`, `false`, or `"unknown"` | Optional | Whether an earlier attempt on the same source state was red. `false` means the history was read and held no red. `"unknown"` means it could not be read. |
| `priorRedTests` | array of strings | Optional | The tests that failed in the earlier red attempt or attempts, each named in the same form as a `testsSkipped` entry's `testFile` (a test file path). |
| `wallTimeMs` | integer ≥ 0 | Optional | The run's wall-clock time in milliseconds. |
| `machine` | string | Optional | Identifies the machine or CI runner that ran the gate. Opaque to readers. |
| `policyVersion` | string | Optional | The version of the project's lane-classification or selection policy the run used. |
| `wouldHaveSkipped` | array of `{"lane": string, "reason": string}` | Optional | In an observation mode that runs everything, the lanes selection would have skipped. |
| `interpreter` | string | Optional | The interpreter or runtime version the run actually executed on. |
| `testsSkipped` | object | Optional | The tests not run, as one of four shapes keyed by `kind`. `{"kind": "inline", "count": <int>, "tests": [{"testFile": string, "reason": string}]}`. `{"kind": "by-reference", "count": <int>, "artifact": <string locating the full list>, "digest": <string>}`. `{"kind": "not-applicable", "reason": string}`. `{"kind": "unavailable", "reason": string}`. In `inline` and `by-reference`, `count` is an integer ≥ 0 equal to the number of skipped tests. In `inline`, `count` equals the number of entries in `tests`, and a mismatch makes the receipt malformed. In `by-reference`, `digest` is the lowercase hex SHA-256 of the full list as the artifact stores it. |

## Reading rules

- A reader is tolerant. It ignores any field it does not know.
- Tolerance never turns into a pass. Only the exact value `"pass"` is a pass. Any other or unrecognized `result` is not.
- An absent optional field means unknown. A reader never treats it as a first attempt, as no earlier red, or as zero, and never fills it in for a measurement. A measurement over receipts counts receipts missing the field as missing.
- A `source` of kind `"unavailable"` attests no source state, even when `result` is `"pass"`.
- A reader that meets a `schema` value other than `"gate-receipt/1"` does not read it as this format. It treats the object as no receipt and says which value it found.
- A value of the wrong type in a known field, or a value outside its stated bound or rule (for example an `attempt` of 0, or an `inline` count that disagrees with `tests`), makes the receipt malformed. The reader treats it as no receipt and says which field.
- An emitter never gives a `tree` source an id that equals a commit id. A reader that finds the two equal treats the `source` as malformed.

## Versions

The version number belongs to this format. Adding a new optional field is additive and keeps `gate-receipt/1`. A change that removes a field, renames one, changes a type, or makes an optional field required is a new version.

A project never mints its own `gate-receipt/N`. It adds project-specific fields as extra top-level fields under the current version. A project-specific field must not reuse a name this table defines with a different shape.

## Conformance is not sufficiency

A receipt that follows this format is well-formed. That does not mean it grounds a claim. Whether a receipt grounds a "the gate passed" claim is the reading project's policy.

The policy names which optional fields it requires and checks the receipt against the change. For example, it checks that `runId` resolves to a run that wrote this receipt, and that `source` matches the commit being handed back. Under that policy, a receipt missing a required field, or failing one of those checks, grounds nothing.

What a receipt proves about tests is the question of `rubric/test-receipt-evidence.md`, not of this file.

## Emitter and reader obligations

- The gate run writes the receipt itself. A person never types one.
- An emitter fills `attempt` and `priorRed` from its own run history for that source state.
- An emitter that cannot determine a field omits it, or uses the field's own "unknown" or "unavailable" shape. It never guesses.
- A project adopting this format states in its own configuration or docs which optional fields its policy requires.

## Example

```json
{
  "schema": "gate-receipt/1",
  "runId": "https://ci.example.test/runs/4821",
  "source": {"kind": "commit", "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
  "lanesRun": ["unit", "lint"],
  "lanesSkipped": [{"lane": "browser", "reason": "no browser files changed"}],
  "result": "pass",
  "attempt": 2,
  "priorRed": true,
  "priorRedTests": ["tests/test_parse.py"],
  "wallTimeMs": 41250,
  "machine": "runner-07",
  "mode": "full"
}
```

The `mode` field is project-specific. Readers ignore it.
