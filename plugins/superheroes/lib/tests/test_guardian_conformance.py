"""Per-lens conformance harness — honesty invariants every production lens must prove."""
import errno
import json
import subprocess

import guardian_collect as gc
import guardian_lens as gl
import pytest

_DEGRADED_SCENARIOS = frozenset((
    "missing-tool",
    "timeout",
    "nonzero-exit",
    "findings-empty-output",
    "unparseable",
))
_REPORTED_NONZERO_PARSED_ZERO = "reported-nonzero-parsed-zero"
_PREV_DIGEST = {"v": 1, "ids": ["prior-1"]}
_REPORTED_NONZERO_STDOUT = json.dumps({"reported_findings": 3, "findings": []})


def _ok_run(stdout_text, exit_code=0):
    def run(argv, **kwargs):
        class R(object):
            returncode = exit_code
            stdout = stdout_text
            stderr = ""
        return R()
    return run


def assert_lens_conformance(lens, cwd="/tmp", root="/tmp"):
    """Drive REQUIRED_CONFORMANCE_SCENARIOS for ``lens``; raise AssertionError on any gap."""
    cases = lens.conformance_cases()
    missing = set(gl.REQUIRED_CONFORMANCE_SCENARIOS) - set(cases.keys())
    assert not missing, (
        "lens %r missing conformance scenarios: %s"
        % (lens.name, sorted(missing)))

    for scenario in gl.REQUIRED_CONFORMANCE_SCENARIOS:
        case = cases[scenario]
        ctx = {
            "cwd": cwd,
            "root": root,
            "config": case.get("config"),
            "run": case["run"],
            "prevDigest": case.get("prev_digest"),
        }
        out = lens.collect(ctx)
        status, reason = gl.classify_collect(out)

        if scenario in _DEGRADED_SCENARIOS:
            assert status in ("not-collected", "partial"), (
                "lens %r scenario %r: expected not-collected or partial, got %r"
                % (lens.name, scenario, status))
            assert isinstance(reason, str) and reason.strip(), (
                "lens %r scenario %r: degraded collect requires non-empty reason"
                % (lens.name, scenario))
            if status == "not-collected":
                assert out.get("digest") is None, (
                    "lens %r scenario %r: not-collected must not overwrite digest"
                    % (lens.name, scenario))

        elif scenario == _REPORTED_NONZERO_PARSED_ZERO:
            assert not (
                status == "collected" and (out.get("candidates") or []) == []
            ), (
                "lens %r scenario %r: tool reported problems must not read as "
                "collected with zero candidates" % (lens.name, scenario))

        if status != "collected":
            diff_out = lens.diff(case.get("prev_digest"), out.get("digest"))
            assert diff_out.get("resolved", []) == [], (
                "lens %r scenario %r: stopped looking must not emit resolved ids"
                % (lens.name, scenario))


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
            "missing-tool": {
                "run": lambda argv, **kwargs: (_ for _ in ()).throw(
                    FileNotFoundError(errno.ENOENT, "conformance-tool")),
                "config": None,
                "prev_digest": dict(_PREV_DIGEST),
            },
            "timeout": {
                "run": lambda argv, **kwargs: (_ for _ in ()).throw(
                    subprocess.TimeoutExpired(cmd=argv, timeout=60)),
                "config": None,
                "prev_digest": dict(_PREV_DIGEST),
            },
            "nonzero-exit": {
                "run": _ok_run("", exit_code=2),
                "config": None,
                "prev_digest": dict(_PREV_DIGEST),
            },
            "findings-empty-output": {
                "run": _ok_run(""),
                "config": None,
                "prev_digest": dict(_PREV_DIGEST),
            },
            "unparseable": {
                "run": _ok_run("not-json{{{"),
                "config": None,
                "prev_digest": dict(_PREV_DIGEST),
            },
            "reported-nonzero-parsed-zero": {
                "run": _ok_run(_REPORTED_NONZERO_STDOUT),
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


class MissingCoverageFake(CompliantFakeLens):
    name = "missing-coverage"

    def conformance_cases(self):
        cases = super().conformance_cases()
        del cases["unparseable"]
        return cases


class SilentCleanFake(CompliantFakeLens):
    name = "silent-clean"

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


class EmptyReasonFake(CompliantFakeLens):
    name = "empty-reason"

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


def test_compliant_fake_passes():
    assert_lens_conformance(CompliantFakeLens())


def test_missing_coverage_fake_fails():
    with pytest.raises(AssertionError, match="unparseable"):
        assert_lens_conformance(MissingCoverageFake())


def test_silent_clean_fake_fails():
    with pytest.raises(AssertionError, match="reported problems"):
        assert_lens_conformance(SilentCleanFake())


def test_resolved_on_stop_fake_fails():
    with pytest.raises(AssertionError, match="resolved"):
        assert_lens_conformance(ResolvedOnStopFake())


def test_empty_reason_fake_fails():
    with pytest.raises(AssertionError, match="not-collected or partial"):
        assert_lens_conformance(EmptyReasonFake())


def _conformance_lens_ids(lens):
    return getattr(lens, "name", repr(lens))


@pytest.mark.parametrize(
    "lens",
    list(gl.registered_lenses()) + [CompliantFakeLens()],
    ids=_conformance_lens_ids,
)
def test_registered_lenses_conformance(lens):
    assert_lens_conformance(lens)
