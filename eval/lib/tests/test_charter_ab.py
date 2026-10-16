"""Deterministic tests for eval/charter-ab/ab.py. No test calls a model: exec_seat/exec_judge are replaced."""
import importlib.util
import json
import os
import random
import re
import signal
import subprocess
import sys
from pathlib import Path

import pytest

_AB_PATH = Path(__file__).resolve().parents[2] / "charter-ab" / "ab.py"
_spec = importlib.util.spec_from_file_location("charter_ab", _AB_PATH)
ab = importlib.util.module_from_spec(_spec)
sys.modules["charter_ab"] = ab
_spec.loader.exec_module(ab)

_REAL_EXEC_JUDGE = ab.exec_judge

SEED_PROMPT = (
    "You are the superheroes showrunner advisor for this repository. First read "
    "plugins/superheroes/skills/showrunner/SKILL.md in full, and read any reference file it "
    "tells you to read for this situation. Then answer in at most 150 words: what you do next, "
    "step by step, and which rule (file and section) governs it. Do not edit anything. "
    "Situation: {situation} Question: {question}"
)
SIDE_DIRS = {"base": "/wt/base", "candidate": "/wt/candidate"}


@pytest.fixture(autouse=True)
def no_models(monkeypatch):
    def boom(*args, **kwargs):
        pytest.fail("a model CLI (claude/codex) would have been called")
    monkeypatch.setattr(ab, "exec_seat", boom)
    monkeypatch.setattr(ab, "exec_judge", boom)


@pytest.fixture
def git_env(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


# ---------------------------------------------------------------- helpers

def per(sid, base, cand, complete=True):
    return {"id": sid, "complete": complete, "base": base, "candidate": cand}


def make_ident(reps=1, **over):
    d = {"base_ref": "b", "base_sha": "a" * 40, "candidate_ref": "c", "candidate_sha": "b" * 40,
         "charter": "CHARTER.md", "scenarios_file": "/x/s.json", "scenarios_sha256": "0" * 64,
         "role": "the tester", "model": "opus", "judge_model": "gpt-6.1-sol", "replicates": reps, "seed": 7,
         "plugin_dir": None}
    d.update(over)
    return d


def scen(sid):
    return {"id": sid, "situation": f"situation of {sid}", "question": f"question of {sid}",
            "expected_rule": f"rule of {sid}", "targeted_block": f"block of {sid}"}


def judge_line(reps, correct=True, diff="same", note="n"):
    return json.dumps({"correct": {l: correct for l in ab.labels(reps)}, "sources_differ": diff, "note": note})


def write_judged(run_dir, sc, m, reps, text=None):
    prompt = ab.render_judge(str(run_dir), sc, m, reps)
    out, _, shap = ab.judge_paths(str(run_dir), sc["id"])
    Path(out).write_text(text if text is not None else judge_line(reps))
    Path(shap).write_text(ab.sha256_text(prompt))


def build_run(tmp_path, reps=1, ids=("s1", "s2"), judged=True):
    """A tiny run dir: sides.json, answers for both sides, mapping, and (optionally) bound judge outputs."""
    run_dir = tmp_path / "run"
    (run_dir / "answers").mkdir(parents=True)
    (run_dir / "judge").mkdir()
    ident = make_ident(reps)
    (run_dir / "sides.json").write_text(json.dumps(ident))
    scenarios = [scen(i) for i in ids]
    for sc in scenarios:
        for side in ab.SIDES:
            for k in range(1, reps + 1):
                Path(ab.ans_path(str(run_dir), sc["id"], side, k)).write_text(f"answer {sc['id']} {side} {k}\n")
    mapping = ab.make_mapping(list(ids), reps, ident["seed"])
    (run_dir / "judge" / "mapping.json").write_text(json.dumps(mapping))
    if judged:
        for sc in scenarios:
            write_judged(run_dir, sc, mapping[sc["id"]], reps)
    return str(run_dir), scenarios, ident, mapping


def fake_judge_all_correct(calls):
    def fake(cmd, prompt):
        calls.append(prompt)
        found = re.findall(r"^## Answer (\d+[AB])$", prompt, re.M)
        return 0, json.dumps({"correct": {l: True for l in found}, "sources_differ": "same", "note": "ok"}), ""
    return fake


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def g(*args):
        return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                               *args], check=True, capture_output=True, text=True).stdout.strip()
    g("init", "-q")
    (repo / "CHARTER.md").write_text("the charter\n")
    g("add", ".")
    g("commit", "-q", "-m", "c1")
    return repo, g("rev-parse", "HEAD")


def write_scenarios(tmp_path, ids=("e1", "e2")):
    p = tmp_path / "scen.json"
    p.write_text(json.dumps({"role": "the tester", "scenarios": [scen(i) for i in ids]}))
    return str(p)


def worktree_count(repo):
    out = subprocess.run(["git", "-C", str(repo), "worktree", "list", "--porcelain"], capture_output=True,
                         text=True, check=True).stdout
    return out.count("worktree ")


