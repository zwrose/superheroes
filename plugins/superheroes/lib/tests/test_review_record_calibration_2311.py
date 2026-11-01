"""The review record shows each seat's calibration read and the test-lens evidence (#2311).

A reviewer row credited from an engine record carries `calibrationRead` (the engine record's `observation.calibration`
as the runner stamped it) and its line says read, did not read, unknown, or none named. A credited row whose engine
record carries no such fact reads unmeasured, never "did not read". The record carries one `testLens` part, shown as
one `Test lens:` line; a record written before it reads unmeasured.

Edges: F1 a credited row with no observation `calibration` reads unmeasured · F2 a malformed entry is dropped and never
raises · F3 `testLens` is computed from the credited rows, never taken from the account · F4 an old record with no
`testLens`, or a row with no `calibrationRead`, reads unmeasured · F5 a session-reported row never claims a read.
"""
import copy
import hashlib

import pytest

import review_record as rr
from test_review_record import CODEX, EARLIER, GOOD_RUN, HEAD, Fake, account, build, finding, reviewer

POLICY = "2026-10-27.942777056682"
FILES = (("core", "core.md"), ("review-crew", "review-crew.md"), ("CLAUDE.md", "CLAUDE.md"))


def entry(label, file, read, policy=POLICY):
    return {"label": label, "file": file, "sha256": hashlib.sha256(file.encode()).hexdigest(),
            "policyVersion": policy, "read": read}


def cal(core="read", crew="read", claude="read", policy=POLICY):
    return [entry(label, file, read, policy) for (label, file), read in zip(FILES, (core, crew, claude))]


NONE = object()


def run(calibration=NONE, **over):
    """An engine record that credits a codex reviewer on the final commit, its observation carrying `calibration`."""
    obs = {"tokens": 100, "wallSeconds": 120, "read": "engaged"}
    if calibration is not NONE:
        obs["calibration"] = calibration
    return (dict(GOOD_RUN, observation=obs, **over), None)


def rec_of(rows, runs, **over):
    return build(account(reviewers=rows, **over), Fake(runs=runs))


def bullet(text, name):
    (line,) = [l for l in text.split("\n") if l.startswith(f"- {name}:")]
    return line


def test_three_read_entries_show_on_the_line_and_ride_the_row():
    # axis: a credited row whose engine record read all three calibration files says so, with the policy once
    rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run(cal())})
    assert rec["reviewers"][0]["calibrationRead"] == cal()
    line = bullet(rr.render(rec), "code-reviewer")
    assert line.endswith("; read its calibration: core.md, review-crew.md, CLAUDE.md (policy 2026-10-27.942777056682)")
    assert "did not read" not in line and "unmeasured" not in line


def test_a_not_read_entry_shows_did_not_read_for_that_file():
    # axis: the not-read words; an entry that reads not-read shown as read, or left off the line
    rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run(cal(crew="not-read"))})
    line = bullet(rr.render(rec), "code-reviewer")
    assert line.endswith(f"; read its calibration: core.md, CLAUDE.md; did not read review-crew.md (policy {POLICY})")


def test_an_unknown_entry_shows_unknown_and_never_did_not_read():
    # axis: the unknown words; a stream that could not tell shown as a file that went unread
    rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run(cal("unknown", "unknown", "unknown"))})
    line = bullet(rr.render(rec), "code-reviewer")
    assert line.endswith(f"; calibration read unknown for core.md, review-crew.md, CLAUDE.md (policy {POLICY})")
    assert "did not read" not in line


def test_the_three_states_say_each_part_in_file_order():
    # axis: the order of the parts and the single policy suffix when the files differ
    rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run(cal("read", "unknown", "not-read"))})
    line = bullet(rr.render(rec), "code-reviewer")
    assert line.endswith(f"; read its calibration: core.md; did not read CLAUDE.md; "
                         f"calibration read unknown for review-crew.md (policy {POLICY})")


