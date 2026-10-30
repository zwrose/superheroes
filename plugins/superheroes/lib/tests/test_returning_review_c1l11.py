# plugins/superheroes/lib/tests/test_returning_review_c1l11.py
"""C1-L11: the returning-review decider reads only what changed since the last reviewed commit, and asks for a
full panel when that change is over the countable-lines bar or touches risk the pull request had not."""
import hashlib
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import countable_lines  # noqa: E402
import returning_review as R  # noqa: E402
import review_diff_bytes  # noqa: E402

_SCRIPT = os.path.join(_LIB, "returning_review.py")
RESULT_KEYS = {"read", "lastReviewed", "countable", "bar", "unsettled", "changedFiles", "newAreas", "overlap", "why",
               "deltaDiff"}

PAYMENTS = {"name": "Payments", "covers": ["src/payments/*"], "why": "Charges customers.",
            "undo": "Hard: a charge needs a refund."}
CUSTOMER_DATA = {"name": "Customer data", "covers": ["src/db/*.sql", "migrations/*"],
                 "why": "Holds personal details.", "undo": "Hard: a leak cannot be taken back."}


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("GIT_CONFIG_PARAMETERS", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


class Repo:
    """A throwaway repository: ``main`` holds a README and one shared file; ``pr`` is checked out."""

    def __init__(self, tmp_path):
        self.root = str(tmp_path / "repo")
        os.makedirs(self.root)
        self.git("init", "-q", "-b", "main")
        # the risk-area store stays out of every commit, so it is never part of a diff
        with open(os.path.join(self.root, ".git", "info", "exclude"), "a", encoding="utf-8") as fh:
            fh.write(".claude/\n")
        self.write("README.md", "readme\n")
        self.write("src/shared.py", numbered("shared", 30))
        self.commit("initial")
        self.git("checkout", "-q", "-b", "pr")

    def git(self, *args):
        argv = ["git", "-C", self.root, "-c", "user.name=T", "-c", "user.email=t@example.com",
                "-c", "commit.gpgsign=false", *args]
        proc = subprocess.run(argv, capture_output=True, text=True)
        assert proc.returncode == 0, (argv, proc.stdout, proc.stderr)
        return proc.stdout.strip()

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def set_areas(self, areas):
        """An in-repo core.md (left untracked) that holds the given risk areas."""
        block = json.dumps({"schemaVersion": 2, "verifyCommand": "npm test", "stackTags": ["node"],
                            "projectConfiguration": {"riskAreas": areas}})
        text = ("<!-- superheroes-core: schemaVersion=2 status=confirmed created=2026-06-26 "
                "updated=2026-06-26 -->\n\n## Threat model\n\nsingle-user\n\n"
                "## Canonical patterns\n\n- x: a.ts:1\n\n```json superheroes-core\n%s\n```\n" % block)
        path = os.path.join(self.root, ".claude", "superheroes", "core.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def main_commit(self, rel, text):
        """A new commit on ``main`` (the moved base); returns its sha and leaves ``pr`` checked out."""
        self.git("checkout", "-q", "main")
        self.write(rel, text)
        sha = self.commit("base moves")
        self.git("checkout", "-q", "pr")
        return sha

    def merge_main(self):
        self.git("merge", "-q", "--no-ff", "-m", "catch up", "main")
        return self.git("rev-parse", "HEAD")


def numbered(tag, count):
    return "".join("value_%s_%d = %d\n" % (tag, i, i) for i in range(count))


def earlier_record(sha, *, covers=True, touched=(), unclear=False, basis=None):
    """A hand-built record shaped like ``review_record.py read`` output."""
    why = ["risk-unclear-not-set: the project's risk areas are not set (missing)"] if unclear \
        else ["no-floor: the risk is clear and no risk area is touched"]
    laneBasis = {
        "floor": "full" if unclear else None, "lane": "full", "why": why,
        "riskAreas": {"state": "not-set" if unclear else "set", "reason": None, "detail": None},
        "touched": [{"name": n, "matched": ["x"]} for n in touched], "unmatchable": [],
        "source": "lane rule over the PR's changed files",
    }
    return {
        "ok": True, "finalCommit": {"sha": sha, "source": "GitHub PR"},
        "reviewers": [{"seat": "panel-1", "coversFinalCommit": covers}],
        "laneBasis": laneBasis if basis is None else basis, "findings": [],
    }


def returning(repo, *, first=None, areas=(PAYMENTS, CUSTOMER_DATA), **record):
    """A pull request reviewed once on ``first`` files; returns ``(base, reviewed, record)``."""
    base = repo.git("rev-parse", "main")
    for rel, text in (first or {"src/app.py": numbered("app", 100)}).items():
        repo.write(rel, text)
    reviewed = repo.commit("first leg")
    if areas is not None:
        repo.set_areas(list(areas))
    return base, reviewed, earlier_record(reviewed, **record)


def decide(repo, base, earlier, **kwargs):
    head = repo.git("rev-parse", "HEAD")
    return R.decide(repo.root, base, head, earlier, **kwargs)


def tokens(result):
    return [w.split(":", 1)[0] for w in result["why"]]


# --- FR-44: a returning pull request reads only what changed ----------------------------------


def test_a_forty_line_fix_after_one_review_reads_only_the_fix(tmp_path):
    repo = Repo(tmp_path)
    base, reviewed, earlier = returning(repo, first={"src/app.py": numbered("app", 100), "docs/notes.md": "notes\n"})
    fix = numbered("fix", 40)
    repo.write("src/app.py", repo.read("src/app.py") + fix)
    repo.commit("fix")
    got = decide(repo, base, earlier)
    assert set(got) == RESULT_KEYS
    assert got["read"] == "changed" and got["countable"] == 40
    assert got["lastReviewed"] == reviewed and got["bar"] == countable_lines.COUNTABLE_LINES_BAR
    assert got["changedFiles"] == ["src/app.py"] and got["newAreas"] == [] and got["overlap"] == []
    assert got["unsettled"] == [] and tokens(got) == [R.WHY_CHANGED_ONLY]
    added = [line[1:] + "\n" for line in got["deltaDiff"].splitlines() if line.startswith("+") and not line.startswith("+++")]
    assert "".join(added) == fix
    assert "docs/notes.md" not in got["deltaDiff"] and "value_app_0 " not in got["deltaDiff"]


# --- FR-45: over the bar ----------------------------------------------------------------------


@pytest.mark.parametrize("unsettled", [False, True], ids=["settled", "unsettled-lines"])
def test_a_later_change_of_1001_countable_lines_reads_full_and_exactly_1000_reads_changed(tmp_path, monkeypatch, unsettled):
    # axis: the over-bar comparison; one line over the bar reading changed
    # axis: the lines of a file the counter cannot settle are added to the count; an unsettled file counted as nothing
    if unsettled:
        monkeypatch.setattr(countable_lines, "_attribute_flags", lambda *args, **kwargs: None)
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo)
    repo.write("src/big.py", numbered("big", 1000))
    repo.commit("exactly the bar")
    exact = decide(repo, base, earlier)
    assert exact["read"] == "changed" and exact["countable"] == 1000
    repo.write("src/big.py", numbered("big", 1000) + "one_more = 1\n")
    repo.commit("one over")
    over = decide(repo, base, earlier)
    assert over["read"] == "full" and over["countable"] == 1001
    assert tokens(over)[-1] == R.WHY_OVER_BAR and over["changedFiles"] == ["src/big.py"]
    expected = [{"file": "src/big.py", "reason": "attribute-unreadable"}] if unsettled else []
    assert over["unsettled"] == expected and exact["unsettled"] == expected
    assert any(w.startswith(R.WHY_UNSETTLED) for w in over["why"]) is unsettled
    assert any(w.startswith(R.WHY_UNSETTLED) for w in exact["why"]) is unsettled


# --- FR-45: a new risk area -------------------------------------------------------------------


def test_a_later_change_touching_an_area_the_earlier_review_did_not_reads_full(tmp_path):
    # axis: the new-area test; a change into an untouched area reading changed
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo, first={"src/payments/charge.py": numbered("charge", 10)}, touched=["Payments"])
    repo.write("migrations/001.sql", "alter table t add column c int;\n")
    repo.commit("add a migration")
    got = decide(repo, base, earlier)
    assert got["read"] == "full" and got["newAreas"] == ["Customer data"]
    assert tokens(got)[-1] == R.WHY_NEW_AREA and got["countable"] == 1