# ---------------------------------------------------------------- 1-4 verdict rule

def test_verdict_minus_one_bound():
    assert ab.verdict([per("a", 3, 1)], 3)["verdict"] == "FAIL"
    assert ab.verdict([per("a", 3, 2)], 3)["verdict"] == "PASS"
    assert ab.verdict([per("a", 1, 0)], 3)["verdict"] == "PASS"
    # the 2-of-3 rule also fires on 3/1, so only the minus-1 reason text isolates the minus-1 bound
    assert any("< BASE" in r for r in ab.scenario_flags(3, 1, 3)) and not ab.scenario_flags(3, 2, 3)
    assert ab.verdict([per("a", 3, 1)], 3)["failing"][0]["id"] == "a"


def test_two_of_three_rule():
    # base 2 / cand 1 is inside the minus-1 bound but candidate is wrong 2 of 3 while base is right 2 of 3
    assert ab.verdict([per("a", 2, 1)], 3)["verdict"] == "FAIL"
    reasons = ab.verdict([per("a", 2, 1)], 3)["failing"][0]["reasons"]
    assert len(reasons) == 1 and "wrong 2/3" in reasons[0]
    assert ab.verdict([per("a", 1, 1)], 3)["verdict"] == "PASS"


def test_both_wrong_reported_not_failing():
    v = ab.verdict([per("a", 0, 0), per("b", 3, 3)], 3)
    assert v["both_wrong"] == ["a"]
    assert v["verdict"] == "PASS" and v["failing"] == []


def test_incomplete_dominates_and_empty_is_incomplete():
    assert ab.verdict([per("a", None, None, complete=False), per("b", 3, 3)], 3)["verdict"] == "INCOMPLETE"
    v = ab.verdict([per("a", None, None, complete=False), per("b", 3, 0)], 3)
    assert v["verdict"] == "INCOMPLETE" and v["incomplete"] == ["a"]
    assert ab.verdict([], 3)["verdict"] == "INCOMPLETE"
    # claimed complete but no counts: still not a PASS
    assert ab.verdict([per("a", None, None, complete=True)], 3)["verdict"] == "INCOMPLETE"


# ---------------------------------------------------------------- 5 parse_judge

def test_parse_judge_rejects_malformed():
    reps = 2
    good = judge_line(reps, diff="minor-difference")
    d = ab.parse_judge("preamble\n" + good + "\n", reps)
    assert d["sources_differ"] == "minor-difference" and set(d["correct"]) == set(ab.labels(reps))
    labs = ab.labels(reps)
    all_true = {l: True for l in labs}

    def line(correct, diff="same"):
        return json.dumps({"correct": correct, "sources_differ": diff, "note": "x"})
    assert ab.parse_judge('{"correct": {"1A": tru}, "sources_differ": "same"}', reps) is None  # malformed JSON
    assert ab.parse_judge(line({l: True for l in labs[:-1]}), reps) is None  # missing label
    assert ab.parse_judge(line(dict(all_true, **{"3A": True})), reps) is None  # extra label
    assert ab.parse_judge(line(dict(all_true, **{"1A": "yes"})), reps) is None  # non-bool value
    assert ab.parse_judge(line(all_true, diff="whatever"), reps) is None  # unknown sources_differ
    assert ab.parse_judge("", reps) is None
    first, last = judge_line(reps, correct=True, note="first"), judge_line(reps, correct=False, note="last")
    assert ab.parse_judge(first + "\n" + last, reps)["note"] == "last"
    assert ab.parse_judge(first + "\n" + line({"1A": True}), reps)["note"] == "first"  # a later invalid one is skipped


def test_parse_judge_is_order_and_brace_independent():
    reps, labs = 1, ab.labels(1)

    def obj(correct, note="n", diff="same", first_diff=False):
        c = {l: correct for l in labs}
        parts = [("sources_differ", diff), ("correct", c), ("note", note)] if first_diff else \
            [("correct", c), ("sources_differ", diff), ("note", note)]
        return json.dumps(dict(parts))
    assert ab.parse_judge(obj(True, first_diff=True), reps)["sources_differ"] == "same"  # reordered keys
    assert ab.parse_judge(obj(True, note="see {head_sha} and {}"), reps)["note"] == "see {head_sha} and {}"
    draft, fix = obj(True, note="draft"), obj(False, note="fix", first_diff=True)
    assert ab.parse_judge("draft:\n" + draft + "\nfinal:\n" + fix, reps)["note"] == "fix"  # correction wins
    for junk in ("{{{{", "}{ not json {", '{"correct": {', "[]", "null {}"):
        assert ab.parse_judge(junk, reps) is None