def test_policy_versions_are_listed_once_each_and_left_off_when_there_are_none():
    # axis: the policy suffix; a repeated version, or a suffix with nothing in it
    mixed = [entry("core", "core.md", "read", "v1"), entry("review-crew", "review-crew.md", "read", "v2"),
             entry("CLAUDE.md", "CLAUDE.md", "read", "v1")]
    assert rr._calibration_words({"ran": "engine-record", "calibrationRead": mixed}) == \
        "read its calibration: core.md, review-crew.md, CLAUDE.md (policy v1, v2)"
    bare = [dict(e, policyVersion=None, sha256=None) for e in cal()]
    assert rr._calibration_words({"ran": "engine-record", "calibrationRead": bare}) == \
        "read its calibration: core.md, review-crew.md, CLAUDE.md"


def test_an_engine_record_row_with_no_calibration_reads_unmeasured_not_did_not_read():
    # axis: F1; a credited row whose engine record carries no calibration fact is unmeasured, never "did not read"
    rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run()})
    assert "calibrationRead" not in rec["reviewers"][0]
    line = bullet(rr.render(rec), "code-reviewer")
    assert line.endswith("; calibration read: unmeasured") and "did not read" not in line


def test_an_empty_calibration_list_reads_none_named_in_its_order():
    # axis: an order that named no calibration file is none named, which is not unmeasured
    rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run([])})
    assert rec["reviewers"][0]["calibrationRead"] == []
    assert bullet(rr.render(rec), "code-reviewer").endswith("; calibration read: none named in its order")


def test_malformed_entries_are_dropped_and_never_crash_the_writer():
    # axis: F2; a malformed entry is dropped, the good ones stay, and a list with no good entry is unmeasured
    good = cal()[0]
    junk = [good, "text", 7, None, {"label": "core"}, dict(good, read="maybe"), dict(good, label="other"),
            dict(good, sha256="XYZ"), dict(good, file=3), dict(good, policyVersion=4), dict(good, file="no bugs.md")]
    rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run(junk)})
    assert rec["reviewers"][0]["calibrationRead"] == [good]
    assert bullet(rr.render(rec), "code-reviewer").endswith(f"; read its calibration: core.md (policy {POLICY})")
    for bad in ([junk[1], junk[5]], "core.md", {"core": "read"}, 3, None):
        rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run(bad)})
        assert "calibrationRead" not in rec["reviewers"][0]
        assert bullet(rr.render(rec), "code-reviewer").endswith("; calibration read: unmeasured")


def test_a_row_that_did_not_run_or_was_demoted_carries_no_calibration():
    # axis: only a row credited from an engine record carries the key; a demoted row's calibration is not shown
    other = run(cal(), source="claude")
    rows = [reviewer("code-reviewer"), reviewer("test-role", ran=False, runDir=None)]
    rec = rec_of(rows, {"/run/code-reviewer": other})
    assert [v["ran"] for v in rec["reviewers"]] == ["not-run", "not-run"]
    assert all("calibrationRead" not in v for v in rec["reviewers"])
    text = rr.render(rec)
    assert "calibration read" not in text.split("Test lens:")[0].split("\n- code-reviewer")[1]
    assert rr._calibration_words(rec["reviewers"][0]) is None


def test_a_session_reported_row_never_claims_a_read():
    # axis: F5; a row with no engine record says the calibration read is not shown, even if a read is smuggled onto it
    rec = rec_of([reviewer("code-reviewer", runDir=None, calibrationRead=cal())], {})
    row = rec["reviewers"][0]
    assert row["ran"] == "reported-by-session" and "calibrationRead" not in row
    assert bullet(rr.render(rec), "code-reviewer").endswith("; calibration read: not shown (no engine record)")


def test_a_session_reported_row_that_carries_a_read_is_still_not_shown_as_read():
    # axis: F5; a row that ran with no engine record says not shown even when a calibration read is on the row
    rec = rec_of([reviewer("code-reviewer", runDir=None)], {})
    smuggled = dict(rec["reviewers"][0], calibrationRead=cal())
    assert rr._calibration_words(smuggled) == "calibration read: not shown (no engine record)"
    rec["reviewers"][0] = smuggled
    line = bullet(rr.render(rec), "code-reviewer")
    assert line.endswith("; calibration read: not shown (no engine record)") and "read its calibration" not in line


