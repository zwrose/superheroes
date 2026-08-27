# Contents

- [The one entrypoint](#the-one-entrypoint)
- [next / submit protocol](#next--submit-protocol)
- [checkpoint](#checkpoint)
- [Durable-record path](#durable-record-path)
- [Base guard](#base-guard)
- [Batch concurrency — an independent batch goes out together](#batch-concurrency--an-independent-batch-goes-out-together)
- [Lens coverage beside counts](#lens-coverage-beside-counts)
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
cross-cutting rework) or when the changed surface is **unknown** (fail toward run-everything). On
the **auto-fix loop**, the orchestrator never plans, records, or decides continuation by eye — it
calls `next`, dispatches the emitted order (or fulfills a gate action), and `submit`s the
artifact. **Prose-driven review** on the read-only path (`--review-only`) is a different
lane with its own receipt obligation — see `rubric/review-discipline.md` § Prose-driven review; it
is not governed by this loop contract.

The review auto-fixer's file-scope guard answers `{"allow": false}` for
`lib/round_driver.py` because the driver is **safety machinery**
(`lib/escalation.py:92-126` — the safety-machinery set, which names `round_driver.py` explicitly
with the `#507` reason), so a review of the driver's own source **escalates those findings to the
orchestrator as implementer work instead of self-fixing** — that is **intended**, not a gap: a
fixer that could edit the loop's own driver could edit away the guard that constrains it.

Degraded / single-vendor environments stay **on** the mandated path: the same driver, the same
journal, and `independence: "degraded"` stamps on audit targets and the terminal certification
shape — never a silent off-ramp.

## next / submit protocol

Fresh state (first `next` of a session):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/round_driver.py" next \
  --session-dir "$SESSION_DIR" \
  --diff-path "$SESSION_DIR/round-1/diff.txt" \
  --verify-command "${VERIFY_CMD:-none}" \
  --max-rounds 7
```

Every step thereafter:

```bash
python3 -B "$ROOT_DIR/lib/round_driver.py" next --session-dir "$SESSION_DIR"
```

`--diff-path` belongs only on the first `next` of a session (#699 rider 6). A continuation
`next` that passes it is refused with `diff-path-not-fresh-state` — check raw stdout and the
driver journal; the driver does not crash.

**Why session-birth only.** The first `next` binds the round-1 diff artifact into session state
(`config.diff`, `reviewedDiff`, and the base-guard stat binding). Rounds 2+ regenerate the diff
from the shell per `SKILL.md` Setup; the driver refuses a later `--diff-path` because swapping the
round-1 artifact mid-session would break the pin/stat contract the base guard stamped at birth.
Same discipline as `--vendors` / `--fixer-vendor` on non-fresh state.

**`--seat-map <path>`** carries the #510 seat map into round 1 and is subject to that same
fresh-state discipline. The file must be a JSON **object** shaped `{"seats": {"<dimension>":
{"vendor": "...", "model": "...", "engine": "..."}}}`, keyed by the full reviewer dimension names —
an unreadable file, malformed JSON, or a non-object all fail loud with `seat-map-unparseable`,
never a silent fall-through. It is what lets round 1 resolve each seat's vendor: the panel artifact
that otherwise supplies the seat map does not exist until the panel has already been dispatched.
See § Emitted orders for what an unsupplied map does to each seat's output contract.

After fulfilling the emitted action, fold the artifact:

```bash
python3 -B "$ROOT_DIR/lib/round_driver.py" submit \
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

## checkpoint

Orchestrator-invoked verb at a **non-terminal** stop — like `next`, `submit`, and `advance`, the
driver does not observe tripwire doctrine itself; the orchestrator decides the stop and calls
`checkpoint`.

```bash
python3 -B "$ROOT_DIR/lib/round_driver.py" checkpoint \
  --session-dir "$SESSION_DIR" \
  --stop-reason <tripwire|park|held>
```

`--stop-reason` is required; the only accepted values are `tripwire`, `park`, and `held`
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
with `--stop-reason` matching the stop: **tripwire** (third-rework tripwire), **park** (owner gate
park before the owner rules), or **held** (stall menu — certification not yet folded; the
orchestrator checkpoints progress before the hold choice is submitted). Once the hold fold sets
`terminal = "held"`, `checkpoint` refuses (`checkpoint-session-terminal`) and the terminal
`round-receipt.json` (full `rounds` record, `verdict: "held"`) is the record from then on. These are
orchestrator doctrine; the driver only validates the reason against `CHECKPOINT_STOP_REASONS`.

**Terminal receipt preserved.** `cmd_checkpoint` refuses when the session is already terminal
(`checkpoint-session-terminal`) or when a **terminal** certified/attested receipt sits on disk
(`checkpoint-terminal-receipt-exists`). Re-invoking `checkpoint` after an earlier interim receipt is
allowed — each write supersedes the previous interim. The write-once rule applies only to terminal
receipts, not interim supersession.

**Not handback evidence.** `handback_gate` refuses an interim receipt at the receipt-binding check
with `receipt-interim-not-handback-evidence` — progress evidence for the operator, not valid
handback.

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
python3 -B "$ROOT_DIR/lib/round_driver.py" next --session-dir "$SESSION_DIR"
# … dispatch seats, compile artifact …
python3 -B "$ROOT_DIR/lib/round_driver.py" submit \
  --session-dir "$SESSION_DIR" \
  --phase "<phase from next>" \
  --attempt <attempt from next> \
  --state-hash "<expectedStateHash from next>" \
  --artifact "$SESSION_DIR/round-<N>/<phase>-artifact.json"
```

**Durable-record path** (panel and other record-capable phases):

```bash
python3 -B "$ROOT_DIR/lib/round_driver.py" next --session-dir "$SESSION_DIR"
# … dispatch seats; each seat lands under landing/ …
python3 -B "$ROOT_DIR/lib/round_driver.py" record-result \
  --session-dir "$SESSION_DIR" --seat "<seat>"  # or: record-result --sweep
# … record-missing for any slot that forfeit/timeout …
python3 -B "$ROOT_DIR/lib/round_driver.py" advance \
  --session-dir "$SESSION_DIR"
```

No `submit` on this path — `advance` echoes `expectedStateHash` itself; do not pass
`--state-hash`. **Orchestrator-fulfilled phases** (`run-verify` — see
`round_adapters.ORCHESTRATOR_FULFILLED_PHASES` / `is_orchestrator_fulfilled`) also fold through
`advance` from the host-seat **bare payload** at
`$SESSION_DIR/round-N/landing/<phase>/<skey>.a<K>.payload.json` — no orders manifest, no anchor,
validated through the phase's existing submit-shape guard. An accepted fold **writes that slot's
durable `seat-result/1` record in the same commit**, so both fold paths leave the same
reconstructable per-seat provenance. Named refusals:
`orchestrator-payload-missing`, `orchestrator-payload-unreadable`, `landing-ambiguous` (a bare
payload beside a durable seat record — two claims for one slot; the shape guard's fault is reported
first when the payload is also malformed; recover by deleting whichever artifact is not the one you
meant), `bootstrap-required` (no session id in `meta.json` — the record could not carry its session
provenance, so nothing is folded; recover by restoring the session id, which `next` mints), and the
shape guard's own fault. `manifest-anchor-unanchored` stays reserved for seat phases.

**Owner gates on the durable-record path.** When `advance` parks at `present-judgment` or
`present-stall-menu` because gate policy has not pre-authorized the resolution
(`advance-judgment-park` / `advance-stall-park`), fold the owner's choice with `--owner-artifact` —
the same JSON **object** shape hand `submit` takes for that gate: `{"dispositions": [...]}` for
`present-judgment`, `{"choice": "<stall choice>"}` for `present-stall-menu`. The fold runs through
the same `cmd_submit` chokepoint as every other fold (echo, state-hash, terminal-receipt gate, round
ceiling, stall guards `stall-choice-retired:<name>`, `stall-choice-not-offered:<name>`,
`stall-choice-missing`, `stall-accept-risk-not-eligible`). The resolution is journalled as **owner-supplied**: the
`policyApplied` record carries `source: "owner-supplied"` (calibration-resolved carries
`source: "gate-policy"`) plus `artifactSha256` naming the artifact folded, on the fold's own commit.

```bash
python3 -B "$ROOT_DIR/lib/round_driver.py" advance \
  --session-dir "$SESSION_DIR" \
  --owner-artifact "$SESSION_DIR/round-<N>/<phase>-artifact.json"
```

**Refusal tokens when paths interleave.** One token can be returned by more than one command — the
token names the seam, not the direction.

| `reason` | condition | recovery |
| --- | --- | --- |
| `owner-artifact-terminal` | session already terminal and `--owner-artifact` supplied | read `terminal` from `next`; do not fold |
| `advance-submit-interleaved` | a hand `submit` after any `advance` in this session (`_advanceUsed`) | use `advance` |
| `advance-submit-interleaved` | an `advance` (including `--owner-artifact`) after any hand `submit` in this session (`_submitUsed`; the artifact file is never read) | compile and hand-`submit` this phase |
| `advance-submit-interleaved` | `--owner-artifact` supplied while the pending phase is a **seat** phase (the fence is not loosened) | use plain `advance` on seat phases; on owner gates use `--owner-artifact` instead of hand `submit` on an advance-path session |
| `owner-artifact-unreadable` | `--owner-artifact` path missing or JSON unparseable | fix or recreate the artifact file |
| `owner-artifact-shape` | `--owner-artifact` parses but is not a JSON object | resubmit a JSON object per gate shape above |
| `record-submit-interleaved` | a `record-result` / `record-missing` after any hand `submit` in this session (`_submitUsed`) | compile and hand-`submit` this phase — **not** `advance` (this session's latch refuses it) |
| `record-submit-interleaved` | a hand `submit` for a phase that already carries durable store records at the pending `(round, phase, attempt)` on a session that has **not** hand-folded yet (**per-attempt** fence — defers when `_submitUsed` is set) | **`advance`** — **except** on a refuse-fold phase (`dispatch-synthesis`, `dispatch-gap-sweep`, `dispatch-scoped-finder`, `run-verify`, `dispatch-fixer`) whose only store record is a `seat-missing/1` envelope: there `advance` answers `assemble-refused` / `missing-seat-refuse-fold:<seat>`, and the slot must first be replaced via `record-result --supersede --expect-sha256 …` |

**Owner-artifact refusal causes** (authoritative list — drift-tested against `round_driver`
`OWNER_ARTIFACT_*_REFUSAL` constants):

```text
owner-artifact-terminal
owner-artifact-unreadable
owner-artifact-shape
```

**Policy-applied sources** (authoritative list — drift-tested against `round_driver`
`POLICY_APPLIED_SOURCE_*` constants):

```text
gate-policy
owner-supplied
```

**No dead ends.** Whichever fold path a session has committed to, that path's fold command stays
legal for the pending phase: `_submitUsed` → hand `submit`; `_advanceUsed` → `advance` (including
`advance --owner-artifact` at owner gates when gate policy parks); neither latch → `advance` when
durable records are present, hand `submit` when they are not. Owner gates (`present-judgment`,
`present-stall-menu`) still park with `advance-judgment-park` / `advance-stall-park` when
calibration has not pre-authorized the resolution, but that park is **not** a dead end on an
advance-path session — pass the owner's artifact with `advance --owner-artifact`. `record-result` /
`record-missing` are legal only on a session that has not hand-folded.

When a hand-path session (`_submitUsed`) still carries durable records at the pending slot from
before the entry-point latch existed, hand `submit` proceeds and journals `record-orphans-ignored`
with the slot label(s) — the records are deliberately ignored, not silently dropped.

**Durable-record artifacts** (round `N`, phase `P`, attempt `K`, storage key `skey`, vendor `vendor`):

| Artifact | Path | Producer / what absence does |
| --- | --- | --- |
| Dispatch manifest | `$SESSION_DIR/round-N/landing/P/_dispatch.aK.json` | **Orchestrator** — never written by the driver; read only by `advance` on **seat** phases. Top-level JSON keyed by the **exact roster seat key**; each value requires non-empty `vendor` (`model` / `engine` are optional, descriptive, neither validated nor trusted — `round_adapters._trusted_vendors` reads only `vendor`). **Orchestrator-fulfilled phases** (`run-verify`) emit no manifest — `advance` folds from the host bare payload instead. **Absence on a seat phase:** the manifest key is omitted, the adapter discloses `dispatchManifestUnavailable`, and on `dispatch-audits` a clearing ruling (`discharged` / `discharged-but-new-issue`) is **not authenticated** — fails closed to `not-discharged` + `unauthenticated`, which can drive the audit stall and `advance-stall-park`. Check this file first on an unexplained fix-audit stall. |
| Canary probe | `$SESSION_DIR/round-N/landing/dispatch-panel/_canary/vendor.aK.json` | **Orchestrator** (`seat_canary.py probe`) — panel phase only. Carries the cross-vendor control-probe result `advance` folds as `canaryResult`. **Absence:** no canary evidence; when every cross-vendor seat that ran returned zero findings, the round records `canaryUnverified` instead of `canaryVerified`. |
| Seat store | `$SESSION_DIR/round-N/seats/P/skey.aK.json` | **`record-result`** / **`record-missing`** / `advance`'s sweep — the durable `seat-result/1` or `seat-missing/1` envelope for one roster slot. **Absence:** the slot is incomplete; `advance` refuses **`incomplete-roster`** until every slot has a store record or a missing envelope. |
| Head-diff store | `$SESSION_DIR/round-N/seats/P/skey.aK.headdiff` | **`record-result`** on the fixer phase — the driver-owned post-fix diff blob referenced by the stored envelope's `headDiffStorePath`. **Absence:** fixer fold treats the changed surface as unknown (full panel on the next round), never a silent scoped skip. |

## Emitted orders

Every `next` whose `phase` starts with `dispatch-` emits, atomically in one `orders-emit` commit:

- one **order file** per roster slot (`round_orders.render_order` over `rubric/orders/<phase>.md`);
- one **envelope stub** per slot (`seat-result/1` header fields knowable at emission — session,
  round, phase, seat, attempt, vendor, model, `dispatchRef`, `orderSha256`, `manifestSha256` — but
  not `recordedAt` / `payloadSha256`);
- an **orders manifest** listing every slot's `orderPath`, `envelopeStubPath`, and hashes.

Paths (round `N`, phase `P`, attempt `K`, storage key `skey`):

| Artifact | Path |
| --- | --- |
| Order | `$SESSION_DIR/round-N/orders/P/skey.aK.md` |
| Envelope stub | `$SESSION_DIR/round-N/orders/P/skey.aK.envelope.json` |
| Manifest | `$SESSION_DIR/round-N/orders/P/manifest.aK.json` |

**Landing shapes** (`round_records.ingest_landing`):

| Seat kind | Landing path | What the seat writes |
| --- | --- | --- |
| **Engine** (`codex`/`cursor`) | `.../landing/P/skey.aK.json` | **Orchestrator** writes the full `seat-result/1` envelope (stub header + payload) from the folded `dispatch-review` stdout result; the engine seat emits JSON on stdout only |
| **Host** (`claude` native subagent) | `.../landing/P/skey.aK.payload.json` | Payload only; driver wraps with the stub at ingest |

Both shapes present → `landing-ambiguous`. The order's landing block names the paths; seats copy
stub header fields verbatim and never recompute hashes.

**Gap-sweep re-emission trap.** A live build lost a debugging cycle to this exact sequence: (1)
`dispatch-gap-sweep` produces a new finding; (2) the driver **re-opens an already-folded phase
with a different roster**, rewriting `orders/<phase>/manifest.a0.json` **in place at the same
`attempt: 0`**; (3) the **prior wave's landing files are still on disk** from the first fold; (4)
`record-result --sweep` (`round_records.sweep_landing`) walks the **landing directory**, not the
manifest, so it finds those stale files, finds they map to no slot in the *current* roster, and
hard-refuses `unknown-seat` for each one; (5) `advance` then refuses too, and the phase is left
**pending** — a stuck session with no obvious cause, because the failure reads as a driver bug
when it is really a directory-vs-manifest mismatch. **Recovery, proven in that build:** move the
prior wave's landing files aside — never delete — keeping only the file(s) that match the current
manifest, then re-run the sweep.

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

The **`seat-missing/1`** shape is deliberately different: it records a seat that produced no artifact
and carries **no** `payload` or `payloadSha256` — instead `reason` (one of `forfeit`, `timeout`,
`refusal`, `killed`, `malformed-output`) and optional `evidence`.

**The order's output contract follows the seat's channel** (`round_driver._seat_channel`, the one
home for the choice): an order names a landing path to **write** only when the seat's transport row
carries a vendor positively known to be a host seat, and every other case — an engine vendor, or a
vendor the driver cannot resolve — renders the **stdout** contract instead. The fold is deliberately
asymmetric, because the two mistakes are not: a host seat handed the stdout contract still returns
its payload for the orchestrator to land, while an engine seat handed a write contract forfeits on
the forbidden write (#767 class). **A vendor the driver DEFAULTED to is not a resolved vendor**: the
reviewer phases (verifiers, gap-sweep, scoped) fall back to an all-claude stand-in when the
engine-preference read cannot answer — `engine_pref.load_engine_prefs` never raises, so that
failure arrives as `refusal_engine_prefs(readError=…)`, and `readError` is what marks it (a
genuinely absent config is `degenerate_engine_prefs()`, whose documented defaults *are* the
configuration). The transport row therefore carries `vendorSource: "configured" | "defaulted"`,
and `_seat_channel` treats a defaulted vendor exactly like an unresolved one — stdout.
Reading a defaulted `claude` as positive host evidence is what handed an engine-dispatched seat the
write contract. Every such fallback is disclosed as `orderVendorProvenanceGaps` (the row carries
`vendorSource` when it has one) — the fold makes the gap safe, not silent. The collector derives
from the **same** predicate the channel folds on, across every `dispatch-review` phase (panel,
verifiers, synthesis, gap-sweep, audits, scoped), so a channel that fell back for want of vendor
evidence can never do so without a receipt. `dispatch-fixer` is outside this rule: it is a
foreground in-place writer, never a `dispatch-review` consumer, and its vendor is unknown by
default (#608).

**Supply `--seat-map` on the first `next` to keep host seats on the direct-write path.** Round 1 is
the round that dispatches the panel, and before this flag the driver's only vendor source was the
panel artifact — which does not exist yet. Without a seat map, no round-1 seat's vendor resolves, so
**every** panel seat renders the stdout contract and the orchestrator lands each payload itself.
That is correct and safe, merely one hop less direct than a native seat writing its own landing
file.

The manifest and per-order hashes are mirrored into state (`_ordersAnchors`) and journaled as
`orders-emitted`; ingestion checks envelopes against that anchor (`manifest-anchor-mismatch` when
they disagree).

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
  orders render (the orchestrator supplies `headDiff` inline or via `headDiffPath` at fixer
  `submit`; the driver then materializes the file the audit/scoped order cites).
- **`round-<N>/fix-batch.json`** — `_ensure_fix_batch_file` from state `_fixBatch` / `fixBatch` when
  the fixer order renders. If the orchestrator pre-writes this file and the bytes differ from the
  driver's re-derivation, the driver **replaces** it silently — do not treat a hand-written
  `fix-batch.json` as authoritative over loop state.

## Base guard

Before any round work, every `next` invocation runs through `lib/review_base_guard.py` at the **CLI
layer** (`next` subcommand), not inside `run_loop`. The library/eval path drives `run_loop` with
scripted seams and no real repo, so a git check there would be meaningless; `review-code` actually
calls `next`, so that is where the invariant is enforced. On refusal the driver prints
`{"ok": false, "reason": ..., "detail": ...}` to stdout, exits **1**, and appends a durable journal
line with `outcome: "refused-base-guard"`.

**Why it exists.** The review diff base used to live only in skill text, and that text drifted. A
live incident put ~6,600 already-merged lines into a review of 2,931 real ones (#637), and an unset
base produced a zero-line diff at exit 0 that the loop certified clean. #641 fixed the text; #648
moved the invariant into the driver so a future text edit cannot reintroduce it. On fresh state the
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
| `diff-path-not-fresh-state` | `--diff-path` passed on non-fresh state (the same discipline as `--vendors` / `--fixer-vendor`) |

**What to do on refusal (by family).**

- **Base / pin / repo / checkout** (`base-meta-unreadable`, `base-not-pinned`, `base-unresolved`,
  `base-pin-moved`, `base-repo-root-mismatch`, `pr-base-repo-unresolved`, `origin-unresolved`):
  re-run Setup's resolve block and check `origin`; confirm `meta.json` has a full commit pin and
  `repoRoot` matches this checkout.
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
phase's result (the fixer after the panel, verification after the fix), and any two dispatches that
would write the same worktree or the same output path. Sequencing on a real dependency is correct;
sequencing an independent batch is the defect this section exists to remove.

## Lens coverage beside counts

**Every reported round count carries its lens coverage** — confirmation rounds at minimum, and any
round whose counts anyone reads or acts on. A round is **complete** when every configured dimension
folded `seatStatus: "run"` and the round records no `vacuousSeats`, no `canaryUnverified`, and no
`canaryFailed`. A round is **partial** when any configured dimension folded `missing`, or the round
records any `vacuousSeats`, or `canaryUnverified`, or `canaryFailed`. Completeness is defined by
the **configured** dimensions, never by the seats that happened to return. Report it as
`<complete>/<configured> dimensions` beside the count, naming the dimensions that did not land.

**A partial round's counts are floors, and are labeled as floors** — never totals.
`2 blocking (floor — 3/5 dimensions; security and premortem did not land)` is honest; a bare
`2 blocking` from the same round is not.

**Trajectory and convergence claims cite complete rounds only.** A trend drawn through partial rounds
reads a queued backlog as a regression and an unexamined surface as clean. Field evidence (the #723
stack's halves, 2026-08-09): two lenses never examined one half across several rounds, so the first
complete round landed their whole backlog at once and read as a new crop — and leg planning was
steered by the partial trend line.

## Actions and payloads

### Owner gates and gate policy (`present-judgment`, `present-stall-menu`)

When the loop reaches an owner-judgment or audit-stall gate, `advance` (the record-layer subcommand
that folds landed seats without a hand `submit`) resolves an **owner-calibrated gate policy** before
parking: the shipped default in `rubric/review-gate-policy.json` (`gate-policy/1`, **zero rules**,
`default: "park"` — pre-authorizes nothing) plus an optional project overlay under `core.md`'s
`reviewGatePolicy` key (sibling of `enginePreferences`, owner-editable through `configure`). Overlay
rules are evaluated **before** the shipped layer; the first matching rule wins. **Judgment is
all-or-nothing** — `resolve_judgment` must find a rule for **every** finding row or the whole gate
parks (`gate-policy-unmatched-class:<class>`). Stall resolution is per stall class
(`stall:accept-risk-eligible` vs `stall:accept-risk-ineligible`). Stall-menu `submit` refuses at
the chokepoint (before the fold, so pending survives and the same attempt/state-hash stays
resubmittable): `stall-choice-retired:<name>` (a **retired** choice submitted by name — never
mapped to a live choice), `stall-choice-not-offered:<name>` (a choice **not in the menu the
session offered**), `stall-choice-missing` (the submit artifact carries no `choice` at all), and
`stall-accept-risk-not-eligible` (an `accept-the-disclosed-risk` choice submitted when the session
did not mark it eligible).

When no rule matches, `advance` parks (`advance-judgment-park` / `advance-stall-park`). The refusal
carries a `detail` cause distinct from the top-level reason so operators can tell *why* it parked.
On the orchestrator's `next`/`submit` path you still present the gate and submit the owner's choice;
gate policy pre-authorization is what lets `advance` fold without stopping. On the `advance` path
when policy has not pre-authorized, present the gate and fold the owner's resolution with
`advance --owner-artifact` — the `policyApplied` record carries `source: "owner-supplied"` (vs
`"gate-policy"` for a calibration-resolved fold).

**Advance gate-policy park detail causes** (authoritative list — drift-tested against
`round_driver.owner_gate_policy_park_detail_causes()`):

```text
gate-policy-calibration-unreadable
gate-policy-calibration-absent
gate-policy-calibration-refused
gate-policy-calibration-structurally-ambiguous
repo-root-unavailable
gate-policy-judgment-no-findings
gate-policy-unknown-phase
gate-policy-park
gate-policy-no-valid-layer
gate-policy-judgment-input-not-list
gate-policy-judgment-row-not-object
gate-policy-judgment-row-missing-class
gate-policy-unknown-stall-class
```

Parameterized (suffix after `:` is diagnostic detail):

```text
gate-policy-unmatched-class:<findingClass>
```

`gate-policy-calibration-unreadable`, `gate-policy-calibration-structurally-ambiguous`, and
`repo-root-unavailable` may also carry a `: <detail>` suffix when the underlying read failure or
structural ambiguity has a message.

When the review-gate-policy overlay has ambiguous duplicate keys, `advance` parks with
`gate.detail` returned verbatim — `duplicate-policy-key:<key>` where `<key>` is the conflicting
policy key name. The sync test's parameterized fenced block drift-checks only
`gate-policy-unmatched-class:<findingClass>`; this form is documented here in prose instead.

**Ownership boundary (stated narrowly).** The overlay lives on the same ownership surface as
`enginePreferences` — an honest-agent boundary, **not** a security boundary. No CLI flag can
substitute a policy: exactly two fixed sources are read (shipped file + optional `core.md` overlay).
Resolution returns a `layers` audit (each layer's `identity` carries `source`, `schema`, `sha256`)
so a substitution is visible after the fact. A builder **can** change `core.md`; claiming they
cannot is an overclaim.

| `action` / `phase` | Orchestrator fulfills |
| --- | --- |
| `dispatch-panel` | Dispatch the round's `reviewer-deep` panel per `payload.dimensions`, `payload.tier`, and optional `payload.shards` (big-diff sharding; cross-cutting lenses always get the whole diff). Submit `{seats: {<dim>: {findings, receiptMissing?, receiptStale?, vacuous?, reason?}}, seatMap?, ranManifest?, canaryResult?}`. A seat whose `dispatch-review` returned `reason: "vacuous"` (or equivalent double vacuous forfeit) is folded with `vacuous: true` or `reason: "vacuous"`. When every configured cross-vendor seat that **ran** returned zero findings, run `seat_canary.py probe` and submit its JSON as `canaryResult` (see `auto-fix-loop.md`). `ranManifest: {<dim>: <vendor>}` is the orchestrator's OWN trusted record of which vendor produced each seat's folded findings — mirroring `collectionManifest`; an in-seat `ranVendor` echo is advisory only and authenticates nothing. The driver mechanically compares it to the seat map's configured vendor and records a per-round `fellOpen` dispatch-provenance row + a `degraded` disclosure for any `run` seat that fell open to a different vendor (#563 DoD1) — the disclosure is machinery, not builder discipline. A cross-vendor seat that ran without a trusted manifest entry is disclosed as provenance-unavailable. The guarantee is exactly as strong as the orchestrator's manifest — the driver cannot cryptographically verify engine identity and does not pretend to (the same posture as `collectionManifest`). Receipt-missing seats re-dispatch at most `REDISPATCH_BUDGET` times (`loop_plan_common.REDISPATCH_BUDGET` — the single home) before terminal `missing` with findings carried unverified. The driver refuses a submit whose seat keys are not configured dimensions — keys must be the full reviewer names from `payload.dimensions`, never the findings-file stems (`architecture`, `code`, …); unknown keys only — a partial seats map (subset of configured dimensions) and an empty one are still accepted, and an absent lens is caught later by the panel's own incomplete-panel park, not here. Recovery is to re-key the seats map and resubmit the same phase/attempt/state-hash (no re-dispatch, no fresh session dir). **`payload.dimensions` is an independent batch — dispatch its seats concurrently, per § Batch concurrency above; submit the phase once, with every seat in the one artifact.** |
| `dispatch-verifiers` | One verifier per cluster in `payload.clusters` (`model: $VERIFIER_MODEL`, reviewer engine). Submit `{verdicts: [...]}`. **`payload.clusters` is an independent batch — dispatch its verifiers concurrently, per § Batch concurrency above; submit the phase once, with every verdict in the one artifact.** |
| `dispatch-synthesis` | One synthesis judge over `payload.findings` (`model: $SYNTH_MODEL`). Submit `{grouping: [{group_id, member_ids}, ...]}`. Mechanical compile (citation, diff-scope, dedupe, nit cap) and `verification.merge_and_rank` run inside the driver — the merge keeps the **highest** severity among a group's members on the normalized fail-closed vocabulary (`circuit_breaker.severity_rank` / `effective_severity`), so a group can never come out less blocking than its most severe member; the **author-justification post-filter** runs here too (may drop only non-CONFIRMED findings; CONFIRMED survives stamped `challenge: "author-justified"`). |
| `dispatch-gap-sweep` | Big-diff only: one full-diff finder pass. Submit `{findings: [...]}`. |
| `dispatch-audits` | Delta round: one auditor per target in `payload.targets` — **never the fixer's vendor**; single-vendor runs stamp `independence: "degraded"`. Each target carries **two** id-shaped fields: `id` (per-location — the dispatch/result/manifest key) and `identity` (line-less, driver-internal stall alias), plus `verdict` and `evidence` — finding-derived text that rides into each auditor seat's order payload. Submit `{results: [...], collectionManifest: {<result-id>: <vendor>}}`. **Every transport key is `payload.targets[].id`:** each `results[].id` and **every** `collectionManifest` key must be the per-location `id` — never `targets[].identity` (driver-internal; must not be used as a transport key). A manifest key outside the round's target ids is **refused at submit** with the mistake named — nothing folds, recovery is a corrected resubmit on the same phase/attempt/state-hash. **Provenance rests on the orchestrator's dispatch manifest, not the result's echo:** you (the dispatching orchestrator) are the trusted collector — build `collectionManifest` from your OWN dispatch records (which vendor you seated per target, keyed by `targets[].id`, out-of-band from the results you got back), never copied from a result's `auditorVendor`. A clearing ruling (`discharged` / `discharged-but-new-issue`) is authenticated **iff `collectionManifest[id]` exists AND equals the driver-recorded selected auditor** (where `id` is the per-location target id); a missing manifest entry or a manifest vendor ≠ the selection → **not-discharged + `unauthenticated`**. The in-result `auditorVendor` is **advisory only** (a claimant-controlled echo authenticates nothing — a fixer can echo the expected value); an echo that disagrees with the manifest is disclosed as `echoMismatch` but the manifest governs and the discharge stands. Recorded per round as `auditProvenance: "collection-manifest"`. The driver **cannot cryptographically verify engine identity and does not pretend to** — the guarantee is exactly as strong as your dispatch manifest. **`payload.targets` is an independent batch — dispatch its auditors concurrently, per § Batch concurrency above; submit the phase once, with every result in the one artifact.** |
| `dispatch-scoped-finder` | Delta round: scoped scan over `payload.hunks` (the split's computed new surface — file → hunk ranges + text) at `reviewer-deep`. Submit `{findings: [...]}`. Emitted **only when the computed new surface is non-empty**; a genuinely empty new surface (the split returned `unknown: False` with no new hunks) skips this dispatch and records `scopedFinder: skipped-empty-surface` on the round (receipt-visible) — never a vacuous scan over nothing. |
| `run-verify` | Run `payload.command` from the working tree (non-interactive, timeout). **The verify step may run harness-backgrounded and polled in-turn** — the already-sanctioned shape for long local work — because the host's foreground command-timeout cap bounds a **single call**, not the step; what stays forbidden is unchanged, `&`/setsid/nohup and ending the turn to wait. Hand path: submit `{result: "pass" \| "fail" \| "timeout" \| "skipped" \| "none" \| "unverified"}`. Durable-record path: orchestrator-fulfilled — `advance` folds from the host bare payload at `$SESSION_DIR/round-N/landing/run-verify/<skey>.a<K>.payload.json` where `<skey>` is `round_records.storage_key("verify")` (no orders manifest, no anchor). **The fold writes the durable seat record** for that slot (`seat-result/1` at `$SESSION_DIR/round-N/seats/run-verify/<skey>.a<K>.json`, stamped `fulfilledBy: "orchestrator"`, `orderSha256` / `manifestSha256` = `not-emitted` because there is no anchor to check them against) **in the same commit as the fold**, so a `verifyResult` folded this way reconstructs from the record exactly as a seat-path fold does. **Both artifacts present → `landing-ambiguous`, no fold** — the bare payload and a durable seat record are two claims for one slot, the same invariant the seat path refuses on the envelope/bare-payload pair; delete whichever is not the one you meant. The refusal is **unconditional**: a re-entry after this fold already committed refuses too, rather than re-folding, because recognising "this record is mine" duplicates the already-folded judgment `submit`'s duplicate contract owns. Fail → terminal halt, certification withheld. |
| `dispatch-fixer` | Dispatch fixer over `payload.batch` (blocking findings the driver selected). Submit `{fixes, headDiff \| headDiffPath, escalated?, coverageDecisions?}` — `coverageDecisions` is a list of coverage-decision objects the driver accumulates into `state["_coverage"]`. The post-fix head diff comes from git via the **guarded per-round command in the SKILL's Setup** (`git diff "$BASE_REF"...HEAD` against the **pinned remote base commit** — never a local branch name, and never a bare copy without Setup's failed-diff and empty-diff halts; if `$BASE_REF` is not in this shell, restore and re-validate it first, #637), never the fixer's self-report. Provide it **inline** (`headDiff`) or, since a real head diff can be hundreds of KB and cannot reasonably inline into a JSON submit artifact, as an **absolute** file path (`headDiffPath`) the driver reads itself (**inline wins if both are present**). A missing / non-absolute / unreadable `headDiffPath` or empty content is treated as an **unknown surface** → the next round runs a full reviewer-deep panel (the unknown→run-everything rule), never an empty diff and never a silent scoped skip; the source used is recorded on the round as `headDiffSource: inline\|path\|unknown`. The changed policy subjects the #174 confirmation re-arm consumes are **derived by the driver itself** from the reviewed-vs-head diff through the accumulated findings (the injectable `changed_subjects` seam — library default + CLI wire the real git derivation, #157/#158); a self-reported `changedSubjects` is ignored on the live path. |
| `present-judgment` | A tradeoff/product-choice blocker is an **owner-judgment** call routed here — an **intervention gate, not a terminal**. Present each `payload.findings[]` (id, file, line, title, severity) with `payload.findings[].dispositions` (`fix-as-suggested`, `fix-with-guidance`, `skip`). Submit `{dispositions: [{id, disposition, guidance?, reason?}, ...]}` — `skip` needs a citable `reason`. Fixes fold into the round's fix batch and the loop proceeds into the fix leg; skips ride the exit disclosure. Fail-closed: a missing/unknown disposition (or a reasonless skip) folds as `fix-as-suggested` — a judgment blocker is never silently skipped. Never judge the dispute yourself. |
| `present-stall-menu` | The **audit-stall owner gate** — reached only after one invisible self-recovery (never for a judgment blocker; those go to `present-judgment`). Present `payload.choices` (three-choice menu: `one-more-round`, `accept-the-disclosed-risk`, `hold`; `accept-the-disclosed-risk` only when `payload.acceptRiskEligible` — gated on a stalled audit target that is CONFIRMED with evidence; `one-more-round` only when offered — once per session). Submit `{choice}`. **`hold`** → terminal `held`, certification withheld (absorbs the retired scope-reduction choice). **`accept-the-disclosed-risk`** → certifies when eligible. **`one-more-round`** → not a terminal: clears the stall once, re-enters `dispatch-fixer` → `dispatch-audits` with the stalled targets as the batch (journaled; recorded on the round); an empty/unresolvable stall-target snapshot parks `cannot-certify` instead of re-entering. |
| `terminal` | Stop looping; read `payload.verdict` and `payload.certification`; surface honestly in the End-of-Loop Summary. |

## Journal and receipt

**Journal (`driver-journal.jsonl`).** One JSON object per line: `{cmd, phase, round, attempt, outcome, ts}`.
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
session already at its terminal step — re-emits the stored terminal pending WITHOUT re-running
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

**Receipt (`round-receipt.json`).** Required keys (shape-checked by `validate_receipt`, fail-closed):

- `schemaVersion` — `2` or `3` (`validate_receipt` accepts both). It is the **state's** version, not
  a constant: a session bootstrapped at v2 still terminates to a v2 receipt, while a fresh session
  (`STATE_SCHEMA_VERSION` = 3) emits 3.
- `verdict` — `converged`, `halted`, `held`, `stalled`, `cannot-certify`, `capped-with-open-critical`, …
- `certificationShape` — e.g. `full-panel-confirmed`, `audited-chain`, or `*-degraded` variants
- `certification` — full block (`shape`, `fullPanel`, `independence`, `base` — `fetched` |
  `degraded` | `not-checked`, optional `note`/`reason`, `pluginVersionSkew` — tri-state skew
  disclosure: `checked-clean`, `checked-degraded`, `not-checked`, `absent` when the seat map
  carries no `pluginVersionSkew` receipt (older map or missing field — distinct from
  `seatMap.pluginVersionSkew`, the compose receipt object with `status`, `detail`, and
  `inspectedRoot`), or `unknown` when a receipt is present but its `status` is not one this
  build recognizes (degrading — not `absent`), `shapeDrivers` — sorted
  channel names that fired for the certification shape (`independence`, `base`, `same-family`,
  `plugin-version-skew`, `seat-map-violation`, `unproven-liveness`, `seat-pin`))
- `rounds` — per-round `kind`, `seatStatus`, `lensCoverage` (`{ran, expected, floor}` — partial rounds report `floor: true`, never a bare total; the receipt validator refuses a **full-panel-anchored** `converged` claim whose anchor round is floor-marked or missing coverage), `blockingCount`, `verifyResult`, `audits`, `auditProvenance` (`collection-manifest` when the round ran fix audits — the manifest-keyed provenance boundary, visible at vet), `fellOpen`, `fellOpenProvenanceMissing`, `seatMapUnavailable`, `seatMapViolations`, `vacuousSeats`, `canaryUnverified`, `canaryFailed`, `canaryVerified`, `orderVendorProvenanceGaps`, `unverified`, `authorJustifiedDrops`, `compileDrops`, `selfRecovery`, `stallChoice`
- `findings`, `decisions`, `seatMap`, `scriptRan`, `degraded` (disclosure list)

**Per-round fields and `degraded` disclosures (#563, #666, #668).** Machinery records these on the round when `_fold_panel` (or dispatch-provenance folding) detects them; `_finalize_receipt` mirrors each into a `degraded` line except `canaryVerified` (evidence-only, no disclosure).

| Round field | Set when | `degraded` line |
| --- | --- | --- |
| `fellOpen` | A `run` seat's `ranManifest` vendor differs from the seat map's configured vendor (cross-vendor seat fell open to Claude). | `reviewer-fell-open (round N): …` |
| `fellOpenProvenanceMissing` | A cross-vendor seat ran but has no trusted `ranManifest` entry. | `reviewer-fell-open-provenance-unavailable (round N): …` |
| `seatMapUnavailable` | Live cross-vendor vendor(s) ran but no `seatMap` was submitted. | `reviewer-fell-open-seatmap-unavailable (round N): …` |
| `seatMapViolations` | The submitted seat map carries constraint violation(s) not excused by its own degradation channel (#680). | `seat-map constraint breach: …` (terminal `degraded` list; also recorded per round) |
| *(pin excusal)* | A standing excusable violation was excused because a collapsed seat was owner-pinned (`classify_violations` → `excusedByPin`). | `seat-map pin excusal: seat(s) …` (terminal `degraded`; `shapeDrivers` includes `seat-pin` and certification shape uses `-degraded`, not a third suffix) |
| `vacuousSeats` | Seat dict has `vacuous: true` or `reason: "vacuous"` (empty findings with no verifiable investigation record). The seat folds as `missing` in `seatStatus` — it cannot anchor a `full-panel-confirmed` certification. | `vacuous-seat (round N): …` |
| `canaryUnverified` | Every cross-vendor seat that ran returned zero findings and no `canaryResult` was submitted. | `canary-unverified (round N): …` |
| `canaryFailed` | `canaryResult` was submitted but `engaged` is not true — cross-vendor seats in that panel are downgraded to `missing`. | `canary-failed (round N): …` |
| `canaryVerified` | `canaryResult.engaged` is true — records the probe's `evidence` dict on the round. | *(none)* |
| `orderVendorProvenanceGaps` | An emitted order seat on a `dispatch-review` phase had no **resolved** vendor — absent from the seat map, or `vendorSource: "defaulted"` (a fallback the driver guessed, not evidence). Its order rendered the stdout contract. | `order-vendor-provenance-gap (round N): …` |

- `skippedBlockers` — the dedicated skipped-blocking channel (`{id, title, severity, reason}` per owner-skipped judgment blocker; possibly empty). **Required** (possibly empty) so a receipt can never omit the channel — a converge over any skip is CLEAN EXCEPT FOR SKIPPED, never a plain success, and its certification `reason` leads with `clean-except-skipped: N blocker(s) skipped with citable reasons`.

`validate_receipt(receipt)` returns `(ok, reason)` — a missing `scriptRan.byPhase` or non-list
`rounds`/`findings`/`skippedBlockers` rejects the receipt.

### Handback receipt gate (Claude host, Bash tool)

**Shipped dark in 0.25.0** — the review-receipt handback refusal class is built and in-tree but
**unwired** from the PreToolUse chain; it enforces nothing today (arming: #954). The scope markers
and sidecar below still ship and still produce data.

When armed, the PreToolUse `handback_receipt_gate` hook would refuse `gh pr ready` and non-draft
`gh pr create` when the worktree is mechanically in scope but lacks a valid full-lane review receipt.
Scope is marked by
`build-lane.json` (written by `lib/build_lane.py` `declare`, invoked from the workhorse charter's
full-lane intake step) or `review-session.json` (written on the driver's first fresh `next`); both
markers carry a `branch` field — a marker whose `branch` differs from the worktree's current branch
is **stale → out of scope → silent**. **Neither marker present → the gate stays silent** (not in
scope). Terminal verdicts that
permit handback are `converged` (with certification) and `uncertified-manual` (with attestation). A
bare `gh pr ready` with no PR selector binds by branch + HEAD — the PR's remote base is not resolved
inside the hook; that residual is covered by the advisor vet's remote-head duty.

This class is a **Claude-host, Bash-tool, honest-agent tripwire**; it does not cover aliases,
wrapper scripts, non-Bash tools, or other hosts. **It is not a security boundary and is not claimed
as one.** Codex (`hooks-codex.json`) wires no PreToolUse hooks — the asymmetry is intentional.

## Certification shapes

| Shape | Meaning |
| --- | --- |
| `full-panel-confirmed` | A qualifying full `reviewer-deep` confirmation panel ran before exit. |
| `audited-chain` | Scoped certifying finish — fixes discharged via audits + scoped verification; **no** final full panel. Surface this honestly; never imply a pristine fresh pass. |
| `*-degraded` | Appended when `independence` is degraded (single live vendor — auditor is fixer's vendor), base fetch degraded, the seat map disclosed same-family self-review, or compose disclosed `plugin-version-skew` (semantics-divergent or evidence-unreadable across `lib/model_registry.py`, `lib/seat_map.py`, and `lib/version_skew.py` against the superheroes source repo — detection only, not a version-string compare). |
| `*-constraint-violated` | Appended when the seat map carries unexcused constraint violation(s) (#680); supersedes `*-degraded` when both would apply. |
| `null` / withheld | Verify fail, stall unresolved (`stalled`), capped-with-open-Critical park, round-ceiling halt, owner `hold`, or `cannot-certify` (including an unresolvable `one-more-round` stall-target snapshot). |

**Terminals the orchestrator must surface honestly:**

- **Scoped certifying finish** (`audited-chain` / `audited-chain-degraded`) — delta rounds verified the fix chain; say so.
- **Judgment gate is an intervention, not a terminal** — a tradeoff blocker routes to `present-judgment` (fix-as-suggested / fix-with-guidance / skip-with-reason) and folds back into the fix leg; a skipped blocker rides the exit disclosure. It never dead-ends in the stall menu.
- **One invisible self-recovery** — audit-stall triggers a single fixer escalation (journaled); never offered as an owner menu item.
- **Three-choice stall menu** — `one-more-round` (offerable once per session; not a terminal — re-enters the fix leg), `accept-the-disclosed-risk` (stalled CONFIRMED-with-evidence audit target only), `hold` (terminal `held`). Reached only from the audit-stall path after self-recovery.
- **Capped-with-open-Critical park** — confirmation budget exhausted with a Critical still owed.
- **Round-ceiling halt** — a hard bound on the round counter (default 10, config `maxRoundsAbsolute`): the round **at** the ceiling **runs to completion**, then the loop **refuses to begin** the next round — unconditional in that **no finding state can buy another round**, not in that it preempts the current round's own terminal; terminal `halted` with certification **withheld**; reason token `round-ceiling` (**distinct from** `max-iterations`, whose ratified meaning — the cap reached *with an open finding* — is unchanged); the receipt states the **ceiling** and the **rounds reached**, and names the round not begun. A fold answer from `cmd_submit` carries `foldLanded` only when a fold actually committed; an `advance` whose nested submit parked at the ceiling answers `notFolded` with the terminal halt rather than a `folded` receipt, and the durable seat record is either written in the fold's commit or its absence is stated on the receipt.

**Library `recordsPath` / `round-records.json` seam (#720, #1187).** When `run_loop` config carries
`recordsPath`, `_persist_round_records` refreshes that file after every fold: each in-memory ledger
record is written through `review_memory.summarize_record` (a skeleton — no evidence bodies) and
carries the declared per-round disclosure block selected by `_declared_disclosures` from
`RESUMABLE_DISCLOSURE_CHANNELS`. The producer writes the whole outgoing ledger in one atomic
`persist_record` call — no intermediate strict-prefix state on disk. A caller that already owns
`round-records.json` opts out with `persistRecords: False` (`eval/review_loop_runner.py` is the
one in-repo caller that does). A destination the producer cannot read and a persist it cannot
complete both park `cannot-certify` rather than certifying off a stale file; `_seed_resume` is the
read path on the next invocation. `recordsPath` is not reachable from the `next` CLI today — this
is the library / `run_loop` path only.

## Invariants

Pinned by `test_round_driver.py` (ported from the retired `test_code_loop_plan.py`):

- Round 1 = full `reviewer-deep` baseline. Unknown changed surface → full panel (never risk a blind skip).
- #174 confirmation economics kept: at most two full confirmation panels; a Critical since the last
  qualifying panel or cross-cutting rework (≥3 subjects) re-arms one more; Critical still owed at
  the cap → `capped-with-open-critical` park.
- Audit-keyed stall breaker (`circuit_breaker.check_audit_breaker`) — not the old per-finding
  `circuit_breaker.py "$SESSION_DIR" 7` call inside the loop; the driver owns stall/self-recovery.
  Criterion 2 (`audit-stall`) evaluates the **last two** audit rounds only — an honestly-folded
  clean round resets the window; criteria 1 (round cap with an open finding) and 3 are unchanged,
  and a separate hard ceiling bounds the round counter — **no session's round counter exceeds the
  ceiling without a terminal halt**; the counter is written only by `_advance_round` and
  `_seed_resume`, each of which asks the ceiling before writing, and a loaded persisted state above
  the ceiling is guarded at command entry too — so a round above the ceiling can never begin. Callers
  of `advance` must not treat `ok: true` from a nested `cmd_submit` as a landed fold unless
  `foldLanded` is set; the `notFolded` receipt names why. A policy **naming** a
  ceiling below `maxRounds` refuses at load; an unnamed one takes the flat default and simply binds
  first.
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
Treat `round_driver.py` as the contract of record.
