"""#2284: a break-it test whose text a transit redactor damaged is reported not run, never executed.

The invariant: a break-it block whose text (header lines or content) carries a transit redaction placeholder (a
bracketed ``[REDACTED`` family closed by ``]`` on the same line) is never executed. It is recorded ``not-run`` with the
reason ``transit-redacted`` on every path that would otherwise run it (the panel's intercept, the second test, the
break-it-change verb), and the review record names that reason. The placeholder pattern lives in ``break_it.py`` alone.

Pins, each at the place the rule is enforced:

A1  the adapter's chokepoint stamps ``TRANSIT_FIELD`` off the original suggestion (header and content), and only when
    the suggestion parses as a block; a clean block carries neither field;
A2  the plugin's own scrub leaves a block's content alone: content is byte-identical and ``REDACTED_FIELD`` is set
    only when a header line changed;
B1  ``intercept`` stamps ``(not-run, transit-redacted)`` and never calls the runner; it wins over ``suggestion-redacted``;
C1  the second-test fold carries the field; C2 the correction fold names the reason; C3 ``break-it-change`` never runs
    a changed block that carries a placeholder;
D1  the review record renders ``not run: transit-redacted``;
E   the test role's doctrine names run-time construction for placeholder-shaped text; the pattern has one home.

Edges: E1 a non-string suggestion · E2 a seat-supplied ``TRANSIT_FIELD`` stays (fail-closed) · E3 an unparseable
block keeps the malformed-block refusal · E4 a placeholder in prose fields only runs · E5 the ``change`` alias.

Bite-proof record: wo_a_2284_transit_redacted
"""
import glob
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import break_it  # noqa: E402
import engine_adapter as EA  # noqa: E402
import review_record  # noqa: E402
import test_break_it_attached_2210 as AT  # noqa: E402
import test_c1l10_audit_checks as C1  # noqa: E402
import test_c1l10b_test_restore as TR  # noqa: E402
from test_break_it_attached_2210 import fx  # noqa: E402,F401  (a fixture)
from test_break_it_loop import (  # noqa: E402,F401
    PY, TEST_PATH, _TEST_FAILING, _block, _break_it_finding, world)

RD = TR.RD
# Built from pieces, so neither this file nor a redactor's pass over it carries the placeholder or a credential whole.
PLACEHOLDER = "[" + "REDACTED]"
TOKEN = "sk-" + "a" * 48


@pytest.fixture(autouse=True)
def _pinned_git_env(monkeypatch, tmp_path):
    """The fixture repos' git calls read no user or system git config."""
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _spy_runner(calls):
    """An intercept runner that records each call and returns a not-run record of its own reason."""
    def runner(repo_root, head, block, **kwargs):
        calls.append(block["path"])
        return break_it._not_run(head, block, "stub-ran")
    return runner


def _reason(world_):
    (run,) = world_.round_record["breakItRuns"]
    return run["outcome"], run["reason"]


def _scrub_one(finding):
    accepted, _ = EA._scrub_findings([finding])
    return accepted[0]


# --- the placeholder shapes (the one home) ----------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    pytest.param("[" + "REDACTED]", id="bare"),
    pytest.param("x = '[" + "REDACTED_TOKEN]'", id="suffix"),
    pytest.param("[" + "REDACTED SECRET]", id="spaced"),
])
def test_the_bracketed_redacted_family_is_a_placeholder(text):
    assert break_it.transit_redacted(text) is True


@pytest.mark.parametrize("text", [
    pytest.param('assert value == "REDACTED"', id="bare-word"),
    pytest.param("[" + "REDACTED", id="unclosed"),
    pytest.param("[" + "REDACTED\n]", id="closed-on-another-line"),
    pytest.param('"[" + "REDACTED]"', id="built-from-pieces"),
    pytest.param("", id="empty"),
])
def test_text_that_is_not_the_bracketed_family_is_not_a_placeholder(text):
    assert break_it.transit_redacted(text) is False


@pytest.mark.parametrize("value", [None, 5, b"[" + b"REDACTED]", ["[" + "REDACTED]"], {"a": PLACEHOLDER}])
def test_e1_a_non_string_is_never_a_placeholder_and_never_raises(value):
    assert break_it.transit_redacted(value) is False


def test_e1_a_non_string_suggestion_passes_the_chokepoint_without_a_stamp():
    for suggestion in (5, None, ["x"]):
        got = _scrub_one({"title": "t", "body": "a real body", "suggestion": suggestion})
        assert break_it.TRANSIT_FIELD not in got and break_it.REDACTED_FIELD not in got


