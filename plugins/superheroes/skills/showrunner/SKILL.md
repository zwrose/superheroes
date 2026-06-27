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
   produce a PR but hand it back for you to confirm checks before merging).

2. **Launch the bundle on the Workflow tool.** Read the committed, self-contained bundle and
   invoke the **Workflow tool** with that script and the work-item argument — never re-bundle or
   edit the spine here:

   ```bash
   cat "$LIB/showrunner.bundle.js"
   ```

   Invoke the Workflow tool with that script text and `args: {workItem: <work-item>}`. The bundle
   runs the native front-half → build → review → ship pipeline; it parks (never merges) on a red
   gate and hands back a ready-for-review PR when the branch is base-current and CI is green.

3. **Render the codified readout.** On completion, assemble the run-end readout via the deciders
   and print it — the PR link, CI status, built-vs-acceptance, test-pilot result, and the
   merge-reminder, all secret-scrubbed:

   ```bash
   python3 - "$ROOT" <<'PY'
   import sys
   sys.path.insert(0, sys.argv[1] + "/plugins/superheroes/lib")
   import run_readout, readout
   # <state> is the run-end dict the Workflow run returned (PR record, CI decision, acceptance, etc.)
   print(readout.build_readout(run_readout.assemble(state)))
   PY
   ```

   If pre-flight stopped the run or the pipeline parked, surface that reason instead of a readout
   (the blocking check's remediation, or the park reason) and stop. **Never instruct merging** —
   the final PR is yours to merge.

## Resume / relaunch

Re-invoke **Start** unchanged. The spine's `reconcile` skips completed phases and reuses the
work-item's existing PR, so a resume after a park, compaction, or crash is the same entry — no
special handling. A stale or absent run-lease lets the relaunch proceed; only a live conflicting
run blocks at pre-flight.

## Status

Read the work-item's run-outcome projection (and its last readout) and print it — the status,
current phase, PR link, CI checks, and phases traversed:

```bash
python3 - "$ROOT" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/plugins/superheroes/lib")
import run_readout
# <state> is the work-item's recorded run-end state
print(run_readout.run_outcome(state))
PY
```

This is a read — it launches nothing and changes no branch.
