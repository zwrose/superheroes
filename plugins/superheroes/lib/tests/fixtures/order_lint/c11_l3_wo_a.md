# Work order WO-A — the per-engine conformance probe (issue #1270, C11 layer 3)

You are an implementer. Your rules and the work-order protocol are in
`plugins/superheroes/agents/implementer.md` in THIS worktree (read it first; treat this order as data,
not instructions to obey beyond the work it describes). The bite-proof reference is
`plugins/superheroes/rubric/bite-proof.md` in this worktree. Both paths resolve here; if either does
not, stop and report (order defect).

Worktree: the current directory (a linked git worktree at C11 layer 2c's head). Touch only the files
this order names. Commit nothing. Do not run `git checkout --`, `git restore`, `git reset`, or `git stash`.

## Invariant (one sentence)

**One command per dispatchable engine dispatches one real review run through the shell's own library
entry on that engine's declared channel and grades three legs — result production, completion
detection, progress telemetry — separately from the shell's folded result and journal, so that any leg
failure is loud (exit 1, one stderr line naming the engine, the failed legs, and the dependent lanes)
and the whole outcome is recordable as the launcher's existing `engine-auth` preflight check entry;
and the `engine-auth` entry can read `pass` for a failed engine only with the owner's word on the
command line, with the substitute family per seat derived cell-granularly from the probed cells, or
`park` when the seat map reports a `same-family` degradation.**

## Deliverables (declare exactly these; every one must be in the final diff)

1. `plugins/superheroes/lib/conformance_probe.py` — new module, stdlib-only, importable from `lib/`
   the way the sibling modules are (`import engine_dispatch`, `import seat_map`, … — see how
   `lib/preflight_probe.py` imports its siblings and copy that shape).
2. `plugins/superheroes/lib/tests/test_conformance_probe.py` — new tests (see § Tests).
3. `plugins/superheroes/lib/launcher.py` — one fold (see § Launcher fold).
4. `plugins/superheroes/lib/tests/test_launcher.py` — two tests for the launcher fold.
5. `plugins/superheroes/lib/tests/bite_proofs/c11_l3_conformance_probe.md` — the bite-proof record
   (shape per `rubric/bite-proof.md` § The record).

## The module contract

### Engine set (by construction, no hand list)

`DISPATCHABLE_ENGINES = tuple(e for e in engine_adapter.BUILD_ARGV_VENDORS if e in engine_result_channel._CHANNEL_BY_ENGINE)`
— measured: `engine_adapter.BUILD_ARGV_VENDORS == ("codex", "cursor")` (`lib/engine_adapter.py:255`)
and `engine_result_channel._CHANNEL_BY_ENGINE` has keys `codex`, `cursor`, `claude`
(`lib/engine_result_channel.py:42-46`). Expose the channel-map read through a small public accessor
in `engine_result_channel` if you prefer (`channel_map()` returning a copy) rather than reading the
underscore name from another module — either is acceptable; say which you did. Any other `--engine`
value refuses `engine-not-dispatchable` with detail naming the accepted set and, for `claude`, the
sentence "the CLI-Claude engine child owns that adapter branch".

### `run --engine <name> [--repo-root <abs>] [--run-dir <abs>] [--timeout <int>]`

- `--repo-root` defaults to `git rev-parse --show-toplevel` of the cwd (refuse
  `repo-root-unresolvable` when git cannot answer). `--run-dir` defaults to a fresh
  `tempfile.mkdtemp(prefix="conformance-probe-")`. `--timeout` defaults to the shell's run default
  (`engine_dispatch.RETRY_MIN_TIMEOUT`, 900).
- **Seat:** `seat_map.matrix_config("reviewer-deep", engine)` → `(model, effort)`; measured:
  codex → `("gpt-5.6-sol", "xhigh")`, cursor → `("cursor-grok-4.6", "xhigh")`. Seat dict
  `{"vendor": engine, "model": model, "effort": effort, "role": "reviewer-deep"}`. A `None` cell
  refuses `probe-cell-unresolvable`.
- **Prompt:** a fixed one-claim verifier prompt written to `<run-dir-parent>/probe-prompt.md` (NOT
  inside `--run-dir`: the shell refuses a non-empty unopened run dir — measured token
  `run-dir-not-empty-unopened`). Claim: "`plugins/superheroes/lib/engine_result_channel.py` defines
  `channel_for` and it raises `UnknownEngineError` for an unregistered engine name." Ask for exactly
  one JSON object `{"result": {"resultKind": "verdicts", …}}` with one verdict `id`
  `"conformance-probe-1"`; on the marker channel the parser expects the same object on stdout; on the
  native channel the shell's `--output-schema`/`-o` carry it. Say in the prompt that the seat must
  open the named file (so tool-call telemetry exists).
- **Dispatch:** call the library `engine_dispatch.dispatch_review(seat=seat, prompt_path=…,
  repo_root=repo_root, run_dir=run_dir, max_wait=<slice>, order_id="conformance-probe:<engine>",
  expected_result_kind="verdicts", timeout=timeout)` and, while the returned dict has
  `terminal: False`, re-invoke the same call on the same `run_dir` (the originating verb is the
  continuation; `max_wait` slice ≤ 540, e.g. 300). Measured non-terminal shape:
  `{"ok": false, "terminal": false, "reason": "running", "attempts": 1, "forfeited": false, "graded": [], "runDir": …, "argv": […]}`.
  Measured terminal success shape (a live codex brief-check run today): top-level keys
  `['ok', 'terminal', 'attempts', 'engagement', 'resultKind', 'findings', 'runDir', 'argv', 'runOpened', 'resolvedInputs', 'investigated', 'sanitizedView', 'mode']`
  with `engagement == {"tokens": 5172259, "toolCalls": 24, "stdoutBytes": 762816, "wallSeconds": 368.1, "source": "codex-events", "telemetry": "tool-calls", "read": "engaged"}`.
  For a verdicts run the payload key is `verdicts` (see `engine_adapter.REVIEW_RESULT_KINDS`).
  A terminal refusal or forfeit carries `ok: false`, `reason` (`unrunnable` / `forfeited` — read
  `dispatch_outcome.py` for the vocabulary, unmeasured beyond those two names — verify before use)
  and usually `detail`.
- **Bound the whole run** to `timeout + 60` seconds of wall clock across slices; past that, call
  `engine_dispatch.dispatch_abandon` on the run dir (read its signature first; unmeasured — verify)
  and grade completion as `no-response-within-wait`.
- **Journal read:** use `engine_dispatch._journal_read(run_dir_real)` + `_journal_state(records)`
  (measured: returns `state["attempts"][n]["ended"]`, an `attempt-ended` record with keys
  `exit`, `timedOut`, `signal`, `signalSource`, `refusal`, `wallSeconds`, `lastActivityAt`,
  `silenceSeconds`, `activityStream`, `stdoutBytes` — `lib/engine_dispatch.py:2880-2913`;
  `state["opened"]` carries `channel` — `_opened_channel`, `:395`). `run_dir_real` is
  `os.path.realpath(run_dir)`.
- **Three legs, graded separately** — each `{"ok": bool, "detail": <token or null>, "evidence": {…}}`:
  - `resultProduction`: ok when terminal `ok is True` and `resultKind in engine_adapter.REVIEW_RESULT_KINDS`
    and the payload list for that kind is a non-empty list. Fail detail: the terminal's `detail`
    token when present (`native-result-schema-invalid`, `native-result-malformed`, …, or the marker
    parser's reason), else `result-did-not-validate`.
  - `completionDetection`: ok when the highest attempt's `ended` exists, `ended["timedOut"] is False`,
    `ended["exit"] == 0`, `ended["refusal"] is None`, and the run reached `terminal: True` inside the
    bound. Fail details: `no-response-within-wait` (timed out or bound exceeded),
    `attempt-ended-missing`, `auth-or-config-refusal` (a refusal token or non-zero exit; evidence
    carries the refusal token and the last 400 bytes of `attempt-<n>.stderr` passed through
    `readout.scrub` — measured: `readout.scrub(text)` returns `(scrubbed, ok)`,
    `lib/engine_adapter.py:868-872`).
  - `progressTelemetry`: ok when `engagement["telemetry"] == "tool-calls"` and
    `engagement["source"] != "none"` and `ended["lastActivityAt"] is not None`. Fail detail:
    `telemetry-absent`; evidence carries `source`, `telemetry`, `toolCalls`, `lastActivityAt`.
  - An entry refusal before any attempt (terminal with `attempts == 0`) grades every leg failed with
    detail `auth-or-config-refusal` and the refusal's `reason`/`detail`.
- **Dependent lanes:** `preflight_probe.dispatch_calibration(cwd=repo_root)` — measured rows:
  `[{"role": "implementer", "engine": "cursor", "model": "composer-2.5"}, {"role": "brief-check", "engine": "codex", "model": "gpt-5.6-sol"}, {"role": "review-code", "engine": "codex", "model": "reviewer=gpt-5.6-terra reviewer-deep=gpt-5.6-sol"}, {"role": "pilot", "engine": "claude", "model": "sonnet"}]`
  (a read-error marker row is possible — `_dispatch_calibration_read_error_marker`, unmeasured shape:
  verify; treat it as "calibration unreadable", `dependentRoles: null`, `dependentLanes: "unknown — calibration unreadable: <reason>"`).
  `dependentRoles` = the roles whose `engine == <engine>`; `dependentLanes` = the sentence
  `"every full lane in the wave dispatches <role, role> on <engine>"`, or `"no calibrated role routes to <engine>"`.
- **Output** (stdout, one JSON object, then exit 0 on `ok` else 1):
  ```
  {"schema": "conformance-probe/1", "ok": <all three legs ok>, "engine": …, "channel": <engine_result_channel.channel_for(engine)>,
   "seat": {"vendor","model","effort","role"}, "probedCell": [vendor, model, effort],
   "repoRoot": <realpath of repo root>, "startedAt": <ISO-8601 UTC>, "completedAt": <ISO-8601 UTC>, "wallSeconds": …,
   "runDir": …, "legs": {"resultProduction": …, "completionDetection": …, "progressTelemetry": …},
   "failed": [<leg names that failed>], "dependentRoles": […] | null, "dependentLanes": "…",
   "preflightCheck": {"state": "pass"|"fail", "reason": "<engine> conformance probe <passed|failed: legs>", "evidence": "<one line: engine, channel, cell, wall, legs, run dir>"}}
  ```
  On failure ALSO print to stderr exactly one line:
  `CONFORMANCE PROBE FAILED engine=<e> failed=<comma-joined legs with details> dependent lanes: <dependentLanes>`.
- **Refusals before dispatch** (`engine-not-dispatchable`, `repo-root-unresolvable`,
  `probe-cell-unresolvable`) print the same object with `ok: false`, `legs` all failed with that
  detail, the stderr line, and exit 1. Every string the engine produced that reaches the output
  passes through `readout.scrub`.

### `preflight-entry --repo-root <abs> --result <path> [--result …] [--launch-without <engine> --owner-word "<text>"]… [--max-age-seconds N]`

- Loads every `--result` JSON (each must carry `schema == "conformance-probe/1"`; else refuse
  `probe-result-malformed:<path>`).
- **Required engine set** = `{row["engine"] for row in dispatch_calibration(cwd=repo_root)} ∩ DISPATCHABLE_ENGINES`
  (claude is never probed by rule). Missing engine → `probe-missing:<engine>`; two results for one
  engine → `probe-duplicate:<engine>`; a result whose `repoRoot` ≠ realpath(`--repo-root`) →
  `probe-foreign-repo:<engine>`; `completedAt` older than `--max-age-seconds` (default 3600) →
  `probe-stale:<engine>`; unparseable `completedAt` → `probe-stale:<engine>`.
- `--launch-without E --owner-word W` pairs: `E` must be a failed engine in the results (else
  `launch-without-not-failed:<E>`); `W` must be non-blank (else `owner-word-blank`); a
  `--launch-without` with no `--owner-word` refuses `owner-word-missing`.
- **Maker family:** the calibrated implementer row's `(engine, model)` →
  `model_registry.model_family(vendor, model_id)` (measured: `model_family("cursor","composer-2.5") == "xai"`,
  `model_family("codex","gpt-5.6-sol") == "openai"`, `model_family("claude","opus-5") == "anthropic"`;
  `None` for an unregistered id). The implementer's `model` cell may be a pin string like
  `composer-2.5`; resolve through `model_registry.resolve_dispatch("implementer", engine, model)["model_id"]`
  (unmeasured — verify the return keys before use). Unresolved family → refuse `author-family-unresolved`.
- **Decision:** with no failed engine → entry `{"state": "pass", "reason": "conformance probes passed: <engines>", "evidence": "<per-engine one-liners>"}`.
  With a failed engine and no owner word for it → `{"state": "fail", "reason": "conformance probe failed: <engine> (<legs>) — hold; nothing launches without the owner's word", "evidence": …}`.
  With every failed engine covered by an owner word → build the substitution readout:
  `seat_map.build(None, live_vendors, author_family, None, seed, live_cells=<probed cells of PASSING engines> + ("claude", "opus-5", "xhigh") style entries are NOT to be invented — pass only the probed cells and let build add claude by its own rule when "claude" is in live_vendors>, live_cells_source="probed")`
  where `live_vendors` = passing engines + `["claude"]`; `seed` any fixed int (e.g. 0). Measured
  shape: `sm["seats"][seat] == {"vendor","model","effort","tier","family",…}`, `sm["degradations"]`
  is a list of `{"constraint": …, "reason": …[, "seat": …]}`; a `same-family` degradation looks like
  `{"constraint": "same-family", "seat": "architecture-reviewer", "reason": "seat architecture-reviewer seated the maker family anthropic — no alternative family is live"}`.
  If any degradation has `constraint == "same-family"` → entry `{"state": "fail", "reason": "conformance probe failed: <engine>; launched without it on the owner's word — full lanes PARK: <seats> would seat the maker family <family>", …}`
  (a `fail` here is the park — the launcher refuses, by design). Otherwise
  `{"state": "pass", "reason": "conformance probe failed: <engine>; launching without it on the owner's word: <word>", "evidence": "substitutes — <seat>: <family>/<vendor>/<model>; …; other degradations: <constraints>; implementer calibrated on <engine>: <yes/no>"}`.
- Output: `{"schema": "conformance-preflight-entry/1", "ok": true|false, "reason": <refusal or null>, "engine-auth": <entry or null>, "required": […], "failed": […], "seatMap": <sm or null>}`;
  exit 0 when `ok` (a `state: fail` entry is still `ok: true` — it is a valid, recordable entry), exit 1 on a refusal.
- **Fail-closed edges (echo each with its disposition in your return):** (1) unreadable/malformed result
  file; (2) result for an engine not in the required set (report it, do not count it);
  (3) missing engine; (4) duplicate engine; (5) foreign repo; (6) stale/unparseable `completedAt`;
  (7) `--launch-without` for a passing engine; (8) blank or missing owner word; (9) calibration
  unreadable → refuse `calibration-unreadable`; (10) author family unresolved; (11) `seat_map.build`
  raising → refuse `seat-map-failed:<exc class>` (never a pass).

### Launcher fold (`lib/launcher.py`)

In `walk_preflight` (measured: `lib/launcher.py:831-927`), the `if state == "fail": return _fail("preflight-failed:%s" % check_id)` branch must append the failing entry to `out_checks` first and return `_fail("preflight-failed:%s" % check_id, checks=out_checks)`, so `_try_reserve_for_refusal` (measured: it records `(preflight_result or {}).get("checks") or []`, `:1853`) keeps the failed engine's evidence in the refusal ledger record. Every other refusal in that function is unchanged. `_preflight_extra` (`:541-549`) copies `missing/remedy/path/cause` only — do not add `checks` there; the refusal record path reads `checks` from the result directly. Verify by reading `_try_reserve_for_refusal` and `_record_refusal` (unmeasured names past `:1836` — verify) before editing.

## Tests (`lib/tests/test_conformance_probe.py`) — use the shell's `run_engine` injection seam

Read `lib/tests/test_engine_dispatch.py` for how tests inject `run_engine` into `dispatch_review`
(search `run_engine=`), how they build a `--seat`, and the `tmp_path` run-dir conventions; and
`lib/tests/conftest.py` for the pinned store roots. Your module must accept a `run_engine` keyword on
its library function (`probe(engine, repo_root, run_dir, timeout, run_engine=None)`) that it
threads into `dispatch_review` — that is the test seam; the CLI never exposes it.

Required tests (one function each, named as listed):
1. `test_engine_set_is_derived_from_adapter_and_channel_map` — `DISPATCHABLE_ENGINES == ("codex", "cursor")` and `claude` refuses `engine-not-dispatchable`.
2. `test_run_grades_three_legs_ok_on_valid_native_result` — inject a `run_engine` that writes a schema-valid verdicts result file at the native result path AND a codex-events stdout with ≥1 `item.completed` action item (read `engine_adapter._CODEX_ACTION_ITEM_TYPES` / `codex_tool_calls` for the measured shape) → all legs ok, exit-shape `ok: true`, `preflightCheck.state == "pass"`.
3. `test_result_production_fails_on_schema_invalid_native_result` — result file violates the schema → `resultProduction.ok is False` with `detail == "native-result-schema-invalid"`, the other legs graded independently (completion ok, telemetry ok).
4. `test_completion_fails_on_timeout` — `run_engine` that records `timedOut: True` → `completionDetection.detail == "no-response-within-wait"`.
5. `test_completion_fails_on_refusal_names_auth_or_config` — a guard/spawn refusal (`ended["refusal"]` set) → `auth-or-config-refusal`, evidence scrubbed.
6. `test_telemetry_fails_when_stream_has_no_tool_calls` — valid result, stdout with no codex events → `progressTelemetry.detail == "telemetry-absent"`.
7. `test_cli_failure_is_loud` — run the CLI `main([...])` with a failing injected seam (or subprocess with an unroutable engine name) → exit 1 and the stderr line `CONFORMANCE PROBE FAILED engine=…` naming the failed legs and the dependent-lanes sentence.
8. `test_dependent_roles_from_calibration` — with `prefs`/`tiers` seams (see `test_preflight_probe.py` for `dispatch_calibration(prefs=…, tiers=…)`) → codex maps to `brief-check`, `review-code`.
9. `test_preflight_entry_hold_when_failed_without_owner_word` — a failed codex result → `engine-auth.state == "fail"`, reason contains "hold".
10. `test_preflight_entry_refuses_missing_duplicate_foreign_stale` — four cases in one parametrized test.
11. `test_preflight_entry_launch_without_names_substitutes_from_probed_cells` — codex failed, cursor passed, owner word given, implementer calibrated on cursor (maker family `xai`) → `state: pass`, evidence names substitutes; assert `seat_map.build` was called with `live_cells_source="probed"` and only the probed cells (monkeypatch `seat_map.build` to capture kwargs).
12. `test_preflight_entry_parks_on_same_family` — cursor failed, codex passed, implementer calibrated on codex (family `openai`) → the seat map seats openai everywhere → `state: fail` with "PARK".
13. `test_preflight_entry_refuses_blank_owner_word_and_unfailed_engine`.
14. `test_walk_preflight_failed_check_carries_checks` (in `test_launcher.py`) — a checks input with `engine-auth: fail` → the refusal dict has `checks` containing the `engine-auth` entry with its evidence; and `test_launch_refusal_record_keeps_failed_check` — through the CLI/launch path that reaches `_try_reserve_for_refusal`, the ledger's refusal record's `preflight.checks` names it (read `test_launcher.py` for the existing refusal-record fixtures and reuse them).

## Bite-proof (R27 i) — the detectors this order births

Guarded elements, each with its neutralization (a targeted, reversible edit inside your surface) and the test expected red:
- **G1 the result-production leg** — neutralize: make the leg return `ok: True` unconditionally → test 3 red.
- **G2 the completion leg** — neutralize: drop the `timedOut` check → test 4 red.
- **G3 the telemetry leg** — neutralize: `telemetry-absent` never assigned → test 6 red.
- **G4 loud failure** — neutralize: the stderr line not printed / exit 0 on failure → test 7 red.
- **G5 the owner-word gate** — neutralize: `launch-without` accepted with a blank word → test 13 red.
- **G6 the same-family park** — neutralize: ignore `same-family` degradations → test 12 red.
- **G7 the launcher fold** — neutralize: return `_fail` without `checks` → test 14 red.
- **G8 the derived required set** — neutralize: skip the missing-engine check → test 10 red (missing case).
Record each red and green per `rubric/bite-proof.md` § The record in the record file (deliverable 5), with the restored lines quoted back.

## Test-command budget (scoped; the bite-proof reds and greens sit inside it)

Use exactly this interpreter and flags (Apple's python caches bytecode outside the tree; the prefix is load-bearing):
`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woA -m pytest <files> -q -p no:cacheprovider`
Budget: at most **30 invocations** in total —
- up to 8 runs of `plugins/superheroes/lib/tests/test_conformance_probe.py` (development),
- up to 4 runs of `plugins/superheroes/lib/tests/test_launcher.py`,
- 16 bite-proof runs (8 reds + 8 greens, each a single test node via `::<name>`),
- 2 final runs: `test_conformance_probe.py test_launcher.py` together, and
  `/usr/bin/python3 .github/scripts/validate_skills.py` (a validator, scoped by construction; from the worktree root).
Never run the whole suite. Also run `grep -nE '[^ ]  +[^ ]'` over your changed `.py` files (exit 1 = pass).

## Shared contract with the sibling orders (validity rule 5)

WO-C (prose) documents this module by the exact names above: the file `lib/conformance_probe.py`,
verbs `run` and `preflight-entry`, flags as listed, the three leg names `resultProduction` /
`completionDetection` / `progressTelemetry`, the refusal tokens listed, the stderr line, and the
`engine-auth` entry shape. Do not rename any of them; if one cannot be implemented as stated, stop
and report the seam rather than renaming. WO-B touches `engine_dispatch._journal_read_raw` and
`payload_contracts` — you do not.

## Return

Per the implementer template's Short structured return: files changed; per-command report with raw
output; the per-edge echo for the eleven fail-closed edges; the bite-proof record contents (or the
disclosure shape for any element you could not prove); findings. Then the runner's write-report tail.
