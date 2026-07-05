# plugins/superheroes/lib/tests/test_acceptance_run_cli.py
#
# Task 13 DoD guard: the live-run command the acceptance SKILL.md documents
# (`python3 "$LIB/acceptance_run.py" --fixture <fixture> --root <root>`) must be a
# REAL, honest entrypoint that actually drives the harness — not a silent no-op AND
# not a stub that declines to run. Before this task it had no `__main__` block at
# all (silent exit-0, no verdict/record/report); a later attempt added a guard that
# always exited non-zero explaining that "this bare entrypoint does not spawn a live
# showrunner" — honest about not running, but still never assembled the real `deps`
# anywhere in the repo, so the documented command could never produce a verdict no
# matter who ran it.
#
# These tests pin the entrypoint's contract:
#   - in-process: `_cli` with no `deps_builder` override defaults to the REAL
#     `acceptance_deps.build` (the actual live-run wiring), not a stub;
#   - in-process: `_cli` with an injected fake `deps_builder` actually calls
#     `acceptance_run.invoke` on the assembled deps and prints its report / exits
#     0-or-1 on the computed verdict — i.e. the CLI performs a real invocation, it
#     does not just validate arguments and refuse;
#   - subprocess: never a real live run in this suite — a BOGUS fixture path (never the
#     real committed fixture) makes the real wiring's own `materialize()` fail closed
#     before `preflight_ok`/`launcher` ever runs (see `invoke`'s step ordering: 2.
#     materialize precedes 3. preflight), so these subprocess tests can drive the actual
#     `__main__` entrypoint end-to-end without ever spawning `claude --headless`. Each
#     subprocess also gets its own `SUPERHEROES_STORE_ROOT` (tmp_path) so it never
#     touches this repo's real control-plane store;
#   - subprocess: the documented command never silently exits 0 with empty output, even
#     on that internal failure;
#   - subprocess: the execution-context marker (UFR-5) makes it refuse to nest — before
#     even the bogus fixture is touched.
import io
import os
import subprocess
import sys

HERE = os.path.dirname(__file__)
LIB = os.path.normpath(os.path.join(HERE, ".."))
RUN_PY = os.path.join(LIB, "acceptance_run.py")
FIXTURE = os.path.normpath(
    os.path.join(HERE, "..", "..", "eval", "fixtures", "acceptance")
)
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
# Deliberately not a real fixture dir — see the module docstring: this guarantees the
# subprocess tests below never reach the real launcher (no live `claude --headless`).
BOGUS_FIXTURE = os.path.join(HERE, "no-such-acceptance-fixture-dir")

sys.path.insert(0, LIB)
import acceptance_run as run          # noqa: E402
import acceptance_deps                # noqa: E402


def _invoke_subprocess(tmp_path, env_extra=None, fixture=BOGUS_FIXTURE):
    env = dict(os.environ)
    # Never let a surrounding acceptance/showrunner context leak into the top-level cases.
    env.pop("SUPERHEROES_ACCEPTANCE_CONTEXT", None)
    # Isolate the control-plane store per-subprocess (never write into the real repo's).
    env["SUPERHEROES_STORE_ROOT"] = str(tmp_path)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, RUN_PY, "--fixture", fixture, "--root", ROOT],
        capture_output=True,
        text=True,
        env=env,
    )


