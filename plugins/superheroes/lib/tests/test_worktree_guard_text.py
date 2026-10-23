"""Tests for the worktree guard telling text from a command (#2054, layer 2 of 3).

Text that names a git subcommand is data only inside an allowlist of whole-command heredoc
shapes (`_mask_data_heredoc`); everything else is read as commands. Every test runs against a
DIRTY tree, so a discard read as a command is denied — an allow therefore proves the guard saw
text, not that the tree happened to be clean.
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


# A body that names a hard reset and a path checkout as bare lines, with a line holding a double
# quote: read as commands, the discard lines are refused.
_BODY = 'git reset --hard\ngit checkout -- f.txt\nsay "hi" and a lone " quote'
# The same idea for the `-m "$(cat <<'EOF'` shapes, where the body sits inside a double-quoted
# string until a quote in the body ends it.
_MESSAGE_BODY = 'x" ; git reset --hard ; git checkout -- f.txt ; echo "'


def _heredoc(operator_line, body=_BODY, terminator="EOF", after=""):
    return f"{operator_line}\n{body}\n{terminator}{after}"


# --- the definition-of-done pair ------------------------------------------------

_ALLOWED = {
    "cat-redirect": _heredoc("cat > notes.md <<'EOF'"),
    "cat-append": _heredoc("cat >> notes.md <<'EOF'"),
    "cat-redirect-after-operator": _heredoc("cat <<'EOF' > notes.md"),
    "cat-double-quoted-delimiter": _heredoc('cat > notes.md <<"EOF"'),
    "tee": _heredoc("tee notes.md <<'EOF'"),
    "tee-append-devnull": _heredoc("tee -a notes.md > /dev/null <<'EOF'"),
    "gh-issue-body-file": _heredoc("gh issue create --title x --body-file - <<'EOF'"),
    "gh-pr-comment-F": _heredoc("gh pr comment 1 -F - <<'EOF'"),
    "git-commit-F": _heredoc("git commit -F - <<'EOF'"),
    "git-commit-message": _heredoc(
        "git commit -m \"$(cat <<'EOF'", _MESSAGE_BODY, after='\n)"'),
    "gh-pr-create-body": _heredoc(
        "gh pr create --title x --body \"$(cat <<'EOF'", _MESSAGE_BODY, after='\n)"'),
}


@pytest.mark.parametrize("name", sorted(_ALLOWED))
def test_dod_allowlisted_heredoc_naming_a_discard_is_allowed(name, dirty_repo):
    assert wg.classify(_ALLOWED[name], dirty_repo) == ("allow", ""), name


def test_dod_the_same_discard_run_as_a_command_is_denied(dirty_repo):
    decision, reason = wg.classify("git reset --hard", dirty_repo)
    assert decision == "deny"
    assert reason == wg.refusal_message("reset-hard", 1)


# --- near-misses: each is read as commands, so the bare discard line is refused -------

_NEAR_MISSES = {
    "bash": _heredoc("bash <<'EOF'"),
    "sh": _heredoc("sh <<'EOF'"),
    "python3": _heredoc("python3 <<'EOF'"),
    "piped-to-sh": _heredoc("cat <<'EOF' | sh"),
    "redirected-and-piped-to-sh": _heredoc("cat > f.sh <<'EOF' | sh"),
    "unquoted-delimiter": _heredoc("cat > f.sh <<EOF"),
    "backslash-delimiter": _heredoc("cat > f.sh <<\\EOF"),
    "dash-operator": _heredoc("cat > f.sh <<-'EOF'"),
    "here-string": _heredoc("cat > f.sh <<<'x'"),
    "two-operators": _heredoc("cat <<'A' <<'EOF' > f.sh"),
    "line-before-operator-line": "trap 'bash f.sh' EXIT\n" + _heredoc("cat > f.sh <<'EOF'"),
    "line-after-terminator": _heredoc("cat > f.sh <<'EOF'", after="\nbash f.sh"),
    "assignment-prefix": _heredoc("FOO=1 cat > f.sh <<'EOF'"),
    "path-prefixed-command-word": _heredoc("/bin/cat > f.sh <<'EOF'"),
    "git-global-option": _heredoc("git -C . commit -F - <<'EOF'"),
    "gh-release": _heredoc("gh release create v1 --notes-file - <<'EOF'"),
    "gh-api": _heredoc("gh api repos/o/r/issues -F body=@- <<'EOF'"),
    "gh-issue-without-stdin-flag": _heredoc("gh issue create --title x <<'EOF'"),
    "git-commit-without-stdin-flag": _heredoc("git commit -a <<'EOF'"),
    "no-terminator": "cat > f.sh <<'EOF'\n" + _BODY,
    "cat-without-redirection": _heredoc("cat <<'EOF'"),
    "cat-two-redirections": _heredoc("cat > a.sh > b.sh <<'EOF'"),
    "tee-two-paths": _heredoc("tee a.sh b.sh <<'EOF'"),
    "semicolon-on-operator-line": _heredoc("cat > f.sh <<'EOF'; bash f.sh"),
    "and-on-operator-line": _heredoc("cat > f.sh <<'EOF' && bash f.sh"),
    "comment-on-operator-line": _heredoc("cat > f.sh <<'EOF' # note"),
    "substitution-on-operator-line": _heredoc("cat > $(echo f.sh) <<'EOF'"),
    "message-without-closer": _heredoc("git commit -m \"$(cat <<'EOF'", _MESSAGE_BODY),
    "message-with-line-after-closer": _heredoc(
        "git commit -m \"$(cat <<'EOF'", _MESSAGE_BODY, after='\n)"\nbash f.sh'),
    "message-with-other-flag": _heredoc(
        "git commit --author \"$(cat <<'EOF'", _MESSAGE_BODY, after='\n)"'),
    "gh-message-with-title-flag": _heredoc(
        "gh pr create --title \"$(cat <<'EOF'", _MESSAGE_BODY, after='\n)"'),
    "message-with-unquoted-delimiter": _heredoc(
        "git commit -m \"$(cat <<EOF", _MESSAGE_BODY, after='\n)"'),
}


@pytest.mark.parametrize("name", sorted(_NEAR_MISSES))
def test_near_miss_is_read_as_commands_and_denied(name, dirty_repo):
    decision, _ = wg.classify(_NEAR_MISSES[name], dirty_repo)
    assert decision == "deny", name


@pytest.mark.parametrize("name", sorted(_NEAR_MISSES))
def test_near_miss_is_left_unmasked(name):
    command = _NEAR_MISSES[name]
    assert wg._mask_data_heredoc(command) == command, name


# --- the open Critical ----------------------------------------------------------

def test_shell_dash_c_with_an_unterminated_escaped_quote_is_denied(dirty_repo):
    command = 'bash -c "echo \\"hello; git reset --hard; true"'
    decision, _ = wg.classify(command, dirty_repo)
    assert decision == "deny"


# --- the masker itself ----------------------------------------------------------

def test_mask_blanks_body_lines_and_keeps_operator_terminator_and_closer():
    command = "git commit -m \"$(cat <<'EOF'\nline one\nline two\nEOF\n)\"\n"
    assert wg._mask_data_heredoc(command) == "git commit -m \"$(cat <<'EOF'\n\n\nEOF\n)\"\n"
    command = "cat > f.sh <<'EOF'\nline one\nEOF\n\n"
    assert wg._mask_data_heredoc(command) == "cat > f.sh <<'EOF'\n\nEOF\n\n"


def test_mask_returns_a_one_line_command_unchanged():
    command = "cat > f.sh <<'EOF'"
    assert wg._mask_data_heredoc(command) == command
