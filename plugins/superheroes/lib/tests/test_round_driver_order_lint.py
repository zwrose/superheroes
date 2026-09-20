"""Round driver order lint at emission (#1339 WO-2)."""
import importlib.util
import os
import shlex

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_PLUGIN_RUBRIC = os.path.join(_PLUGIN_ROOT, "rubric", "review-base.md")
_SESSION = "/tmp/superheroes-session-wo2-order-lint"
_REPO = "/home/user/proj"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RO = _load("round_orders")
RP = _load("round_phases")
OL = _load("order_lint")
RR = _load("round_records")

# Copied from test_round_orders.py — golden fixer render context helpers.
def _base_context(**over):
    ctx = {
        "session_dir": _SESSION,
        "round": 2,
        "attempt": 0,
        "diff_path": os.path.join(_SESSION, "round-2", "diff.txt"),
        "rubric_path": _PLUGIN_RUBRIC,
        "core_path": "",
        "layer_path": "",
        "repo_root": _REPO,
        "landing_path": os.path.join(_SESSION, "round-2", "landing", "seat.a0.json"),
        "envelope_stub_path": os.path.join(_SESSION, "round-2", "stubs", "seat.json"),
        "ratified_residuals": "- Flaky integration test in CI lane B is accepted",
        "residuals_provenance": "Residuals below are read from the review base commit (base-pinned).",
        "residuals_read_failure": None,
        "payload": {},
        "host_seat": False,
        "placeholders": {},
    }
    ctx.update(over)
    return ctx


def _fixer_placeholders():
    return {
        "FIX_BATCH_PATH": os.path.join(_SESSION, "round-2", "fix-batch.json"),
        "PROFILE_PATH": "(Project profile not resolved for this project)",
        "RUBRIC_PATH": _PLUGIN_RUBRIC,
        "CWD": _REPO,
        "REPO_ROOT": shlex.quote(_REPO),
        # The round economy (C13 layer 2d) replaced the fixer template's bare VERIFY_COMMAND
        # with the scoped verify budget; this golden copy fills it the way
        # `test_round_orders._fixer_placeholders` does, so the render leaves neither an
        # unfilled placeholder nor an unused context key.
        "VERIFY_BUDGET": (
            "Scoped verify budget for this batch — target files: auth.py. "
            "Run the tests that reference those files (select by reading the test files' own text "
            "for the target path, never by test-file name) plus the project's static validators, "
            "at most once each. The project's full verify command is NOT yours to run inside this "
            "attempt — the orchestrator runs it once after the round's fixes land: pytest -q"
        ),
        "ROUND": "2",
        "GATE_GUIDANCE": "No owner-gate guidance is attached to this batch.",
    }


def _section(path, third):
    return ("diff --git a/%s b/%s\n" % (path, path)
            + "index 1111111..2222222 100644\n"
            + "--- a/%s\n" % path
            + "+++ b/%s\n" % path
            + "@@ -1,2 +1,4 @@\n alpha\n+beta\n+%s\n delta\n" % third)


DIFF = "".join(_section("src/f%02d.py" % i, "gamma") for i in range(3))
_FIXER_SKEY = "fixer-508e7896192355de"


def _seed_session(tmp_path, monkeypatch):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir, exist_ok=True)
    monkeypatch.setattr(RD.engine_pref, "load_engine_prefs", lambda _root: {})
    monkeypatch.setattr(RD.engine_pref, "resolve_engine", lambda _role, _prefs: "claude")
    out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
                                    "fixerVendor": "claude", "verifyCommand": "none"})
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    state["headDiff"] = DIFF
    state["fixBatch"] = []
    return session_dir, state


def _emit_fixer(session_dir, state, pending_payload=None):
    return RD._emit_orders_manifest(
        session_dir, state, state["round"], RD.P_FIXER, 0, ["fixer"],
        journal_cmd="next", pending_payload=pending_payload or {}, seat_map={})


def _seed_gate_guidance(state, guidance_text):
    rnd = str(state["round"])
    state["rounds"].setdefault(rnd, {})["judgmentDispositions"] = [
        {
            "id": "f.py::result shape@L1",
            "title": "result shape",
            "file": "f.py",
            "line": 1,
            "disposition": "fix-with-guidance",
            RD.GATE_GUIDANCE_RECORD_KEY: guidance_text,
        }
    ]
    state["_fixBatch"] = [{"title": "result shape", "file": "f.py", "line": 1}]


