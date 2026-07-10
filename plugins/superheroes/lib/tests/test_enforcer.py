import json
import os

import pytest

import enforcer

# The REAL in-tree safety files (all under the single superheroes plugin root, which is what
# classify_path anchors against via escalation.is_safety_machinery). No band_lib resolution /
# monkeypatch is needed any more — the guard runs directly against the real in-tree layout.
_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LIB = os.path.join(_PLUGIN, "lib")
_ESC = os.path.join(_LIB, "escalation.py")
_RC_ESC = os.path.join(_LIB, "escalation_resolve.py")
_RC_LOOP = os.path.join(_LIB, "loop_state.py")
_ENFORCER = os.path.join(_LIB, "enforcer.py")
_HOOKS = os.path.join(_PLUGIN, "hooks", "hooks.json")



@pytest.fixture
def basename_guard(monkeypatch):
    """Recreate the old test-env condition for the redirect/exec TARGET-precision tests: in the
    pre-collapse env band_lib was unresolved, so classify_path fail-closed to deny for ANY
    safety-basename token — meaning those cases pinned the TARGET logic in
    _bash_writes_to_safety_machinery alone, NOT the guard resolution. Now that the guard
    resolves for real, we patch escalation.is_safety_machinery to a basename-only matcher so
    bare in-test basenames still "resolve", and the tests keep pinning TARGET precision."""
    monkeypatch.setattr(
        enforcer.escalation, "is_safety_machinery",
        lambda path, band_roots: bool(isinstance(path, str)
                                      and os.path.basename(path) in enforcer._SAFETY_BASENAMES))


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


def test_denies_force_push():
    # force-push stays gated — it's the producer's "never rewrite shared history" invariant.
    assert enforcer.classify_command("git push --force origin main")[0] == "deny"


def test_allows_generic_dangerous_commands_left_to_the_harness():
    # Generic dangerous-command classes are deliberately OFF the deterministic hook (they're
    # contemplated by the host harness's permission prompt + `rm -rf /|~` circuit breaker, and
    # covered by the cooperative F5 layer). The enforcer must ALLOW them so it doesn't
    # false-positive on routine build commands or duplicate harness controls.
    for cmd in ("kubectl apply -f prod.yaml",        # deploy
                "terraform apply",                    # deploy
                "vercel --prod",                      # deploy (--prod shortcut)
                "npx vercel --prod",
                "psql -c 'DROP TABLE users'",         # destructive SQL
                "psql -c 'TRUNCATE events'",
                "rm -rf /tmp/build",                  # rm -rf (routine cleanup)
                "rm -rf node_modules",
                "rm -fr build/",
                "rm -Rf dist/"):
        assert enforcer.classify_command(cmd)[0] == "allow", cmd


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
    # The guard now resolves for real (in one tree): a write op AT a REAL in-tree band file
    # denies via band-root anchoring. Covers the no-space redirect form too (the round-1
    # `>enforcer.py` bypass). Repointed from the old bare/relative basenames (which only
    # denied because band_lib was unresolved in the old test env) to real in-tree paths.
    for cmd in ("sed -i 's/x/y/' %s" % _ENFORCER,
                "echo '{}' > %s" % _HOOKS,
                "echo '{}' >%s" % _HOOKS,          # no space — must still deny
                ">%s" % _ENFORCER,                  # bare no-space redirect
                "cp /tmp/x.py %s" % _ESC):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_denies_bash_write_to_safety_machinery_all_ops():
    # Pin every _WRITE_OPS alternative so dropping any one op fails the suite. The target is a
    # REAL in-tree band file so the band-root-anchored guard denies; the point is that each
    # operator is RECOGNIZED (the pre-filter fires) and the write AT the band file denies.
    for cmd in (
        "echo x >> %s" % _ENFORCER,           # >> append
        "tee %s < /tmp/x" % _ENFORCER,        # tee
        "mv /tmp/x %s" % _ENFORCER,           # mv
        "dd if=/dev/null > %s" % _ENFORCER,   # dd (redirect form — of= syntax not tokenised)
        "truncate -s0 %s" % _ENFORCER,        # truncate
        "chmod 777 %s" % _ENFORCER,           # chmod
        "ln -sf /tmp/x %s" % _ENFORCER,       # ln
    ):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_allows_bash_write_to_ordinary_file():
    assert enforcer.classify_command("sed -i 's/x/y/' src/app.py")[0] == "allow"
    assert enforcer.classify_command("echo hi > out.txt")[0] == "allow"


def test_bash_write_to_target_repo_lookalike_is_allowed(tmp_path):
    # Anchoring: a file named like a safety basename but OUTSIDE the band plugin tree
    # (an arbitrary target repo's own file) must NOT be refused — only real band
    # machinery is. `loop_state.py` is already a SAFETY_MACHINERY member, so this
    # exercises the band-root anchoring (not mere absent-membership). classify_path now
    # anchors against the real in-tree plugin root directly (no band_lib monkeypatch).
    lookalike = tmp_path / "loop_state.py"
    lookalike.write_text("# unrelated target-repo file\n")
    assert enforcer.classify_command("sed -i 's/a/b/' %s" % lookalike)[0] == "allow"


def test_bash_write_band_anchoring_positive(tmp_path):
    # test-002: pin that the deny comes from the band-root anchoring. A write to the REAL
    # in-tree band escalation.py denies (band-root anchored), while a same-basename file
    # OUTSIDE the band root allows.
    # Real band file → deny via anchoring
    assert enforcer.classify_command("sed -i 's/x/y/' %s" % _ESC)[0] == "deny"
    # Same basename outside band roots → allow (not false-positive)
    outside = tmp_path / "escalation.py"
    outside.write_text("# unrelated\n")
    assert enforcer.classify_command("sed -i 's/x/y/' %s" % outside)[0] == "allow"


