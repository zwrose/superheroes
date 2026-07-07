import os

import ci_loop
import control_plane
import enforcer
import permission_rules
import reset


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def test_never_merge_invariant_across_every_merge_shape():
    # The deny-list is self-contained for commands (no classify_floor consult), so
    # every owner-role / repo-shaping shape — merge/release/run-workflow/force-push and
    # the git-native push-to-default-branch paths, incl. the gh-api / GraphQL merge forms
    # — is denied without resolving any sibling lib. (Generic dangerous-command classes
    # like deploy/destructive/rm -rf are deliberately NOT here — see test_enforcer.py
    # ::test_allows_generic_dangerous_commands_left_to_the_harness.)
    for cmd in ("gh pr merge 1", "gh pr merge 1 --squash --admin",
                "gh pr merge --auto 1",
                "gh api -X PUT repos/o/r/pulls/1/merge",
                "gh api graphql -f query='mutation { mergePullRequest }'",
                "gh release create v1", "gh workflow run deploy.yml",
                "git push --force-with-lease", "git push -f origin main",
                # git-native push-to-default-branch (security-001)
                "git push origin main",
                "git push origin HEAD:main",
                "git push origin feature-branch:main",
                "git push origin master",
                "git push origin HEAD:master"):
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


def test_permission_store_never_resolves_inside_the_repo_tree():
    # Task 15 criterion (c): the permission rules store is an OUT-OF-REPO data store —
    # it must never resolve to a path under the repo working tree (no committed rule
    # artifact, no session-local repo write). The store dir is config-keyed under
    # control_plane.store_root(); with the default root it lands under ~/.claude/superheroes,
    # never under the repo. A regression that re-rooted the store into the repo (e.g.
    # defaulting to a repo-relative path) would leak a data artifact and fail here.
    repo = os.path.realpath(_repo_root())
    # Resolve against the real default root (no `root=` override), from a cwd inside the repo.
    store_dir = os.path.realpath(permission_rules._store_dir(repo))
    assert store_dir.startswith(os.path.realpath(control_plane.store_root())), store_dir
    # And it is not a descendant of the repo tree.
    assert os.path.commonpath([store_dir, repo]) != repo, \
        "permission store must not resolve inside the repo tree (Task 15 criterion c): %s" % store_dir


def test_enforcer_selfcheck_passes_with_allowance_layer_present():
    # Task 15 criterion (a): the enforcer selfcheck still exits 0 (all invariants hold)
    # with the below-the-floor allowance layer wired in. A broken allowance layer that
    # widened the owner-role floor, or that raised, would flip selfcheck non-zero.
    assert enforcer.selfcheck() == 0


def test_showrunner_path_is_superpowers_free():
    root = _repo_root()
    # (a) the showrunner authoring leaf names NO superpowers toolkit — it authors natively (FR-8).
    leaf = open(os.path.join(root, "plugins/superheroes/eval/produce-leaf.md")).read().lower()
    assert "superpowers" not in leaf, \
        "produce-leaf (the showrunner authoring path) must name no superpowers toolkit (FR-8)"
    # (b) the generated live bundle invokes no superpowers skill — a residual call fails CI loudly.
    bundle = os.path.join(root, "plugins/superheroes/lib/showrunner.bundle.js")
    if os.path.exists(bundle):
        b = open(bundle).read().lower()
        for token in ("superpowers", "writing-plans", "subagent-driven"):
            assert token not in b, "showrunner bundle must not reference %s (FR-8)" % token