_LINT_TRIGGER_GUIDANCE = (
    '{"fixes"} via marker channel parser with "resultKind" and --output-schema. '
    'See `plugins/superheroes/lib/no_such_file_1339.py`.'
)


def test_rendered_fixer_order_lints_clean_at_head(tmp_path):
    repo = str(tmp_path / "proj")
    os.makedirs(repo)
    ph = _fixer_placeholders()
    ph["CWD"] = repo
    ph["REPO_ROOT"] = shlex.quote(repo)
    text, reason = RO.render_order(
        RP.P_FIXER, "seat", _base_context(repo_root=repo, placeholders=ph))
    assert reason is None, reason
    lint = OL.check_text(text, repo, kind="fixer")
    assert lint["ok"] is True
    assert lint["kind"] == "fixer"
    assert lint["findings"] == []
    assert lint["checked"] == {"paths": 0, "placeholders": 0}


def test_fixer_emission_refuses_on_lint_finding(tmp_path, monkeypatch):
    # axis: a lint finding's token and detail appear in the order-render-refused string
    session_dir, state = _seed_session(tmp_path, monkeypatch)
    monkeypatch.setattr(
        RD.order_lint, "check_text",
        lambda _text, _root, kind="fixer", **_kw: {
            "ok": False, "kind": "fixer",
            "findings": [{"token": "order-placeholder-unfilled", "detail": "FOO"}],
            "checked": {"paths": 0, "placeholders": 1},
        })
    with pytest.raises(ValueError, match=r"order-render-refused:%s:order-lint:order-placeholder-unfilled:FOO" % _FIXER_SKEY):
        _emit_fixer(session_dir, state)


def test_fixer_emission_refuses_on_real_placeholder(tmp_path, monkeypatch):
    # axis: P_FIXER emission runs order_lint.check_text before committing the manifest
    session_dir, state = _seed_session(tmp_path, monkeypatch)

    def _poisoned_render(phase, seat_key, context):
        return ("You are the fixer.\n\nRepo root: " + "{{" + "REPO_ROOT" + "}}" + "\n", None)

    monkeypatch.setattr(RD.round_orders, "render_order", _poisoned_render)
    with pytest.raises(ValueError, match=r"order-render-refused:%s:order-lint:order-placeholder-unfilled:REPO_ROOT" % _FIXER_SKEY):
        _emit_fixer(session_dir, state)


def test_fixer_emission_passes_when_lint_clean(tmp_path, monkeypatch):
    session_dir, state = _seed_session(tmp_path, monkeypatch)
    anchor = _emit_fixer(session_dir, state)
    assert "manifestSha256" in anchor


def test_non_fixer_phase_is_not_linted(tmp_path, monkeypatch):
    session_dir = str(tmp_path / "verifier-lint")
    os.makedirs(session_dir, exist_ok=True)
    out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
                                    "fixerVendor": "claude", "verifyCommand": "none",
                                    "seatMap": {"seats": {}}})
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    state["headDiff"] = DIFF
    rnd_key = str(state["round"])
    state["rounds"].setdefault(rnd_key, {}).pop("orderVendorProvenanceGaps", None)
    monkeypatch.setattr(RD.engine_pref, "load_engine_prefs", lambda _root: {})
    monkeypatch.setattr(RD.engine_pref, "resolve_engine", lambda _role, _prefs: "claude")

    def _raise_on_lint(*_args, **_kwargs):
        raise AssertionError("linted a non-fixer phase")

    monkeypatch.setattr(RD.order_lint, "check_text", _raise_on_lint)
    seat = "verifier:c1"
    RD._emit_orders_manifest(
        session_dir, state, state["round"], RD.P_VERIFIERS, 0, [seat],
        journal_cmd="next", pending_payload={"clusters": [{"key": "c1", "issues": []}]},
        seat_map={})


