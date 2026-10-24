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


@pytest.mark.parametrize("shell", ["bash", "sh", "zsh"])
def test_variable_script_path_without_c_remains_allowed(shell, dirty_repo, monkeypatch):
    with open(os.path.join(dirty_repo, "harmless.sh"), "w") as f:
        f.write("printf hi\n")
    monkeypatch.setenv("SCRIPT", "harmless.sh")
    command = f'{shell} "./$SCRIPT"'
    assert wg.classify(command, dirty_repo) == ("allow", ""), command


def test_split_segments_with_ends_names_the_boundary_that_flushed_each_segment():
    assert wg._split_segments_with_ends("eval 'git' `echo x`; ls") == [
        ("eval 'git'", "`"), ("echo x", "`"), ("ls", ""),
    ]