def test_a_later_change_touching_only_an_area_already_touched_reads_changed(tmp_path):
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo, first={"src/payments/charge.py": numbered("charge", 10)}, touched=["Payments"])
    repo.write("src/payments/charge.py", repo.read("src/payments/charge.py") + "refund = 1\n")
    repo.commit("more payments")
    got = decide(repo, base, earlier)
    assert got["read"] == "changed" and got["newAreas"] == [] and got["countable"] == 1


# --- FR-45: unclear risk ----------------------------------------------------------------------


def test_an_unclear_risk_reads_full_when_the_earlier_review_was_clear(tmp_path):
    # axis: the unclear-risk rule; an unclear change passing as changed against a clear earlier basis
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo, areas=None)
    repo.write("src/app.py", repo.read("src/app.py") + "extra = 1\n")
    repo.commit("fix")
    got = decide(repo, base, earlier)
    assert got["read"] == "full" and tokens(got)[-1] == R.WHY_RISK_UNCLEAR and got["newAreas"] == []


def test_an_unclear_risk_reads_changed_when_the_earlier_review_was_unclear_too(tmp_path):
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo, areas=None, unclear=True)
    repo.write("src/app.py", repo.read("src/app.py") + "extra = 1\n")
    repo.commit("fix")
    got = decide(repo, base, earlier)
    assert got["read"] == "changed"
    assert tokens(got) == [R.WHY_UNCLEAR_AS_BEFORE, R.WHY_CHANGED_ONLY]