# --- redirect/exec TARGET precision (workhorse-2026-06-20 false-positive fix) ---
# REGRESSION: _bash_writes_to_safety_machinery used to deny ANY command that paired a bare
# write-operator token (`>`, `>>`, `2>&1`) with a safety-basename token appearing ANYWHERE
# — even when the safety file was an EXECUTION arg and the redirect targeted /dev/null. The
# guard must key off the write operator's TARGET, not mere co-occurrence. These tests use the
# `basename_guard` fixture so any safety-basename token "resolves" (recreating the old
# unresolved-lib env), forcing each case to pass on TARGET logic ALONE.
def test_allows_executing_band_cli_with_unrelated_redirect(basename_guard):
    # Running a band CLI (a safety basename as the EXECUTION target) with a >/dev/null or
    # 2>&1 redirect is NOT a write to the band file — the redirect targets /dev/null / an fd.
    for cmd in (
        "python3 plugins/superheroes/lib/definition_doc.py read-gate >/dev/null",
        "python3 plugins/superheroes/lib/definition_doc.py read-gate > /dev/null 2>&1",
        "python3 plugins/superheroes/lib/gate_write.py set k v 2>&1",
    ):
        assert enforcer.classify_command(cmd)[0] == "allow", cmd


def test_allows_compound_band_cli_calls_with_redirect(basename_guard):
    # The real-world compounds that tripped the false positive: a band CLI executed in one
    # segment (a safety basename as exec target) while a /dev/null redirect rides elsewhere.
    for cmd in (
        "GATE=$(python3 a/definition_doc.py set-gate g) ; "
        "python3 b/decisions.py append \"$DEC\" \"$1\" >/dev/null 2>&1",
        "python3 b/decisions.py append \"$DEC\" x >/dev/null 2>&1 && "
        "python3 a/definition_doc.py read-gate g",
    ):
        assert enforcer.classify_command(cmd)[0] == "allow", cmd


def test_allows_reading_band_file_redirected_elsewhere(basename_guard):
    # Reading a band file and redirecting stdout to a NON-band path is not a write to it.
    assert enforcer.classify_command("grep x enforcer.py > /tmp/out.txt")[0] == "allow"


def test_still_denies_redirect_AT_band_file(basename_guard):
    # The genuine write-AT-a-band-file via redirection stays denied (target IS the band
    # file), incl. the no-space and stderr-redirect forms.
    for cmd in ("echo x > enforcer.py", "echo x >>enforcer.py",
                "echo '{}' > hooks.json", "python3 gen.py 2>escalation.py"):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_still_denies_file_mutating_command_at_band_file(basename_guard):
    # sed -i / cp / mv with a band file as an ARGUMENT stay denied.
    for cmd in ("sed -i 's/x/y/' plugins/superheroes/lib/enforcer.py",
                "cp /tmp/x.py escalation.py",
                "mv /tmp/x definition_doc.py"):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_denies_quoted_redirect_target_at_band_file(basename_guard):
    # security-001 / code-001: a QUOTED redirect target must still be denied. The old
    # whole-command tokenizer stripped quotes; the redirect-target path must too, else
    # `echo x > "enforcer.py"` becomes a guard bypass.
    for cmd in ('echo x > "enforcer.py"', "echo x >'enforcer.py'",
                'echo x >"hooks.json"', 'python3 gen.py 2>"escalation.py"'):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_denies_noclobber_and_combined_redirect_at_band_file(basename_guard):
    # premortem-001 (`>|` noclobber override) and test-001 (`&>`/`&>>` combined redirect):
    # both are redirect-AT-a-band-file forms and must be denied.
    for cmd in ("echo x >|enforcer.py", "python3 gen.py 2>|escalation.py",
                "echo x &>enforcer.py", "python3 gen.py &>>hooks.json"):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_denies_sed_long_form_in_place_at_band_file(basename_guard):
    # GNU sed's long-form `--in-place` (and `--in-place=SUFFIX`) is an in-place write just
    # like `-i`; a band file argument must be denied. An ordinary file stays allowed.
    for cmd in ("sed --in-place 's/x/y/' plugins/superheroes/lib/enforcer.py",
                "sed --in-place=.bak 's/x/y/' hooks.json"):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd
    assert enforcer.classify_command("sed --in-place 's/x/y/' src/app.py")[0] == "allow"


def test_denies_dd_of_keyword_operand_at_band_file(basename_guard):
    # premortem-002: `dd` names its write destination with the `of=<path>` keyword operand,
    # not a bare positional arg, so the basename pre-filter must see through `of=`.
    for cmd in ("dd of=enforcer.py",
                "dd bs=1 count=0 of=plugins/superheroes/lib/enforcer.py"):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_allows_quoted_nonband_redirect_target(basename_guard):
    # The broadened redirect/operand parsing must not over-deny a quoted NON-band target,
    # nor an ordinary dd whose of= destination is not a band file.
    assert enforcer.classify_command('python3 x.py > "/dev/null" 2>&1')[0] == "allow"
    assert enforcer.classify_command("echo hi > 'out.txt'")[0] == "allow"
    assert enforcer.classify_command("dd if=/dev/null of=/tmp/out bs=1")[0] == "allow"


def test_denies_ampersand_redirect_at_band_file(basename_guard):
    # security-001/code-001 (round 2): `>&<filename>` (and `>>&`) redirects BOTH stdout and
    # stderr INTO the file — a real truncating write, equivalent to `&>file`. Only the
    # `>&<digit>` / `>&-` forms are fd duplications. The filename form must be denied (the
    # old whole-command tokenizer caught it).
    for cmd in ("echo x >&enforcer.py", "echo x >&'hooks.json'",
                "echo x >>&escalation.py"):
        assert enforcer.classify_command(cmd)[0] == "deny", cmd


def test_allows_fd_duplication_not_treated_as_write():
    # `>&<digit>`, `2>&1`, and `>&-` (close) are fd manipulations, not file writes — they
    # must stay allowed even though the broadened operator now consumes the `&`.
    for cmd in ("python3 x.py >&2", "python3 x.py 2>&1", "python3 x.py >&-"):
        assert enforcer.classify_command(cmd)[0] == "allow", cmd


def test_command_fail_closed_on_non_string():
    assert enforcer.classify_command(None)[0] == "deny"


# --- safety-machinery edit guard ---
def test_denies_edit_to_safety_machinery():
    assert enforcer.classify_path(_ESC)[0] == "deny"   # escalation.py is protected


def test_allows_edit_to_ordinary_file(tmp_path):
    ordinary = tmp_path / "app.py"
    ordinary.write_text("x = 1\n")
    assert enforcer.classify_path(str(ordinary))[0] == "allow"


