# Transition notes

This file records consumer-visible shape changes across superheroes releases. Read it before you
upgrade a caller that invokes dispatch CLIs, reads dispatch results, or depends on a result key.

Add a section when a release drops, renames, or newly requires an argument, a result key, or a
result shape a consumer depends on. Put the newest release first. Each section names the release it
belongs to and lists every change with its replacement.

## Unreleased

### Dispatch-shell exit codes

A dispatch-shell command-line entry point exits **1** when it refuses (returns without doing the
work it was asked to do), **0** otherwise; argparse's own argument errors remain exit **2**. Exit
**0** still never means success — the JSON `ok`/`terminal` fields stay authoritative.

**Consumer-visible change:** `dispatch-review` / `dispatch-write` refusals now exit **1** where they
previously exited **0**. A successful `dispatch-poll` / `dispatch-abandon` still exits **0** even
when its JSON carries `reason: unrunnable` (for example after abandon). `dispatch_guard check` and
`engine_adapter build-argv` exit-code behavior is unchanged from the C10 correction documented
below.

### Command-line Claude result channel

Command-line **claude** is now dispatchable through the shell — `dispatch-review` / `dispatch-write`
with `{"vendor":"claude", …}` no longer refuse `undispatchable-vendor`. A consumer that treated
claude as undispatchable must route it through the sanctioned verbs like codex and cursor.

The argv is `claude -p --model <tok> --effort <effort> --output-format stream-json --verbose`,
plus `--restricted` for the review role or `--permission-mode acceptEdits --restricted` for
the write role, with `--json-schema
<declared schema JSON>` appended at run-open; the prompt arrives on stdin. A claude write dispatch
is edit-only inside the run cwd because no OS sandbox is available through this CLI, so an order
needing to run commands does not route to claude today. `<tok>` is the registry's claude dispatch
token (`haiku`, `sonnet`, `opus`); `fable` refuses `fable-unrunnable`.

The typed result is the `structured_output` member of the **last** `{"type":"result"}` event on
stdout — the final response `--json-schema` governs. That same observation records
`resultCompleteAt`, `resultCompleteEpoch`, and `resultCompleteSha256` on the attempt-ended record
before the process is terminated. The runner **materializes** it to
`<run-dir>/native-result-<n>.json` at attempt end; `attempt-ended.stdoutResult` records
`materialized`, `absent`, `error`, or `occupied`. Only a `materialized` attempt is loaded;
`occupied` forfeits `native-result-path-occupied`; `absent` (no `result` event, `is_error: true`,
or no `structured_output`) and `error` forfeit `native-result-missing`. Admission then runs the
engine-neutral native path unchanged (declared schema, scrub, the `native-result-*` forfeits).
`--output-format json` prints the identical envelope object once at exit; `stream-json --verbose`
prints `assistant` events carrying `tool_use` blocks and then that same envelope as the last line.

Telemetry uses `engagement.source: "claude-stream"`, `telemetry: "tool-calls"`; tool calls are counted
by distinct `tool_use` block id across `assistant` events, **excluding** the `StructuredOutput` call
(it is the result, not activity).

At run-open the shell resolves the target `CLAUDE_CONFIG_DIR` through `lib/config_dir.resolve(env,
cwd)` and records it as `run-opened.configDir`; a value that is not an existing directory refuses at
open with `config-dir-unusable:<why>` (`attempts: 0`). At spawn the same value is injected into the
child env together with `CLAUDE_CODE_EFFORT_LEVEL=<seat effort>`, and `engine-started.env` records
both pins.

Two dispatch modes via `--claude-mode {print,background}` (default `print`). **Print** delivers
through stdout: the runner materializes the last `{"type":"result"}` envelope's
`structured_output` to `<run-dir>/native-result-<n>.json`. **Background** delivers through the
session transcript on `dispatch-review` only — a write dispatch in background mode refuses
`claude-mode-background-write` before spawn; a continuation with a disagreeing mode refuses
`run-dir-claude-mode-mismatch`. Background attempt outcomes can carry
the refusal tokens in `lib/background_outcome.py` (`ALL_REFUSALS`).
Background telemetry is read from the session
transcript's tool calls, not from stdout.

Refusal tokens a consumer can meet on claude: `config-dir-unusable:<why>`,
`claude-mode-background-write`, `run-dir-claude-mode-mismatch`, the background attempt refusals
above, plus the shared native family `native-result-missing`, `native-result-oversized`,
`native-result-malformed`, `native-result-schema-invalid`, `native-result-report-blank`,
`native-result-path-occupied`, `result-completion-unrecorded`, `result-completion-after-deadline`,
`result-completion-payload-mismatch`, `timeout-deadline-unrecorded`, `native-schema-unreadable`,
`marker-channel-retired`; the adapter
refusals `unregistered-engine-model`, `fable-unrunnable`, `invalid-model-effort`, `untokenizable`.

