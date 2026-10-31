# Contents

- [The one entrypoint](#the-one-entrypoint)
- [next / submit protocol](#next--submit-protocol)
- [checkpoint](#checkpoint)
- [break-it-change](#break-it-change)
- [Durable-record path](#durable-record-path)
- [Base guard](#base-guard)
- [Batch concurrency — an independent batch goes out together](#batch-concurrency--an-independent-batch-goes-out-together)
- [Round economy](#round-economy)
- [Rounds, the cap and handback](#rounds-the-cap-and-handback)
- [The extra audit round](#the-extra-audit-round)
- [Lens coverage beside counts](#lens-coverage-beside-counts)
- [Dispositions](#dispositions)
- [Actions and payloads](#actions-and-payloads)
- [The re-dispatch carry](#the-re-dispatch-carry)
- [Transition — plugin versions under a live session](#transition--plugin-versions-under-a-live-session)
- [Session repair](#session-repair)
- [Journal and receipt](#journal-and-receipt)
- [Certification shapes](#certification-shapes)
- [Invariants](#invariants)
- [Port note](#port-note)

`lib/round_driver.py` is the **one entrypoint** for the review-code auto-fix loop. It
collapses the old `code_loop_plan.py` plan/record/decide choreography, the manual circuit-breaker
call, and the head-diff derivation into a single `next`/`submit` state machine the orchestrator
obeys. `$ROOT_DIR` is `${CLAUDE_PLUGIN_ROOT}`.

## The one entrypoint

Round 1 is a full `reviewer-deep` baseline panel, except for a returning pull request (next
paragraph). Rounds 2+ are **delta rounds**, and only
that: the [fix auditor](../../../rubric/glossary.md#fix-auditor) over each just-fixed finding plus the
[scoped finder](../../../rubric/glossary.md#scoped-finder) over the code the fixes touched. No later
round runs a full panel, and no separate pass runs on the final commit: a converged review that
needed fixes ends on a round's audit and scoped finder. When the driver cannot work out what the
fixes changed (the **fix surface is unknown**), it does not run a panel to cover the gap: it hands
the PR back with its findings still open, decision kind `fix-surface-unknown`. On
the **auto-fix loop**, the orchestrator never plans, records, or decides continuation by eye — it
calls `next`, dispatches the emitted order, and `submit`s the artifact.

A **returning pull request** gets a different round 1. When a fresh PR-mode session holds an earlier
record (`earlier-findings.json`) and the returning-review decider (`lib/returning_review.py`) answers
`changed` on it, round 1 is a **returning round**: no panel, and the scoped finder reads only what
changed since the last reviewed commit (round kind `returning`). Every other fresh session — no earlier
record, a `full` answer, a decision that could not be made, a surface the driver cannot work out — runs
round 1 as above. The first `next` takes the decision once and stores it as the config's `returning`; a
later `next` never takes it again. Round 1's record carries it as `returning`: `read`, `lastReviewed`,
`countable`, `newAreas`, `why`. A proven copy is in no input of a returning round. A catch-up that
touched a file the PR also changes reads no changed file when the PR's own lines in that file did not
change. An earlier record whose only gap was CI pending on its final commit counts as finished once CI
has passed on that commit, or on a head reached from it by catch-up merges only.

An **empty returning round** — the change since the last reviewed commit is a catch-up merge or proven
copies only, with no carried finding due an audit — converges with no reviewer run (`scopedFinder:
skipped-empty-surface`). Its record carries the earlier record's covering reviewers, each marked
`carried` with the commit it read, and says no reviewer ran in this round. That holds only when the
writer, reading git itself, finds nothing changed since that commit and the earlier record is a finished,
not abandoned review whose findings all have an outcome (see `review-record.md`); otherwise the record
write refuses `review-session-unsupported`.

Every round from 2 on records its `focus` on its round record: `{"on": "fixes", "fixes": [<finding
keys of the previous round's fix batch>]}`. Round 1 records no `focus`. A review record from an
earlier version may list a wider round with its reason; the driver no longer writes one.

Single-vendor environments stay **on** the mandated path: the same driver, the same journal, and,
when no live vendor sits outside the makers' families, a fix whose audit does not
run (it is never counted as audited) with `independence: "degraded"` on the terminal certification
shape — never a silent off-ramp.

## next / submit protocol

Write each call as one line with the real paths — `SKILL.md` § Auto-Fix Loop.

Fresh state (first `next` of a session; it carries `--verify-command`, so the hook leaves it to the normal permission check by design):

```bash
python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir> --diff-path <session dir>/round-1/diff.txt --verify-command '<verify command, or none>' --max-rounds 4
```

`--max-rounds N` accepts 1 to 4 on a fresh session; any other value is refused `max-rounds-invalid` (§ Rounds, the cap and handback).

`--break-it-interpreter <text>` (config `breakItInterpreter`; fresh-state only, refused `break-it-interpreter-not-fresh-state` otherwise) is the launcher the session's break-it tests run under. The value, an empty string included, is stored as the session's `breakItInterpreter`; setup passes it only when calibration sets the key (`skills/review-code/reference/setup.md`).

`--copy-proof <path>` (config `copyProof`; fresh-state only, refused `copy-proof-not-fresh-state` otherwise) names a checksum proof of files the change copies byte for byte from a named source: `{"schema": "copy-proof/1", "copies": [{"file", "source", "sha256"}]}`, with `sha256` the hash of the file's bytes at the reviewed head. Take the checksum from the named source's bytes: a copy is a byte-for-byte copy of its source, so the source's sha256 is the copy's, and the advisor's vet compares it with the source ([the review record checks](../../showrunner/reference/vet-receipt.md#the-review-record-checks)). A proof file that does not read, parse or fit that shape is refused `copy-proof-invalid` with the fault in `detail`, never taken as no proof. The proof is checked once, when the session starts: a copy is proven only when its file is in the change, is not deleted, is a regular file at the head whose blob the diff section names, and has the proof's checksum. A proven copy is left out of the diff every seat is given (`round-<N>/reviewer-diff.txt` and `reviewer-head.diff`, written beside `diff.txt` and `head.diff` only when a copy is left out; the round's `diff.txt` and `head.diff` keep the whole diff), out of the engine reviewer's patch (the session's `reviewer-leave-out.json`, which the recipe passes as `--leave-out-file`), and out of the test role's risk-area clause, and it is listed in the review record. A copy the proof does not cover or whose content does not match stays in every diff and counts. A copy whose diff section changes in a later round is given back to the seats and no longer listed. Proven copies are not countable lines.

`--fix-batch-cap N` (config `fixBatchCap`, default `round_phases.FIX_BATCH_CAP_DEFAULT` (stated once in § Round economy), a positive integer; fresh-state only, refused `fix-batch-cap-invalid` otherwise) is the most findings one `apply-fixes` step carries — § Round economy states the split.

`--earlier-findings <path>` (fresh-state only, like `--prior-comments`; PR mode) names the JSON that `python3 -B <plugin root>/lib/review_record.py read --pr <N>` prints, so synthesis can mark a finding that repeats one of the PR's earlier findings (§ Actions and payloads, `dispatch-synthesis`). The file reads three ways. `{"ok": true, "findings": [...], "finalCommit": {"sha": ...}, ...}` supplies the record's findings as earlier findings, each judged on an unknown commit (a record finding names none); an unknown commit counts as changed code, so the no-change branch of `synthesis-pass.md` § Repeats cannot apply to them, and a repeat of one closed as wrong takes the verifier's fresh grade. `{"ok": false, "reason": "review-record-missing", ...}` means the PR has no earlier record: there are no record findings and nothing is disclosed. A missing file, JSON that does not parse, or any other refusal supplies no record findings, and the round record discloses `earlierFindingsUnavailable` with the reason. A session started without the flag discloses `earlierFindingsUnavailable` with reason `not-supplied`; its repeats are matched by exact identity against its own earlier rounds only.

Every step thereafter:

```bash
python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir>
```

`--diff-path` belongs only on the first `next` of a session. A continuation
`next` that passes it is refused with `diff-path-not-fresh-state` — check raw stdout and the
driver journal; the driver does not crash.

**Why session-birth only.** The first `next` binds the round-1 diff artifact into session state
(`config.diff`, `reviewedDiff`, and the base-guard stat binding). Rounds 2+ regenerate the diff
from the shell per `SKILL.md` Setup; the driver refuses a later `--diff-path` because swapping the
round-1 artifact mid-session would break the pin/stat contract the base guard stamped at birth.
Same discipline as `--vendors` on non-fresh state.

**`--seat-map <path>`** carries the seat map into round 1 and is subject to that same
fresh-state discipline. The file must be a JSON **object** shaped `{"seats": {"<dimension>":
{"vendor": "...", "model": "...", "engine": "..."}}}`, keyed by the full reviewer dimension names —
an unreadable file, malformed JSON, or a non-object all fail loud with `seat-map-unparseable`,
never a silent fall-through. It is what lets round 1 resolve each seat's vendor: the panel artifact
that otherwise supplies the seat map does not exist until the panel has already been dispatched.
See § Emitted orders for what an unsupplied map does to each seat's output contract.

After fulfilling the emitted action, fold the artifact:

```bash
python3 -B <plugin root>/lib/round_driver.py submit --session-dir <session dir> --phase "<phase from next>" --attempt <attempt from next> --state-hash "<expectedStateHash from next>" --artifact "<session dir>/round-<N>/<phase>-artifact.json"
```

**Freshness / idempotence echo.** Each `next` returns `expectedStateHash` (a SHA-256 over canonical
`loop-state.json`). `submit` must echo `phase`, `attempt`, and `state-hash` exactly — a stale or
forked submit is rejected `{ok: false}`. A second `next` before `submit` returns the same pending
step and hash again. An exact duplicate `submit` (same phase/attempt/artifact) returns
`{ok: true, duplicate: true}`.

Persist state under `$SESSION_DIR/loop-state.json`. Append every `next`/`submit` to
`$SESSION_DIR/driver-journal.jsonl` (the `scriptRan` evidence). On `terminal`, the driver writes
`$SESSION_DIR/round-receipt.json` — validate with `round_driver.validate_receipt`.

## checkpoint

Orchestrator-invoked verb at a **non-terminal** stop — like `next`, `submit`, and `advance`, the
driver does not observe tripwire doctrine itself; the orchestrator decides the stop and calls
`checkpoint`.

```bash
python3 -B <plugin root>/lib/round_driver.py checkpoint --session-dir <session dir> --stop-reason <tripwire or park>
```

`--stop-reason` is required; the only accepted values are `tripwire` and `park`
(`CHECKPOINT_STOP_REASONS`).

**What it writes.** An interim `round-receipt-interim.json` built by `build_interim_receipt`: it starts from
`build_receipt` (journal-derived `rounds`, `findings`, `decisions`, `seatMap`, `scriptRan`,
`degraded`, `skippedBlockers` — including **per-pass verdict totals** on each round as
`rounds[].verifyPasses`), then strips terminal-only keys (`certification`, `certificationShape`,
`schemaVersion`, `verdict`), sets `schema` to `receipt-interim/1`, and adds a `stop` block
(`reason`, `writtenAt`). `_validate_interim_receipt` enforces that interim receipts carry **no**
`certification`, `certificationShape`, `verdict`, or `attestation` — an interim is not a
certification.

**Which stops invoke it.** Call `checkpoint` when the orchestrator parks at a non-terminal stop
with `--stop-reason` matching the stop: **tripwire** (third-rework tripwire) or **park** (the
orchestrator parks before the review can continue). Once the hold fold has set `terminal = "held"` (a
session state the driver no longer writes), `checkpoint` refuses (`checkpoint-session-terminal`) and
the terminal `round-receipt.json` (full `rounds` record, `verdict: "held"`) is the record from then on.
The same holds for any terminal verdict, `handed-back` included. These are orchestrator doctrine; the
driver only validates the reason against `CHECKPOINT_STOP_REASONS`.

**Terminal receipt preserved.** `cmd_checkpoint` refuses when the session is already terminal
(`checkpoint-session-terminal`) or when a **terminal** certified/attested receipt sits on disk
(`checkpoint-terminal-receipt-exists`). Re-invoking `checkpoint` after an earlier interim receipt is
allowed — each write supersedes the previous interim. The write-once rule applies only to terminal
receipts, not interim supersession.

**Not handback evidence.** An interim receipt is progress evidence for the operator, not valid
handback.

## break-it-change

The build session's only edit to a reviewer's break-it test: when the test cannot run as written for
a reason inside the test itself that a small change fixes, such as a compile, syntax or type error,
the session changes it through this verb and says why.

```bash
python3 -B <plugin root>/lib/round_driver.py break-it-change --session-dir <session dir> --finding <id> --content-file <value> --why <value>
```

The verb is accepted only while the round waits on the verifiers (the pending action is
`dispatch-verifiers`). The path and the run command stay the reviewer's; only the test's content
changes. On success it returns `{"ok": true, "finding": <id>, "run": <the new run record>}`. The new
run is the changed test run again in the working copy, and the second record carries the reason in
its `changedWhy` field. The verb rewrites the finding's `suggestion` block with the changed content
(same `path` and `run`), so the changed test is the one the build session writes and commits at `apply-fixes` and the kept
check reads. It clears the pending verifier dispatch, so the next `next` re-emits the verifier
orders at a fresh attempt carrying the changed test and both runs; a verifier result for the
superseded attempt is refused.

Each refusal is `{"ok": false, "reason": <token>}`:

- `break-it-change-not-at-verifiers`: the pending action is not `dispatch-verifiers`.
- `break-it-change-finding-unknown`: `--finding` names no staged finding.
- `break-it-change-no-test`: the finding carries no break-it test the driver ran.
- `break-it-change-why-missing`: `--why` is absent or blank.
- `break-it-change-content-unreadable`: the content file cannot be read.
- `break-it-change-content-unchanged`: the content equals the test already in the block.

## Durable-record path

Each pending phase folds by **one** of two paths — they are **mutually exclusive, per SESSION**
(the first path a session uses is the path it keeps for every later phase — not a per-phase choice):

- **Hand path** — `submit` folds **the artifact you compile**; it **never reads** the durable
  store.
- **Durable-record path** — `record-result` / `record-missing` write per-seat envelopes into the
  store; **`advance` assembles the phase artifact from those records** and folds it. `record-result`
  **never feeds** `submit`; both **refuse** with `record-submit-interleaved` once the session has
  hand-folded any phase (`_submitUsed`).

Before the record-submit interleave fence existed, a hand `submit` after `record-result --sweep`
ignored every store record and folded the caller's artifact instead — the field failure mode that
motivated this section. **Now** that combination is refused (`record-submit-interleaved` below); the
store records remain on disk and the pending phase is unchanged until you `advance`.

**Hand path** (every phase that accepts a compiled artifact):

```bash
python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir>
# … dispatch seats, compile artifact …
python3 -B <plugin root>/lib/round_driver.py submit --session-dir <session dir> --phase "<phase from next>" --attempt <attempt from next> --state-hash "<expectedStateHash from next>" --artifact "<session dir>/round-<N>/<phase>-artifact.json"
```

**Durable-record path** (panel and other record-capable phases):

```bash
python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir>
# … dispatch seats; each seat lands under landing/ …
python3 -B <plugin root>/lib/round_driver.py record-result --session-dir <session dir> --seat "<seat>" --round <round from next> --phase "<phase from next>"
# or: record-result --sweep with the same --round and --phase
# … record-missing for any slot that forfeit/timeout — echo the same --round and --phase …
# … write <session dir>/round-<N>/landing/<phase>/_dispatch.a<K>.json (seat phases only — run-verify and apply-fixes emit none); shape: Dispatch manifest row
python3 -B <plugin root>/lib/round_driver.py advance --session-dir <session dir>
```

The driver creates `$SESSION_DIR/round-N/landing/<phase>/` before it hands back any seat-dispatch or `run-verify` step, so a seat or a hand-run command never writes into a missing folder.

**Dispatch manifest before `advance`.** On the durable-record path at state v5, `$SESSION_DIR/round-<N>/landing/<phase>/_dispatch.a<K>.json` is **not** a provenance source — `advance` reads it only to disclose `dispatchManifestIgnored`; provenance is the runner record on each stored envelope (`executionEvidence.source`). A finished session of an earlier state version (2–4) never takes `record-result`/`advance` (`legacy-session-use-next-submit`); an unfinished one is refused before any command reads it (`session-from-earlier-version`, see Transition below). **Orchestrator-fulfilled phases** (`run-verify`, `apply-fixes`) emit no manifest.

No `submit` on this path — `advance` echoes `expectedStateHash` itself; do not pass
`--state-hash`. **Orchestrator-fulfilled phases** (`run-verify` and `apply-fixes` — see
`round_adapters.ORCHESTRATOR_FULFILLED_PHASES` / `is_orchestrator_fulfilled`) also fold through
`advance` from the host-seat **bare payload** at
`$SESSION_DIR/round-N/landing/<phase>/<skey>.a<K>.payload.json` (for `apply-fixes`, the step's
`landingPath`) — no orders manifest, no anchor,
validated through the phase's existing submit-shape guard. An accepted fold **writes that slot's
durable `seat-result/1` record in the same commit**, so both fold paths leave the same
reconstructable per-seat provenance. Named refusals:
`orchestrator-payload-missing`, `orchestrator-payload-unreadable`, `landing-ambiguous` (a bare
payload beside a durable seat record — two claims for one slot; the shape guard's fault is reported
first when the payload is also malformed; recover by deleting whichever artifact is not the one you
meant), `bootstrap-required` (no session id in `meta.json` — the record could not carry its session
provenance, so nothing is folded; recover by restoring the session id, which `next` mints), and the
shape guard's own fault. `manifest-anchor-unanchored` stays reserved for seat phases.

**Refusal tokens when paths interleave.** One token can be returned by more than one command — the
token names the seam, not the direction.

| `reason` | condition | recovery |
| --- | --- | --- |
| `advance-submit-interleaved` | a hand `submit` after any `advance` in this session (`_advanceUsed`) | use `advance` |
| `advance-submit-interleaved` | an `advance` after any hand `submit` in this session (`_submitUsed`) | compile and hand-`submit` this phase |
| `record-submit-interleaved` | a `record-result` / `record-missing` after any hand `submit` in this session (`_submitUsed`) | compile and hand-`submit` this phase — **not** `advance` (this session's latch refuses it) |
| `record-submit-interleaved` | a hand `submit` for a phase that already carries durable store records at the pending `(round, phase, attempt)` on a session that has **not** hand-folded yet (**per-attempt** fence — defers when `_submitUsed` is set) | **`advance`** — **except** on a refuse-fold phase (`dispatch-synthesis`, `dispatch-seams-check`, `dispatch-second-test`, `dispatch-scoped-finder`, `run-verify`, `apply-fixes`) whose only store record is a `seat-missing/1` envelope: there `advance` answers `assemble-refused` / `missing-seat-refuse-fold:<seat>`, and the slot must first be replaced via `record-result --supersede --expect-sha256 …` |
| `fold-refused` (`detail: verify-landing-not-driver-written`) | `advance` at `run-verify` over a non-CI landing the driver did not write: hand-written, edited after the driver wrote it, a journal row for another round or attempt, or a journal that cannot be read | run `python3 -B <plugin root>/lib/round_driver.py run-verify --session-dir <session dir>` (remove the hand-written landing first; the verb refuses a filled slot) |
| `round-phase-not-pending` | `record-result` / `record-missing` with `--round` and/or `--phase` that do not match the pending slot | re-read `next` and echo the current `round` and `phase` onto the durable-record command |

**No dead ends.** Whichever fold path a session has committed to, that path's fold command stays
legal for the pending phase: `_submitUsed` → hand `submit`; `_advanceUsed` → `advance`; neither latch
→ `advance` when durable records are present, hand `submit` when they are not. `record-result` /
`record-missing` are legal only on a session that has not hand-folded.

When a hand-path session (`_submitUsed`) still carries durable records at the pending slot from
before the entry-point latch existed, hand `submit` proceeds and journals `record-orphans-ignored`
with the slot label(s) — the records are deliberately ignored, not silently dropped.

**Durable-record artifacts** (round `N`, phase `P`, attempt `K`, storage key `skey`, vendor `vendor`):

| Artifact | Path | Producer / what absence does |
| --- | --- | --- |
| Dispatch manifest | `$SESSION_DIR/round-N/landing/P/_dispatch.aK.json` | **Orchestrator** — never written by the driver. On the durable-record path at state v5 (`seat-result/2`), when every landed envelope is v2 the file is read **only** to disclose `dispatchManifestIgnored` — no vendor is taken from it; provenance is each stored envelope's `executionEvidence.source`. A finished session of an earlier state version (2–4) never reaches `advance` (`legacy-session-use-next-submit`), and an unfinished one is refused before any command reads it (`session-from-earlier-version`). **Where the manifest is still read** — a landed `seat-result/1` envelope on a seat phase — it is top-level JSON keyed by the **exact roster seat key**: on `dispatch-panel` that is the bare dimension name exactly as `payload.dimensions` lists it (`code-reviewer`), **never** the storage key `skey` (`<seat>-<hash>`); on `dispatch-audits` it is `payload.targets[].id`, verbatim (row below). `advance` reads the file on every seat phase; its consumers are `_assemble_panel` (→ `ranManifest`) and `_assemble_audits` (→ `collectionManifest`). A manifest keyed in any other spelling reads as absent for every seat: on the panel `ranManifest` is omitted and every cross-vendor `run` seat is disclosed provenance-missing (`reviewer-fell-open-provenance-unavailable` — two lanes mis-keyed it by storage key on 2026-09-19 and the runner journals were the only record); on audits `collectionManifest` is omitted, so no auditor ruling is authenticated. Each value requires non-empty `vendor` (`model` / `engine` are optional, descriptive, neither validated nor trusted — `round_adapters._trusted_vendors` reads only `vendor`). **Orchestrator-fulfilled phases** (`run-verify`) emit no manifest — `advance` folds from the host bare payload instead. **Absence on a seat phase carrying a `seat-result/1` envelope:** the manifest key is omitted, the adapter discloses `dispatchManifestUnavailable`, and on `dispatch-audits` a clearing ruling (`discharged` / `discharged-but-new-issue`) is **not authenticated** — fails closed to `not-discharged` + `unauthenticated`, which can drive the audit stall. Check this file first on an unexplained fix-audit stall. |
| Seat store | `$SESSION_DIR/round-N/seats/P/skey.aK.json` | **`record-result`** / **`record-missing`** / `advance`'s sweep — the durable `seat-result/1` or `seat-result/2` (state v5) or `seat-missing/1` envelope for one roster slot. **Absence:** the slot is incomplete; `advance` refuses **`incomplete-roster`** until every slot has a store record or a missing envelope. |

## Emitted orders

Every `next` whose `phase` starts with `dispatch-` emits, atomically in one `orders-emit` commit:

- one **order file** per roster slot (`round_orders.render_order` over `rubric/orders/<phase>.md`);
- one **envelope stub** per slot (the schema follows the session's state version: `seat-result/1`
  at state v2–v4, `seat-result/2` at state v5 — header fields knowable at emission: session, round,
  phase, seat, attempt, vendor, model, `dispatchRef`, `orderSha256`, `manifestSha256`, and at v5
  `provenance`; never `recordedAt`, `payloadSha256`, `executionEvidence`, or `envelopeSha256`);
- an **orders manifest** listing every slot's `orderPath`, `envelopeStubPath`, `channel`, and hashes.

Paths (round `N`, phase `P`, attempt `K`, storage key `skey`):

| Artifact | Path |
| --- | --- |
| Order | `$SESSION_DIR/round-N/orders/P/skey.aK.md` |
| Envelope stub | `$SESSION_DIR/round-N/orders/P/skey.aK.envelope.json` |
| Manifest | `$SESSION_DIR/round-N/orders/P/manifest.aK.json` |

**Landing shapes** (`round_records.ingest_landing`):

| Seat kind | Landing path | What the seat writes |
| --- | --- | --- |
| **Engine** (`codex`/`cursor`) | `.../landing/P/skey.aK.json` | **Orchestrator** writes the full seat-result envelope (stub header + payload; schema from state version) from the folded `dispatch-review` stdout result; the engine seat emits JSON on stdout only. **Codex** dispatches run with `--json` for telemetry and return their result as a typed file on `--output-schema`/`-o` that the runner validates against the declared schema; engagement is read from the event stream (`source: "codex-events"`). The findings payload comes from the typed result file, never from stdout or a last-message file. A result that fails validation forfeits with no salvage. A stream that does not parse records `telemetry: "none"`, and a seat whose engagement does not read `engaged` does not qualify. At state v5 the stub carries `provenance: dispatch-observed`; `record-result --evidence-run-dir` may stamp `executionEvidence` and compute `envelopeSha256` before ingest. |
| **Host** (`claude` native subagent) | `.../landing/P/skey.aK.payload.json` | Payload only; driver wraps with the stub at ingest. At state v5 the wrapped envelope is `seat-result/2` with `provenance: dispatch-observed`; when execution evidence is stamped, the bare-payload landing stays single-file and the stamped envelope is written to the durable store copy only. |

Both shapes present → `landing-ambiguous`. The order's landing block names the paths; seats copy
stub header fields verbatim and never recompute hashes.

**Re-emission trap.** A live build lost a debugging cycle to this exact sequence: (1)
a later phase hands the verifiers a new finding; (2) the driver **re-opens an already-folded phase
with a different roster**, rewriting `orders/<phase>/manifest.a0.json` **in place at the same
`attempt: 0`**; (3) the **prior wave's landing files are still on disk** from the first fold; (4)
`record-result --sweep` (`round_records.sweep_landing`) walks the **landing directory**, not the
manifest, so it finds those stale files. It detects **both** landing shapes — a host bare payload
`<skey>.a<K>.payload.json` as well as a full envelope `<skey>.a<K>.json` — and one stray storage
key yields **one** refusal however many shapes it carries on disk. Files that map to no slot in the
*current* roster are hard-refused with **`stale-landing`**; the sweep **ingests and journals every
roster slot's real landing before it refuses**, so recovery converges without hand-moving the good
files: **move only the stray file(s) aside — never delete — and re-run the sweep**. One pass names
**every** stray: the refusal forwards `storageKey` and `landingPaths`, and a `strays` list carries
one entry per stray storage key (each with those same fields). (5) Until that
is done `advance` refuses too, and the phase is left **pending** — a stuck session with no obvious
cause, because the failure reads as a driver bug when it is really a directory-vs-manifest
mismatch. **`unknown-seat`** is a **different** token: an *addressed* seat
(`record-result --seat <key>`) that is not on the current roster — not the sweep's stray-file
refusal; a reader must be able to tell the two apart from this doc alone.

**`record-result --sweep` cannot supersede.** Combining `record-result --sweep` with `--supersede` or
`--expect-sha256` returns the literal refusal **`sweep-supersede-unsupported`**. Supersede is
compare-and-swap and the CAS token is **per-slot**; a sweep that superseded would have to drop the
CAS and blind-overwrite the durable record. Recovery: the refusal's `recovery` list carries a
ready-to-paste per-slot command **only for a slot whose landing CAS token differs from the
stored record** (equal tokens mean the landing is the envelope already stored, as with
`record-missing`; no landing means nothing to supersede). Each command uses the **raw
seat key**, an explicit `--occurrence` (never the `<seat>#<n>` display label), and `--attempt` for
the attempt the refusal was produced for (round and phase are not separately addressable on this
CLI; `--attempt` is the fence). Every `seat-missing/1` envelope shares one CAS token, so an
occurrence-1 supersede with the occurrence omitted would pass CAS against occurrence 0 and replace
the wrong record; a command produced for one attempt and pasted after a retry would likewise pass
CAS against a newer slot unless `--attempt` binds it. When no slot has a landing whose CAS token
differs from the stored record, `recovery` is empty and the refusal still fires on the flags. A stored envelope
with no readable CAS token is listed with `expectSha256` null and no paste-and-run command.

**`seat-result/1` envelope fields** (engine-seat full envelope — the orchestrator writes every field
below when landing a `dispatch-review` stdout result):

| Field | Carries |
| --- | --- |
| `schema` | Literal `seat-result/1` |
| `session` | Session id from `meta.json` |
| `round` | Round number |
| `phase` | Phase name (e.g. `dispatch-panel`) |
| `seat` | Roster seat key |
| `attempt` | Attempt counter for this phase |
| `vendor` | Seat vendor string |
| `model` | Seat model string |
| `dispatchRef` | Dispatch reference id |
| `orderSha256` | SHA-256 of the order file, or `not-emitted` when no emission anchor exists |
| `manifestSha256` | SHA-256 of the orders manifest, or `not-emitted` when no emission anchor exists |
| `recordedAt` | ISO-8601 timestamp when the envelope was stamped |
| `payloadSha256` | SHA-256 over the canonical JSON of `payload`; an envelope **without** this field, or with a hash that does not match `payload`, is refused **`landing-torn`** at ingest |
| `payload` | The seat's artifact (JSON object) |

**`seat-result/2` envelope fields** (state v5 — extends `seat-result/1` with provenance binding and
optional execution evidence; the orchestrator or driver must supply every field below when landing or
ingesting):

| Field | Carries |
| --- | --- |
| `schema` | Literal `seat-result/2` |
| `executionEvidence` | Optional runner telemetry block (`source`, `runnerNonce`, `recordDigest`, `observation`) stamped by `record-result --evidence-run-dir` for `dispatch-observed` seats |
| `provenance` | One of `dispatch-observed`, `hand-landed`, `orchestrator-fulfilled` — required at v2; emission stubs for dispatch phases carry `dispatch-observed`. On `dispatch-audits`, an unenumerated value refuses **`provenance-unknown`**; a landing whose vendor provenance cannot be derived from a runner record refuses **`provenance-underivable`** at `record-result`/sweep (dispatch-observed without minted evidence, hand-landed without `executionEvidence`, or `executionEvidence.source` outside `model_registry.VENDORS`). |
| `envelopeSha256` | SHA-256 over canonical `{"payload": <payload>, "executionEvidence": <evidence-or-null>}`; required at ingest — an absent or mismatched value is refused **`envelope-torn`** |
| `headSha` | Optional; the emission stub carries the head the driver bound into the orders anchor at emission — when present it must equal the anchor's head (refused **`head-anchor-mismatch`**), and an envelope carrying one against an anchor that has none is refused **`head-anchor-unanchored`**. On a `dispatch-observed` seat whose evidence is minted from a runner **review** run, `record-result` stamps `headSha` from the runner view only when the landed envelope omitted it; a seat-declared `headSha` that disagrees with the runner-observed view is refused **`head-anchor-mismatch`** rather than overwritten |
| `citedHeadSource` | One of `runner-view`, `order-anchor` — how the `citedHead` on the journal row was derived; stamped by `envelope_bind_cited_head_source` at ingest and on the two driver sinks that build store-bound envelopes |

All other fields match `seat-result/1`. The emission stub never carries `recordedAt`, `payloadSha256`,
`executionEvidence`, or `envelopeSha256` — the orchestrator stamps `recordedAt` and `payloadSha256`
when landing, and `record-result` computes `envelopeSha256` (and may add `executionEvidence`) at
ingest; when the orders anchor carries a head, the emission stub may carry `headSha` bound to that
anchor.

The **`seat-missing/1`** shape is deliberately different: it records a seat that produced no artifact
and carries **no** `payload` or `payloadSha256` — instead `reason` (one of `forfeit`, `timeout`,
`refusal`, `killed`, `malformed-output`) and optional `evidence`.

**The order's output contract follows the seat's channel** (`round_driver._seat_channel`, the one
home for the choice): an order names a landing path to **write** only when the seat's transport row
carries a vendor positively known to be a host seat, and every other case — an engine vendor, or a
vendor the driver cannot resolve — renders the **stdout** contract instead. The fold is deliberately
asymmetric, because the two mistakes are not: a host seat handed the stdout contract still returns
its payload for the orchestrator to land, while an engine seat handed a write contract forfeits on
the forbidden write. **A vendor the driver DEFAULTED to is not a resolved vendor**: the
reviewer phases (verifiers, seams-check, scoped) take a stand-in vendor when the
engine-preference read cannot answer (a forfeited or unreadable reviewer seat is re-run on a vendor outside every maker family, the driver's choice; when there is none the seat is recorded missing and counts as not run, and it is never re-run on the host model when the host's family is a maker) — `engine_pref.load_engine_prefs` never raises, so that
failure arrives as `refusal_engine_prefs(readError=…)`, and `readError` is what marks it (a
genuinely absent config is `degenerate_engine_prefs()`, whose documented defaults *are* the
configuration). The transport row therefore carries `vendorSource: "configured" | "defaulted"`,
and `_seat_channel` treats a defaulted vendor exactly like an unresolved one — stdout.
Reading a defaulted `claude` as positive host evidence is what handed an engine-dispatched seat the
write contract. Every such fallback is disclosed as `orderVendorProvenanceGaps` (the row carries
`vendorSource` when it has one) — the fold makes the gap safe, not silent. The collector derives
from the **same** predicate the channel folds on, across every `dispatch-review` phase (panel,
verifiers, synthesis, seams-check, audits, scoped), so a channel that fell back for want of vendor
evidence can never do so without a receipt.

**Supply `--seat-map` on the first `next` to keep host seats on the direct-write path.** Round 1 is
the round that dispatches the panel, and before this flag the driver's only vendor source was the
panel artifact — which does not exist yet. Without a seat map, no round-1 seat's vendor resolves, so
**every** panel seat renders the stdout contract and the orchestrator lands each payload itself.
That is correct and safe, merely one hop less direct than a native seat writing its own landing
file.

The manifest and per-order hashes are mirrored into state (`_ordersAnchors`) and journaled as
`orders-emitted`; ingestion checks envelopes against that anchor (`manifest-anchor-mismatch` when
they disagree). The anchor and the hashed manifest also carry the emission head as `headSha`. Every
`recorded` journal row declares how its `citedHead` was derived via `citedHeadSource`. For a seat
whose evidence is minted from a runner **review** run, the cited head is the runner-observed view
head and must equal the emission anchor head — disagreement refuses `view-head-anchor-mismatch` at
record time and stores nothing; an underivable run kind or absent view head refuses
`view-head-underivable`. A **write** run has no sanitized view: the row keeps the emission-anchor
citation and declares `order-anchor`.

**Order-input ownership.** Orders cite round-scoped paths that must exist before a seat can run.
The driver materializes them before order emit (see also the inline comment at
`_emit_orders_for_phase`):

- **Phase sidecars** — written in the `orders-emit` commit and materialized before render from the
  single `_order_sidecar_writes` derivation: `round-<N>/clusters/<i>.json` (verifiers),
  `round-<N>/audit-targets/<skey>.json` (audits), `round-<N>/scoped-hunks.json` (scoped),
  `round-<N>/verified.json` (synthesis).
- **`round-<N>/diff.txt`** — `_ensure_round_diff` when absent or its bytes do not match loop state
  (`reviewedDiff`), via `round_commit.atomic_write_bytes` (atomic tmp+rename) **outside** the
  `orders-emit` commit. The orchestrator still owns the real round diff: produce the bytes with
  `git diff <pinned baseRef>...HEAD` and bind them on the first `next` via `--diff-path` (see
  `setup.md`'s session-artifact table).
- **`round-<N>/head.diff`** — `_ensure_round_head_diff` from state `headDiff` when audits or scoped
  orders render (the driver derives `headDiff` from git at the `apply-fixes` fold, or reads the supplied
  one in a run with no repository; it then materializes the file the audit/scoped order cites).
- **`round-<N>/fix-delta.diff`** — `_ensure_round_fix_delta` from state `_fixDeltaDiff` when the scoped
  order renders (the driver computes the change between the reviewed, pre-fix diff and the post-fix head
  diff when the delta round begins, proven copies left out; it then materializes the file the scoped
  order cites).
- **The `apply-fixes` step's files** — `round-<N>/fix-batch.json` and `round-<N>/fix-guidance.md`
  (`fix-batch.<i>.json` and `fix-guidance.<i>.md` for a later slice), written from state when the
  step is set; the session reads them, and no order is rendered. Each `fix-batch.json` row carries
  `priorAudit {round, ruling, reason}` (the last audit
  ruling on that finding) and `gateRuling {round, disposition, reason}` (the last gate decision the state recorded on that finding, when it holds one),
  derived from the loop record by finding key. `fix-guidance.md` holds the owner or advisor guidance
  for the batch's findings. Loop state is authoritative: do not treat a hand-written copy of either
  file as the batch.

## Base guard

Before any round work, every `next` invocation runs through `lib/review_base_guard.py` at the **CLI
layer** (`next` subcommand), not inside `run_loop`. The library/eval path drives `run_loop` with
scripted seams and no real repo, so a git check there would be meaningless; `review-code` actually
calls `next`, so that is where the invariant is enforced. On refusal the driver prints
`{"ok": false, "reason": ..., "detail": ...}` to stdout, exits **1**, and appends a durable journal
line with `outcome: "refused-base-guard"`.

**Why it exists.** The review diff base used to live only in skill text, and that text drifted. A
live incident put ~6,600 already-merged lines into a review of 2,931 real ones, and an unset
base produced a zero-line diff at exit 0 that the loop certified clean. The text was fixed first;
the invariant then moved into the driver so a future text edit cannot reintroduce it. On fresh state the
guard also stamps `baseGuard` on the receipt path — `"checked-stat-bound"` on this CLI path,
`"not-checked"` on the library/eval path — so a receipt can never silently *look* guarded when it
was not. The stat binding applies to the **round-1** diff artifact the driver receives on fresh
state; rounds 2+ rely on the skill's per-round shell halt for diff integrity.

**Inputs (no new required CLI flag).** The guard reads the session's own records: `$SESSION_DIR/meta.json`
(`mode`, `baseRef`, `baseBranch`, `baseFetch`, `repoRoot`) and, in PR mode, `$SESSION_DIR/pr.json`
(`url`) — both written by the skill's Setup before the first `next`. One optional flag:
`--repo-root` (default: the process cwd), for tests.

On fresh state, resolved values ride into config and may appear in the terminal receipt as an
optional **`base` block** — `baseRef`, `baseFetch`, `mode`, `baseRepo`, `baseRepoCheck`,
`diffBinding` (`file-set+line-counts` when per-file stat binding succeeded, or `line-counts-only`
when git-quoted paths or an unresolvable `--numstat` path column forced a global-totals fallback). Terminal `certification.base` is tri-state:
`fetched` (CLI guard ran with a healthy `baseFetch`), `degraded` (fetch provenance unknown or
failed), or `not-checked` (library/eval `run_loop` — guard did not run). `validate_receipt`
**accepts but does not require** the `base` block, like the existing per-round `auditProvenance`
field.

**Refusal reasons.**

| `reason` | condition |
| --- | --- |
| `base-meta-unreadable` | `$SESSION_DIR/meta.json` missing / unparseable / not a JSON object |
| `base-not-pinned` | `meta.baseRef` is not a full hex object id (40 or 64 chars) — catches an absent key, JSON `null`, `""`, the literal string `null`, an abbreviated sha, and a **branch name** substituted for a pin |
| `base-unresolved` | `git rev-parse --verify --quiet "<baseRef>^{commit}"` fails, or peels to a *different* id (a deleted commit, an annotated-tag id, a well-formed sha that is not an object in this repo, or no git repo at all) |
| `base-pin-moved` | on non-fresh state, `meta.baseRef` no longer equals the pin recorded in `loop-state.json` — a mid-session re-pin to a moved `origin/<base>` |
| `base-repo-mismatch` | PR mode: the PR's base repository ≠ the repo `origin` resolves to (**the fork / multi-remote case**) |
| `pr-base-repo-unresolved` | PR mode: `pr.json` missing, or its `url` is absent / not a PR url |
| `origin-unresolved` | PR mode: `git remote get-url origin` unresolvable |
| `base-repo-root-mismatch` | the checkout the driver is resolving against is not the one the session recorded in `meta.repoRoot` |
| `round-diff-required` | fresh state with no `--diff-path` |
| `round-diff-unreadable` | `--diff-path` absent, unreadable, a directory, or not valid UTF-8 — **the failed-diff case**, given the atomic publish below |
| `round-diff-empty` | `--diff-path` is empty or whitespace-only — **an empty review surface is never certifiable-clean** |
| `round-diff-malformed` | `--diff-path` is non-empty but carries no `diff --git ` header — not `git diff` output |
| `round-diff-base-mismatch` | round-1 diff artifact's file set or per-file +/- counts disagree with `git diff <pin>...HEAD` |
| `round-diff-base-unverifiable` | `git diff --numstat` could not be run (git failure/timeout/unavailable) — expectation not computed |
| `base-mode-unrecognized` | `meta.mode` is not `pr` or `branch` |
| `diff-path-not-fresh-state` | `--diff-path` passed on non-fresh state (the same discipline as `--vendors`) |

**Pending hand-out refusals (`next`).** After the base guard, `_next_response` may refuse before it returns a non-terminal pending step.

| `reason` | condition |
| --- | --- |
| `disposition-ledger-owner-unrecognized` | `state.dispositionLedgerOwner` is present but not the recognized `"ledger"` value, and the pending action is not `terminal` |
| `auditor-unseatable` | on a durable-record session, `next` would emit `dispatch-audits` but no runner-backed vendor (`codex`/`cursor`) is live to seat the fix auditor, or an independent-family vendor is live only as a host seat and cannot prove it ran |

**What to do on refusal (by family).**

- **Base / pin / repo / checkout** (`base-meta-unreadable`, `base-not-pinned`, `base-unresolved`,
  `base-pin-moved`, `base-repo-root-mismatch`, `pr-base-repo-unresolved`, `origin-unresolved`):
  re-run Setup's resolve block and check `origin`; confirm `meta.json` has a full commit pin and
  `repoRoot` matches this checkout. A session whose checkout changed starts a fresh session.
- **Diff artifact** (`round-diff-required`, `round-diff-unreadable`, `round-diff-empty`,
  `round-diff-malformed`, `round-diff-base-mismatch`, `round-diff-base-unverifiable`,
  `diff-path-not-fresh-state`): fix the diff step and do not proceed with review if the diff
  command failed, produced nothing, or produced output that is not a valid diff; for
  `round-diff-base-mismatch`, re-derive the round-1 artifact from the pinned base; for
  `round-diff-base-unverifiable`, fix git availability/timeouts before re-running `next`.
- **`base-mode-unrecognized`:** re-run Setup so `meta.mode` is `pr` or `branch`.
- **`base-repo-mismatch`:** this checkout's `origin` is not the PR's base repository — re-run from
  a clone of the base repo (full fork support is deliberately not built).

Git worktrees share one object store, so a pinned base commit can resolve from the *wrong* worktree
while `origin` still matches there; `meta.repoRoot` lets the driver refuse `base-repo-root-mismatch`
when the field is absent or disagrees with `--repo-root`.

## Owner and advisor rulings (`rule`)

```bash
python3 -B <plugin root>/lib/round_driver.py rule --session-dir <session dir> --ruling-file <rulings file> --by '<who>'
```

The ruling file is JSON: `_provenance` plus a non-empty `rulings` list. `_provenance` is an object
with `ruledBy` (who ruled, transcribed, not invented), `ruledAt` (the ISO-8601 time of the ruling,
not of the file's writing) and `records` (a non-empty list of URLs of durable records a third party
can open, such as the issue or PR comment where the ruling was given; never a file name the recipe
invented); `OWNER_PROVENANCE_FIELD_SHAPES` in `lib/round_driver.py` is the one declaration. Its values
are transcribed from the real ruling, never composed to satisfy the verb; fabricating any of them is
forbidden. The validator checks shape only and cannot detect a false value. Each entry has `id` (finding id or key), `ruling` (`out-of-scope` or `guidance`),
`reason`, and for out-of-scope a shaped `followUp`; for guidance a non-empty `guidance` string
within the gate row byte cap. A guidance entry may also carry `allowsChange`, a JSON boolean
(`true` lets the fix change behaviour its finding does not name; anything but a boolean is refused
with `ruling-file-shape`, and so is `allowsChange` on an `out-of-scope` entry). `rule` copies it onto
the `rulingsLog` row; owner-gate guidance never carries it. **Never append a ruling to a seat
prompt** — the driver carries live guidance in the `apply-fixes` step's guidance file and excludes
out-of-scope keys from the fix batch.

An entry may also carry `decidedBy`, the decision the ruling rests on:
`{"kind": "canon" | "residual" | "sheet-answer" | "owner-ruling", "ref": ...}` and nothing else. For `canon` and
`residual` the `ref` is a non-blank string (the Canon entry's id, or the residual's text); for
`sheet-answer` it is `{"pr": <int>, "card": <non-blank string>}`; for `owner-ruling` it is
`{"url": <non-blank string>, "words": <non-blank string>}`. A `decidedBy` of any other shape
is refused with `ruling-decided-by-malformed`. `rule` only records it in `rulingsLog`; it does not
decide the finding's outcome — the end of the loop does (§ Dispositions).

On success the driver appends to `state.rulingsLog` and the round's `rulings`, records
dispositions for out-of-scope rows, and refreshes gate guidance for a fix batch not yet set.
A guidance ruling that supersedes a live out-of-scope ruling clears that disposition family from
the ledger and the live finding (history stays in `rulingsLog`) and restores the row to the
fix queue. A ruling accepted while `apply-fixes` is pending re-slices `_fixBatch`/`_fixQueue`
through the same exclusion filter and rewrites that step's batch and guidance files; an emptied
first slice settles via empty-batch convergence.

**Rule before the call that sets `apply-fixes`.** Record every ruling on a round's findings before
the call that sets the step. A finding can be ruled on from the fold that staged it: staging seeds its
disposition-ledger row, and `rule` resolves it there by the `findingKey` the verifiers and synthesis
orders carry (a bare staged id does not resolve). On the durable-record path `advance` folds the
phase and then sets the next step through `next` in the same call, so the `advance` whose fold
queues a fix batch returns the `apply-fixes` payload itself: record rulings before any `advance` that
folds synthesis, the seams check, or the scoped finder. On the hand path
a `submit` sets nothing, so record them before the `next` that follows that fold's `submit`.

A ruling is accepted whenever it arrives, at any step that is not terminal, and binds the next fix of
its finding. A ruling accepted while `apply-fixes` is pending rewrites that step's batch and guidance
files, and the next `next` returns the current direction. When the re-slice empties the batch, the
step is dropped and the session settles as it does when a ruling empties the batch before the step is
set (convergence or post-fix). A ruling recorded after the session folded the step reaches the next
round.

Refusal tokens (each leaves state bytes unchanged; none is about timing):
`ruling-file-unreadable`, `ruling-file-shape`, `ruling-provenance-malformed`,
`ruling-unknown-kind`, `ruling-reason-missing`, `ruling-follow-up-malformed`,
`ruling-guidance-oversize`, `ruling-target-unknown`, `ruling-target-ambiguous`,
`ruling-critical-out-of-scope`, `ruling-decided-by-malformed`,
`ruling-session-terminal`,
`disposition-ledger-owner-unrecognized`, `disposition-ledger-malformed`.

### Where a ruling reaches the fix step (the one resolution point)

Which finding a ruling names is worked out once, as a fix batch is finalized: every batch passes
`_resolve_ruled_batch` (called by `_queue_fix_batch`, the one writer of the batch). Out-of-scope
decisions drop their findings first. Each effective `guidance` or `fix` decision is then attached to
the row it binds (a decision given to a finding merged into another rides the representative, as
`ruledBy`), and each finding such a decision names that has not been sent under it joins the batch,
whatever its severity. A finding is found by following the lineage and `mergedInto` to the one live
row. One that is no longer live comes back from the ledger as an open finding when an `apply-fixes`
step carried it before the ruling (the fix went against the ruling, so the next round sends it back) or
when it left the live list with no disposition. For any other the ruling names no live finding: a
`ruling-no-live-finding` decision records it and the end-of-loop settle takes the finding.
`state.sentUnderDecision` keeps, by lineage root, the decision `seq` each finding was last sent under,
so a decision is sent once; a round with no blocker still starts a fix step for an owner-named row.
`state.restagedAfterDispositionSeq` marks a finding restaged from the ledger: the disposition the ruling
reopened does not exclude it as discharged.

### Below-blocking findings settle at convergence

No below-blocking finding joins a fix batch on its own. When the loop converges, every finding with
no outcome gets one (§ Dispositions): left for the owner with its consequence when it states a real
one, otherwise craft. The only below-blocking finding the fix step receives is one an owner `guidance` or
`fix` decision names.

Guidance is held to the same measure. The guidance file never truncates guidance: a write that meets guidance over 2000 bytes (stripped UTF-8) refuses with `order-render-refused:gate-guidance-oversize`. The same holds for the 8000-byte aggregate: a write whose fix batch would carry more guidance than one guidance file holds refuses with `order-render-refused:gate-guidance-aggregate-oversize` (or `ruling-guidance-omitted` when the overflow reaches guidance from a ruling) rather than leave any guidance out.

A finding has one effective decision: the latest of a `rule` ruling and a gate decision the state recorded (`skip`, `fix-with-guidance`, `fix-as-suggested`), ordered by one shared sequence; a gate entry written before that sequence existed counts as older than every sequenced decision. A later `fix-as-suggested` (or a `fix-with-guidance` with no guidance text) supersedes an earlier skip or guidance; a skip carries its `followUp`. The guidance file carries only that decision — guidance the owner later replaced is never shown beside the new guidance — and a tradeoff whose effective decision is a non-Critical skip is not held for the owner's choice again. Only guidance carries: a skip (a `rule` out-of-scope ruling or a recorded gate skip) binds its own finding only — also inside a lineage made by carried guidance — so a reworded or different finding at its place is judged fresh — fixed, or left for the owner. When a later round raises a finding at the same file and line under different wording, it takes the guidance decision of the finding it rewords (`state.findingLineage`, with a `ruling-carried` entry in the decisions), provided exactly one finding is raised at that place in that round (across every staging of the round, every staging alike — a carry a later staging of the round makes ambiguous is undone, `ruling-carry-revoked`, with the disposition it inherited), the earlier finding is not itself raised again in that round, and only one earlier decision sits there. Anything less certain carries nothing, and the reworded finding is judged fresh.

## Batch concurrency — an independent batch goes out together

Several `dispatch-` phases hand you a **batch**: `dispatch-panel`'s `payload.dimensions`,
`dispatch-verifiers`' `payload.clusters`, and `dispatch-audits`' `payload.targets`. **The members of
each of those batches are independent of one another** — the test is no result dependency, no shared
writable worktree, and no shared output path — so they **SHOULD be dispatched concurrently**, and a
round that dispatches them one at a time is paying a cost this contract does not ask for. A batch
larger than the host or account can carry at once launches in waves — each wave launched, then
rotated to terminal, before the next wave launches — and the SHOULD is about not serialising an
independent batch, never a requirement to open every member simultaneously.

**How** to dispatch a batch concurrently — run-dirs and slice sizes in
`skills/workhorse/reference/dispatch-mechanics.md` § Launch slice vs continuation slice,
rotation in `rubric/launch-doctrine.md`'s `await-dispatches` ruling, and the
native-subagent channel in `skills/workhorse/reference/dispatch-mechanics.md` — this
section does not restate them. **Per-arrival `submit` is wrong:** a
`dispatch-panel` submit **accepts a partial seats map** (the `dispatch-panel` row below says so), so
submitting on the first seat's arrival would advance an **incomplete** panel — the exact partial-round
hazard § Lens coverage beside counts exists to prevent. Submit the phase **once**, with every member's
result in the one artifact. On the durable-record path, `record-result` persists each member's envelope
as it lands and **`advance` folds the phase once**, refusing **`incomplete-roster`** until every roster
slot has a result or a missing envelope.

**This changes a batch's shape, never its invariant:** in-turn awaiting only; never harness-external
backgrounding (`&`/setsid/nohup), never an unwatched run-dir at turn end. Ending the turn ends a
headless session; "wait" must be an in-turn poll, never a final message. Concurrency is a way of
awaiting *more* dispatches inside one turn — never a licence to end the turn with a run unwatched.
The one exception to every run reaching terminal before the turn ends is a **durable park** on the
issue or PR.

**What stays sequenced.** Anything failing the independence test above: phases that consume a prior
phase's result (the fix step after the panel — but **not** the verify gate
after the fix: the gate and the fix audits are independent (the audits read the fix diff, the gate
reads the head; neither reads the other's verdict) and go out together, per the `dispatch-audits`
row), and any two dispatches that would write the same worktree or the same output path. Sequencing
on a real dependency is correct; sequencing an independent batch is the defect this section exists
to remove.

## Round economy

Three invariants shape how each round spends verification and fix capacity.

**One full verify run per round.** The session's own checks while it applies fixes are **scoped** —
tests that reference the files it changed plus the project's static validators, at most once each —
never the project's full verify command. The `run-verify` phase is the round's **one** full gate run
on the post-fix head (it runs once more after a first `fail`; § The verify gate runs once more after
one failure). A touched-tests gate that diffs against `main` selects a stacked branch's whole stack; the
`{baseRef}` token is what keeps the gate to its own layer — where the driver predates it, a stacked
lane passes `--base <layer base>` by hand until the stack merges. At the cap round the gate always runs on the post-fix head, including when the
round's earlier gate already passed.

**The gate and the fix audits run concurrently.** After an `apply-fixes` fold the durable path advertises
`payload.verify` on the `dispatch-audits` `next` payload (`{phase: "run-verify", command, round,
attempt, landingPath}`); the gate and the auditors dispatch **in the same turn**. Audits read the
fix diff; the gate reads the post-fix head — neither waits on the other. Two consecutive phases
(`dispatch-audits`, then `run-verify`) preserve one pending step, one state hash, one fold per
phase, and one durable slot per round/phase/attempt — a compound step would need a joint fold and a
new record shape, and emitting audit orders early under a not-yet-pending phase would break the
emission anchor's keying. On the durable-record path the orchestrator runs
`python3 -B <plugin root>/lib/round_driver.py run-verify --session-dir <session dir>` in the same turn as the auditors (it may run
harness-backgrounded and polled in-turn); the driver runs the command and writes `landingPath`
itself, and a hand-written landing is refused at `advance`. `advance` folds it once `run-verify` is pending. On a
hand-`submit` session keep the result and submit `{result}` at `run-verify`. Both arrival orders
fold to the same state.

**Fix batches are capped and split.** `fixBatchCap` (config key, CLI `--fix-batch-cap`,
default `round_phases.FIX_BATCH_CAP_DEFAULT` (the one home; the driver reads it at runtime), positive integer — refused `fix-batch-cap-invalid` otherwise) limits findings per
`apply-fixes` step. A larger blocking set is set as consecutive `apply-fixes` steps
in the same round (`fix-batch.json`, `fix-batch.1.json`, …), each folded on its own with a
`fix-batch-split` decision; the round record carries `fixBatches` and `fix.fixes` is the union.
Later slices queue within the round; audit targets derive from the whole batch, so slices are
audited as one round.

## Rounds, the cap and handback

A review session runs at most 4 rounds. The one constant is `round_phases.ROUND_CAP = 4`, and the
skill passes `--max-rounds 4`. `--max-rounds` accepts 1 to 4 on a fresh session; any other value is
refused `max-rounds-invalid`. There is no ceiling above the cap.

The cap is a boundary on the round about to begin. The cap round completes its audits, its fix leg
and its verify gate, and then the session hands the PR back.

**How a session stops.**

- **Nothing blocking left.** The session converges at that round, round 1 included.
- **The cap round ends with something open.** The session hands back through the one handback
  terminal (`_hand_back` in `lib/round_driver.py`), verdict `handed-back`, last decision
  `round-cap`, with every open finding, Important and Critical alike, each with its outcome. There
  is no park or held state, no automatic extra round (the advisor may order one audit round, § The
  extra audit round), and no new session started to keep going.
- **The same fix fails its audit in two rounds in a row.** The session makes one automatic recovery
  attempt: the fix step is set again. No recovery attempt runs when the second failure is
  in the cap round. If the fix still fails after the recovery attempt, the session hands back with
  `handed-back` / `fix-keeps-failing`; in the cap round it hands back with `round-cap`.
- **A blocking finding only the owner's choice can settle** (a finding marked `tradeoff: true`). It
  is held out of the fix batch: the build session does not make the owner's choice. A `rule`
  decision (guidance or out-of-scope) recorded on it is the in-session way to settle it (§ Owner and
  advisor rulings). If it is still unsettled when nothing else is left to fix, the session hands
  back with `handed-back` / `owner-choice-open`, and the finding reaches the owner as a leftover at
  the vet, framed in owner terms.
- **Nothing from the review reaches the owner mid-review.** The driver emits no owner-facing step,
  and accepts no owner artifact on `advance`. No setting or saved calibration stands in for the owner
  at a step, because there is no such step.

A fix surface the driver cannot work out hands the PR back too, as `fix-surface-unknown`: the
post-fix head diff could not be read, the round's baseline diff is missing or stamped for another
round, or the fixes' own diff could not be computed for every file. No panel runs in its place.
A session saved while it waited at a panel in round 2 or later (written by an earlier version) is
handed back as `later-round-panel-retired` the next time any command loads it.

The seven `handed-back` decision kinds are `round-cap`, `fix-keeps-failing`, `owner-choice-open`,
`extra-audit-open` (§ The extra audit round), `fix-surface-unknown`, `break-it-restore-failed` (a restore of the
test role's break-it test could not be made, so the PR goes back with its findings open) and
`later-round-panel-retired`.
The result file maps `converged` to `exit_clean` and
every other verdict to `halt`. The review record reads rounds as `<count> of <cap>` and says the
loop stopped at its cap for `round-cap` and `extra-audit-open` ([review-record.md](review-record.md)).

## The extra audit round

When a session hands the PR back at the cap with a fix the cap round applied and no audit checked,
the advisor may order one [extra audit round](../../../rubric/glossary.md#extra-audit-round) at the
vet. At most one is allowed per PR, across all its sessions. The build session that holds the
handed-back session directory orders it:

```bash
python3 -B <plugin root>/lib/round_driver.py extra-audit --session-dir <session dir> --order-file <the order file> --by <who> --pr <N>
```

`--repo <owner/name>` is optional: append it to that line to name the PR's repository. The order
file is the JSON object `{"why": "<non-blank reason>"}`, with no other key. The build session
then carries on with the normal `next` / `advance` loop to the terminal and writes the review record
as usual.

**The refusals,** checked in this order. Each refuses with nothing changed but a journal row.

1. The shared lock, upgrade and commit-recovery refusals.
2. `extra-audit-state-unreadable`.
3. `extra-audit-order-invalid`.
4. `extra-audit-already-run`: this session already ran one. This comes before the at-cap check
   because a session that ran its extra round ends on that round's own terminal, never on the cap's.
5. `extra-audit-not-at-cap`: the session is not `handed-back` with last decision `round-cap` or
   `fix-keeps-failing`.
6. `extra-audit-nothing-to-audit`: no fix the cap round applied is unaudited. A `fix-keeps-failing`
   handback always lands here, because its last fix was already audited.
7. `extra-audit-head-unresolvable` and `extra-audit-head-moved`: the checkout's HEAD is not the
   session's certified head.
8. `extra-audit-receipt-faulted` (the finalized-receipt check): the finalized receipt fails its
   on-disk check.
9. `extra-audit-pr-history-unreadable` (the first PR-history read): the repository could not be
   resolved from the session checkout, or the PR's comments could not be listed, or a review-record
   comment on it does not parse, or an extra-audit reservation comment names no session. This fails
   closed.
10. `extra-audit-already-run-on-pr` (the first PR-history read): an earlier review record on the PR
    shows an extra audit round, or another session already posted its reservation comment on the PR.
11. `extra-audit-reservation-failed`: the reservation comment could not be posted. Once every check
    above passes, and before the receipt copy and the state commit, the verb posts one comment on the
    PR (first line `<!-- superheroes:extra-audit-reserved -->`, then the session id and the order's
    why). A reservation from the same session does not count, so a re-run after a crash carries on.
    A refusal after this point leaves the reservation comment on the PR.
12. `extra-audit-pr-history-unreadable` (the re-read after the reservation is posted): the verb reads
    the PR's comments again, and the re-read fails for any reason item 9 names. This fails closed.
13. `extra-audit-already-run-on-pr` (the re-read): another session's reservation, or a review record
    showing the extra round, has a lower comment id than this session's own reservation. The first
    reservation posted wins; the loser keeps its reservation in place and refuses.
14. `extra-audit-receipt-faulted` (the superseded-copy check): the receipt cannot be copied to its
    superseded name, the copy does not match it, or an existing superseded copy does not match it.

**The round.** The verb reopens the session as round 5, the cap plus one. That round dispatches
**only `dispatch-audits`**, over the cap round's fixes. It runs no panel, scoped finder, seams check,
verifiers, synthesis, fix step or verify run. A surface the round cannot derive hands back
`extra-audit-open` instead of scheduling a panel.

**The two ends.**

- **Every fix discharged, nothing else blocking.** The session ends `converged` through the normal
  convergence check, which still hands back a held owner choice as `owner-choice-open`.
- **Otherwise** it ends `handed-back` with the decision kind `extra-audit-open`, which counts as a
  stop at the cap. An auditor's new issue in that round is not searched or fixed; it is left open for
  the vet.

**The receipt.** The finalized `round-receipt.json` is copied, byte for byte, to
`round-receipt.superseded-1.json` before the state is reopened. It is never moved or deleted. The
extra round's terminal then writes a fresh `round-receipt.json`. A crash between the copy and the
state commit leaves the original session as it was, and a re-run carries on.

**The record.** `rounds.count` does not count the extra round. `rounds.extraAudit` is
`{"why": …}`. `stoppedAtCap` is true for `extra-audit-open`. The record writer also refuses
`review-record-extra-audit-repeated`: an account showing the extra round, when an earlier readable
record from another session on the PR shows one too. That is a backstop; the verb's own check comes
first. The fields are described in [review-record.md](review-record.md).

## Lens coverage beside counts

**Every reported round count carries its lens coverage** — the round-1 panel at minimum, and any
round whose counts anyone reads or acts on. A round is **complete** when every configured dimension
folded `seatStatus: "run"` and the round records no `vacuousSeats`. A round is **partial** when any
configured dimension folded `missing`, or the round records any `vacuousSeats`. Completeness is defined by
the **configured** dimensions, never by the seats that happened to return. Report it as
`<complete>/<configured> dimensions` beside the count, naming the dimensions that did not land.

**A partial round's counts are floors, and are labeled as floors** — never totals.
`2 blocking (floor — 3/5 dimensions; security and premortem did not land)` is honest; a bare
`2 blocking` from the same round is not.

**Trajectory and convergence claims cite complete rounds only.** A trend drawn through partial rounds
reads a queued backlog as a regression and an unexamined surface as clean. Field evidence (a stacked
review, 2026-08-09): two lenses never examined one half across several rounds, so the first
complete round landed their whole backlog at once and read as a new crop — and leg planning was
steered by the partial trend line.

## Dispositions

One ledger owns every finding's disposition — the loop seeds it and archives departures there.

- Every compiled candidate that enters verification is **seeded** into `dispositionLedger`, keyed by
  `findingKey`, carrying `raisedRound`. A finding that leaves the live list is **archived** there
  whether or not it carries a disposition.
- A candidate merged into a representative at synthesis carries `mergedInto`.
- The state marker `dispositionLedgerOwner: "ledger"` records that the **disposition ledger is the
  durable owner of record**; seeding sets it (`_stage_findings`, `lib/round_driver.py`). A marker value the driver
  does not recognize refuses at the fold with `disposition-ledger-owner-unrecognized`
  (`_fold`, `lib/round_driver.py`).
- The three dispositions recorded as the loop goes (the three the end of the loop adds are below): `fixed` carries `dispositionReceipt {headSha}` — the fix-fold head the
  config records, and an empty receipt when it records none (`_fixed_disposition_receipt`,
  `lib/round_driver.py`); `refuted` carries `refutedReason`;
  `out-of-scope` carries `outOfScopeReason` plus a `followUp` object with shape
  `{item, revisitTrigger, classClosure}` — judged by `session_contract.follow_up_shape_fault`
  at submit. A new follow-up must include a nonblank `item`. The fault it returns names
  `missing-follow-up-item`, `missing-revisit-trigger` or `missing-class-closure`
  (`follow_up_shape_fault`, `lib/session_contract.py`).
- Where each is recorded: `fixed` at the audits fold for every target the independent auditor
  discharged — and only for a target whose auditor named no unnamed behaviour change (`unnamedChange`,
  the behaviour the fix changes that its finding does not name), or whose auditor named, by
  `unnamedChangeAllowedBySeq`, a carried decision (the target's own or a batch sibling's) that is
  still current, is a `guidance` ruling with `allowsChange: true` and is not overridden by the
  target's own `allowsChange: false`, or whose auditor attributed every unnamed change, by
  `unnamedChangeFixes`, to findings of the round outside the batch (the target's `roundFindings`: no
  owner skip or out-of-scope ruling, not refuted) and/or, by `unnamedChangeReverts`, to undoing named
  changes an earlier audit of the review reported (refs into `reportedUnnamedChanges`); the fold
  checks each claim against the driver's record and records `attributedChange` (plus `sameRoundFixes`
  / `revertedChanges`) on the audit and an `audit-attributed-change` decision; any other target is
  `not-discharged` with the auditor's reason, recorded as `auditUnnamedChange` on the round with an
  `audit-unnamed-change` decision, and returns to the fix list; `refuted` at the verifiers fold (the verdict's reason) and at synthesis for an
  author-justified drop (the quoted justification); `out-of-scope` where a `rule` out-of-scope
  ruling gives it (§ Owner and advisor rulings), with its shaped `followUp`.
- A finding an audit raised (a `discharged-but-new-issue` ruling's `newIssues`) is linked to the target
  it came from in `state.auditSpawned` (`{child key: parent key}`), bound by compile anchor after the
  compile (`_bind_audit_spawned`, `lib/round_driver.py`): a scoped-finder candidate never supplies a
  link, and an anchor two different targets raised links nothing. When a later fix batch carries the
  parent again, the child rides that round's audits as a target of its own (`spawnedFrom: <parent
  key>`, the same row as a batch target) and is listed in every target's `roundFindings`, so the
  parent's auditor can attribute the child's repair. A rider is skipped when it has a current
  disposition, is merged, or is out of scope, and when the ledger cannot be read; a finding whose
  effective owner decision is not a fix or guidance never rides. A rider the auditor
  discharged is `fixed` at the audits fold, like any audited fix; one ruled anything else
  (`not-discharged`, no result, unauthenticated, no independent auditor, ambiguous) keeps no
  disposition and is left to the settle below. A rider never joins the fix list, the audit-stall
  breaker's outcomes or the `prBodyAudited` check. The round records `spawnedAudits`
  (`{id, spawnedFrom, ruling}`), and a rider not discharged records a `spawned-audit-not-discharged`
  decision in place of `not-discharged`.
- An out-of-scope finding is offered to the fix step in at most one round while it stays out of scope
  (one episode: the decision's sequence number, or its round for a legacy gate decision). The first
  offer is recorded in `state.outOfScopeFixerRounds`; in a later round of the same episode the
  finding is left out of the fix batch, its out-of-scope disposition is recorded again naming the
  round it was offered in, and an `out-of-scope-fix-spent` decision says so. A later `guidance`
  decision ends the episode. A batch emptied only this way settles through empty-batch convergence
  and is not counted in `fixBatchExcludedByDischarge`.
- A **malformed** `followUp` is refused at `rule` with `ruling-follow-up-malformed`, so the ruling is
  corrected while the one who gave it is still present.
- A verifier drop, author-justified drop, or synthesis merge whose staged id is missing, maps to
  nothing, is duplicated, or has no derivable finding key refuses `staged-id-unresolvable` at
  submit — never silently skipped.

### How the loop settles what is left

Every finding the review took in ends with an outcome. This is the one place the rule is stated;
other docs link here.

- **When.** Only when the loop reaches a terminal, by the one terminal writer (`_set_terminal`,
  `lib/round_driver.py`). A stop at the round cap (`handed-back`) settles the same way; only the reason
  differs, and it names the cap.
- **Who keeps its disposition.** A finding that is fixed, or shown wrong (disposition `refuted`), keeps
  that disposition, as does a finding merged into another (it follows the other). A Nit the readout
  cap collapsed is already `craft`, recorded when it was collapsed. A finding an audit raised and a
  later audit discharged under its own key (a rider, § Dispositions) is `fixed` and keeps it; one that
  audit did not discharge has no disposition and is settled below like any other.
- **Who is settled.** Every other finding the review took in — no disposition, a disposition older than
  the finding's last raise, or `out-of-scope` — is settled by `settle` (`lib/finding_outcomes.py`):
  1. A finding whose only consequence is code quality (`consequenceKind` `code-quality`) is `craft`.
     It is recorded for the owner's veto and no ruling overrides it.
  2. Otherwise, a finding whose latest ruling cites a `decidedBy` decision that is **on record** is
     `ruling`, and the decision is named.
  3. Otherwise it is `left-for-owner` (a [leftover](../../../rubric/glossary.md#leftover)). The reason
     says why it is open and, when a cited decision did not resolve, why not.
- **Severity never decides the outcome.** `settle` is never given it.
- **On record.** A decision is on record only when it is an active Canon entry (complete, and not
  superseded), a recorded residual (its text appears in the residuals the review read), or a settled
  saved sheet answer for this PR (`aligned` on a card the published sheet gives no options, or a picked option). A decision that cannot be read is not
  on record.
- **Where it is written.** The disposition ledger, as disposition `craft`, `left-for-owner` or
  `ruling`, with `settledReason`, and for a `ruling` (or a `left-for-owner` whose cited decision was not on record) also `decidedBy`. An out-of-scope finding keeps its
  `outOfScopeReason` and `followUp`. The session record adapter reads these as the outcomes of the same
  name ([review-record.md](review-record.md) § The full lane writes it from the session).
- **Once.** A second settle finds nothing left to settle. If the disposition ledger cannot be read,
  nothing is settled and the state records `settleSkipped` with the fault.

## Actions and payloads

### Synthesis coverage (`dispatch-synthesis`)

`synthesis_results_fault` **refuses** a submit with no `grouping` key at all.
`verification.grouping_coverage_fault` enforces the synthesis **coverage guarantee** for non-empty
groupings: **`grouping: null`** and an **empty list** carry no coverage obligation and fall open
to unmerged survivors — **synthesis drops nothing** and synthesis failure never aborts the review.
A **non-empty** grouping is checked against the coverage rule in
[verification-pass.md § Synthesis merge + rank](verification-pass.md#synthesis-merge--rank), and
a fault refuses the submit with `staged-id-unresolvable`. A `repeatOf` ref or a member id the
order's input does not carry refuses at submit with the same token. `_fold_synthesis` then runs `verification.merge_and_rank` on accepted groups.

| `action` / `phase` | Orchestrator fulfills |
| --- | --- |
| `dispatch-panel` | Dispatch the round's `reviewer-deep` panel per `payload.dimensions`, `payload.tier`, and no per-lens split of the diff: every lens reads the whole diff. A dimension whose seat the seat map marks `source: "unfilled"` (no candidate outside the makers' families) gets no order: the driver writes its `seat-missing/1` record itself with reason `unfilled`, and a hand submit folds that dimension `missing` whatever payload it carries. Submit `{seats: {<dim>: {findings, receiptMissing?, receiptStale?, vacuous?, reason?}}, seatMap?, ranManifest?}`. A seat whose `dispatch-review` returned `reason: "vacuous"` (or equivalent double vacuous forfeit) is folded with `vacuous: true` or `reason: "vacuous"`. `ranManifest: {<dim>: <vendor>}` is the orchestrator's OWN trusted record of which vendor produced each seat's folded findings — mirroring `collectionManifest`; an in-seat `ranVendor` echo is advisory only and authenticates nothing. The driver mechanically compares it to the seat map's configured vendor and records a per-round `fellOpen` dispatch-provenance row + a `degraded` disclosure for any `run` seat that fell open to a different vendor — the disclosure is machinery, not builder discipline. A cross-vendor seat that ran without a trusted manifest entry is disclosed as provenance-unavailable. The guarantee is exactly as strong as the orchestrator's manifest — the driver cannot cryptographically verify engine identity and does not pretend to (the same posture as `collectionManifest`). Receipt-missing seats re-dispatch at most `REDISPATCH_BUDGET` times (`loop_plan_common.REDISPATCH_BUDGET` — the single home) before terminal `missing` with findings carried unverified. The driver refuses a submit whose seat keys are not configured dimensions — keys must be the full reviewer names from `payload.dimensions`, never the findings-file stems (`architecture`, `code`, …); unknown keys only — a partial seats map (subset of configured dimensions) and an empty one are still accepted, and an absent lens is caught later by the panel's own incomplete-panel park, not here. Recovery is to re-key the seats map and resubmit the same phase/attempt/state-hash (no re-dispatch, no fresh session dir). **`payload.dimensions` is an independent batch — dispatch its seats concurrently, per § Batch concurrency above; submit the phase once, with every seat in the one artifact.** |
| `dispatch-verifiers` | One verifier per cluster in `payload.clusters` (`model: $VERIFIER_MODEL`, dispatched on the vendor the orders manifest names for the seat — the reviewer engine only when the manifest names none; the driver replaces a maker-family reviewer engine). Each non-panel phase seats its reviewer only on a vendor whose dispatched cell for that phase (the verifier cell for verifiers, the reviewer-deep cell for seams check and scoped) the seat map proves live; a seat map that carries none of the cell-proof keys proves no non-claude cell. A native host seat takes the host's family from the seat map, and an unknown host makes it ineligible. Submit `{verdicts: [...], verifierVendor}`. A verdict may carry `pathReached` for a finding whose break-it test passed. `verifierVendor` is the vendor that actually ran; on a hand `submit`, verdicts whose `verifierVendor` is not the driver's selected vendor (or is absent when the selection replaced the reviewer engine, whatever the preference read's provenance) fold as silence; on the durable `record-result` + `advance` path the executed vendor is each stored envelope's runner execution evidence (`executionEvidence.source`), never the selection, judged per cluster (a seat's evidence authenticates only its own cluster's verdicts; absent or different evidence folds that cluster as silence while a proven cluster still folds), against the vendor the verifier orders manifest recorded at emission rather than a fresh read of the live preference, and the round records each pairing as `verifierProvenance`. A host-seat (file-channel) verifier landing as a bare payload carries no runner evidence; its executed vendor is the driver's own orders-manifest entry for the seat (recorded with `provenance: dispatch-manifest`), unless that vendor is in a maker family. The seams-check and scoped-finder results are authenticated the same way against the vendor recorded at emission: an unauthenticated result folds as the seat missing (refuse-fold), and a hand `submit` for them carries `reviewerVendor` when independence replaced the reviewer engine. A non-panel result whose vendor equals the ordered vendor still does not count when that vendor is in a maker family, and a hand finder `submit` on an emission whose orders manifest no longer verifies is refused. **`payload.clusters` is an independent batch — dispatch its verifiers concurrently, per § Batch concurrency above; submit the phase once, with every verdict in the one artifact.** A REFUTED whose reason or evidence shows a check that did not execute the code under test (a missing command or module, exit 127) is not a drop: the fold keeps the finding unverified, records a `verifier-not-executed` decision and lists it under the verify record's `notExecuted`, with no disposition written. |
| `dispatch-synthesis` | One synthesis judge over `payload.findings`, dispatched on the vendor the orders manifest names for the seat (outside every maker family, on a proven synthesis cell). The seat also gets the round's refuted findings and the PR's earlier findings. When no vendor qualifies there is no synthesis order: the driver folds no grouping (every verified finding stays separate), records `synthesisUnseatable` and discloses it on the receipt. When verification leaves no survivors there is still a repeat-only synthesis order in the case [verification-pass.md § Synthesis merge + rank](verification-pass.md#synthesis-merge--rank) states; otherwise the driver folds an empty grouping itself and records the `synthesis-no-survivors` decision. When synthesis is unseatable or not dispatched, only exact identity marks repeats, and the round records `repeatMatching: "exact-only"` with its reason. Submit `{grouping: [{group_id, member_ids, repeatOf}, ...]}`; [synthesis-pass.md § Repeats](synthesis-pass.md#repeats) says what a mark does. Mechanical compile (citation, diff-scope, dedupe, nit cap) and `verification.merge_and_rank` run inside the driver — the merge keeps the **highest** severity among a group's members on the normalized fail-closed vocabulary (`circuit_breaker.severity_rank` / `effective_severity`), so a group can never come out less blocking than its most severe member; the **author-justification post-filter** runs here too (may drop only non-CONFIRMED findings; CONFIRMED survives stamped `challenge: "author-justified"`). |
| `dispatch-seams-check` | Sliced change, round 1 only, once: one full-diff finder pass at `reviewer-deep` over the problems that sit across slices, given `payload.slices` (each slice's id and files). Its findings are staged with the panel's for the verifiers. Submit `{findings: [...]}`. |
| `dispatch-second-test` | Only when the verifiers held a finding whose passing break-it test missed its path: one fresh test-role run at `reviewer-deep`, outside every maker's family (authenticated like the seams check), over `payload.findings` (each held finding with its first test, its output and the verifier's note). Submit `{findings: [...]}`, each held finding echoed by its staged `id` with its one new `break-it-test v1` block as `suggestion`. The driver runs each new test in the session's working copy, records it with the finding, and re-dispatches the verifiers over the held findings only; there is no third test. With no seatable vendor no order is emitted and the held findings go straight to the verifiers. See [the missed-path step](verification-pass.md#the-grade-and-the-missed-path-step). **The correction form.** The same phase offers the test role one correction, after a restore, for each restored target whose test the fix auditor judged `weakened` and whose finding has not used its correction. `payload` carries `correction: true` and `findings`, each `{id, path, reviewerTest (the version just restored), committedTest (the build session's), changedWhy, why (the auditor's)}`; the order is `dispatch-second-test-correction`, its inputs in a `second-test-correction.json` sidecar. Submit `{findings: [...]}` like any second-test result. A result for the item at the same `path` whose `suggestion` is a `break-it-test v1` block that is not redacted and differs from the restored test is the corrected test, and a second restore-only `apply-fixes` step commits it (`source: "corrected"`, decided `break-it-correction-landed`); a missing, blockless, other-path, redacted, unchanged or duplicate-id result is no correction (`break-it-correction-none`), the restored test stands, and the correction's result never goes to the verifiers' second pass. Either way the finding's `testCorrection` is `{round, used: true, outcome: "corrected" \| "none"}`, so no finding is offered a second correction in the session. With no seat to seat, nothing is offered and nothing is used: `testCorrection` stays unset on the finding, the round records `{findingKey, outcome: "unseatable"}` and the driver decides `break-it-correction-unseatable`. A seat that forfeits or fails authentication keeps the refusals above: the test role's version is already committed. |
| `dispatch-audits` | Delta round: one auditor per target in `payload.targets`. Seat each auditor at the registry's `auditor` role (`python3 -B <plugin root>/lib/dispatch_guard.py check --seat '{"vendor":"<vendor>","model":"<id>","effort":<effort or null>,"role":"auditor"}'`). **Auditor independence:** an auditor is never from any maker's family (the seat map's `makerFamilies`). The build session is a maker of every fix it applies, and the family barred as the fix's maker is the build session's own, read from the seat map at session start (its host family, else its author family). Without a seat map that family is unknown, and the audit runs as a disclosed degraded audit. When every filled roster seat is pinned, the auditor must also be one of the pinned vendors. When no live vendor qualifies there is no auditor and no vendor stands in: the target carries no `auditorVendor` and is stamped `independence: "unseatable"`, the audit counts as not run (its fix is never counted as audited or discharged, and any result submitted for it is ignored), and the receipt independence block is stamped `degraded`. On a durable-record session `next` refuses `auditor-unseatable` only when a qualifying vendor is live solely as a host seat, not as a runner-channel vendor; a hand-submit session may still seat an independent host auditor. `payload.targets[].auditorVendor` names the vendor to dispatch each auditor on; on a durable-record session the driver seats only a runner-backed vendor (`codex`/`cursor`). Each target carries **two** id-shaped fields: `id` (per-location — the dispatch/result/manifest key) and `identity` (line-less, driver-internal stall alias), plus `verdict` and `evidence` — finding-derived text that rides into each auditor seat's order payload. A target may carry `spawnedFrom` (the parent finding key) when it is a finding an audit raised, audited under its own key; it is otherwise an ordinary target. Submit `{results: [...], collectionManifest: {<result-id>: <vendor>}}`. **Every transport key is `payload.targets[].id`:** each `results[].id` and **every** `collectionManifest` key must be the per-location `id` — never `targets[].identity` (driver-internal; must not be used as a transport key). A manifest key outside the round's target ids is **refused at submit** with the mistake named — nothing folds, recovery is a corrected resubmit on the same phase/attempt/state-hash. **Hand `submit`** keeps `collectionManifest` (orchestrator-written; a missing entry folds `not-discharged` + `unauthenticated` with an `audit-provenance-fail` decision naming the expected key and the keys found). **Durable-record path** at state v5 derives `collectionManifest` from each stored envelope's `executionEvidence.source`; a landing whose provenance cannot be derived refuses **`provenance-underivable`** at `record-result`/sweep. A clearing ruling (`discharged` / `discharged-but-new-issue`) is authenticated **iff `collectionManifest[id]` exists AND equals the driver-recorded selected auditor** (where `id` is the per-location target id); a missing entry or wrong vendor → **not-discharged + `unauthenticated`**. The in-result `auditorVendor` is **advisory only**; an echo that disagrees with the trusted source is disclosed as `echoMismatch` but the trusted source governs and the discharge stands. Recorded per round as `auditProvenance` from the adapter's per-seat `provenanceSource`: `"runner-record"` when every audited seat's source is dispatch-observed runner evidence; `"hand-landed-evidence"` when every audited seat's source is hand-landed execution evidence; `"mixed-evidence"` when sources disagree or any audited seat lacks a derived source; `"collection-manifest"` on a hand `submit` at any version (or when no `provenanceSource` is present). The driver **cannot cryptographically verify engine identity and does not pretend to** — the guarantee is exactly as strong as the recorded dispatch provenance. **`payload.targets` is an independent batch — dispatch its auditors concurrently, per § Batch concurrency above; submit the phase once, with every result in the one artifact.** For a fix auditor's `ruling` result, the orchestrator may land the stub envelope with `payload: null`, and `record-result --evidence-run-dir` fills it from the runner's graded record. **Concurrent gate.** When the delta round was entered from an `apply-fixes` fold, `payload.verify` carries the verify gate — `{phase: "run-verify", command, round, attempt, landingPath}` — and the gate is dispatched **in the same turn as the auditors** (it reads the post-fix head; the audits read the fix diff; neither waits on the other). On the durable-record path run `python3 -B <plugin root>/lib/round_driver.py run-verify --session-dir <session dir>` in the same turn (it may run harness-backgrounded and polled in-turn): the driver runs the command and writes `payload.verify.landingPath` itself, a hand-written landing is refused at `advance`, and `advance` folds it once `run-verify` is pending (the phase right after this one). On a hand-`submit` session keep the result and submit it at `run-verify`. A missing gate result when `run-verify` is pending refuses `orchestrator-payload-missing` — it is never skipped. **The three checks.** Every result carries `checks` — `right`, `brokeNothing` and `testWouldFail`, each `{answer: "yes" \| "no", why}` with a usable `why` — whatever its ruling; one function, `audits.audit_checks_fault`, judges the shape for the payload contract's `audit-checks` predicate, the submit guard (a refusal; the step stays pending) and the fold (a result that fails it folds `not-discharged`, listed in `malformed`, reason `audit refused: <fault>`). A clearing ruling stands only on three `yes`; with any `no` it folds `not-discharged`, reason `audit check failed: <check>: <why>`. A target whose finding carries a break-it test carries `breakIt` — `{path, reviewerTest (the test role's content), committedTest (the blob at the audited head, null when absent), changedWhy, match}` — with `match` one of `same`, `changed-explained` (the committed test is the build session's `break-it-change` text and a reason was given), `changed-unexplained` and `missing` (including when git cannot be read). `missing` and `changed-unexplained` fold `not-discharged` whatever the result says; for `changed-explained` the result also carries `testMatch` `{answer: "matches" \| "weakened", why}` and `weakened` folds `not-discharged` (`break-it test weakened: <why>`). Both blocking cases are listed in the outcome's `testMismatch`, recorded on the round and decided `break-it-test-mismatch`; each audit entry records `testMatch {match, answer, blocking}`. **The restore.** A `testMismatch` is never left standing: when the audit folds with a target listed in it (a spawned rider excluded), the next step is a restore-only `apply-fixes` step that puts the test role's version back (see `apply-fixes` below), before the scoped finder, the settle, a halt or a hand back can run. The finding stays not discharged; at the cap the settle hands it back like any other open finding. After the restore, and after the one correction below when one landed, the round's verify gate runs on the new head, in every round and in the extra audit round too; its result is the gate's, never one taken before the restore. A gate failure halts as it does anywhere else, with the test role's version committed. |
| `dispatch-scoped-finder` | Delta round: scoped scan over `payload.hunks` (the fixes' own surface — for each file the fixes changed, the head-file lines they changed, file → line range + text) at `reviewer-deep`, dispatched with `"role":"scoped-finder"` in the `--seat` bundle. The finder is given only the fixes' own diff (`round-<N>/fix-delta.diff`: the change between the reviewed, pre-fix diff and the post-fix head diff, each file under its `diff --git` line), proven copies left out; it is not given the head diff. Submit `{findings: [...]}`. Emitted **whenever the fixes changed a file that is not a proven copy**; a genuinely empty surface (the fixes touched only proven copies) skips this dispatch and records `scopedFinder: skipped-empty-surface` on the round (receipt-visible) — never a vacuous scan over nothing. |
| `run-verify` | Run `payload.command` from the working tree (non-interactive, timeout). **The verify step may run harness-backgrounded and polled in-turn** — the already-sanctioned shape for long local work — because the host's foreground command-timeout cap bounds a **single call**, not the step; what stays forbidden is unchanged, `&`/setsid/nohup and ending the turn to wait. Hand path: submit `{result: "pass" \| "fail" \| "timeout" \| "skipped" \| "none" \| "unverified"}`. When the local verify command cannot run, the payload may instead carry `via: "ci-exact-head"` with `ci: {workflow, runId, headSha, conclusion}` and a non-empty `reason` naming why, with `result: "pass"`; the driver fetches the run and refuses the submit, keeping the step pending, on `ci-verify-shape:` (a malformed claim), `ci-verify-run-unreadable`, `ci-verify-sha-mismatch`, `ci-verify-workflow-unconfigured` (the project declares no readable `ciWorkflow`; checked before the fetch), `ci-verify-workflow-mismatch` (the claimed workflow or the fetched run's name is not the declared `ciWorkflow`) or `ci-verify-conclusion-mismatch` before folding, and the round records which verify it used in `verifyVia`. Durable-record path: run `python3 -B <plugin root>/lib/round_driver.py run-verify --session-dir <session dir>` (add `--timeout SECONDS` to change the default 3600). The driver runs the bound command (`{baseRef}` bound to the pinned base) under `bash -c` in the repo root, with stdin closed and stderr merged into stdout, and publishes `{result, exitCode, outputSha256, outputPath, command, ranBy: "round-driver", headSha, treeSha}` (plus `headShaAfter` when HEAD moved while the command ran, and `treeShaAfter` when the working-tree contents changed while it ran) as the bare landing at `$SESSION_DIR/round-N/landing/run-verify/<skey>.a<K>.payload.json` where `<skey>` is `round_records.storage_key("verify")`, plus a `run-verify`/`landed` journal row carrying the payload's hash, in one commit; `state.json` is untouched. Exit 0 lands `pass`, any other exit `fail`, a run past the timeout `timeout` (`exitCode: null`); an unconfigured command (absent, empty or `none`) runs nothing and lands `{result: "none", ranBy: "round-driver"}`. The captured output is in the per-claim log `landing/run-verify/_verify-output.a<K>.<token>.log`, and `outputSha256` is the hash of exactly those bytes. While the command runs the verb holds an exclusive claim file `landing/run-verify/_verify-claim.a<K>.json` (`{pid, token, startedAt}`); a claim whose pid is gone (or that cannot be read) is taken over and reported as `staleClaimTakenOver: true`. The session lock is held only to read the slot and take the claim, and again to publish — retried every 0.5 s for up to 300 s — so `next`, `advance` and the auditors are never blocked by the run. The slot is the pending `run-verify` step, or the `payload.verify` slot while `dispatch-audits` is pending; it is re-checked under the lock before anything lands. The verb answers one JSON object, `{ok: true, result, round, attempt, landingPath, outputPath, payloadSha256, staleClaimTakenOver?}`; every refusal answers `ok: false` and exits 0: `run-verify-not-pending` (nothing pending, another phase, terminal, or `dispatch-audits` with no `payload.verify`), `run-verify-already-landed` (a bare landing or a durable record is already in the slot), `run-verify-locked` (the session lock was held on entry), `run-verify-in-progress` (a live claim; names `claimPath`), `run-verify-claim-failed` (the claim file could not be created), `run-verify-no-bash` (a configured command and no `bash` on `PATH`; checked before any claim), `run-verify-spawn-failed` (the process could not start; nothing lands), `run-verify-output-unwritable` (the output log could not be written; nothing lands), `run-verify-publish-lock-held` (the lock stayed held for the whole wait; nothing lands and the run is re-run later — a computed result is never parked for a later invocation to trust) and `run-verify-slot-moved` (the slot moved or filled during the run; nothing lands). Every refusal after the claim was taken releases it. `advance` folds a non-CI `run-verify` landing only when the journal holds the driver's own row for exactly that round, attempt and payload hash; a hand-written or edited landing, a row for another slot, or a journal that cannot be read refuses at `advance` as `fold-refused` with **`verify-landing-not-driver-written`** in `detail` (it is the `reason` at `submit`, the `detail` under `fold-refused` at `advance`), the step stays pending and the state hash is unchanged. A `ci-exact-head` claim is still written by the orchestrator and still checked against the fetched run at fold, unchanged; the hand-`submit` path is unchanged and is not subject to this check. **The fold writes the durable seat record** for that slot (`seat-result/1` at `$SESSION_DIR/round-N/seats/run-verify/<skey>.a<K>.json`, stamped `fulfilledBy: "orchestrator"`, `orderSha256` / `manifestSha256` = `not-emitted` because there is no anchor to check them against) **in the same commit as the fold**, so a `verifyResult` folded this way reconstructs from the record exactly as a seat-path fold does. **Both artifacts present → `landing-ambiguous`, no fold** — the bare payload and a durable seat record are two claims for one slot, the same invariant the seat path refuses on the envelope/bare-payload pair; delete whichever is not the one you meant. The refusal is **unconditional**: a re-entry after this fold already committed refuses too, rather than re-folding, because recognising "this record is mine" duplicates the already-folded judgment `submit`'s duplicate contract owns. A first `fail` runs the gate once more; the second result decides, and any other result but a `pass` (or a skip with no verify command configured) is a terminal halt, certification withheld (§ The verify gate runs once more after one failure). **Placement.** After a fix round the gate is the phase after `dispatch-audits` (advertised on the audits payload — see that row), or the last phase of the cap round (the cap round completes its audits, its fix step and this gate before the session hands the PR back, and the gate runs on the post-fix head even when the round's earlier gate already passed). A second `fail` or a `timeout` halts before any next panel or scoped finder. **It is the round's one full verify run** — the session's own checks while it applies fixes are scoped, never this command. |
| `apply-fixes` | The build session applies the fixes itself, as it fulfils `run-verify`; no fixer agent, fix order, order file, envelope stub, orders manifest, order lint or locked-down fixer sandbox takes part. `payload` carries `batch` (the blocking findings the driver selected), `fixBatchPath`, `guidancePath`, `startHead`, `landingPath` and, only when one is staged, `prBodyPath` — their shapes, the report and the fold checks are in § The `apply-fixes` step below; what the session does is `auto-fix-loop.md` § Applying the fixes. Submit `{fixes, unfixed?, coverageDecisions?, headDiff? \| headDiffPath?}` — `fixes` is the one required key; `coverageDecisions` is a list of coverage-decision objects the driver accumulates into `state["_coverage"]`. The step folds on whichever path the session already uses, like every other phase: a hand `submit` on a hand-path session, or the report written to `landingPath` and `advance` on a durable-record session. A session that has used one path refuses the other (`advance-submit-interleaved`). The driver derives the post-fix diff itself (`git diff <pinned baseRef>...<fix-fold head>`), never from the session's report. A supplied `headDiff` (inline) or `headDiffPath` (an **absolute** file path the driver reads itself; inline wins if both are present) is a cross-check, produced by the **guarded per-round command in the SKILL's Setup** (`git diff "$BASE_REF"...HEAD` against the **pinned remote base commit** — never a local branch name, and never a bare copy without Setup's failed-diff and empty-diff halts; if `$BASE_REF` is not in this shell, restore and re-validate it first). A supplied diff that differs from git's (line endings aside) stops the round with `head-diff-mismatch`; git unable to read the head beside a supplied diff stops it with `head-diff-unverifiable`; a non-absolute `headDiffPath` is refused before the fold (the step stays pending; resubmit with an absolute path or without the key), while a missing or unreadable absolute `headDiffPath` is recorded as `supplied-unreadable` and git governs; submitting none is allowed. A fix round whose diff git supplies audits its fixes. A derivation that fails with nothing supplied is an **unknown surface** → the next round hands the PR back (`fix-surface-unknown`), never an empty diff, never a panel and never a silent scoped skip. Each round records `headDiffSource: git\|inline\|path\|unknown` (`inline` and `path` only in a run with no repository) and `headDiffCheck: match\|mismatch\|none-supplied\|supplied-unreadable\|unverifiable\|no-repository`. The changed policy subjects the review record carries are **derived by the driver itself** from the reviewed-vs-head diff through the accumulated findings (the injectable `changed_subjects` seam — library default + CLI wire the real git derivation); a self-reported `changedSubjects` is ignored on the live path. **Batches.** `payload.batch` carries at most `fixBatchCap` findings (default per § Round economy), with one exception: a slice that would cut through a fix group takes the rest of the group, so it may exceed the cap by those members. The batch is closed over fix groups: when one member is in it, every other member is added, a non-blocking one included, and the queue's filters still apply to each. A larger blocking set is set as consecutive `apply-fixes` steps in the same round, each folded on its own, and the round's audit targets derive from the whole batch. Each member of a fix group keeps its own audit target and its own break-it test comparison; the group's one fix is judged against each member's own test. **The restore step.** After an audit lists a target in `testMismatch`, the driver sets a restore-only `apply-fixes` step in place of the fix batch: `payload` carries `restoreOnly: true`, `restores` (one `{findingKey, path, content, sha256}` per mismatched target, `content` the test role's version), `startHead` and `landingPath`, and no `batch`, `fixBatchPath` or `guidancePath`. The build session writes each file byte for byte, commits (a commit that carries only the test is right here), makes no other change, and submits `{fixes: []}`. The report takes no `unfixed` and no fix binding (it is refused, the step staying pending). One check, `_restore_commit_fault`, judges the commit at the submit chokepoint, in `run_loop` and in the fold: git (or the `fix_commits` seam, asked for `HEAD`) must show every `restores` path holding exactly its `content`, at a head that is reachable and new since the step started. The restore is no fix: it is not in the fix batch, not audited, not credited, and the head-diff derivation does not run. A restore that fails the check, or a mismatched target whose finding carries no readable block or no test role's version, hands the PR back as `break-it-restore-failed` (decided before any step is set in the second case). The fold records `testRestore` on the round (`{findingKey, path, source: "reviewer" \| "corrected", restoredHead}`) and decides `break-it-test-restored`. The pending restore lives in driver state (`_testRestore`), so a resumed session's `next` sets the same step again. |
| `terminal` | Stop looping; read `payload.verdict` and `payload.certification`; surface honestly in the End-of-Loop Summary. |

### The `apply-fixes` step

The `payload` of `apply-fixes`:

- `batch` — the findings to fix, the rows `fix-batch.json` holds.
- `fixBatchPath` — `round-<N>/fix-batch.json`, or `fix-batch.<i>.json` for a later slice.
- `guidancePath` — `round-<N>/fix-guidance.md` (or `fix-guidance.<i>.md`), the owner or advisor guidance for the batch's findings, or `null`.
- `startHead` — HEAD when the step was set; `null` when the session has no repository root.
- `landingPath` — the bare-payload landing for the `advance` path.
- `prBodyPath` — the staged PR body, `<session>/pr-body/staged.md`; present only when one is staged.

The report is a JSON object. `fixes` is required and is a list; `unfixed` and `coverageDecisions` are optional lists of objects:

- `fixes` — an entry `{"finding": <the finding's key or staged id>, "commit": <full sha>}` binds a finding to the commit that fixed it. The binding is **required** for every finding that carries a break-it test, and the fixed members of one fix group are bound to the same commit. Other entries may be plain notes. An object entry with a `finding` key or a `commit` key must give both as non-empty strings; an object with neither key is a note. The round records each verified binding with the commit's full resolved sha, whatever expression the report gave.
- `unfixed` — `{"finding", "why"}`, both non-empty strings, for a finding the session could not fix, for example one that needs a judgment call it cannot make. Such a finding is not credited as fixed, and the next audit judges it.
- `coverageDecisions` — as in the table row.
- `headDiff` (a string) / `headDiffPath` (an absolute path) stay optional cross-checks.

**What the driver checks before folding.** A hand `submit` first checks the report's shape; a malformed report is refused with the field-naming reason the payload contract gives (for example `` `fixes` is missing ``), with no `detail`, and the driver journals `apply-fixes-shape`. The driver then derives what was committed from git, never from the report. A refusal leaves the step pending, with the same phase and attempt, so the session fixes things and folds again. For each batch finding that carries a break-it test and is not listed `unfixed`:

- the report must bind it to a commit;
- that commit must be known to git and reachable from HEAD, and not reachable from `startHead`;
- the test must sit at the block's path with the block's bytes: the commit's own file when the commit adds or changes that path, else the file at `startHead` when it was already there with those bytes (a later round's repair of the same finding), else the commit's file;
- that commit must change at least one path other than the test.

When a finding has several bindings, one that passes is enough; a refusal names the first binding's reason. A failed check refuses `fold-refused` with `detail` `fix-without-break-it-test:<finding key>:<why>`:

| `<why>` | Meaning |
| --- | --- |
| `no-binding` | no `fixes` entry binds the finding to a commit |
| `commit-unknown` | git does not know the bound commit, or it is not reachable from HEAD |
| `commit-not-in-step` | the commit is reachable from `startHead`, so an earlier step made it |
| `test-missing` | there is no file at the block's path where the check above looks |
| `test-bytes-differ` | the file at the block's path does not hold the block's bytes |
| `no-fix-change` | the commit changes no path other than the test |
| `unverifiable` | the driver could not read git: the session has no repository root, base reference or step start head |

Two group checks run after the per-finding checks, for the members of one fix group in the batch. A group with some members listed `unfixed` and others not refuses `fix-group-split:<group id>`: fix all of the members or list all of them `unfixed`. A group whose fixed members have no single bound commit that passes every member's test check above, or whose shared commit changes only the members' tests, refuses `fix-group-no-shared-commit:<group id>`. After a shared fix, if the audit clears one member and leaves another open, the open one's repair runs alone; the cleared member stays protected by the converge-time kept check below, which runs every fixed break-it test at the final head.

Three other refusals exist. A `fixes` object that has a `finding` key or a `commit` key without both being non-empty strings refuses `fix-binding-malformed:<index>` (its position in `fixes`, from 0) before any lookup; the step and attempt stay unchanged. The other two name the value as the report gave it: a `fixes` entry with a `finding` and a `commit` whose `finding` is neither a key nor a staged id of the batch refuses `fix-finding-unknown:<value>`, and an `unfixed` entry whose `finding` is outside the batch refuses `unfixed-finding-unknown:<value>`; the `unfixed` list is checked first. A step with no commit at all is not a refusal; a PR-body-only fix makes none. The converge-time check that each fixed finding's break-it test is kept in the final diff and passes is unchanged.

**Who is a maker.** The build session is a maker of every fix it applies. The family the driver bars from auditing a fix is the build session's family: the seat map's host family, else its author family, read at session start and mapped to the registered vendor whose models sit in that family (`model_registry.family_for`). Without a seat map, or when no registered vendor sits in that family, that family is unknown, and the audit runs as a disclosed degraded audit. A `fixerVendor` already given is kept. The review record lists the build session's family among the makers, with source `build session's fixes`.

### The verify gate runs once more after one failure

At every `run-verify` gate, the first `fail` does not halt. The driver records that run and sets the same gate again at the next attempt, and the second result decides: a `pass` goes on as a first-time pass does, and any other result halts as it does without a re-run. A re-run that passes but ran at a different head than the first run halts, with decision `verify-rerun-head-moved`; a head unknown on either side is not a difference. A re-run that passes on different working-tree contents than the first run saw halts the same way, with decision `verify-rerun-tree-changed`. The contents are the tracked changes against HEAD plus every untracked file that is not ignored, each with its bytes, so a new file that appears between the runs counts and ignored build output does not. A file that cannot be read gives no digest, which the driver treats as no evidence either way, as it treats a head it cannot read.

- Only `fail` starts a re-run, once per gate. A `timeout`, a skip or an unknown result halts as before, and so does a first `fail` whose own run straddled a head change (`headShaAfter` differs from `headSha`).
- Both runs are recorded on the round as one `rerunChecks` entry, `{"check": "verify", "runs": [<run>, <run>], "decision": <decision>}`, with `"heads": [<earlier>, <later>]` added when the decision is `head-moved`. Each run carries `status` (`ran`, `timed-out` or `not-started`), `exitCode`, `output` (the tail of the run's output), `reason`, `head` and `headSource`. The review record shows them.
- The driver decides once, when it folds the second run, and records the decision on the entry: `went-on` (a pass at one head on one set of contents), `head-moved`, `tree-changed`, or `failed` (the second run did not pass). The review record reads that decision and never works it out again: its re-run line says "on unchanged code" only for `went-on`, names the two heads for `head-moved`, says the second run saw changed working-tree contents for `tree-changed`, and says nothing about the code for `failed` or for an entry with no decision (a record an earlier version wrote).
- `run-verify` records the head it ran at, `headSha`, and the working-tree digest it ran on, `treeSha`, plus `headShaAfter` when HEAD moved while the command ran and `treeShaAfter` when the contents changed while it ran.
- The driver cannot tell from a project's verify command which code a failure sits in, so the re-run follows any first failure. A failure the round's own change caused fails again and halts.

## The re-dispatch carry

A finding the loop re-dispatches in a later round never reaches the fix step as its original text alone —
every `fix-batch.json` row carries `priorAudit` and `gateRuling` as above; the
guidance file renders the latest guidance ruling on any finding in the batch
from any earlier round, marked `Ruled in round N`; the routing site (`_fold_audits`) does not know
about it — the materializer does; history rows are keyed
by `findingKey` (the marker the writers stamp on audit rows and on a resumed session's `judgmentDispositions` entries;
`session_contract.finding_identity_key` is the one derivation), never by a row's `id`. **Limitation,
stated plainly:** the carry reads the live loop record (`state.rounds`) of the current session
only; a records file is an export and is never read back, until a disposition ledger owns a
finding's history.

## Transition — plugin versions under a live session

Never downgrade the plugin under an in-flight review session; finish or discard the session first.

A session's state can carry ids, keys, and fields a driver that did not mint it does not read (for
example the finding keys this driver mints), so resuming under a plugin other than the one that
minted the session can apply the wrong disposition. Recorded rows that carry no cited-head
derivation are read as they were recorded, not refused.

**A session of generation 6 at state version 5 finishes; every other earlier session is not
continued.** State the driver mints carries `sessionGeneration`, set to the integer `7`; the key is
written only when state is minted and is never added to a loaded state. Generation 7 is current.

An unfinished session of generation 6, at the current state version, `5`, is not refused. It
finishes under the round cap it recorded at its start, its stored `maxRounds` (often 7). That cap is
applied as the round boundary, with no ceiling above it and no owner gate. A session of generation 6
that is waiting at a retired gate hands back: waiting at the judgment gate, it ends `handed-back` /
`owner-choice-open`, and the gate's findings show as owner-choice leftovers; waiting at the stall
menu, it ends `handed-back` / `fix-keeps-failing`. Its `sessionGeneration` stays `6` on disk.

A saved state is from an earlier generation that is not continued when it is a JSON object whose
`sessionGeneration` is absent, is not an integer, or is an integer other than `7` and other than
`6` (`5` and older included), or whose `sessionGeneration` is `6` and whose `schemaVersion` is not
`5`; or whose `schemaVersion` is an integer the driver still supports (`2`, `3` or `4`) that is older
than the current state version, `5`. Any other `schemaVersion` (`1`, a later one, a non-integer,
`true`, or `null`) is not such a session: the state loader refuses it as unsupported and no restart
marker is written. While such a session is unfinished (its `terminal` is empty), every driver
command on it — `next`, `submit`, `record-result`, `record-missing`, `advance`, `attest`,
`checkpoint`, `break-it-change`, `rule` and `extra-audit` — answers, before it recovers a commit, reads or writes the
journal, mints a session id, emits an order, records or folds:

```json
{"ok": false, "reason": "session-from-earlier-version", "restart": "fresh-session",
 "alreadyRestarted": false, "detail": "…"}
```

From the command line the exit status is non-zero. The first refusal writes `restarted-on-upgrade.json`
into the session directory, once, by an exclusive create; `alreadyRestarted` is `false` on that call
and `true` on every later one, which leaves the file as it is. If the file cannot be created for any
reason other than already existing, or is created but cannot be written, the command is still
refused, with `alreadyRestarted` `false` and `markerWritten` `false` (a file this call created and
could not write is removed again); `markerWritten` appears only in those two cases. The driver reads only
`loop-state.json` in the old directory and touches nothing else there: no journal row is appended,
and every other file stays as it was; a session lock held by another process answers the usual
`<cmd>-locked` refusal with its `holder`, likewise without a journal row. A finished session of
an earlier generation is left alone: `next` on it returns its terminal answer again. A missing, unreadable, non-JSON
or non-object `loop-state.json` is repaired from its mirror when the mirror can be trusted (§ Session
repair), and otherwise handled by the refusals that exist for those cases.

The caller starts the review again, once, in a fresh session directory: Setup into a new
`$SESSION_DIR`, then Bootstrap from round 1 there. It leaves the old directory as it is and never
edits it to make the session continue.

**A step at `dispatch-fixer` is moved.** The upgrade gate runs first, so the move reaches only a
saved session the driver still continues: one of the current generation, or of the previous
generation finishing under its own cap. A session of an older generation is refused
`session-from-earlier-version` as above and is not moved. When such a session's step, or the action
or phase it has pending, is `dispatch-fixer`, the next command that loads it clears the pending
action and sets `apply-fixes`; the next `next` emits it at a fresh attempt. The start head is
`_fixStepHead`, taken from the old order's anchor (the head the old order was emitted at, so commits
a fixer already made count), else the current HEAD. It still finishes under the round cap it
recorded. The driver journals `fix-step-migrated`, with the old attempt.

## Session repair

Every write of `loop-state.json` is followed by a write of `loop-state.mirror.json`: the exact state
bytes, their sha256, and the session id from `meta.json` (or null when there is none). The two-phase
commits stage both files together, so no commit installs a state without its mirror.

A locked command repairs a damaged state before it reads one: `next`, `submit`, `rule`,
`record-result`, `record-missing`, `advance`, `attest` and `checkpoint` each take the session lock,
replay any sealed commit, and only then check the state file. One that reads as a JSON object is
left alone. One that is missing, unreadable, not JSON, or not an object is restored from the mirror
byte for byte, and the journal gets one row, `cmd: "repair"`, `outcome: "session-repaired"`, naming
the `damaged` kind and the restored state's `round`. The session then carries on from the last
committed write, with every finding, disposition and outcome it held.

The mirror restores only when it parses, names the mirror schema, hashes to the hash it carries,
holds a JSON object of a supported `schemaVersion`, and names the same session id as `meta.json`
(when both name one). A mirror of an unfinished earlier-version session is never restored: the
command gets the `session-from-earlier-version` restart refusal. Any other mirror that fails a check
changes nothing, and the command meets the refusal it always met. A read outside the lock (the
fresh-state checks of `--vendors` and `--seat-map`) never repairs.

**Not covered:** a damaged journal or disposition ledger, and a session whose state file and mirror
are both damaged. The mirror is also not part of the attestation digest: it is rewritten with every
state write, like the state file.

## Journal and receipt

**Journal (`driver-journal.jsonl`).** One JSON object per line: `{cmd, phase, round, attempt, outcome, ts}`.
Every `recorded` row carries the complete revision identity — `payloadSha256`, `casToken`,
`executionEvidence`, `provenance`, `envelopeSha256`, `executionEvidencePresent`, `citedHead` — built
from the stored envelope; a row missing any of them is refused at the write (**`recorded-row-incomplete`**
inside a commit); a sweep or reappend whose store record cannot be read refuses
**`recorded-row-store-unreadable`** and journals nothing. A write run's execution stamp is
`execution-only` (one home, `session_contract.evidence_binding`) — it proves the run happened under
the order and never proves the transported payload; every other result kind is `payload-bound`.
Outcomes include `refused-base-guard` when `next` is rejected by the base guard before round work.
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
session already at its terminal step — returns the stored terminal pending again WITHOUT re-running
`_finalize_receipt`, so a receipt fault recorded/surfaced *after* the receipt was first written (the
`driver-journal-fault.jsonl` marker, or a `round-receipt.json` that has become unreadable/invalid
since) would be masked by the replay's `ok`. So **every** terminal `next` — the first emission and
every replay — re-verifies receipt integrity before answering: the fault-marker's presence and
`validate_receipt` over the on-disk `round-receipt.json` **re-read fresh from disk** (never a cached
copy). Any fault → the CLI answers `{"ok": false, "reason": "receipt-fault", "detail": …}` with a
**nonzero exit** (never `terminal`-with-ok), the same fail-loud family as `journal-fault-unrecordable`.

When the driver cannot continue — a refusal, a park, `journal-fault-unrecordable`, `receipt-fault`,
or any other halt — park citing the blocker and never hand-drive the remainder; `rubric/review-discipline.md`
is the home for the driver-or-park valve.

A session the orchestrator abandons, because it will not drive the loop to a terminal, still writes its
review record in PR mode from the session: `python3 -B "$ROOT_DIR/lib/review_record_session.py" write
--session-dir "$SESSION_DIR" --extras <extras file> --repo-root <repo root> --abandoned "<why>"`. The record
reads `not-reviewed` and names the reason; see [the full lane writes it from the
session](review-record.md#the-full-lane-writes-it-from-the-session). Never hand-build an account for an
abandoned session.

**Receipt (`round-receipt.json`).** Required keys (shape-checked by `validate_receipt`, fail-closed):

- `schemaVersion` — one of `SUPPORTED_STATE_VERSIONS` in `lib/round_driver.py` (`validate_receipt` accepts all). It is the **state's** version,
  not a constant: a session bootstrapped at v2 still terminates to a v2 receipt, while a fresh session
  emits the current `STATE_SCHEMA_VERSION`. State v5 lands `seat-result/2` envelopes carrying `provenance`
  (required) and `executionEvidence` (optional), bound together by `envelopeSha256`; sessions at v2–v4
  continue to land `seat-result/1`. No stored state field is removed at the bump, so in-flight lanes
  complete on their recorded version.
- `verdict` — the terminal verdicts the driver writes are `converged`, `handed-back`, `halted` (the verify gate failed or did not run, a head that now needs a larger seat map than the session was composed with, or the library `run_loop` guard tripping; § Certification shapes), `cannot-certify` and the attested `uncertified-manual`. `held`, `stalled`, `capped-with-open-critical` and `capped-with-open-blocker` are never written; a reader meets them only in the state of a finished session of an earlier generation. A `handed-back` receipt names its decision kind (§ Rounds, the cap and handback). The result file maps `converged` to `exit_clean` and every other verdict to `halt`.
- `certificationShape` — e.g. `full-panel-confirmed`, `audited-chain`, or `*-degraded` variants
- `certification` — full block (`shape`, `fullPanel`, `independence`, `base` — `fetched` |
  `degraded` | `not-checked`, optional `note`/`reason`, `shapeDrivers` — sorted
  channel names that fired for the certification shape (the channel names are the `shape_drivers.append(...)` sites in `lib/round_driver.py`))
- `rounds` — per-round `kind`, `seatStatus`, `lensCoverage` (`{ran, expected, floor}` — partial rounds report `floor: true`, never a bare total; the receipt validator refuses a **full-panel-anchored** `converged` claim whose anchor round is floor-marked or missing coverage), `blockingCount`, `verifyResult`, `audits`, `auditProvenance` (`runner-record` | `hand-landed-evidence` | `mixed-evidence` | `collection-manifest` — derived from the adapter's per-seat `provenanceSource` on the durable-record path; `collection-manifest` on a hand `submit` at any version — visible at vet), plus one field per disclosure channel in `CARRIED_DISCLOSURE_CHANNELS` (`lib/receipt_disclosures.py`), `unverified`, `authorJustifiedDrops`, `compileDrops`, `selfRecovery`, `stallChoice` (set only when the state recorded one). `judgmentDispositions` carries the per-finding judgment dispositions the state recorded — including free-text guidance on a `fix-with-guidance` ruling, so a finished run's receipt still shows what the owner instructed. `gateGuidanceRowCarried` records when a fix-batch row carried the guidance key while the fold recorded none — never rendered as owner guidance. Each `compileDrops` entry's `reason` is one of `uncited — no file:line`, `line is not an integer` — a non-integer citation is never reported as out of scope; a numeric string is coerced first — `outside the round diff scope`; seams check and scoped finder append their drops to the same channel.
- `findings` — each row carries `id`; `findingKey` is stamped only when the state's
  `schemaVersion` is at least `STATE_SCHEMA_VERSION` — receipt schema versions 2–4 omit it
- `decisions`, `seatMap`, `scriptRan`, `degraded` (disclosure list)

**Seat-map storage.** The driver stores each round's submitted seat map as an append-only
`state["seatMapReceipts"]` list (`{round, map}` entries). There is no shared accumulated
`state["seatMap"]` blob — `_fold_panel` appends one receipt per non-empty submitted map; reads
route through projection helpers (`_seat_map_receipts` and its family). A legacy persisted
`state["seatMap"]` dict, when present, is prepended at read time as `round: "legacy"` (no write-side
migration). `build_receipt`'s `seatMap` is a derived union projection (latest seats, degradations
union by whole-row identity, other keys last-receipt-wins). `--seat-map` at fresh state seeds
receipt round `"0"`.

**Per-round fields and `degraded` disclosures.** Machinery records these on the round when `_fold_panel` (or dispatch-provenance folding) detects them; `_finalize_receipt` mirrors each into a `degraded` line.

| Round field | Set when | `degraded` line |
| --- | --- | --- |
| `fellOpen` | A `run` seat's `ranManifest` vendor differs from the seat map's configured vendor (cross-vendor seat fell open to **the host model**). | `reviewer-fell-open (round N): …` |
| `fellOpenProvenanceMissing` | A cross-vendor seat ran but has no trusted `ranManifest` entry. | `reviewer-fell-open-provenance-unavailable (round N): …` |
| `seatMapUnavailable` | No `seatMap` was submitted while the panel ran (live panel-vendor pool recorded; never empty — `["unknown"]` when unknowable). | `reviewer-fell-open-seatmap-unavailable (round N): …` |
| `seatMapUnjudgeable` | A seat map was submitted and is readable, but its violation basis is incomplete (basis literal(s) recorded). | `seat-map-unjudgeable (round N): …` (terminal `degraded`; `shapeDrivers` includes `seat-map-unavailable` and certification shape uses `-degraded`, not a third suffix) |
| `seatMapViolations` | The submitted seat map carries constraint violation(s) not excused by its own degradation channel. | `seat-map constraint breach: …` (terminal `degraded` list; also recorded per round) |
| *(pin excusal)* | A standing excusable violation was excused because a collapsed seat was owner-pinned (`classify_violations` → `excusedByPin`). | `seat-map pin excusal: seat(s) …` (terminal `degraded`; `shapeDrivers` includes `seat-pin` and certification shape uses `-degraded`, not a third suffix) |
| `vacuousSeats` | Seat dict has `vacuous: true` or `reason: "vacuous"` (empty findings with no verifiable investigation record). The seat folds as `missing` in `seatStatus` — it cannot anchor a `full-panel-confirmed` certification. | `vacuous-seat (round N): …` |
| `orderVendorProvenanceGaps` | An emitted order seat on a `dispatch-review` phase had no **resolved** vendor — absent from the seat map, or `vendorSource: "defaulted"` (a fallback the driver guessed, not evidence). Its order rendered the stdout contract. | `order-vendor-provenance-gap (round N): …` |

- `skippedBlockers` — the dedicated skipped-blocking channel (`{id, title, severity, reason}` per blocker the state recorded as skipped at a judgment step; possibly empty). **Required** (possibly empty) so a receipt can never omit the channel — a converge over any skip is CLEAN EXCEPT FOR SKIPPED, never a plain success, and its certification `reason` leads with `clean-except-skipped: N blocker(s) skipped with citable reasons`.

`validate_receipt(receipt)` returns `(ok, reason)` — a missing `scriptRan.byPhase` or non-list
`rounds`/`findings`/`skippedBlockers` rejects the receipt.

**This summary is deliberately non-exhaustive, and it is not pinned.** The authoritative field set
and the complete refusal enumeration live in `lib/round_driver.py` — the `validate_receipt`
implementation and the round-entry constants it reads (`ROUND_ENTRY_KEY_FORMS`,
`CARRIED_DISCLOSURE_CHANNELS`). Read the code for the full list; do not treat the prose above as
complete, and do not extend it into a second enumeration that would drift.

### Handback scope markers (Claude host, Bash tool)

Two scope markers sit in the worktree's sidecar directory: `build-lane.json` (written by
`lib/build_lane.py` `declare`, from the workhorse charter's full-lane intake step) and
`review-session.json` (written on the driver's first fresh `next`). Both carry a `branch` field.
`lib/review_record.py` reads `build-lane.json` for the lane its record states; no shipped module
reads `review-session.json`. No automated check refuses a handback; the rule for a PR handed back
without a review record is `rubric/review-discipline.md` § The driver mandate — the review record.

## Certification shapes

The names in this section — the receipt's `certification` block, `certificationShape`, and the
`cannot-certify` verdict — say how the loop ended. The loop writes no certificate and nothing waits
on one: what a review rests on is the review record (`skills/review-code/reference/review-record.md`).

| Shape | Meaning |
| --- | --- |
| `full-panel-confirmed` | The round-1 `reviewer-deep` panel converged with no fix to make. |
| `audited-chain` | The finish of every review that needed fixes — the last round's fixes discharged via audits + scoped verification; **no** final full panel. Surface this honestly; never imply a pristine fresh pass. |
| `*-degraded` | Appended when `independence` is degraded — including a fix whose audit did not run because no live vendor sits outside the makers' families, a true single-vendor configuration, base fetch degraded, the seat map disclosed same-family self-review, no usable seat map was submitted (`seat-map-unavailable`), the submitted seat map's violation basis is incomplete (`seat-map-unavailable` shape driver — same token as absent-map), or a standing pin excused a constraint. |
| `*-constraint-violated` | Appended when the seat map carries unexcused constraint violation(s); supersedes `*-degraded` when both would apply. |
| `null` / withheld | Verify fail, a handback (`handed-back`: `round-cap`, `fix-keeps-failing`, `owner-choice-open`, `extra-audit-open`, `fix-surface-unknown`, `break-it-restore-failed`, `later-round-panel-retired`), or `cannot-certify`. |

**Terminals the orchestrator must surface honestly:**

- **Scoped certifying finish** (`audited-chain` / `audited-chain-degraded`) — the review needed fixes and ended on a round's audit and scoped finder; delta rounds verified the fix chain; say so.
- **One recovery attempt** — the same fix failing its audit in two rounds in a row triggers a single recovery attempt, the fix step set again (journaled); nothing is offered to the owner.
- **Handback at the cap** — `handed-back` / `round-cap`: round 4 ended with something open. Every open finding, Important and Critical alike, is listed with its outcome; the PR goes back to its owner.
- **Handback after a failed recovery** — `handed-back` / `fix-keeps-failing`: the fix still fails its audit after the recovery attempt.
- **Handback on an owner's choice** — `handed-back` / `owner-choice-open`: a finding only the owner's choice can settle is still open when nothing else is left to fix. It reaches the owner as a leftover at the vet.
- **Extra audit unfinished** — `handed-back` / `extra-audit-open`: the extra audit round ended with a fix undischarged, an auditor's new issue, or a surface it could not derive (§ The extra audit round).
- **Handback on an unknown fix surface** — `handed-back` / `fix-surface-unknown`: the driver could not work out what the round's fixes changed, so it could neither audit them nor search the code they touched. Every finding keeps its outcome or is shown open.
- **Handback on a restore that failed** — `handed-back` / `break-it-restore-failed`: the audit listed a break-it test as missing, changed without a reason or weakened, and the restore of the test role's version could not be made (the commit did not hold its bytes, added no commit, or could not be read from git; or the finding carried no readable test to restore). Every finding is shown open.
- **Handback of a retired panel** — `handed-back` / `later-round-panel-retired`: a session saved at a round-2-or-later panel, or at the verify gate that was to be followed by one, by an earlier version.
- **Halted** — terminal `halted`, certification withheld, in three cases. The verify gate stops the session (`verify-fail`: the verify command failed, and the one re-run decided it; a re-run that passes at a different head halts too, with decision `verify-rerun-head-moved`, and one that passes on changed working-tree contents (a changed tracked file or a new file that is not ignored) halts with `verify-rerun-tree-changed` — § The verify gate runs once more after one failure; `verify-skip-but-configured`: it reported a skip although a verify command is configured; `verify-unresolved`: its result was neither pass nor skip). A head that now touches a risk area the session's smaller seat map was not composed for stops it (`lane-expanded-recompose`); the review restarts in a fresh session with a freshly composed map. The library `run_loop` stops a loop that has not reached a terminal after its step guard, and writes no decision kind. A finished session of an earlier generation can also read `halted` / `round-ceiling`; the driver no longer writes it.

**Library `recordsPath` / `round-records.json` seam.** When config carries
`recordsPath`, each in-memory ledger record is written through `review_memory.summarize_record` (a
skeleton — no evidence bodies) and carries the declared per-round disclosure block selected by
`_declared_disclosures` from `CARRIED_DISCLOSURE_CHANNELS`. The file is an export of the session's
ledger: the producer writes the whole outgoing ledger as `review_memory.records_bytes` in one atomic
write, replacing whatever was at that path, and the driver never reads the file — a new session
takes nothing from it, and a file left by another session, valid or corrupt, is simply replaced on
the first write. A write the producer cannot complete parks `cannot-certify` rather than
certifying with the export out of step. The `next --records-path` flag sets `recordsPath` on fresh
state only — supplying it on existing state refuses `records-path-not-fresh-state`. The export is
kept outside the session folder, so any path at or inside `$SESSION_DIR` refuses
`records-path-reserved` before any work. On the CLI path the write rides
`cmd_submit`'s `submit-accept` commit as a `targetKind: "round-records"` sidecar, so the file
changes only if that commit sealed and then rolls forward with the state; recovery dispatches
sidecar replay by `targetKind` and refuses rather than falling back. The library
`run_loop` path calls `_persist_round_records` after every fold.

## PR-body findings

A finding about the PR body cites `SUPERHEROES_PR_BODY.md` (`pr_body_stage.CITATION`, the name `sanitized_view` gives the body); compile keeps it in scope though the git diff never holds it. It is fixed only in a staged copy, never on the live PR, and the build session never writes to GitHub while it applies fixes.

- Layout under `<session>/pr-body/`: `original.md` (the body as `pr.json` held it, written once), `staged.md` (the working copy, created from it once) and `published.json` (the publish receipt, written for every outcome).
- The `apply-fixes` payload's `prBodyPath` is `staged.md` itself, present only when a body is staged. The session fixes a PR-body finding by editing that file; the file is never committed. When `next` first emits the step it snapshots the staged file's sha256; the fold records the round's `prBodyFix` `{before, after}`, the sha256 of the staged file at that snapshot and after the session's edit, only when the two differ. Branch mode, or a session with no `pr.json`, has no `prBodyPath`, and the session lists such a finding `unfixed`.
- The audit fold records `prBodyAudited` (the `after` sha) in the audit round only when every audit target of that round folded to an authenticated clearing ruling. The fix folds in round N and its audits in round N+1, so the fold reads `prBodyFix` from the round before.
- `pr_body_stage.py publish --session-dir D --pr N` is the one chokepoint that writes a PR body; the review-code skill runs it after a `converged` terminal. It reads and writes the live body through GitHub's REST API (`gh api repos/{owner}/{repo}/pulls/<n>`, and a `PATCH` with `-F body=@<staged>` for the edit), so it works where `gh pr view` and `gh pr edit` cannot. It writes `staged.md` only when the staged sha256 equals the highest audited round's and the live body still equals `original.md`; it reads the live body back after the edit.
- Outcomes: `published` (also `already-published` on a re-run), `unchanged` (`live-moved` when the live body changed outside the review), or a refusal: `review-not-converged`, `pr-body-not-staged`, `pr-body-live-unreadable`, `pr-body-published-unaudited`, `pr-body-not-audited`, `pr-body-moved`, `pr-body-publish-failed`, `pr-body-publish-unverified`.
- The review record's `checked` list gains one plain sentence from `record_line`; a single trailing newline difference is not a body difference. A review with no PR-body fix (nothing staged, or the staged text unchanged) never says in its record that it did not copy one.

## Invariants

Pinned by `test_round_driver.py` (ported from the retired `test_code_loop_plan.py`):

- Round 1 = full `reviewer-deep` baseline (or a returning round, which runs no panel; see The one
  entrypoint); it is the only round that can run a panel. Unknown changed
  surface → handed back (`handed-back` / `fix-surface-unknown`), never a blind skip and never a panel.
- Every later round = the fix auditor over each fix plus the scoped finder over the fixes' own
  diff; a review that needed fixes converges on such a round (`audited-chain`).
- Audit-keyed stall breaker (`circuit_breaker.check_audit_breaker`) — not the old per-finding
  `circuit_breaker.py "$SESSION_DIR" 7` call inside the loop; the driver owns stall/self-recovery.
  Criterion 2 (`audit-stall`) evaluates the **last two** audit rounds only — an honestly-folded
  clean round resets the window; it triggers the one recovery attempt, and a stall that persists
  hands back (`fix-keeps-failing`). The round cap is a boundary on the round about to begin, and
  **no session's round counter exceeds the cap**. Callers
  of `advance` must not treat `ok: true` from a nested `cmd_submit` as a landed fold unless
  `foldLanded` is set; the `notFolded` receipt names why.
- `REDISPATCH_BUDGET` reads `loop_plan_common.REDISPATCH_BUDGET` only — never a local literal.
- Fail-closed everywhere: junk in → conservative out; never certify on silence.
- Base guard on every CLI `next`: pinned resolvable base, matching checkout/repo (PR mode), and a
  valid non-empty round diff on fresh state — pinned by `lib/tests/test_review_base_guard.py` and the
  CLI-gate tests in `lib/tests/test_round_driver.py`.

## Port note

Layer 1 (`run_loop`) is the one-entrypoint loop orchestration with injectable seams (`reviewer`,
`synthesis`, `verifier`, `auditor`, `fix_step`, `verify_runner`, `changed_subjects`, `io`);
Layer 2 (`next`/`submit`) is the state machine between orchestrator dispatches. Parity is locked
by the goldens in `test_round_driver.py` and the PARITY receipt in `test_retry_budget_parity.py`.
Treat `round_driver.py` as the contract of record. The `verifier` seam may return `{"verdicts": [...],
"vendor": v}` and the seams-check and scoped-finder `reviewer` calls `{"findings": [...], "vendor": v}`
to report the vendor that ran; a finder result that reports a vendor other than the driver's
selection (or an ineligible one), or reports none when the selection replaced the reviewer engine,
parks the loop `cannot-certify` instead of folding.

**`run_loop` return contract.** `run_loop` drives the scripted seam path end-to-end and returns the
driver's terminal receipt, built from the loop state alone (`_driver_receipt`,
`lib/round_driver.py`).

**Leaf modules (`record_paths`, `receipt_disclosures`).** Pure vocabulary and path helpers live in
two leaf modules the driver does not own:

- `receipt_disclosures` — disclosure-channel registry, per-round selection rule, degraded-prose
  collector, and certification-shape inputs. `round_driver` imports and re-exports its `__all__`
  names as aliases (same function objects — drift-tested by `test_receipt_disclosures_home.py`).
- `record_paths` — `storage_key` and `store_path` for seat envelope filenames. `round_records`
  imports from here.

A drift-tested copy in a consumer is not a second home. Shared pure functions live in the leaf
module its consumers import.

**Which builder produces which artifact.** `build_receipt` produces `round-receipt.json` at terminal. `build_interim_receipt` is the loop's
progress artifact on the CLI `checkpoint` path and the durable-record `advance` path.
