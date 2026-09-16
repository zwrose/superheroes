#!/usr/bin/env python3
"""Planted-defect control probe (#668): dispatch a known-bad fixture through the real seat path
and score two axes — engagement (requires investigation evidence in `investigated`) and plant
detection (whether the planted defect was named in findings). stdlib only; does not raise from dispatch()."""
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
import model_registry  # noqa: E402
import review_findings_schema  # noqa: E402
import seat_bundle  # noqa: E402
import seat_map  # noqa: E402

PLANT_MARKER = "verify_submission"

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

A Critical-severity fail-open was planted in the diff above — the error path returns a value
that permits the submission when it should not. Report it as Critical if you engage.

In addition, ground your review in the repository you are running in: name one existing
repo-relative file path from that repository and the top-level definition it contains, and
list that path in `investigated`. A review that lists nothing in `investigated` has not grounded
itself and will be graded as not engaged.
""" % review_findings_schema.example_prompt_block()


def _identity_refusal(reason, detail):
    return {
        "ok": False,
        "reason": reason,
        "detail": detail,
    }


def _resolve_canary_identity(seat_key, seat_config):
    """Derive the four-key dispatch seat from seat-map identity; refuse without a tier."""
    if not isinstance(seat_key, str) or not seat_key.strip():
        return _identity_refusal(
            "seat-identity-absent",
            "seat_canary requires --seat-key and seat config with tier from the seat map",
        )
    if not isinstance(seat_config, dict):
        return _identity_refusal(
            "seat-identity-absent",
            "seat_canary requires seat config dict with vendor, model, effort, and tier",
        )
    if "tier" not in seat_config:
        return _identity_refusal(
            "tier-absent",
            "seat config must carry tier (registry role name); seat key %r" % seat_key.strip(),
        )
    tier = seat_config.get("tier")
    if not isinstance(tier, str) or tier not in model_registry.roles():
        valid = ", ".join(model_registry.roles())
        return _identity_refusal(
            "unknown-tier",
            "tier %r is not a registry role; valid roles: %s" % (tier, valid),
        )
    seat_name = seat_key.strip()
    if seat_name not in seat_map.PANEL_ROSTER:
        valid = ", ".join(sorted(seat_map.PANEL_ROSTER))
        return _identity_refusal(
            "unknown-seat-key",
            "seat key %r is not a panel seat; accepted seat keys: %s"
            % (seat_name, valid),
        )
    canonical_tier = seat_map.DEFAULT_TIER_BY_SEAT.get(seat_name)
    if tier != canonical_tier:
        return _identity_refusal(
            "seat-tier-mismatch",
            "seat key %r requires tier %r (registry role); accepted canonical "
            "seat-bundle shape is {vendor, model, effort, tier: %r}"
            % (seat_name, canonical_tier, canonical_tier),
        )
    vendor = seat_config.get("vendor")
    model = seat_config.get("model")
    if "effort" not in seat_config:
        return _identity_refusal(
            "effort-key-absent",
            "seat config must include effort key (value may be null); seat key %r"
            % seat_key.strip(),
        )
    effort = seat_config.get("effort")
    seat = {
        "vendor": vendor,
        "model": model,
        "effort": effort,
        "role": tier,
    }
    entry = seat_bundle.resolve_entry(seat, verb="dispatch-review")
    if not entry.get("ok"):
        return _identity_refusal(
            entry.get("reason") or "seat-unresolved",
            entry.get("detail") or "seat resolution refused",
        )
    return {
        "ok": True,
        "seat": {
            "vendor": entry["vendor"],
            "model": entry["model"],
            "effort": entry.get("effort"),
            "role": entry["role"],
        },
        "seatKey": seat_key.strip(),
        "tier": tier,
    }


def _unrunnable_identity_result(resolved, *, vendor=None, model=None):
    detail = resolved.get("detail") or resolved.get("reason") or "seat-identity-refused"
    return {
        "engine": vendor,
        "model": model,
        "outcome": dispatch_outcome.REASON_UNRUNNABLE,
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
        "detail": "not-dispatched: %s" % detail,
    }


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
    # axis: at least one non-empty investigated path required for engagement
    # Canary diverges from engagement_read: findings and toolCalls alone are not investigation evidence.
    if engine_adapter.engagement_read(res) != "engaged":
        return False
    investigated = res.get("investigated")
    if not isinstance(investigated, (list, tuple)):
        return False
    for entry in investigated:
        if isinstance(entry, str) and entry.strip():
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


def run_canary(seat_key, seat_config, *, repo_root, dispatch=None, timeout=300):
    """Dispatch the planted-defect fixture through the real seat path and score ENGAGEMENT.

    ``seat_key`` and ``seat_config`` (with ``tier`` from the seat map) supply seat identity; the
    registry role rides inside the four-key seat — never chosen locally.

    ``timeout`` bounds the first dispatch attempt only. On retry the runner floors its wait at
    ``RETRY_MIN_TIMEOUT`` (900 s), so worst-case wall time is ``timeout + 900`` seconds.
    """
    if dispatch is None:
        dispatch = engine_dispatch.dispatch_review

    resolved = _resolve_canary_identity(seat_key, seat_config)
    if not resolved.get("ok"):
        vendor = seat_config.get("vendor") if isinstance(seat_config, dict) else None
        model = seat_config.get("model") if isinstance(seat_config, dict) else None
        return _unrunnable_identity_result(resolved, vendor=vendor, model=model)

    seat = resolved["seat"]
    vendor = seat["vendor"]
    model_id = seat["model"]

    prompt_path = None
    try:
        fd, prompt_path = tempfile.mkstemp(prefix="seat-canary-", suffix=".txt")
        os.close(fd)
        with open(prompt_path, "w", encoding="utf-8") as fh:
            fh.write(CANARY_FIXTURE_PROMPT)

        try:
            res = dispatch(
                seat=seat,
                prompt_path=prompt_path,
                repo_root=repo_root,
                timeout=timeout,
                expected_result_kind="findings",
            )
        except Exception as exc:
            return {
                "engine": vendor,
                "model": model_id,
                "outcome": dispatch_outcome.REASON_UNRUNNABLE,
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
            detail = canary_outcome.OUTCOME_PLANT_UNDETECTED
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
            "engine": vendor,
            "model": model_id,
            "outcome": outcome,
            "engaged": engaged,
            "evidence": _evidence_from_dispatch(res),
            "detectedPlant": detected_plant,
            "detail": detail,
            "sanitizedView": res.get("sanitizedView"),
            "seatKey": resolved.get("seatKey"),
            "tier": resolved.get("tier"),
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
    p.add_argument("--seat-key", required=True)
    p.add_argument("--tier", required=True,
                   help="Seat-map tier (registry role name) for this probe")
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
    seat_config = {
        "vendor": args.engine,
        "model": args.engine_model,
        "effort": args.effort,
        "tier": args.tier,
    }
    res = run_canary(
        args.seat_key,
        seat_config,
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
