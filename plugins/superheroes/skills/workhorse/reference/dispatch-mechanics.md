# Contents

1. [Dispatch mechanics — long dispatches you own](#dispatch-mechanics--long-dispatches-you-own)
2. [Supervised review dispatch](#supervised-review-dispatch)
3. [Supervised write dispatch](#supervised-write-dispatch)
4. [Engine forfeits and order shape](#engine-forfeits-and-order-shape)

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
nothing. Optional **`--diff-base <ref>`** stages the reviewed change as
`SUPERHEROES_REVIEW_DIFF.patch` inside the gitless sanitized view — the machinery external seats need
because `git diff <ref>` and `git log` cannot work there; the `sanitizedView` receipt then also
carries `diffBase`, `diffPath`, `diffBytes`, and `diffWithheldCount` (all `null` when the flag is
omitted). On a continuation (`--run-dir` naming an existing run), `--diff-base` is accepted but
ignored — the live run's view is not rebuilt. Full contract — refusals, withheld stripped-config
paths, investigation-floor rejection — is in `auto-fix-loop.md`.
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

## Engine forfeits and order shape

An external engine can forfeit *after* writing files — characteristically with cursor's
**`NonRetriableError "Agent Looping Detected"`** while the engine is producing a long report, with
on-disk work already complete and correct. Field evidence: three builds in one wave; in one of them
four of six dispatches forfeited, every one with correct files on disk. **Inspect the worktree before
discarding or re-dispatching** — "inspect the diff" alone is not a decision rule:

- **What the tree inspection establishes.** Before dispatching, capture a pre-dispatch baseline —
  same probe as charter §8 `check-runner`: `git rev-parse HEAD` plus full `git status --porcelain` on
  the build worktree. Against that baseline, spanning committed/staged/unstaged/untracked: whether
  **this dispatch** wrote anything at all (**no delta = it wrote nothing**, whatever earlier orders
  left), and whether what it wrote is **inside the order's scope**. The delta test is an **authorship
  and scope** check — each named target must **differ from that baseline**, not merely exist.
- **What it does not establish.** A delta on every named target proves each was **touched**, not that
  the order was **finished** — a partial edit to every target passes it. **Completeness and correctness
  are established only by the orchestrator's own verification against the order's acceptance items**,
  plus standing in for the three evidence channels the forfeit destroyed: the **per-edge fail-closed
  dispositions** (validity rule 2), the **order-validity findings** the implementer would have raised,
  and any **test change** (was it order-authorized, and does it match the named assertion?). Gate-green
  does not re-derive any of the three. **All three are the orchestrator's to reconstruct**, not just the
  fail-closed edges.
- **The default when you cannot establish it.** If the orchestrator cannot establish completeness and
  correctness itself, **re-dispatch is the default, not recovery** — and a re-dispatch first
  **restores the worktree to the pre-dispatch baseline** (or uses a fresh worktree), never riding the
  abandoned attempt. Park when neither is available. Re-dispatching without looking re-does correct work
  and re-runs the very report that forfeited.

Author orders so the forfeit does not fire: keep in-dispatch verification targeted and returns short
and structured. The implementer template `agents/implementer.md` states this to the implementer
directly, so an order that additionally demands a full-suite run, a pasted diff, or a long verbatim
report is **overriding the template against its own purpose**.

Never assume the implementer can run anything — an external engine's shell availability is set
**outside your build**; the engine CLI consults its own permission surface, not your order. It is
normally available on the sanctioned write path (so a blocked shell is not the expected state). But
two builds in one wave had **every** implementer shell call rejected, and that is not yet explained
— so it cannot be inferred from a previous build. Write every external order to be correct when the
implementer can run nothing; the orchestrator's own re-run is the verification either way, and a
corrective round is worth budgeting.
