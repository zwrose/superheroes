"""Per-lens conformance harness — honesty invariants every production lens must prove."""
import contextlib
import errno
import importlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

import guardian_collect as gc
import guardian_lens as gl
import pytest

_HARNESS_OWNED = set(gl.REQUIRED_CONFORMANCE_SCENARIOS) - frozenset(
    gl.LENS_SUPPLIED_CONFORMANCE_SCENARIOS)
_LENS_SUPPLIED = frozenset(gl.LENS_SUPPLIED_CONFORMANCE_SCENARIOS)
_REPORTED_NONZERO_PARSED_ZERO = "reported-nonzero-parsed-zero"
_PREV_DIGEST = {"v": 1, "ids": ["prior-1"]}
_REPORTED_NONZERO_STDOUT = json.dumps({"reported_findings": 3, "findings": []})
_CLEAN_STDOUT = json.dumps({"findings": []})


def _counting_run(body):
    """Return (run_stub, call_counter) where call_counter[0] tracks invocations."""
    calls = [0]

    def run(argv, **kwargs):
        calls[0] += 1
        return body(argv, **kwargs)

    return run, calls


def _harness_run_missing_tool(argv, **kwargs):
    raise FileNotFoundError(errno.ENOENT, "conformance-tool")


def _harness_run_timeout(argv, **kwargs):
    raise subprocess.TimeoutExpired(cmd=argv, timeout=60)


def _harness_run_nonzero_exit(argv, **kwargs):
    class R(object):
        returncode = 127
        stdout = ""
        stderr = ""
    return R()


def _harness_run_findings_empty(argv, **kwargs):
    class R(object):
        returncode = 0
        stdout = ""
        stderr = ""
    return R()


def _harness_run_unparseable(argv, **kwargs):
    class R(object):
        returncode = 0
        stdout = "\x00not-parseable\xffgarbage{{{"
        stderr = ""
    return R()


_HARNESS_RUN_BUILDERS = {
    "missing-tool": _harness_run_missing_tool,
    "timeout": _harness_run_timeout,
    "nonzero-exit": _harness_run_nonzero_exit,
    "findings-empty-output": _harness_run_findings_empty,
    "unparseable": _harness_run_unparseable,
}


def _lens_supplied_run_body(stdout_text, exit_code):
    def body(argv, **kwargs):
        class R(object):
            returncode = exit_code
            stdout = stdout_text
            stderr = ""
        return R()
    return body


def _dispatch_run_body(case, probe):
    """Return a run stub that dispatches stdout/exit on argv[0] (PRE-AUTHORIZED per-tool
    payloads).

    ``probe`` is ``"clean"`` or ``"findings"``. A multi-collector lens can declare
    ``stdout_by_tool`` / ``clean_stdout_by_tool`` (argv[0] → stdout) so ONLY its targeted
    collector gets the findings payload and every co-firing collector gets a CLEAN one —
    otherwise a single shared stdout degrades the whole lens through a co-firing tool
    regardless of whether the targeted gate works (which would let a deleted gate still
    pass conformance).

    Backward-compatible: a case with NO ``stdout_by_tool`` behaves exactly as the legacy
    single-stdout body — the findings probe hands ``case["stdout"]`` to every tool at the
    findings exit; the clean probe hands ``case["clean_stdout"]`` to every tool at the
    clean exit.
    """
    exit_code = case["exit"]
    clean_exit = case.get("clean_exit", exit_code)
    default_clean = case["clean_stdout"]
    default_findings = case["stdout"]
    findings_by_tool = case.get("stdout_by_tool") or {}
    clean_by_tool = case.get("clean_stdout_by_tool") or {}

    def body(argv, **kwargs):
        argv0 = argv[0] if argv else ""
        if probe == "clean":
            out_text, code = clean_by_tool.get(argv0, default_clean), clean_exit
        elif not findings_by_tool:
            # Legacy single-stdout findings probe: every tool gets the findings payload.
            out_text, code = default_findings, exit_code
        elif argv0 in findings_by_tool:
            out_text, code = findings_by_tool[argv0], exit_code
        else:
            # Co-firing collector under a dispatch case: a clean payload so ONLY the
            # targeted collector exercises the findings path.
            out_text, code = clean_by_tool.get(argv0, default_clean), clean_exit

        class R(object):
            returncode = code
            stdout = out_text
            stderr = ""
        return R()
    return body


def _conformance_prev_spec(lens, case):
    """Resolve the prior digest + non-vacuity sentinel for a lens-supplied case.

    A lens may expose ``conformance_prev_digest() -> {"prev", "cleared", "sentinelIds"}``
    to feed a SCHEMA-VALID prior digest whose sentinel finding its OWN ``diff()`` tracks.
    The harness proves the sentinel is recognized (``diff(prev, cleared)`` resolves it)
    before asserting the degraded findings probe resolves nothing — otherwise "resolved
    must be empty" is vacuous (a generic ``_PREV_DIGEST`` carries no finding the real
    lens's diff even reads). Falls back to the case's ``prev_digest`` (or the generic
    ``_PREV_DIGEST``) with no sentinel when the lens does not provide the hook.
    """
    hook = getattr(lens, "conformance_prev_digest", None)
    if callable(hook):
        spec = hook() or {}
        return {
            "prev": spec.get("prev", case.get("prev_digest", dict(_PREV_DIGEST))),
            "cleared": spec.get("cleared"),
            "sentinelIds": list(spec.get("sentinelIds") or []),
        }
    return {
        "prev": case.get("prev_digest", dict(_PREV_DIGEST)),
        "cleared": None,
        "sentinelIds": [],
    }