# --- R3: proven copies ------------------------------------------------------------------------


def _proof_for(repo, rel):
    data = repo.read(rel).encode("utf-8")
    return {"schema": countable_lines.PROOF_SCHEMA,
            "copies": [{"file": rel, "source": "upstream/lib.py", "sha256": hashlib.sha256(data).hexdigest()}]}


def _proven(repo, base, proof):
    head = repo.git("rev-parse", "HEAD")
    diff = repo.git("diff", *review_diff_bytes.REVIEW_DIFF_ARGS, "%s...%s" % (base, head))
    proven, rejected = countable_lines.proven_copies(diff + "\n", repo.root, proof, head=head)
    assert proven and not rejected, rejected
    return proven


def test_a_returning_change_that_is_only_a_proven_copy_reads_changed_with_nothing_to_read(tmp_path):
    # axis: leaving proven copies out of the changed files; a copy listed as a changed file
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo)
    repo.write("vendor/lib.py", numbered("vendored", 2000))
    repo.commit("vendor a copy")
    got = decide(repo, base, earlier, proven=_proven(repo, base, _proof_for(repo, "vendor/lib.py")))
    assert got["read"] == "changed" and got["countable"] == 0
    assert got["changedFiles"] == [] and got["deltaDiff"] == "" and tokens(got) == [R.WHY_CHANGED_ONLY]


def test_a_proven_copy_of_2000_lines_beside_a_10_line_edit_counts_only_the_edit(tmp_path):
    # axis: leaving proven copies out of the changed files; a copy listed or read beside the edit
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo)
    repo.write("vendor/lib.py", numbered("vendored", 2000))
    repo.write("src/app.py", repo.read("src/app.py") + numbered("edit", 10))
    repo.commit("vendor a copy and edit")
    got = decide(repo, base, earlier, proven=_proven(repo, base, _proof_for(repo, "vendor/lib.py")))
    assert got["read"] == "changed" and got["countable"] == 10
    assert got["changedFiles"] == ["src/app.py"] and "vendor/lib.py" not in got["deltaDiff"]


