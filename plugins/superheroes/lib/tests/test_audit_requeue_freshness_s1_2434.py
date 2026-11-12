"""A requeued audit target retains the provenance needed to clear a duplicate-test deletion."""
import os
import subprocess
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import audits  # noqa: E402
import round_driver as RD  # noqa: E402
import session_contract as SC  # noqa: E402


def test_requeued_duplicate_test_deletion_keeps_its_citation_fresh(tmp_path, monkeypatch):
    # axis: a projected audit target requeued after an unsuccessful attempt still clears a cited deletion when its cited file did not change before the retry.
    # Git configuration is isolated; the citation and removal facts come from real commits.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repo), *args], check=True,
            capture_output=True, text=True,
        ).stdout.strip()

    def commit(message):
        git("add", "-A")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-q", "-m", message)
        return git("rev-parse", "HEAD")

    git("init", "-q", "-b", "main")
    path = "tests/test_example.py"
    test_file = repo / path
    test_file.parent.mkdir()
    kept = "def test_keep():\n    assert True\n\n"
    test_file.write_text(
        kept + "def test_duplicate():\n    assert True\n", encoding="utf-8",
    )
    raised = commit("reviewed head")

    # The unsuccessful first attempt changes another file, leaving this citation valid.
    (repo / "tests/test_other.py").write_text(
        "def test_other():\n    assert True\n", encoding="utf-8",
    )
    first_head = commit("first attempt")
    first_diff = git("diff", "--no-ext-diff", "--no-textconv", raised, first_head)
    state = RD.new_state({
        "leg": "code", "vendors": ["claude", "codex"], "fixerVendor": "claude",
        "repoRoot": str(repo), "headSha": raised, "diff": "",
    })
    config = state["config"]
    state["round"] = 2
    state["rounds"]["1"] = {"fixFoldHead": first_head}
    state["headDiff"] = first_diff
    state["fixBatch"] = [{
        "file": path, "line": 4, "title": "Remove duplicate test",
        "severity": "Important", "dimension": "Test", "taxonomy": "duplicate-test",
        "body": "The second test duplicates the first without covering another input.",
        SC.RAISED_ROUND_FIELD: 1,
    }]
    (first_target,) = RD._audit_targets(
        state, config, {}, reviewed_diff="", removal_base=raised, removal_head=first_head,
    )
    assert first_target["citationFresh"] is True

    # _settle_delta copies unresolved audit targets into the next fix batch.
    state["fixBatch"] = [dict(first_target)]
    test_file.write_text(kept, encoding="utf-8")
    fixed_head = commit("remove the cited duplicate")
    state["round"] = 3
    state["rounds"]["2"] = {"fixFoldHead": fixed_head}
    state["headDiff"] = git("diff", "--no-ext-diff", "--no-textconv", raised, fixed_head)
    (retry_target,) = RD._audit_targets(
        state, config, {}, reviewed_diff=first_diff,
        removal_base=first_head, removal_head=fixed_head,
    )
    evidence, failing, detail = audits.test_removal_clearance(retry_target)
    assert evidence is not None, (failing, detail, retry_target["citationCheck"])
