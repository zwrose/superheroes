"""The review record certifies the commit its session reviewed (#2496).

A record's `finalCommit.sha` is the account's `finalCommit`, never the PR head read from GitHub. A head that moved
past it adds no open line to the record (the vet's shared check decides whether the commit covers the head). The record
still never takes the session's word for coverage it cannot check: a reviewer row counts for the certified commit
through an engine record, and a row only the session reports counts only when GitHub confirmed that commit as the PR
head. The PR's changed files describe the head GitHub serves, so they are the lane basis only for the certified commit.
"""
import os
import subprocess

import pytest

import review_record as rr
from test_review_record import EARLIER, GOOD_RUN, GREEN, HEAD, PAYMENTS, Fake, account, build, reviewer, risk_repo

RUN = "/run/code-reviewer"
MOVED_LINE = "the PR head moved while the record was written; this record does not cover the new head"
BR1 = "the PR head moved past the session's final commit, so only an engine record can show a reviewer read it"
COULD_NOT_READ = "the final commit could not be read from the PR"


def engine_on(sha):
    """The engine run record of the one reviewer, covering `sha`."""
    return {RUN: (dict(GOOD_RUN, viewHeadSha=sha), None)}


def head_lines(rec):
    """Every open line of the retired head rules: the moved-head line and the session-ended-on line."""
    return [m for m in rec["whatIsMissing"] if "moved" in m or "session ended on" in m]


def unread_pr(fake):
    return {**fake.readers(), "pr_meta": lambda pr, repo: None}


def test_the_moved_head_source_is_pinned():
    # axis: the external literal a reader of the record sees when the PR head moved past the certified commit
    assert rr.HEAD_MOVED_SOURCE == "reported by the session; the PR head had moved past it"
    assert rr.FINAL_COMMIT_CONFIRMED == "GitHub PR"


def test_a_session_on_an_earlier_commit_than_the_pr_head_reads_reviewed_on_its_own_commit():
    # axis: the record's final commit is the session's own, whatever the PR head is, with the source saying the head moved and the head kept beside it; CI is read on the certified commit — see bite-proof record i2496_wo_b_record_commit (E-source)
    seen = []
    readers = dict(Fake(runs=engine_on(EARLIER)).readers(), check_data=lambda sha, repo: seen.append(sha) or GREEN)
    rec = rr.build_record(account(finalCommit=EARLIER, ci="green"), readers)
    assert rec["finalCommit"] == {"sha": EARLIER, "source": rr.HEAD_MOVED_SOURCE}
    assert rec["headAtWrite"] == HEAD
    assert rec["reviewers"][0]["ran"] == "engine-record" and rec["reviewers"][0]["coversFinalCommit"] is True
    assert (rec["status"], rec["whatIsMissing"]) == ("reviewed", [])
    assert head_lines(rec) == []
    body = rr.render(rec)
    assert "session ended on" not in body and MOVED_LINE not in body
    assert seen == [EARLIER] and rec["ci"]["sha"] == EARLIER
    assert not [d for d in rec["sessionDisagreements"] if d["fact"] == "finalCommit"]


def test_a_pr_head_equal_to_the_certified_commit_is_the_github_source_with_no_head_beside_it():
    # axis: the three-way source choice; a confirmed head read as moved, or a head recorded beside a commit it equals — see bite-proof record i2496_wo_b_record_commit (E-source)
    rec = build(account(finalCommit=HEAD))
    assert rec["finalCommit"] == {"sha": HEAD, "source": "GitHub PR"}
    assert "headAtWrite" not in rec and rec["status"] == "reviewed"


def test_an_unreadable_pr_keeps_the_session_source_and_the_could_not_be_read_line():
    # axis: pr_meta unreadable is the session's source and an open line, as before; never the moved-head source — see bite-proof record i2496_wo_b_record_commit (E-source)
    rec = rr.build_record(account(finalCommit=HEAD), unread_pr(Fake()))
    assert rec["finalCommit"] == {"sha": HEAD, "source": rr.SESSION}
    assert "headAtWrite" not in rec
    assert rec["status"] == "not-reviewed" and COULD_NOT_READ in rec["whatIsMissing"]


def test_a_moved_head_adds_no_could_not_be_read_line():
    # axis: the could-not-be-read line fires only for the session's source, never for a head that moved — see bite-proof record i2496_wo_b_record_commit (E-source)
    rec = rr.build_record(account(finalCommit=EARLIER), Fake(runs=engine_on(EARLIER)).readers())
    assert COULD_NOT_READ not in rec["whatIsMissing"]


