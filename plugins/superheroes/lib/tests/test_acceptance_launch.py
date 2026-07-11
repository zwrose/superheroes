# plugins/superheroes/lib/tests/test_acceptance_launch.py
import os, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_launch as al

CEIL = {"elapsed_sec": 100.0, "spend": 10.0}

# code-001 regression guard: the production launcher must spawn a real, working
# non-interactive `claude` invocation (`-p`/`--print`), never the invalid `--headless`
# flag, and it must actually drive `superheroes:showrunner` on the stamped work-item
# rather than opening a bare/instructionless session.


class FakeClock:
    def __init__(self, ticks): self.ticks = list(ticks); self.i = -1
    def now(self):
        self.i += 1
        return self.ticks[min(self.i, len(self.ticks) - 1)]


class FakeChild:
    def __init__(self, exits_after, group_empty_after=None):
        self.calls = 0; self.exits_after = exits_after
        self.signals = []; self._group_empty_after = group_empty_after
        self._killed_at = None
    def poll(self):
        self.calls += 1
        if self._killed_at is not None:
            return 0
        return None if self.calls < self.exits_after else 0
    def killpg(self, sig):
        self.signals.append(sig)
        if self._killed_at is None:
            self._killed_at = self.calls
    def group_empty(self):
        if self._group_empty_after is None:
            return self._killed_at is not None
        return self._killed_at is not None and self.calls - self._killed_at >= self._group_empty_after
    def terminal_location(self):
        return "/run/terminal-record.json"


def test_natural_exit_returns_terminal_location_and_spend_elapsed():
    child = FakeChild(exits_after=2)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 1, 2]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "exited"
    assert res["terminal_location"] == "/run/terminal-record.json"
    assert res["spend_partial"] is False
    # the launcher MUST surface the final sampled spend + elapsed so the orchestrator can
    # populate the FR-5-required record fields (Task 7 write_record rejects them missing).
    assert "spend" in res and "elapsed_sec" in res
    assert res["spend"] == 0.1
    assert res["elapsed_sec"] >= 0.0


def test_unreadable_spend_surfaces_none_spend_not_crash():
    child = FakeChild(exits_after=2)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 1, 2]), spend_sampler=lambda: (None, False),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "exited"
    assert res["spend"] is None            # unreadable throughout -> None, still present
    assert "elapsed_sec" in res


def test_retry_budget_threaded_trips_on_reduced_ceiling():
    # FR-8 invocation-scoped budget: attempt 2 inherits budget_consumed, so the ceiling watch
    # enforces (ceiling - consumed). With 90s already spent against a 100s ceiling, a 20s
    # elapsed on attempt 2 (90+20 > 100) MUST trip elapsed — not get a fresh full 100s.
    child = FakeChild(exits_after=999)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 5, 20, 20]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"all": "claude"},
                 budget_consumed={"elapsed_sec": 90.0, "spend": 0.0}, attempt=2)
    assert res["outcome"] == "killed" and res["ceiling"] == "elapsed"


def test_elapsed_breach_kills_whole_group_and_names_ceiling():
    child = FakeChild(exits_after=999)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 50, 101, 101]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "killed" and res["ceiling"] == "elapsed"
    assert child.signals  # the group was signaled (SIGTERM at least)


def test_spend_breach_kills_and_names_spend():
    child = FakeChild(exits_after=999)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 1, 2, 3]), spend_sampler=lambda: (10.5, True),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "killed" and res["ceiling"] == "spend"


def test_external_engine_pref_marks_spend_partial():
    child = FakeChild(exits_after=2)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 1, 2]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"review": "codex"})
    assert res["spend_partial"] is True