def _run_conformance_probe(lens, scenario, run_stub, call_counter, config, prev_digest,
                           cwd, root):
    ctx = {
        "cwd": cwd,
        "root": root,
        "config": config,
        "run": run_stub,
        "prevDigest": prev_digest,
    }
    out = lens.collect(ctx)

    assert call_counter[0] >= 1, (
        "lens %r scenario %r: ctx['run'] stub was never invoked"
        % (lens.name, scenario))

    status, reason = gl.classify_collect(out)
    return out, status, reason


@contextlib.contextmanager
def _scenario_workspace(lens, default_cwd, default_root):
    """Per-scenario cwd/root for a lens that declares ``conformance_fixture``.

    A manifest-gated lens (needs package.json / requirements.txt present to reach its
    tool) never invokes ctx["run"] at /tmp. When the lens defines conformance_fixture(),
    the harness writes those files into a fresh temp dir and uses it as BOTH ctx["cwd"]
    and ctx["root"] so the tool is reachable under the injected run stub. A lens that
    does not define it keeps the unchanged /tmp behavior.
    """
    fixture_method = getattr(lens, "conformance_fixture", None)
    if fixture_method is None:
        yield default_cwd, default_root
        return
    files = fixture_method() or {}
    tmpdir = tempfile.mkdtemp(prefix="guardian-conformance-fixture-")
    try:
        _write_workspace_files(tmpdir, files)
        yield tmpdir, tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _write_workspace_files(tmpdir, files):
    for relpath, content in files.items():
        dest = os.path.join(tmpdir, relpath)
        os.makedirs(os.path.dirname(dest) or tmpdir, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(content)


class _ToolFreeSpawnViolation(BaseException):
    """Raised by a stubbed spawn primitive when a tool-free lens tries to spawn.

    A BaseException (not Exception) so a lens's own ``except Exception`` cannot swallow
    the proof that it violated its ``uses_external_tools = False`` claim.
    """


_TOOL_FREE_SPAWN_TARGETS = (
    ("guardian_collect", "run_tool"),
    ("store_core", "run_git"),
    ("core_md", "read"),
)
_TOOL_FREE_MODULE_SPAWN_ATTRS = {
    subprocess: ("run", "Popen", "call", "check_call", "check_output"),
    # fork / forkpty / posix_spawn(p) are guarded by hasattr in the patch loop (they do
    # not exist on every platform), so a tool-free lens that reaches ANY spawn primitive —
    # not just system/popen — surfaces its violation. The AST guard in
    # test_guardian_lens_no_subprocess.py is the fail-closed static complement.
    os: ("system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp"),
}


def _lens_fixture_files(lens):
    fixture_method = getattr(lens, "conformance_fixture", None)
    if fixture_method is None:
        return {}
    return fixture_method() or {}


@contextlib.contextmanager
def _tool_free_workspace(case):
    """Materialize a tool-free scenario workspace: fixture files + unreadable inputs.

    An ``unreadable`` entry is a path that exists where the lens expects a readable file
    but cannot be read as one. It is materialized as a **directory** rather than a
    chmod(0) file: ``open()`` on a directory raises ``IsADirectoryError`` (an ``OSError``)
    for every uid, whereas chmod(0) is ignored by root — so the scenario holds under
    root/CI too.
    """
    tmpdir = tempfile.mkdtemp(prefix="guardian-toolfree-")
    try:
        _write_workspace_files(tmpdir, case.get("fixture") or {})
        for relpath in (case.get("unreadable") or []):
            dest = os.path.join(tmpdir, relpath)
            os.makedirs(os.path.dirname(dest) or tmpdir, exist_ok=True)
            if os.path.exists(dest):
                os.remove(dest)
            os.makedirs(dest)
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _assert_no_indirect_spawn(lens):
    """Prove (do not trust) that a tool-free lens's collect() spawns nothing.

    Monkeypatch run_tool + the indirect spawn helpers + the raw spawn primitives to raise,
    then run collect() over the lens's declared fixture. A lens that reaches any of them
    surfaces its violation.
    """
    def _raiser(*_a, **_k):
        raise _ToolFreeSpawnViolation("spawn primitive invoked")

    saved = []
    for module_name, attr in _TOOL_FREE_SPAWN_TARGETS:
        try:
            module = importlib.import_module(module_name)
        except Exception:  # helper module not importable in this tree — skip
            continue
        if hasattr(module, attr):
            saved.append((module, attr, getattr(module, attr)))
            setattr(module, attr, _raiser)
    for module, attrs in _TOOL_FREE_MODULE_SPAWN_ATTRS.items():
        for attr in attrs:
            if hasattr(module, attr):
                saved.append((module, attr, getattr(module, attr)))
                setattr(module, attr, _raiser)

    try:
        with _tool_free_workspace({"fixture": _lens_fixture_files(lens)}) as workspace:
            ctx = {
                "cwd": workspace,
                "root": workspace,
                "config": None,
                "run": None,
                "prevDigest": dict(_PREV_DIGEST),
            }
            try:
                lens.collect(ctx)
            except _ToolFreeSpawnViolation as exc:
                raise AssertionError(
                    "lens %r declares uses_external_tools=False but collect() invoked a "
                    "spawn primitive: %s" % (lens.name, exc))
    finally:
        for module, attr, value in saved:
            setattr(module, attr, value)


def _assert_tool_free_conformance(lens):
    """Honesty invariants + no-spawn proof for a ``uses_external_tools = False`` lens."""
    cases = lens.conformance_cases()
    missing = set(gl.TOOL_FREE_CONFORMANCE_SCENARIOS) - set(cases.keys())
    assert not missing, (
        "tool-free lens %r missing conformance scenarios: %s"
        % (lens.name, sorted(missing)))

    _assert_no_indirect_spawn(lens)

    # B2 non-vacuity: if the lens supplies a sentinel-carrying prior digest, prove its own
    # diff() tracks that sentinel (resolves it against a clean re-measure) BEFORE the
    # scenarios below assert "resolved must be empty" — otherwise those checks are vacuous.
    _hook = getattr(lens, "conformance_prev_digest", None)
    if callable(_hook):
        _spec = _hook() or {}
        _sentinels = list(_spec.get("sentinelIds") or [])
        if _sentinels and _spec.get("cleared") is not None:
            _recognized = set(lens.diff(
                _spec["prev"], _spec["cleared"]).get("resolved", []))
            assert set(_sentinels) <= _recognized, (
                "tool-free lens %r: conformance_prev_digest sentinel(s) %s not resolved by "
                "diff() against a clean re-measure — the scenarios' 'resolved must be "
                "empty' checks would be vacuous" % (lens.name, sorted(_sentinels)))

    for scenario in gl.TOOL_FREE_CONFORMANCE_SCENARIOS:
        case = cases[scenario]
        config = case.get("config")
        prev_digest = case.get("prev_digest", dict(_PREV_DIGEST))
        with _tool_free_workspace(case) as workspace:
            ctx = {
                "cwd": workspace,
                "root": workspace,
                "config": config,
                "run": None,
                "prevDigest": prev_digest,
            }
            out = lens.collect(ctx)
        status, reason = gl.classify_collect(out)
        diff_out = lens.diff(prev_digest, out.get("digest"))
        resolved = diff_out.get("resolved", [])

        # (d) — when measurement stopped, diff() must resolve nothing.
        if status != "collected":
            assert resolved == [], (
                "tool-free lens %r scenario %r: stopped looking must not emit resolved ids"
                % (lens.name, scenario))

        if scenario == "unreadable-input":
            # (a) degrade OR carry — but never a false clean (never resolve unmeasured).
            if status == "collected":
                assert resolved == [], (
                    "tool-free lens %r unreadable-input: a carried collect must not "
                    "resolve prior findings it never re-measured (false clean)"
                    % (lens.name,))
                # B3(ii): a 'collected' carry must PRESERVE the prior digest — a dropped
                # (None) snapshot would be a false clean the resolved==[] check alone
                # cannot catch (diff(prev, None) is guarded to return no movement).
                assert out.get("digest") is not None, (
                    "tool-free lens %r unreadable-input: a 'collected' carry must preserve "
                    "a digest snapshot (no false clean via a dropped digest)"
                    % (lens.name,))
            else:
                assert status in ("not-collected", "partial"), (
                    "tool-free lens %r unreadable-input: got %r"
                    % (lens.name, status))
                assert isinstance(reason, str) and reason.strip(), (
                    "tool-free lens %r unreadable-input: degrade requires a reason"
                    % (lens.name,))
        elif scenario == "all-inputs-unavailable":
            # (b) nothing to measure must degrade with a non-empty reason.
            assert status in ("not-collected", "partial"), (
                "tool-free lens %r all-inputs-unavailable: must degrade, got %r"
                % (lens.name, status))
            assert isinstance(reason, str) and reason.strip(), (
                "tool-free lens %r all-inputs-unavailable: degrade requires a reason"
                % (lens.name,))
        elif scenario == "partial-carry-forward":
            # (c) a partial result must preserve the prior digest.
            assert status == "partial", (
                "tool-free lens %r partial-carry-forward: must be partial, got %r"
                % (lens.name, status))
            assert isinstance(reason, str) and reason.strip(), (
                "tool-free lens %r partial-carry-forward: partial requires a reason"
                % (lens.name,))
            assert resolved == [], (
                "tool-free lens %r partial-carry-forward: carry-forward must preserve "
                "the prior digest (diff() resolved nothing)" % (lens.name,))


def assert_lens_conformance(lens, cwd="/tmp", root="/tmp"):
    """Drive the conformance scenarios for ``lens``; raise AssertionError on any gap.

    Tool-using lenses (the default) route every tool invocation through ctx["run"] /
    guardian_collect.run_tool — a lens that shells out directly cannot be
    conformance-verified. A lens that sets ``uses_external_tools = False`` is driven
    through the tool-free path instead (TOOL_FREE_CONFORMANCE_SCENARIOS + no-spawn proof).
    """
    roster = set(gl.REQUIRED_CONFORMANCE_SCENARIOS)
    assert _HARNESS_OWNED | _LENS_SUPPLIED == roster, (
        "harness partition must cover every REQUIRED_CONFORMANCE_SCENARIOS member")
    assert not (_HARNESS_OWNED & _LENS_SUPPLIED), (
        "harness-owned and lens-supplied scenario sets must not overlap")

    if getattr(lens, "uses_external_tools", True) is False:
        _assert_tool_free_conformance(lens)
        return

    cases = lens.conformance_cases()
    missing = _LENS_SUPPLIED - set(cases.keys())
    assert not missing, (
        "lens %r missing conformance scenarios: %s"
        % (lens.name, sorted(missing)))

    for scenario in gl.REQUIRED_CONFORMANCE_SCENARIOS:
        with _scenario_workspace(lens, cwd, root) as (scn_cwd, scn_root):
            if scenario in _HARNESS_OWNED:
                run_stub, call_counter = _counting_run(_HARNESS_RUN_BUILDERS[scenario])
                config = None
                prev_digest = dict(_PREV_DIGEST)
                out, status, reason = _run_conformance_probe(
                    lens, scenario, run_stub, call_counter, config, prev_digest,
                    scn_cwd, scn_root)

                assert status in ("not-collected", "partial"), (
                    "lens %r scenario %r: expected not-collected or partial, got %r"
                    % (lens.name, scenario, status))
                # Belt-and-suspenders — negatively proven one layer down by
                # guardian_lens.classify_collect (see test_guardian_lens.py).
                assert isinstance(reason, str) and reason.strip(), (
                    "lens %r scenario %r: degraded collect requires non-empty reason"
                    % (lens.name, scenario))
                # B3(iii): assert the lens ITSELF put a non-empty reason in out["reason"],
                # not that classify_collect synthesized one downstream — the honest reason
                # is the lens's own, and a lens returning a degraded status with no reason
                # of its own must be caught here.
                assert isinstance(out.get("reason"), str) and out["reason"].strip(), (
                    "lens %r scenario %r: a degraded collect must itself carry a non-empty "
                    "out['reason'] (not lean on classify_collect to synthesize one)"
                    % (lens.name, scenario))
                if status == "not-collected":
                    assert out.get("digest") is None, (
                        "lens %r scenario %r: not-collected must not overwrite digest"
                        % (lens.name, scenario))

                if status != "collected":
                    diff_out = lens.diff(prev_digest, out.get("digest"))
                    assert diff_out.get("resolved", []) == [], (
                        "lens %r scenario %r: stopped looking must not emit resolved ids"
                        % (lens.name, scenario))

            elif scenario in _LENS_SUPPLIED:
                case = cases[scenario]
                config = case.get("config")
                prev_spec = _conformance_prev_spec(lens, case)
                prev_digest = prev_spec["prev"]

                # Clean probe — per-argv[0] dispatch so co-firing collectors get clean
                # payloads and the declared clean exit must be an ok exit.
                run_stub, call_counter = _counting_run(
                    _dispatch_run_body(case, "clean"))
                out, status, reason = _run_conformance_probe(
                    lens, scenario, run_stub, call_counter, config, prev_digest,
                    scn_cwd, scn_root)
                assert status == "collected", (
                    "lens %r scenario %r: clean probe must collect "
                    "(declared clean exit must be an ok exit)" % (lens.name, scenario))

                # Non-vacuity (B2): prove the prior digest's sentinel is a finding this
                # lens's diff() actually tracks — it must RESOLVE against a clean
                # re-measure — so the findings-probe "resolved must be empty" below is a
                # real check, not trivially true.
                if prev_spec["sentinelIds"]:
                    recognized = set(lens.diff(
                        prev_digest, prev_spec["cleared"]).get("resolved", []))
                    assert set(prev_spec["sentinelIds"]) <= recognized, (
                        "lens %r scenario %r: conformance_prev_digest sentinel(s) %s "
                        "not resolved by diff() against a clean re-measure — the "
                        "findings-probe honesty check would be vacuous"
                        % (lens.name, scenario, sorted(prev_spec["sentinelIds"])))

                # Findings probe — honesty invariant at the declared findings exit; ONLY
                # the targeted collector gets the findings payload.
                run_stub, call_counter = _counting_run(
                    _dispatch_run_body(case, "findings"))
                out, status, reason = _run_conformance_probe(
                    lens, scenario, run_stub, call_counter, config, prev_digest,
                    scn_cwd, scn_root)
                assert status in ("not-collected", "partial"), (
                    "lens %r reported-nonzero-parsed-zero: a tool that reported "
                    "problems with zero parsed candidates must degrade (never read "
                    "as collected)" % (lens.name,))

                if status != "collected":
                    diff_out = lens.diff(prev_digest, out.get("digest"))
                    assert diff_out.get("resolved", []) == [], (
                        "lens %r scenario %r: stopped looking must not emit resolved ids "
                        "(non-vacuous: the sentinel above IS resolvable by this diff)"
                        % (lens.name, scenario))

            else:
                raise AssertionError(
                    "scenario %r is in neither harness-owned nor lens-supplied partition"
                    % (scenario,))


class CompliantFakeLens(object):
    """Conformance-positive fake — routes collect through guardian_collect.run_tool."""

    name = "compliant-fake"
    collector_version = "0.0.0-conformance"
    cost = {"collectorSeconds": 0.01, "note": "conformance compliant fake"}
    required_facts = ()
    validation_guidance = "Validate conformance fake candidates."
    consequence_template = "Conformance fake consequence."

    def conformance_cases(self):
        return {
            "reported-nonzero-parsed-zero": {
                "stdout": _REPORTED_NONZERO_STDOUT,
                "clean_stdout": _CLEAN_STDOUT,
                "exit": 0,
                "config": None,
                "prev_digest": dict(_PREV_DIGEST),
            },
        }

    def collect(self, ctx):
        result = gc.run_tool(["conformance-tool"], ctx=ctx, cwd=ctx.get("cwd"))
        if not result["ok"]:
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected(result["reason"]),
            }

        stdout = (result.get("stdout") or "").strip()
        if not stdout:
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected("tool produced empty findings output"),
            }

        try:
            parsed = json.loads(stdout)
        except (ValueError, TypeError):
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected("unparseable tool output"),
            }

        if isinstance(parsed, dict) and parsed.get("reported_findings") and not parsed.get("findings"):
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected(
                    "tool reported findings but normalization yielded zero candidates"),
            }

        findings = parsed if isinstance(parsed, list) else parsed.get("findings", [])
        candidates = [
            {"id": item["id"]}
            for item in findings
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        digest = {"v": 1, "ids": [c["id"] for c in candidates]}
        return {
            "candidates": candidates,
            "digest": digest,
            **gc.collected(),
        }

    def diff(self, prev_digest, cur_digest):
        if cur_digest is None:
            return {"new": [], "worsened": [], "resolved": []}
        prev_ids = set((prev_digest or {}).get("ids", []))
        cur_ids = set(cur_digest.get("ids", []))
        return {
            "new": sorted(cur_ids - prev_ids),
            "worsened": [],
            "resolved": sorted(prev_ids - cur_ids),
        }

    def red_lines(self, candidates):
        return []

    def degrade(self, reason):
        return {"lens": self.name, "degraded": True, "reason": reason}


class AliasedScenariosFake(CompliantFakeLens):
    """Ignores ctx['run'] — caught by invocation proof before status assertions."""

    name = "aliased-scenarios"

    def collect(self, ctx):
        return {
            "candidates": [],
            "digest": {"v": 1, "ids": []},
            **gc.collected(),
        }


class MissingReportedNonzeroFake(CompliantFakeLens):
    name = "missing-reported-nonzero"

    def conformance_cases(self):
        return {}


class OkExitsThreeFake(CompliantFakeLens):
    """Findings-success exit is 3 — certifiable under the two-probe harness."""

    name = "ok-exits-three"

    def conformance_cases(self):
        return {
            "reported-nonzero-parsed-zero": {
                "stdout": _REPORTED_NONZERO_STDOUT,
                "clean_stdout": _CLEAN_STDOUT,
                "exit": 3,
            },
        }

    def collect(self, ctx):
        result = gc.run_tool(
            ["conformance-tool"], ctx=ctx, cwd=ctx.get("cwd"), ok_exits=(3,))
        if not result["ok"]:
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected(result["reason"]),
            }

        stdout = (result.get("stdout") or "").strip()
        if not stdout:
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected("tool produced empty findings output"),
            }

        try:
            parsed = json.loads(stdout)
        except (ValueError, TypeError):
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected("unparseable tool output"),
            }

        if isinstance(parsed, dict) and parsed.get("reported_findings") and not parsed.get("findings"):
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected(
                    "tool reported findings but normalization yielded zero candidates"),
            }

        findings = parsed if isinstance(parsed, list) else parsed.get("findings", [])
        candidates = [
            {"id": item["id"]}
            for item in findings
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        digest = {"v": 1, "ids": [c["id"] for c in candidates]}
        return {
            "candidates": candidates,
            "digest": digest,
            **gc.collected(),
        }


class DodgeExitFake(CompliantFakeLens):
    """Declares a non-ok exit to dodge the parser — caught by the clean probe."""

    name = "dodge-exit"

    def conformance_cases(self):
        return {
            "reported-nonzero-parsed-zero": {
                "stdout": _REPORTED_NONZERO_STDOUT,
                "clean_stdout": _CLEAN_STDOUT,
                "exit": 9,
            },
        }


class SilentCleanFake(CompliantFakeLens):
    name = "silent-clean"

    def conformance_cases(self):
        return {
            "reported-nonzero-parsed-zero": {
                "stdout": _REPORTED_NONZERO_STDOUT,
                "clean_stdout": _CLEAN_STDOUT,
                "exit": 0,
            },
        }

    def collect(self, ctx):
        result = gc.run_tool(["conformance-tool"], ctx=ctx, cwd=ctx.get("cwd"))
        stdout = (result.get("stdout") or "").strip()
        if stdout == _REPORTED_NONZERO_STDOUT:
            return {
                "candidates": [],
                "digest": {"v": 1},
                "status": "collected",
            }
        return super().collect(ctx)


class ResolvedOnStopFake(CompliantFakeLens):
    name = "resolved-on-stop"

    def diff(self, prev_digest, cur_digest):
        if cur_digest is None and prev_digest is not None:
            return {"new": [], "worsened": [], "resolved": ["x"]}
        return super().diff(prev_digest, cur_digest)


class CollectedOnDegradedFake(CompliantFakeLens):
    name = "collected-on-degraded"

    def collect(self, ctx):
        result = gc.run_tool(["conformance-tool"], ctx=ctx, cwd=ctx.get("cwd"))
        reason = result.get("reason") or ""
        if "timed out" in reason:
            return {
                "candidates": [{"id": "bogus"}],
                "digest": {"v": 1},
                "status": "collected",
            }
        return super().collect(ctx)


class DigestOnNotCollectedFake(CompliantFakeLens):
    name = "digest-on-not-collected"

    def collect(self, ctx):
        result = gc.run_tool(["conformance-tool"], ctx=ctx, cwd=ctx.get("cwd"))
        if not result["ok"]:
            return {
                "candidates": [],
                "digest": {"v": 9},
                "status": "not-collected",
                "reason": "x",
            }
        return super().collect(ctx)


class InvokeButIgnoreFake(CompliantFakeLens):
    """Calls ctx['run'] but ignores the outcome — caught by degraded-status assertion."""

    name = "invoke-but-ignore"

    def collect(self, ctx):
        gc.run_tool(["conformance-tool"], ctx=ctx, cwd=ctx.get("cwd"))
        return {
            "candidates": [],
            "digest": {"v": 1, "ids": []},
            **gc.collected(),
        }


def test_compliant_fake_passes():
    assert_lens_conformance(CompliantFakeLens())


def test_ok_exits_three_fake_passes():
    assert_lens_conformance(OkExitsThreeFake())


def test_dodge_exit_fake_fails():
    with pytest.raises(AssertionError, match="clean probe must collect"):
        assert_lens_conformance(DodgeExitFake())


def test_aliased_scenarios_fake_fails():
    with pytest.raises(AssertionError, match="never invoked"):
        assert_lens_conformance(AliasedScenariosFake())


def test_missing_reported_nonzero_fake_fails():
    with pytest.raises(AssertionError, match="reported-nonzero-parsed-zero"):
        assert_lens_conformance(MissingReportedNonzeroFake())


def test_silent_clean_fake_fails():
    with pytest.raises(AssertionError, match="must degrade \\(never read as collected\\)"):
        assert_lens_conformance(SilentCleanFake())


def test_resolved_on_stop_fake_fails():
    with pytest.raises(AssertionError, match="resolved"):
        assert_lens_conformance(ResolvedOnStopFake())


def test_collected_on_degraded_fake_fails():
    # Non-empty-reason invariant is enforced + negatively proven one layer down by
    # guardian_lens.classify_collect (see test_guardian_lens.py).
    with pytest.raises(AssertionError, match="not-collected or partial"):
        assert_lens_conformance(CollectedOnDegradedFake())


def test_digest_on_not_collected_fake_fails():
    with pytest.raises(AssertionError, match="overwrite digest"):
        assert_lens_conformance(DigestOnNotCollectedFake())


def test_invoke_but_ignore_fake_fails():
    with pytest.raises(AssertionError, match="not-collected or partial"):
        assert_lens_conformance(InvokeButIgnoreFake())


# --- item 1: optional clean_exit (dual-success-exit tools) ------------------------

def _parse_conformance_findings(result):
    """Shared normalization for the fakes that route through gc.run_tool."""
    if not result["ok"]:
        return {"candidates": [], "digest": None, **gc.not_collected(result["reason"])}
    stdout = (result.get("stdout") or "").strip()
    if not stdout:
        return {
            "candidates": [], "digest": None,
            **gc.not_collected("tool produced empty findings output"),
        }
    try:
        parsed = json.loads(stdout)
    except (ValueError, TypeError):
        return {
            "candidates": [], "digest": None,
            **gc.not_collected("unparseable tool output"),
        }
    if isinstance(parsed, dict) and parsed.get("reported_findings") and not parsed.get("findings"):
        return {
            "candidates": [], "digest": None,
            **gc.not_collected(
                "tool reported findings but normalization yielded zero candidates"),
        }
    findings = parsed if isinstance(parsed, list) else parsed.get("findings", [])
    candidates = [
        {"id": item["id"]}
        for item in findings
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    digest = {"v": 1, "ids": [c["id"] for c in candidates]}
    return {"candidates": candidates, "digest": digest, **gc.collected()}


class DualExitFake(CompliantFakeLens):
    """npm-audit-style dual success exits: 0 = clean, 1 = findings — both are ok exits.

    The clean probe runs at ``clean_exit`` (0) and the findings probe at ``exit`` (1);
    without ``clean_exit`` the harness would run the clean probe at exit 1 and a lens with
    ok_exits=(0, 1) could not distinguish clean from findings.
    """

    name = "dual-exit"

    def conformance_cases(self):
        return {
            "reported-nonzero-parsed-zero": {
                "stdout": _REPORTED_NONZERO_STDOUT,
                "clean_stdout": _CLEAN_STDOUT,
                "exit": 1,
                "clean_exit": 0,
            },
        }

    def collect(self, ctx):
        result = gc.run_tool(
            ["conformance-tool"], ctx=ctx, cwd=ctx.get("cwd"), ok_exits=(0, 1))
        return _parse_conformance_findings(result)


def test_dual_exit_fake_passes():
    """A lens declaring exit=1, clean_exit=0 passes the two-probe harness."""
    assert_lens_conformance(DualExitFake())


def test_default_single_exit_fake_still_passes():
    """A case with no clean_exit keeps the byte-for-byte single-exit behavior."""
    assert_lens_conformance(CompliantFakeLens())


# --- item 2: per-lens fixture files (manifest-gated lenses) -----------------------

_MANIFEST_NAME = "guardian-conformance.manifest"  # stands in for package.json/requirements.txt


class ManifestGatedFake(CompliantFakeLens):
    """Reaches its tool only when a manifest file is present in ctx["cwd"].

    At the harness default (/tmp) the manifest is absent, so collect() degrades WITHOUT
    invoking ctx["run"] and trips the ``ctx['run'] never invoked`` guard — unless the lens
    declares conformance_fixture() so the harness writes the manifest into a temp workspace.
    """

    name = "manifest-gated"

    def conformance_fixture(self):
        return {_MANIFEST_NAME: '{"name": "fixture"}\n'}

    def collect(self, ctx):
        cwd = ctx.get("cwd") or ""
        if not os.path.isfile(os.path.join(cwd, _MANIFEST_NAME)):
            return {
                "candidates": [], "digest": None,
                **gc.not_collected("no %s manifest present — lens gated" % _MANIFEST_NAME),
            }
        return super().collect(ctx)


class ManifestGatedNoFixtureFake(ManifestGatedFake):
    """Same gate, but no conformance_fixture — must trip the never-invoked guard."""

    name = "manifest-gated-no-fixture"
    conformance_fixture = None


def test_manifest_gated_fake_passes_with_fixture():
    assert_lens_conformance(ManifestGatedFake())


def test_manifest_gated_fake_without_fixture_trips_never_invoked():
    with pytest.raises(AssertionError, match="never invoked"):
        assert_lens_conformance(ManifestGatedNoFixtureFake())


# --- item 3: tool-free (stdlib-only) lens mode ------------------------------------

_TOOL_FREE_PREV = {"v": 1, "ids": ["prior-1"]}


class ToolFreeFake(object):
    """A genuinely stdlib-only lens: reads files, spawns nothing.

    Inputs live under docs/. An input that exists-but-cannot-be-read degrades; a missing
    input degrades; a partially-readable run carries the prior digest forward.
    """

    name = "tool-free-fake"
    collector_version = "0.0.0-tool-free"
    cost = {"collectorSeconds": 0.01, "note": "tool-free conformance fake"}
    required_facts = ()
    validation_guidance = "Validate tool-free fake candidates."
    consequence_template = "Tool-free fake consequence."
    uses_external_tools = False

    _PRIMARY = "docs/guide.md"
    _SECONDARY = "docs/other.md"

    def conformance_fixture(self):
        return {self._PRIMARY: "# Guide\nsome docs\n"}

    def conformance_cases(self):
        return {
            "unreadable-input": {
                "fixture": {},
                "unreadable": [self._PRIMARY],
                "prev_digest": dict(_TOOL_FREE_PREV),
            },
            "all-inputs-unavailable": {
                "fixture": {},
                "prev_digest": dict(_TOOL_FREE_PREV),
            },
            "partial-carry-forward": {
                "fixture": {self._PRIMARY: "# Guide\nsome docs\n"},
                "unreadable": [self._SECONDARY],
                "prev_digest": dict(_TOOL_FREE_PREV),
            },
        }

    def collect(self, ctx):
        cwd = ctx.get("cwd") or ""
        prev = ctx.get("prevDigest")
        primary = os.path.join(cwd, self._PRIMARY)
        secondary = os.path.join(cwd, self._SECONDARY)

        if not os.path.exists(primary):
            return {
                "candidates": [], "digest": None,
                **gc.not_collected("no docs inputs present"),
            }
        try:
            with open(primary, encoding="utf-8") as fh:
                fh.read()
        except OSError:
            return {
                "candidates": [], "digest": None,
                **gc.not_collected("primary docs input unreadable: %s" % self._PRIMARY),
            }

        if os.path.exists(secondary):
            try:
                with open(secondary, encoding="utf-8") as fh:
                    fh.read()
            except OSError:
                # Could not read a secondary input — carry the prior digest forward so a
                # partial run never drops (resolves) findings it did not re-measure.
                return {
                    "candidates": [], "digest": dict(prev or {}),
                    **gc.partial("secondary docs input unreadable — carried prior digest"),
                }

        digest = {"v": 1, "ids": ["doc-guide"]}
        return {"candidates": [{"id": "doc-guide"}], "digest": digest, **gc.collected()}

    def diff(self, prev_digest, cur_digest):
        if cur_digest is None:
            return {"new": [], "worsened": [], "resolved": []}
        prev_ids = set((prev_digest or {}).get("ids", []))
        cur_ids = set(cur_digest.get("ids", []))
        return {
            "new": sorted(cur_ids - prev_ids),
            "worsened": [],
            "resolved": sorted(prev_ids - cur_ids),
        }

    def red_lines(self, candidates):
        return []

    def degrade(self, reason):
        return {"lens": self.name, "degraded": True, "reason": reason}


class CheatingToolFreeFake(ToolFreeFake):
    """Declares tool-free but secretly routes through gc.run_tool — must be rejected.

    Wraps the spawn in ``except Exception`` to prove the no-spawn guard survives a lens
    that swallows ordinary exceptions (the guard raises a BaseException the lens cannot
    catch).
    """

    name = "cheating-tool-free"

    def collect(self, ctx):
        try:
            gc.run_tool(["sneaky-tool"], ctx=ctx, cwd=ctx.get("cwd"))
        except Exception:  # noqa: BLE001 — deliberately swallow to test the guard
            pass
        return super().collect(ctx)


class IndirectSpawnToolFreeFake(ToolFreeFake):
    """Declares tool-free but spawns directly via subprocess — must be rejected."""

    name = "indirect-spawn-tool-free"

    def collect(self, ctx):
        try:
            subprocess.run(["true"], capture_output=True)
        except Exception:  # noqa: BLE001
            pass
        return super().collect(ctx)


def test_tool_free_fake_passes():
    assert_lens_conformance(ToolFreeFake())


def test_cheating_tool_free_fake_rejected():
    with pytest.raises(AssertionError, match="spawn primitive"):
        assert_lens_conformance(CheatingToolFreeFake())


def test_indirect_spawn_tool_free_fake_rejected():
    with pytest.raises(AssertionError, match="spawn primitive"):
        assert_lens_conformance(IndirectSpawnToolFreeFake())


def test_tool_free_fake_actually_spawns_nothing():
    """Positive control: the honest tool-free fake completes under the no-spawn proof."""
    _assert_no_indirect_spawn(ToolFreeFake())


def _conformance_lens_ids(lens):
    return getattr(lens, "name", repr(lens))


@pytest.mark.parametrize(
    "lens",
    list(gl.registered_lenses()) + [CompliantFakeLens()],
    ids=_conformance_lens_ids,
)
def test_registered_lenses_conformance(lens):
    assert_lens_conformance(lens)


_COMPOSE_MARKER = "GUARDIAN_COMPOSE_RCE_MARKER"


def _make_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").mkdir()
    return str(path)


def _write_executable(path, body):
    path = str(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def test_run_tool_seam_composition_conformance_and_production_rejection(
        tmp_path, monkeypatch):
    """DoD composition probe — the mandated run_tool path is BOTH conformance-compatible
    AND hardened in production, proven together in one test.

    (i)  ctx["run"] injected → the same lens PASSES the full conformance harness.
    (ii) ctx["run"] absent (production) → a repo-local binary named like the lens's
         collector is REJECTED, not executed, and the lens degrades.
    """
    lens = CompliantFakeLens()

    # (i) Conformance-compatible via the injected ctx["run"] seam.
    assert_lens_conformance(lens)

    # (ii) Production mode (no ctx["run"]) against a planted repo-local binary. The
    # CompliantFakeLens collects with gc.run_tool(["conformance-tool"], ...), so plant
    # a repo-local "conformance-tool" on PATH with a side-effect it would leave if run.
    repo = _make_repo(tmp_path / "repo")
    marker = os.path.join(repo, _COMPOSE_MARKER)
    binp = _write_executable(
        tmp_path / "repo" / "bin" / "conformance-tool",
        "#!%s\nopen(%r, 'w').write('x')\n" % (sys.executable, marker))
    monkeypatch.setenv("PATH", os.path.dirname(binp))

    ctx = {  # deliberately NO "run" key — exercises the production spawn path.
        "cwd": repo,
        "root": repo,
        "config": None,
        "prevDigest": None,
    }
    out = lens.collect(ctx)
    status, reason = gl.classify_collect(out)

    assert status == "not-collected", (status, reason)
    assert isinstance(reason, str) and reason.strip()
    # The repo-local executable must NOT have run.
    assert not os.path.exists(marker)
    assert os.path.isfile(binp)
