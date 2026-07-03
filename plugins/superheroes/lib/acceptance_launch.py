"""Child-process launcher + ceiling watch for the acceptance harness
(FR-1 / FR-8 / UFR-2 / UFR-5 / UFR-6).

`run(...)` spawns the live showrunner as an isolated process-group leader and watches it
tick-by-tick against the invocation's *remaining* budget. All judgment about whether a
breach has occurred lives in the pure `acceptance_ceiling.decide` — this module is the
thin mechanical layer that samples the clock + spend, feeds the decider, and (on a `kill`
decision) hard-signals the whole group SIGTERM → SIGKILL until it is confirmed empty
(UFR-2). Every I/O boundary — the child, the clock, the spend sampler, the engine-pref
read — is injected so the tests drive only fakes and never spawn a live run.

Real defaults (used in production, not in tests) spawn a non-interactive `claude` CLI
session as a process-group leader (`start_new_session=True`) with two env markers set
on the child:

  - `SUPERHEROES_ACCEPTANCE_CONTEXT=1`   — the execution-context marker the front-door
    skill reads to refuse nesting (UFR-5).
  - `SUPERHEROES_ACCEPTANCE_DENY_ONLY=1` — the enforcement marker the workhorse enforcer
    reads to run deny-only across the full owner-authority set (Task 8 / UFR-6).

The spawned child is driven with a non-interactive prompt (`claude -p "<prompt>"` — `-p`/
`--print` is the CLI's actual non-interactive form; there is no `--headless` flag) built by
`build_launch_prompt`. The prompt directs the session to run `superheroes:showrunner` on the
stamped work-item and then persist the showrunner's machine-readable `run_outcome` projection
(`run_readout.run_outcome`) to the `terminal_location` path as JSON — that write is the ONLY
thing that makes a run-level terminal record exist at the path `real_run_outcome` reads; the
showrunner itself does not persist one, so without this explicit instruction the harness would
have no terminal record to judge no matter how the child was invoked.

Return contract (every path):
  {"outcome": "exited"|"killed",
   "ceiling": None|"elapsed"|"spend",
   "terminal_location": str|None,
   "spend_partial": bool,
   "spend": float|None,          # final sampled spend; None if unreadable throughout
   "elapsed_sec": float}         # final computed elapsed

The launcher ALWAYS surfaces the final `spend` + `elapsed_sec` so the orchestrator has a
real source for the FR-5-required record fields (Task 7's `write_record` rejects a record
missing either). `spend` is `None` when spend was unreadable for the whole run.

Teardown-readiness gate (UFR-2): on a kill it only stops signaling once `group_empty()`
reports no surviving group member; the escalation is bounded so a stuck group cannot hang
the watch forever.
"""

import os
import signal
import subprocess
import time

import acceptance_ceiling

# Bounded SIGKILL escalation: after SIGTERM we re-signal the group with SIGKILL at most
# this many times, polling between, until `group_empty()` confirms it is gone. Bounded so
# an un-reapable group can never hang the watch indefinitely.
_MAX_KILL_ESCALATIONS = 50

# Poll cadence for the real-default watch loop (seconds). Injected clocks in tests never
# reach this sleep because their fakes exit/breach deterministically per tick.
_POLL_INTERVAL_SEC = 2.0

# Env markers set on the spawned child (see module docstring).
_CONTEXT_MARKER = "SUPERHEROES_ACCEPTANCE_CONTEXT"
_DENY_ONLY_MARKER = "SUPERHEROES_ACCEPTANCE_DENY_ONLY"


def run(stamped, ceilings, child_factory, clock, spend_sampler, engine_pref_reader,
        budget_consumed=None, attempt=1):
    """Launch the stamped work-item and watch it against the remaining budget.

    See the module docstring for the full return contract. `budget_consumed` defaults to
    an all-zero budget (attempt 1); on a retry the caller threads in the prior attempt's
    `{elapsed_sec, spend}` so the ceiling watch enforces `ceiling - consumed` — the
    invocation's *remaining* budget (FR-8), never a fresh full ceiling.
    """
    if budget_consumed is None:
        budget_consumed = {"elapsed_sec": 0.0, "spend": 0.0}

    # spend_partial: any role's engine preference resolving to a non-claude (external)
    # engine means engine-dispatched leaf spend is outside the sampled stream, so the
    # sampled total is a partial view (UFR-6-adjacent cost caveat).
    spend_partial = _compute_spend_partial(engine_pref_reader)

    child = child_factory()
    start = clock.now()

    last_spend = None
    last_elapsed = 0.0

    while True:
        status = child.poll()
        if status is not None:
            # Natural exit — the child finished on its own; report its terminal location.
            return {
                "outcome": "exited",
                "ceiling": None,
                "terminal_location": child.terminal_location(),
                "spend_partial": spend_partial,
                "spend": last_spend,
                "elapsed_sec": last_elapsed,
            }

        elapsed = clock.now() - start
        spend, readable = spend_sampler()
        last_elapsed = elapsed
        if readable:
            last_spend = spend

        decision = acceptance_ceiling.decide({
            "ceilings": ceilings,
            "elapsed_sec": elapsed,
            "spend_sampled": spend,
            "spend_readable": readable,
            "budget_consumed": budget_consumed,
            "attempt": attempt,
        })

        if decision.get("action") == "kill":
            _hard_kill_group(child)
            return {
                "outcome": "killed",
                "ceiling": decision.get("ceiling"),
                "terminal_location": None,
                "spend_partial": spend_partial,
                "spend": last_spend,
                "elapsed_sec": last_elapsed,
            }

        # Continue watching. The real-default watch paces itself; injected clocks in tests
        # drive the loop deterministically and never reach this sleep.
        if clock is _REAL_CLOCK:
            time.sleep(_POLL_INTERVAL_SEC)