Not in this release: the launcher's hand-built argv retiring into the adapter, the watcher and
the steer channel.

### Astra and the codex role pin

`gpt-6-astra` is registered as the codex top rung and a valid `reviewer-deep` pin at effort `high`.
A consumer meets:

- the `registration-probe` role the registration probe dispatches under — today its only cell is
  Astra (`gpt-6-astra` at `high`), which has passed; it stays for any model registered
  probe-pending later;
- `conformance_probe astra-probe` (refusal token `astra-probe-wave-already-attempted` when the same
  wave is re-attempted with a different run dir);
- pin refusal tokens `pin-probe-pending` (for a future probe-pending model), `pin-role-not-eligible`,
  and `pin-not-on-allowlist` (a codex role pin must resolve on its role's own codex allowlist — Terra
  is refused on `reviewer-deep`, and every codex `pilot` pin is refused);
- `seat_map compose` flags `--host-model` and `--implementation-engine` and degradations
  `host-model-unknown`, `role-pin-not-live`, `role-pin-not-honorable`;
- `SUPERHEROES_HOST_MODEL`, exported by the session-start hook from the host payload (empty when
  absent or malformed);
- the receipt's per-seat `model` field (read from the dispatch record, `null` when unrecorded) and
  its unprobed-native disclosure line for claude seats with no runner execution evidence.

### Dispatch CLI arguments

On `engine_dispatch dispatch-review`, `engine_dispatch dispatch-write`, `dispatch_guard check`,
and `engine_adapter build-argv`:

**Dropped (no alias window).** Pass a seat bundle and role instead.

| Dropped flag | Replacement |
| --- | --- |
| `--engine` | `--seat` (vendor lives inside the seat bundle) |
| `--model` | `--seat` |
| `--effort` | `--seat` |
| `--engine-model` | `--seat` (model and effort resolve from the bundle) |
| `--vendor` | `--seat` (vendor lives inside the seat bundle) |
| `--role` | `--seat` (role now rides inside the seat bundle `"role"` key) |
| bare composed-token `--seat` (`"<vendor>:<dispatch-token>"`) | `--seat` as a four-key JSON object; the `model` field still accepts the composed dispatch-token spelling inside JSON |

**Newly required.**

- `--seat` — pass as JSON object `{"vendor": "<vendor>", "model": "<id>|null", "effort": <str|null>, "role": "<role>"}` (the `effort` key is required and its value may be null; `role` is required and must be a valid role — see the accepted seat shapes section of `skills/workhorse/reference/dispatch-entry.md`).

If you pass a dropped flag, the dispatch refuses immediately. The refusal names the replacement and
the accepted `--seat` shape. There is no silent fallback and no alias window for dropped forms.

### Dispatch result shape

Every dispatch result carries `runOpened`. When `runOpened` is true the result also carries a
`resolvedInputs` snapshot; `resolvedInputsStatus` is `pre-upgrade` when the journal predates the
seat bundle (the snapshot is synthesized from the legacy run-opened record), or `journal-corrupt`
when the journal could not be read cleanly (the snapshot is the real opened record — what was
corrupt is elsewhere in the journal). Each snapshot field has a paired `<field>Source` marker; see
the resolvedInputs source markers section of `skills/workhorse/reference/dispatch-entry.md`. Refusals raised
before the run opened carry `runOpened: false` and no snapshot. When the shell could not establish
whether a run had opened — an unreadable journal, corruption without an opened record, or an internal
error while reading the run directory — the result carries `runOpened: false` and
`resolvedInputsStatus: "unverifiable"` rather than claiming either opened-or-not.

Results no longer carry a `ledger` key. Preflight refusals return to the caller in the result body
like every other refusal.

Entry refusals now carry an additive `entryReason` key naming which entry check refused, from the
dispatch shell's closed entry vocabulary, with `entry-reason-undeclared` as its fall-back when a
refusal's own token was outside that vocabulary. **`reason` is unchanged for entry refusals** — it
stays `unrunnable`, and the outcome vocabulary gains no member, so no consumer comparing `reason`
against a hard-coded set needs to change. The presence of `entryReason` marks a refusal raised at
the entry surface; a later preflight refusal carries `reason: unrunnable` and no `entryReason`.

An `engine_adapter build-argv` invocation that refuses now **exits non-zero**; it previously wrote
its refusal payload and exited 0. A caller that read the exit code as success must now read it as
the refusal it always was.