# Equivalence note: `test_path_fail_closed_on_unresolvable` (band_lib.resolve_target -> None)
# and `test_path_fail_closed_on_guard_nonzero_returncode` (subprocess returncode != 0) tested
# branches that no longer exist in one tree — there is no cross-plugin lib to be unresolvable
# and no guard subprocess to return non-zero. classify_path now calls escalation.is_safety_machinery
# directly. The PRESERVED fail-closed branch (the try/except: any core error -> deny) is covered
# by the re-expressed test below.

def test_path_fail_closed_on_guard_exception(monkeypatch):
    # test-003b (re-expressed): the in-tree guard raising → deny (fail-closed). Patches the
    # direct seam (escalation.is_safety_machinery) instead of the removed subprocess seam.
    monkeypatch.setattr(enforcer.escalation, "is_safety_machinery",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert enforcer.classify_path(_ESC)[0] == "deny"


# --- host- and scope-aware gate (issue #14) ---
def _scoped_cwd(tmp_path):
    # A cwd that resolves inside a superheroes repo (has docs/superheroes/).
    (tmp_path / "docs" / "superheroes").mkdir(parents=True, exist_ok=True)
    return str(tmp_path)


def test_gated_is_ask_on_claude_in_scope():
    for cmd in ("gh pr merge 42 --squash", "gh release create v1",
                "git push --force origin main", "git push origin main",
                "gh workflow run deploy.yml"):
        assert enforcer.classify_command(cmd, host="claude", in_scope=True)[0] == "ask", cmd


def test_gated_is_deny_on_codex_in_scope():
    # Deny-only host: the deny is the backstop that forces the ask (the hook overlays the
    # single-use allowance flow on top).
    for cmd in ("gh pr merge 42", "gh release create v1", "git push --force-with-lease"):
        assert enforcer.classify_command(cmd, host="codex", in_scope=True)[0] == "deny", cmd


def test_gated_is_allowed_outside_a_superheroes_repo():
    # Flaw #1: outside a superheroes repo the gate does not fire, on EITHER host.
    for host in ("claude", "codex"):
        for cmd in ("gh pr merge 42", "gh release create v1", "git push -f origin main"):
            assert enforcer.classify_command(cmd, host=host, in_scope=False)[0] == "allow", (host, cmd)


def test_canary_and_safety_writes_are_unconditional_deny(basename_guard):
    # Host/scope NEVER relax the unconditional surfaces. (basename_guard so the bare
    # `enforcer.py` safety-write target "resolves" — TARGET logic is what's under test.)
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


def test_hook_apply_patch_to_safety_machinery_denies(capsys):
    # Codex's native edit tool is `apply_patch`; an edit to band safety-machinery must be
    # refused (the path lives in the patch body, not a file_path field). No band_lib
    # monkeypatch needed — _ESC is the REAL in-tree escalation.py, so the direct guard denies.
    patch = "*** Begin Patch\n*** Update File: %s\n@@\n-x\n+y\n*** End Patch\n" % _ESC
    enforcer.hook(json.dumps({"tool_name": "apply_patch",
                              "tool_input": {"input": patch}}), host="codex")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_apply_patch_to_ordinary_file_is_silent(monkeypatch, capsys, tmp_path):
    ordinary = tmp_path / "app.py"
    ordinary.write_text("x = 1\n")
    patch = "*** Begin Patch\n*** Update File: %s\n@@\n-x\n+y\n*** End Patch\n" % ordinary
    rc = enforcer.hook(json.dumps({"tool_name": "apply_patch",
                                   "tool_input": {"input": patch}}), host="codex")
    assert rc == 0 and capsys.readouterr().out.strip() == ""


def test_hook_apply_patch_add_and_move_to_safety_machinery_deny(capsys):
    # The patch-target guard must catch every header variant that names a safety file,
    # not just `*** Update File:` — `*** Add File:` and `*** Move to:` too (moving an
    # arbitrary file ONTO a safety basename is the security-interesting one). _ESC is the real
    # in-tree file, so the direct guard denies (no band_lib monkeypatch).
    for header in ("*** Add File: %s" % _ESC, "*** Move to: %s" % _ESC):
        patch = "*** Begin Patch\n%s\n@@\n+x\n*** End Patch\n" % header
        enforcer.hook(json.dumps({"tool_name": "apply_patch",
                                  "tool_input": {"input": patch}}), host="codex")
        out = json.loads(capsys.readouterr().out)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny", header


def test_hook_compound_safety_write_plus_gated_never_enters_allowance(capsys, tmp_path, monkeypatch, basename_guard):
    # A command that is BOTH a safety-machinery write AND a gated action must stay an
    # UNCONDITIONAL deny — it must not enter the Codex allowance overlay (else an owner
    # approving the merge would also wave the safety-write through). And no challenge is
    # issued for it. (basename_guard so the bare `enforcer.py` write target "resolves".)
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


def test_denies_merge_api_with_variable_pr_number():
    assert enforcer.classify_command("gh api -X PUT repos/o/r/pulls/$PR/merge")[0] == "deny"
    assert enforcer.classify_command(
        "gh api repos/o/r/pulls/${PR_NUMBER}/merge --method PUT")[0] == "deny"


# --- band-root anchoring (code-code-001) ---
def test_denies_edit_to_review_crew_safety_file():
    # In one tree the (formerly review-crew) safety files live under the single merged plugin
    # root, which is exactly what classify_path anchors against. No band_lib monkeypatch — the
    # direct guard denies the real in-tree loop_state.py via band-root anchoring.
    assert enforcer.classify_path(_RC_LOOP)[0] == "deny"


# --- hook() Edit/Write dispatch branch (test-test-001) ---
def test_hook_denies_edit_to_safety_machinery(capsys):
    # End-to-end: hook() with an Edit payload whose file_path is a safety-machinery
    # file must emit a deny. _ESC is the real in-tree file → the direct guard denies.
    enforcer.hook(json.dumps({"tool_name": "Edit",
                              "tool_input": {"file_path": _ESC}}))
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_allows_edit_to_ordinary_file_is_silent(capsys, tmp_path):
    # End-to-end: hook() with an Edit payload for an ordinary (non-safety) file
    # must be silent (allow).
    ordinary = tmp_path / "app.py"
    ordinary.write_text("x = 1\n")
    rc = enforcer.hook(json.dumps({"tool_name": "Edit",
                                   "tool_input": {"file_path": str(ordinary)}}))
    assert rc == 0 and capsys.readouterr().out.strip() == ""


# --- #38 DoD: owner-authority boundary holds for external-engine-dispatched commands ---
def test_external_engine_paths_still_gate_owner_authority():
    # #38: an external producer is CONFINED, not policed — the enforcer fires on the HOST's Bash
    # invocation regardless of whether the command was authored for a codex/cursor dispatch. The
    # owner-authority set (merge / release / force-push / push-to-default / run-workflow) stays gated,
    # so an external engine can never autonomously merge/force-push/push-to-default.
    for cmd in (
        "gh pr merge 42 --squash",
        "gh api -X PUT repos/o/r/pulls/42/merge",
        "gh release create v1.0.0",
        "git push --force origin superheroes/x",
        "git push origin HEAD:main",
        "gh workflow run deploy.yml",
    ):
        # Codex host: gated -> deny (ask is not honored -> fail-safe deny + allowance flow).
        assert enforcer.classify_command(cmd, host="codex", in_scope=True)[0] == "deny", cmd
        # Claude host: gated -> ask (a native human prompt the agent cannot answer itself).
        assert enforcer.classify_command(cmd, host="claude", in_scope=True)[0] == "ask", cmd


def test_external_engine_own_feature_branch_push_is_allowed():
    # The producer's OWN feature-branch push (no :main / force) is allowed — the named residual is
    # contained by the single-owner threat model (the engine is the owner's own signed-in tool).
    assert enforcer.classify_command("git push origin superheroes/x-abc", host="codex")[0] == "allow"
    assert enforcer.classify_command("cursor-agent -f -m composer", host="codex")[0] == "allow"


# --- Task 5: allowance layer wired into the NON-GATED branch only (UFR-1/UFR-2) ---
# enforcer's import inserts lib/ onto sys.path, so the sibling core is importable here.
import permission_rules  # noqa: E402


def test_owner_role_outcome_unchanged_with_rules_present(monkeypatch):
    # A rule that would match a merge must never flip the floor's ask/deny — the allowance
    # layer is NEVER consulted on the gated branch (it returns before the layer's call site).
    monkeypatch.setattr(permission_rules, "evaluate",
                        lambda *a, **k: ("allow", "should-not-be-consulted"))
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=True)[0] == "ask"
    assert enforcer.classify_command("gh pr merge 1", host="codex", in_scope=True)[0] == "deny"
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=False)[0] == "allow"


