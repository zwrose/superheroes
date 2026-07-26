#!/usr/bin/env python3
"""Config-time dispatch vocabulary round-trip self-test (issue #636).

Pure, stdlib-only; never touches disk; never raises from run()."""
from __future__ import annotations

import io
import itertools
import json
import os
import sys
from contextlib import redirect_stdout

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import dispatch_guard  # noqa: E402
import engine_adapter  # noqa: E402
import model_registry  # noqa: E402
import seat_map  # noqa: E402

_EXTERNAL_ENGINES = ("codex", "cursor")
_ROLE_KINDS = ("review", "build", "fix")
_NAMED_REFUSALS = frozenset({
    "unknown-engine",
    "unknown-claude-tier",
    "fable-unrunnable",
    "unregistered-engine-model",
    "engine-model-effort-conflict",
    "invalid-model-effort",
    "untokenizable",
})
_DETAIL_CAP = 5


def _fail(failures, where, detail):
    failures.append({"where": where, "detail": detail})


def _vendor_allowlist_union(vendor):
    seen = set()
    out = []
    for role in model_registry.roles():
        for pair in model_registry.allowlist(role, vendor):
            if pair not in seen:
                seen.add(pair)
                out.append(pair)
    return out


def _model_flag_index(engine):
    return "-m" if engine == "codex" else "--model"


def _assert_build_argv_invariant(engine, role_kind, effort, opts, failures, checked, where_base):
    checked[0] += 1
    try:
        res = engine_adapter.build_argv_result(engine, role_kind, effort, opts)
    except Exception as exc:
        _fail(failures, where_base, "build_argv_result raised: %s" % exc)
        return
    argv = res.get("argv")
    reason = res.get("reason")
    if argv == [] and reason is None:
        _fail(failures, where_base, "nameless refusal: empty argv with reason is None")
        return
    if argv and reason is not None:
        _fail(
            failures,
            where_base,
            "argv non-empty (%r) with reason %r" % (argv, reason),
        )
        return
    if reason is not None:
        checked[0] += 1
        if reason not in _NAMED_REFUSALS:
            _fail(failures, where_base, "unknown refusal token %r" % reason)
        return
    checked[0] += 1
    flag = _model_flag_index(engine)
    if flag not in argv:
        _fail(failures, where_base, "argv missing model flag %r: %r" % (flag, argv))
        return
    idx = argv.index(flag)
    if idx + 1 >= len(argv):
        _fail(failures, where_base, "no value after %r in argv" % flag)
        return
    model_val = argv[idx + 1]
    em = opts.get("engine_model")
    if isinstance(em, str) and em:
        vendor = engine
        if model_registry.is_registered(vendor, em):
            expected_tok = model_registry.dispatch_token(vendor, em, effort)
        else:
            parsed = model_registry.parse_dispatch_token(vendor, em)
            if parsed is not None:
                m_id, tok_eff = parsed
                eff = effort if tok_eff is None else tok_eff
                expected_tok = model_registry.dispatch_token(vendor, m_id, eff)
            else:
                expected_tok = None
        if expected_tok is not None and model_val != expected_tok:
            _fail(
                failures,
                where_base,
                "model flag value %r != expected dispatch token %r" % (model_val, expected_tok),
            )