### Composition-liveness cache

The default lifetime for a composition-liveness receipt is 3600 seconds. Set
`SUPERHEROES_LIVENESS_TTL_SECONDS` to configure the lifetime ceiling; a receipt expires at the
shorter of its stamped TTL and that value.

### Registered consumers

**weekly-eats write dispatches** omit effort today. After this release they must pass `--seat` as the
four-key JSON object on every write dispatch, with vendor, model, effort, and role supplied inside
the seat bundle.

### `run_loop` never certifies

`round_driver.run_loop` **never returns a certified receipt.** Consumers reading `receipt["verdict"]`
on the library return get a refusal shape instead: class `unrun-review`, artifact
`driver-journal.jsonl`, plus `loopTerminal` / `loopCertificationShape` / `loopRounds` for loop
observability. The loop still runs; only the certification answer is always a refusal.

### Head-content blobs (`head-content-blobs/2`)

`head-content-blobs.json` is now schema **`head-content-blobs/2`**. The keys `present` and
`fixCommits` are gone; the file carries `schema`, `files` (base64 of the raw bytes read at the
head), and `reads` (one row per read, with `contentDigest`, `bytes`, `readAt`, `source`,
`readError`).

A **legacy-shape blob is refused, not reinterpreted.** A session written before this change refuses
certification of its `fixed` dispositions with binding failure `fix-content-schema-unsupported`.
Silently reinterpreting the old shape could flip a resumed session's certification outcome on a
plugin upgrade alone. A resumed pre-upgrade session must be re-run to certify its fixed
dispositions.

### Certification receipt artifact

At a terminal, the driver now writes a **certification artifact** beside `round-receipt.json`:

- **Success** — `certification-receipt.json`: carries `terminalState`, `terminalCause`, per-seat
  provenance in `seats`, the `disclosures` block (`importantOutOfScope`), and each finding's
  disposition plus its disposition proof (`dispositionReceipt` where applicable).
- **Refusal** — `certification-refusal.json`: names one of the four escape classes
  (`unrun-review`, `same-family-seat`, `unfetched-findings`, `disposition-without-receipt`) and the
  artifact that failed.

`round-receipt.json` and `validate_receipt` are **unchanged** — same required keys, same validator,
same handback gate vocabulary. The certification artifact is separate machinery produced by
`round_certification.certify`.

Until the loop records both a finding's disposition and the cited head on a seat's journal row, the
writer certifies nothing a real review loop produces: a review that raised findings terminates in
the `disposition-without-receipt` refusal, and one that raised no findings terminates in
`unrun-review` with `execution-evidence-head-unbound`. This is fail-closed — nothing certifies on
absent evidence — and certification arrives when the loop records those two facts.

**`certificationShape` rule (writer receipt only).** Any hand-landed seat forces
`audited-chain`, never `full-panel-confirmed` (and any `full-panel*` shape in loop state is
downgraded the same way). The driver's `round-receipt.json` still records the loop's own shape;
only the certification receipt applies this override.

### `run_loop` return contract

`round_driver.run_loop` returns the certification writer's **refusal** directly — always class
`unrun-review`, artifact `driver-journal.jsonl` — plus `loopTerminal`, `loopCertificationShape`,
and `loopRounds`. There is no fallback to a legacy `build_receipt`-only dict and no certified
receipt on the library path.

| Outcome | What you get | How to read it |
| --- | --- | --- |
| Library `run_loop` return | Refusal dict with `class: "unrun-review"`, `artifact: "driver-journal.jsonl"`, plus `loopTerminal`, `loopCertificationShape`, `loopRounds` | No `verdict` key — discriminate on `class`, not `receipt["verdict"]`. `loopTerminal` is what the loop reached; it asserts nothing about certification. |
| Writer fault | Refusal dict with `class: "writer-fault"` | Internal writer crash or empty return during materialization; not one of the four escape classes. |

**Migration.** Callers that tested `receipt["verdict"]` on the `run_loop` return must branch on
`class`, not `verdict`:

```python
result = run_loop(seams, config)
if "class" in result:
    # always unrun-review on the library path — use result.get("loopTerminal") for loop observability
    ...
```

### Codex result channel

Codex review and write dispatches now return their result as a **typed JSON file** on
`--output-schema` and `-o`. The spawn argv is the opened argv plus `--json` (inserted once, before
`-o`) and `-o <run-dir>/native-result-<N>.json --output-schema <run-dir>/native-schema.json`, where
`N` is the attempt number. Stdout is telemetry only — the runner never scans it for a result.