def test_non_gated_command_allowed_when_rule_matches(monkeypatch):
    monkeypatch.setattr(permission_rules, "evaluate",
                        lambda *a, **k: ("allow", "routine:test-run"))
    decision, reason = enforcer.classify_command("python3 -m pytest", host="claude", in_scope=True)
    assert decision == "allow"
    # The allowance layer must actually be consulted — its reason surfaces (distinguishes an
    # auto-allow from today's default-allow, which would otherwise mask an unwired layer).
    assert "auto-allowed" in reason and "routine:test-run" in reason


def test_non_gated_command_falls_through_to_default_allow(monkeypatch):
    monkeypatch.setattr(permission_rules, "evaluate", lambda *a, **k: ("fall", "no match"))
    # today's outcome is preserved (default allow)
    assert enforcer.classify_command("python3 -m pytest", host="claude", in_scope=True)[0] == "allow"


def test_allowance_exception_falls_through(monkeypatch):
    monkeypatch.setattr(permission_rules, "evaluate",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert enforcer.classify_command("python3 -m pytest", host="claude", in_scope=True)[0] == "allow"


def test_unconditional_surfaces_still_deny_before_allowance(monkeypatch):
    monkeypatch.setattr(permission_rules, "evaluate",
                        lambda *a, **k: ("allow", "should-not-be-reached"))
    assert enforcer.classify_command(": workhorse-enforcer-canary")[0] == "deny"


# --- Task 6: hook threads cwd + run_id; selfcheck asserts the invariant (UFR-1) ---


def test_hook_passes_cwd_run_id_and_work_item(monkeypatch):
    # The hook resolves the (work_item, run_id) PAIR once via the shared lease seam and
    # threads BOTH into classify_command (work_item namespaces the frozen-file read and
    # keeps the allowance journal attributed to the same run the evaluation used).
    seen = {}

    def fake_classify(command, host="codex", in_scope=True, cwd=None, run_id=None, work_item=None):
        seen.update(cwd=cwd, run_id=run_id, work_item=work_item)
        return ("allow", "")

    monkeypatch.setattr(enforcer, "classify_command", fake_classify)
    monkeypatch.setattr(enforcer.permission_rules, "resolve_active_lease",
                        lambda cwd, run_id=None: ("wi-9", "RUN9"))
    payload = '{"tool_name":"Bash","tool_input":{"command":"python3 -m pytest"},"cwd":"/w"}'
    enforcer.hook(payload, host="claude")
    assert seen["cwd"] == "/w" and seen["run_id"] == "RUN9" and seen["work_item"] == "wi-9"


def test_selfcheck_matrix_holds_with_allowance(monkeypatch):
    assert enforcer.selfcheck() == 0   # the added assertions pass on a correct build



# --- Task 8: deny-only marker (UFR-6) — the acceptance-harness never-merge floor ---
MARKER = "SUPERHEROES_ACCEPTANCE_DENY_ONLY"


def _with_marker(monkeypatch, on):
    if on:
        monkeypatch.setenv(MARKER, "1")
    else:
        monkeypatch.delenv(MARKER, raising=False)


def test_deny_only_marker_turns_claude_ask_into_deny(monkeypatch):
    _with_marker(monkeypatch, True)
    # without the marker, claude in-scope gets ask; with it, deny.
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=True)[0] == "deny"


def test_deny_only_marker_covers_full_owner_authority_set(monkeypatch):
    _with_marker(monkeypatch, True)
    for cmd in ["gh pr merge 1", "gh release create v1", "gh workflow run ci",
                "git push --force origin b", "git push origin main"]:
        assert enforcer.classify_command(cmd, host="claude", in_scope=True)[0] == "deny", cmd


def test_without_marker_claude_still_asks(monkeypatch):
    _with_marker(monkeypatch, False)
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=True)[0] == "ask"


