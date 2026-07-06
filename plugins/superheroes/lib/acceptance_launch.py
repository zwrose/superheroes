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
  {"outcome": "exited"|"killed"|"kill-unconfirmed",
   "ceiling": None|"elapsed"|"spend",
   "terminal_location": str|None,
   "teardown_safe": bool,          # present on kill paths
   "spend_partial": bool,
   "spend": float|None,          # final sampled spend; None if unreadable throughout
   "elapsed_sec": float}         # final computed elapsed

The launcher ALWAYS surfaces the final `spend` + `elapsed_sec` so the orchestrator has a
real source for the FR-5-required record fields (Task 7's `write_record` rejects a record
missing either). `spend` is `None` when spend was unreadable for the whole run.

Teardown-readiness gate (UFR-2): on a kill it only reports `killed` once `group_empty()`
confirms no surviving group member. If the bounded escalation ends without confirmation,
it reports `kill-unconfirmed` and `teardown_safe: false` so cleanup does not start while a
child may still be mutating artifacts.
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
_KILL_CONFIRM_INTERVAL_SEC = 0.05

# Poll cadence for the real-default watch loop (seconds). Injected clocks in tests never
# reach this sleep because their fakes exit/breach deterministically per tick.
_POLL_INTERVAL_SEC = 2.0

# Env markers set on the spawned child (see module docstring).
_CONTEXT_MARKER = "SUPERHEROES_ACCEPTANCE_CONTEXT"
_DENY_ONLY_MARKER = "SUPERHEROES_ACCEPTANCE_DENY_ONLY"

# The model the child driver session is pinned to by default. The child does only wrapper
# work (skill-following, the Workflow launch, the run_outcome projection write) — all the
# in-run intelligence is pinned by the plugin's own tier config — so a fixed, cheap-but-capable
# tier is correct here. Pinning it also closes a model-governance leak: an unpinned `claude -p`
# child inherits the invoking user's CLI default (potentially Fable), which the repo's
# no-session-model-inheritance governance forbids. Overridable per-run via `--child-model`.
DEFAULT_CHILD_MODEL = "sonnet"

# Filenames inside a spine-lib override tree. Named here (with the spawn/prompt logic that
# owns the tree layout) and referenced from BOTH the launch-side prompt builder and the
# deps-side override guard/provenance (`acceptance_deps._spine_bundle` /
# `_spine_showrunner_js`), so the two sides can never disagree about which files an override
# tree must carry — the deps guard validates the exact file the prompt tells the child to launch.
SHOWRUNNER_BUNDLE_NAME = "showrunner.bundle.js"
SHOWRUNNER_JS_NAME = "showrunner.js"

# The child handle run()'s watch loop is currently supervising, or None between runs.
# Published so the harness's SIGTERM/SIGINT handler (acceptance_run) can reach the LIVE
# group and hard-kill it before the process exits — an ungraceful harness death otherwise
# re-parents the child group with no supervisor, and (until the finite bg-wait ceiling in
# PR #244) it keeps running/spending unsupervised (issue #245). The harness is one-shot
# (nesting is refused, UFR-5), so a single module-level slot is sufficient; run() sets it
# at spawn and clears it on every exit path (including an exception unwinding the loop).
_live_child = None


def current_live_child():
    """The child handle run()'s watch loop is currently supervising, or None.

    The harness signal handler reads this at signal-delivery time — while run()'s loop is
    still on the stack and the slot is populated — so it can reap the live group through the
    shared escalation before unwinding into teardown. Returns None when no run is in flight."""
    return _live_child