@pytest.mark.parametrize("over", [{}, {"commit": EARLIER}], ids=["unnamed row", "row naming the certified commit"])
def test_a_session_only_row_on_a_moved_head_reads_not_run_with_the_br1_note(over):
    # axis: a row only the session reports counts only when GitHub confirmed the final commit as the PR head — see bite-proof record i2496_wo_b_record_commit (E-session-row)
    rec = build(account(finalCommit=EARLIER, reviewers=[reviewer(runDir=None, **over)]))
    row = rec["reviewers"][0]
    assert row["ran"] == "not-run" and row["runNote"] == BR1 and row["coversFinalCommit"] is False
    assert {"fact": "code-reviewer ran", "session": True, "code": "not-run"} in rec["sessionDisagreements"]
    assert rec["status"] == "not-reviewed" and "no planned reviewer ran" in rec["whatIsMissing"]


def test_a_session_only_row_never_covers_a_commit_github_did_not_confirm():
    # axis: an unreadable PR head confirms nothing, so a session-only row never counts; fail closed — see bite-proof record i2496_wo_b_record_commit (E-session-row)
    rec = rr.build_record(account(finalCommit=HEAD, reviewers=[reviewer(runDir=None)]), unread_pr(Fake()))
    row = rec["reviewers"][0]
    assert row["ran"] == "not-run" and row["runNote"] == BR1
    assert rec["status"] == "not-reviewed" and COULD_NOT_READ in rec["whatIsMissing"]


def test_a_session_only_row_counts_when_the_pr_head_is_the_certified_commit():
    # axis: the confirmed case of the same rule; a confirmed head demoting the row — see bite-proof record i2496_wo_b_record_commit (E-session-row)
    rec = build(account(finalCommit=HEAD, reviewers=[reviewer(runDir=None)]))
    assert rec["reviewers"][0]["ran"] == "reported-by-session" and rec["reviewers"][0]["coversFinalCommit"] is True
    assert (rec["status"], rec["whatIsMissing"]) == ("reviewed", [])


def test_an_engine_record_row_counts_on_a_moved_head_for_the_commit_its_run_names():
    # axis: engine-record rows are bound to the commit their run record names, whatever the head did
    rec = build(account(finalCommit=EARLIER), Fake(runs=engine_on(EARLIER)))
    assert rec["reviewers"][0]["ran"] == "engine-record" and rec["reviewers"][0]["coversFinalCommit"] is True


def test_a_wrong_certified_commit_is_not_reviewed():
    # axis: the account says EARLIER and the only engine record covers HEAD, so nothing reviewed the certified commit
    rec = build(account(finalCommit=EARLIER))
    row = rec["reviewers"][0]
    assert row["ran"] == "not-run"
    assert row["runNote"] == f"the run record covers {HEAD[:7]}, not the final commit {EARLIER[:7]}"
    assert rec["status"] == "not-reviewed" and head_lines(rec) == []


@pytest.mark.parametrize("row_commit,run_commit,final", [(HEAD, HEAD, EARLIER), (EARLIER, EARLIER, HEAD)],
                         ids=["engine row covers the PR head, session ended earlier",
                              "engine row covers an earlier commit, session ended on the PR head"])
def test_a_record_none_of_whose_planned_reviewers_ran_on_the_certified_commit_has_the_one_open_line(
        row_commit, run_commit, final):
    # axis: a planned reviewer that ran must have run on the commit the record certifies, else exactly one open line says so — see bite-proof record i2496_wo_b_record_commit (E-only-line)
    rec = build(account(finalCommit=final, reviewers=[reviewer(commit=row_commit)]), Fake(runs=engine_on(run_commit)))
    row = rec["reviewers"][0]
    assert row["ran"] == "engine-record" and row["coversFinalCommit"] is False
    assert rec["status"] == "not-reviewed" and rec["parked"] is False
    assert rec["whatIsMissing"] == [f"no planned reviewer's run covers the final commit {final[:7]}"]


def test_the_same_record_with_the_row_on_the_certified_commit_reads_reviewed():
    # axis: the only-open-line pin's other half; the line firing on a row that does cover the certified commit — see bite-proof record i2496_wo_b_record_commit (E-only-line)
    rec = build(account(finalCommit=EARLIER, reviewers=[reviewer(commit=EARLIER)]), Fake(runs=engine_on(EARLIER)))
    assert rec["reviewers"][0]["coversFinalCommit"] is True
    assert (rec["status"], rec["whatIsMissing"]) == ("reviewed", [])


