"""Tests for the worktree guard reading a `bash|sh|zsh -c` or `eval` program as commands (#2087).

The program text is decided on exactly as a top-level command is, one level in; a program the
guard cannot read is refused whatever the tree holds. Every test runs against a DIRTY tree, so a
discard read as a command is denied — an allow therefore proves the guard saw a harmless program,
not that the tree happened to be clean.
"""
import os
import subprocess

import pytest

import mode_registry
import worktree_guard as wg


def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd, *args], check=True, capture_output=True, text=True)


def _calibrated(monkeypatch):
    monkeypatch.setattr(mode_registry, "calibration_state", lambda cwd: "calibrated")


@pytest.fixture
def dirty_repo(tmp_path, monkeypatch):
    repo = str(tmp_path / "repo")
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True,
                   capture_output=True, text=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("committed\n")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "init")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("PRIOR_UNCOMMITTED_DELIVERY")
    _calibrated(monkeypatch)
    return repo


# --- a readable program is decided on as commands --------------------------------

_CHECKOUT = wg.refusal_message("checkout-path", 1)
_RESET = wg.refusal_message("reset-hard", 1)

_REFUSED = {
    "bash-c": ('bash -c "git checkout -- ."', _CHECKOUT),
    "sh-c-cd": ('sh -c "cd . && git checkout -- ."', wg.indeterminate_message("checkout-path")),
    "eval-quoted": ('eval "git checkout -- ."', _CHECKOUT),
    "bash-lc": ("bash -lc 'git reset --hard'", _RESET),
    "bash-o-pipefail": ("bash -o pipefail -c 'git reset --hard'", _RESET),
    "bash-c-double-dash": ("bash -c -- 'git reset --hard'", _RESET),
    "eval-bare-words": ("eval git reset --hard", _RESET),
    "assignment-after-then": (
        'if true; then LC_ALL=C bash -c "git checkout -- ."; fi', _CHECKOUT),
    "git-dir-after-then": (
        "then GIT_DIR=/elsewhere git checkout -- .", wg.indeterminate_message("checkout-path")),
}


@pytest.mark.parametrize("name", sorted(_REFUSED))
def test_a_discard_inside_a_readable_program_is_denied_with_its_next_step(name, dirty_repo):
    command, reason = _REFUSED[name]
    assert wg.classify(command, dirty_repo) == ("deny", reason), name
    assert "Next step:" in reason


