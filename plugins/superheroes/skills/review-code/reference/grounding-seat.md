## Contents

Live-dispatched grounding seat on the review-code compile leg (#609).

- [Invariant](#invariant)
- [Where it runs](#where-it-runs)
- [Staging contract](#staging-contract)
- [Vendor paths and reachability](#vendor-paths-and-reachability)
- [Dispatched seat output](#dispatched-seat-output)
- [Fail-closed gate](#fail-closed-gate)
- [Orchestrator mints findings](#orchestrator-mints-findings)
- [The claims projection](#the-claims-projection)
- [Retained inline check (second leg)](#retained-inline-check-second-leg)
- [Seat-map vendor](#seat-map-vendor)
- [Known limitation — auto-fix loop path](#known-limitation--auto-fix-loop-path)

`$ROOT_DIR` is `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`. Fail-closed rules live in
`lib/grounding_stage.py` — do not judge reachability yourself and do not reimplement them
here or in a second script.

## Invariant

**No grounding result can be trusted without the staged input having been proven read.**

Citing `SUPERHEROES_PR_BODY.md` in `investigated` does **not** satisfy the "did this seat
read the repository" floor — the body is a generated artifact inside the sanitized view, and
a payload with no accepted investigation is a forfeit.

The stage token must **never** appear in an order file, a prompt, or any orchestrator-authored
prose: the seat's only lawful source for it is the staged body inside the view.

## Where it runs

On the **read-only paths** (`--post`, `--review-only`), inside `## Compile + Dedupe`
(SKILL.md §4 step 8). Sequence: **stage → check → dispatch → fold → attest → retained
inline check**.

Branch mode has no PR body — skip staging and both grounding legs.

## Staging contract

| Path | Writer | Purpose |
| ---- | ------ | ------- |
| `$SESSION_DIR/grounding/pr-body.md` | `grounding_stage.py stage` | Nonce-fenced PR body the seat reads |
| `$SESSION_DIR/grounding/stage.json` | `grounding_stage.py stage` | Manifest: stage token, claim enumeration, region map, source-body hash |

The `stage` command:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/grounding_stage.py" stage --session-dir "$SESSION_DIR"
```

## Vendor paths and reachability

An **engine** seat reads `SUPERHEROES_PR_BODY.md` relative to its working directory (the
sanitized view root), materialized by
`dispatch-review --pr-body-path <file> --session-dir "$SESSION_DIR"`; **those two flags are
an inseparable pair — supplying one without the other is refused.** A **native host** seat
reads the absolute `<session>/grounding/pr-body.md` named in its order. Any other vendor
path refuses `stage-unreachable-for-vendor`. Both verbs take `--vendor-path {engine,native}`
and pass it to the same chokepoint validator.

Branch mode has no PR body — skip staging and both grounding legs.

## Dispatched seat output

The seat emits `verdicts` (`--expected-result-kind verdicts`): one row per `repo`-verifiable
`claimId` with `verdict` ∈ `CONFIRMED`/`PLAUSIBLE`/`REFUTED` and a non-empty `reason`;
plus exactly one reserved row `id = "stage-token:<token>"` echoing the token read from the
staged file, also with a non-empty `reason`. A clean run is therefore a **non-empty**
payload — that is what makes the read-proof possible. Rule `PLAUSIBLE`, never `CONFIRMED`,
for anything the seat cannot settle from the repository it can see.

## Fail-closed gate

`check` before dispatch, `attest` on the folded result. **Every** refusal is the one shape
`{"ok": false, "signal": "cannot-certify", "reason": "<token>"}` with exit 1, and the
orchestrator **halts**; it never proceeds. This is the exact fail-direction a review
Critical protected when an earlier unstaged version of the seat was reverted: a sandboxed
seat with no PR-body access would have certified self-claims it could not read.

`plausible[]` is **disclosure-bearing**, not a silent pass: the orchestrator must surface
a non-empty `plausible[]` in the review's disclosures. An **all-`PLAUSIBLE`** result over
a non-empty claim set is a seat that settled nothing and must be reported as such — not read
as clean.

`check`:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/grounding_stage.py" check --session-dir "$SESSION_DIR" --vendor-path <engine|native>
```

`attest`:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/grounding_stage.py" attest \
  --session-dir "$SESSION_DIR" \
  --vendor-path <engine|native> \
  --result-path "$SESSION_DIR/round-<N>/landing/<phase>/grounding-seat.a<K>.json"
```

The folded seat result must land under the session directory — write it to the landing path
the orchestrator uses (`$SESSION_DIR/round-<N>/landing/<phase>/<seat>.a<K>.json`) so
`attest-result-outside-session` cannot fire.

## Orchestrator mints findings

Each `REFUTED` `repo`-verifiable claim becomes one **Important** finding cited at the PR
body, `tradeoff: true`, author-resolved. The seat emits verdicts; the orchestrator mints
findings.

## The claims projection

The orchestrator composes the seat's order from `claimId`, `kind` and `verifiability`
**only**. Claim **text is never interpolated into the order**; it lives only inside the
nonce-fenced staged body the seat reads. Order prose is trusted context, and
author-controlled text placed there is an injection surface.

## Retained inline check (second leg)

Retained **deliberately**, not retired by #609. It runs after the seat and covers
`external`-verifiability claims a sandboxed seat cannot settle (is a `deferred` row's
`#NNN` really filed; does a "verify passed" artifact exist), and it continues to enforce
the DoD table, the `build-record` / `degradations` markers and the omission floor
(CONVENTIONS §10.7). Retirement is a later decision, not this change's.

## Seat-map vendor

The seat runs on `$SEAT_MAP.seats["grounding-seat"]`, composed by `lib/seat_map.py` and
chosen independent of both author (code) and narrative (PR text) families. #609 changes
nothing about seat-map composition.

## Known limitation — auto-fix loop path

The driver-owned auto-fix loop does **not** run SKILL step 8 today; the PR-body honesty
check has never had a `round_driver` phase, so on that path the grounding seat does **not**
influence certification. This gap is **pre-existing and inherited, not introduced by
#609** — do not imply loop-path coverage that does not exist.