def test_a_seat_across_rounds_says_equal_words_once_and_different_words_per_round():
    # axis: the seat bullet; equal words said once, different words said round by round
    rows = [reviewer("code-reviewer (round 1)"), reviewer("code-reviewer (round 2)")]
    same = {"/run/code-reviewer (round 1)": run(cal()), "/run/code-reviewer (round 2)": run(cal())}
    line = bullet(rr.render(rec_of(rows, same)), "code-reviewer")
    assert line.count("read its calibration") == 1 and "round 1:" not in line
    differ = {"/run/code-reviewer (round 1)": run(cal(crew="not-read")), "/run/code-reviewer (round 2)": run(cal())}
    line = bullet(rr.render(rec_of(rows, differ)), "code-reviewer")
    assert line.endswith(f"; round 1: read its calibration: core.md, CLAUDE.md; did not read review-crew.md "
                         f"(policy {POLICY}); round 2: read its calibration: core.md, review-crew.md, CLAUDE.md "
                         f"(policy {POLICY})")
    unmeasured = {"/run/code-reviewer (round 1)": run(), "/run/code-reviewer (round 2)": run(cal())}
    line = bullet(rr.render(rec_of(rows, unmeasured)), "code-reviewer")
    assert "round 1: calibration read: unmeasured; round 2: read its calibration" in line


def test_a_carried_row_takes_the_held_rows_calibration_and_no_other_row_does():
    # axis: a carried row takes the earlier record's held row's calibration when it carries one, else none
    r = {"name": "test-role", "vendor": "codex", "model": CODEX, "planned": True, "ran": True, "runDir": None,
         "commit": EARLIER, "carriedFrom": EARLIER}
    held = {"name": "test-role", "vendor": "codex", "model": CODEX, "coversFinalCommit": True,
            "ran": "engine-record", "family": "openai", "calibrationRead": cal()}

    def carried(held_row):
        return rr._reviewer(r, Fake().readers(), [], HEAD, lane_value="full", maker_families=frozenset(),
                            carry=(None, {"reviewers": [held_row]}))
    row = carried(held)
    assert "carried" in row and row["calibrationRead"] == cal()
    assert rr._calibration_words(row).startswith("read its calibration: core.md")
    bare = carried({k: v for k, v in held.items() if k != "calibrationRead"})
    assert "carried" in bare and "calibrationRead" not in bare
    assert rr._calibration_words(bare) == "calibration read: unmeasured"
    assert "calibrationRead" not in carried(dict(held, calibrationRead=[{"label": "core"}]))


def test_a_test_role_row_that_ran_gives_the_test_lens_part_and_line():
    # axis: the part is computed from the rows: ran, commit, covers, calibration, findings across every test-lens row
    rows = [reviewer("test-role (round 1)", commit=EARLIER), reviewer("test-role (round 2)"),
            reviewer("code-reviewer")]
    runs = {"/run/test-role (round 1)": run(cal(crew="not-read"), viewHeadSha=EARLIER),
            "/run/test-role (round 2)": run(cal()), "/run/code-reviewer": run()}
    found = [finding("t1", reviewer="test-role (round 1)"), finding("t2", reviewer="test-role (round 2)"),
             finding("t3", reviewer="test-role (round 2)"), finding("c1", reviewer="code-reviewer")]
    rec = rec_of(rows, runs, findings=found)
    part = rec["testLens"]
    assert part == {"listed": True, "ran": True, "ranFrom": "engine-record", "row": "test-role (round 2)",
                    "commit": HEAD, "coversFinalCommit": True, "calibrationRead": cal(), "findings": 3}
    assert rec["reviewers"][0]["coversFinalCommit"] is False
    (line,) = [l for l in rr.render(rec).split("\n") if l.startswith("Test lens:")]
    assert line == (f"Test lens: ran on {HEAD[:7]} (engine record), the final commit; read its calibration: "
                    f"core.md, review-crew.md, CLAUDE.md (policy {POLICY}); 3 findings raised.")