def test_marker_does_not_change_ordinary_commands(monkeypatch):
    _with_marker(monkeypatch, True)
    assert enforcer.classify_command("git commit -m x", host="claude", in_scope=True)[0] == "allow"


def test_deny_only_marker_denies_out_of_scope_from_build_worktree(monkeypatch):
    # UFR-6 security floor: the showrunner child's Build phase runs from a build worktree
    # whose fresh checkout has no docs/superheroes/ (gitignored), so in_scope resolves False.
    # Without the marker, out-of-scope owner-authority is allowed; UNDER the marker it MUST
    # still deny — the marker deny is evaluated before the `if not in_scope: allow` short-circuit.
    _with_marker(monkeypatch, True)
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=False)[0] == "deny"
    for cmd in ["gh release create v1", "gh workflow run ci",
                "git push --force origin b", "git push origin main"]:
        assert enforcer.classify_command(cmd, host="claude", in_scope=False)[0] == "deny", cmd
    # the marker does NOT widen non-gated commands: ordinary out-of-scope stays allow.
    assert enforcer.classify_command("git commit -m x", host="claude", in_scope=False)[0] == "allow"


def test_without_marker_out_of_scope_owner_authority_still_allowed(monkeypatch):
    # regression guard: default (marker unset) out-of-repo behavior is byte-identical to today.
    _with_marker(monkeypatch, False)
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=False)[0] == "allow"


def test_allowance_overlay_not_honored_under_marker(monkeypatch):
    # The allowance overlay lives in `hook()` and only fires on the deny-only (non-claude) host
    # path (enforcer gates it on `host != "claude"`). Under the marker, the `and not _deny_only()`
    # guard must stop `hook()` from consuming an allowance to flip a denied owner-authority action
    # — exercised on the reachable (host="codex") path so this is a real test of the guard, not a
    # no-op. We assert the hook does NOT emit an allow even when a matching allowance is mintable.
    import json as _json
    _with_marker(monkeypatch, True)
    consumed = {"called": False}
    monkeypatch.setattr(enforcer.allowance, "consume",
                        lambda *a, **k: consumed.__setitem__("called", True) or True)
    emitted = {}
    monkeypatch.setattr(enforcer, "_emit",
                        lambda decision, reason: emitted.__setitem__("d", decision))
    # a superheroes-repo cwd so in_scope is True on this deny-only host path:
    payload = _json.dumps({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 1"},
                           "cwd": os.getcwd()})
    enforcer.hook(payload, host="codex")
    assert emitted.get("d") == "deny"            # denied despite a mintable allowance
    assert consumed["called"] is False           # the overlay was NOT consulted under the marker


def test_deny_only_floor_holds_on_claude_host_without_allowance_path(monkeypatch):
    # On the claude host the allowance overlay never runs at all; the floor is purely the
    # marker deny in classify_command, so this documents the load-bearing UFR-6 path directly.
    _with_marker(monkeypatch, True)
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=True)[0] == "deny"




def test_dod_filler_command_surface_stays_non_gated(monkeypatch):
    """PR #251 regression pin: the mark-ready DoD fill leg's whole command surface must
    stay OUT of the owner-authority gated set — on BOTH floors. A future gated-set
    expansion (e.g. a broad `gh pr` pattern) would silently park every spec-driven
    acceptance run at mark-ready, reintroducing the 0.10.0 mutual-deadlock class."""
    surface = [
        "gh pr edit 42 --body-file /tmp/x.md",
        "gh pr view 42 --json body",
        "gh pr diff 42",
        "gh issue view 7 --json state",
    ]
    for cmd in surface:
        assert enforcer.classify_command(cmd, host="claude", in_scope=True)[0] == "allow", cmd
    monkeypatch.setenv("SUPERHEROES_ACCEPTANCE_DENY_ONLY", "1")
    for cmd in surface:
        assert enforcer.classify_command(cmd, host="claude", in_scope=True)[0] == "allow", (
            "deny-only floor must not gate the fill leg: %s" % cmd)


# --- #149 auditability NFR: auto-ALLOWANCES are journaled (best-effort, fail-open) ---
# Denials already ride the journal's permission_denied event → the readout. Automatic
# allowances (evaluate -> ('allow', <reason>)) were silent; these pin that each one now
# leaves an allowance_fired line in the run's OWN events.jsonl, and that the emission is pure
# observability — it can NEVER change the allow decision or let an error escape.


def test_allowance_fired_is_journaled(tmp_path, monkeypatch):
    # An auto-allowance leaves exactly one allowance_fired line carrying the reason + the
    # first-16-hex command hash (the SAME hashing permission_rules._hash uses, so it correlates
    # against the composed-command store) — and NEVER the raw command text.
    import journal
    import control_plane
    monkeypatch.setattr(permission_rules, "evaluate",
                        lambda *a, **k: ("allow", "routine:test-run"))
    monkeypatch.setattr(enforcer, "_active_work_item", lambda c, r: "wi-x")
    cwd = str(tmp_path)
    cmd = "python3 -m pytest"
    decision, reason = enforcer.classify_command(cmd, host="claude", in_scope=True,
                                                 cwd=cwd, run_id="RUN1")
    assert decision == "allow" and "auto-allowed" in reason
    events = control_plane.paths(cwd, "wi-x")["events"]
    fired = [e for e in journal.read_events(events) if e.get("type") == "allowance_fired"]
    assert len(fired) == 1
    payload = fired[0]["payload"]
    assert payload["reason"] == "routine:test-run"
    assert payload["command_sha256"] == permission_rules._hash(cmd)[:16]
    assert len(payload["command_sha256"]) == 16
    assert payload["cwd"] == cwd
    assert cmd not in open(events).read()      # the raw command is never written


def test_default_allow_journals_nothing(tmp_path, monkeypatch):
    # The default-allow fall-through (evaluate -> 'fall') must journal NOTHING — else every
    # routine command in every session would spam the run's journal.
    import journal
    import control_plane
    monkeypatch.setattr(permission_rules, "evaluate", lambda *a, **k: ("fall", "no match"))
    monkeypatch.setattr(enforcer, "_active_work_item", lambda c, r: "wi-x")
    cwd = str(tmp_path)
    assert enforcer.classify_command("python3 -m pytest", host="claude", in_scope=True,
                                     cwd=cwd, run_id="RUN1")[0] == "allow"
    events = control_plane.paths(cwd, "wi-x")["events"]
    assert journal.read_events(events) == []


