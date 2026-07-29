# Dispatch mechanics — long dispatches you own

Read this at dispatch time, before you invoke a long dispatch. On Claude Code harness **2.1.219** the
foreground Bash tool does **not** clamp-and-kill a long `timeout` — at **600 s** it **converts** the
call to harness-tracked background while the session stays in the turn; when the **turn ends**, a
converted run **dies with the session** (work in flight is lost). A child that outlives the turn on
harness **2.1.219** is the **`start_new_session` subprocess shape with stdout/stderr redirected to
files** (the shape `lib/engine_dispatch.py` uses at launch); a bare `setsid <cmd> &` inside a single
harness tool call **did not survive** that tool call's process group on **2.1.219** (no output files,
no sentinel, no surviving process). **#656** owns encoding the surviving shape at launch.
Harness-tracked background is the **more dangerous** option headless because it still dies at turn-end
without a recoverable artifact. The **detach-and-park
contract** (files not pipes, stamp and completion sentinel before waiting, shell-detach not
harness-background, durable park, recovery rules) is **only** in the workhorse charter §7
(Channel-conditioned) — not restated here. Mechanics by dispatch kind:

- **A shell/CLI run** (an engine CLI invoked through the host's run action) on harness **2.1.219**:
  the plugin's `bash_timeout` hook injects 600 s **only when a call omits its own `timeout`** (an
  explicit one is not silently replaced). A foreground call with a larger explicit `timeout` is **not
  clamped and not killed at 600 s** — the harness **converts** it to background at 600 s while you
  remain in the turn (interactive: the child can finish; headless with turn-end: the converted run
  dies and loses tail work). You **cannot** rely on a single foreground Bash call to hold the turn for
  3600s+ on headless paths — conversion plus turn-end is fatal. **Harness-tracked background**
  (`run_in_background: true`) is **worse headless**: when the model ends its turn, that background
  call dies with the session on harness **2.1.219** — no completion marker, no orphan process.
  Prefer the **`start_new_session` subprocess with output to files** (not a bare `setsid … &` inside
  one tool call — that shape did not survive on **2.1.219**); **#656** owns encoding that shape at
  launch. With **no matching permission grant**, a
  dispatch-shaped command is **denied outright** — the run simply does not happen (fail-closed). Redirect
  output to a **file, never a pipe or `| tail`** — pipes die with the reader and make a stall look like
  progress. Watch that **output/transcript file growing as your primary stall signal**: a growing file
  is live; use the process's **CPU-time column only as corroboration** (an engine CLI can sit at ~0%
  CPU for minutes and still be live, so CPU alone can't separate idle-but-live from stuck). Treat
  **elapsed time as your *runaway* bound, not a liveness signal** — a quiet run may still be live, but
  one that has far outrun any plausible dispatch time is a runaway to kill even while its file grows.
  Four 0.18.0-wave sessions died when **converted runs were killed at turn-end** mid-dispatch — not at
  a ten-minute cap kill — one mid-review-panel — losing the run (WE review session, WE-510, sh-566,
  WE-484). **If the dispatch cannot finish inside the turn:** follow the charter's detach-and-park
  fallback (§7 Channel-conditioned); the output-file stall signals above still apply to the detached
  child.
- **A native subagent dispatch** has a **harness-managed lifecycle** — no `bash_timeout` floor and no
  CPU column of your own to watch — so those shell mechanics don't apply and there is **no caller-set
  ceiling to invent**; the harness manages the lifecycle and returns when the subagent completes. **No
  shell-detach** — await in-turn when you dispatch; if it genuinely cannot fit the turn, **do not
  dispatch** — park durably on the issue or PR **with the work order ready** (charter §7), or split so
  each dispatch fits one turn.

## Supervised engine dispatch runner (`lib/engine_dispatch.py`)

For external-engine review/write seats, the **supervised runner** is the sanctioned path — not a
hand-rolled foreground Bash engine line. Its supervision primitive (harness **2.1.219**) uses a **run
directory** per dispatch:

- Durable per-attempt **`stdout`** / **`stderr`** files (never pipes).
- A **`state.json`** receipt the runner maintains.
- A **done sentinel** the **detached child** writes with its exit code when the engine finishes.
- **Heartbeats** while the attempt is live.
- **One bounded retry** on terminal forfeit (timeout, unreadable, vacuous — per runner policy).
- A **bounded synchronous wait** (`--max-wait`, default **540 s**, hard-capped **below the 600 s
  conversion boundary** on harness **2.1.219**) so each runner invocation **always returns** before
  conversion — while the result is non-terminal, **re-invoke the originating verb** (`dispatch-review`
  / `dispatch-write`) with the **same `--run-dir`**; `dispatch-poll` **never spawns — no exceptions.**
  A run that outlives the session is **recoverable** from the run directory rather than lost.

**Fail-closed incomplete rule:** output present in the run directory **with no completion sentinel**
is an **incomplete run**, not a result — do not parse it as findings or a write outcome.

A non-terminal `{"reason": "running", "terminal": false, "forfeited": false}` — **must
not** be read as a forfeit. Use `dispatch-abandon` for cleanup when abandoning a run directory. Every
result carries **`terminal`**, **`argv`** (exact spawned command), and **`runDir`** keys for audit.
