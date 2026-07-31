# Contents

1. [Dispatch mechanics — long dispatches you own](#dispatch-mechanics--long-dispatches-you-own)
2. [Supervised write dispatch](#supervised-write-dispatch)
3. [Engine forfeits and order shape](#engine-forfeits-and-order-shape)

---

# Dispatch mechanics — long dispatches you own

Read this at dispatch time, before you invoke a long dispatch. **In-turn background-and-poll** is the
normal path past the foreground Bash cap; **shell-detach** so work outlives the turn is the rare
fallback. The **detach-and-park contract** (files not pipes, stamp and completion sentinel before
waiting, shell-detach not harness-background, durable park, recovery rules) is **only** in the workhorse
charter §7 (Channel-conditioned) — not restated here. Mechanics by dispatch kind:

- **A shell/CLI run** (an engine CLI invoked through the host's run action) is bounded by the host's
  Bash timeout. On the Claude host (harness **2.1.219**) that is **ten minutes (600 s) — a
  foreground-conversion boundary, not a ceiling you lift by passing a bigger `timeout`**: the plugin's
  `bash_timeout` hook injects 600 s **only when a call omits its own `timeout`** (an explicit one is
  never touched), and the host **converts** a foreground call whose `timeout` exceeds 600 s to
  background — it does **not** clamp-and-kill at 600 s. What kills a converted run is **the turn
  ending**. Give the dispatch that room by **backgrounding the run and polling it** — a backgrounded
  run is not bound by the foreground cap — never by trying to raise a foreground timeout. Redirect its
  output to a **file, never a pipe or `| tail`** — pipes die with the reader and make a stall look
  like progress. Watch that **output/transcript file growing as your primary stall signal**: a growing
  file is live; use the process's **CPU-time column only as corroboration** (an engine CLI can sit at
  ~0% CPU for minutes and still be live, so CPU alone can't separate idle-but-live from stuck). Treat
  **elapsed time as your *runaway* bound, not a liveness signal** — a quiet run may still be live, but
  one that has far outrun any plausible dispatch time is a runaway to kill even while its file grows.
  Four 0.18.0-wave sessions died as **turn-end kills of converted runs** mid-dispatch — one
  mid-review-panel — losing the run (WE review session, WE-510, sh-566, WE-484). **If the dispatch
  cannot finish inside the turn:** follow the charter's detach-and-park fallback (§7 Channel-conditioned);
  the output-file stall signals above still apply to the detached child.
- **A native subagent dispatch** has a **harness-managed lifecycle** — no `bash_timeout` floor and no
  CPU column of your own to watch — so those shell mechanics don't apply and there is **no caller-set
  ceiling to invent**; the harness manages the lifecycle and returns when the subagent completes. **No
  shell-detach** — await in-turn when you dispatch; if it genuinely cannot fit the turn, **do not
  dispatch** — park durably on the issue or PR **with the work order ready** (charter §7), or split so
  each dispatch fits one turn.

## Supervised write dispatch

The sanctioned way to dispatch a long-running **external implementer** is the supervised runner:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/engine_dispatch.py" dispatch-write \
  --engine "$IMPL_ENGINE" --engine-model "$IMPL_ENGINE_MODEL" \
  --prompt-path "$ORDER_PROMPT" --cwd "$BUILD_WORKTREE" --order-id "$ORDER_ID" \
  --run-dir "$RUN_DIR" --max-wait 540
```

`$IMPL_ENGINE` and `$IMPL_ENGINE_MODEL` come from the project's dispatch calibration for the
**implementer** role. `--effort` is **optional** on `dispatch-write` because a registry model may
legitimately carry no effort, while it stays **required** on `dispatch-review`; an engine/model that
*does* need an effort still fails closed without one (`engine-config:invalid-model-effort`,
`attempts: 0`, no spawn, no lease). Re-invoke the **originating verb**
(`dispatch-write`, never `dispatch-poll`) with the same `--run-dir` and `--max-wait 540` while
`.terminal` is false. A non-terminal `{"reason": "running", "terminal": false}` is **not** a forfeit.
`dispatch-poll` is observational and never spawns; `dispatch-abandon` abandons a run directory. Every
result carries `terminal`, `argv` (the exact spawned command), and `runDir`. Omitting `--max-wait`
loops until terminal in 540 s slices (below the 600 s foreground-conversion boundary on harness
2.1.219). The runner owns the bound — its per-attempt timeout, journal, and bounded slice — so **do
not compose a separate per-dispatch watchdog** on top of it. **`cwd` must be a linked build worktree**
— a primary checkout is refused (`cwd-primary-checkout`) — which is exactly why this is the workhorse's
implementer path and not review-code's in-place fixer path. `BASH_MAX_TIMEOUT_MS` is a **headless-launch
premise field owned by [#656](https://github.com/zwrose/superheroes/issues/656)**; this change sets it
nowhere.

## Engine forfeits and order shape

An external engine can forfeit *after* its files are written. Cursor's `NonRetriableError "Agent
Looping Detected"` characteristically fires while the engine is producing a long report, with the
on-disk work already complete and correct — field evidence: three builds in one wave; in one of them
four of six dispatches forfeited, **every one with correct files on disk**. **Inspect the dispatch
worktree before you discard or re-dispatch anything** — but "inspect the diff" alone is not a
decision rule:

- Look at **base→HEAD plus staged, unstaged, and untracked state** — a forfeited engine may have committed, so a bare `git diff` can be empty while the work is complete; untracked new files are invisible to it too.
- Confirm **every target the work order named** is actually present. Partial work looks like work.
- **The orchestrator's own gates are what authorize keeping it.** A forfeit with complete work is a
  **recovery** — verify it yourself exactly as you would verify a clean return. Partial or out-of-scope
  state is **not** recovered: re-dispatch or park, and never let "inspect first" become "assume work
  exists" — a forfeit with nothing on disk is simply a failed dispatch.
- Re-dispatching without looking re-does correct work and re-runs the very report that forfeited.

Author orders so the forfeit does not fire: keep in-dispatch verification targeted and returns short
and structured. The implementer template `agents/implementer.md` states this to the implementer
directly, so an order that additionally demands a full-suite run, a pasted diff, or a long verbatim
report is **overriding the template against its own purpose**.

Never assume the implementer can run anything. An external engine's shell availability is set
**outside your build** — the engine CLI consults its own permission surface, not your order. It is
normally available on the sanctioned write path, but two builds in one wave had **every** implementer
shell call rejected, and that is not yet explained — so it **cannot be inferred from a previous
build**. Write every external order to be correct when the implementer can run nothing; the
orchestrator's own re-run is the verification either way, and a corrective round is worth budgeting.