def test_allowance_journal_failure_never_affects_decision(tmp_path, monkeypatch):
    # Fail-open: a journal.append that RAISES must not change the allow decision nor escape.
    import journal
    monkeypatch.setattr(permission_rules, "evaluate",
                        lambda *a, **k: ("allow", "worktree-confined"))
    monkeypatch.setattr(enforcer, "_active_work_item", lambda c, r: "wi-x")
    monkeypatch.setattr(journal, "append",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    decision, reason = enforcer.classify_command("python3 -m pytest", host="claude",
                                                 in_scope=True, cwd=str(tmp_path), run_id="RUN1")
    assert decision == "allow" and "auto-allowed" in reason


def test_hook_journals_allowance_via_active_run(tmp_path, monkeypatch, capsys):
    # End-to-end through hook(): an active run (the lease resolves to the (work_item, run_id)
    # pair via the shared permission_rules.resolve_active_lease seam hook() actually calls) + an
    # auto-allowance leaves the allowance_fired record AND now EMITS an explicit `allow` (#311
    # defect 1 — the layer must override a harness ask rule for the confined command).
    import journal
    import control_plane
    monkeypatch.setattr(enforcer.permission_rules, "resolve_active_lease",
                        lambda cwd, run_id=None: ("wi-x", "RUN1"))
    monkeypatch.setattr(permission_rules, "evaluate",
                        lambda *a, **k: ("allow", "composed-exact"))
    cwd = str(tmp_path)
    rc = enforcer.hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                                   "tool_input": {"command": "python3 build.py"}}), host="claude")
    out = json.loads(capsys.readouterr().out)   # #311: allowance-layer allow is now emitted
    assert rc == 0
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "auto-allowed (composed-exact)" in out["hookSpecificOutput"]["permissionDecisionReason"]
    events = control_plane.paths(cwd, "wi-x")["events"]
    fired = [e for e in journal.read_events(events) if e.get("type") == "allowance_fired"]
    assert len(fired) == 1 and fired[0]["payload"]["reason"] == "composed-exact"


# --- #149 REAL-SEAM integration: no monkeypatch of the lease-resolution chain ------------
# The phantom `control_plane.get_current` (removed by #170) left `_active_run_id`/`_run_is_live`
# DEAD in production while every existing test monkeypatched `_active_run_id`/`_run_is_live` or
# passed run_id directly — so a nonexistent function passed the whole suite. These drive the
# REAL `ref_lock` lease on disk (the conftest pins the store root under tmp_path) and let the
# repaired `_active_run_id` resolve run_id INTERNALLY through hook(); nothing in the resolution
# chain is stubbed.


def _real_lease_cwd(tmp_path, monkeypatch, work_item):
    """A real checkout dir + a real LIVE ref_lock lease for `work_item`, in the pinned
    tmp store. Returns (cwd, generation). The lease store is the real control-plane
    checkout store `resolve_active_lease`/`_active_run_id` read — no seam is patched."""
    import control_plane
    import ref_lock
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    cwd = str(tmp_path / "checkout")
    os.makedirs(cwd, exist_ok=True)
    store = control_plane.ensure_store(cwd)
    assert store is not None and store == control_plane.checkout_dir(cwd)
    ok, generation, _ = ref_lock.acquire(store, work_item)
    assert ok
    return cwd, generation, store


def test_active_run_id_resolves_live_lease_generation(tmp_path, monkeypatch):
    # Direct pin: with a REAL live lease on disk, _active_run_id resolves its generation via
    # the real active_work_items seam (NOT the dead control_plane.get_current). This is the
    # exact assertion that would have caught the phantom-function escape.
    cwd, generation, _store = _real_lease_cwd(tmp_path, monkeypatch, "wi-live")
    assert enforcer._active_run_id(cwd) == generation


def test_active_run_id_none_when_lease_stale(tmp_path, monkeypatch):
    # Direct pin, fail-safe: a STALE lease (ancient acquiredAt + dead pid) is filtered by
    # active_work_items, so _active_run_id resolves to None — never a spurious run_id.
    import control_plane
    import ref_lock
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    cwd = str(tmp_path / "checkout")
    os.makedirs(cwd, exist_ok=True)
    store = control_plane.ensure_store(cwd)
    ref_lock._force_lease(store, "wi-stale", {"pid": 999999, "host": ref_lock._host(),
                          "acquiredAt": "1970-01-01T00:00:00Z", "bootId": None,
                          "generation": 7, "ttl": 1})
    assert enforcer._active_run_id(cwd) is None


def test_hook_allowance_fires_end_to_end_through_real_lease(tmp_path, monkeypatch, capsys):
    # (a) THE load-bearing integration test. A real live lease + a frozen routine rule for that
    # run's generation; hook() resolves run_id INTERNALLY via the real _active_run_id and the
    # allowance fires end-to-end: an EMITTED `allow` (#311 defect 1) AND one allowance_fired line
    # in the resolved run's OWN journal (real _active_work_item). NOTHING in the resolution chain
    # is stubbed.
    import control_plane
    import journal
    cwd, generation, _store = _real_lease_cwd(tmp_path, monkeypatch, "wi-run")
    # Seed a routine-family rule + freeze it for THIS run's generation, in the real store
    # (default root == the pinned control_plane.store_root()).
    permission_rules.set_rule(cwd, {"family": "test-run", "pattern": r"\bpytest\b"})
    permission_rules.freeze_run_rules(generation, cwd, work_item="wi-run")
    cmd = "python3 -m pytest -q"
    rc = enforcer.hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                                   "tool_input": {"command": cmd}}), host="claude")
    out = json.loads(capsys.readouterr().out)     # #311: allowance-layer allow is emitted, not silent
    assert rc == 0
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "auto-allowed (routine:test-run)" in out["hookSpecificOutput"]["permissionDecisionReason"]
    events = control_plane.paths(cwd, "wi-run")["events"]
    fired = [e for e in journal.read_events(events) if e.get("type") == "allowance_fired"]
    assert len(fired) == 1, "the repaired seam must let the allowance fire+journal end-to-end"
    assert fired[0]["payload"]["reason"].startswith("routine:")
    assert fired[0]["payload"]["command_sha256"] == permission_rules._hash(cmd)[:16]


