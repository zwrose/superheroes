# Contents

1. [Dispatch mechanics — long dispatches you own](#dispatch-mechanics--long-dispatches-you-own)
2. [Supervised review dispatch](#supervised-review-dispatch)
3. [Supervised write dispatch](#supervised-write-dispatch)

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

## Supervised review dispatch

The sanctioned way to dispatch a long-running **external reviewer** seat is `dispatch-review`. The
full stdout and result contract lives in `auto-fix-loop.md` — read that before authoring seat
prompts; this subsection is the at-dispatch-time summary only.

Every `dispatch-review` result is a **top-level** object. **Always present:** `ok`, `terminal`,
`runDir`, and `argv`; on a failure, `reason` (and usually `detail`). **Outcome-dependent:**
`findings`, `investigated`, `engagement`, and `sanitizedView` — do **not** read an absent `findings`
as "zero findings". An `unrunnable` refusal carries no `findings` / `investigated` / `engagement`; it
carries `sanitizedView` **only when raised after the sanitized view was built** — the early refusals
(`repo-root-*`, `prompt-*`, `run-dir-*`, `schema-*`) precede the view and carry none. A terminal
forfeit carries no `findings`/`investigated`. There is no `result` wrapper; `result.findings` reads
nothing.
The runner's transport carries **only** `findings` and `investigated` from the seat's stdout — every
other key the seat emits is dropped, so verdict-shaped or other alternate payloads parse `unreadable`,
retry once, and forfeit.

When the result carries an **`engagement`** block with a non-`null` value (present only when the
attempt produced stdout that was graded), `engagement.read` is `"engaged"` when the seat
demonstrably acted (a finding, an accepted `investigated` path, or `engagement.toolCalls >= 1`);
otherwise `"unknown"`. On a timeout, refusal, nonzero-exit, or missing-stdout forfeit the
`engagement` key is **present with the value `null`** (there was no graded stdout to measure), so
`engagement.read` is unavailable — `result.get("engagement", {})` is **unsafe** because the key may
carry `null`, not merely be missing; consumers must handle a `null` value. The runner **never**
asserts `"inert"` — absence of positive evidence is not proof of inaction, and only `seat_canary
probe` can justify calling a seat inert. Token spend does not measure engagement: through the
calibrated codex reviewer seat, a 2,449-token dispatch was engaged-clean and a 10,415-token
dispatch produced a Critical finding.

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