def _set_live_child(child):
    """Publish (or clear, with None) the live-child slot. `run()` owns the lifecycle (set at
    spawn, cleared in its finally), but the real launcher's spawn wrapper also calls this ONE
    beat earlier — right after Popen, before the pgid-persist file I/O — so a signal during that
    (slower, syscall-heavy) window still reaches the live group instead of capturing None and
    reaping a just-spawned orphan's future artifacts (issue #245 review). The residual Popen→
    handle-construct gap is irreducible and stays bounded by the 2×-elapsed bg-wait ceiling."""
    global _live_child
    _live_child = child


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
    # Publish the live child so the harness signal handler can reach the group if a SIGTERM/
    # SIGINT arrives mid-watch (issue #245). The real spawn wrapper already published it one
    # beat earlier (before its pgid-persist I/O); this is the canonical set for every path
    # (including injected-fake children in tests). Cleared in the finally on every exit —
    # including an exception (e.g. the signal handler's) unwinding the loop; the handler has
    # already captured the child by then, so clearing here cannot lose it.
    _set_live_child(child)
    start = clock.now()

    last_spend = None
    last_elapsed = 0.0

    try:
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
                confirmed = _hard_kill_group(child)
                return {
                    "outcome": "killed" if confirmed else "kill-unconfirmed",
                    "ceiling": decision.get("ceiling"),
                    "terminal_location": None,
                    "teardown_safe": confirmed,
                    "spend_partial": spend_partial,
                    "spend": last_spend,
                    "elapsed_sec": last_elapsed,
                }

            # Continue watching. The real-default watch paces itself; injected clocks in tests
            # drive the loop deterministically and never reach this sleep.
            if clock is _REAL_CLOCK:
                time.sleep(_POLL_INTERVAL_SEC)
    finally:
        _set_live_child(None)


def _compute_spend_partial(engine_pref_reader):
    """True when any resolved ROLE's engine preference is a non-claude external engine.

    `engine_pref.load_engine_prefs`'s real return shape carries a non-role "effort"
    sub-map (`{"reviewer": ..., "implementation": ..., "effort": {...}}`) alongside the
    role keys. That sub-map must be excluded from this test: iterating all values naively
    would fold `effort`'s dict value into the any() check (`str({}) != "claude"` -> True),
    falsely marking an all-claude run as spend_partial on every real invocation.
    """
    try:
        prefs = engine_pref_reader() or {}
    except Exception:
        return False
    return any(str(v).lower() != "claude"
               for k, v in prefs.items() if k != "effort")


def _hard_kill_group(child):
    """Signal the whole group SIGTERM → SIGKILL until it is confirmed empty (UFR-2).

    Bounded escalation: after the initial SIGTERM, re-signal SIGKILL and re-poll until
    `group_empty()` reports no survivor, up to `_MAX_KILL_ESCALATIONS` rounds so a stuck
    group cannot hang the watch forever.
    """
    child.killpg(signal.SIGTERM)
    for _ in range(_MAX_KILL_ESCALATIONS):
        if child.group_empty():
            return True
        child.killpg(signal.SIGKILL)
        child.poll()
        if child.group_empty():
            return True
        time.sleep(_KILL_CONFIRM_INTERVAL_SEC)
    return False