def _leg_registry(failures, checked):
    for role in model_registry.roles():
        for vendor in model_registry.vendors():
            where_rv = "registry %s/%s" % (role, vendor)
            try:
                pairs = model_registry.allowlist(role, vendor)
                cell = model_registry.matrix_config(role, vendor)
                if not pairs and cell is None:
                    continue
                checked[0] += 1
                if not pairs and cell is not None:
                    _fail(
                        failures,
                        where_rv,
                        "allowlist empty but matrix_config is %r" % (cell,),
                    )
                    continue
                if pairs and cell is None:
                    _fail(
                        failures,
                        where_rv,
                        "allowlist non-empty but matrix_config is None",
                    )
                    continue

                for m, e in pairs:
                    w = "roundtrip %s/%s (%s, %s)" % (role, vendor, m, e)
                    checked[0] += 1
                    ok_cfg, why = model_registry.validate_config(
                        vendor, m, e, allow_override_only=True
                    )
                    if not ok_cfg:
                        _fail(failures, w, "validate_config: %s" % why)
                        continue
                    checked[0] += 1
                    tok = model_registry.dispatch_token(vendor, m, e)
                    if tok is None:
                        _fail(failures, w, "dispatch_token returned None")
                        continue
                    checked[0] += 1
                    parsed = model_registry.parse_dispatch_token(vendor, tok)
                    if parsed is None:
                        _fail(failures, w, "parse_dispatch_token returned None for %r" % tok)
                        continue
                    p_m, p_e = parsed
                    if p_m != m:
                        _fail(failures, w, "parsed model %r != %r" % (p_m, m))
                    if p_e is not None and p_e != e:
                        _fail(
                            failures,
                            w,
                            "parsed effort %r contradicts allowlist effort %r" % (p_e, e),
                        )
                    eff_for_validate = p_e if p_e is not None else e
                    checked[0] += 1
                    ok_pb, why_pb = model_registry.validate_config(
                        vendor, p_m, eff_for_validate, allow_override_only=True
                    )
                    if not ok_pb:
                        _fail(failures, w, "parse-back validate_config: %s" % why_pb)
                    checked[0] += 1
                    rd = model_registry.resolve_dispatch(role, vendor, m, e)
                    if not rd.get("ok"):
                        _fail(failures, w, "resolve_dispatch(m,e): %s" % rd.get("reason"))
                    elif (rd["model_id"], rd["effort"], rd["dispatch_token"]) != (m, e, tok):
                        _fail(
                            failures,
                            w,
                            "resolve_dispatch(m,e) got (%r,%r,%r)" % (
                                rd["model_id"],
                                rd["effort"],
                                rd["dispatch_token"],
                            ),
                        )
                    checked[0] += 1
                    rd2 = model_registry.resolve_dispatch(role, vendor, tok, e)
                    if not rd2.get("ok"):
                        _fail(failures, w, "resolve_dispatch(tok,e): %s" % rd2.get("reason"))
                    elif (rd2["model_id"], rd2["effort"], rd2["dispatch_token"]) != (m, e, tok):
                        _fail(
                            failures,
                            w,
                            "resolve_dispatch(tok,e) got (%r,%r,%r)" % (
                                rd2["model_id"],
                                rd2["effort"],
                                rd2["dispatch_token"],
                            ),
                        )
                    checked[0] += 1
                    rd3 = model_registry.resolve_dispatch(role, vendor, tok, None)
                    if not rd3.get("ok"):
                        _fail(failures, w, "resolve_dispatch(tok,None): %s" % rd3.get("reason"))
                    else:
                        pair3 = (rd3["model_id"], rd3["effort"])
                        if pair3 not in pairs:
                            _fail(
                                failures,
                                w,
                                "resolve_dispatch(tok,None) pair %r not in allowlist" % (pair3,),
                            )
                        es = rd3.get("effort_source")
                        allowed_es = ("resolved-lowest-rung", "resolved-unique")
                        if p_e is not None:
                            allowed_es = allowed_es + ("token-encoded",)
                        if es not in allowed_es:
                            _fail(
                                failures,
                                w,
                                "resolve_dispatch(tok,None) effort_source %r" % es,
                            )
                    checked[0] += 1
                    dg = dispatch_guard.validate(role, vendor, m, e)
                    if not dg.get("ok"):
                        _fail(failures, w, "dispatch_guard: %s" % dg.get("reason"))
                    elif dg.get("dispatch_token") != tok or dg.get("resolved_model") != tok:
                        _fail(
                            failures,
                            w,
                            "dispatch_guard tokens mismatch: %r / %r" % (
                                dg.get("dispatch_token"),
                                dg.get("resolved_model"),
                            ),
                        )
                    elif (dg.get("model_id"), dg.get("effort")) != (m, e):
                        _fail(
                            failures,
                            w,
                            "dispatch_guard model/effort mismatch",
                        )

                if cell is not None:
                    w_cell = "matrix %s/%s" % (role, vendor)
                    checked[0] += 1
                    if cell not in pairs:
                        _fail(
                            failures,
                            w_cell,
                            "matrix cell %r not in allowlist" % (cell,),
                        )
                    checked[0] += 1
                    rd_def = model_registry.resolve_dispatch(role, vendor)
                    if not rd_def.get("ok"):
                        _fail(failures, w_cell, "resolve_dispatch default: %s" % rd_def.get("reason"))
                    elif (rd_def["model_id"], rd_def["effort"]) != cell:
                        _fail(
                            failures,
                            w_cell,
                            "default resolved %r != cell %r" % (
                                (rd_def["model_id"], rd_def["effort"]),
                                cell,
                            ),
                        )
                    elif rd_def.get("effort_source") != "seat-default":
                        _fail(
                            failures,
                            w_cell,
                            "effort_source %r != seat-default" % rd_def.get("effort_source"),
                        )
            except Exception as exc:
                _fail(failures, where_rv, "unexpected: %s: %s" % (type(exc).__name__, exc))