# --- the lane basis is bound to the certified commit ---

def git(repo, *args):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout.strip()


def new_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    return repo


def commit(repo, name, write=(), move=()):
    """One commit of `repo`: the files written, then the files moved; its sha."""
    for rel, text in write:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
        git(repo, "add", rel)
    for old, new in move:
        (repo / new).parent.mkdir(parents=True, exist_ok=True)
        git(repo, "mv", old, new)
    git(repo, "commit", "-q", "-m", name)
    return git(repo, "rev-parse", "HEAD")


def history(tmp_path):
    """A repo with a risk area (src/payments), the base, X (a docs file only) and a later head (a payments file)."""
    repo = new_repo(tmp_path)
    base = commit(repo, "base", write=[("README.md", "r\n")])
    x = commit(repo, "x", write=[("docs/guide.md", "g\n")])
    later = commit(repo, "later", write=[("src/payments/charge.py", "c\n")])
    return risk_repo(repo, areas=(PAYMENTS,)), base, x, later


def boom(pr, repo):
    raise AssertionError("the PR's changed files were read for a head that is not the certified commit")


def recorder(seen):
    return lambda root, sha, paths: seen.append((sha, list(paths))) or []


def test_a_moved_head_reads_the_certified_commits_paths_from_git_not_the_heads_files(tmp_path):
    # axis: the path list is bound to the certified commit; a risk-area file changed only after X never raises the floor, and the PR's files are not read for a head that is not X — see bite-proof record i2496_wo_b_record_commit (E-paths)
    repo, base, x, later = history(tmp_path)
    seen = []
    fake = Fake(meta={"head": later, "body": "", "issues": []}, runs=engine_on(x))
    readers = {**fake.readers(), "changed_paths": boom, "withheld_paths": recorder(seen)}
    rec = rr.build_record(account(finalCommit=x, carryBase=base, repoRoot=repo, lane="light"), readers)
    basis = rec["laneBasis"]
    assert basis["source"] == "lane rule over the certified commit's changed files (git)"
    assert basis["floor"] is None and basis["touched"] == [] and "headMoved" not in basis
    assert rec["finalCommit"] == {"sha": x, "source": rr.HEAD_MOVED_SOURCE} and rec["headAtWrite"] == later
    assert (rec["status"], rec["whatIsMissing"]) == ("reviewed", [])
    assert seen == [(x, ["docs/guide.md"])]


def test_a_head_that_moves_during_the_files_read_reads_the_certified_commits_paths_from_git(tmp_path):
    # axis: the PR's files are the lane basis only when the head read before and after them equals the certified commit — see bite-proof record i2496_wo_b_record_commit (E-paths)
    repo, base, x, later = history(tmp_path)
    reads, seen = [], []
    fake = Fake(runs=engine_on(x))
    fake.changed = ["docs/guide.md", "src/payments/charge.py"]

    def meta(pr, repo_name):
        reads.append(1)
        return {"head": x if len(reads) == 1 else later, "body": "", "issues": []}
    readers = {**fake.readers(), "pr_meta": meta, "withheld_paths": recorder(seen)}
    rec = rr.build_record(account(finalCommit=x, carryBase=base, repoRoot=repo, lane="light"), readers)
    assert len(reads) == 2 and rec["finalCommit"] == {"sha": x, "source": "GitHub PR"}
    assert rec["laneBasis"]["source"] == "lane rule over the certified commit's changed files (git)"
    assert rec["laneBasis"]["floor"] is None
    assert (rec["status"], rec["whatIsMissing"]) == ("reviewed", [])
    assert seen == [(x, ["docs/guide.md"])]


def test_the_prs_files_are_the_lane_basis_when_the_head_is_the_certified_commit_before_and_after(tmp_path):
    # axis: the confirmed case; the PR's file list kept as the basis when the head never moved, with the withheld list reading the same list
    repo, base, x, later = history(tmp_path)
    seen = []
    fake = Fake(meta={"head": later, "body": "", "issues": []}, runs=engine_on(later))
    fake.changed = ["docs/guide.md", "src/payments/charge.py"]
    readers = {**fake.readers(), "withheld_paths": recorder(seen)}
    rec = rr.build_record(account(finalCommit=later, carryBase=base, repoRoot=repo), readers)
    assert rec["laneBasis"]["source"] == "lane rule over the PR's changed files" and rec["laneBasis"]["floor"] == "full"
    assert seen == [(later, ["docs/guide.md", "src/payments/charge.py"])]