def test_a_proven_copy_that_an_earlier_rename_came_from_is_never_passed_on(tmp_path, monkeypatch):
    # axis: the proven-copy filter over the final path list; a proven copy coming back as a rename's source path
    repo = Repo(tmp_path)
    repo.main_commit("vendor/lib.py", numbered("lib", 40))
    repo.merge_main()
    os.remove(os.path.join(repo.root, "vendor", "lib.py"))
    base, reviewed, earlier = returning(repo, first={"src/app.py": numbered("lib", 40)})
    reviewed_diff = repo.git("diff", *review_diff_bytes.REVIEW_DIFF_ARGS, "%s...%s" % (base, reviewed))
    assert "rename from vendor/lib.py" in reviewed_diff and "rename to src/app.py" in reviewed_diff
    repo.write("vendor/lib.py", numbered("newlib", 40))
    repo.write("src/app.py", repo.read("src/app.py") + numbered("edit", 3))
    repo.commit("restore the vendor file with new bytes and edit the src file")
    seen = []
    real_call = R.lane_call.call

    def recording_call(cwd, paths, *args, **kwargs):
        seen.append(list(paths))
        return real_call(cwd, paths, *args, **kwargs)

    monkeypatch.setattr(R.lane_call, "call", recording_call)
    got = decide(repo, base, earlier, proven=_proven(repo, base, _proof_for(repo, "vendor/lib.py")))
    assert got["read"] == "changed" and got["countable"] == 3
    assert got["changedFiles"] == ["src/app.py"] and "vendor/lib.py" not in got["deltaDiff"]
    assert seen == [["src/app.py"]]


# --- the incremental count --------------------------------------------------------------------


def test_a_one_line_replacement_in_a_file_the_earlier_review_added_whole_counts_two(tmp_path):
    # axis: the incremental diff being two-dot from the last reviewed commit; the whole section of the file counted
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo, first={"src/big.py": numbered("big", 1500)})
    repo.write("src/big.py", repo.read("src/big.py").replace("value_big_700 = 700", "value_big_700 = -1"))
    repo.commit("replace one line")
    got = decide(repo, base, earlier)
    assert got["read"] == "changed" and got["countable"] == 2 and got["changedFiles"] == ["src/big.py"]


# --- the base moves ---------------------------------------------------------------------------


def test_a_catch_up_merge_alone_reads_changed_with_nothing_to_read(tmp_path):
    repo = Repo(tmp_path)
    _, _, earlier = returning(repo)
    moved = repo.main_commit("docs/other.md", "other\n")
    repo.merge_main()
    got = decide(repo, moved, earlier)
    assert got["read"] == "changed" and got["countable"] == 0
    assert got["changedFiles"] == [] and got["overlap"] == [] and got["deltaDiff"] == ""


def test_a_file_the_base_and_the_pull_request_both_changed_is_named_and_the_count_follows_the_rules(tmp_path):
    repo = Repo(tmp_path)
    _, _, earlier = returning(repo)
    moved = repo.main_commit("src/shared.py", numbered("shared", 30) + numbered("basechange", 5))
    repo.merge_main()
    repo.write("src/shared.py", numbered("own", 3) + repo.read("src/shared.py"))
    repo.commit("own change to the shared file")
    got = decide(repo, moved, earlier)
    assert got["changedFiles"] == ["src/shared.py"] and got["overlap"] == ["src/shared.py"]
    assert any(w.startswith(R.WHY_OVERLAP) for w in got["why"])
    assert got["countable"] == 8 and got["read"] == "changed"


# --- fail-closed rows -------------------------------------------------------------------------