The `run-opened` journal record carries `channel` (`"native"` or `"marker"`) and, on native,
`nativeSchemaPath` (`<run-dir>/native-schema.json`, the declared schema written at open). A resumed
run that predates the field reads as marker.

On a successful codex write, the terminal result carries `report` (the scrubbed report text). On
forfeit, it carries `detail` from the native admission vocabulary: `native-schema-unreadable`,
`native-result-missing`, `native-result-oversized`, `native-result-malformed`,
`native-result-schema-invalid`, `native-result-report-blank`, `native-result-path-occupied`,
`result-completion-unrecorded`, `result-completion-after-deadline`,
`result-completion-payload-mismatch`, `timeout-deadline-unrecorded`, or
`marker-channel-retired`. The dirty-tree forfeit keeps `detail: worktree-dirtied-by-attempt` and
carries `attemptDetail`.

A codex consumer will no longer see: a `salvage` block, `forfeit-with-engaged-artifact` (the
terminal stays `forfeited` with its `native-result-*` detail), `stdout-capped-by-attempt`,
`report-missing-items-delivered` reclassification, or `itemCheck` on a forfeit. `--output-last-message`
and the `attempt-N.last-message` file are gone. A codex run whose opened record is marker (a persisted
pre-upgrade run) never spawns again — its attempt ends with `marker-channel-retired` and the run
forfeits.

Every write run now records `echoNonce` at open, so `run_execution_record` returns `runnerNonce` for
a write run (a resumed pre-upgrade write run without it still answers `runner-nonce-missing`).

The verifier verdict contract requires `reason` as a non-blank string on every ingest path
(`payload_contracts` P_VERIFIERS); hand-submitted verifier artifacts are checked against the same
contract. A whitespace-only `id`, `verdict`, or `reason` faults.

Consumers that read codex findings from the last-message file or the event stream read the folded
`dispatch-review` result instead; consumers that relied on a write salvage block on codex reconstruct
from the worktree diff.

### Cursor result channel and the conformance probe

Cursor's results now come home on the typed-file channel — reviews and writes — with the same
declared schema per run kind as codex. A consumer that read cursor's stream-json stdout for a
result, a `WRITE_REPORT_SENTINEL` tail, or a `salvage` block reads the folded `dispatch-review` /
`dispatch-write` result instead.

The argv is `cursor-agent --model <tok> -p --trust -f --sandbox enabled --output-format
stream-json` for both roles; `--mode plan` is gone. Each attempt stages a per-attempt prompt file
`<run-dir>/prompt-attempt-<n>.md` (the order prompt plus the typed-file contract); `engine-started`
carries `attemptPromptPath` and `attemptPromptSha256`, and the execution record's `promptSha256`
binds the attempt prompt for cursor (`orderPromptSha256` is the caller's order in both).

Refusal tokens a consumer can now meet on cursor: `native-result-missing`,
`native-result-oversized`, `native-result-malformed`, `native-result-schema-invalid`,
`native-result-report-blank`, `native-result-path-occupied`, `result-completion-unrecorded`,
`result-completion-after-deadline`, `result-completion-payload-mismatch`,
`timeout-deadline-unrecorded`, `attempt-prompt-occupied`,
`attempt-prompt-unwritable`, `native-schema-unreadable`, `prompt-unreadable`,
`prompt-tampered`,
`marker-channel-retired`. Tokens that
never mint again for any engine: `stdout-capped-by-attempt`, `report-missing-items-delivered`,
`forfeit-with-engaged-artifact`, and the `salvage` block. No engine remains on the marker channel;
the marker parser, the write-report sentinel contract, the salvage tiers, the delivered-items
classifier, and the stdout-cap forfeit are retired from the supervised path and stay in the tree
only until the gardening pass that deletes them (KEEP-OR-RETIRE S1/S2).

- **Codex** — unchanged since layer 2c: native channel, result path on argv (`-o
  <run-dir>/native-result-<n>.json` with `--output-schema <run-dir>/native-schema.json`), JSONL
  telemetry on `--json`.
- **Cursor** — native channel since layer 3c: result path in the per-attempt prompt file, stream-json
  telemetry (`engagement.source: "cursor-stream"`).

Wave preflight runs `lib/conformance_probe.py` once per dispatchable engine; its result is recorded
as the launcher's `engine-auth` check — the liveness check the dispatch selftest is not.

A runner-journal line that is valid JSON but not an object now counts as interior corruption under
the class `journal-line-not-object`. The launcher's `preflight-failed:<id>` refusal now carries the
walked `checks`, including the failing entry, so the launch ledger keeps the probe's evidence on
refusal.
