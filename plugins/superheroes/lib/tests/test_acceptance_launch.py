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


def test_kill_confirmed_dead_only_when_group_empty():
    # SIGTERM then SIGKILL escalation until the group is empty.
    child = FakeChild(exits_after=999, group_empty_after=1)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 101, 101, 101, 101]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "killed"
    assert len(child.signals) >= 2  # SIGTERM then SIGKILL escalation


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
