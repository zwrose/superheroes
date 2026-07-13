---
name: showrunner
description: Use when an approved work-item (gates.review == passed on its spec) should be RUN end-to-end by the live showrunner — "launch the showrunner", "run the showrunner on this work item", "take this approved work-item all the way to a ready-for-review PR". Runs a deterministic pre-flight gate, then drives the native front-half → build → review → ship pipeline to a ready-for-review PR. It NEVER merges — that is always yours.
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Showrunner — the live run engine

Turn the already-merged showrunner spine **on** for one approved work-item. The skill is
**control-flow narration only**: it runs a deterministic pre-flight gate, hands the live run to
the Workflow tool on the committed bundle, and renders the codified readout at the end. Every
judgement stays a pure decider — the skill asks no question a decider can answer and **never
merges, deploys, releases, or force-pushes** (those are the owner's; the run confines its changes
to the work-item's own branch and its PR).

Resolve the plugin lib dir once: `LIB="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib"`, and the repo
root: `ROOT=$(git rev-parse --show-toplevel)`.

This skill is **re-invocable**: the same entry covers a fresh start, a resume/relaunch after a
park or crash, and a status read. The advisory path-choice record is not authoritative — the run
state is; a never-started showrunner pick simply re-enters here.

## Start

1. **Pre-flight (deterministic gate).** Run the pure pre-flight decider — it fail-closes any
   check it cannot substantiate:

   ```bash
   python3 "$LIB/preflight.py" --work-item "<work-item>" --root "$ROOT"
   ```

   Parse the verdict JSON. On `ok: false`, print each `blocking` check's `cause` + `remediation`
   and **STOP** — do not launch. On `ok: true`, print the launch confirmation; when an
   `advisory` entry with `check: ci-visibility` is present, surface its `note` too (the run will
   produce a PR but hand it back for you to confirm checks before merging). The pre-flight is
   **route-aware** (#25): it gates on the **spec** on the full route and on the **tasks** doc on
   the quick route, and the verdict echoes the resolved `route` (`full` | `quick`) — a validated
   literal the launch step (2) declares to the spine. Read `route` from the verdict; do not
   free-type it.

1.5. **Preflight readout — confirm/override the run (the one interactive surface).** After the
   gate passes, show the owner exactly what the confirmed run will dispatch and let them override
   any overridable role for this run, then confirm. **No agent dispatches before this confirm**
   (FR-1). Read the recorded per-run overrides first, so a relaunch re-renders with what was
   already accepted (FR-9/FR-14):

   ```bash
   OV=$(python3 - "$LIB" "<work-item>" "$ROOT" <<'PY'
   import sys, json
   sys.path.insert(0, sys.argv[1]); import run_overrides
   print(json.dumps(run_overrides.read(sys.argv[2], sys.argv[3]).get("overrides") or {}))
   PY
   )
   ```

   - **Assemble** the snapshot from the run's own resolvers (never a parallel table), carrying the
     accumulated overrides so the render matches dispatch:

     ```bash
     python3 "$LIB/preflight_readout.py" assemble --work-item "<work-item>" --root "$ROOT" \
       --run-overrides "$OV"
     ```

     Parse the snapshot JSON. On a **total-failure sentinel** (`ok:false`), print its `reason` +
     `remediation` and **STOP** — do not launch (UFR-3, fail-closed, matching the gate's posture).
     A snapshot with a non-empty `degraded[]` is NOT a failure: each degraded field renders as
     `unavailable` and the run still proceeds (UFR-2).

   - **Render** the readout and print it verbatim (or render in-process via a heredoc, like the
     run-end readout in step 3):

     ```bash
     python3 "$LIB/preflight_readout.py" render --snapshot "$SNAPSHOT_JSON"
     ```

     A recorded override that is **no longer valid** prints on its own phase line as
     `recorded override no longer valid, NOT applied ⚠` — carried, not silently applied (FR-14).
     A role whose engine is unauthorized prints on its own row as `falls back to Claude ⚠`
     (FR-4). Provisional (not owner-confirmed) calibration is flagged; the verify command and the
     storage mode + docs read/write location are named.

   - **Ask the owner** via the host **ask primitive** (resolve per the host tool map), and loop:
     - **Confirm** → freeze the snapshot + persist any accepted overrides to the durable per-run
       record, then proceed to step 2 (launch). The spine reads this frozen snapshot at startup so
       dispatch honors it even if config is edited afterward (FR-8/FR-13):

       ```bash
       python3 - "$LIB" "<work-item>" "$ROOT" "$OV" "$SNAPSHOT_JSON" <<'PY'
       import sys, json
       sys.path.insert(0, sys.argv[1]); import run_overrides
       run_overrides.write(sys.argv[2], sys.argv[3], json.loads(sys.argv[4] or "{}"),
                           json.loads(sys.argv[5]))
       PY
       ```

     - **Override** → collect `role`, `field` (engine/model/effort), and `value`, then gate it:

       ```bash
       python3 "$LIB/preflight_readout.py" validate-override \
         --role "<role>" --field "<field>" --value "<value>" \
         --snapshot "$SNAPSHOT_JSON"
       ```

       On `ok:false`, show the verdict's `acceptedValues` + `reason`, keep the currently-effective
       value, and re-prompt (UFR-6). On `ok:true`, fold the accepted `{role:{field:value}}` into
       `$OV`, re-assemble (`--run-overrides "$OV"`), re-render (the overridden line marked, all
       others unchanged, FR-11), and re-confirm.

     - **Decline** → abort the launch immediately: **no `run_overrides.write`, no bundle launch,
       the run is not marked started, no branch or PR touched** (UFR-1). Print a plain
       `aborted, no changes` line and stop.

2. **Launch the bundle on the Workflow tool.** Read the committed, self-contained bundle and
   invoke the **Workflow tool** with that script and the work-item argument — never re-bundle or
   edit the spine here:

   ```bash
   cat "$LIB/showrunner.bundle.js"
   ```

   Invoke the Workflow tool with that script text and
   `args: {workItem: <work-item>, root: <ROOT>, libRoot: <LIB>}` — pass the resolved `$ROOT`
   (target repo) and `$LIB` (the versioned plugin-cache lib dir) so the run operates on this repo
   while executing the spine from immutable cache code, portable to any project. **On the quick
   route** (the pre-flight verdict's `route` is `quick`), also pass `route: "quick"` in that args
   object so the spine's intake **declares** the route explicitly — it is validated by
   construction (the verdict only ever emits `full`/`quick`, never a typo), and the spine refuses
   fail-closed if a declared route ever conflicts with the on-disk artifact. A `full` verdict
   launches with the args unchanged (no `route` key — the spine derives `full` from the spec). The
   bundle runs the native front-half → build → review → ship pipeline; it parks (never merges) on
   a red gate and hands back a ready-for-review PR when the branch is base-current and CI is green.
   Then print the zero-token watcher command for a second terminal:

   ```bash
   python3 "$LIB/run_watch.py" --work-item "<work-item>" --root "$ROOT" --print-command
   ```

   Show its single-line output under: `Watch this run live (zero tokens) from another terminal:`

3. **Render the codified readout.** On completion, assemble the run-end readout via the deciders
   and print it — the PR link, CI status, built-vs-acceptance, test-pilot result, and the
   merge-reminder, all secret-scrubbed:

   ```bash
   python3 - "$ROOT" <<'PY'
   import sys
   sys.path.insert(0, sys.argv[1] + "/plugins/superheroes/lib")
   import run_readout, readout, control_plane
   # <state> is the run-end dict the Workflow run returned (PR record, CI decision, acceptance, etc.)
   # #130: set events_path to the work-item's events.jsonl so the readout's run-cost line
   # (dispatches + output tokens + the most expensive phases) renders from the run's own journal.
   state.setdefault("events_path", control_plane.paths(sys.argv[1], "<work-item>")["events"])
   print(readout.build_readout(run_readout.assemble(state)))
   PY
   ```

   If pre-flight stopped the run or the pipeline parked, surface that reason instead of a readout
   (the blocking check's remediation, or the park reason) and stop. **Never instruct merging** —
   the final PR is yours to merge.

   For the cross-run efficiency trend (tokens-per-completed-work-item and tokens-per-park across
   this checkout's recorded runs), point the owner at:

   ```bash
   python3 "$LIB/token_trend.py" --root "$ROOT"
   ```

## Resume / relaunch

Re-invoke **Start** unchanged. The spine's `reconcile` skips completed phases and reuses the
work-item's existing PR, so a resume after a park, compaction, or crash is the same entry — no
special handling. A stale or absent run-lease lets the relaunch proceed; only a live conflicting
run blocks at pre-flight.

## Status

Read the work-item's run-outcome projection (and its last readout) and print it — the status,
current phase, PR link, CI checks, and phases traversed:

`<state>` is the run outcome loaded from the work-item's control-plane run record (its last
recorded readout / run-end state) — not a fresh run.

```bash
python3 - "$ROOT" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/plugins/superheroes/lib")
import run_readout, control_plane
# <state> is the work-item's recorded run-end state (read from the control-plane run record)
# #25: point run_outcome at the run's journal so a quick run's route + skipped front-half phases
# project honestly (derived from the phases_skipped event), instead of defaulting to full/[].
state.setdefault("events_path", control_plane.paths(sys.argv[1], "<work-item>")["events"])
print(run_readout.run_outcome(state))
PY
```

This is a read — it launches nothing and changes no branch.
