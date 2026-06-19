import json
import os

import band_lib
import enforcer

# Resolve the REAL in-repo escalation.py so classify_floor / guard run for real.
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_ESC = os.path.join(_REPO, "plugins", "the-architect", "lib", "escalation.py")
_RC_ESC = os.path.join(_REPO, "plugins", "review-crew", "lib", "escalation_resolve.py")
_RC_LOOP = os.path.join(_REPO, "plugins", "review-crew", "lib", "loop_state.py")


def _point_at_real_escalation(monkeypatch):
    monkeypatch.setattr(band_lib, "resolve_target",
                        lambda target, root=None, plugin_root=None: _ESC)


# --- command deny-list (the enumerated floor) ---
def test_denies_every_merge_shape():
    for cmd in ("gh pr merge 42 --squash",
                "gh api -X PUT repos/o/r/pulls/42/merge",
                "gh api graphql -f query='mutation { mergePullRequest(...) }'"):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_denies_push_to_default_branch():
    # security-001: git-native push-to-default-branch paths must be denied.
    for cmd in ("git push origin main",
                "git push origin HEAD:main",
                "git push origin feature-branch:main",
                "git push origin master",
                "git push origin HEAD:master"):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_allows_push_to_feature_branch():
    # Confirm the producer's own feature-branch pushes are still allowed (security-001).
    for cmd in ("git push origin my-branch",
                "git push -u origin superheroes/x-abc123",
                "git push origin superheroes/phase-2a-core"):
        assert enforcer.classify_command(cmd)[0] == "allow", cmd


def test_allows_push_compound_commands_with_main_after_separator():
    # REGRESSION guard (premortem-001): a later `main`/`master` token in a COMPOUND
    # command (after &&, ;, |) must NOT cause the push segment to be denied.
    for cmd in (
        "git push -u origin superheroes/x && git checkout main",
        "git commit -m 'sync main' && git push origin superheroes/y",
        "git push origin superheroes/x ; echo on main",
    ):
        assert enforcer.classify_command(cmd)[0] == "allow", cmd


def test_denies_gh_release_and_workflow_run():
    assert enforcer.classify_command("gh release create v1.0.0")[0] == "deny"
    assert enforcer.classify_command("gh workflow run deploy.yml")[0] == "deny"


def test_denies_force_push_and_deploy_and_destructive():
    assert enforcer.classify_command("git push --force origin main")[0] == "deny"
    assert enforcer.classify_command("kubectl apply -f prod.yaml")[0] == "deny"
    assert enforcer.classify_command("psql -c 'DROP TABLE users'")[0] == "deny"


def test_denies_rm_rf_flag_order_agnostic():
    # rm-rf deny must catch both -rf AND -fr flag orderings (security-002).
    assert enforcer.classify_command("rm -rf /tmp/build")[0] == "deny"
    assert enforcer.classify_command("rm -fr build/")[0] == "deny"
    assert enforcer.classify_command("rm -Rf dist/")[0] == "deny"


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


def test_denies_bash_write_to_safety_machinery_all_ops():
    # Pin every _WRITE_OPS alternative so dropping any one op fails the suite.
    # band_lib unresolved in the test env → classify_path fail-closes to deny,
    # so the point is that each operator is RECOGNIZED (the pre-filter fires).
    for cmd in (
        "echo x >> enforcer.py",           # >> append
        "tee enforcer.py < /tmp/x",        # tee
        "mv /tmp/x enforcer.py",           # mv
        "dd if=/dev/null > enforcer.py",   # dd (redirect form — of= syntax not tokenised)
        "truncate -s0 enforcer.py",        # truncate
        "chmod 777 enforcer.py",           # chmod
        "ln -sf /tmp/x enforcer.py",       # ln
    ):
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