def test_real_shaped_all_claude_prefs_with_effort_submap_not_partial():
    # Regression: engine_pref.load_engine_prefs's real return shape is
    # {"reviewer": ..., "implementation": ..., "effort": {...}} — the "effort" sub-map
    # is NOT a role and must be excluded from the any-non-claude test. A prior bug
    # folded "effort"'s dict value into the check (str({}) != "claude" -> True),
    # falsely marking an all-claude run as spend_partial.
    child = FakeChild(exits_after=2)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 1, 2]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {
                     "reviewer": "claude", "implementation": "claude", "effort": {}
                 })
    assert res["spend_partial"] is False


def test_real_shaped_external_prefs_with_effort_submap_is_partial():
    child = FakeChild(exits_after=2)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 1, 2]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {
                     "reviewer": "codex", "implementation": "claude",
                     "effort": {"review": "xhigh"}
                 })
    assert res["spend_partial"] is True


def test_kill_confirmed_dead_only_when_group_empty():
    # SIGTERM then SIGKILL escalation until the group is empty.
    child = FakeChild(exits_after=999, group_empty_after=1)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 101, 101, 101, 101]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "killed"
    assert len(child.signals) >= 2  # SIGTERM then SIGKILL escalation


def test_kill_not_confirmed_surfaces_explicit_unsafe_outcome(monkeypatch):
    sleeps = []
    monkeypatch.setattr(al.time, "sleep", lambda sec: sleeps.append(sec))
    child = FakeChild(exits_after=999, group_empty_after=10_000)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 101, 101, 101, 101]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "kill-unconfirmed"
    assert res["teardown_safe"] is False
    assert sleeps


def test_real_child_group_empty_probes_whole_group_not_just_leader():
    # UFR-2 regression guard: `_RealChild.group_empty()` must probe the WHOLE process
    # group, not just the leader. A leader that exits quickly while a subprocess it
    # spawned into the same group survives must report group_empty()==False until that
    # survivor is actually gone — otherwise the SIGKILL escalation is skipped and the
    # survivor keeps running (and spending) after the harness reports a clean kill.
    #
    # The leader here backgrounds a `sleep` child (same pgid, since it never calls
    # setsid) and exits immediately, mirroring "leader reaps fast, children linger".
    proc = subprocess.Popen(
        ["bash", "-c", "sleep 2 & disown; exit 0"], start_new_session=True)
    child = al._RealChild(proc, "/tmp/does-not-matter.json")
    try:
        deadline = time.monotonic() + 5
        while child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert child.poll() is not None  # the leader has exited
        # The grandchild sleep is still running -> group must NOT be reported empty yet.
        assert child.group_empty() is False
        # Once the grandchild actually finishes, the group is confirmed empty.
        deadline = time.monotonic() + 5
        while not child.group_empty() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert child.group_empty() is True
    finally:
        try:
            os.killpg(proc.pid, 9)
        except OSError:
            pass


def test_build_launch_prompt_names_the_skill_work_item_and_terminal_path():
    prompt = al.build_launch_prompt("accept-harness-abc123", "/run/dir/terminal-record.json")
    assert "superheroes:showrunner" in prompt
    assert "accept-harness-abc123" in prompt
    assert "/run/dir/terminal-record.json" in prompt
    # must direct the child to persist the run_outcome projection to that exact path —
    # otherwise no run-level terminal record is ever written for real_run_outcome to read.
    assert "run_outcome" in prompt


def test_build_launch_prompt_forbids_merging():
    prompt = al.build_launch_prompt("accept-harness-xyz", "/t.json").lower()
    assert "do not merge" in prompt


