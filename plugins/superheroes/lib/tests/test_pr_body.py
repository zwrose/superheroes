# plugins/superheroes/lib/tests/test_pr_body.py
import dod_gate
import pr_body
import stub_markers

BULLETS = ["**One.** owner can do X", "**Two.** #112 reshape landed"]


def test_seed_dod_block_has_marker_and_one_row_per_bullet():
    block = pr_body.seed_dod_block(BULLETS)
    assert dod_gate.TABLE_MARKER in block
    # one data row per bullet (blank disposition + evidence)
    rows = [ln for ln in block.split("\n") if ln.startswith("| ") and "---" not in ln]
    # header + 2 data rows
    assert len(rows) == 3
    assert "| **One.** owner can do X |  |  |" in block


def test_seed_dod_block_empty_when_no_bullets():
    assert pr_body.seed_dod_block([]) == ""
    assert pr_body.seed_dod_block(None) == ""


def test_seeded_table_round_trips_through_the_gate_as_park():
    # A freshly seeded (blank) table must PARK the gate — nothing is disposed yet.
    block = pr_body.seed_dod_block(BULLETS)
    r = dod_gate.decide(BULLETS, block, spec_present=True)
    assert r["verdict"] == "park"


def test_stubbed_seams_block_from_diff_markers():
    diff = ("+++ b/acceptance_launch.py\n"
            "+x = 0  # STUB(#231): spend ceiling inert in live runs\n")
    markers = stub_markers.markers_in_diff(diff)
    block = pr_body.stubbed_seams_block(markers)
    assert pr_body.STUBS_MARKER in block
    assert "- `acceptance_launch.py` — spend ceiling inert in live runs (#231)" in block


def test_stubbed_seams_block_empty_omitted():
    assert pr_body.stubbed_seams_block([]) == ""


def test_compose_appends_both_blocks():
    body = pr_body.compose_body("base body",
                                pr_body.seed_dod_block(BULLETS),
                                pr_body.stubbed_seams_block(
                                    [{"file": "f.py", "issue": 9, "description": "d"}]))
    assert body.startswith("base body")
    assert dod_gate.TABLE_MARKER in body and pr_body.STUBS_MARKER in body


def test_compose_is_idempotent_on_markers():
    once = pr_body.compose_body("base", pr_body.seed_dod_block(BULLETS), "")
    twice = pr_body.compose_body(once, pr_body.seed_dod_block(BULLETS), "")
    assert once == twice  # the DoD marker already present -> not re-appended


def test_compose_empty_blocks_leaves_base():
    assert pr_body.compose_body("just base", "", "").rstrip() == "just base"


# ---- #219: context gather + prose/tail split (appended; the #228 tests above are untouched) ----
import json
import os
import subprocess
import sys as _sys


def _repo_with_change(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True)
    (repo / "a.txt").write_text("one\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "feature/x"], check=True)
    (repo / "a.txt").write_text("one\ntwo\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "feat(x): add the second line"],
                   check=True)
    return repo


def _run_context(repo, tmp_path, extra=None):
    lib = os.path.dirname(os.path.abspath(pr_body.__file__))
    env = os.environ.copy()
    env["WORKHORSE_STORE_ROOT"] = str(tmp_path / "store")
    cmd = [_sys.executable, os.path.join(lib, "pr_body.py"), "context",
           "--work-item", "wi", "--base", "main",
           "--worktree", str(repo), "--root", str(repo)]
    if extra:
        cmd += extra
    proc = subprocess.run(cmd, cwd=str(repo), env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_context_carries_commits_and_bounded_diff(tmp_path):
    repo = _repo_with_change(tmp_path)
    ctx = _run_context(repo, tmp_path)
    assert ctx["work_item"] == "wi"
    assert any("second line" in c for c in ctx["commits"])
    assert "a.txt" in ctx["diffstat"]
    assert "+two" in ctx["diff_excerpt"]
    assert len(ctx["diff_excerpt"]) <= pr_body._DIFF_EXCERPT_CAP


def test_context_reports_prior_body_usability(tmp_path):
    repo = _repo_with_change(tmp_path)
    ctx = _run_context(repo, tmp_path, extra=["--body-path", str(tmp_path / "absent.md")])
    assert ctx["prior_body_usable"] is False
    prior = tmp_path / "prior.md"
    prior.write_text("A real composed body.\n\nCloses #219\n")
    ctx = _run_context(repo, tmp_path, extra=["--body-path", str(prior)])
    assert ctx["prior_body_usable"] is True
    blank = tmp_path / "blank.md"
    blank.write_text("   \n")
    ctx = _run_context(repo, tmp_path, extra=["--body-path", str(blank)])
    assert ctx["prior_body_usable"] is False


def test_split_prose_separates_generated_tail():
    prose = "A real body.\n\nCloses #219"
    dod = pr_body.seed_dod_block(["bullet one"])
    body = pr_body.compose_body(prose, dod, "")
    got_prose, got_tail = pr_body.split_prose(body)
    assert got_prose.strip() == prose
    assert "superheroes:dod-table" in got_tail
    # no tail -> everything is prose, tail empty
    p2, t2 = pr_body.split_prose("just prose\n")
    assert p2.strip() == "just prose" and t2 == ""