def test_a_carried_test_role_row_reads_carried_not_ran_on_the_final_commit():
    # axis: a carried test-role row covers the final commit without a run on it; the line says carried from the earlier commit
    row = {"name": "test-role", "ran": "engine-record", "commit": EARLIER, "coversFinalCommit": True,
           "carried": {"commit": EARLIER}}
    part = rr._test_lens([row], [], HEAD)
    assert part["carried"] == {"commit": EARLIER} and part["coversFinalCommit"] is True
    line = rr._test_lens_line({"testLens": part, "reviewers": [row]})
    assert line.startswith(f"Test lens: carried from the earlier review of {EARLIER[:7]} (engine record), "
                           "not run in this round; it covers the final commit;")
    assert "ran on" not in line and ", the final commit" not in line
    plain = dict(row, commit=HEAD)
    plain.pop("carried")
    assert "carried" not in rr._test_lens([plain], [], HEAD)


def test_findings_labelled_by_dimension_or_bare_seat_count_for_the_test_lens():
    # axis: the session writer labels a finding by its dimension (`Test`, merged `Code, Test`) or bare seat, never the row's round suffix
    rows = [reviewer("test-role (round 1)"), reviewer("code-reviewer")]
    runs = {"/run/test-role (round 1)": run(cal()), "/run/code-reviewer": run()}
    found = [finding("a", reviewer="Test"), finding("b", reviewer="Code, Test"), finding("c", reviewer="test-role"),
             finding("d", reviewer="Code"), finding("e", reviewer="Testing")]
    assert rec_of(rows, runs, findings=found)["testLens"]["findings"] == 3


def test_the_chosen_row_is_the_last_one_covering_the_final_commit_not_the_first_that_ran():
    # axis: the chosen-row rule; an earlier-commit row that ran first, or a later one that does not cover, taking the part
    early_first = [reviewer("test-role (round 1)", commit=EARLIER), reviewer("test-role (round 2)")]
    runs = {"/run/test-role (round 1)": run(cal("not-read", "not-read", "not-read"), viewHeadSha=EARLIER),
            "/run/test-role (round 2)": run(cal())}
    part = rec_of(early_first, runs)["testLens"]
    assert (part["row"], part["commit"], part["coversFinalCommit"]) == ("test-role (round 2)", HEAD, True)
    covering_first = [reviewer("test-role (round 1)"), reviewer("test-role (round 2)", commit=EARLIER)]
    runs = {"/run/test-role (round 1)": run(cal()),
            "/run/test-role (round 2)": run(cal("not-read", "not-read", "not-read"), viewHeadSha=EARLIER)}
    rec = rec_of(covering_first, runs)
    part = rec["testLens"]
    assert (part["row"], part["coversFinalCommit"], part["calibrationRead"]) == ("test-role (round 1)", True, cal())
    # none covers: the last row that ran, and the line says it is not the final commit
    neither = [reviewer("test-role (round 1)", commit=EARLIER), reviewer("test-role (round 2)", commit=EARLIER)]
    runs = {"/run/test-role (round 1)": run(cal(), viewHeadSha=EARLIER),
            "/run/test-role (round 2)": run(cal(crew="unknown"), viewHeadSha=EARLIER)}
    rec = rec_of(neither, runs)
    assert (rec["testLens"]["row"], rec["testLens"]["coversFinalCommit"]) == ("test-role (round 2)", False)
    (line,) = [l for l in rr.render(rec).split("\n") if l.startswith("Test lens:")]
    assert line.startswith(f"Test lens: ran on {EARLIER[:7]} (engine record), not the final commit; read its "
                           f"calibration: core.md, CLAUDE.md; calibration read unknown for review-crew.md")
    assert line.endswith("; 0 findings raised.")