def test_bash_write_band_anchoring_positive(monkeypatch, tmp_path):
    # test-002: pin that the deny comes from the band-root anchoring, not the
    # unresolvable-lib fail-closed branch. With band_lib pointing at real escalation,
    # a write to the REAL band escalation.py denies (band-root anchored), while a
    # same-basename file OUTSIDE the band roots allows.
    _point_at_real_escalation(monkeypatch)
    # Real band file → deny via anchoring
    assert enforcer.classify_command("sed -i 's/x/y/' %s" % _ESC)[0] == "deny"
    # Same basename outside band roots → allow (not false-positive)
    outside = tmp_path / "escalation.py"
    outside.write_text("# unrelated\n")
    assert enforcer.classify_command("sed -i 's/x/y/' %s" % outside)[0] == "allow"


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


def test_path_fail_closed_on_guard_nonzero_returncode(monkeypatch):
    # test-003a: subprocess guard returns non-zero → deny (fail-closed).
    _point_at_real_escalation(monkeypatch)

    class _FakeResult:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(enforcer.subprocess, "run", lambda *a, **k: _FakeResult())
    assert enforcer.classify_path(_ESC)[0] == "deny"


def test_path_fail_closed_on_guard_exception(monkeypatch):
    # test-003b: subprocess raises → deny (fail-closed).
    _point_at_real_escalation(monkeypatch)
    monkeypatch.setattr(enforcer.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert enforcer.classify_path(_ESC)[0] == "deny"


# --- host- and scope-aware gate (issue #14) ---
def _scoped_cwd(tmp_path):
    # A cwd that resolves inside a superheroes repo (has docs/superheroes/).
    (tmp_path / "docs" / "superheroes").mkdir(parents=True, exist_ok=True)
    return str(tmp_path)


def test_gated_is_ask_on_claude_in_scope():
    for cmd in ("gh pr merge 42 --squash", "gh release create v1",
                "git push --force origin main", "kubectl apply -f prod.yaml"):
        assert enforcer.classify_command(cmd, host="claude", in_scope=True)[0] == "ask", cmd


def test_gated_is_deny_on_codex_in_scope():
    # Deny-only host: the deny is the backstop that forces the ask (the hook overlays the
    # single-use allowance flow on top).
    for cmd in ("gh pr merge 42", "gh release create v1", "rm -rf build/"):
        assert enforcer.classify_command(cmd, host="codex", in_scope=True)[0] == "deny", cmd


def test_gated_is_allowed_outside_a_superheroes_repo():
    # Flaw #1: outside a superheroes repo the gate does not fire, on EITHER host.
    for host in ("claude", "codex"):
        for cmd in ("gh pr merge 42", "gh release create v1", "git push -f origin main"):
            assert enforcer.classify_command(cmd, host=host, in_scope=False)[0] == "allow", (host, cmd)


def test_canary_and_safety_writes_are_unconditional_deny():
    # Host/scope NEVER relax the unconditional surfaces.
    for host in ("claude", "codex"):
        for scope in (True, False):
            assert enforcer.classify_command(": workhorse-enforcer-canary",
                                             host=host, in_scope=scope)[0] == "deny"
            assert enforcer.classify_command("sed -i 's/x/y/' enforcer.py",
                                             host=host, in_scope=scope)[0] == "deny"


def test_gated_action_names_the_action():
    assert enforcer.gated_action("gh pr merge 1") == "merge-pr"
    assert enforcer.gated_action("gh release create v1") == "release"
    assert enforcer.gated_action("git commit -m x") is None
    assert enforcer.gated_action(": workhorse-enforcer-canary") is None  # not gated


def test_in_superheroes_repo_walks_up(tmp_path):
    root = tmp_path
    (root / "docs" / "superheroes").mkdir(parents=True)
    nested = root / "a" / "b" / "c"
    nested.mkdir(parents=True)
    assert enforcer._in_superheroes_repo(str(nested)) is True
    assert enforcer._in_superheroes_repo(str(root)) is True


def test_in_superheroes_repo_false_without_marker(tmp_path):
    assert enforcer._in_superheroes_repo(str(tmp_path)) is False
    assert enforcer._in_superheroes_repo(None) is False
    assert enforcer._in_superheroes_repo("") is False


# --- hook stdin contract (host- and scope-aware) ---
def test_hook_asks_on_claude_in_scope(capsys, tmp_path):
    enforcer.hook(json.dumps({"tool_name": "Bash", "cwd": _scoped_cwd(tmp_path),
                              "tool_input": {"command": "gh pr merge 1"}}), host="claude")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_hook_denies_gated_on_codex_in_scope_and_issues_nonce(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    enforcer.hook(json.dumps({"tool_name": "Bash", "cwd": _scoped_cwd(tmp_path),
                              "tool_input": {"command": "gh pr merge 1"}}), host="codex")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    # The deny issued a challenge the agent can relay to `approve` after owner sign-off.
    assert "approve" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_hook_allows_gated_on_codex_after_valid_allowance(capsys, tmp_path, monkeypatch):
    import allowance
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    scoped = _scoped_cwd(tmp_path)
    allowance.clear_all(scoped)
    cmd = "gh pr merge 1"
    # Mint the allowance in the SAME checkout the hook runs in (per-checkout namespace).
    nonce = allowance.challenge(cmd, "merge-pr", cwd=scoped)
    assert allowance.approve(allowance.command_hash(cmd), nonce, cwd=scoped) is True
    # The very next matching call is allowed once (silent), and the allowance is consumed.
    rc = enforcer.hook(json.dumps({"tool_name": "Bash", "cwd": scoped,
                                   "tool_input": {"command": cmd}}), host="codex")
    assert rc == 0 and capsys.readouterr().out.strip() == ""
    # Consumed: a second identical call is denied again (single-use).
    enforcer.hook(json.dumps({"tool_name": "Bash", "cwd": scoped,
                              "tool_input": {"command": cmd}}), host="codex")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_allows_gated_out_of_scope_is_silent(capsys):
    # No cwd → not a superheroes repo → gated action allowed (silent), both hosts.
    for host in ("claude", "codex"):
        rc = enforcer.hook(json.dumps({"tool_name": "Bash",
                                       "tool_input": {"command": "gh pr merge 1"}}), host=host)
        assert rc == 0 and capsys.readouterr().out.strip() == "", host


# --- host-agnostic dispatch: Codex tool names (shell / apply_patch) (issue #14 review) ---
def test_hook_gates_codex_shell_tool_name(capsys, tmp_path, monkeypatch):
    # Codex names its command tool `shell`, not `Bash`. The gate MUST still fire — else
    # the whole Codex mechanism falls through to allow.
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    enforcer.hook(json.dumps({"tool_name": "shell", "cwd": _scoped_cwd(tmp_path),
                              "tool_input": {"command": "gh pr merge 1"}}), host="codex")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_codex_shell_argv_list_command(capsys, tmp_path, monkeypatch):
    # Codex shell may pass an argv LIST; the gate must read it too.
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    enforcer.hook(json.dumps({"tool_name": "shell", "cwd": _scoped_cwd(tmp_path),
                              "tool_input": {"command": ["bash", "-lc", "gh pr merge 1"]}}),
                  host="codex")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_apply_patch_to_safety_machinery_denies(monkeypatch, capsys):
    # Codex's native edit tool is `apply_patch`; an edit to band safety-machinery must be
    # refused (the path lives in the patch body, not a file_path field).
    def _target_aware(target, root=None, plugin_root=None):
        if target == enforcer._ESC:
            return _ESC
        if target == enforcer._RC:
            return _RC_ESC
        return None
    monkeypatch.setattr(band_lib, "resolve_target", _target_aware)
    patch = "*** Begin Patch\n*** Update File: %s\n@@\n-x\n+y\n*** End Patch\n" % _ESC
    enforcer.hook(json.dumps({"tool_name": "apply_patch",
                              "tool_input": {"input": patch}}), host="codex")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_apply_patch_to_ordinary_file_is_silent(monkeypatch, capsys, tmp_path):
    _point_at_real_escalation(monkeypatch)
    ordinary = tmp_path / "app.py"
    ordinary.write_text("x = 1\n")
    patch = "*** Begin Patch\n*** Update File: %s\n@@\n-x\n+y\n*** End Patch\n" % ordinary
    rc = enforcer.hook(json.dumps({"tool_name": "apply_patch",
                                   "tool_input": {"input": patch}}), host="codex")
    assert rc == 0 and capsys.readouterr().out.strip() == ""


def test_hook_apply_patch_add_and_move_to_safety_machinery_deny(monkeypatch, capsys):
    # The patch-target guard must catch every header variant that names a safety file,
    # not just `*** Update File:` — `*** Add File:` and `*** Move to:` too (moving an
    # arbitrary file ONTO a safety basename is the security-interesting one).
    def _target_aware(target, root=None, plugin_root=None):
        if target == enforcer._ESC:
            return _ESC
        if target == enforcer._RC:
            return _RC_ESC
        return None
    monkeypatch.setattr(band_lib, "resolve_target", _target_aware)
    for header in ("*** Add File: %s" % _ESC, "*** Move to: %s" % _ESC):
        patch = "*** Begin Patch\n%s\n@@\n+x\n*** End Patch\n" % header
        enforcer.hook(json.dumps({"tool_name": "apply_patch",
                                  "tool_input": {"input": patch}}), host="codex")
        out = json.loads(capsys.readouterr().out)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny", header


def test_hook_compound_safety_write_plus_gated_never_enters_allowance(capsys, tmp_path, monkeypatch):
    # A command that is BOTH a safety-machinery write AND a gated action must stay an
    # UNCONDITIONAL deny — it must not enter the Codex allowance overlay (else an owner
    # approving the merge would also wave the safety-write through). And no challenge is
    # issued for it.
    import allowance
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    scoped = _scoped_cwd(tmp_path)
    cmd = "cp /tmp/evil.py enforcer.py && gh pr merge 1"
    enforcer.hook(json.dumps({"tool_name": "Bash", "cwd": scoped,
                              "tool_input": {"command": cmd}}), host="codex")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    # No challenge RECORD was written (the overlay was never entered) — proving the
    # safety-write deny didn't leak into the allowance flow. Read the record directly;
    # a bare consume()==False would also pass if a challenge HAD been wrongly written.
    assert allowance._read(allowance._path(allowance.command_hash(cmd), scoped)) is None
    assert allowance.consume(cmd, cwd=scoped) is False


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


# --- review-crew band-root anchoring (code-code-001) ---
def test_denies_edit_to_review_crew_safety_file(monkeypatch):
    # Target-aware monkeypatch: return the real escalation.py for the _ESC target
    # and the real escalation_resolve.py for the _RC target, so band_roots covers
    # the review-crew plugin root and classify_path correctly denies loop_state.py.
    def _target_aware(target, root=None, plugin_root=None):
        if target == enforcer._ESC:
            return _ESC
        if target == enforcer._RC:
            return _RC_ESC
        return None
    monkeypatch.setattr(band_lib, "resolve_target", _target_aware)
    assert enforcer.classify_path(_RC_LOOP)[0] == "deny"


# --- hook() Edit/Write dispatch branch (test-test-001) ---
def test_hook_denies_edit_to_safety_machinery(monkeypatch, capsys):
    # End-to-end: hook() with an Edit payload whose file_path is a safety-machinery
    # file must emit a deny.
    def _target_aware(target, root=None, plugin_root=None):
        if target == enforcer._ESC:
            return _ESC
        if target == enforcer._RC:
            return _RC_ESC
        return None
    monkeypatch.setattr(band_lib, "resolve_target", _target_aware)
    enforcer.hook(json.dumps({"tool_name": "Edit",
                              "tool_input": {"file_path": _ESC}}))
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_allows_edit_to_ordinary_file_is_silent(monkeypatch, capsys, tmp_path):
    # End-to-end: hook() with an Edit payload for an ordinary (non-safety) file
    # must be silent (allow).
    def _target_aware(target, root=None, plugin_root=None):
        if target == enforcer._ESC:
            return _ESC
        if target == enforcer._RC:
            return _RC_ESC
        return None
    monkeypatch.setattr(band_lib, "resolve_target", _target_aware)
    ordinary = tmp_path / "app.py"
    ordinary.write_text("x = 1\n")
    rc = enforcer.hook(json.dumps({"tool_name": "Edit",
                                   "tool_input": {"file_path": str(ordinary)}}))
    assert rc == 0 and capsys.readouterr().out.strip() == ""