def test_no_earlier_record_reads_full(tmp_path):
    repo = Repo(tmp_path)
    base, _, _ = returning(repo)
    for earlier in (None, {"ok": False, "reason": "review-record-missing"}):
        got = decide(repo, base, earlier)
        assert got["read"] == "full" and tokens(got) == [R.WHY_NO_EARLIER] and got["lastReviewed"] is None
        assert set(got) == RESULT_KEYS and got["countable"] is None and got["unsettled"] == []


@pytest.mark.parametrize("earlier", [
    {"ok": False, "reason": "gh-unavailable"},
    "not a dict",
    [],
    {"ok": "yes", "finalCommit": {"sha": "a" * 40}},
    {"ok": True},
    {"ok": True, "finalCommit": {"sha": "abc123"}},
    {"ok": True, "finalCommit": {"sha": 7}},
])
def test_an_earlier_record_that_is_not_an_ok_record_with_a_final_sha_reads_full(tmp_path, earlier):
    repo = Repo(tmp_path)
    base, _, _ = returning(repo)
    got = decide(repo, base, earlier)
    assert got["read"] == "full" and tokens(got) == [R.WHY_EARLIER_UNUSABLE]


def test_a_rewritten_history_whose_last_reviewed_commit_is_not_an_ancestor_reads_full(tmp_path):
    # axis: the ancestor check; an orphaned last reviewed commit read as the starting point
    repo = Repo(tmp_path)
    base, reviewed, earlier = returning(repo)
    repo.git("commit", "-q", "--amend", "-m", "reworded first leg")
    assert repo.git("rev-parse", "HEAD") != reviewed
    got = decide(repo, base, earlier)
    assert got["read"] == "full" and tokens(got) == [R.WHY_NOT_ANCESTOR] and got["lastReviewed"] == reviewed


def test_a_git_that_fails_the_ancestor_check_counts_as_not_an_ancestor(tmp_path):
    seen = []

    def failing(argv):
        seen.append(argv)
        return 1, ""

    got = R.decide(str(tmp_path), "b" * 40, "c" * 40, earlier_record("a" * 40), git=failing)
    assert got["read"] == "full" and tokens(got) == [R.WHY_NOT_ANCESTOR]
    assert seen == [["merge-base", "--is-ancestor", "a" * 40, "c" * 40]]


@pytest.mark.parametrize("covers", [False, None, "true", 1])
def test_an_earlier_review_that_did_not_cover_its_final_commit_reads_full(tmp_path, covers):
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo, covers=covers)
    repo.write("src/app.py", repo.read("src/app.py") + "extra = 1\n")
    repo.commit("fix")
    got = decide(repo, base, earlier)
    assert got["read"] == "full" and tokens(got) == [R.WHY_NOT_COVERED]
    earlier["reviewers"] = []
    assert tokens(decide(repo, base, earlier)) == [R.WHY_NOT_COVERED]


@pytest.mark.parametrize("basis", [
    {"touched": [], "why": ["no-floor: x"], "touchedCount": 9},
    {"touched": [], "why": ["no-floor: x"], "source": "unavailable"},
    {"why": ["no-floor: x"]},
    {"touched": "Payments", "why": []},
    "unavailable",
    None,
])
def test_an_earlier_risk_basis_that_cannot_be_read_reads_full(tmp_path, basis):
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo)
    earlier["laneBasis"] = basis
    repo.write("src/app.py", repo.read("src/app.py") + "extra = 1\n")
    repo.commit("fix")
    got = decide(repo, base, earlier)
    assert got["read"] == "full" and tokens(got)[-1] == R.WHY_BASIS_UNUSABLE and got["countable"] == 1


def test_a_diff_git_cannot_produce_reads_full(tmp_path):
    repo = Repo(tmp_path)
    _, _, earlier = returning(repo)
    for base in ("d" * 40, "not-a-sha"):
        got = decide(repo, base, earlier)
        assert got["read"] == "full" and tokens(got) == [R.WHY_DIFF_UNREADABLE]
    got = R.decide(repo.root, repo.git("rev-parse", "main"), "not-a-sha", earlier)
    assert got["read"] == "full" and tokens(got) == [R.WHY_NOT_ANCESTOR]


