# plugins/superheroes/lib/tests/test_acceptance_launch.py
import os, subprocess, sys, time
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


# #235 default byte-identical guard: with no spine-lib override the prompt must be exactly
# today's installed-plugin wording — nothing about the override may leak in.
_DEFAULT_PROMPT = (
    "Run the superheroes:showrunner skill end-to-end on the approved work-item "
    "accept-harness-abc123 (invoke it exactly as documented in its SKILL.md — pre-flight, "
    "then the Workflow tool on the committed bundle with args: {workItem: accept-harness-abc123}). "
    "After the run reaches a terminal state (ready or parked), compute its "
    "run-outcome projection via plugins/superheroes/lib/run_readout.py's "
    "run_outcome(state) function over the run's end state, and write that projection "
    "as JSON to this exact path, creating parent directories as needed: /run/dir/terminal-record.json. "
    "Do not merge, release, or force-push anything — this run's changes are confined "
    "to the work-item's own branch and PR."
)


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