def test_default_deps_builder_is_the_real_wiring_not_a_stub():
    """`_cli` with no override must default to the real `acceptance_deps.build` — the
    thing that actually assembles a live launcher/gh-reader/lease, not a decline.

    Safety: this must NEVER let a real launch happen (no `claude --headless` spawn) even
    though `acceptance_deps.build` is genuinely called. It intercepts at `invoke` — one
    layer past `build` — so `build` runs for real (proving the wiring is genuine) but the
    assembled deps are never actually executed.
    """
    calls = []
    captured_deps = {}
    real_build = acceptance_deps.build
    real_invoke = run.invoke

    def _spy_build(fixture, root):
        calls.append((fixture, root))
        return real_build(fixture, root)

    def _fake_invoke(deps):
        # Never call the real deps (would spawn a live showrunner) — just prove `_cli`
        # handed `invoke` a deps dict built by the real, non-stub wiring.
        captured_deps["deps"] = deps
        return {"verdict": "fail", "report": "intercepted before any live launch",
               "record_path": None}

    acceptance_deps.build = _spy_build
    run.invoke = _fake_invoke
    try:
        env = dict(os.environ)
        env.pop("SUPERHEROES_ACCEPTANCE_CONTEXT", None)
        code = run._cli(["--fixture", FIXTURE, "--root", ROOT], env,
                        io.StringIO(), io.StringIO())
    finally:
        acceptance_deps.build = real_build
        run.invoke = real_invoke
    assert calls == [(FIXTURE, ROOT)]
    assert code == 1   # the intercepted fake_invoke returned a fail verdict
    # every seam `acceptance_run.invoke` requires is present and callable — real wiring,
    # not a stub that returns an incomplete/placeholder bundle.
    required_seams = {"reclaim_probe", "materialize", "preflight_ok", "launcher",
                      "run_outcome", "gh_reader", "expected_phases", "discover_artifacts",
                      "reap", "write_record", "write_refusal_record", "write_orphan_record",
                      "quarantine_lease", "release_lease", "clock_now"}
    assert required_seams <= set(captured_deps["deps"].keys())
    assert all(callable(captured_deps["deps"][k]) for k in required_seams)


def test_cli_threads_ceiling_overrides_to_the_real_builder():
    calls = []
    real_build = acceptance_deps.build
    real_invoke = run.invoke

    def _spy_build(fixture, root, ceilings=None):
        calls.append({"fixture": fixture, "root": root, "ceilings": ceilings})
        return real_build(fixture, root, ceilings=ceilings)

    def _fake_invoke(deps):
        return {"verdict": "fail", "report": "intercepted before any live launch",
                "record_path": None}

    acceptance_deps.build = _spy_build
    run.invoke = _fake_invoke
    try:
        env = dict(os.environ)
        env.pop("SUPERHEROES_ACCEPTANCE_CONTEXT", None)
        code = run._cli([
            "--fixture", FIXTURE, "--root", ROOT,
            "--ceiling-elapsed-sec", "7",
            "--ceiling-spend", "123",
        ], env, io.StringIO(), io.StringIO())
    finally:
        acceptance_deps.build = real_build
        run.invoke = real_invoke

    assert code == 1
    assert calls[0]["ceilings"] == {"elapsed_sec": 7.0, "spend": 123.0}


def test_cli_threads_spine_lib_to_the_real_builder():
    # #235: `--spine-lib` must reach the real `acceptance_deps.build` as its `spine_lib`
    # kwarg (and coexist with the ceiling overrides).
    calls = []
    real_build = acceptance_deps.build
    real_invoke = run.invoke

    def _spy_build(fixture, root, ceilings=None, spine_lib=None):
        calls.append({"fixture": fixture, "root": root, "ceilings": ceilings,
                      "spine_lib": spine_lib})
        return real_build(fixture, root, ceilings=ceilings, spine_lib=spine_lib)

    def _fake_invoke(deps):
        return {"verdict": "fail", "report": "intercepted before any live launch",
                "record_path": None}

    acceptance_deps.build = _spy_build
    run.invoke = _fake_invoke
    try:
        env = dict(os.environ)
        env.pop("SUPERHEROES_ACCEPTANCE_CONTEXT", None)
        code = run._cli([
            "--fixture", FIXTURE, "--root", ROOT,
            "--spine-lib", "/repo/plugins/superheroes/lib",
        ], env, io.StringIO(), io.StringIO())
    finally:
        acceptance_deps.build = real_build
        run.invoke = real_invoke

    assert code == 1
    assert calls[0]["spine_lib"] == "/repo/plugins/superheroes/lib"
    # unset ceilings still not forced through (only pass kwargs that were given)
    assert calls[0]["ceilings"] is None