def test_worktree_paths_never_reach_the_judge_prompt(tmp_path):
    run_dir, scenarios, ident, mapping = build_run(tmp_path, judged=False)
    roots = ["/tmp/charter-ab-wt-Q1/base", "/private/tmp/charter-ab-wt-Q1/candidate"]
    Path(run_dir, "worktrees.json").write_text(json.dumps(roots))
    Path(ab.ans_path(run_dir, "s1", "base", 1)).write_text(f"see {roots[0]}/plugins/x.md and {roots[1]}/y.md\n")
    prompt = ab.render_judge(run_dir, scenarios[0], mapping["s1"], 1)
    assert "<worktree>/plugins/x.md" in prompt and "<worktree>/y.md" in prompt
    assert "charter-ab-wt" not in prompt and "/base" not in prompt and "/candidate" not in prompt


def test_forced_rerun_removes_saved_reports_first(tmp_path, monkeypatch):
    run_dir, scenarios, ident, _ = build_run(tmp_path)
    assert ab.stage_report(run_dir, scenarios, ident) == 0
    assert Path(run_dir, "verdict.json").exists()
    monkeypatch.setattr(ab, "exec_seat", lambda c, w, e: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        with pytest.raises(KeyboardInterrupt):
            ab.stage_seats(run_dir, SIDE_DIRS, scenarios, ident, True, 1, "/cfg")
    finally:
        ab._STOPPING.clear()
    assert not Path(run_dir, "verdict.json").exists() and not Path(run_dir, "results.md").exists()


# ---------------------------------------------------------------- 6 report never PASSes on a bad judge

def test_malformed_judge_output_makes_report_incomplete(tmp_path):
    run_dir, scenarios, ident, mapping = build_run(tmp_path, judged=False)
    for sc in scenarios:  # a hash that matches the prompt, so only the unparseable output can block
        out, _, shap = ab.judge_paths(run_dir, sc["id"])
        Path(out).write_text("garbage, not a judgement")
        Path(shap).write_text(ab.sha256_text(ab.render_judge(run_dir, sc, mapping[sc["id"]], 1)))
    code = ab.stage_report(run_dir, scenarios, ident)
    assert code == ab.EXIT_BY_VERDICT["INCOMPLETE"] == 2
    v = json.loads(Path(run_dir, "verdict.json").read_text())
    assert v["verdict"] == "INCOMPLETE" and v["incomplete"] == ["s1", "s2"]
    assert "INCOMPLETE" in Path(run_dir, "results.md").read_text()


def test_fully_bound_run_reports_pass(tmp_path):
    run_dir, scenarios, ident, _ = build_run(tmp_path)
    assert ab.stage_report(run_dir, scenarios, ident) == 0
    v = json.loads(Path(run_dir, "verdict.json").read_text())
    assert v["verdict"] == "PASS" and v["identity"]["model"] == "opus"
    assert "| s1 |" in Path(run_dir, "results.md").read_text()


def test_asymmetric_scores_reach_totals_and_fail_verdict(tmp_path):
    reps = 3
    run_dir, scenarios, ident, mapping = build_run(tmp_path, reps=reps, ids=("s1",), judged=False)
    sc, m = scenarios[0], mapping["s1"]
    correct = {f"{k}{lab}": m["replicates"][str(k)][lab] == "base" for k in range(1, reps + 1) for lab in "AB"}
    write_judged(run_dir, sc, m, reps, text=json.dumps({"correct": correct, "sources_differ": "same", "note": "n"}))
    rec = ab.completeness(run_dir, scenarios, mapping, reps)[0]
    assert rec["complete"] and rec["base"] == 3 and rec["candidate"] == 0
    assert ab.stage_report(run_dir, scenarios, ident) == 1
    v = json.loads(Path(run_dir, "verdict.json").read_text())
    assert v["verdict"] == "FAIL" and [f["id"] for f in v["failing"]] == ["s1"]


def test_populated_run_dir_without_sides_json_refused(tmp_path, monkeypatch, git_env):
    repo, _ = make_repo(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    run_dir = tmp_path / "run"
    (run_dir / "answers").mkdir(parents=True)
    (run_dir / "answers" / "e1.base.r1.txt").write_text("old answer\n")
    for sides in (None, "{not json"):
        if sides is not None:
            (run_dir / "sides.json").write_text(sides)
        assert ab.main(["seats", "--repo", str(repo), "--candidate", "HEAD", "--base", "HEAD", "--charter",
                        "CHARTER.md", "--scenarios", write_scenarios(tmp_path), "--run-dir", str(run_dir)]) == 3
    assert (run_dir / "sides.json").read_text() == "{not json"
    for stage in ("judge", "report"):
        assert ab.main([stage, "--repo", str(repo), "--run-dir", str(run_dir)]) == 3


# ---------------------------------------------------------------- 7 unmap, make_mapping

def test_unmap_inverts_labels():
    entry = {"replicates": {"1": {"A": "base", "B": "candidate"}, "2": {"A": "candidate", "B": "base"}},
             "X": "base", "Y": "candidate"}
    judged = {"1A": True, "1B": False, "2A": False, "2B": True}
    assert ab.unmap(entry, judged, 2) == {"base": [True, True], "candidate": [False, False]}
    judged = {"1A": True, "1B": False, "2A": True, "2B": False}
    assert ab.unmap(entry, judged, 2) == {"base": [True, False], "candidate": [False, True]}
    with pytest.raises(ValueError):
        ab.unmap(entry, {"1A": True, "1B": True, "2A": True}, 2)
    with pytest.raises(ValueError):
        ab.unmap(entry, dict(judged, **{"3A": True}), 2)


def test_make_mapping_deterministic_and_balanced():
    ids, reps = ["s1", "s2", "s3"], 3
    m = ab.make_mapping(ids, reps, 1882)
    assert m == ab.make_mapping(ids, reps, 1882)
    for e in m.values():
        assert set(e["replicates"]) == {"1", "2", "3"} and {e["X"], e["Y"]} == set(ab.SIDES)
        for ab_map in e["replicates"].values():
            assert {ab_map["A"], ab_map["B"]} == set(ab.SIDES)
    rng = random.Random(1882)  # the seed's draw order, with its "trim" side now called "candidate"
    expect = {}
    for sid in ids:
        per_rep = {}
        for k in range(1, reps + 1):
            per_rep[str(k)] = ({"A": "base", "B": "candidate"} if rng.random() < 0.5
                               else {"A": "candidate", "B": "base"})
        x = "base" if rng.random() < 0.5 else "candidate"
        expect[sid] = {"replicates": per_rep, "X": x, "Y": "candidate" if x == "base" else "base"}
    assert m == expect


# ---------------------------------------------------------------- 8-9 seats: resume and admission

def test_resume_keeps_existing_answer_unless_force(tmp_path, monkeypatch):
    run_dir, scenarios, ident, _ = build_run(tmp_path, judged=False)
    sc, path = scenarios[0], ab.ans_path(run_dir, "s1", "base", 1)
    before = Path(path).read_text()
    calls = []

    def fake(cmd, cwd, env):
        calls.append((cmd, cwd, env))
        return 0, "fresh answer", ""
    monkeypatch.setattr(ab, "exec_seat", fake)
    r = ab.run_seat(run_dir, SIDE_DIRS, sc, "base", 1, False, ident, "/cfg")
    assert calls == [] and r["skipped"] and Path(path).read_text() == before
    r = ab.run_seat(run_dir, SIDE_DIRS, sc, "base", 1, True, ident, "/cfg")
    assert len(calls) == 1 and not r["skipped"] and Path(path).read_text() == "fresh answer"
    cmd, cwd, env = calls[0]
    assert cmd[:8] == ["claude", "-p", "--model", "opus", "--allowedTools", "Read,Grep,Glob", "--output-format",
                       "text"]
    assert cmd[8] == ab.render_prompt("the tester", "CHARTER.md", sc["situation"], sc["question"])
    assert cwd == "/wt/base" and env["CLAUDE_CONFIG_DIR"] == "/cfg"


def test_seat_argv_binds_plugin_dir_to_its_side(tmp_path, monkeypatch):
    run_dir, scenarios, ident, _ = build_run(tmp_path, judged=False)
    ident, sc, calls = dict(ident, plugin_dir="plugins/x"), scenarios[0], []

    def fake(cmd, cwd, env):
        calls.append((cmd, cwd))
        return 0, "fresh answer", ""
    monkeypatch.setattr(ab, "exec_seat", fake)
    for side in ab.SIDES:  # rep 2 has no existing answer, so each call really runs the seat
        assert ab.run_seat(run_dir, SIDE_DIRS, sc, side, 2, False, ident, "/cfg")["ok"]
    assert [cwd for _, cwd in calls] == [SIDE_DIRS["base"], SIDE_DIRS["candidate"]]
    for (cmd, cwd), side in zip(calls, ab.SIDES):
        assert cmd.count("--plugin-dir") == 1
        i = cmd.index("--plugin-dir")
        assert cmd[i - 2:i] == ["--model", "opus"]
        assert cmd[i + 1] == os.path.join(SIDE_DIRS[side], "plugins/x")
        assert cmd[i + 2] == "--allowedTools"
        assert cmd[-1] == ab.render_prompt("the tester", "CHARTER.md", sc["situation"], sc["question"])


def test_failed_call_publishes_no_answer(tmp_path, monkeypatch):
    run_dir, scenarios, ident, _ = build_run(tmp_path, judged=False)
    sc, path = scenarios[0], ab.ans_path(run_dir, "s1", "base", 1)

    def timeout(cmd, cwd, env):
        raise subprocess.TimeoutExpired(cmd, 1)
    behaviours = {"nonzero exit with output": lambda c, w, e: (1, "partial answer", "boom"),
                  "exit 0 but blank": lambda c, w, e: (0, "  \n", ""),
                  "timeout": timeout}
    for name, fake in behaviours.items():
        if os.path.exists(path):
            os.unlink(path)
        monkeypatch.setattr(ab, "exec_seat", fake)
        r = ab.run_seat(run_dir, SIDE_DIRS, sc, "base", 1, False, ident, "/cfg")
        assert not os.path.exists(path), name
        assert r["ok"] is False and r["attempts"] == 2, name
        assert os.path.exists(path + ".fail1.err") and os.path.exists(path + ".fail2.err"), name
        if name == "nonzero exit with output":
            assert "partial answer" in Path(path + ".fail2.err").read_text()  # kept for diagnosis only


# ---------------------------------------------------------------- 10 judge binding

def test_judge_binding_follows_answer_content(tmp_path, monkeypatch):
    run_dir, scenarios, ident, mapping = build_run(tmp_path)
    calls = []
    monkeypatch.setattr(ab, "exec_judge", fake_judge_all_correct(calls))
    ab.stage_judge(run_dir, scenarios, ident, False, 1)
    assert calls == []  # bound outputs are reused
    assert ab.stage_report(run_dir, scenarios, ident) == 0

    side = mapping["s1"]["replicates"]["1"]["A"]
    Path(ab.ans_path(run_dir, "s1", side, 1)).write_text("a different answer now\n")
    done = {p["id"]: p["complete"] for p in ab.completeness(run_dir, scenarios, mapping, 1)}
    assert done == {"s1": False, "s2": True}
    assert ab.stage_report(run_dir, scenarios, ident) == 2

    ab.stage_judge(run_dir, scenarios, ident, False, 1)
    assert len(calls) == 1 and "a different answer now" in calls[0]  # only the changed scenario re-judged
    assert ab.stage_report(run_dir, scenarios, ident) == 0


# ---------------------------------------------------------------- 11 identity

def test_identity_mismatch_names_guarded_keys():
    stored = make_ident(3)
    assert ab.identity_mismatch(stored, dict(stored)) == []
    for key, new in (("model", "sonnet"), ("judge_model", "other"), ("candidate_sha", "c" * 40),
                     ("replicates", 5), ("scenarios_sha256", "1" * 64), ("seed", 1), ("plugin_dir", "plugins/x"), ("claude_config_dir", "/other")):
        assert ab.identity_mismatch(stored, dict(stored, **{key: new})) == [key]
    assert ab.identity_mismatch(dict(stored, plugin_dir="plugins/x"), stored) == ["plugin_dir"]
    moved = dict(stored, base_ref="x", candidate_ref="y", scenarios_file="/elsewhere.json")
    assert ab.identity_mismatch(stored, moved) == []


# ---------------------------------------------------------------- 12-13 refusals

def test_config_dir_refusal_precedes_any_worktree(tmp_path, monkeypatch, git_env, capsys):
    repo, _ = make_repo(tmp_path)
    real_run = subprocess.run

    def guarded(cmd, *args, **kwargs):
        if "worktree" in cmd:
            pytest.fail(f"git worktree was called before the CLAUDE_CONFIG_DIR refusal: {cmd}")
        return real_run(cmd, *args, **kwargs)
    monkeypatch.setattr(subprocess, "run", guarded)
    argv = ["seats", "--repo", str(repo), "--candidate", "HEAD", "--base", "HEAD", "--charter", "CHARTER.md",
            "--scenarios", write_scenarios(tmp_path), "--run-dir", str(tmp_path / "run")]
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert ab.main(argv) == 3
    assert "CLAUDE_CONFIG_DIR" in capsys.readouterr().err
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "")
    assert ab.main(["run"] + argv[1:]) == 3
    assert not (tmp_path / "run").exists()


def test_run_dir_inside_repo_refused(tmp_path, monkeypatch, git_env, capsys):
    repo, _ = make_repo(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    inside_dir = repo / "out" / "run"
    argv = ["seats", "--repo", str(repo), "--candidate", "HEAD", "--base", "HEAD", "--charter", "CHARTER.md",
            "--scenarios", write_scenarios(tmp_path), "--run-dir", str(inside_dir)]
    assert ab.main(argv) == 3
    assert "inside the repo" in capsys.readouterr().err
    assert not inside_dir.exists()
    assert worktree_count(repo) == 1


# ---------------------------------------------------------------- 14 prompt identity

def test_seat_prompt_matches_seed_byte_for_byte():
    role, scenarios, _ = ab.load_scenarios(str(_AB_PATH.parent / "scenarios" / "showrunner.json"))
    assert role == "the superheroes showrunner advisor"
    assert ab.DEFAULT_CHARTER == "plugins/superheroes/skills/showrunner/SKILL.md"
    assert len(scenarios) == 15
    for sc in scenarios:
        assert ab.render_prompt(role, ab.DEFAULT_CHARTER, sc["situation"], sc["question"]) == \
            SEED_PROMPT.format(situation=sc["situation"], question=sc["question"])


# ---------------------------------------------------------------- extras: plumbing, E8/E9, scenario guards

def test_relative_config_dir_reaches_seats_as_the_recorded_absolute_path(tmp_path, monkeypatch, git_env):
    repo, _ = make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "rel/cfg")
    seen = []

    def seat(cmd, cwd, env):
        seen.append(env["CLAUDE_CONFIG_DIR"])
        return 0, "answer", ""
    monkeypatch.setattr(ab, "exec_seat", seat)
    run_dir = tmp_path / "run"
    assert ab.main(["seats", "--repo", str(repo), "--charter", "CHARTER.md", "--scenarios", write_scenarios(tmp_path),
                    "--run-dir", str(run_dir), "--candidate", "HEAD", "--base", "HEAD"]) == 0
    recorded = json.loads((run_dir / "sides.json").read_text())["claude_config_dir"]
    assert seen and set(seen) == {recorded} and os.path.isabs(recorded) and recorded.endswith("rel/cfg")


def test_run_end_to_end_with_fakes(tmp_path, monkeypatch, git_env):
    repo, _ = make_repo(tmp_path)
    cfg = str(tmp_path / "cfg")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", cfg)
    seen = []

    def seat(cmd, cwd, env):
        seen.append((cwd, env["CLAUDE_CONFIG_DIR"]))
        return 0, f"answer from {os.path.basename(cwd)}", ""
    monkeypatch.setattr(ab, "exec_seat", seat)
    monkeypatch.setattr(ab, "exec_judge", fake_judge_all_correct([]))
    run_dir = tmp_path / "run"
    common = ["--repo", str(repo), "--charter", "CHARTER.md", "--scenarios", write_scenarios(tmp_path),
              "--run-dir", str(run_dir), "--replicates", "2"]
    assert ab.main(["run", "--candidate", "HEAD", "--base", "HEAD"] + common) == 0
    assert len(seen) == 8 and {c for _, c in seen} == {cfg}
    assert {os.path.basename(w) for w, _ in seen} == {"base", "candidate"}
    sides = json.loads((run_dir / "sides.json").read_text())
    assert sides["candidate_sha"] == sides["base_sha"] and len(sides["base_sha"]) == 40
    assert json.loads((run_dir / "verdict.json").read_text())["verdict"] == "PASS"
    assert (run_dir / "walltime.txt").exists() and worktree_count(repo) == 1
    assert ab.main(["report", "--repo", str(repo), "--run-dir", str(run_dir)]) == 0
    assert json.loads((run_dir / "worktrees.json").read_text())  # roots recorded for the judge's redaction
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "other-cfg"))  # resumed seats under another config
    assert ab.main(["seats", "--candidate", "HEAD", "--base", "HEAD"] + common) == 3
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", cfg)
    assert ab.main(["judge", "--repo", str(repo), "--run-dir", str(run_dir)]) == 0
    # a later stage under a different identity is refused, not mixed in
    assert ab.main(["report", "--repo", str(repo), "--run-dir", str(run_dir), "--model", "sonnet"]) == 3
    assert ab.main(["seats", "--candidate", "HEAD", "--base", "HEAD", "--model", "sonnet"] + common) == 3
    assert ab.main(["seats", "--candidate", "HEAD", "--base", "HEAD", "--replicates", "3"] + common[:-2]) == 3