def test_every_why_token_is_exported_and_leads_its_line():
    assert len(set(R.WHY_TOKENS)) == len(R.WHY_TOKENS)
    for token in ("no-earlier-record", "earlier-record-unusable", "last-reviewed-not-ancestor",
                  "earlier-review-did-not-cover", "diff-unreadable", "over-bar", "unsettled-counted", "new-risk-area",
                  "risk-unclear", "earlier-basis-unusable", "catch-up-overlap", "changed-only"):
        assert token in R.WHY_TOKENS


# --- the command line -------------------------------------------------------------------------


def _cli(*args):
    return subprocess.run([sys.executable, "-B", _SCRIPT, "decide", *args], capture_output=True, text=True)


def test_the_command_prints_the_result_and_writes_the_delta_to_a_file(tmp_path):
    repo = Repo(tmp_path)
    base, reviewed, earlier = returning(repo)
    fix = numbered("fix", 5)
    repo.write("src/app.py", repo.read("src/app.py") + fix)
    repo.commit("fix")
    record = tmp_path / "earlier.json"
    record.write_text(json.dumps(earlier))
    delta_out = tmp_path / "delta.diff"
    proc = _cli("--repo-root", repo.root, "--base", base, "--earlier-record", str(record), "--delta-out", str(delta_out))
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    assert set(got) == RESULT_KEYS - {"deltaDiff"}
    assert got["read"] == "changed" and got["countable"] == 5 and got["lastReviewed"] == reviewed
    assert got["changedFiles"] == ["src/app.py"]
    delta = delta_out.read_text()
    assert delta == repo.git("diff", *review_diff_bytes.REVIEW_DIFF_ARGS, reviewed, "HEAD", "--", "src/app.py") + "\n"
    assert delta.startswith("diff --git a/src/app.py b/src/app.py\n") and delta.count("\n+value_fix_") == 5


def test_the_command_reads_a_missing_or_garbled_earlier_record_as_full(tmp_path):
    repo = Repo(tmp_path)
    base, _, _ = returning(repo)
    proc = _cli("--repo-root", repo.root, "--base", base, "--earlier-record", str(tmp_path / "absent.json"))
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    assert got["read"] == "full" and got["why"][0].startswith(R.WHY_EARLIER_UNUSABLE)
    garbled = tmp_path / "garbled.json"
    garbled.write_text("{not json")
    assert json.loads(_cli("--repo-root", repo.root, "--base", base, "--earlier-record", str(garbled)).stdout)["read"] == "full"


def test_the_command_leaves_a_proven_copy_out_of_the_read(tmp_path):
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo)
    repo.write("vendor/lib.py", numbered("vendored", 50))
    repo.commit("vendor a copy")
    record = tmp_path / "earlier.json"
    record.write_text(json.dumps(earlier))
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps(_proof_for(repo, "vendor/lib.py")))
    proc = _cli("--repo-root", repo.root, "--base", base, "--earlier-record", str(record), "--proof", str(proof))
    got = json.loads(proc.stdout)
    assert proc.returncode == 0 and got["read"] == "changed" and got["changedFiles"] == [] and got["countable"] == 0


def test_the_command_exits_2_on_a_usage_error(tmp_path):
    assert _cli("--repo-root", str(tmp_path)).returncode == 2
    repo = Repo(tmp_path)
    base, _, earlier = returning(repo)
    record = tmp_path / "earlier.json"
    record.write_text(json.dumps(earlier))
    bad = tmp_path / "proof.json"
    bad.write_text("{}")
    proc = _cli("--repo-root", repo.root, "--base", base, "--earlier-record", str(record), "--proof", str(bad))
    assert proc.returncode == 2 and proc.stdout == ""