def test_cli_threads_child_model_to_the_real_builder():
    # #235 scope addition: `--child-model` must reach the real `acceptance_deps.build` as
    # its `child_model` kwarg; unset leaves it to build's own default (sonnet).
    calls = []
    real_build = acceptance_deps.build
    real_invoke = run.invoke

    def _spy_build(fixture, root, ceilings=None, spine_lib=None, child_model=None):
        calls.append({"child_model": child_model})
        return real_build(fixture, root, ceilings=ceilings, spine_lib=spine_lib,
                          child_model=child_model)

    def _fake_invoke(deps):
        return {"verdict": "fail", "report": "intercepted", "record_path": None}

    acceptance_deps.build = _spy_build
    run.invoke = _fake_invoke
    try:
        env = dict(os.environ)
        env.pop("SUPERHEROES_ACCEPTANCE_CONTEXT", None)
        code = run._cli(["--fixture", FIXTURE, "--root", ROOT, "--child-model", "opus"],
                        env, io.StringIO(), io.StringIO())
    finally:
        acceptance_deps.build = real_build
        run.invoke = real_invoke
    assert code == 1
    assert calls[0]["child_model"] == "opus"


def test_cli_unset_child_model_not_forced_through():
    # When --child-model is omitted, the CLI must NOT pass the kwarg (so a legacy 2-arg
    # spy builder still works); build's own default (sonnet) then applies.
    calls = []
    real_build = acceptance_deps.build
    real_invoke = run.invoke

    def _spy_build(fixture, root):   # legacy 2-arg signature
        calls.append((fixture, root))
        return real_build(fixture, root)

    def _fake_invoke(deps):
        return {"verdict": "fail", "report": "intercepted", "record_path": None}

    acceptance_deps.build = _spy_build
    run.invoke = _fake_invoke
    try:
        env = dict(os.environ)
        env.pop("SUPERHEROES_ACCEPTANCE_CONTEXT", None)
        code = run._cli(["--fixture", FIXTURE, "--root", ROOT], env,
                        io.StringIO(), io.StringIO())
    finally:
        acceptance_deps.build = real_build
        run.invoke = real_invoke
    assert code == 1
    assert calls == [(FIXTURE, ROOT)]


def test_cli_bad_ceilings_config_returns_argparse_status_without_raising(tmp_path):
    env = dict(os.environ)
    env.pop("SUPERHEROES_ACCEPTANCE_CONTEXT", None)
    code = run._cli([
        "--fixture", FIXTURE, "--root", ROOT,
        "--ceilings-config", str(tmp_path / "missing.json"),
    ], env, io.StringIO(), io.StringIO(), deps_builder=lambda fixture, root: {})

    assert code == 2


def test_cli_threads_valid_ceilings_config_to_the_real_builder(tmp_path):
    config = tmp_path / "ceilings.json"
    config.write_text('{"elapsed_sec": 9, "spend": 456}\n', encoding="utf-8")
    calls = []
    real_build = acceptance_deps.build
    real_invoke = run.invoke

    def _spy_build(fixture, root, ceilings=None):
        calls.append({"fixture": fixture, "root": root, "ceilings": ceilings})
        return real_build(fixture, root, ceilings=ceilings)

    def _fake_invoke(deps):
        return {"verdict": "fail", "report": "intercepted before any live launch",
                "record_path": None}

    acceptance_deps.build = _spy_build
    run.invoke = _fake_invoke
    try:
        env = dict(os.environ)
        env.pop("SUPERHEROES_ACCEPTANCE_CONTEXT", None)
        code = run._cli([
            "--fixture", FIXTURE, "--root", ROOT,
            "--ceilings-config", str(config),
        ], env, io.StringIO(), io.StringIO())
    finally:
        acceptance_deps.build = real_build
        run.invoke = real_invoke

    assert code == 1
    assert calls[0]["ceilings"] == {"elapsed_sec": 9.0, "spend": 456.0}