def test_hook_falls_back_when_lease_released_no_allowance(tmp_path, monkeypatch, capsys):
    # (b) With the SAME setup but the lease RELEASED (no live run), _active_run_id resolves to
    # None, evaluate is inert (FR-3), and the very same command falls back to today's default
    # allow with NO allowance_fired journaled — proving the allowance only fires on a real run.
    import control_plane
    import journal
    import ref_lock
    cwd, generation, store = _real_lease_cwd(tmp_path, monkeypatch, "wi-run")
    permission_rules.set_rule(cwd, {"family": "test-run", "pattern": r"\bpytest\b"})
    permission_rules.freeze_run_rules(generation, cwd, work_item="wi-run")
    assert ref_lock.release(store, "wi-run", generation) is True     # run ends -> lease gone
    assert enforcer._active_run_id(cwd) is None                       # real seam sees no run
    cmd = "python3 -m pytest -q"
    rc = enforcer.hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                                   "tool_input": {"command": cmd}}), host="claude")
    assert rc == 0 and capsys.readouterr().out.strip() == ""          # still allow (default), silent
    events = control_plane.paths(cwd, "wi-run")["events"]
    fired = [e for e in journal.read_events(events) if e.get("type") == "allowance_fired"]
    assert fired == [], "no active run -> allowance layer inert -> nothing journaled"


# --- fix round 2 (escalated pair): work-item-namespaced run files + injected floor check ---


def test_run_files_namespaced_by_work_item_no_collision(tmp_path, monkeypatch):
    # premortem-002: a lease generation is a per-work-item counter, so two concurrent
    # same-project runs both present generation 1. Namespaced run files keep run B's freeze
    # from wiping run A's frozen snapshot (UFR-9) or resetting its composed set (FR-8).
    import permission_rules
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    cwd = str(tmp_path / "proj")
    os.makedirs(cwd, exist_ok=True)
    permission_rules.freeze_run_rules(1, cwd, work_item="wi-a")
    permission_rules.record_composed(1, "cmd-for-a", cwd, work_item="wi-a")
    permission_rules.freeze_run_rules(1, cwd, work_item="wi-b")  # would clobber pre-fix
    a = permission_rules.frozen_rules(1, cwd, work_item="wi-a")
    b = permission_rules.frozen_rules(1, cwd, work_item="wi-b")
    assert permission_rules._hash("cmd-for-a") in a["composed"]   # A's set survived B's freeze
    assert b["composed"] == []
    # cross-run isolation: A's composed command confers nothing under B's file
    assert permission_rules._hash("cmd-for-a") not in b["composed"]


def test_resolve_active_lease_prefers_cwd_matching_work_item(tmp_path, monkeypatch):
    # premortem-002 attribution: with TWO live leases in one clone, a cwd that names exactly
    # one work-item (a build worktree path embeds it) resolves to THAT run; an ambiguous cwd
    # falls back to sorted-first (deterministic).
    import control_plane
    import ref_lock
    import permission_rules
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    cwd = str(tmp_path / "checkout")
    os.makedirs(cwd, exist_ok=True)
    store = control_plane.ensure_store(cwd)
    ok_a, gen_a, _ = ref_lock.acquire(store, "wi-alpha")
    ok_b, gen_b, _ = ref_lock.acquire(store, "wi-beta")
    assert ok_a and ok_b
    wt_b = str(tmp_path / "trees" / "wi-beta-1234" / "sub")
    # a real build worktree shares the clone's common-dir store key; a scratch dir does not,
    # so pin the store resolution to target the preference logic itself.
    monkeypatch.setattr(permission_rules.control_plane, "checkout_dir", lambda c: store)
    wi, gen = permission_rules.resolve_active_lease(wt_b)
    assert (wi, gen) == ("wi-beta", gen_b)
    wi_first, _ = permission_rules.resolve_active_lease(cwd)   # no work-item in cwd -> sorted-first
    assert wi_first == "wi-alpha"


def test_resolve_active_lease_prefers_longest_overlapping_work_item(tmp_path, monkeypatch):
    # code-001: when one work-item name is a substring of another (`wi-abc` inside
    # `wi-abc-task5`), a plain `p[0] in cwd` test matches BOTH and the preference collapses to
    # the wrong (shorter, sorted-first) run. Longest-UNIQUE match must pick the more specific one.
    import control_plane
    import ref_lock
    import permission_rules
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    cwd = str(tmp_path / "checkout")
    os.makedirs(cwd, exist_ok=True)
    store = control_plane.ensure_store(cwd)
    ok_short, _gs, _ = ref_lock.acquire(store, "wi-abc")
    ok_long, _gl, _ = ref_lock.acquire(store, "wi-abc-task5")
    assert ok_short and ok_long
    monkeypatch.setattr(permission_rules.control_plane, "checkout_dir", lambda c: store)
    # a build worktree whose path embeds the LONGER name (and therefore the shorter as a substring)
    wt_long = str(tmp_path / "trees" / "wi-abc-task5-1234" / "sub")
    wi_long, _ = permission_rules.resolve_active_lease(wt_long)
    assert wi_long == "wi-abc-task5"                 # longest-unique wins over the embedded prefix
    # a worktree whose path embeds ONLY the shorter name resolves to it
    wt_short = str(tmp_path / "trees" / "wi-abc-9999" / "sub")
    wi_short, _ = permission_rules.resolve_active_lease(wt_short)
    assert wi_short == "wi-abc"


def test_evaluate_uses_injected_gated_check_and_lazy_fallback(tmp_path, monkeypatch):
    # architecture-001: the enforcer injects its own gated_action (primary path — no upward
    # import); a caller that injects nothing still gets the lazy fail-closed fallback.
    import permission_rules
    flagged = {}

    def fake_gated(cmd):
        flagged["cmd"] = cmd
        return True

    verdict, why = permission_rules.evaluate("echo hi", None, "RUN1", gated_check=fake_gated)
    assert verdict == "fall" and "floor owns it" in why and flagged["cmd"] == "echo hi"
    # fallback: no injection -> lazy enforcer import still gates a real owner-role command
    verdict2, why2 = permission_rules.evaluate("gh pr " + "merge 1", None, "RUN1")
    assert verdict2 == "fall" and "floor owns it" in why2


