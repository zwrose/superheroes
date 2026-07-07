# plugins/superheroes/lib/tests/test_acceptance_deps_reap.py
#
# Pins the detectability fix: a FAILED `gh pr list` lookup during reap (or discovery) must
# never be folded into the "confirmed absent / nothing to discover" empty-match sentinel.
# A failed lookup is "couldn't check" — it must be reported left-behind / discovery-degraded,
# never silently reported as cleaned up or silently dropped from the discovered list.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_deps as deps
import acceptance_fixture as af


def test_reap_pr_confirmed_absent_when_lookup_succeeds_empty(monkeypatch):
    # rc == 0 with no matching PR -> confirmed gone -> cleaned up.
    def fake_run(args, cwd, timeout=15):
        if args[:3] == ["gh", "pr", "list"]:
            return 0, "", ""
        return 1, "", ""
    monkeypatch.setattr(deps, "_run", fake_run)
    reap = deps.real_reap("root", lambda: None)
    result = reap({"reap": [{"kind": "pr", "name": "some pr title"}], "leave_behind": []})
    assert result["cleaned_up"] == ["some pr title"]
    assert result["left_behind"] == []


def test_reap_pr_failed_lookup_is_left_behind_not_cleaned(monkeypatch):
    # rc != 0 (network blip / rate-limit / timeout) -> "couldn't check", never "already
    # gone". Must be reported left-behind, not silently marked cleaned up.
    def fake_run(args, cwd, timeout=15):
        if args[:3] == ["gh", "pr", "list"]:
            return 1, "", "rate limited"
        return 1, "", ""
    monkeypatch.setattr(deps, "_run", fake_run)
    reap = deps.real_reap("root", lambda: None)
    result = reap({"reap": [{"kind": "pr", "name": "some pr title"}], "leave_behind": []})
    assert result["cleaned_up"] == []
    assert len(result["left_behind"]) == 1
    left = result["left_behind"][0]
    assert left["name"] == "some pr title"
    assert "could not confirm" in left["reason"].lower()


def test_reap_pr_found_and_closed_is_cleaned(monkeypatch):
    def fake_run(args, cwd, timeout=15):
        if args[:3] == ["gh", "pr", "list"]:
            return 0, "42", ""
        if args[:3] == ["gh", "pr", "close"]:
            return 0, "", ""
        return 1, "", ""
    monkeypatch.setattr(deps, "_run", fake_run)
    reap = deps.real_reap("root", lambda: None)
    result = reap({"reap": [{"kind": "pr", "name": "some pr title"}], "leave_behind": []})
    assert result["cleaned_up"] == ["some pr title"]
    assert result["left_behind"] == []


def test_reap_pr_looked_up_by_head_branch_not_free_text_search(monkeypatch):
    # real_discover_artifacts now emits the PR artifact's `name` as its head branch
    # (which embeds the stamp for parse_stamp routing) — real_reap must look it back up
    # by that exact branch (`--head`), never a free-text `--search`.
    calls = []

    def fake_run(args, cwd, timeout=15):
        calls.append(args)
        if args[:3] == ["gh", "pr", "list"]:
            return 0, "42", ""
        if args[:3] == ["gh", "pr", "close"]:
            return 0, "", ""
        return 1, "", ""
    monkeypatch.setattr(deps, "_run", fake_run)
    reap = deps.real_reap("root", lambda: None)
    result = reap({"reap": [{"kind": "pr", "name": "superheroes/accept-harness-xyz-abc123"}],
                   "leave_behind": []})
    assert result["cleaned_up"] == ["superheroes/accept-harness-xyz-abc123"]
    list_calls = [c for c in calls if c[:3] == ["gh", "pr", "list"]]
    assert len(list_calls) == 1
    assert "--head" in list_calls[0]
    assert "superheroes/accept-harness-xyz-abc123" in list_calls[0]
    assert "--search" not in list_calls[0]


