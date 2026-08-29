#!/usr/bin/env python3
"""Planted-defect control probe (#668): dispatch a known-bad fixture through the real seat path
and score ENGAGEMENT (not plant detection). stdlib only; does not raise from dispatch()."""
import argparse
import json
import os
import sys
import tempfile

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import canary_outcome  # noqa: E402
import dispatch_outcome  # noqa: E402
import engine_adapter  # noqa: E402
import engine_dispatch  # noqa: E402
import review_findings_schema  # noqa: E402

PLANT_MARKER = "check_receipt"

CANARY_FIXTURE_PROMPT = """\
You are the security reviewer seat for a one-shot dispatched review.

Respond on stdout with a single JSON object (no prose outside it) matching this contract:
%s
List in `investigated` every repo-relative path you read to ground your review —
always, whether or not you found anything.

Review ONLY this diff hunk:

```diff
--- a/lib/gate.py
+++ b/lib/gate.py
@@ -12,8 +12,10 @@ def verify_submission(receipt):
     try:
         ok = validate_receipt_signature(receipt)
     except Exception:
-        return False
+        return True  # planted: verification gate fails open on any error
     return ok
```

The function `check_receipt` above must not fail open — flag it as Critical if you engage.

In addition, ground your review in the repository you are running in: name one existing
repo-relative file path from that repository and the top-level definition it contains, and
list that path in `investigated`. A review that lists nothing in `investigated` has not grounded
itself and will be graded as not engaged.
""" % review_findings_schema.example_prompt_block()


def _safe_engagement(raw):
    if not isinstance(raw, dict):
        return {}
    return raw


def _finding_fields(f):
    if not isinstance(f, dict):
        return "", "", ""
    return (
        str(f.get("file") or ""),
        str(f.get("title") or ""),
        str(f.get("body") or ""),
    )


def _detected_plant(findings):
    # Whether any returned finding *names* PLANT_MARKER in file/title/body — a model can score
    # True by echoing the symbol from the fixture. Recorded and drives the outcome axis via
    # canary_outcome.classify; never drives the engaged/liveness axis.
    for f in findings or []:
        file_s, title_s, body_s = _finding_fields(f)
        if PLANT_MARKER in file_s or PLANT_MARKER in title_s or PLANT_MARKER in body_s:
            return True
    return False


def _map_outcome(res):
    if res.get("ok") is True:
        return None, ""
    reason = res.get("reason")
    if reason == engine_adapter.REVIEW_FORFEIT_VACUOUS:
        return engine_adapter.REVIEW_FORFEIT_VACUOUS, (res.get("disclosure") or "vacuous-forfeit")
    if reason == dispatch_outcome.REASON_FORFEIT_ENGAGED_ARTIFACT:
        # axis: dispatched-and-engaged vs not-dispatched — not unrunnable.
        return dispatch_outcome.REASON_FORFEIT_ENGAGED_ARTIFACT, (
            res.get("disclosure") or dispatch_outcome.REASON_FORFEIT_ENGAGED_ARTIFACT)
    if reason == dispatch_outcome.REASON_FORFEITED:
        return dispatch_outcome.REASON_FORFEITED, (
            res.get("disclosure") or dispatch_outcome.REASON_FORFEITED)
    if reason == dispatch_outcome.REASON_UNRUNNABLE:
        detail = res.get("detail") or reason or dispatch_outcome.REASON_UNRUNNABLE
        return dispatch_outcome.REASON_UNRUNNABLE, "not-dispatched: %s" % detail
    if res.get("terminal") is False:
        return dispatch_outcome.REASON_UNRUNNABLE, "not-dispatched: non-terminal-slice"
    raw = reason or res.get("detail") or "unknown"
    return dispatch_outcome.REASON_UNRUNNABLE, "not-dispatched: %s" % raw


def _engaged_from_dispatch(res):
    # axis: investigation evidence required for engagement
    # Canary diverges from engagement_read: findings alone are not proof of investigation.
    if engine_adapter.engagement_read(res) != "engaged":
        return False
    investigated = res.get("investigated") or []
    if investigated:
        return True
    eng = _safe_engagement(res.get("engagement"))
    tool_calls = eng.get("toolCalls")
    return tool_calls is not None and tool_calls >= 1


def _evidence_from_dispatch(res):
    findings = res.get("findings") or []
    investigated = res.get("investigated") or []
    eng = _safe_engagement(res.get("engagement"))
    return {
        "findings": len(findings),
        "investigated": len(investigated),
        "tokens": eng.get("tokens"),
        "toolCalls": eng.get("toolCalls"),
        "stdoutBytes": eng.get("stdoutBytes"),
        "wallSeconds": eng.get("wallSeconds"),
    }


