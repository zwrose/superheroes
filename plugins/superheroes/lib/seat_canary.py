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

import engine_adapter  # noqa: E402
import engine_dispatch  # noqa: E402

PLANT_MARKER = "check_receipt"

CANARY_FIXTURE_PROMPT = """\
You are the security reviewer seat for a one-shot dispatched review.

Respond on stdout with a single JSON object (no prose outside it) matching this contract:
{"findings": [{"id": "...", "severity": "...", "file": "...", "title": "...", "body": "..."}],
 "investigated": ["relative/path.py", ...]}
The investigated array is required when you have no findings: list every repo-relative path you
read to ground your review.

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
"""


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
    # True by echoing the symbol from the fixture. Recorded for humans reading a probe result;
    # deliberately never a branch anywhere (do not gate on this field).
    for f in findings or []:
        file_s, title_s, body_s = _finding_fields(f)
        if PLANT_MARKER in file_s or PLANT_MARKER in title_s or PLANT_MARKER in body_s:
            return True
    return False


def _is_non_terminal(res):
    return res.get("terminal") is False


def _map_outcome(res):
    if _is_non_terminal(res):
        reason = res.get("reason")
        if reason == "running":
            return "running", ""
        raw = reason or res.get("detail") or "unknown"
        raise ValueError("non-terminal dispatch with unrecognised reason: %s" % raw)

    if res.get("ok") is True:
        return "ok", ""
    reason = res.get("reason")
    if reason == engine_adapter.REVIEW_FORFEIT_VACUOUS:
        return engine_adapter.REVIEW_FORFEIT_VACUOUS, (res.get("disclosure") or "vacuous-forfeit")
    if reason == "forfeited":
        return "forfeited", (res.get("disclosure") or "forfeited")
    if reason == "unrunnable":
        detail = res.get("detail") or reason or "unrunnable"
        return "unrunnable", "not-dispatched: %s" % detail
    raw = reason or res.get("detail") or "unknown"
    return "unrunnable", "not-dispatched: %s" % raw


def _unmeasured_evidence():
    return {
        "findings": None,
        "investigated": None,
        "tokens": None,
        "toolCalls": None,
        "stdoutBytes": None,
        "wallSeconds": None,
    }


def _engaged_from_dispatch(res):
    findings = res.get("findings") or []
    if findings:
        return True
    investigated = res.get("investigated") or []
    if investigated:
        return True
    eng = _safe_engagement(res.get("engagement"))
    # Token spend cannot separate engaged from vacuous, and an absolute floor would classify backwards.
    # Measured 2026-07-26 on codex 0.144.1 in this repo: a genuinely engaged clean review that read
    # repo files spent 2,460 tokens, while the field's vacuous seat (issue #666) spent ~23,000 — ten
    # times more — because prompt ingestion dominates. Engaged runs here ranged 2,460 → 34,857 tokens.
    # Wall time is equally unusable: an engaged dispatch returned a Critical finding in 8 seconds.
    # Only *actions* count — findings produced, files provably read, tools invoked.
    tool_calls = eng.get("toolCalls")
    if tool_calls is not None and tool_calls >= 1:
        return True
    return False


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


def run_canary(engine, *, engine_model, effort, repo_root, dispatch=None, timeout=300,
               run_dir=None, max_wait=None):
    """Dispatch the planted-defect fixture through the real seat path and score ENGAGEMENT.

    By default blocks until the dispatch result is terminal (``max_wait`` omitted). With an
    explicit ``max_wait``, dispatch may return a non-terminal ``running`` outcome for continuation.

    ``timeout`` bounds the first dispatch attempt only. On retry the runner floors its wait at
    ``RETRY_MIN_TIMEOUT`` (900 s), so worst-case wall time for a blocking run is ``timeout + 900``
    seconds.
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
            dispatch_kw = {
                "model": None,
                "effort": effort,
                "engine_model": engine_model,
                "prompt_path": prompt_path,
                "repo_root": repo_root,
                "timeout": timeout,
            }
            if run_dir is not None:
                dispatch_kw["run_dir"] = run_dir
            if max_wait is not None:
                dispatch_kw["max_wait"] = max_wait
            res = dispatch(engine, **dispatch_kw)
        except Exception as exc:
            return {
                "engine": engine,
                "model": engine_model,
                "outcome": "unrunnable",
                "terminal": True,
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

        if _is_non_terminal(res):
            outcome, _ = _map_outcome(res)
            return {
                "engine": engine,
                "model": engine_model,
                "outcome": outcome,
                "terminal": False,
                "engaged": None,
                "evidence": _unmeasured_evidence(),
                "detectedPlant": False,
                "detail": "",
                "runDir": res.get("runDir"),
                "resume": res.get("resume"),
            }

        outcome, detail_hint = _map_outcome(res)
        if outcome == "unrunnable":
            engaged = False
        else:
            engaged = _engaged_from_dispatch(res)

        detail = ""
        if not engaged:
            if outcome == "unrunnable":
                detail = detail_hint
            elif outcome == engine_adapter.REVIEW_FORFEIT_VACUOUS:
                detail = detail_hint or "vacuous-forfeit"
            elif outcome == "forfeited":
                detail = detail_hint or "forfeited"
            elif outcome == "ok":
                detail = "no-engagement-evidence"

        findings = res.get("findings") or []
        # Record detection only; never branch on it (PR #667 round-1 probe and codex seam probe both
        # missed the planted defect while demonstrably alive).
        detected_plant = _detected_plant(findings)

        return {
            "engine": engine,
            "model": engine_model,
            "outcome": outcome,
            "terminal": True,
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
    p.add_argument("--effort", required=True)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--run-dir", default=None)
    p.add_argument("--max-wait", type=int, default=None)
    args = ap.parse_args(argv)
    res = run_canary(
        args.engine,
        engine_model=args.engine_model,
        effort=args.effort,
        repo_root=args.repo_root,
        timeout=args.timeout,
        run_dir=args.run_dir,
        max_wait=args.max_wait,
    )
    sys.stdout.write(json.dumps(res) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