def test_cli_drives_a_real_invocation_via_an_injected_deps_builder():
    """With a fake (but complete) deps bundle injected, `_cli` must actually call
    `acceptance_run.invoke` — not merely parse args and refuse — and surface its
    verdict/report through the exit code and stdout."""
    written = []

    def _fake_builder(fixture, root):
        return dict(
            reclaim_probe=lambda: ({"in_flight": False, "stamp": None, "has_record": False}, "dead"),
            preflight_ok=lambda wi: {"ok": True},
            materialize=lambda: {"work_item": "wi-s1", "branch": "b-s1", "pr_title": "PR s1",
                                 "stamp": "s1"},
            launcher=lambda stamped, budget_consumed=None, attempt=1: {
                "outcome": "exited", "terminal_location": "/t.json", "spend_partial": False,
                "spend": 0.5, "elapsed_sec": 10.0},
            run_outcome=lambda loc: {"terminal": "ready",
                                     "phases": ["plan", "tasks", "build", "review", "ship"],
                                     "readout_pr_link": "https://x/pr/1",
                                     "readout_claimed_checks_green": True,
                                     "readout_claimed_pr": "https://x/pr/1"},
            gh_reader=lambda: {"pr_exists": True, "pr_ready_for_review": True,
                               "checks_green": True, "live_checks_green": True,
                               "live_pr": "https://x/pr/1", "unreadable": []},
            expected_phases=lambda: ["plan", "tasks", "build", "review", "ship"],
            discover_artifacts=lambda stamp: [],
            reap=lambda planned: {"cleaned_up": [], "left_behind": []},
            write_record=lambda rec: written.append(rec) or "/rec.json",
            release_lease=lambda: None,
            clock_now=lambda: "2026-07-02T00:00:00Z",
        )

    env = dict(os.environ)
    env.pop("SUPERHEROES_ACCEPTANCE_CONTEXT", None)
    out = io.StringIO()
    code = run._cli(["--fixture", FIXTURE, "--root", ROOT], env, out, io.StringIO(),
                    deps_builder=_fake_builder)
    assert code == 0                       # the fake bundle above computes a pass
    assert len(written) == 1               # invoke() actually ran the lifecycle
    printed = out.getvalue()
    assert "PASS" in printed.upper()
    assert "/rec.json" in printed          # the report names where the record lives


def test_documented_command_is_a_real_entrypoint_not_a_silent_noop(tmp_path):
    """The SKILL.md DoD command must not silently exit 0 with no output, and must
    actually run the real lifecycle (verdict + a written record), not merely refuse."""
    proc = _invoke_subprocess(tmp_path)
    combined = (proc.stdout or "") + (proc.stderr or "")
    # The original bug: exit 0 AND no output == a silent no-op live run.
    silent_success = proc.returncode == 0 and combined.strip() == ""
    assert not silent_success, (
        "acceptance_run.py ran as the documented DoD command but produced a silent "
        "exit-0 no-op (no verdict / record / report); a live run must never silently "
        "succeed with no effect"
    )
    # The later regression this guards against: a stub that always declines without
    # ever running the lifecycle. A real run always renders a verdict + record line.
    assert "verdict" in combined.lower()
    assert "record" in combined.lower()


def test_documented_command_refuses_to_nest(tmp_path):
    """UFR-5: with the execution-context marker set the entrypoint refuses (non-zero)."""
    proc = _invoke_subprocess(tmp_path, {"SUPERHEROES_ACCEPTANCE_CONTEXT": "1"})
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0
    assert "nest" in combined.lower()
