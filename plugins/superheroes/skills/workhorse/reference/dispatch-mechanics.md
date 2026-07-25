# Dispatch mechanics — long dispatches you own

Read this at dispatch time, before you invoke a long dispatch. The one-line core rule (a long
dispatch you own gets room to finish + a stuck/runaway monitor; never a borderline limit; never end
the turn while it runs) lives in the workhorse charter §7. The concrete mechanics differ by dispatch
kind:

- **A shell/CLI run** (an engine CLI invoked through the host's run action) is bounded by the host's
  Bash timeout. On the Claude host that is **ten minutes (600s) — a hard cap on a foreground call, not
  a ceiling you lift by passing a bigger `timeout`**: the plugin's `bash_timeout` hook injects 600s
  **only when a call omits its own `timeout`** (an explicit one is never touched), and the host **caps
  any foreground `timeout` at ten minutes** regardless (a larger value is clamped) — so you **cannot**
  get the 3600s+ room a long dispatch needs on a foreground call (other hosts defer to their own,
  shorter default). Give the dispatch that room by **backgrounding the run and polling it** — a
  backgrounded run is not bound by the foreground cap — never by trying to raise a foreground timeout.
  Redirect its output to a **file, never `| tail`**, and watch that **output/transcript file growing as
  your primary stall signal**: a growing file is live; use the process's **CPU-time column only as
  corroboration** (an engine CLI can sit at ~0% CPU for minutes and still be live, so CPU alone can't
  separate idle-but-live from stuck). Treat **elapsed time as your *runaway* bound, not a liveness
  signal** — a quiet run may still be live, but one that has far outrun any plausible dispatch time is a
  runaway to kill even while its file grows. Four 0.18.0-wave sessions died at the ten-minute cap
  mid-dispatch — one mid-review-panel — losing the run (WE review session, WE-510, sh-566, WE-484).
- **A native subagent dispatch** has a **harness-managed lifecycle** — no `bash_timeout` floor and no
  CPU column of your own to watch — so those shell mechanics don't apply and there is **no caller-set
  ceiling to invent** — the harness manages the lifecycle and returns when the subagent completes; the
  core reduces to awaiting that completion in-turn and not imposing a borderline limit.