# The harness self-identification preamble (0.10.0 qualification finding: an unidentified
# driver prompt reads as evidence-forging to the child and gets refused). Byte-pinned like
# the body: every claim in it must stay VERIFIABLE (the fixture-dir pointer is threaded
# from the actually-materialized paths by _default_child_factory).
def _preamble(fixture_dir):
    return (
        "CONTEXT — who is asking and why this is sanctioned: you are the acceptance "
        "harness's own non-interactive driver session, spawned and supervised by the "
        "harness process (acceptance_run.py, the superheroes acceptance flow). Your "
        "spawn is mechanically verifiable — the launcher set "
        "SUPERHEROES_ACCEPTANCE_CONTEXT in your environment; check it now, only the "
        "harness sets it on the child it spawns. Your protocol lives on this checkout's "
        "own reviewed surface: invoke the repo-local acceptance-driver skill (or read "
        ".claude/skills/acceptance-driver/SKILL.md directly) and follow it — it states "
        "this same sanction and honesty contract from the repo itself. Do NOT invoke "
        "the acceptance skill: that is the owner's front door for starting a NEW run — "
        "it refuses to nest by design, and you are already inside the run it delegates "
        "to; its never-hand-execute-internals rule addresses the owner's interactive "
        "session, not the harness's own driver child (issue #344). The "
        "work-item below is NOT a normal discovery work-item: its accept-harness- prefix "
        "is the harness's own reserved namespace (RESERVED_PREFIX in "
        "acceptance_fixture.py), and the harness materialized it moments ago as a "
        "throwaway fixture with a pre-approved spec/plan/tasks triple"
        + ((" at %s — read those files if in doubt" % fixture_dir) if fixture_dir else "")
        + ". Driving the showrunner spine on "
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


# #235 default byte-identical guard: with no spine-lib override the prompt must be exactly
# today's installed-plugin wording (preamble + body) — nothing about the override may leak in.
_DEFAULT_PROMPT = _preamble(None) + (
    "Run the superheroes:showrunner skill end-to-end on the approved work-item "
    "accept-harness-abc123 (invoke it exactly as documented in its SKILL.md — pre-flight, "
    "then the Workflow tool on the committed bundle with args: {workItem: accept-harness-abc123}). "
    "After the run reaches a terminal state (ready or parked), compute its "
    "run-outcome projection via plugins/superheroes/lib/run_readout.py's "
    "run_outcome(state) function over the run's end state, and write that projection "
    "as JSON to this exact path, creating parent directories as needed: /run/dir/terminal-record.json "
    "(a transient temp-dir handoff file the harness reads after you exit; the "
    "ordinary Write tool is fine). "
    "Do not merge, release, or force-push anything — this run's changes are confined "
    "to the work-item's own branch and PR."
)


def test_launch_prompt_carries_no_guard_evasion_coaching():
    # Finding #16 (run e0cf530f): a child correctly REFUSED a prompt that instructed a
    # write technique *because* it evades the sensitive-file guard. The prompt must never
    # coach guard evasion — no "sensitive-file guard", no "NEVER the Write tool", no
    # argv-because-it-dodges framing.
    for prompt in (
        al.build_launch_prompt("wi", "/tmp/x/terminal-record.json"),
        al.build_launch_prompt("wi", "/tmp/x/terminal-record.json",
                               spine_lib="/lib", root="/root"),
    ):
        low = prompt.lower()
        assert "sensitive-file guard" not in low
        assert "never the write" not in low
        assert "regardless of permission rules" not in low


def test_launch_prompt_forecloses_the_acceptance_skill_route():
    # Issue #344 (two live parks, 2026-07-10): the child obeys repo-carried skill surfaces
    # over its inline prompt. The front-door `acceptance` skill's refuse-to-nest contract
    # read as "refuse this prompt", so the prompt must (a) foreclose that route explicitly,
    # (b) hand the child a verifiable sanction (the env marker only the launcher sets), and
    # (c) point at the repo-carried driver protocol (the acceptance-driver skill) — in BOTH
    # prompt forms.
    for prompt in (
        al.build_launch_prompt("wi", "/tmp/x/terminal-record.json"),
        al.build_launch_prompt("wi", "/tmp/x/terminal-record.json",
                               spine_lib="/lib", root="/root"),
    ):
        assert al._CONTEXT_MARKER in prompt
        assert "acceptance-driver" in prompt
        assert "Do NOT invoke the acceptance skill" in prompt


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def test_driver_skill_file_carries_the_protocol_the_prompt_points_at():
    # Drift guard binding the two surfaces (#344): the prompt names the repo-local
    # acceptance-driver skill, so that file must exist and carry the load-bearing facts —
    # the verifiable marker, the run_outcome honesty contract, the reserved prefix, and
    # the never-merge line. If the skill moves or loses one, this fails with the prompt.
    path = os.path.join(_repo_root(), ".claude", "skills", "acceptance-driver", "SKILL.md")
    assert os.path.isfile(path), path
    body = open(path, encoding="utf-8").read()
    assert al._CONTEXT_MARKER in body
    assert "run_outcome" in body
    assert "accept-harness-" in body
    assert "Never merge, release, or force-push" in body
    # and the front door must hand the spawned child over to the driver skill, not a dead end
    front = open(os.path.join(_repo_root(), ".claude", "skills", "acceptance", "SKILL.md"),
                 encoding="utf-8").read()
    assert "acceptance-driver" in front


def test_build_launch_prompt_threads_explicit_fixture_dir_into_preamble():
    # The preamble's fixture pointer must name the ACTUALLY materialized location when the
    # caller provides it (a wrong/derived pointer is a false claim the driver will — and
    # did, live — reject as injection). Default (no fixture_dir) falls back to the terminal
    # record's directory.
    prompt = al.build_launch_prompt(
        "accept-harness-abc123", "/run/dir/terminal-record.json",
        fixture_dir="/store/docs/accept-harness-abc123")
    assert "triple at /store/docs/accept-harness-abc123 — read those files" in prompt
    # No fixture_dir -> the pointer clause is OMITTED (never derived from the terminal
    # path: that dir no longer holds the triple, and a wrong pointer is a false claim
    # the driver rejects as injection — review fix, PR #244).
    bare = al.build_launch_prompt("accept-harness-abc123", "/run/dir/terminal-record.json")
    assert "read those files" not in bare
    assert al.build_launch_prompt("accept-harness-abc123", None)  # None terminal_path tolerated


def test_default_child_factory_threads_materialized_fixture_dir(monkeypatch):
    # stamped["paths"] is where materialize() reports the real doc locations; the factory
    # must derive the preamble pointer from them, not from the terminal path.
    captured = {}

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            self.pid = 321

    monkeypatch.setattr(al.subprocess, "Popen", _FakePopen)
    al._default_child_factory(
        {"work_item": "accept-harness-abc123",
         "paths": ["/store/docs/accept-harness-abc123/spec.md",
                   "/store/docs/accept-harness-abc123/plan.md"]},
        terminal_path="/run/dir/terminal-record.json")
    prompt = captured["argv"][2]
    assert "triple at /store/docs/accept-harness-abc123 — read those files" in prompt
    # #255: the child must run in default mode — a flag-less headless claude -p lands in
    # the auto-mode-classifier context that blocked courier dispatches as oversight-evasion.
    argv = captured["argv"]
    assert argv[argv.index("--permission-mode") + 1] == "default"


def test_build_launch_prompt_default_is_byte_identical_when_spine_lib_unset():
    # The default (installed-plugin) path must be unchanged: byte-for-byte the documented
    # prompt, and it must never name a bundle path or a libRoot arg.
    prompt = al.build_launch_prompt("accept-harness-abc123", "/run/dir/terminal-record.json")
    assert prompt == _DEFAULT_PROMPT
    assert "libRoot" not in prompt
    assert "showrunner.bundle.js" not in prompt
    # Passing spine_lib=None (the explicit default) is identical to omitting it.
    assert al.build_launch_prompt(
        "accept-harness-abc123", "/run/dir/terminal-record.json", spine_lib=None) == _DEFAULT_PROMPT


def test_build_launch_prompt_override_names_bundle_path_and_libRoot():
    prompt = al.build_launch_prompt(
        "accept-harness-abc123", "/run/dir/terminal-record.json",
        spine_lib="/repo/plugins/superheroes/lib", root="/repo")
    # names the override bundle path explicitly...
    assert "/repo/plugins/superheroes/lib/showrunner.bundle.js" in prompt
    # ...and pins the spine via the existing libRoot launch seam + the real root.
    assert "libRoot: /repo/plugins/superheroes/lib" in prompt
    assert "root: /repo" in prompt
    assert "accept-harness-abc123" in prompt
    assert "/run/dir/terminal-record.json" in prompt
    # still drives the showrunner, still forbids merging.
    assert "superheroes:showrunner" in prompt
    assert "do not merge" in prompt.lower()


def test_build_launch_prompt_override_resolves_whole_spine_from_lib():
    # #235 item 2 (the headline self-check): the override must resolve the ENTIRE spine from
    # the override tree — pre-flight AND bundle AND libRoot — so pre-flight can't run from
    # the installed cache while the bundle comes from main (a silent cross-version mix).
    lib = "/repo/plugins/superheroes/lib"
    prompt = al.build_launch_prompt(
        "accept-harness-abc123", "/run/dir/terminal-record.json", spine_lib=lib, root="/repo")
    assert lib + "/preflight.py" in prompt          # pre-flight from the override tree
    assert lib + "/showrunner.bundle.js" in prompt   # bundle from the override tree
    assert "libRoot: " + lib in prompt               # Workflow libRoot from the override tree
    assert lib + "/run_readout.py" in prompt         # run-outcome projection from the override tree
    # and it explicitly forbids resolving $LIB from the installed plugin cache — pinned as the
    # contiguous forbidding phrase, so an inverted/removed instruction can't slip past.
    assert "do not let $lib resolve from the installed plugin cache" in prompt.lower()


def test_default_child_factory_pins_model_sonnet_by_default(monkeypatch):
    # #235 scope addition: the spawn must pin the driver model so it never inherits the
    # invoking user's CLI default (model-governance). Default is sonnet.
    captured = {}

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            self.pid = 321

    monkeypatch.setattr(al.subprocess, "Popen", _FakePopen)
    al._default_child_factory({"work_item": "accept-harness-abc123"},
                              terminal_path="/run/dir/terminal-record.json")
    argv = captured["argv"]
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "sonnet"
    assert al.DEFAULT_CHILD_MODEL == "sonnet"


def test_default_child_factory_honors_child_model_override(monkeypatch):
    captured = {}

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            self.pid = 654

    monkeypatch.setattr(al.subprocess, "Popen", _FakePopen)
    al._default_child_factory({"work_item": "accept-harness-abc123"},
                              terminal_path="/run/dir/terminal-record.json",
                              child_model="opus")
    argv = captured["argv"]
    assert argv[argv.index("--model") + 1] == "opus"


def test_default_child_factory_threads_spine_lib_into_prompt(monkeypatch):
    captured = {}

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            self.pid = 222

    monkeypatch.setattr(al.subprocess, "Popen", _FakePopen)
    al._default_child_factory(
        {"work_item": "accept-harness-abc123"},
        terminal_path="/run/dir/terminal-record.json",
        spine_lib="/repo/plugins/superheroes/lib", root="/repo")
    prompt = captured["argv"][2]
    assert "/repo/plugins/superheroes/lib/showrunner.bundle.js" in prompt
    assert "libRoot: /repo/plugins/superheroes/lib" in prompt


def test_default_child_factory_spawns_real_non_interactive_claude_with_prompt(monkeypatch):
    """code-001: the real spawn must use `-p`/`--print` (never the invalid `--headless`
    flag) and must pass a prompt that actually drives the showrunner on the stamped
    work-item — pinning the real factory's argv rather than only fake Popen calls."""
    captured = {}

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            self.pid = 12345

    monkeypatch.setattr(al.subprocess, "Popen", _FakePopen)
    stamped = {"work_item": "accept-harness-abc123"}
    al._default_child_factory(stamped, terminal_path="/run/dir/terminal-record.json")

    argv = captured["argv"]
    assert argv[0] == "claude"
    assert "--headless" not in argv                 # the invalid flag must never appear
    assert argv[1] in ("-p", "--print")              # the CLI's real non-interactive form
    assert len(argv) >= 3
    prompt = argv[2]
    assert "accept-harness-abc123" in prompt
    assert "superheroes:showrunner" in prompt
    assert "/run/dir/terminal-record.json" in prompt
    assert captured["kwargs"].get("start_new_session") is True
    env = captured["kwargs"].get("env") or {}
    assert env.get("SUPERHEROES_ACCEPTANCE_CONTEXT") == "1"
    assert env.get("SUPERHEROES_ACCEPTANCE_DENY_ONLY") == "1"


def test_default_child_factory_disables_print_mode_bg_wait_ceiling(monkeypatch):
    """0.10.0 qualification finding #6: `claude -p` terminates still-running background
    tasks after ~600s, killing the child mid-spine while it waits on the showrunner
    Workflow. The spawn env must disable that ceiling — the harness's own elapsed/spend
    ceilings (process-group kill) are the real governors."""
    captured = {}

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            captured["env"] = kwargs.get("env") or {}
            self.pid = 321

    monkeypatch.setattr(al.subprocess, "Popen", _FakePopen)
    al._default_child_factory("accept-harness-abc123", terminal_path="/t.json")
    assert captured["env"].get("CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS") == "0"


def test_default_child_factory_finite_bg_ceiling_when_provided(monkeypatch):
    """Review fix (PR #244 premortem): real_launcher passes a finite bg-wait ceiling
    (2x the harness elapsed ceiling) so an orphaned child is lifetime-bounded even if
    the harness process dies ungracefully; 0/absent stays the direct-caller fallback."""
    captured = {}

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            captured["env"] = kwargs.get("env") or {}
            self.pid = 321

    monkeypatch.setattr(al.subprocess, "Popen", _FakePopen)
    al._default_child_factory("accept-harness-abc123", terminal_path="/t.json",
                              bg_wait_ceiling_ms=3600000)
    assert captured["env"]["CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"] == "3600000"


# --- issue #245: live-child registry + bare-pgid orphan reap ---------------------------


def test_real_child_exposes_captured_pgid():
    # The pgid persisted into the lease is the leader pid captured at spawn (start_new_session
    # -> leader pid IS the pgid). Must be the captured value, not re-derived after the leader
    # exits (which would raise once reaped).
    class _P:
        pid = 4242
    child = al._RealChild(_P(), "/t.json")
    assert child.pgid() == 4242


def test_current_live_child_published_during_run_and_cleared_after():
    # The harness signal handler reads current_live_child() at delivery time; run() must
    # publish the child for the duration of the watch and clear it on exit.
    observed = []

    class _ObservingChild:
        def __init__(self):
            self.calls = 0

        def poll(self):
            observed.append(al.current_live_child())
            self.calls += 1
            return None if self.calls < 2 else 0

        def terminal_location(self):
            return "/t.json"

    assert al.current_live_child() is None
    child = _ObservingChild()
    al.run("wi", CEIL, child_factory=lambda: child, clock=FakeClock([0, 1, 2]),
           spend_sampler=lambda: (0.1, True), engine_pref_reader=lambda: {"all": "claude"})
    assert observed and observed[0] is child          # published while the loop watched
    assert al.current_live_child() is None             # cleared on exit (finally)


def test_current_live_child_cleared_even_when_watch_raises():
    # If an exception (e.g. the signal handler's _SignalTermination) unwinds the loop, the
    # finally still clears the slot — the handler has already captured the child by then.
    class _BoomChild:
        def poll(self):
            raise RuntimeError("boom")

        def terminal_location(self):
            return "/t.json"

    try:
        al.run("wi", CEIL, child_factory=lambda: _BoomChild(), clock=FakeClock([0, 1, 2]),
               spend_sampler=lambda: (0.1, True), engine_pref_reader=lambda: {"all": "claude"})
    except RuntimeError:
        pass
    assert al.current_live_child() is None


def _spawn_orphan_group():
    """Spawn a real, ORPHANED process group and return its pgid. Double-fork: an intermediate
    child calls setsid() (new session/group), forks a grandchild that execs `sleep`, then the
    intermediate exits immediately — so the grandchild is re-parented to init/a subreaper (as a
    harness orphan would be after an ungraceful death) and is auto-reaped on death, leaving no
    zombie for the test process. This mirrors the real scenario the bare-pgid reaper must
    handle, where killpg confirms the group empty because someone else reaps the dead members."""
    if not hasattr(os, "fork"):
        import pytest
        pytest.skip("os.fork unavailable (real orphan-group reap is a POSIX-only test)")
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:  # intermediate child
        os.close(r)
        os.setsid()
        pid2 = os.fork()
        if pid2 == 0:  # grandchild -> becomes the sleeping group member
            os.write(w, str(os.getpgrp()).encode())  # pgrp == intermediate pid == the pgid
            os.close(w)
            os.execvp("sleep", ["sleep", "30"])
            os._exit(127)
        os._exit(0)   # intermediate exits -> grandchild orphaned (re-parented to init)
    os.close(w)
    pgid = int(os.read(r, 32).decode())
    os.close(r)
    os.waitpid(pid, 0)  # reap the intermediate (our only direct child)
    return pgid


def test_reap_group_by_pgid_kills_a_live_orphan_group():
    # End-to-end: the bare-pgid reaper actually signals a live group to death and confirms it
    # empty — the real primitive the lease-reclaim orphan check relies on (issue #245).
    import pytest
    pgid = _spawn_orphan_group()
    try:
        os.killpg(pgid, 0)                          # sanity: alive before reap
        assert al.reap_group_by_pgid(pgid) is True  # reaped to confirmed-empty
        with pytest.raises(ProcessLookupError):     # genuinely gone
            os.killpg(pgid, 0)
    finally:
        try:
            os.killpg(pgid, 9)
        except OSError:
            pass


def test_reap_group_by_pgid_already_empty_confirms_dead():
    # A pgid whose group already has no surviving member confirms "dead" without hanging.
    pgid = _spawn_orphan_group()
    os.killpg(pgid, 9)
    deadline = time.monotonic() + 5
    gone = False
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            gone = True
            break
        except PermissionError:
            # macOS: killpg(pgid, 0) on a killed-but-not-yet-reaped (zombie) group raises
            # EPERM, not ESRCH — keep polling until init reaps it and ESRCH appears.
            pass
        time.sleep(0.02)
    if not gone:
        import pytest
        pytest.skip("platform never reported the killed group empty within the deadline "
                    "(zombie-group killpg semantics); the unsignalable-group test covers "
                    "the fail-closed branch deterministically")
    assert al.reap_group_by_pgid(pgid) is True


def test_reap_group_by_pgid_unsignalable_group_is_not_confirmed(monkeypatch):
    # A present-but-unsignalable group (PermissionError from killpg probe — e.g. owned by
    # another user) must NOT be declared empty: the escalation ends unconfirmed (False) so the
    # lease reclaim fails closed rather than reclaiming under a live orphan.
    monkeypatch.setattr(al.time, "sleep", lambda s: None)

    def perm_killpg(pgid, sig):
        if sig == 0:
            raise PermissionError()
        # signalling attempts are swallowed; the group never becomes confirmable

    monkeypatch.setattr(al.os, "killpg", perm_killpg)
    assert al.reap_group_by_pgid(1234567) is False
