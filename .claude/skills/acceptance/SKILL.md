---
name: acceptance
description: Use to run the standalone showrunner acceptance harness — "run the acceptance harness", "acceptance-test the showrunner", "verify the showrunner end-to-end on the fixture". Takes NO free-form input — it launches the real showrunner on a canned throwaway fixture, judges the terminal outcome against machine-checkable facts, tears down every artifact on every exit path, and hands back one plain-language pass/fail verdict. It NEVER merges and refuses to nest inside a run.
user-invocable: true
---

# Acceptance harness — the developer front door

> **Repo-local dev tool.** This skill validates the superheroes band itself; it is not
> distributed with the plugin (issue #237). It lives in the repo checkout and resolves the
> harness lib from that checkout — repo-local skills cannot use `${CLAUDE_PLUGIN_ROOT}`, and
> that's correct: the acceptance run is checkout-bound by definition (it points the run at this
> tree). It runs on Claude Code; each "run this shell command" step is the Bash tool.

Durabilize the one-shot manual acceptance run into one command. The skill is **control-flow
narration only**: it takes **no free-form input** (the fixture is canned — UFR-7), refuses
**before any launch or create** when it detects it is running inside a showrunner or acceptance
run (UFR-5), and otherwise delegates the whole invocation to `acceptance_run.invoke`. Every
judgement stays a pure decider; the skill asks no question a decider can answer and **never
merges, releases, or force-pushes** — the launcher structurally denies those owner-authority
actions in the child (UFR-6), and the final verdict is the owner's to act on.

Resolve the repo root and the plugin lib dir from the checkout once:
`ROOT=$(git rev-parse --show-toplevel); export LIB="$ROOT/plugins/superheroes/lib"`. The
`export` matters: step 1 reads `LIB` back via `os.environ["LIB"]` inside a quoted heredoc child
process, which only sees exported variables.

## Start

1. **Refuse to nest (UFR-5) — before anything else.** Read the execution-context marker and stop
   if it is set. This marker is distinct from the on-disk `active_run` lease state: it is the
   environment flag the launcher sets on the child, so a nested invocation refuses without touching
   any state.

   ```bash
   python3 - <<'PY'
   import os, sys
   sys.path.insert(0, os.environ["LIB"])
   import acceptance_run
   r = acceptance_run.nesting_refusal(os.environ)
   print(r["reason"])
   sys.exit(1 if r["refuse"] else 0)
   PY
   ```

   On a non-zero exit, print the refusal reason — acceptance runs cannot nest inside the pipeline
   they test — and **STOP**. Create nothing, launch nothing.

2. **Refuse on a missing or drifted prerequisite (UFR-7).** The orchestrator runs the deterministic
   pre-flight decider and the committed-fixture drift check as its first in-process steps; a failed
   pre-flight or a drifted fixture (absent, phase-list drift, or a missing target file) refuses
   before launching anything and names what is missing or drifted — the drift is never reported as
   a pipeline failure.

3. **Delegate the whole invocation.** Hand the run to the orchestrator, which sequences the entire
   lifecycle (reclaim/refuse a prior run → materialize the stamped throwaway fixture → pre-flight →
   launch the real showrunner out-of-process → judge the terminal outcome and the readout-vs-reality
   consistency → tear down every stamped artifact on every exit path → write exactly one result
   record → release the lease only after the record is durable):

   ```bash
   python3 "$LIB/acceptance_run.py" --fixture "$LIB/../eval/fixtures/acceptance" --root "$ROOT"
   ```

   Optional owner ceilings are supported when a run needs a tighter or looser harness budget:
   pass `--ceilings-config /path/to/ceilings.json` where the JSON object may contain
   `elapsed_sec` and/or `spend`, or pass `--ceiling-elapsed-sec <seconds>` /
   `--ceiling-spend <measured-output-tokens>` directly. Unset or partial values fall back to
   the built-in defaults: 1800 elapsed seconds and 5,000,000 measured output tokens. The
   `spend` ceiling is measured output tokens, not dollars.

   **Pre-release gate (`--spine-lib`).** By default the child launches the spine from the
   installed plugin cache — the last *released* version — so merged-but-unreleased spine
   changes are invisible (post-release smoke). To gate merged `main` **before** cutting a
   release, pass `--spine-lib "$LIB"` pointing at the checkout's own
   `plugins/superheroes/lib` (must contain `showrunner.bundle.js` + `showrunner.js`): the
   child then resolves the **entire** spine from that tree — pre-flight, the committed bundle,
   the Workflow `libRoot`, and the run-outcome projection — never a cross-version mix of a
   cached pre-flight against a main bundle. Phase-truth follows the same tree, and the
   record/report record the bundle's SHA-256 so the pass is attributable to the exact spine.
   A missing dir / bundle / `showrunner.js` refuses pre-launch, naming the path (never a
   silent fall-back to the installed plugin). The exact happy path — run it on merged `main`,
   pointing `--spine-lib` at that same checkout's lib:

   ```bash
   git -C "$ROOT" checkout main && git -C "$ROOT" pull
   python3 "$LIB/acceptance_run.py" \
     --fixture "$LIB/../eval/fixtures/acceptance" \
     --root "$ROOT" \
     --spine-lib "$LIB"
   # green verdict (recording main's bundle hash + driver model) -> the release evidence gate
   ```

   The child **driver** session is pinned to `sonnet` by default so it never inherits the
   invoking user's CLI model (model-governance); override with `--child-model <model>` if
   needed. Every verdict's provenance names both the spine under test and the driver model.

4. **Render the single verdict report.** Print the orchestrator's one plain-language report — the
   pass/fail verdict, the reason, where the result record lives, and what was cleaned up or left
   behind — and stop. **Never instruct merging**; the run mutates no real state and the verdict is
   yours to act on.

This is a one-shot, unattended command: exactly one record and one report per invocation, never a
merge, and protected against mutating real state by structure.