def test_lint_refusal_names_first_finding_only(tmp_path, monkeypatch):
    session_dir, state = _seed_session(tmp_path, monkeypatch)
    monkeypatch.setattr(
        RD.order_lint, "check_text",
        lambda _text, _root, kind="fixer", **_kw: {
            "ok": False, "kind": "fixer",
            "findings": [
                {"token": "order-placeholder-unfilled", "detail": "FIRST"},
                {"token": "order-path-unresolved", "detail": "second/path.py"},
            ],
            "checked": {"paths": 1, "placeholders": 1},
        })
    with pytest.raises(ValueError) as exc:
        _emit_fixer(session_dir, state)
    msg = str(exc.value)
    assert "order-lint:order-placeholder-unfilled:FIRST" in msg
    assert "order-path-unresolved" not in msg


def test_empty_findings_with_ok_false_refuses_unknown(tmp_path, monkeypatch):
    session_dir, state = _seed_session(tmp_path, monkeypatch)
    monkeypatch.setattr(
        RD.order_lint, "check_text",
        lambda _text, _root, kind="fixer", **_kw: {
            "ok": False, "kind": "fixer", "findings": [], "checked": {"paths": 0, "placeholders": 0},
        })
    with pytest.raises(ValueError, match=r"order-render-refused:%s:order-lint:unknown" % _FIXER_SKEY):
        _emit_fixer(session_dir, state)


def test_fixer_emission_ignores_lint_triggers_inside_gate_guidance(tmp_path, monkeypatch):
    # axis: owner-gate guidance prose is elided from fixer-emission lint text
    session_dir, state = _seed_session(tmp_path, monkeypatch)
    _seed_gate_guidance(state, _LINT_TRIGGER_GUIDANCE)
    anchor = _emit_fixer(session_dir, state)
    assert "manifestSha256" in anchor
    order_path = RR.order_prompt_path(session_dir, state["round"], RP.P_FIXER, _FIXER_SKEY, 0)
    order_text = open(order_path, encoding="utf-8").read()
    assert _LINT_TRIGGER_GUIDANCE in order_text


def test_fixer_emission_still_refuses_driver_authored_trigger_with_guidance_present(
        tmp_path, monkeypatch):
    session_dir, state = _seed_session(tmp_path, monkeypatch)
    _seed_gate_guidance(state, _LINT_TRIGGER_GUIDANCE)

    def _poisoned_render(phase, seat_key, context):
        guidance = (context.get("placeholders") or {}).get("GATE_GUIDANCE") or ""
        return ("You are the fixer.\n\n" + guidance + "\n\nRepo root: "
                + "{{" + "REPO_ROOT" + "}}" + "\n", None)

    monkeypatch.setattr(RD.round_orders, "render_order", _poisoned_render)
    with pytest.raises(
            ValueError,
            match=r"order-render-refused:%s:order-lint:order-placeholder-unfilled:REPO_ROOT"
            % _FIXER_SKEY):
        _emit_fixer(session_dir, state)


_LINT_TRIGGER_RESIDUALS = (
    '{"fixes"} via marker channel parser with "resultKind". '
    'See `lib/tests/no_such_residual_file_1339.py`.'
)


def test_fixer_emission_ignores_lint_triggers_inside_ratified_residuals(tmp_path, monkeypatch):
    # axis: ratified-residuals quoted data is elided from fixer-emission lint text
    session_dir, state = _seed_session(tmp_path, monkeypatch)
    monkeypatch.setattr(
        RD.round_orders, "resolve_order_residuals",
        lambda _repo, _base: (_LINT_TRIGGER_RESIDUALS, "provenance line", None))
    anchor = _emit_fixer(session_dir, state)
    assert "manifestSha256" in anchor
    order_path = RR.order_prompt_path(session_dir, state["round"], RP.P_FIXER, _FIXER_SKEY, 0)
    order_text = open(order_path, encoding="utf-8").read()
    assert _LINT_TRIGGER_RESIDUALS in order_text


