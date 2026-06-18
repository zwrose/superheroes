import json
import os

import band_lib
import enforcer

# Resolve the REAL in-repo escalation.py so classify_floor / guard run for real.
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_ESC = os.path.join(_REPO, "plugins", "the-architect", "lib", "escalation.py")


def _point_at_real_escalation(monkeypatch):
    monkeypatch.setattr(band_lib, "resolve_target",
                        lambda target, root=None, plugin_root=None: _ESC)


# --- command deny-list (the enumerated floor) ---
def test_denies_every_merge_shape():
    for cmd in ("gh pr merge 42 --squash",
                "gh api -X PUT repos/o/r/pulls/42/merge",
                "gh api graphql -f query='mutation { mergePullRequest(...) }'"):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_denies_gh_release_and_workflow_run():
    assert enforcer.classify_command("gh release create v1.0.0")[0] == "deny"
    assert enforcer.classify_command("gh workflow run deploy.yml")[0] == "deny"


def test_denies_force_push_and_deploy_and_destructive():
    assert enforcer.classify_command("git push --force origin main")[0] == "deny"
    assert enforcer.classify_command("kubectl apply -f prod.yaml")[0] == "deny"
    assert enforcer.classify_command("psql -c 'DROP TABLE users'")[0] == "deny"


def test_denies_canary():
    assert enforcer.classify_command(": workhorse-enforcer-canary")[0] == "deny"


def test_allows_producer_normal_commands():
    # CRITICAL: the producer's own push MUST be allowed (the classify_floor wedge).
    for ok in ("git commit -m 'wip'", "git push origin my-branch",
               "git push -u origin superheroes/x-abc123",
               "gh pr create --draft", "gh pr ready 42", "gh pr checks 42",
               "npm run build", "python3 lib/engine.py status --json"):
        assert enforcer.classify_command(ok)[0] == "allow", ok


def test_denies_bash_write_to_safety_machinery():
    # band_lib unresolved in the test env → classify_path fail-closes to deny, so any
    # token that IS a band safety basename + a write op denies. Covers the no-space
    # redirect form too (the round-1 `>enforcer.py` bypass).
    for cmd in ("sed -i 's/x/y/' plugins/workhorse/lib/enforcer.py",
                "echo '{}' > hooks.json",
                "echo '{}' >hooks.json",          # no space — must still deny
                ">enforcer.py",                    # bare no-space redirect
                "cp /tmp/x.py escalation.py"):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_allows_bash_write_to_ordinary_file():
    assert enforcer.classify_command("sed -i 's/x/y/' src/app.py")[0] == "allow"
    assert enforcer.classify_command("echo hi > out.txt")[0] == "allow"


def test_bash_write_to_target_repo_lookalike_is_allowed(monkeypatch, tmp_path):
    # Anchoring: a file named like a safety basename but OUTSIDE the band plugin tree
    # (an arbitrary target repo's own file) must NOT be refused — only real band
    # machinery is. `loop_state.py` is already a SAFETY_MACHINERY member, so this
    # exercises the band-root anchoring (not mere absent-membership). Point band_lib at
    # the real escalation so classify_path anchors against the real band roots.
    _point_at_real_escalation(monkeypatch)
    lookalike = tmp_path / "loop_state.py"
    lookalike.write_text("# unrelated target-repo file\n")
    assert enforcer.classify_command("sed -i 's/a/b/' %s" % lookalike)[0] == "allow"


def test_command_fail_closed_on_non_string():
    assert enforcer.classify_command(None)[0] == "deny"


# --- safety-machinery edit guard ---
def test_denies_edit_to_safety_machinery(monkeypatch):
    _point_at_real_escalation(monkeypatch)
    assert enforcer.classify_path(_ESC)[0] == "deny"   # escalation.py is protected


def test_allows_edit_to_ordinary_file(monkeypatch, tmp_path):
    _point_at_real_escalation(monkeypatch)
    ordinary = tmp_path / "app.py"
    ordinary.write_text("x = 1\n")
    assert enforcer.classify_path(str(ordinary))[0] == "allow"


def test_path_fail_closed_on_unresolvable(monkeypatch):
    monkeypatch.setattr(band_lib, "resolve_target",
                        lambda *a, **k: None)
    assert enforcer.classify_path("/anything.py")[0] == "deny"


# --- hook stdin contract ---
def test_hook_denies_bash_floor(capsys):
    enforcer.hook(json.dumps({"tool_name": "Bash",
                              "tool_input": {"command": "gh pr merge 1"}}))
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_allows_bash_safe_is_silent(capsys):
    rc = enforcer.hook(json.dumps({"tool_name": "Bash",
                                   "tool_input": {"command": "git commit -m x"}}))
    assert rc == 0 and capsys.readouterr().out.strip() == ""   # allow == silent


def test_hook_unparseable_fails_closed(capsys):
    enforcer.hook("{ not json")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denies_vercel_prod_shortcut():
    # the standalone production-deploy flag (no 'deploy' subcommand) must deny
    assert enforcer.classify_command("vercel --prod")[0] == "deny"
    assert enforcer.classify_command("npx vercel --prod")[0] == "deny"


def test_allows_production_longflag_lookalike():
    # --production (e.g. npm install --production) must NOT be denied — only --prod
    assert enforcer.classify_command("npm install --production")[0] == "allow"


def test_denies_merge_api_with_variable_pr_number():
    assert enforcer.classify_command("gh api -X PUT repos/o/r/pulls/$PR/merge")[0] == "deny"
    assert enforcer.classify_command(
        "gh api repos/o/r/pulls/${PR_NUMBER}/merge --method PUT")[0] == "deny"


def test_selfcheck_armed(capsys, monkeypatch):
    # hooks.json must exist for "armed"; it is created in Task 6. Assert the
    # classifier half here; the file half is asserted post-Task-6.
    ok = (enforcer.classify_command("gh pr merge 1")[0] == "deny"
          and enforcer.classify_command("git commit -m x")[0] == "allow")
    assert ok
