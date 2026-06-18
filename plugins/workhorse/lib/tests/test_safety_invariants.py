import ci_loop
import enforcer
import reset


def test_never_merge_invariant_across_every_merge_shape():
    # The deny-list is self-contained for commands (no classify_floor consult), so
    # every merge/release/deploy/force-push shape — incl. the gh-api / GraphQL forms —
    # is denied without resolving any sibling lib.
    for cmd in ("gh pr merge 1", "gh pr merge 1 --squash --admin",
                "gh pr merge --auto 1",
                "gh api -X PUT repos/o/r/pulls/1/merge",
                "gh api graphql -f query='mutation { mergePullRequest }'",
                "gh release create v1", "gh workflow run deploy.yml",
                "git push --force-with-lease", "git push -f origin main"):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_producer_push_is_allowed():
    # The never-merge floor must NOT wedge the producer's own required pushes.
    assert enforcer.classify_command("git push -u origin superheroes/x-abc123")[0] == "allow"


def test_parks_safely_decision_on_gate():
    # On a GATE, reset.plan_reset must never claim a clean baseline under a live lock.
    assert reset.plan_reset({"entries": [], "lock": {"pid": 1},
                             "lockStale": False})[0] == "gate"


def test_ci_loop_cannot_run_forever():
    # No matter the history, at the cap it halts (revert + GATE).
    assert ci_loop.decide(["x"], history=[["a"], ["b"], ["c"], ["d"]],
                          rnd=5, max_rounds=5)[0] == "revert_and_gate"


def test_command_path_fails_closed_on_non_string():
    # The command path's fail-closed surface is a non-string command (process-level
    # failure is the hook wrapper's job, §Task 6); a None command must deny.
    assert enforcer.classify_command(None)[0] == "deny"