def test_fixer_emission_ignores_lint_triggers_inside_verify_command(tmp_path, monkeypatch):
    # axis: owner-configured verify command is elided from fixer-emission lint text
    session_dir, state = _seed_session(tmp_path, monkeypatch)
    repo = str(tmp_path / "proj")
    os.makedirs(repo)
    verify = "npm run build && node dist/cli.js && xargs -I {item} echo ok"
    state.setdefault("config", {})["repoRoot"] = repo
    state["config"]["verifyCommand"] = verify
    anchor = _emit_fixer(session_dir, state)
    assert "manifestSha256" in anchor
    order_path = RR.order_prompt_path(session_dir, state["round"], RP.P_FIXER, _FIXER_SKEY, 0)
    order_text = open(order_path, encoding="utf-8").read()
    assert verify in order_text
    # R28 re-pin (C13 bring-current, option b): the retired VERIFY_COMMAND placeholder is no
    # longer the elision's source — the owner's command is read from the session config and
    # elided inside the scoped verify budget. The emission above is the production gate; this
    # asserts the lint text the emission built.
    budget = RD._fixer_verify_budget(state.get("fixBatch") or [], state["config"])
    lint = OL.check_text(RD._order_lint_text(order_text, {
        "placeholders": {"VERIFY_BUDGET": budget},
        "verify_command": verify,
    }), repo, kind="fixer")
    assert lint["ok"] is True


def test_fixer_emission_elides_only_the_owner_verify_command_from_the_budget(tmp_path, monkeypatch):
    # axis: the narrow elision — the owner's command goes, the driver's target-file list stays graded
    session_dir, state = _seed_session(tmp_path, monkeypatch)
    repo = str(tmp_path / "proj")
    os.makedirs(repo)
    # A real project-shaped verify command: validator paths, the driver-bound `{baseRef}` token
    # (exempt by `order_lint._DRIVER_PH`, so it is NOT what bites), and one ordinary `{name}`
    # token of the owner's own — which is what the lint would refuse on if it were not elided.
    verify = ("/venv/bin/python .github/scripts/validate_skills.py"
              " && /usr/bin/python3 .github/scripts/verify_touched_tests.py --base {baseRef}"
              " && xargs -I {item} echo ok")
    state.setdefault("config", {})["repoRoot"] = repo
    state["config"]["verifyCommand"] = verify
    target = "plugins/superheroes/lib/round_driver.py"
    # Every path the order names resolves, so the ONE thing the lint could still refuse on is
    # the `{baseRef}` token inside the owner's command — the production failure exactly.
    for path in (target, ".github/scripts/validate_skills.py",
                 ".github/scripts/verify_touched_tests.py"):
        os.makedirs(os.path.join(repo, os.path.dirname(path)), exist_ok=True)
        open(os.path.join(repo, path), "w", encoding="utf-8").close()
    state["fixBatch"] = [{"file": target, "title": "t", "line": 1}]
    # The production path emits without refusing.
    assert "manifestSha256" in _emit_fixer(session_dir, state)
    order_path = RR.order_prompt_path(session_dir, state["round"], RP.P_FIXER, _FIXER_SKEY, 0)
    order_text = open(order_path, encoding="utf-8").read()
    assert verify in order_text
    budget = RD._fixer_verify_budget(state["fixBatch"], state["config"])
    lint_text = RD._order_lint_text(order_text, {
        "placeholders": {"VERIFY_BUDGET": budget},
        "verify_command": verify,
    })
    # The owner's command is gone from the lint text; the driver's own target-file list is not.
    assert verify not in lint_text
    assert RD.QUOTED_DATA_LINT_ELISION in lint_text
    assert target in lint_text


def test_fixer_emission_resolves_plugin_relative_citation_via_plugin_root(tmp_path, monkeypatch):
    # axis: driver-authored plugin-relative citations resolve via the plugin root at fixer emission
    session_dir, state = _seed_session(tmp_path, monkeypatch)

    def _render_with_path(phase, seat_key, context, cited):
        return ("You are the fixer.\n\nSee `%s` for the rubric.\n" % cited, None)

    monkeypatch.setattr(
        RD.round_orders, "render_order",
        lambda phase, seat_key, context: _render_with_path(
            phase, seat_key, context, "rubric/review-base.md"))
    anchor = _emit_fixer(session_dir, state)
    assert "manifestSha256" in anchor

    monkeypatch.setattr(
        RD.round_orders, "render_order",
        lambda phase, seat_key, context: _render_with_path(
            phase, seat_key, context, "rubric/no_such_rubric_1339.md"))
    with pytest.raises(
            ValueError,
            match=r"order-render-refused:%s:order-lint:order-path-unresolved:rubric/no_such_rubric_1339.md"
            % _FIXER_SKEY):
        _emit_fixer(session_dir, state)