def test_discover_branch_lookup_failure_surfaces_degraded_placeholder_not_silently_dropped(monkeypatch):
    def fake_run(args, cwd, timeout=15):
        if args[:2] == ["git", "branch"]:
            return 1, "", "git failed"
        if args[:3] == ["gh", "pr", "list"]:
            return 0, "", ""
        return 1, "", ""
    monkeypatch.setattr(deps, "_run", fake_run)
    discover = deps.real_discover_artifacts("root")
    artifacts = discover("some-stamp")
    branch_artifacts = [a for a in artifacts if a["kind"] == "branch"]
    assert len(branch_artifacts) == 1
    name = branch_artifacts[0]["name"]
    assert name.startswith(af.RESERVED_PREFIX)
    # Must NOT parse to a valid full stamp (never silently reaped as if it were real).
    assert af.parse_stamp(name) is None
    assert "degraded" in name.lower()


def test_discover_pr_lookup_failure_surfaces_degraded_placeholder_not_silently_dropped(monkeypatch):
    def fake_run(args, cwd, timeout=15):
        if args[:2] == ["git", "branch"]:
            return 0, "", ""
        if args[:3] == ["gh", "pr", "list"]:
            return 1, "", "gh failed"
        return 1, "", ""
    monkeypatch.setattr(deps, "_run", fake_run)
    discover = deps.real_discover_artifacts("root")
    artifacts = discover("some-stamp")
    pr_artifacts = [a for a in artifacts if a["kind"] == "pr"]
    assert len(pr_artifacts) == 1
    name = pr_artifacts[0]["name"]
    assert name.startswith(af.RESERVED_PREFIX)
    assert af.parse_stamp(name) is None
    assert "degraded" in name.lower()


def test_discover_success_lists_no_degraded_placeholder(monkeypatch):
    def fake_run(args, cwd, timeout=15):
        if args[:2] == ["git", "branch"]:
            return 0, "", ""
        if args[:3] == ["gh", "pr", "list"]:
            return 0, "", ""
        return 1, "", ""
    monkeypatch.setattr(deps, "_run", fake_run)
    discover = deps.real_discover_artifacts("root")
    artifacts = discover("some-stamp")
    assert artifacts == []


def test_discover_strips_worktree_checkout_marker_from_branch_names(monkeypatch):
    """0.10.0 qualification finding #8a: `git branch --list` prefixes a branch checked out
    in another worktree with "+ " — every live build branch. The old parse stripped only
    "* ", so reap ran `git branch -D "+ superheroes/..."` and stranded the branch."""
    def fake_run(argv, cwd=None):
        if argv[:3] == ["git", "branch", "--list"]:
            return 0, "+ superheroes/accept-harness-aa11bb22-cafe\n* main\n", ""
        return 0, "", ""
    monkeypatch.setattr(deps, "_run", fake_run)
    discover = deps.real_discover_artifacts("/repo")
    names = [a["name"] for a in discover("accept-harness-aa11bb22") if a["kind"] == "branch"]
    assert "superheroes/accept-harness-aa11bb22-cafe" in names
    assert not any(n.startswith("+") for n in names)


def test_reap_branch_checked_out_in_worktree_removes_worktree_then_deletes(monkeypatch):
    """0.10.0 qualification finding #8b: a live build branch is checked out in its managed
    worktree, so plain `git branch -D` fails. Reap must remove that worktree first and
    retry — the live run 7 record shows the branch stranded (`reap action failed`)."""
    calls = []
    state = {"worktree_removed": False}
    BR = "superheroes/accept-harness-aa11bb22-cafe"
    WTP = "/wt/accept-harness-aa11bb22-cafe"
    def fake_run(argv, cwd=None):
        calls.append(argv)
        if argv[:3] == ["git", "branch", "-D"]:
            return (0, "", "") if state["worktree_removed"] else (1, "", "checked out at " + WTP)
        if argv[:4] == ["git", "worktree", "list", "--porcelain"]:
            return 0, "worktree /repo\nbranch refs/heads/main\n\nworktree %s\nbranch refs/heads/%s\n" % (WTP, BR), ""
        if argv[:3] == ["git", "worktree", "remove"]:
            state["worktree_removed"] = True
            return 0, "", ""
        return 0, "", ""
    monkeypatch.setattr(deps, "_run", fake_run)
    reap = deps.real_reap("/repo", lambda: None)
    result = reap({"reap": [{"kind": "branch", "name": BR}], "leave_behind": []})
    assert result["cleaned_up"] == [BR]
    assert result["left_behind"] == []
    assert ["git", "worktree", "remove", "--force", WTP] in calls