class _PgidGroup:
    """A minimal group handle over a bare pgid (no live Popen) so the SIGTERM→SIGKILL
    escalation in `_hard_kill_group` can be REUSED to reap a RECORDED orphan group during
    lease reclaim (issue #245) — not only a child this process itself spawned.

    `poll()` is a no-op (there is no Popen of ours to reap); confirmation relies entirely on
    `group_empty()` probing the pgid with signal 0. An unsignalable-but-present group
    (PermissionError — e.g. the orphan is owned by another user) stays "not empty" so the
    escalation fails closed to unconfirmed rather than declaring a false victory.

    Caveat (documented, matches the issue's pgid+bootId design): within a single boot a
    reaped leader's pgid can in principle be recycled to an unrelated group. bootId gates
    this to the same boot only; the residual same-boot reuse window is bounded by the child's
    2×-elapsed bg-wait ceiling (PR #244) and is the accepted tradeoff versus the alternative
    — deleting the artifacts a genuinely-live orphan is still building on."""

    def __init__(self, pgid):
        self._pgid = int(pgid)

    def poll(self):
        return None

    def killpg(self, sig):
        try:
            os.killpg(self._pgid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def group_empty(self):
        try:
            os.killpg(self._pgid, 0)
        except ProcessLookupError:
            return True
        except (PermissionError, OSError):
            # Present-but-unsignalable, or an unexpected killpg error (e.g. EINVAL on a
            # malformed pgid): fail closed — "not empty" keeps the escalation honest and
            # never declares a false victory. (Callers gate pgid <= 1 upstream; this is
            # defense in depth so a stray value can never crash the reclaim probe.)
            return False
        else:
            return False

    def terminal_location(self):
        return None


def reap_group_by_pgid(pgid):
    """Reap a bare process group by pgid via the SAME bounded SIGTERM→SIGKILL escalation the
    live ceiling-kill path uses (`_hard_kill_group`). Returns True iff the group is confirmed
    empty, False if it could not be confirmed dead. Used by the lease-reclaim orphan check
    (acceptance_deps) so a reclaim after an ungraceful harness death signals a surviving
    orphan group instead of proceeding into discovery teardown under a live orphan."""
    return _hard_kill_group(_PgidGroup(pgid))


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

    def pgid(self):
        """The captured process-group id (the leader pid at spawn). Persisted into the
        lease at spawn time so a reclaim after an ungraceful harness death can probe/kill
        the orphaned group rather than deleting the artifacts it is still building on
        (issue #245)."""
        return self._pgid

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


def build_launch_prompt(work_item, terminal_path, spine_lib=None, root=None, fixture_dir=None):
    """The non-interactive prompt handed to `claude -p` for a live acceptance run.

    Directs the headless session to drive `superheroes:showrunner` to completion on the
    stamped work-item, then persist the showrunner's machine-readable run-outcome
    projection (`run_readout.run_outcome`) to `terminal_path` as JSON — the one write
    that makes a run-level terminal record exist at the path `real_run_outcome` reads.
    Pure string-building so the exact wording is unit-tested without a live spawn.

    Default (`spine_lib is None`) is byte-identical to the installed-plugin form: the child
    resolves the spine from its own plugin cache — i.e. the last *released* version. When
    `spine_lib` is set (the #235 pre-release gate), the prompt pins the ENTIRE spine to the
    override tree under test: the child must treat `<spine_lib>` as the showrunner skill's
    `$LIB` for EVERY step — pre-flight (`<spine_lib>/preflight.py`), the committed bundle
    (`<spine_lib>/showrunner.bundle.js`), the Workflow `libRoot: <spine_lib>`, and the
    run-outcome projection (`<spine_lib>/run_readout.py`) — and must NOT let `$LIB` resolve
    from the installed plugin cache. That consistency is the whole point: if pre-flight ran
    from the cached (released) tree while the bundle came from main, the run would be a
    silent cross-version mix and the pre-release baseline it exists to produce would be
    invalid.
    """
    # Pointer clause ONLY when the caller knows the actually-materialized dir: a
    # derived-but-wrong pointer is a false claim the driver rejects as injection
    # (live finding #3; the old dirname(terminal_path) fallback points at the
    # harness control-plane dir, which no longer holds the triple).
    where = (" at %s — read those files if in doubt" % fixture_dir) if fixture_dir else ""
    preamble = (
        "CONTEXT — who is asking and why this is sanctioned: you are the acceptance "
        "harness's own non-interactive driver session, spawned and supervised by the "
        "harness process (acceptance_run.py, the superheroes acceptance flow). The "
        "work-item below is NOT a normal discovery work-item: its accept-harness- prefix "
        "is the harness's own reserved namespace (RESERVED_PREFIX in "
        "acceptance_fixture.py), and the harness materialized it moments ago as a "
        "throwaway fixture with a pre-approved spec/plan/tasks triple"
        + where + ". Driving the showrunner spine on "
        "this fixture is the sanctioned harness lifecycle: the parent process enforces "
        "ceilings, reads and judges the terminal record you write, and tears down every "
        "artifact (worktree, branch, PR) on every exit path. The run-outcome projection "
        "you persist must be computed from the run's ACTUAL end state via "
        "run_readout.run_outcome — never hand-authored or approximated. Writing an "
        "honest projection of a real run to the path the harness gave you is the "
        "harness working as designed, not evidence fabrication. Pointing the run at "
        "the real repo root is also by design: every showrunner run starts from the "
        "live root and isolates its work in a managed per-work-item worktree, branch, "
        "and draft PR — the fixture's changes never touch the working tree or main. "
    )
    if spine_lib:
        bundle = os.path.join(spine_lib, SHOWRUNNER_BUNDLE_NAME)
        preflight = os.path.join(spine_lib, "preflight.py")
        return preamble + (
            "Run the superheroes:showrunner skill end-to-end on the approved work-item "
            "%(work_item)s, but resolve the ENTIRE spine from the override lib UNDER TEST at "
            "%(spine_lib)s — treat %(spine_lib)s as the skill's $LIB for EVERY step and do NOT "
            "let $LIB resolve from the installed plugin cache. Concretely: run the pre-flight "
            "gate via %(preflight)s (never the cached preflight.py), read the committed bundle "
            "at %(bundle)s, and invoke the Workflow tool on that bundle with "
            "args: {workItem: %(work_item)s, root: %(root)s, libRoot: %(spine_lib)s}. "
            "After the run reaches a terminal state (ready or parked), compute its "
            "run-outcome projection via %(spine_lib)s/run_readout.py's "
            "run_outcome(state) function over the run's end state, and write that projection "
            "as JSON to this exact path, creating parent directories as needed: %(terminal_path)s. "
            "Do not merge, release, or force-push anything — this run's changes are confined "
            "to the work-item's own branch and PR."
            % {"work_item": work_item, "terminal_path": terminal_path,
               "bundle": bundle, "preflight": preflight, "spine_lib": spine_lib, "root": root}
        )
    return preamble + (
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


def _default_child_factory(stamped, terminal_path=None, spine_lib=None, root=None,
                           child_model=None, bg_wait_ceiling_ms=None):
    """Spawn `claude -p <prompt> --model <child_model>` as an isolated process-group leader
    (UFR-5/UFR-6).

    `-p`/`--print` is the CLI's actual non-interactive form (there is no `--headless`
    flag); the prompt (`build_launch_prompt`) directs the session to drive
    `superheroes:showrunner` on the stamped work-item and persist its run-outcome
    projection to `terminal_path`. `spine_lib` (when set) pins the spine under test into
    the prompt (#235); `root` is threaded so the override's `args.root` names the real
    repo root. `child_model` (default `DEFAULT_CHILD_MODEL`) pins the driver session's model
    so it never inherits the invoking user's CLI default (model-governance). Sets the
    execution-context + deny-only markers on the child env. Returns a `_RealChild` handle
    for the watch loop.
    """
    env = dict(os.environ)
    env[_CONTEXT_MARKER] = "1"
    env[_DENY_ONLY_MARKER] = "1"
    # The child waits on the showrunner Workflow as a BACKGROUND task; non-interactive
    # `claude -p` kills still-running background tasks at a ~600s ceiling, which
    # terminated a live run mid-spine (0.10.0 qualification finding #6; the CLI's own
    # kill message documents the env: "Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 to
    # wait indefinitely"). Callers pass a FINITE ceiling derived from the harness
    # elapsed ceiling (2x): the watch loop kills at 1x while the harness lives, and
    # the finite value keeps an orphan's lifetime bounded if the harness dies
    # ungracefully. 0 (wait forever) is the fallback only for direct callers.
    env["CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"] = str(int(bg_wait_ceiling_ms)) if bg_wait_ceiling_ms else "0"
    work_item = stamped.get("work_item") if isinstance(stamped, dict) else stamped
    fixture_dir = None
    if isinstance(stamped, dict):
        paths = stamped.get("paths")
        vals = list(paths.values()) if isinstance(paths, dict) else list(paths or [])
        if vals:
            fixture_dir = os.path.dirname(vals[0])
    prompt = build_launch_prompt(work_item, terminal_path, spine_lib=spine_lib, root=root,
                                 fixture_dir=fixture_dir)
    model = child_model or DEFAULT_CHILD_MODEL
    proc = subprocess.Popen(
        ["claude", "-p", prompt, "--model", model],
        start_new_session=True,
        env=env,
    )
    return _RealChild(proc, terminal_path)


def _default_engine_pref_reader(cwd=None, root=None):
    """Read the project's resolved engine preferences via the band's engine-pref lib."""
    try:
        import engine_pref
        return engine_pref.load_engine_prefs(cwd or os.getcwd(), root=root)
    except Exception:
        return {}