@pytest.mark.parametrize("key", ["path", "run", "content"])
def test_transit_not_run_reads_path_run_and_content_of_a_block(key):
    block = {"path": TEST_PATH, "run": "pytest " + TEST_PATH, "content": _TEST_FAILING}
    assert break_it.transit_not_run("h1", block) is None
    block[key] = block[key] + " " + PLACEHOLDER
    record = break_it.transit_not_run("h1", block)
    assert (record["outcome"], record["reason"], record["head"]) == (break_it.OUTCOME_NOT_RUN, "transit-redacted", "h1")
    assert record["sha256"] is None


def test_transit_not_run_of_something_that_is_no_block_is_none():
    assert break_it.transit_not_run("h1", None) is None and break_it.transit_not_run("h1", "text") is None


# --- A1: the chokepoint stamps off the original suggestion ----------------------------------------------------------

def test_a1_a_clean_block_carries_neither_field_and_runs(world):
    got = _scrub_one(_break_it_finding())
    assert break_it.TRANSIT_FIELD not in got and break_it.REDACTED_FIELD not in got
    world.fold_panel(got)
    outcome, reason = _reason(world)
    assert outcome != break_it.OUTCOME_NOT_RUN and reason is None


def test_a1_a_placeholder_in_the_content_is_stamped_and_the_test_is_never_run(world):
    content = _TEST_FAILING + "# the token was " + PLACEHOLDER + "\n"
    got = _scrub_one(_break_it_finding(content))
    assert got[break_it.TRANSIT_FIELD] is True
    assert got["suggestion"] == _break_it_finding(content)["suggestion"] and break_it.REDACTED_FIELD not in got
    calls = []
    kept, runs, _exempt, _stamped = break_it.intercept([got], world.repo, world.head, runner=_spy_runner(calls))
    assert calls == []
    assert (runs[0]["outcome"], runs[0]["reason"]) == ("not-run", "transit-redacted")
    assert kept[0][break_it.RUN_FIELD]["reason"] == "transit-redacted"
    world.fold_panel(got)
    assert _reason(world) == ("not-run", "transit-redacted")
    assert world.round_record["breakItRuns"][0]["sha256"] is None


def test_a1_a_placeholder_in_the_run_header_is_stamped_and_the_test_is_never_run(world):
    raw = _break_it_finding()
    raw["suggestion"] = "break-it-test v1\npath: %s\nrun: %s %s --opt %s\n---\n%s" % (
        TEST_PATH, PY, TEST_PATH, PLACEHOLDER, _TEST_FAILING)
    got = _scrub_one(raw)
    assert got[break_it.TRANSIT_FIELD] is True
    calls = []
    _kept, runs, _exempt, _stamped = break_it.intercept([got], world.repo, world.head, runner=_spy_runner(calls))
    assert calls == [] and (runs[0]["outcome"], runs[0]["reason"]) == ("not-run", "transit-redacted")
    world.fold_panel(got)
    assert _reason(world) == ("not-run", "transit-redacted")


def test_a1_the_bare_word_redacted_in_an_asserted_string_is_no_placeholder_and_runs(world):
    content = 'value = "REDACTED"\nassert value == "REDACTED"\n' + _TEST_FAILING
    got = _scrub_one(_break_it_finding(content))
    assert break_it.TRANSIT_FIELD not in got and break_it.REDACTED_FIELD not in got
    world.fold_panel(got)
    outcome, reason = _reason(world)
    assert outcome != break_it.OUTCOME_NOT_RUN and reason is None


def test_e4_a_placeholder_in_the_prose_fields_only_still_runs(world):
    raw = _break_it_finding(title="Break-it: the %s token path" % PLACEHOLDER, body="the log shows " + PLACEHOLDER)
    got = _scrub_one(raw)
    assert break_it.TRANSIT_FIELD not in got
    world.fold_panel(got)
    assert _reason(world)[0] != break_it.OUTCOME_NOT_RUN


def test_e3_a_block_that_does_not_parse_keeps_the_malformed_refusal(world):
    raw = _break_it_finding()
    raw["suggestion"] = "not a block " + PLACEHOLDER
    got = _scrub_one(raw)
    assert break_it.TRANSIT_FIELD not in got
    world.fold_panel(got)
    outcome, reason = _reason(world)
    assert outcome == "not-run" and reason == "block-header-missing"


def test_e3_a_header_missing_its_run_line_is_malformed_not_transit():
    raw = _break_it_finding()
    raw["suggestion"] = "break-it-test v1\npath: %s\n---\n%s" % (TEST_PATH, PLACEHOLDER)
    got = _scrub_one(raw)
    assert break_it.TRANSIT_FIELD not in got
    (_kept, runs, _e, _s) = break_it.intercept([got], None, "h", runner=_spy_runner([]))
    assert runs[0]["reason"] == "block-run-missing"