def test_missing_charter_or_ref_refused_and_worktrees_removed(tmp_path, monkeypatch, git_env):
    repo, sha = make_repo(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    base = ["seats", "--repo", str(repo), "--scenarios", write_scenarios(tmp_path), "--run-dir",
            str(tmp_path / "run")]
    assert ab.main(base + ["--candidate", "HEAD", "--base", "HEAD", "--charter", "NOPE.md"]) == 3
    assert ab.main(base + ["--candidate", "no-such-ref", "--base", "HEAD", "--charter", "CHARTER.md"]) == 3
    assert worktree_count(repo) == 1
    assert not (tmp_path / "run" / "sides.json").exists()


def test_worktrees_removed_when_the_body_raises(tmp_path, git_env):
    repo, sha = make_repo(tmp_path)
    seen = []
    with pytest.raises(RuntimeError):
        with ab.worktrees(str(repo), {"base": sha, "candidate": sha}) as wts:
            seen.extend(wts.values())
            assert all(os.path.isfile(os.path.join(p, "CHARTER.md")) for p in seen)
            raise RuntimeError("stage blew up")
    assert len(seen) == 2 and not any(os.path.exists(p) for p in seen)
    assert worktree_count(repo) == 1


def test_plugin_dir_for_finds_nearest_manifest(tmp_path):
    def manifest(rel):
        p = tmp_path / rel / ".claude-plugin" / "plugin.json"
        p.parent.mkdir(parents=True)
        p.write_text("{}")
    manifest("plugins/x")
    manifest("plugins/x/skills/z")
    manifest("")  # the root's own manifest is not below the root, so it never counts
    charter = "plugins/x/skills/y/SKILL.md"
    (tmp_path / charter).parent.mkdir(parents=True)
    (tmp_path / charter).write_text("c")
    assert ab.plugin_dir_for(str(tmp_path), charter) == "plugins/x"
    assert ab.plugin_dir_for(str(tmp_path), str(tmp_path / charter)) == "plugins/x"
    assert ab.plugin_dir_for(str(tmp_path), "plugins/x/skills/z/SKILL.md") == "plugins/x/skills/z"  # nearest wins
    assert ab.plugin_dir_for(str(tmp_path), "docs/CHARTER.md") is None
    assert ab.plugin_dir_for(str(tmp_path), "../outside/CHARTER.md") is None
    assert ab.plugin_dir_for(str(_AB_PATH.parents[2]), ab.DEFAULT_CHARTER) == "plugins/superheroes"


def test_missing_plugin_manifest_on_a_side_refused(tmp_path, monkeypatch, git_env, capsys):
    repo, _ = make_repo(tmp_path)
    charter = repo / "plugins" / "x" / "skills" / "y" / "SKILL.md"
    charter.parent.mkdir(parents=True)
    charter.write_text("the plugin charter\n")
    g = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run(g + ["add", "."], check=True, capture_output=True)
    subprocess.run(g + ["commit", "-q", "-m", "c2"], check=True, capture_output=True)
    base = subprocess.run(g + ["rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    manifest = repo / "plugins" / "x" / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}")
    subprocess.run(g + ["add", "."], check=True, capture_output=True)
    subprocess.run(g + ["commit", "-q", "-m", "c3"], check=True, capture_output=True)  # only c3 has the manifest
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    argv = ["seats", "--repo", str(repo), "--candidate", "HEAD", "--base", base, "--charter",
            "plugins/x/skills/y/SKILL.md", "--scenarios", write_scenarios(tmp_path), "--run-dir", str(tmp_path / "run")]
    assert ab.main(argv) == 3
    err = capsys.readouterr().err
    assert "no plugin manifest" in err and "base" in err
    assert worktree_count(repo) == 1 and not (tmp_path / "run" / "sides.json").exists()


def test_scenario_file_guards(tmp_path):
    def load(data):
        p = tmp_path / "s.json"
        p.write_text(json.dumps(data))
        return ab.load_scenarios(str(p))
    role, scs, sha = load([scen("a")])
    assert role == ab.DEFAULT_ROLE and len(sha) == 64 and scs[0]["id"] == "a"
    assert load({"role": "r", "scenarios": [scen("a")]})[0] == "r"
    assert load({"role": "r", "scenarios": []})[1] == []
    for bad_rule in ("", "   ", None, 7):
        with pytest.raises(ab.Refusal):
            load([dict(scen("a"), expected_rule=bad_rule)])
    for bad_id in (1, "", "  ", None, ["a"]):
        with pytest.raises(ab.Refusal):
            load([dict(scen("a"), id=bad_id)])
    for bad in ([scen("a"), scen("a")], [{k: v for k, v in scen("a").items() if k != "targeted_block"}],
                {"scenarios": [scen("a")]}, {"role": "r", "scenarios": "no"}):
        with pytest.raises(ab.Refusal):
            load(bad)


def test_sigterm_takes_the_interrupt_path_and_handler_is_restored(monkeypatch):
    seen = {}

    def fake_dispatch(a, stack):
        stack.callback(seen.setdefault, "cleaned", True)
        os.kill(os.getpid(), signal.SIGTERM)
    monkeypatch.setattr(ab, "dispatch", fake_dispatch)
    before = signal.getsignal(signal.SIGTERM)
    with pytest.raises(KeyboardInterrupt):
        ab.main(["run"])
    assert seen == {"cleaned": True} and signal.getsignal(signal.SIGTERM) is before


# ---------------------------------------------------------------- round-1 fixes: replicates, judge rc, forced reruns

def test_non_positive_replicates_refused(tmp_path, monkeypatch, git_env):
    repo, _ = make_repo(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    argv = ["run", "--repo", str(repo), "--candidate", "HEAD", "--base", "HEAD", "--charter", "CHARTER.md",
            "--scenarios", write_scenarios(tmp_path), "--run-dir", str(tmp_path / "run")]
    for bad in ("0", "-1"):
        assert ab.main(argv + ["--replicates", bad]) == 3
    monkeypatch.setenv("REPLICATES", "0")
    assert ab.main(argv) == 3
    assert not (tmp_path / "run" / "sides.json").exists()


def test_judge_nonzero_exit_is_not_published(tmp_path, monkeypatch):
    run_dir, scenarios, ident, _ = build_run(tmp_path, judged=False)
    monkeypatch.setattr(ab, "exec_judge", lambda cmd, prompt: (1, judge_line(1), "boom"))
    ab.stage_judge(run_dir, scenarios[:1], ident, False, 1)
    out, _, shap = ab.judge_paths(run_dir, "s1")
    assert not os.path.exists(out) and not os.path.exists(shap)
    assert os.path.exists(out + ".fail1.err") and os.path.exists(out + ".fail2.err")


def test_failed_forced_rerun_stays_incomplete(tmp_path, monkeypatch):
    run_dir, scenarios, ident, mapping = build_run(tmp_path)
    assert ab.stage_report(run_dir, scenarios, ident) == 0
    monkeypatch.setattr(ab, "exec_seat", lambda c, w, e: (1, "", "outage"))
    for sc in scenarios:
        for side in ab.SIDES:
            ab.run_seat(run_dir, SIDE_DIRS, sc, side, 1, True, ident, "/cfg")
    assert ab.stage_report(run_dir, scenarios, ident) == 2
    assert Path(ab.ans_path(run_dir, "s1", "base", 1) + ".prev").exists()
    # restore answers, then fail only the forced judge rerun
    for sc in scenarios:
        for side in ab.SIDES:
            Path(ab.ans_path(run_dir, sc["id"], side, 1)).write_text(f"answer {sc['id']} {side} 1\n")
    monkeypatch.setattr(ab, "exec_judge", lambda cmd, prompt: (1, "", "outage"))
    ab.stage_judge(run_dir, scenarios, ident, True, 1)
    assert ab.stage_report(run_dir, scenarios, ident) == 2


def test_one_replicate_and_escaping_charter_refused_absolute_charter_normalized(tmp_path, monkeypatch, git_env):
    repo, _ = make_repo(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    argv = ["run", "--repo", str(repo), "--candidate", "HEAD", "--base", "HEAD", "--charter", "CHARTER.md",
            "--scenarios", write_scenarios(tmp_path), "--run-dir", str(tmp_path / "run")]
    assert ab.main(argv + ["--replicates", "1"]) == 3
    monkeypatch.setenv("REPLICATES", "1")
    assert ab.main(argv) == 3
    monkeypatch.delenv("REPLICATES")
    for bad in ("../CHARTER.md", str(tmp_path / "elsewhere.md")):
        assert ab.main(argv[:-6] + ["--charter", bad, "--scenarios", write_scenarios(tmp_path),
                                    "--run-dir", str(tmp_path / "run"), "--replicates", "2"]) == 3
    assert ab.normalize_charter(str(repo), str(repo / "CHARTER.md")) == "CHARTER.md"
    assert ab.normalize_charter(str(repo), "./a/../CHARTER.md") == "CHARTER.md"


# ---------------------------------------------------------------- judge process tree, run-dir lock

def test_judge_timeout_kills_the_whole_process_group(tmp_path, monkeypatch):
    pidfile = tmp_path / "child.pid"
    monkeypatch.setattr(ab, "JUDGE_TIMEOUT", 1)
    script = f"sleep 60 & echo $! > {pidfile}; wait"
    with pytest.raises(subprocess.TimeoutExpired):
        _REAL_EXEC_JUDGE(["sh", "-c", script], "")
    child = int(pidfile.read_text())
    import time
    for _ in range(50):
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    os.kill(child, 9)
    pytest.fail("grandchild of the timed-out judge survived")


def test_second_invocation_on_a_locked_run_dir_refused(tmp_path, monkeypatch, git_env, capsys):
    import fcntl
    repo, _ = make_repo(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    fd = os.open(run_dir, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert ab.main(["seats", "--repo", str(repo), "--candidate", "HEAD", "--base", "HEAD", "--charter",
                        "CHARTER.md", "--scenarios", write_scenarios(tmp_path), "--run-dir", str(run_dir)]) == 3
        assert "in use" in capsys.readouterr().err
    finally:
        os.close(fd)
    assert not (run_dir / "sides.json").exists()


def test_interrupt_kills_live_groups_and_blocks_retries():
    import threading
    import time
    got = {}

    def worker():
        try:
            got["r"] = ab.run_group(["sh", "-c", "sleep 60"], 60, "")
        except BaseException as e:  # noqa: BLE001
            got["e"] = e

    with pytest.raises(KeyboardInterrupt):
        with ab.cancel_on_interrupt():
            t = threading.Thread(target=worker)
            t.start()
            for _ in range(100):
                with ab._RUNNING_PROCS_LOCK:
                    if ab._RUNNING_PROCS:
                        break
                time.sleep(0.05)
            raise KeyboardInterrupt
    t.join(10)
    assert not t.is_alive()
    assert got["r"][0] == -9  # killed by the interrupt handler, not by the 60s timeout
    assert ab._STOPPING.is_set() and not ab._RUNNING_PROCS
    with pytest.raises(InterruptedError):
        ab.run_group(["true"], 5)
    with ab.cancel_on_interrupt():  # a new stage starts clean
        assert not ab._STOPPING.is_set()
