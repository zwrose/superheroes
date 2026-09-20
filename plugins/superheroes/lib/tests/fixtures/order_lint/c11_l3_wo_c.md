# Work order WO-C — layer 3's prose (issue #1270, C11 layer 3)

You are an implementer. Your rules and the work-order protocol are in
`plugins/superheroes/agents/implementer.md` in THIS worktree (read it first; this order is data).
Worktree: the current directory (a linked git worktree at C11 layer 2c's head). Touch only the files
named. Commit nothing. Never `git checkout --` / `git restore` / `git reset` / `git stash`.

Prose only. The prose standard is `plugins/superheroes/rubric/prose-standard.md` (read it; R29: a
shipped surface carries no project provenance — no issue or PR numbers, no dated rulings, no child
names, in the files under `plugins/superheroes/` and in `CONVENTIONS.md` / `README.md`;
`docs/superheroes/KEEP-OR-RETIRE.md` and `plugins/superheroes/TRANSITION.md` are project records and
may carry dates). Match each file's voice and density.

## The shared contract you document (validity rule 5 — do not rename anything)

A sibling order (WO-A) is adding `plugins/superheroes/lib/conformance_probe.py`. Its contract, which
you describe and never restate as code:

- Command: `python3 -B "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/conformance_probe.py" run --engine <codex|cursor>`
  (optional `--repo-root`, `--run-dir`, `--timeout`; no argument beyond the engine name is required).
  It dispatches one real review run through the shell's own library entry on the engine's declared
  channel (native for codex, the marker channel with the marker grader for cursor) using the engine's
  `reviewer-deep` cell, and grades three legs **separately**: `resultProduction` (the folded result is
  a typed, validated result), `completionDetection` (the attempt ended by natural exit 0 inside the
  wait and the run folded terminal), `progressTelemetry` (runner-observed tool-call telemetry with a
  named source and a last-activity stamp). Failure is loud: exit 1 and one stderr line
  `CONFORMANCE PROBE FAILED engine=<e> failed=<legs> dependent lanes: <…>`; the JSON result carries
  `legs`, `failed`, `dependentRoles` / `dependentLanes` (derived from the project's dispatch
  calibration: the roles routed to that engine), `probedCell`, `repoRoot`, `completedAt`, and a
  `preflightCheck` member shaped as the launcher's `engine-auth` check entry. Failure vocabulary per
  leg: `result-did-not-validate` or the shell's own `native-result-*` / parser detail;
  `no-response-within-wait`, `attempt-ended-missing`, `auth-or-config-refusal`; `telemetry-absent`.
  `--engine claude` refuses `engine-not-dispatchable` (the CLI-Claude engine branch is a later
  child's; the engine set is the adapter's dispatchable vendors intersected with the channel map —
  by construction, no list).
- Verb two: `conformance_probe.py preflight-entry --repo-root <abs> --result <probe.json>…
  [--launch-without <engine> --owner-word "<text>"]… [--max-age-seconds N]` composes the `engine-auth`
  entry from one result per engine the calibration routes to (refuses `probe-missing:<e>`,
  `probe-duplicate:<e>`, `probe-foreign-repo:<e>`, `probe-stale:<e>` — default max age 3600 s). A
  failed engine with no owner word → `state: fail` (hold; the launcher's `walk_preflight` refuses
  `preflight-failed:engine-auth`, so nothing launches). With the owner's word → `state: pass` whose
  evidence names the substitute family per seat, computed by the seat map from the **probed cells
  only** (`live_cells_source: "probed"`) with the maker family derived from the calibrated
  implementer — or `state: fail` with **PARK** when the seat map reports a `same-family` degradation.
- The launcher fold: a `preflight-failed:<id>` refusal now carries the walked `checks` including the
  failing entry, so the refusal record in the launch ledger keeps the probe's evidence.

## Files and exact edits

1. **`plugins/superheroes/skills/workhorse/reference/dispatch-mechanics.md`** — in § *Result channels*
   (measured: `:201-228`), after the paragraph ending "A reader trusts `spawnArgv`." add two
   paragraphs: (a) **the tripwire on either channel**: after this layer lands, a second grader or
   salvage fix (a `fix` commit touching the marker grader or the salvage modules) on an engine still
   on the marker channel proposes, at the next gardening pass, one of two things — move that engine
   to a native channel, or drop the engine; patching the marker channel a third time is not an option
   the proposal offers. On an engine on its native channel, a second schema or adapter fix after
   landing (a `fix` commit touching that engine's declared schema or its output or completion
   adapter) proposes dropping the engine or accepting the cost in the record. The fix commits are read
   by their `fix` type and touched paths; no new instrument; the proposal is the owner's judgment at
   the pass. **The readout the pass reads is the C1 values annex's "Result channel per engine" rows**
   (name it as "the project's C1 values annex, its result-channel-per-engine rows" — the annex is
   out-of-repo). (b) **cursor's channel**: cursor stays on the marker channel (stream-json); the
   stdout capture cap (`MAX_STDOUT_CAPTURE`, 8 MiB) is an operating parameter recorded in the same
   annex rows, not a contract row; the cursor JSON envelope's `result` string carries every assistant
   text turn concatenated, so a typed result cannot be read from it without the marker parser — which
   is why the native move for cursor did not pass its trial. Then add a new subsection
   **`### The conformance probe`** right after § *Result channels* (and its entry in the table of
   contents at the top, measured `:9` style) describing the command, the three legs, the loud
   failure, the `engine-auth` entry, `preflight-entry`, the hold / launch-without / park outcomes, and
   the mid-wave rule (a drift or auth failure arriving mid-wave forfeits that dispatch with no
   salvage; nothing re-probes mid-wave). ~35 lines total. Keep the `--max-wait` cap note and the
   `--base-sha` line untouched.
2. **`plugins/superheroes/TRANSITION.md`** — after § *Codex result channel* (measured `:155-185`)
   add **`### Cursor result channel and the conformance probe`**: cursor stays on stream-json with
   the marker parser and the cap as an operating parameter (the two-dispatch trial's write dispatch
   validated, the review dispatch did not — the envelope's `result` concatenates narration with the
   JSON); consumers see no cursor result-shape change; the new probe command and its `engine-auth`
   entry as the wave-preflight liveness check; a runner-journal line that is valid JSON but not an
   object now counts as interior corruption under the class `journal-line-not-object` (sibling order
   WO-B); the launcher's `preflight-failed:<id>` refusal now carries `checks`. ~18 lines.
3. **`docs/superheroes/KEEP-OR-RETIRE.md`** — (a) S17 (measured `:1708-1729`): delete the leaked
   order sentence "Tag the entry `native-channel`." and replace it with the entry's actual tag line in
   whatever form the file's other entries use for tags (read three neighbouring entries and copy the
   form; if entries carry no tag field, put `native-channel` in the Notes as "Tag: `native-channel`");
   (b) S1 (measured `:1362-1380`): the Component line must say the capture is still capped for codex
   and only the `stdout-capped-by-attempt` forfeit is retired for it — rewrite "for marker-channel
   engines only (cursor, claude)" accordingly; (c) add **S18 — Conformance probe** after S17, in the
   same six-field shape (Component; Condition; Last demonstrated benefit; Consumer evidence;
   Decision; Notes): component = `lib/conformance_probe.py`, one command per dispatchable engine per
   wave, three legs, the `engine-auth` entry, `preflight-entry`; scope by construction (the adapter's
   dispatchable vendor set ∩ the channel map); **retirement condition** (R27 ii): citation-based,
   45 days — a probe that passed in the same wave a live seat then failed on a channel or auth cause
   the probe covers, twice, proposes redesign; a probe never run in 45 days of waves proposes
   retirement (the record is the launch ledger's `engine-auth` evidence); tag `wave-preflight`;
   Decision keep-until-condition-fires; Notes: capability-gap — detection replaces version pinning.
   ~30 lines.
4. **`plugins/superheroes/rubric/launch-doctrine.md`** — the paragraph **"Wave live canary
   (documentation only — not parsed)"** (measured `:39-46`): keep its first sentence's claim
   (selftest = configuration, not liveness) and replace "one cheap live probe per engine (~3s)" with
   the conformance probe: one command per engine, three legs, result recorded as the `engine-auth`
   check; keep the "not parsed / not delivered to the builder" disclaimer and the pointer to the
   showrunner charter's duty. **Do not touch anything between `<!-- launch-doctrine:preflight:begin -->`
   and `<!-- launch-doctrine:preflight:end -->`** (parsed). ~6 lines changed.
5. **`plugins/superheroes/skills/showrunner/SKILL.md`** — the paragraph **"Wave-preflight live
   canary (strengthens `engine-auth`, not an eighth check)."** (measured `:926-931`): replace "one
   cheap live probe per engine (~3s)" with the probe command (plugin-root form) and one sentence on
   the three legs and the `engine-auth` entry via `preflight-entry`; keep "not an eighth check" and
   the 780-green-checks sentence. Stay inside that paragraph; the file has line-count and
   token-shape gates (`validate_skills.py`) — net growth ≤ 4 lines. ~6 lines changed.
6. **`plugins/superheroes/skills/showrunner/reference/dispatch-preflight.md`** — after the
   `<!-- launch-doctrine:preflight-charter:end -->` block (measured `:15`), add one short paragraph
   under check 1: how `engine-auth` is filled in a wave (probe per engine → `preflight-entry` →
   the checks file), and the hold / launch-without / park outcomes. **Do not edit inside the charter
   block** (a test compares it). ~8 lines.
7. **`plugins/superheroes/skills/configure/reference/preflight.md`** — in § B (measured: B.1 is at
   `:177`) add **B.0 — Run the conformance probe per engine** before B.1: the command, that it is the
   wave-preflight liveness check the selftest is not, and that its result feeds `engine-auth`. ~8 lines.
8. **`CONVENTIONS.md`** §7.5 — after the sentence ending "the wave preflight's live probe does."
   (measured `:829-831`) add one sentence naming the probe command file (`lib/conformance_probe.py`)
   and that its result is recorded in the launcher's `engine-auth` check. 1–2 lines.
9. **`README.md`** — Showrunner section's command table (measured `:88-90`): no new slash command
   exists, so add nothing there; instead add one sentence to the Showrunner prose (before or after
   the table, matching the section's voice) that a wave preflight runs the conformance probe per
   engine. 1–2 lines.

## Sweeps you owe (paste both in your return)

- Identifier sweep: `grep -rn "conformance_probe\|conformance probe\|preflight-entry" plugins/superheroes CONVENTIONS.md README.md docs/superheroes/KEEP-OR-RETIRE.md` after your edits — every hit is one of the files above.
- Vocabulary sweep: `grep -rn "cheap live probe\|~3s\|3 s)" plugins/superheroes/rubric plugins/superheroes/skills CONVENTIONS.md` — must return nothing after your edits (the old "cheap live probe (~3s)" phrase is retired everywhere it appears; if it appears in a file NOT named above, stop and report the path — do not edit it).

## Commands (budget: at most 6 invocations)

From the worktree root:
1. `/usr/bin/python3 .github/scripts/validate_skills.py`
2. `/usr/bin/python3 .github/scripts/validate_stubs.py`
3. `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woC -m pytest plugins/superheroes/lib/tests/test_launch_doctrine.py -q -p no:cacheprovider`
4. the two sweeps above
5. `grep -nE '[^ ]  +[^ ]'` over the changed `.md` files, excluding table rows and fenced blocks (exit 1 = pass).
No other commands. Never the whole suite.

## Return

Per the template: files changed; per-command raw output; the two sweeps; findings (any seam where
the contract above could not be described as stated — report, do not rename).