def _leg_engine_adapter(failures, checked):
    for engine in _EXTERNAL_ENGINES:
        vendor = engine
        pairs = _vendor_allowlist_union(vendor)
        for role_kind in _ROLE_KINDS:
            for m, e in pairs:
                opts_id = {"engine_model": m}
                opts_tok = {
                    "engine_model": model_registry.dispatch_token(vendor, m, e),
                }
                where = "build-argv %s/%s (%s, %s)" % (engine, role_kind, m, e)
                try:
                    r_id = engine_adapter.build_argv_result(engine, role_kind, e, opts_id)
                    r_tok = engine_adapter.build_argv_result(engine, role_kind, e, opts_tok)
                except Exception as exc:
                    _fail(failures, where, "build_argv_result raised: %s" % exc)
                    continue
                checked[0] += 1
                if r_id.get("reason") != r_tok.get("reason"):
                    _fail(
                        failures,
                        where,
                        "reason mismatch id=%r tok=%r"
                        % (r_id.get("reason"), r_tok.get("reason")),
                    )
                checked[0] += 1
                if r_id.get("argv") != r_tok.get("argv"):
                    _fail(
                        failures,
                        where,
                        "argv mismatch id=%r tok=%r" % (r_id.get("argv"), r_tok.get("argv")),
                    )
                _assert_build_argv_invariant(
                    engine, role_kind, e, opts_id, failures, checked, where
                )

    named_cases = [
        (
            "unknown-claude-tier",
            {"model": "cursor-grok-4.5-high"},
            "high",
        ),
        ("fable-unrunnable", {"model": "fable"}, "high"),
        (
            "engine-model-effort-conflict",
            {"engine_model": "cursor-grok-4.5-high"},
            "low",
        ),
        ("unregistered-engine-model", {"engine_model": "not-a-real-model-id"}, "high"),
    ]
    for engine in _EXTERNAL_ENGINES:
        for token, opts, effort in named_cases:
            if token == "engine-model-effort-conflict" and engine == "codex":
                continue
            where = "named-refusal %s %s" % (engine, token)
            checked[0] += 1
            try:
                res = engine_adapter.build_argv_result(engine, "build", effort, opts)
            except Exception as exc:
                _fail(failures, where, "raised: %s" % exc)
                continue
            if res.get("reason") != token:
                _fail(
                    failures,
                    where,
                    "expected reason %r got %r argv=%r"
                    % (token, res.get("reason"), res.get("argv")),
                )
            if res.get("argv") != []:
                _fail(failures, where, "expected empty argv on refusal")

    for engine in _EXTERNAL_ENGINES:
        where = "cursor-composer-default %s" % engine
        if engine != "cursor":
            continue
        checked[0] += 1
        try:
            res = engine_adapter.build_argv_result("cursor", "build", None, {})
        except Exception as exc:
            _fail(failures, where, "raised: %s" % exc)
            continue
        if res.get("reason") is not None:
            _fail(failures, where, "expected runnable default, reason=%r" % res.get("reason"))
        elif not res.get("argv"):
            _fail(failures, where, "expected non-empty argv for composer default")


def _cli_build_argv(args_tail):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = engine_adapter.main(["build-argv"] + args_tail)
    return rc, buf.getvalue().strip()