def test_a_sliced_test_seat_is_a_test_lens_row_and_a_phase_stem_row_is_not():
    # axis: the test-lens mapping is the reviewer header's; a slice seat counts, a second-test stem row does not
    rows = [reviewer("test-role:src (round 1)"), reviewer("second-test test-role (round 1)")]
    rec = rec_of(rows, {"/run/test-role:src (round 1)": run(cal()), "/run/second-test test-role (round 1)": run()})
    assert rec["testLens"]["row"] == "test-role:src (round 1)"
    rec = rec_of([reviewer("second-test test-role (round 1)")], {"/run/second-test test-role (round 1)": run()})
    assert rec["testLens"] == {"listed": False}


def test_no_test_role_row_says_none_was_listed_and_a_row_that_did_not_run_says_so():
    # axis: the listed and did-not-run words; the three states of the part told apart
    rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run()})
    assert rec["testLens"] == {"listed": False}
    assert "Test lens: no test-role reviewer was listed." in rr.render(rec).split("\n")
    rec = rec_of([reviewer("code-reviewer"), reviewer("test-role", ran=False, runDir=None)],
                 {"/run/code-reviewer": run()}, findings=[finding("t1", reviewer="test-role")])
    assert rec["testLens"] == {"listed": True, "ran": False, "ranFrom": None, "row": None, "commit": None,
                               "coversFinalCommit": False, "calibrationRead": None, "findings": 1}
    assert "Test lens: did not run." in rr.render(rec).split("\n")


def test_a_test_role_row_reported_by_the_session_never_claims_a_calibration_read():
    # axis: F5; the part and the line for a session-reported test-lens row say not shown, even with a read smuggled in
    rec = rec_of([reviewer("test-role", runDir=None, calibrationRead=cal())], {}, testLens={"listed": False})
    part = rec["testLens"]
    assert (part["ranFrom"], part["calibrationRead"], part["coversFinalCommit"]) == ("reported-by-session", None, True)
    lines = rr.render(rec).split("\n")
    assert f"Test lens: ran on {HEAD[:7]} (reported by the session), the final commit; " \
           "calibration read: not shown (no engine record); 0 findings raised." in lines
    smuggled = copy.deepcopy(rec)
    smuggled["reviewers"][0]["calibrationRead"] = cal()
    smuggled["testLens"]["calibrationRead"] = cal()
    text = rr.render(smuggled)
    assert "read its calibration" not in text.split("\n</details>")[0].split("<details>")[0]
    assert "calibration read: not shown (no engine record)" in rr._test_lens_line(smuggled)


def test_the_test_lens_part_is_computed_not_taken_from_the_account():
    # axis: F3; an account that claims a test lens ran changes nothing in the part
    claim = {"listed": True, "ran": True, "coversFinalCommit": True, "findings": 9}
    rec = rec_of([reviewer("code-reviewer")], {"/run/code-reviewer": run()}, testLens=claim)
    assert rec["testLens"] == {"listed": False}
    rec = rec_of([reviewer("test-role", ran=False, runDir=None)], {}, testLens=claim)
    assert rec["testLens"]["ran"] is False and rec["testLens"]["findings"] == 0


def test_a_record_written_before_this_change_reads_unmeasured_and_never_did_not_read():
    # axis: F4; no testLens on the record and no calibrationRead on the rows read unmeasured, not did-not-run, not did-not-read
    rec = rec_of([reviewer("test-role"), reviewer("code-reviewer")],
                 {"/run/test-role": run(cal()), "/run/code-reviewer": run(cal())})
    old = copy.deepcopy(rec)
    del old["testLens"]
    for v in old["reviewers"]:
        v.pop("calibrationRead")
    for level in (0, 1, 2):
        text = rr._summary(old, level)
        assert "Test lens: unmeasured (the record predates the test-lens part)." in text.split("\n")
        assert "did not read" not in text and "Test lens: did not run" not in text
    text = rr.render(old)
    assert bullet(text, "test-role").endswith("; calibration read: unmeasured")
    assert bullet(text, "code-reviewer").endswith("; calibration read: unmeasured")
    assert "did not read" not in text
    for odd in ("junk", None, 3, []):
        assert rr._test_lens_line(dict(old, testLens=odd)) == \
            "Test lens: unmeasured (the record predates the test-lens part)."