def test_e5_the_change_alias_is_stamped_like_the_suggestion():
    clean = _break_it_finding()
    clean["change"] = clean.pop("suggestion")
    got = _scrub_one(clean)
    assert break_it.TRANSIT_FIELD not in got and break_it.REDACTED_FIELD not in got
    damaged = _break_it_finding(_TEST_FAILING + "# " + PLACEHOLDER + "\n")
    damaged["change"] = damaged.pop("suggestion")
    got = _scrub_one(damaged)
    assert got[break_it.TRANSIT_FIELD] is True and break_it.REDACTED_FIELD not in got
    (_kept, runs, _e, _s) = break_it.intercept([got], None, "h", runner=_spy_runner([]))
    assert (runs[0]["outcome"], runs[0]["reason"]) == ("not-run", "transit-redacted")


def test_a_placeholder_on_an_attached_block_is_stamped_and_never_run(fx):
    got = _scrub_one(AT._attached(_TEST_FAILING + "# " + PLACEHOLDER + "\n"))
    assert got[break_it.TRANSIT_FIELD] is True
    calls = []
    _kept, runs, _e, _s = break_it.intercept([got], fx.repo, fx.head, runner=_spy_runner(calls))
    assert calls == [] and (runs[0]["outcome"], runs[0]["reason"]) == ("not-run", "transit-redacted")


# --- A2: the plugin's own scrub leaves a block's content alone --------------------------------------------------------

def test_a2_content_the_plugin_scrub_would_rewrite_comes_through_byte_identical_and_runs(world):
    content = 'headers = "Authorization: Bearer %s"\n' % TOKEN + _TEST_FAILING
    assert EA._scrub(content) != content  # premise: the scrub would rewrite this line
    raw = _break_it_finding(content)
    got = _scrub_one(raw)
    assert got["suggestion"] == raw["suggestion"]
    assert break_it.REDACTED_FIELD not in got and break_it.TRANSIT_FIELD not in got
    world.fold_panel(got)
    outcome, reason = _reason(world)
    assert outcome != break_it.OUTCOME_NOT_RUN and reason is None


def test_a2_other_fields_of_the_finding_are_still_scrubbed_in_full():
    raw = _break_it_finding(body="the log held Authorization: Bearer %s" % TOKEN,
                            evidence="token %s" % TOKEN)
    got = _scrub_one(raw)
    assert TOKEN not in got["body"] and TOKEN not in got["evidence"]


def test_a2_a_header_line_the_scrub_rewrites_still_sets_the_redacted_field(world):
    raw = _break_it_finding()
    raw["suggestion"] = "break-it-test v1\npath: %s\nrun: %s %s --token %s\n---\n%s" % (
        TEST_PATH, PY, TEST_PATH, TOKEN, _TEST_FAILING)
    got = _scrub_one(raw)
    assert got["suggestion"] != raw["suggestion"] and TOKEN not in got["suggestion"].split("\n---\n")[0]
    assert got[break_it.REDACTED_FIELD] is True and break_it.TRANSIT_FIELD not in got
    assert got["suggestion"].split("\n", 4)[4] == _TEST_FAILING
    world.fold_panel(got)
    assert _reason(world) == ("not-run", "suggestion-redacted")


def test_a2_a_per_area_suggestion_that_is_no_block_is_still_flagged_when_the_scrub_alters_it():
    raw = _break_it_finding()
    raw["suggestion"] = "token " + TOKEN
    got = _scrub_one(raw)
    assert got[break_it.REDACTED_FIELD] is True


# --- B1: the intercept -----------------------------------------------------------------------------------------------

def test_b1_transit_redacted_wins_when_both_stamps_are_set(world):
    finding = _break_it_finding(**{break_it.TRANSIT_FIELD: True, break_it.REDACTED_FIELD: True})
    calls = []
    kept, runs, exempt, _s = break_it.intercept([finding], world.repo, world.head, runner=_spy_runner(calls))
    assert calls == []
    assert (runs[0]["outcome"], runs[0]["reason"]) == ("not-run", "transit-redacted")
    assert kept[0][break_it.RUNS_FIELD][0]["status"] == "not-started"
    assert id(kept[0]) in exempt  # the parsed block still earns a per-area finding its scope exemption