def test_git_failure_gives_the_unavailable_basis_never_a_partial_list(tmp_path):
    # axis: a path list git could not give whole is unavailable with the floor full, never a shorter list or the head's files — see bite-proof record i2496_wo_b_record_commit (E-paths)
    repo = risk_repo(tmp_path)
    calls = []
    fake = Fake(runs=engine_on(EARLIER))
    readers = {**fake.readers(), "changed_paths": boom, "withheld_paths": recorder([]),
               "commit_paths": lambda root, base, sha: calls.append((root, base, sha)) or None}
    rec = rr.build_record(account(finalCommit=EARLIER, carryBase=HEAD, repoRoot=repo, lane="light"), readers)
    basis = rec["laneBasis"]
    assert calls == [(repo, HEAD, EARLIER)]
    assert basis["source"] == "unavailable" and basis["floor"] == "full" and "headMoved" not in basis
    assert basis["why"][0] == rr.lane_call.WHY_NO_PATHS + " the PR head moved while its changed files were read"
    assert rec["withheldFromReviewers"] is None
    assert rec["status"] == "not-reviewed"
    assert rec["whatIsMissing"] == ["the lane (light) is below the risk floor (full); the Risk floor line gives why"]


def test_a_moved_head_with_no_carry_base_reads_the_unavailable_basis_and_no_open_line(tmp_path):
    # axis: no pinned base means no path list for the certified commit; the floor reads full, the key headMoved is never written, and a full lane has no open line
    repo = risk_repo(tmp_path)
    readers = {**Fake(runs=engine_on(EARLIER)).readers(), "changed_paths": boom}
    rec = rr.build_record(account(finalCommit=EARLIER, repoRoot=repo), readers)
    basis = rec["laneBasis"]
    assert basis["source"] == "unavailable" and basis["floor"] == "full" and "headMoved" not in basis
    assert basis["why"][0] == rr.lane_call.WHY_NO_PATHS + " the PR head moved while its changed files were read"
    assert rec["withheldFromReviewers"] is None
    assert (rec["status"], rec["whatIsMissing"]) == ("reviewed", [])
    assert MOVED_LINE not in rr.render(rec)


def test_the_commit_paths_reader_gives_the_certified_commits_paths_with_each_renames_source(tmp_path):
    # axis: the reader's list is the diff of the certified commit against the base, a rename's source path included, and nothing a later commit changed — see bite-proof record i2496_wo_b_record_commit (E-paths)
    repo = new_repo(tmp_path)
    base = commit(repo, "base", write=[("README.md", "r\n"), ("src/payments/charge.py", "charge = 1\n" * 20)])
    x = commit(repo, "x", write=[("docs/guide.md", "g\n")], move=[("src/payments/charge.py", "src/billing/charge.py")])
    later = commit(repo, "later", write=[("src/payments/late.py", "l\n")])
    assert sorted(rr.commit_paths(str(repo), base, x)) == ["docs/guide.md", "src/billing/charge.py",
                                                           "src/payments/charge.py"]
    assert "src/payments/late.py" in rr.commit_paths(str(repo), base, later)
    assert "commit_paths" in rr._readers(None) and rr._readers(None)["commit_paths"] is rr.commit_paths


def test_the_commit_paths_reader_gives_none_never_a_partial_list(tmp_path):
    # axis: any failure, or any row the reader cannot read whole (a git-quoted path), is None, never a shorter list — see bite-proof record i2496_wo_b_record_commit (E-paths)
    repo = new_repo(tmp_path)
    base = commit(repo, "base", write=[("README.md", "r\n")])
    x = commit(repo, "x", write=[("docs/guide.md", "g\n")])
    odd = commit(repo, "odd", write=[("odd\tname.py", "o\n")])
    assert rr.commit_paths(str(repo), base, x) == ["docs/guide.md"]
    assert rr.commit_paths(str(repo), base, odd) is None
    assert rr.commit_paths(None, base, x) is None
    assert rr.commit_paths(str(tmp_path / "no-such-repo"), base, x) is None
    assert rr.commit_paths(str(repo), None, x) is None
    assert rr.commit_paths(str(repo), base[:7], x) is None
    assert rr.commit_paths(str(repo), base, x[:7]) is None
    assert rr.commit_paths(str(repo), base, "c" * 40) is None
