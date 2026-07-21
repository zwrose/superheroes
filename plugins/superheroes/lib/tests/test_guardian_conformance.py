"""Per-lens conformance harness — honesty invariants every production lens must prove."""
import errno
import json
import subprocess

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


def assert_lens_conformance(lens, cwd="/tmp", root="/tmp"):
    """Drive REQUIRED_CONFORMANCE_SCENARIOS for ``lens``; raise AssertionError on any gap.

    The harness assumes every tool invocation routes through ctx["run"] /
    guardian_collect.run_tool — a lens that shells out directly cannot be
    conformance-verified.
    """
    roster = set(gl.REQUIRED_CONFORMANCE_SCENARIOS)
    assert _HARNESS_OWNED | _LENS_SUPPLIED == roster, (
        "harness partition must cover every REQUIRED_CONFORMANCE_SCENARIOS member")
    assert not (_HARNESS_OWNED & _LENS_SUPPLIED), (
        "harness-owned and lens-supplied scenario sets must not overlap")

    cases = lens.conformance_cases()
    missing = _LENS_SUPPLIED - set(cases.keys())
    assert not missing, (
        "lens %r missing conformance scenarios: %s"
        % (lens.name, sorted(missing)))

    for scenario in gl.REQUIRED_CONFORMANCE_SCENARIOS:
        if scenario in _HARNESS_OWNED:
            run_stub, call_counter = _counting_run(_HARNESS_RUN_BUILDERS[scenario])
            config = None
            prev_digest = dict(_PREV_DIGEST)
            out, status, reason = _run_conformance_probe(
                lens, scenario, run_stub, call_counter, config, prev_digest, cwd, root)

            assert status in ("not-collected", "partial"), (
                "lens %r scenario %r: expected not-collected or partial, got %r"
                % (lens.name, scenario, status))
            # Belt-and-suspenders — negatively proven one layer down by
            # guardian_lens.classify_collect (see test_guardian_lens.py).
            assert isinstance(reason, str) and reason.strip(), (
                "lens %r scenario %r: degraded collect requires non-empty reason"
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
            exit_code = case["exit"]
            config = case.get("config")
            prev_digest = case.get("prev_digest", dict(_PREV_DIGEST))

            # Clean probe — declared exit must be an ok exit for this lens.
            run_stub, call_counter = _counting_run(
                _lens_supplied_run_body(case["clean_stdout"], exit_code))
            out, status, reason = _run_conformance_probe(
                lens, scenario, run_stub, call_counter, config, prev_digest, cwd, root)
            assert status == "collected", (
                "lens %r scenario %r: clean probe must collect "
                "(declared exit must be an ok exit)" % (lens.name, scenario))

            # Findings probe — honesty invariant at the declared exit.
            run_stub, call_counter = _counting_run(
                _lens_supplied_run_body(case["stdout"], exit_code))
            out, status, reason = _run_conformance_probe(
                lens, scenario, run_stub, call_counter, config, prev_digest, cwd, root)
            assert not (
                status == "collected" and (out.get("candidates") or []) == []
            ), (
                "lens %r scenario %r: tool reported problems must not read as "
                "collected with zero candidates" % (lens.name, scenario))

            if status != "collected":
                diff_out = lens.diff(prev_digest, out.get("digest"))
                assert diff_out.get("resolved", []) == [], (
                    "lens %r scenario %r: stopped looking must not emit resolved ids"
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
    with pytest.raises(AssertionError, match="reported problems"):
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


def _conformance_lens_ids(lens):
    return getattr(lens, "name", repr(lens))


@pytest.mark.parametrize(
    "lens",
    list(gl.registered_lenses()) + [CompliantFakeLens()],
    ids=_conformance_lens_ids,
)
def test_registered_lenses_conformance(lens):
    assert_lens_conformance(lens)