# --- #311 defect 1: the allowance-layer allow is EMITTED (overrides a harness ask rule) --------


def test_hook_emits_allow_for_allowance_layer_allow(tmp_path, monkeypatch, capsys):
    # An allowance-layer allow must emit `permissionDecision: "allow"` so it OVERRIDES a
    # harness-level ask rule for the confined command (owner ruling 2026-07-09). Before #311 this
    # was silent, so the harness's own ask rules always decided and the layer was a no-op.
    monkeypatch.setattr(enforcer.permission_rules, "resolve_active_lease",
                        lambda cwd, run_id=None: ("wi-x", "RUN1"))
    monkeypatch.setattr(enforcer.permission_rules, "evaluate",
                        lambda *a, **k: ("allow", "worktree-confined"))
    monkeypatch.setattr(enforcer, "_journal_allowance", lambda *a, **k: None)
    rc = enforcer.hook(json.dumps({"tool_name": "Bash", "cwd": str(tmp_path),
                                   "tool_input": {"command": "cd /wt && python3 x.py"}}), host="claude")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "auto-allowed (worktree-confined)" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_hook_default_allow_stays_silent(tmp_path, monkeypatch, capsys):
    # The default-allow fall-through (evaluate -> 'fall', reason "") must stay SILENT — a blanket
    # allow emitted here would wrongly override every legitimate harness ask rule.
    monkeypatch.setattr(enforcer.permission_rules, "resolve_active_lease",
                        lambda cwd, run_id=None: (None, None))
    monkeypatch.setattr(enforcer.permission_rules, "evaluate", lambda *a, **k: ("fall", "no match"))
    rc = enforcer.hook(json.dumps({"tool_name": "Bash", "cwd": str(tmp_path),
                                   "tool_input": {"command": "python3 x.py"}}), host="claude")
    assert rc == 0 and capsys.readouterr().out.strip() == ""


def test_hook_gated_with_matching_allowance_rule_still_asks(tmp_path, monkeypatch, capsys):
    # UFR-1 re-assertion at the emission layer: even if a (hypothetical) allowance rule WOULD match
    # a gated owner-authority command, the gated arm resolves FIRST (ask on claude) and the allowance
    # layer is never consulted — the emitted decision is `ask`, never an `allow`. A broken evaluate
    # that tried to allow the gated command would be a loud failure here.
    def _boom_allow(*a, **k):
        return ("allow", "routine:should-never-win")
    monkeypatch.setattr(enforcer.permission_rules, "resolve_active_lease",
                        lambda cwd, run_id=None: ("wi-x", "RUN1"))
    monkeypatch.setattr(enforcer.permission_rules, "evaluate", _boom_allow)
    repo = tmp_path / "repo" / "docs" / "superheroes"
    repo.mkdir(parents=True)   # in a superheroes repo -> the gated set is in scope
    cwd = str(tmp_path / "repo")
    rc = enforcer.hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                                   "tool_input": {"command": "gh pr merge 12"}}), host="claude")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["hookSpecificOutput"]["permissionDecision"] == "ask"


# --- #311 defect 5: NO-monkeypatch subprocess integration (the exact hooks.json call shape) ------
# #286 shipped inert because EVERY test monkeypatched the lease / rules / worktree seams. This
# drives `python3 lib/enforcer.py hook --host claude` as a subprocess (re-imported fresh — an
# in-process monkeypatch cannot reach it), with the payload on stdin exactly as hooks.json wires
# it, against a REAL ref_lock lease + REAL managed worktree on disk. Nothing is stubbed.


def _spawn_hook(payload, env):
    import subprocess
    return subprocess.run(
        ["python3", _ENFORCER, "hook", "--host", "claude"],
        input=json.dumps(payload), capture_output=True, text=True, env=env)


def test_hook_subprocess_emits_allow_for_worktree_confined_production_shape(tmp_path, monkeypatch):
    # The load-bearing integration test (defects 1+2+5 together): a real live lease makes the run
    # active; a production `cd <managed-wt> && python3 …` leaf whose PAYLOAD cwd is the (non-worktree)
    # session dir is worktree-confined on its REAL exec dir and the hook EMITS an allow on stdout.
    import control_plane
    import ref_lock
    store_root = tmp_path / "store"
    wt_root = tmp_path / "wt"
    # Pin both roots via env so the IN-PROCESS lease acquire and the SUBPROCESS hook share one store.
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(store_root))
    monkeypatch.setenv("SUPERHEROES_WORKTREES_ROOT", str(wt_root))
    monkeypatch.delenv("SUPERHEROES_ACCEPTANCE_DENY_ONLY", raising=False)
    # a real managed build worktree under the pinned worktrees root (strict descendant)
    managed_wt = wt_root / "wi-run-1234"
    managed_wt.mkdir(parents=True)
    # a real live ref_lock lease so the run is active (FR-3), in the same real store the hook reads.
    session = str(tmp_path / "checkout")
    os.makedirs(session, exist_ok=True)
    store = control_plane.ensure_store(session)
    ok, generation, _ = ref_lock.acquire(store, "wi-run")
    assert ok
    cmd = "cd %s && python3 -m pytest -q" % managed_wt
    payload = {"tool_name": "Bash", "cwd": session, "tool_input": {"command": cmd}}
    proc = _spawn_hook(payload, dict(os.environ))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "auto-allowed (worktree-confined)" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_hook_subprocess_gated_merge_still_asks_no_monkeypatch(tmp_path, monkeypatch):
    # UFR-1 through the real subprocess: an owner-authority command in a real superheroes repo
    # (docs/superheroes/ present) emits `ask` on claude — the gated floor is untouched by #311.
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    monkeypatch.setenv("SUPERHEROES_WORKTREES_ROOT", str(tmp_path / "wt"))
    monkeypatch.delenv("SUPERHEROES_ACCEPTANCE_DENY_ONLY", raising=False)
    repo = tmp_path / "repo"
    (repo / "docs" / "superheroes").mkdir(parents=True)
    payload = {"tool_name": "Bash", "cwd": str(repo),
               "tool_input": {"command": "gh pr merge 12"}}
    proc = _spawn_hook(payload, dict(os.environ))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