def test_the_test_lens_line_is_in_every_summary_level_after_the_reviewer_lines():
    # axis: the line shows at levels 0 to 2, right after the reviewer bullets or the level-2 count line
    rec = rec_of([reviewer("test-role"), reviewer("code-reviewer")],
                 {"/run/test-role": run(cal()), "/run/code-reviewer": run(cal())})
    for level in (0, 1, 2):
        lines = rr._summary(rec, level).split("\n")
        at = next(i for i, l in enumerate(lines) if l.startswith("Test lens:"))
        assert lines[at - 1].startswith("- code-reviewer:" if level < 2 else "Reviewers: 2 rows across 2 seats")


def test_the_new_keys_and_words_are_not_secret_shaped():
    # axis: the record's secret-key scrubber never fires on the new keys; the calibration survives a render and read-back
    for key in ("calibrationRead", "testLens", "policyVersion", "sha256", "label", "file", "read", "listed", "ranFrom",
                "findings", "coversFinalCommit", "row", "commit", "ran"):
        assert not rr._secret_key(key), key
    rec = rec_of([reviewer("test-role")], {"/run/test-role": run(cal())})
    posted = rr._parse_body(rr.render(rec))
    assert posted["reviewers"][0]["calibrationRead"] == cal()
    assert posted["testLens"] == rec["testLens"]


def _many(count=12):
    rows, runs = [], {}
    for i in range(count):
        d = f"/run/r{i:02d}/".ljust(140, "d")
        obs = {"tokens": 1000 + i, "toolCalls": 40 + i, "wallSeconds": 120 + i, "source": "codex",
               "read": "engaged", "calibration": cal(), "telemetry": {"notes": "n" * 400, "tail": "t" * 200}}
        runs[d] = (dict(GOOD_RUN, observation=obs), None)
        rows.append(reviewer(f"reviewer-{i:02d}", runDir=d))
    d = "/run/test-role/".ljust(140, "d")
    runs[d] = (dict(GOOD_RUN, observation={"read": "engaged", "toolCalls": 3, "calibration": cal(crew="not-read"),
                                           "telemetry": {"notes": "n" * 400}}), None)
    rows.append(reviewer("test-role", runDir=d))
    return rec_of(rows, runs, findings=[finding("t1", reviewer="test-role")])


def test_the_shed_steps_leave_the_calibration_read_and_the_test_lens_alone(monkeypatch):
    # axis: a trimmed record keeps calibrationRead on every row and the testLens part, at the deepest shed level
    rec = _many()
    shed = rr._shed_run_dir(rr._shed_observation(rec))
    assert [v.get("calibrationRead") for v in shed["reviewers"]] == [v["calibrationRead"] for v in rec["reviewers"]]
    assert shed["testLens"] == rec["testLens"] and all(v["runDir"] is None for v in shed["reviewers"])
    with monkeypatch.context() as m:
        m.setattr(rr, "_SHED_STEPS", ())
        m.setattr(rr, "MAX_BODY_CHARS", 10 ** 9)
        fits = len(rr.render(dict(shed, reviewerShed=["observation", "runDir"])))
        assert len(rr.render(rec)) > fits
        m.setattr(rr, "MAX_BODY_CHARS", fits)
        body = rr.render(rec)
    posted = rr._parse_body(body)
    assert posted["reviewerShed"] == ["observation", "runDir"]
    assert [v["calibrationRead"] for v in posted["reviewers"]] == [v["calibrationRead"] for v in rec["reviewers"]]
    assert posted["testLens"] == rec["testLens"]
    assert bullet(body, "test-role").endswith(f"; read its calibration: core.md, CLAUDE.md; did not read "
                                              f"review-crew.md (policy {POLICY})")
    assert f"Test lens: ran on {HEAD[:7]} (engine record), the final commit; read its calibration" in body
    assert body.split("\n").index("Reviewer detail trimmed to fit this comment (engine telemetry and run directories); "
                                  "the engines' own run records hold the full output.") > 0