@pytest.mark.parametrize("command", [
    'bash -c "echo hi"',
    'sh -c "git status"',
    'eval "echo hi"',
    "eval -- 'git clean -n'",
    "bash script.sh",
    "env FOO=1 bash script.sh -c value",
    "timeout 5 bash script.sh -c value",
])
def test_a_harmless_program_or_script_is_allowed(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("allow", ""), command


# --- a program the guard cannot read is refused whatever the tree holds ----------

_UNREADABLE = {
    "variable": 'bash -c "$P"',
    "substitution": 'bash -c "$(cat f.sh)"',
    "escape": 'bash -c "echo \\"x\\""',
    "no-operand": "bash -c",
    "eval-variable": "eval $CMD",
    "eval-no-args": "eval",
    "eval-cut-at-backtick": "eval 'git' `printf 'checkout -- .'`",
    "inner-command-word-variable": "bash -c '$PROGRAM'",
    "second-level-shell": "bash -c \"sh -c 'git status'\"",
    "second-level-eval": "eval \"eval 'echo hi'\"",
    "option-from-variable": "bash $OPT -c 'git reset --hard'",
}


@pytest.mark.parametrize("name", sorted(_UNREADABLE))
def test_an_unreadable_program_is_denied_with_the_unreadable_message(name, dirty_repo):
    assert wg.classify(_UNREADABLE[name], dirty_repo) == ("deny", wg.unreadable_program_message())


_REDIRECT_PROGRAMS = {
    "dup-before": "2>&1 bash -c 'git reset --hard'",
    "dup-between": "bash 2>&1 -c 'git reset --hard'",
    "amp-redirect-before": "&>/dev/null bash -c 'git reset --hard'",
    "quoted-space-target": "2>\"/tmp/error log\" bash -c 'git reset --hard'",
}


@pytest.mark.parametrize("name", sorted(_REDIRECT_PROGRAMS))
def test_a_program_behind_a_redirection_is_denied(name, dirty_repo):
    assert wg.classify(_REDIRECT_PROGRAMS[name], dirty_repo)[0] == "deny"


@pytest.mark.parametrize("command", [
    "timeout 5 bash -c 'echo hi'",
    "env bash -c 'echo hi'",
    "xargs sh -c 'echo hi'",
    "env FOO=1 bash -c 'echo hi'",
    "nohup bash -c 'echo hi'",
    "xargs -0 sh -c 'echo hi'",
])
def test_a_wrapper_before_a_shell_c_is_refused_as_unreadable(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", wg.unreadable_program_message())


@pytest.mark.parametrize("command", [
    "bash script.sh -c value",
    "rg bash -c notes.txt",
    "find . -exec bash -c 'echo hi' \\;",
    "bash -c 'exec git status'",
])
def test_the_backstop_fires_only_at_an_executable_command_position(command, dirty_repo):
    assert wg.classify(command, dirty_repo)[0] == "allow"


@pytest.mark.parametrize("command", [
    "TOOL=git bash -c 'exec \"$TOOL\" reset --hard'",
    "bash -c 'command \"$T\" reset --hard'",
    "bash -c 'builtin \"$T\" reset --hard'",
    "TOOL=git bash -c 'exec -- \"$TOOL\" reset --hard'",
    "bash -c 'exec -a x \"$T\" reset --hard'",
    "bash -c 'command -p \"$T\" reset --hard'",
    "TOOL=git bash -c 'command -- \"$TOOL\" reset --hard'",
    "TOOL=git bash -c 'exec -ca x \"$TOOL\" reset --hard'",
    "TOOL=git bash -c 'exec -la x \"$TOOL\" reset --hard'",
    "TOOL=git bash -c 'exec -ax \"$TOOL\" reset --hard'",
    "TOOL=git bash -c 'exec -agit \"$TOOL\" reset --hard'",
    "TOOL=git bash -c 'exec -aalt \"$TOOL\" reset --hard'",
    "bash -c 'exec -ca alt \"git\" reset --hard'",
    "bash -c 'command -v \"$TOOL\"'",
    "TOOL=git bash -c 'env \"$TOOL\" reset --hard'",
    "TOOL=git bash -c 'timeout 5 \"$TOOL\" reset --hard'",
])
def test_a_variable_command_word_behind_an_execution_builtin_is_unreadable(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", wg.unreadable_program_message()), command


@pytest.mark.parametrize("command", [
    "bash -c 'command -v git'",
    "bash -c 'command -V git'",
    "bash -c 'command -pv git'",
    "bash -c 'exec git status'",
    "bash -c 'exec -a x git status'",
    "bash -lc 'git status'",
    "bash -eo pipefail -c 'git status'",
    "bash -o pipefail -c 'git status'",
    "bash -c 'timeout 5 git status'",
])
def test_command_v_lookup_and_plain_wrapped_commands_in_a_program_are_allowed(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("allow", ""), command


@pytest.mark.parametrize("command", [
    "bash -c 'exec git reset --hard'",
    "exec git reset --hard",
    "bash -c 'exec -a x \"git\" reset --hard'",
    "bash -c 'command \"git\" reset --hard'",
])
def test_a_destructive_git_behind_a_bare_execution_builtin_is_still_denied(command, dirty_repo):
    assert wg.classify(command, dirty_repo)[0] == "deny", command


@pytest.mark.parametrize("command", [
    "env GIT_DIR=/other/.git GIT_WORK_TREE=/other git reset --hard",
    "exec git clean -fx",
    "exec -ca alt git reset --hard",
    "command git restore --source=other draft.txt",
    "exec git -c \"user.name=Some Name\" clean -fx",
    "git clean -fd 2>&1> --dry-run",
    "git restore . 2>&1> --staged",
    "exec -aextra \"git\" reset --hard",
    "exec -ca alt \"git\" reset --hard",
    "exec -a git \"git\" reset --hard",
    "env -u FOO \"git\" reset --hard",
    "env -iu FOO \"git\" reset --hard",
])
def test_a_wrapped_destructive_git_is_refused_as_unaccounted_never_parsed(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", wg.unparsed_message()), command
    assert [r["kind"] for r in wg.segment_accounting(command)] == ["unaccounted"], command


@pytest.mark.parametrize("command", [
    "bash -c 'exec -aextra \"git\" reset --hard'",
    "bash -c 'exec -a git \"git\" reset --hard'",
    "bash -c 'env -u FOO \"git\" clean -fd'",
])
def test_an_option_after_an_execution_builtin_in_a_program_is_unreadable(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", wg.unreadable_program_message()), command


@pytest.mark.parametrize("command", [
    "env -i git status",
    "exec -a alt git status",
    "env -u FOO git diff",
    "bash -c 'env -i git status'",
])
def test_an_option_before_a_harmless_wrapped_git_stays_allowed(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("allow", ""), command


def test_a_separated_heredoc_operator_consumes_its_delimiter(dirty_repo):
    assert wg._redirection_width(["<<", "EOF"], 0) == 2
    assert wg._redirection_width(["<<-", "EOF"], 0) == 2
    assert wg._redirection_width(["<<EOF"], 0) == 1
    verdict = wg.classify("bash << EOF -c 'git reset --hard'\nEOF", dirty_repo)
    assert verdict[0] == "deny"


@pytest.mark.parametrize("command", ["grep -c bash notes.txt", "echo bash"])
def test_the_backstop_leaves_ordinary_bash_mentions_alone(command, dirty_repo):
    assert wg.classify(command, dirty_repo)[0] == "allow"


def test_a_redirection_ampersand_is_not_a_segment_boundary():
    assert wg._split_segments("git status 2>&1") == ["git status 2>&1"]
    assert wg._split_segments("git status &>/dev/null") == ["git status &>/dev/null"]
    assert wg._split_segments("a && b") == ["a", "b"]
    assert wg._split_segments("a & b") == ["a", "b"]
    assert wg._split_segments("echo \\>& bash -c x") == ["echo \\>", "bash -c x"]


def test_the_unreadable_message_names_its_next_step():
    message = wg.unreadable_program_message()
    assert message.startswith("superheroes worktree guard:")
    assert "Next step:" in message
    assert "`" in message.split("Next step:", 1)[1]


def test_an_unreadable_program_is_refused_on_a_clean_tree_too(tmp_path, monkeypatch):
    repo = str(tmp_path / "clean")
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True,
                   capture_output=True, text=True)
    _calibrated(monkeypatch)
    assert wg.classify('bash -c "$P"', repo) == ("deny", wg.unreadable_program_message())


# --- the program-shape detector ---------------------------------------------------

def _program(text):
    return wg._shell_program(wg._tokenize_segment(text, keep_quotes=True))


@pytest.mark.parametrize("text, expected", [
    ("bash -c 'git status'", ("program", "git status")),
    ("bash -ec 'git status'", ("program", "git status")),
    ("bash -o pipefail -c 'git status'", ("program", "git status")),
    ("bash --norc -c 'git status'", ("program", "git status")),
    ("bash --rcfile x -c 'git status'", ("program", "git status")),
    ("bash -c -- 'git status'", ("program", "git status")),
    ("/bin/zsh -c \"git status\"", ("program", "git status")),
    ("eval git status", ("program", "git status")),
    ("bash script.sh", None),
    ("bash", None),
    ("bash -x script.sh", None),
    ("bash -c", ("unreadable", None)),
    ("bash $OPT -c 'x'", ("unreadable", None)),
    ("eval", ("unreadable", None)),
    ("eval -- 'git clean -n'", ("program", "git clean -n")),
    ("eval --", ("unreadable", None)),
    ("git status", None),
])
def test_shell_program_reads_the_program_shapes(text, expected):
    assert _program(text) == expected


@pytest.mark.parametrize("command", [
    "if bash -c 'git reset --hard'; then echo done; fi",
    "while bash -c 'git reset --hard'; do echo x; done",
    "until bash -c 'git reset --hard'; do echo x; done",
])
def test_a_program_in_a_conditional_command_position_is_read(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", _RESET), command


@pytest.mark.parametrize("command", [
    "bash -c 'exec \"$@\"' _ git reset --hard",
    "bash -c '`printf \"git reset --hard\"`'",
    "bash -c '$(printf \"git reset --hard\")'",
])
def test_substitution_or_positional_execution_in_a_program_is_unreadable(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", wg.unreadable_program_message()), command


@pytest.mark.parametrize("command", [
    "bash -c 'git reset $FLAGS'",
    "bash -c 'git $SUBCOMMAND --hard'",
    r"bash -c 'g\it reset --hard'",
    "FLAGS=c bash \"-${FLAGS}\" 'git reset --hard'",
])
def test_unreadable_inner_program_cannot_hide_discard(command, dirty_repo, monkeypatch):
    monkeypatch.setenv("FLAGS", "--hard")
    monkeypatch.setenv("SUBCOMMAND", "reset")
    assert wg.classify(command, dirty_repo) == ("deny", wg.unreadable_program_message()), command


@pytest.mark.parametrize("command", [
    "bash -c 'git commit -m \"$m\"'",
    "bash -c 'git commit -m \"msg $m\"'",
    'sh "${CLAUDE_PLUGIN_ROOT}/scripts/check.sh"',
    'bash -- "$script"',
    "bash -- $script",
    'bash -s -- "$arg"',
])
def test_expansion_that_hides_no_discard_or_option_stays_allowed(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("allow", ""), command


@pytest.mark.parametrize("command", [
    'bash "$OPT" -c "git reset --hard"',
    "bash -c 'git reset $FLAGS'",
    "bash \"$OPT\" 'git reset --hard'",
    "bash \"${OPT}\" 'git reset --hard'",
    "eval '`printf \"git reset --hard\"`'",
])
def test_expansion_hiding_a_discard_or_option_is_unreadable(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", wg.unreadable_program_message()), command


@pytest.mark.parametrize("command", [
    "bash \"$@\" 'x'",
    "bash \"$*\" 'x'",
    "bash \"$1\" 'x'",
])
def test_special_or_positional_parameter_word_is_unreadable(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", wg.unreadable_program_message()), command


@pytest.mark.parametrize("command", [
    "2>/dev/null bash -c 'git reset --hard'",
    "bash 2>/dev/null -c 'git reset --hard'",
    "> out.txt bash -c 'git reset --hard'",
    "2> err.txt bash -c 'git reset --hard'",
])
def test_a_program_after_or_among_redirections_is_read(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", _RESET), command


def test_a_harmless_program_with_a_trailing_redirection_is_allowed(dirty_repo):
    assert wg.classify("bash -c 'echo hi' 2>/dev/null", dirty_repo) == ("allow", "")


@pytest.mark.parametrize("shell", ["bash", "sh", "zsh"])
def test_variable_script_path_without_c_remains_allowed(shell, dirty_repo, monkeypatch):
    with open(os.path.join(dirty_repo, "harmless.sh"), "w") as f:
        f.write("printf hi\n")
    monkeypatch.setenv("SCRIPT", "harmless.sh")
    command = f'{shell} "./$SCRIPT"'
    assert wg.classify(command, dirty_repo) == ("allow", ""), command


@pytest.mark.parametrize("command", [
    "env -u FOO bash -c 'git reset --hard'",
    "exec -a process bash -c 'git reset --hard'",
    "bash -c 'echo hi' \"$(echo x; git reset --hard)\"",
    "FOO=\"$(git reset --hard)\" bash -c 'echo hi'",
])
def test_wrapper_operands_and_outer_substitutions_cannot_hide_a_discard(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", wg.unreadable_program_message()), command


@pytest.mark.parametrize("command", [
    "rg bash -c notes.txt",
    "bash script.sh -c value",
    "bash -c 'echo hi'",
    "eval 'echo hi' 2>/dev/null",
    "2>\"/tmp/error log\" bash -c 'echo hi'",
    "command -v cd && git status",
])
def test_harmless_shapes_near_the_hiding_rules_stay_allowed(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("allow", ""), command


@pytest.mark.parametrize("command, message", [
    ("eval 'command cd /other;' git reset --hard", wg.indeterminate_message("reset-hard")),
    ("bash -c 'builtin cd /x && git reset --hard'", wg.indeterminate_message("reset-hard")),
    ("bash -c 'command 2>/dev/null cd /other && git reset --hard'", wg.indeterminate_message("reset-hard")),
    ("command 2>/dev/null cd /other && git reset --hard", wg.indeterminate_message("reset-hard")),
    ("bash -c 'command -p cd /x && git reset --hard'", wg.indeterminate_message("reset-hard")),
    ("eval 'git reset --hard' 2>/dev/null", _RESET),
    ("command -v cd && git reset --hard", wg.refusal_message("reset-hard", 1)),
])
def test_wrapped_directory_change_and_redirected_eval_are_still_refused(command, message, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", message), command


@pytest.mark.parametrize("command", [
    "git checkout HEAD '>notes'",
    "git checkout \">f.txt\"",
    "git 2>/dev/null reset --hard",
    "git 2>\"/tmp/error log\" reset --hard",
])
def test_a_quoted_lookalike_is_kept_and_a_real_redirection_cannot_hide_a_discard(command, dirty_repo):
    assert wg.classify(command, dirty_repo)[0] == "deny", command


def test_a_detached_redirection_target_cannot_hide_a_clean(dirty_repo):
    with open(os.path.join(dirty_repo, "untracked.txt"), "w") as f:
        f.write("x")
    assert wg.classify("git clean -fd > --dry-run", dirty_repo)[0] == "deny"


def test_a_redirection_is_not_the_worktree_removal_target(dirty_repo, tmp_path):
    linked = str(tmp_path / "linked")
    _git(dirty_repo, "worktree", "add", "-q", linked)
    assert wg.classify(f"git worktree remove --force {linked} &>/dev/null", dirty_repo) == ("allow", "")


def test_a_real_redirection_after_a_harmless_checkout_is_dropped(dirty_repo):
    assert wg.classify("git checkout HEAD &>/dev/null", dirty_repo) == ("allow", "")


@pytest.mark.parametrize("command", [
    "bash -c 'command eval \"git reset --hard\"'",
    "command eval \"git reset --hard\"",
    "nohup eval 'echo hi'",
    "bash -o $OPT 'git reset --hard'",
    "bash --rcfile \"$RC\" -c 'echo hi'",
    "timeout 5 bash -o pipefail -c 'git reset --hard'",
    "env FOO=1 bash --rcfile /dev/null -c 'git reset --hard'",
    "env FOO=1 bash 2>/dev/null -c 'git reset --hard'",
    "eval 'echo \\\";' git reset --hard",
    "bash -c 'echo \\\"; git reset --hard'",
    "bash -c 'git reset --hard>/dev/null'",
    "eval 'git reset --hard>/dev/null'",
    "eval git> /dev/null reset --hard",
    "\"eval\" git reset '--hard>\"/dev/null\"'",
    "bash -c 'git reset>/dev/null --hard'",
    "bash -c '\"git\" reset --hard>/dev/null'",
    "bash -c 'git \"reset\" --hard>/dev/null'",
    "eval git \"'reset' --hard>/dev/null\"",
    "bash -c< /dev/null 'git reset --hard'",
    "sh -c> /tmp/x 'git reset --hard'",
    "zsh -oerrexit -c 'git reset --hard'",
    "bash -c 'exec \"git\" reset --hard'",
    "bash -c 'exec \"git\" -c \"user.name=Jane Doe\" reset --hard'",
    "bash -c 'exec \"git\" -c \"core.editor=echo hi\" reset --hard'",
    "bash -c 'git restore . 2>&1> --staged'",
])
def test_eval_behind_a_wrapper_and_an_expandable_option_value_are_unreadable(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", wg.unreadable_program_message()), command


def test_an_attached_redirection_target_cannot_hide_a_flag_and_plain_redirections_stay_allowed(dirty_repo):
    for bad in ("git restore .>& --staged", "git reset>/dev/null --hard", "git status>/tmp/x"):
        assert wg.classify(bad, dirty_repo) == ("deny", wg.unparsed_message()), bad
    for ok in ("bash -c 'git status 2>/dev/null'", "bash -c 'git status > /tmp/x'",
               "bash -c 'echo hi>/tmp/x'"):
        assert wg.classify(ok, dirty_repo) == ("allow", ""), ok


def test_a_word_named_eval_and_a_literal_option_value_stay_as_before(dirty_repo):
    assert wg.classify("grep eval file.py", dirty_repo) == ("allow", "")


def test_an_ampersand_redirection_adjoining_a_flag_is_its_own_word(dirty_repo):
    assert wg.classify("git reset --hard&>/dev/null", dirty_repo) == ("deny", _RESET)
    assert wg._split_segments("git status 2>&1") == ["git status 2>&1"]


def test_split_segments_with_ends_names_the_boundary_that_flushed_each_segment():
    assert wg._split_segments_with_ends("eval 'git' `echo x`; ls") == [
        ("eval 'git'", "`"), ("echo x", "`"), ("ls", ""),
    ]


@pytest.mark.parametrize("command", [
    "eval git reset>'/tmp/output log' --hard",
    "bash -c 'git reset>\"/tmp/error log\" --hard'",
    "eval git '\"reset\" --hard<<<\" x\"'",
])
def test_quoted_redirection_target_attached_to_a_destructive_word_is_unreadable(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("deny", wg.unreadable_program_message()), command


@pytest.mark.parametrize("command", [
    "git diff --word-diff-regex='<[^>]*>'",
    'git commit -m "a->b"',
    'git commit -m "a>b"',
])
def test_angle_brackets_inside_quoted_git_arguments_stay_allowed(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("allow", ""), command


# --- a lone checkout sent to another repository is never resolved against this one ---

@pytest.mark.parametrize("command", [
    "git -C ../other checkout main",
    "git -C /other checkout main",
    "GIT_DIR=/other/.git git checkout main",
    "GIT_DIR=/other/.git GIT_WORK_TREE=/other git checkout main",
    "git --git-dir=/other/.git checkout main",
    "git --git-dir /other/.git checkout main",
    "git --work-tree=/x checkout f.txt",
    "git -C . -C ../other checkout main",
    "bash -c 'git -C ../other checkout f.txt'",
    "bash -c 'GIT_DIR=/other/.git git checkout main'",
    "eval 'git --work-tree=/x checkout f.txt'",
    "if true; then GIT_DIR=/other/.git git checkout main; fi",
    "GIT_WORK_TREE=/x git checkout main",
    "git --work-tree=/x checkout main",
])
def test_a_lone_checkout_sent_to_another_repository_is_refused(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == (
        "deny", wg.indeterminate_message("checkout-path")), command


@pytest.mark.parametrize("command", [
    "git -C . checkout main",
    "git checkout main",
    "git checkout -b feature",
    "git switch main",
    "git -C ../other status",
    "git -C ../other switch main",
    "git -C ../other checkout -b feature",
    "bash -c 'git -C . checkout main'",
    "bash -c 'git -C ../other log'",
    "git -C ./ checkout main",
    "git -C ../other checkout --detach main",
    "git -C ../other checkout -q --detach 0123abcd",
    "git -C ../other checkout --detach f.txt",
    "git -C ../other switch --detach main",
    "git checkout --detach f.txt",
    "bash -c 'git -C ../other checkout --detach main'",
])
def test_a_checkout_in_this_repository_or_a_harmless_other_repository_command_stays_allowed(
        command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("allow", ""), command


def test_the_refusal_for_another_repository_names_an_exact_route():
    message = wg.indeterminate_message("checkout-path")
    assert "git -C <dir> switch <branch>" in message
    assert "git -C <dir> switch --detach <commit>" in message
    assert "Next step:" in message