def test_e2_a_seat_supplied_transit_field_stays_and_the_test_is_not_run(world):
    seat = _break_it_finding(**{break_it.TRANSIT_FIELD: True})
    got = _scrub_one(seat)
    assert got[break_it.TRANSIT_FIELD] is True
    calls = []
    _kept, runs, _e, _s = break_it.intercept([got], world.repo, world.head, runner=_spy_runner(calls))
    assert calls == [] and runs[0]["reason"] == "transit-redacted"


def test_a_stamp_that_is_not_exactly_true_does_not_stop_the_run(world):
    calls = []
    finding = _break_it_finding(**{break_it.TRANSIT_FIELD: "yes"})
    _kept, runs, _e, _s = break_it.intercept([finding], world.repo, world.head, runner=_spy_runner(calls))
    assert calls == [TEST_PATH] and runs[0]["reason"] == "stub-ran"


# --- C1: the second-test fold ----------------------------------------------------------------------------------------

def _second_test(world_, held, result):
    world_.state["_secondTestHeld"] = [{"finding": held, "note": "the test missed the path"}]
    RD._fold_second_test(world_.state, world_.state["config"], {"findings": [result]}, session_dir=str(world_.session))
    (staged,) = world_.state["_toVerify"]
    return staged


def test_c1_a_placeholder_bearing_second_test_is_not_run_with_the_reason(world):
    held = _break_it_finding(id="F1")
    result = _scrub_one(dict(_break_it_finding(_TEST_FAILING + "# " + PLACEHOLDER + "\n"), id="F1"))
    assert result[break_it.TRANSIT_FIELD] is True
    staged = _second_test(world, held, result)
    assert (staged[break_it.RUN_FIELD]["outcome"], staged[break_it.RUN_FIELD]["reason"]) == (
        "not-run", "transit-redacted")
    (run,) = world.round_record["breakItRuns"]
    assert (run["outcome"], run["reason"]) == ("not-run", "transit-redacted")
    assert world.round_record["secondTest"]["ran"] == [{"findingKey": run["findingKey"], "outcome": "not-run"}]


def test_c1_a_clean_second_test_drops_a_stale_stamp_and_runs(world):
    held = _break_it_finding(id="F1", **{break_it.TRANSIT_FIELD: True})
    result = _scrub_one(dict(_break_it_finding(), id="F1"))
    staged = _second_test(world, held, result)
    assert break_it.TRANSIT_FIELD not in staged
    assert staged[break_it.RUN_FIELD]["outcome"] != break_it.OUTCOME_NOT_RUN


# --- C2: the correction fold ------------------------------------------------------------------------------------------

def _correction_detail(w):
    (decision,) = [d for d in w.state["decisions"] if d["kind"] == "break-it-correction-none"]
    return decision["detail"]


def test_c2_a_correction_carrying_a_placeholder_is_no_correction_and_names_transit_redacted(tmp_path):
    w = TR.World(tmp_path)
    w.audit()
    w.restore()
    w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": C1._block_text(TR.CORRECTED_TEST),
                                            break_it.TRANSIT_FIELD: True}]})
    assert w.state["rounds"]["2"]["testCorrection"] == [
        {"findingKey": w.key, "outcome": "none", "reason": "transit-redacted"}]
    assert w.state["step"] == RD.P_VERIFY and w.committed() == TR.ROLE_TEST  # the restored test stands
    assert _correction_detail(w).endswith("; transit-redacted: %s" % w.key)


def test_c2_transit_redacted_wins_over_redacted_in_the_correction_fold(tmp_path):
    w = TR.World(tmp_path)
    w.audit()
    w.restore()
    w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": C1._block_text(TR.CORRECTED_TEST),
                                            break_it.TRANSIT_FIELD: True, break_it.REDACTED_FIELD: True}]})
    assert w.state["rounds"]["2"]["testCorrection"][0]["reason"] == "transit-redacted"


def test_c2_a_redacted_correction_keeps_its_reason_and_names_no_transit_key(tmp_path):
    w = TR.World(tmp_path)
    w.audit()
    w.restore()
    w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": C1._block_text(TR.CORRECTED_TEST),
                                            break_it.REDACTED_FIELD: True}]})
    assert w.state["rounds"]["2"]["testCorrection"][0]["reason"] == "redacted"
    assert "transit-redacted" not in _correction_detail(w)


# --- C3: break-it-change ----------------------------------------------------------------------------------------------