def _compute_spend_partial(engine_pref_reader):
    """True when any resolved engine preference is a non-claude external engine."""
    try:
        prefs = engine_pref_reader() or {}
    except Exception:
        return False
    return any(str(v).lower() != "claude" for v in prefs.values())


def _hard_kill_group(child):
    """Signal the whole group SIGTERM → SIGKILL until it is confirmed empty (UFR-2).

    Bounded escalation: after the initial SIGTERM, re-signal SIGKILL and re-poll until
    `group_empty()` reports no survivor, up to `_MAX_KILL_ESCALATIONS` rounds so a stuck
    group cannot hang the watch forever.
    """
    child.killpg(signal.SIGTERM)
    for _ in range(_MAX_KILL_ESCALATIONS):
        if child.group_empty():
            return
        child.killpg(signal.SIGKILL)
        child.poll()
        if child.group_empty():
            return


# --- Real defaults (production spawn path; the tests drive only injected fakes) -------

class _RealClock:
    def now(self):
        return time.monotonic()


_REAL_CLOCK = _RealClock()


class _RealChild:
    """A live `claude` CLI child spawned as a process-group leader.

    Thin and mechanical: exposes exactly the handle the watch loop needs
    (`poll`/`killpg`/`group_empty`/`terminal_location`). All budget judgment stays in the
    ceiling decider.
    """

    def __init__(self, proc, terminal_path):
        self._proc = proc
        self._terminal_path = terminal_path
        # Capture the pgid ONCE, up front, while the leader is still alive. Because the
        # child is spawned with start_new_session=True, the leader's pid IS the pgid at
        # spawn time. This must not be re-derived later via `os.getpgid(self._proc.pid)`:
        # once the leader has been reaped, getpgid(leader_pid) raises ProcessLookupError
        # even while OTHER members of the same numeric group are still alive — re-deriving
        # it per-call would falsely report the group empty the instant the leader exits.
        self._pgid = proc.pid

    def poll(self):
        return self._proc.poll()

    def killpg(self, sig):
        try:
            os.killpg(self._pgid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            # Group already gone (or un-signalable) — treated as empty by group_empty().
            pass

    def group_empty(self):
        # Probe the WHOLE process group via the captured pgid, not just the leader
        # (UFR-2): the leader can reap quickly on SIGTERM while subprocesses it spawned
        # into the same group (subagent `claude` processes, in-flight `git`/`gh`) are
        # still running. Signal 0 raises no signal, only checks whether any member
        # survives. ProcessLookupError means the pgid has no surviving member -> confirmed
        # empty. PermissionError means a member exists but is unsignalable by us -> treat
        # that as NOT empty so escalation keeps trying rather than declaring victory early.
        try:
            os.killpg(self._pgid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        else:
            return False

    def terminal_location(self):
        return self._terminal_path


def build_launch_prompt(work_item, terminal_path):
    """The non-interactive prompt handed to `claude -p` for a live acceptance run.

    Directs the headless session to drive `superheroes:showrunner` to completion on the
    stamped work-item, then persist the showrunner's machine-readable run-outcome
    projection (`run_readout.run_outcome`) to `terminal_path` as JSON — the one write
    that makes a run-level terminal record exist at the path `real_run_outcome` reads.
    Pure string-building so the exact wording is unit-tested without a live spawn.
    """
    return (
        "Run the superheroes:showrunner skill end-to-end on the approved work-item "
        "%(work_item)s (invoke it exactly as documented in its SKILL.md — pre-flight, "
        "then the Workflow tool on the committed bundle with args: {workItem: %(work_item)s}). "
        "After the run reaches a terminal state (ready or parked), compute its "
        "run-outcome projection via plugins/superheroes/lib/run_readout.py's "
        "run_outcome(state) function over the run's end state, and write that projection "
        "as JSON to this exact path, creating parent directories as needed: %(terminal_path)s. "
        "Do not merge, release, or force-push anything — this run's changes are confined "
        "to the work-item's own branch and PR."
        % {"work_item": work_item, "terminal_path": terminal_path}
    )


def _default_child_factory(stamped, terminal_path=None):
    """Spawn `claude -p <prompt>` as an isolated process-group leader (UFR-5/UFR-6).

    `-p`/`--print` is the CLI's actual non-interactive form (there is no `--headless`
    flag); the prompt (`build_launch_prompt`) directs the session to drive
    `superheroes:showrunner` on the stamped work-item and persist its run-outcome
    projection to `terminal_path`. Sets the execution-context + deny-only markers on the
    child env. Returns a `_RealChild` handle for the watch loop.
    """
    env = dict(os.environ)
    env[_CONTEXT_MARKER] = "1"
    env[_DENY_ONLY_MARKER] = "1"
    work_item = stamped.get("work_item") if isinstance(stamped, dict) else stamped
    prompt = build_launch_prompt(work_item, terminal_path)
    proc = subprocess.Popen(
        ["claude", "-p", prompt],
        start_new_session=True,
        env=env,
    )
    return _RealChild(proc, terminal_path)


def _default_spend_sampler():
    """Real spend sampler placeholder: spend unreadable until wired to the cost source.

    Returns `(None, False)` so the watch governs on elapsed alone (fail-closed on the
    readable ceiling) until a live spend source is injected.
    """
    return (None, False)


def _default_engine_pref_reader(cwd=None, root=None):
    """Read the project's resolved engine preferences via the band's engine-pref lib."""
    try:
        import engine_pref
        return engine_pref.load_engine_prefs(cwd or os.getcwd(), root=root)
    except Exception:
        return {}
