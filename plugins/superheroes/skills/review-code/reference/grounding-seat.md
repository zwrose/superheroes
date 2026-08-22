## Contents

- [Invariant](#invariant)
- [Where it runs](#where-it-runs)
- [Staging contract](#staging-contract)
- [Reachability](#reachability)
- [Dispatched seat output](#dispatched-seat-output)
- [Fail-closed gate](#fail-closed-gate)
- [Orchestrator mints findings](#orchestrator-mints-findings)
- [Retained inline check (second leg)](#retained-inline-check-second-leg)
- [Seat-map vendor](#seat-map-vendor)
- [Known limitation — auto-fix loop path](#known-limitation--auto-fix-loop-path)

---

# Grounding seat — review-code contract (#609)

The **grounding seat** checks the PR's **self-claims** against what the sanitized review
view can actually show. It is **not** one of the five risk-domain lenses; it adds no risk
lens and does not hunt for new code defects. On the code leg it is **really dispatched**
under **#609** (the seat map itself shipped under #510).

## Invariant

> **No grounding result can be trusted without the staged input having been proven read.**

Every refusal path is fail-closed. A seat that cannot read the staged PR body, or that
`grounding_stage` cannot certify, means the review **cannot certify** — never a silent
pass. Citing `SUPERHEROES_PR_BODY.md` in `investigated` does **not** satisfy the
"did this seat read the repository" floor; the body is a **generated artifact** inside
the sanitized view.

## Where it runs

On the **read-only paths** (`--post`, `--review-only`), inside `## Compile + Dedupe`
(**SKILL.md** §4 step 8) — the same placement as the former orchestrator-inline
PR-body honesty check. The orchestrator runs staging, `check`, dispatch, fold, `attest`,
then the retained inline check.

On the **auto-fix loop**, compile is driver-owned and **does not run step 8 today** — the
PR-body honesty check has never had a `round_driver` phase. The dispatched grounding seat
therefore does **not** yet influence certification on that path. That gap is **pre-existing
and inherited**, not introduced by #609; it is recorded as a follow-up.

## Staging contract

The grounding_stage helper (verbs `stage`, `check`, `attest`; module at
`$ROOT_DIR/lib/grounding_stage.py` in the commands below) writes the PR body and an
enumerated claims manifest under `<session-dir>/grounding/`:

| Path | Writer | Purpose |
| --- | --- | --- |
| `$SESSION_DIR/grounding/pr-body.md` | `grounding_stage stage` | Staged PR body the seat must read |
| `$SESSION_DIR/grounding/stage.json` | `grounding_stage stage` | Schema `grounding-stage/1` manifest |

The manifest records per-file `sha256`, a `regions[]` list (each `present: true|false`),
a `claims[]` list (each with a stable `claimId` and `verifiability: "repo"|"external"`),
and a `stageToken`.

**Stage** (orchestrator, PR mode, before dispatch):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/grounding_stage.py" stage \
  --session-dir "$SESSION_DIR" \
  --pr-body "$(jq -r .body "$SESSION_DIR/pr.json")"
```

## Reachability

`dispatch-review --pr-body-path <file>` materializes the staged body **inside the
sanitized view** as `SUPERHEROES_PR_BODY.md` at the view root — the same mechanism that
already stages `SUPERHEROES_REVIEW_DIFF.patch`. The seat reads it **relative to its own
working directory** (the sanitized view root), not from a `/tmp` session path the sandbox
cannot see.

Branch mode has no PR body — skip staging and both grounding legs.

## Dispatched seat output

The dispatched seat emits **`verdicts`**, not findings (`--expected-result-kind verdicts`):

- One row per `repo`-verifiable claim from the manifest: `id` = the `claimId`,
  `verdict` ∈ `CONFIRMED` / `PLAUSIBLE` / `REFUTED`, plus a non-empty `reason`.
- One **reserved** row: `id` = `stage-token:<token>`, where `<token>` is readable **only**
  from inside the staged body file (`SUPERHEROES_PR_BODY.md`). A clean run is therefore a
  **non-empty** payload — which is what makes the read-proof possible.

Rule **`PLAUSIBLE` — never `CONFIRMED`** — for a claim you cannot settle from the
repository you can see. **Never claim a run you did not make** (base rubric).

**Check** (orchestrator, immediately before dispatch):

```bash
python3 -B "$ROOT_DIR/lib/grounding_stage.py" check --session-dir "$SESSION_DIR"
```

Dispatch the grounding seat through `$SEAT_MAP.seats["grounding-seat"]` per
`skills/review-code/reference/auto-fix-loop.md` § Per-seat dispatch + the seat map (#510).

**Attest** (orchestrator, on the folded result):

```bash
python3 -B "$ROOT_DIR/lib/grounding_stage.py" attest \
  --session-dir "$SESSION_DIR" \
  --result-path "$SESSION_DIR/round-<round>/landing/<phase>/grounding-seat.a<K>.json"
```

## Fail-closed gate

`grounding_stage check` runs immediately before dispatch; `grounding_stage attest` runs on
the folded result. Either refusing — and **every** refusal is the single shape
`{"ok": false, "signal": "cannot-certify", ...}`, exit 1 — means the review **cannot
certify**. The orchestrator must **halt** with `cannot-certify` and **never proceed**. This
is the exact fail-direction a review Critical protected when an earlier, unstaged version
of this seat was reverted: a sandboxed seat with no PR-body access would have certified
self-claims it could not read.

## Orchestrator mints findings

The seat emits **verdicts**, not findings. Each `REFUTED` `repo`-verifiable claim becomes
one **Important** finding cited at the PR body, `tradeoff: true`, author-resolved — the
same shape and insertion point as the existing inline check's finding. The orchestrator
mints these during compile; the seat does not.

## Retained inline check (second leg)

The orchestrator-inline PR-body honesty check is **retained deliberately** — it is **not**
retired by #609. It runs **after** the dispatched seat and covers `external`-verifiability
claims the sanitized-view seat cannot settle from the repo alone (whether a `deferred` row's
`#NNN` is really filed; whether a "verify passed" artifact exists). It also continues to
enforce the DoD disposition table, `<!-- superheroes:build-record -->` /
`<!-- superheroes:degradations -->` markers, and the omission floor under `## What we're
accepting` (CONVENTIONS §10.7). Retirement of the inline check is a **later decision**,
not this change's.

## Seat-map vendor

The seat runs on its **seat-map-assigned** vendor and model —
`$SEAT_MAP.seats["grounding-seat"]` — composed by `lib/seat_map.py` and chosen to be
independent of both the author (code) and narrative (PR text) families. #609 changes
nothing about seat-map composition.

## Known limitation — auto-fix loop path

The dispatched seat runs where the inline check already runs: the orchestrator's compile
step (**SKILL.md** §4 step 8). The **driver-owned auto-fix loop does not run step 8
today** — the PR-body honesty check has never had a `round_driver` phase — so on that path
the grounding seat does **not** yet influence certification. That gap is **pre-existing and
inherited, not introduced here**, and is recorded as a follow-up. Do not imply loop-path
coverage that does not exist.
