# Dispatch mechanics — long dispatches you own

Read this at dispatch time, before you invoke a long dispatch. **In-turn background-and-poll** is the
normal path past the foreground Bash cap; **shell-detach** so work outlives the turn is the rare
fallback. The **detach-and-park contract** (files not pipes, stamp and completion sentinel before
waiting, shell-detach not harness-background, durable park, recovery rules) is **only** in the workhorse
charter §7 (Channel-conditioned) — not restated here. Mechanics by dispatch kind:

- **A shell/CLI run** (an engine CLI invoked through the host's run action) is bounded by the host's
  Bash timeout. On the Claude host that is **ten minutes (600s) — a hard cap on a foreground call, not
  a ceiling you lift by passing a bigger `timeout`**: the plugin's `bash_timeout` hook injects 600s
  **only when a call omits its own `timeout`** (an explicit one is never touched), and the host **caps
  any foreground `timeout` at ten minutes** regardless (a larger value is clamped) — so you **cannot**
  get the 3600s+ room a long dispatch needs on a foreground call (other hosts defer to their own,
  shorter default). Give the dispatch that room by **backgrounding the run and polling it** — a
  backgrounded run is not bound by the foreground cap — never by trying to raise a foreground timeout.
  Redirect its output to a **file, never a pipe or `| tail`** — pipes die with the reader and make a
  stall look like progress. Watch that **output/transcript file growing as your primary stall signal**:
  a growing file is live; use the process's **CPU-time column only as corroboration** (an engine CLI can
  sit at ~0% CPU for minutes and still be live, so CPU alone can't separate idle-but-live from stuck).
  Treat **elapsed time as your *runaway* bound, not a liveness signal** — a quiet run may still be
  live, but one that has far outrun any plausible dispatch time is a runaway to kill even while its file
  grows. Four 0.18.0-wave sessions died at the ten-minute cap mid-dispatch — one mid-review-panel —
  losing the run (WE review session, WE-510, sh-566, WE-484). **If the dispatch cannot finish inside
  the turn:** follow the charter's detach-and-park fallback (§7 Channel-conditioned); the output-file
  stall signals above still apply to the detached child.
- **A native subagent dispatch** has a **harness-managed lifecycle** — no `bash_timeout` floor and no
  CPU column of your own to watch — so those shell mechanics don't apply and there is **no caller-set
  ceiling to invent**; the harness manages the lifecycle and returns when the subagent completes. **No
  shell-detach** — await in-turn when you dispatch; if it genuinely cannot fit the turn, **do not
  dispatch** — park durably on the issue or PR **with the work order ready** (charter §7), or split so
  each dispatch fits one turn.