def test_c3_a_changed_test_still_carrying_a_placeholder_is_recorded_not_run_and_never_run(fx, tmp_path, monkeypatch):
    session = str(fx.session)
    AT._drive_to_verifiers(fx, AT._seats(test_role=[AT._per_area(AT._SYNTAX_ERROR)]))
    calls = []

    def stub_run_one(repo_root, head, block, **kwargs):
        calls.append(block["path"])
        return break_it._not_run(head, block, "stub-ran")

    monkeypatch.setattr(break_it, "run_one", stub_run_one)
    changed = _TEST_FAILING + "# the token was " + PLACEHOLDER + "\n"
    out = RD.cmd_break_it_change(session, "v0", AT._content_file(tmp_path, changed), AT.WHY)
    assert out["ok"] is True and calls == []
    assert (out["run"]["outcome"], out["run"]["reason"]) == ("not-run", "transit-redacted")
    ok, state = RD.load_state(session)
    assert ok
    (staged,) = state["_toVerify"]
    assert staged["suggestion"].endswith(changed)
    assert staged[break_it.RUN_FIELD] == out["run"]
    assert staged[break_it.RUNS_FIELD][-1]["reason"] == "transit-redacted"
    assert staged[break_it.RUNS_FIELD][-1]["changedWhy"] == AT.WHY
    last = state["rounds"]["1"]["breakItRuns"][-1]
    assert (last["outcome"], last["reason"], last["changedWhy"]) == ("not-run", "transit-redacted", AT.WHY)


def test_c3_a_changed_test_without_a_placeholder_is_still_run(fx, tmp_path, monkeypatch):
    session = str(fx.session)
    AT._drive_to_verifiers(fx, AT._seats(test_role=[AT._per_area(AT._SYNTAX_ERROR)]))
    calls = []
    real = break_it.run_one

    def spy_run_one(repo_root, head, block, **kwargs):
        calls.append(block["path"])
        return real(repo_root, head, block, **kwargs)

    monkeypatch.setattr(break_it, "run_one", spy_run_one)
    out = RD.cmd_break_it_change(session, "v0", AT._content_file(tmp_path, 'assert "REDACTED" == "REDACTED"\n'
                                                                 + _TEST_FAILING), AT.WHY)
    assert out["ok"] is True and calls == [AT.PER_AREA_TEST]
    assert out["run"]["outcome"] != break_it.OUTCOME_NOT_RUN


# --- D1: the review record --------------------------------------------------------------------------------------------

def test_d1_a_transit_redacted_run_reads_not_run_transit_redacted():
    run = break_it.record_run(break_it._not_run("h1", None, "transit-redacted"))
    assert (run["status"], run["reason"]) == ("not-started", "transit-redacted")
    assert review_record._run_result(run) == "not run: transit-redacted"


@pytest.mark.parametrize("run,want", [
    pytest.param({"status": "not-started", "reason": "path-mismatch"}, "did not start", id="other-reason"),
    pytest.param({"status": "not-started", "reason": None}, "did not start", id="no-reason"),
    pytest.param({"status": "not-started"}, "did not start", id="reason-absent"),
    pytest.param({"status": "ran", "exitCode": 0, "reason": "transit-redacted"}, "passed", id="ran-passed"),
    pytest.param({"status": "ran", "exitCode": 3, "reason": "transit-redacted"}, "failed (exit 3)", id="ran-failed"),
    pytest.param({"status": "timed-out", "reason": "transit-redacted"}, "timed out", id="timed-out"),
])
def test_d1_every_other_run_reads_exactly_as_before(run, want):
    assert review_record._run_result(run) == want


# --- E: the doctrine and the one home ---------------------------------------------------------------------------------

def _read(*parts):
    with open(os.path.join(_LIB, "..", *parts), encoding="utf-8") as fh:
        return fh.read()


def test_the_test_role_is_told_to_build_credentials_and_placeholder_shaped_text_at_run_time():
    text = " ".join(_read("agents", "test-role.md").split())
    assert 'A credential-like value in a break-it test is built at runtime from pieces' in text
    assert "Text shaped like a redaction placeholder" in text
    assert "is also built at run time from pieces" in text
    assert '"[" + "REDACTED]"' in text
    assert "is not run (`transit-redacted`)" in text


def test_the_reference_docs_name_the_reason_and_the_record_reading():
    loop = " ".join(_read("skills", "review-code", "reference", "auto-fix-loop.md").split())
    assert "(`transit-redacted`) and never executed" in loop and "`not run: transit-redacted`" in loop
    handback = " ".join(_read("skills", "workhorse", "reference", "handback.md").split())
    assert "`not run: transit-redacted`" in handback and "missing proof" in handback


def test_the_placeholder_pattern_has_one_home():
    sources = {os.path.basename(p): open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(_LIB, "*.py"))}
    assert "break_it.py" in sources
    homes = sorted(name for name, src in sources.items()
                   if re.search(r"\\\[REDACTED|\[\[\]REDACTED", src))
    assert homes == ["break_it.py"], homes