def _leg_cli(failures, checked):
    cases = [
        (
            "cli composer no effort",
            [
                "--engine",
                "cursor",
                "--role",
                "build",
                "--engine-model",
                "composer-2.5",
            ],
            True,
        ),
        (
            "cli grok by registry id",
            [
                "--engine",
                "cursor",
                "--role",
                "review",
                "--engine-model",
                "cursor-grok-4.5",
                "--effort",
                "high",
            ],
            True,
        ),
        (
            "cli grok by composed token",
            [
                "--engine",
                "cursor",
                "--role",
                "review",
                "--engine-model",
                "cursor-grok-4.5-high",
                "--effort",
                "high",
            ],
            True,
        ),
        (
            "cli fable refusal",
            [
                "--engine",
                "codex",
                "--role",
                "build",
                "--model",
                "fable",
                "--effort",
                "high",
            ],
            False,
        ),
    ]
    for label, tail, expect_argv in cases:
        where = "leg3 %s" % label
        checked[0] += 1
        try:
            rc, out = _cli_build_argv(tail)
        except Exception as exc:
            _fail(failures, where, "main raised: %s" % exc)
            continue
        if rc != 0 and expect_argv:
            _fail(failures, where, "exit %s stdout=%r" % (rc, out))
            continue
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as exc:
            _fail(failures, where, "stdout not JSON: %s (%r)" % (exc, out))
            continue
        if expect_argv:
            if not isinstance(payload, list) or not payload:
                _fail(failures, where, "expected non-empty argv list, got %r" % payload)
        else:
            if not isinstance(payload, dict) or payload.get("ok") is not False:
                _fail(failures, where, "expected refusal envelope, got %r" % payload)
            elif payload.get("detail") != "fable-unrunnable":
                _fail(
                    failures,
                    where,
                    "expected fable-unrunnable detail, got %r" % payload.get("detail"),
                )


def _leg_seat_map(failures, checked):
    vendors = list(model_registry.vendors())
    scenarios = [
        (None, None, 0),
        ("anthropic", "openai", 1),
        ("anthropic", "anthropic", 2),
    ]
    n = len(vendors)
    for r in range(1, n + 1):
        for combo in itertools.combinations(vendors, r):
            live = list(combo)
            for author_family, narrative_family, seed in scenarios:
                where = "seat-map live=%s seed=%s" % (live, seed)
                try:
                    built = seat_map.build(
                        None,
                        live,
                        author_family,
                        narrative_family,
                        seed,
                    )
                except Exception as exc:
                    _fail(failures, where, "seat_map.build raised: %s" % exc)
                    continue
                seats = built.get("seats") or {}
                for seat_name, seat in seats.items():
                    if not isinstance(seat, dict):
                        continue
                    vendor = seat.get("vendor")
                    model = seat.get("model")
                    effort = seat.get("effort")
                    tier = seat.get("tier")
                    if vendor is None or model is None:
                        continue
                    w = "seat %s @ %s" % (seat_name, where)
                    checked[0] += 1
                    if model == "" or not model_registry.is_registered(vendor, model):
                        _fail(
                            failures,
                            w,
                            "seat model %r is not a registry id for vendor %r" % (model, vendor),
                        )
                        continue
                    checked[0] += 1
                    rd = model_registry.resolve_dispatch(tier, vendor, model, effort)
                    if not rd.get("ok"):
                        _fail(
                            failures,
                            w,
                            "resolve_dispatch: %s" % rd.get("reason"),
                        )
                    elif not rd.get("dispatch_token"):
                        _fail(failures, w, "dispatch_token is None")


def run():
    failures = []
    checked = [0]
    try:
        _leg_registry(failures, checked)
        _leg_engine_adapter(failures, checked)
        _leg_cli(failures, checked)
        _leg_seat_map(failures, checked)
    except Exception as exc:
        _fail(failures, "run()", "top-level: %s: %s" % (type(exc).__name__, exc))
    n_checked = checked[0]
    ok = not failures and n_checked > 0
    return {"ok": ok, "checked": n_checked, "failures": failures}


def _format_probe_detail(result):
    if result["checked"] == 0:
        return "dispatch self-test performed zero checks"
    if result["ok"]:
        return "ok (%d checks)" % result["checked"]
    parts = []
    for entry in result["failures"][:_DETAIL_CAP]:
        parts.append("%s: %s" % (entry["where"], entry["detail"]))
    extra = len(result["failures"]) - _DETAIL_CAP
    if extra > 0:
        parts.append("… and %d more failure(s)" % extra)
    return "; ".join(parts)


def probe_result():
    result = run()
    ok = result["ok"] and result["checked"] > 0
    return {
        "tool": "dispatch-vocab",
        "ok": ok,
        "detail": _format_probe_detail({**result, "ok": ok}),
    }


def main(argv):
    args = list(argv[1:]) if len(argv) > 1 and argv[0].endswith(".py") else list(argv)
    if not args or args[0] != "run":
        sys.stderr.write("usage: dispatch_selftest.py run\n")
        return 2
    result = run()
    sys.stdout.write(json.dumps(result) + "\n")
    return 0 if result["ok"] and result["checked"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