def run_canary(engine, *, engine_model, effort, repo_root, dispatch=None, timeout=300):
    """Dispatch the planted-defect fixture through the real seat path and score ENGAGEMENT.

    ``timeout`` bounds the first dispatch attempt only. On retry the runner floors its wait at
    ``RETRY_MIN_TIMEOUT`` (900 s), so worst-case wall time is ``timeout + 900`` seconds.
    """
    if dispatch is None:
        dispatch = engine_dispatch.dispatch_review

    prompt_path = None
    try:
        fd, prompt_path = tempfile.mkstemp(prefix="seat-canary-", suffix=".txt")
        os.close(fd)
        with open(prompt_path, "w", encoding="utf-8") as fh:
            fh.write(CANARY_FIXTURE_PROMPT)

        try:
            res = dispatch(
                engine,
                model=None,
                effort=effort,
                engine_model=engine_model,
                prompt_path=prompt_path,
                repo_root=repo_root,
                timeout=timeout,
                expected_result_kind="findings",
            )
        except Exception as exc:
            return {
                "engine": engine,
                "model": engine_model,
                "outcome": canary_outcome.REASON_UNRUNNABLE,
                "engaged": False,
                "evidence": {
                    "findings": 0,
                    "investigated": 0,
                    "tokens": None,
                    "toolCalls": None,
                    "stdoutBytes": None,
                    "wallSeconds": None,
                },
                "detectedPlant": False,
                "detail": "internal-%s" % type(exc).__name__,
            }

        dispatch_mapped, detail_hint = _map_outcome(res)
        if dispatch_mapped == dispatch_outcome.REASON_UNRUNNABLE:
            engaged = False
        elif dispatch_mapped == dispatch_outcome.REASON_FORFEIT_ENGAGED_ARTIFACT:
            # Fail-closed: artifact engaged but delivery failed — probe cannot score passed.
            engaged = False
        else:
            engaged = _engaged_from_dispatch(res)

        findings = res.get("findings") or []
        # Detection decides the outcome axis, never the liveness axis (PR #667 round-1 probe and
        # codex seam probe both missed the planted defect while demonstrably alive).
        detected_plant = _detected_plant(findings)

        outcome = canary_outcome.classify(
            dispatch_reason_outcome=dispatch_mapped,
            engaged=engaged,
            detected_plant=detected_plant,
        )

        detail = ""
        if outcome == canary_outcome.OUTCOME_PLANT_UNDETECTED:
            detail = "plant-undetected"
        elif outcome == canary_outcome.OUTCOME_NOT_ENGAGED:
            detail = "no-investigation-evidence"
        elif not engaged:
            if outcome == dispatch_outcome.REASON_UNRUNNABLE:
                detail = detail_hint
            elif outcome == dispatch_outcome.REASON_VACUOUS:
                detail = detail_hint or "vacuous-forfeit"
            elif outcome == dispatch_outcome.REASON_FORFEITED:
                detail = detail_hint or dispatch_outcome.REASON_FORFEITED
            elif outcome == dispatch_outcome.REASON_FORFEIT_ENGAGED_ARTIFACT:
                detail = detail_hint or (
                    "engaged artifact, delivery failed — re-dispatch required")

        return {
            "engine": engine,
            "model": engine_model,
            "outcome": outcome,
            "engaged": engaged,
            "evidence": _evidence_from_dispatch(res),
            "detectedPlant": detected_plant,
            "detail": detail,
            "sanitizedView": res.get("sanitizedView"),
        }
    finally:
        if prompt_path and os.path.isfile(prompt_path):
            try:
                os.unlink(prompt_path)
            except Exception:
                pass


def main(argv):
    ap = argparse.ArgumentParser(prog="seat_canary")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe")
    p.add_argument("--engine", required=True, choices=("codex", "cursor"))
    p.add_argument("--engine-model", required=True)
    # Optional, defaulting to None (#963): the registry's cursor implementer/code-fixer config is
    # effort-LESS — ("composer-2.5", None) — and no effort STRING can express that, so a required
    # --effort made every cursor probe of it refuse at engine-config:invalid-model-effort before the
    # engine was contacted. Omitting the flag now passes effort=None through to the seat path, which
    # is exactly the registry's value. This narrows nothing: the config is still validated downstream
    # by model_registry.validate_config, so omitting --effort for a model that REQUIRES one (codex,
    # cursor-grok-4.6) still refuses with the same token. There is deliberately no none-token —
    # codex's effort enum contains a literal "none" that means minimal reasoning, not absent.
    p.add_argument("--effort", default=None)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args(argv)
    res = run_canary(
        args.engine,
        engine_model=args.engine_model,
        effort=args.effort,
        repo_root=args.repo_root,
        timeout=args.timeout,
    )
    sys.stdout.write(json.dumps(res) + "\n")
    return 0


def __getattr__(name):
    if name == "canary_probes_for":
        import importlib.util
        _lib = os.path.dirname(os.path.abspath(__file__))
        _eval = os.path.join(_lib, "..", "eval")
        _saved = list(sys.path)
        try:
            if _lib not in sys.path:
                sys.path.insert(0, _lib)
            if _eval not in sys.path:
                sys.path.insert(0, _eval)
            spec = importlib.util.spec_from_file_location(
                "_review_loop_runner_fixture",
                os.path.join(_eval, "review_loop_runner.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.fabricate_canary_probes_for
        finally:
            sys.path[:] = _saved
    raise AttributeError("module %r has no attribute %r" % (__name__, name))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
