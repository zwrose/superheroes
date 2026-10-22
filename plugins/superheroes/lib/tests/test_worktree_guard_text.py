"""Tests for the worktree guard telling text from a command (#2054).

Heredoc bodies fed to a program that does not run them are data; backslash escapes are read the
way bash reads them. Every test runs against a DIRTY tree, so a discard read as a command would
be denied — an allow therefore proves the guard saw text, not that the tree happened to be clean.
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


def _kinds(command):
    return [record["kind"] for record in wg.segment_accounting(command)]


# --- the definition-of-done pair ------------------------------------------------

def test_dod_heredoc_naming_a_discard_is_allowed(dirty_repo):
    command = "cat > notes.md <<'EOF'\ngit checkout -- f.txt\nEOF"
    assert wg.classify(command, dirty_repo) == ("allow", "")


def test_dod_the_same_discard_run_as_a_command_is_denied(dirty_repo):
    decision, reason = wg.classify("git checkout -- f.txt", dirty_repo)
    assert decision == "deny"
    assert reason == wg.refusal_message("checkout-path", 1)


# --- heredocs that are data -----------------------------------------------------

_ALLOWED_HEREDOCS = {
    "commit-F-stdin":
        "git commit -F - <<'EOF'\nRevert with git checkout -- f.txt\nnot git reset --hard\nEOF",
    "gh-issue-comment-apostrophe":
        "gh issue comment 1 --body-file - <<'EOF'\nNever run git reset --hard here.\n"
        "It's a risky command.\nEOF",
    "commit-message-substitution":
        'git commit -m "$(cat <<\'EOF\'\nx" ; git checkout -- f.txt ; echo "\nEOF\n)"',
    "dash-operator-tab-terminator":
        "cat <<-'EOF'\n\tgit checkout -- f.txt\n\tEOF",
    "unquoted-delimiter-without-substitution":
        "cat <<EOF\ngit reset --hard\nEOF",
    "double-quoted-delimiter":
        'cat <<"EOF"\ngit reset --hard\nEOF',
    "backslash-delimiter":
        "cat <<\\EOF\n$(git reset --hard)\nEOF",
    "space-before-delimiter":
        "cat << 'EOF'\ngit reset --hard\nEOF",
    "tee":
        "tee notes.md <<'EOF'\ngit reset --hard\nEOF",
    "assignment-prefix":
        "FOO=1 cat <<'EOF'\ngit reset --hard\nEOF",
    "path-spelled-consumer":
        "/bin/cat <<'EOF'\ngit reset --hard\nEOF",
    "gh-api":
        "gh api repos/o/r/issues/1/comments -F body=@- <<'EOF'\ngit reset --hard\nEOF",
    "gh-pr-create":
        "gh pr create --body-file - <<'EOF'\ngit reset --hard\nEOF",
    "gh-release":
        "gh release create v1 --notes-file - <<'EOF'\ngit reset --hard\nEOF",
    "redirect-dup-after":
        "cat <<'EOF' >&2\ngit reset --hard\nEOF",
    "redirect-dup-before":
        "cat 2>&1 <<'EOF'\ngit reset --hard\nEOF",
    "redirect-all":
        "cat <<'EOF' &>/dev/null\ngit reset --hard\nEOF",
    "two-heredocs-one-line":
        "cat <<'A' <<'B'\ngit reset --hard\nA\ngit checkout -- f.txt\nB",
    "tee-then-cat":
        "cat <<'EOF' | tee out.md\ngit reset --hard\nEOF",
    "blank-line-in-body":
        "cat <<'EOF'\ngit reset --hard\n\ngit checkout -- f.txt\nEOF",
}


@pytest.mark.parametrize("name", sorted(_ALLOWED_HEREDOCS))
def test_heredoc_body_that_is_data_is_allowed(name, dirty_repo):
    assert wg.classify(_ALLOWED_HEREDOCS[name], dirty_repo) == ("allow", ""), name


@pytest.mark.parametrize("name", sorted(_ALLOWED_HEREDOCS))
def test_scanners_agree_with_classify_on_an_allowed_heredoc(name):
    command = _ALLOWED_HEREDOCS[name]
    assert wg.mentions_destructive_git(command) is False
    assert "unaccounted" not in _kinds(command)
    assert wg.destructive_discard_actions(command) == []


# --- fail-closed edges 1-7 ------------------------------------------------------

def _refused(command, repo):
    decision, reason = wg.classify(command, repo)
    assert decision == "deny", command
    return reason


@pytest.mark.parametrize("shell", ["bash", "sh", "zsh", "eval", "source /dev/stdin",
                                   ". /dev/stdin", "xargs", "python3", "ssh host"])
def test_edge_1_heredoc_fed_to_a_shell_is_denied(shell, dirty_repo):
    command = f"{shell} <<'EOF'\ngit checkout -- f.txt\nEOF"
    assert _refused(command, dirty_repo) == wg.refusal_message("checkout-path", 1)


def test_edge_2_heredoc_piped_to_a_shell_is_denied(dirty_repo):
    command = "cat <<'EOF' | sh\ngit reset --hard\nEOF"
    assert _refused(command, dirty_repo) == wg.refusal_message("reset-hard", 1)


def test_edge_3_git_bisect_run_sh_is_denied(dirty_repo):
    command = "git bisect run sh <<'EOF'\ngit reset --hard\nEOF"
    assert _refused(command, dirty_repo) == wg.refusal_message("reset-hard", 1)


@pytest.mark.parametrize("command", [
    "git -c core.editor=true commit -F - <<'EOF'\ngit reset --hard\nEOF",
    "git log <<'EOF'\ngit reset --hard\nEOF",
    "gh repo clone <<'EOF'\ngit reset --hard\nEOF",
    "mystery-tool <<'EOF'\ngit reset --hard\nEOF",
])
def test_edge_3b_any_other_git_gh_or_unknown_word_is_denied(command, dirty_repo):
    _refused(command, dirty_repo)


def test_edge_4_unquoted_delimiter_with_command_substitution_in_body_is_denied(dirty_repo):
    command = "cat <<EOF\n$(git reset --hard)\nEOF"
    assert _refused(command, dirty_repo) == wg.refusal_message("reset-hard", 1)


def test_edge_4_unquoted_delimiter_with_backtick_in_body_is_denied(dirty_repo):
    command = "cat <<EOF\n`git reset --hard`\nEOF"
    assert _refused(command, dirty_repo) == wg.refusal_message("reset-hard", 1)


def test_edge_5_unterminated_heredoc_is_not_masked(dirty_repo):
    command = "cat <<'EOF'\ngit reset --hard"
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


def test_edge_5_heredoc_operator_inside_a_quoted_string_is_not_masked(dirty_repo):
    command = "echo \"<<'EOF'\"\ngit reset --hard\nEOF"
    assert wg._mask_heredoc_bodies(command) == command
    assert _refused(command, dirty_repo) == wg.refusal_message("reset-hard", 1)


def test_edge_6_quote_left_open_on_an_earlier_line_stops_masking(dirty_repo):
    command = "echo \"start\nmid\" ; cat <<'EOF'\ngit reset --hard\nEOF"
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


def test_edge_7_escaped_quote_does_not_hide_a_real_discard(dirty_repo):
    command = 'echo \\"; git reset --hard; echo \\"'
    assert wg.segment_accounting(command)[1]["action"] == "reset-hard"
    assert _refused(command, dirty_repo) == wg.refusal_message("reset-hard", 1)


# --- adopted design points, each with the deny it guards -------------------------

def test_comment_text_after_an_unquoted_hash_masks_nothing(dirty_repo):
    command = "cat x # <<'EOF'\ngit reset --hard\nEOF"
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


def test_a_hash_inside_a_word_is_not_a_comment(dirty_repo):
    command = "cat a#b <<'EOF'\ngit reset --hard\nEOF"
    assert wg.classify(command, dirty_repo) == ("allow", "")


@pytest.mark.parametrize("opener", ["echo $'a' ;", "(( x = 1 )) ;", "echo $(( 1 + 2 )) ;"])
def test_ansi_c_quote_or_double_paren_on_the_line_stops_masking(opener, dirty_repo):
    command = f"{opener} cat <<'EOF'\ngit reset --hard\nEOF"
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


def test_operator_line_ending_with_a_quote_still_open_masks_nothing():
    command = "cat <<'EOF' \"b\ngit reset --hard\nEOF\nc\""
    assert wg._mask_heredoc_bodies(command) == command
    command = "cat <<'EOF' 'b\ngit reset --hard\nEOF\nc'"
    assert wg._mask_heredoc_bodies(command) == command


def test_operator_line_ending_in_a_backslash_continuation_masks_nothing(dirty_repo):
    command = "sh \\\n<<'EOF'\ngit reset --hard\nEOF"
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


def test_here_string_is_not_a_heredoc(dirty_repo):
    command = "cat <<< x\ngit reset --hard\nEOF"
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


def test_unreadable_delimiter_stops_masking_for_the_rest(dirty_repo):
    command = ("cat <<'a b'\ngit reset --hard\na b\n"
               "cat <<'EOF'\ngit checkout -- f.txt\nEOF")
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


def test_output_of_a_heredoc_consumer_piped_on_to_a_later_line_is_denied(dirty_repo):
    command = "cat <<'EOF' |\ngit reset --hard\nEOF\nsh"
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


def test_substitution_run_as_a_command_word_is_denied(dirty_repo):
    command = "$(cat <<'EOF'\ngit reset --hard\nEOF\n)"
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


def test_substitution_carried_from_an_earlier_line_is_denied(dirty_repo):
    command = "$(\ncat <<'EOF'\ngit reset --hard\nEOF\n)"
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


def test_assignment_only_substitution_is_not_masked(dirty_repo):
    command = "msg=$(cat <<'EOF'\ngit reset --hard\nEOF\n)\neval \"$msg\""
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


@pytest.mark.parametrize("command", [
    "cat <<EOF\nE\\\nOF\ngit reset --hard\nEOF",
    "`cat <<'EOF'\ngit reset --hard\nEOF\n`",
    "`\ncat <<'EOF'\ngit reset --hard\nEOF\n`",
    "sh < <(\ncat <<'EOF'\ngit reset --hard\nEOF\n)",
    "(\ncat <<'EOF'\ngit reset --hard\nEOF\n) | sh",
    "{\ncat <<'EOF'\ngit reset --hard\nEOF\n} | sh",
    "cat <<'EOF' > >(sh)\ngit reset --hard\nEOF",
    "git commit -m \"$(cat <<'EOF'\ngit reset --hard\nEOF\n)\" && git reset --hard",
], ids=["folded-terminator", "backtick-enclosed", "backtick-opened-earlier", "process-substitution",
        "grouped-pipeline", "brace-group-pipeline",
        "output-process-substitution", "chained-after-substitution"])
def test_a_heredoc_whose_output_may_reach_a_shell_is_not_masked(command, dirty_repo):
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


@pytest.mark.parametrize("command", [
    "sh -c \"$(echo hi\ncat <<'EOF'\ngit reset --hard\nEOF\n)\"",
    "sh -c \"$(cat <<'EOF'\ngit reset --hard\nEOF\n)\"",
], ids=["substitution-opened-earlier", "substitution-into-shell"])
def test_a_substitution_feeding_a_shell_is_not_masked(command):
    assert wg._mask_heredoc_bodies(command) == command


def test_a_commit_message_substitution_that_ends_the_command_is_masked(dirty_repo):
    command = "git commit -m \"$(cat <<'EOF'\ngit reset --hard\nEOF\n)\""
    assert wg._mask_heredoc_bodies(command) == "git commit -m \"$(cat <<'EOF'\n\nEOF\n)\""
    assert wg.classify(command, dirty_repo) == ("allow", "")


@pytest.mark.parametrize("command", [
    "( # group\ncat <<'EOF'\ngit reset --hard\nEOF\n) | sh",
    "{ # group\ncat <<'EOF'\ngit reset --hard\nEOF\n} | sh",
    "echo \"(\"\ncat <<'EOF'\ngit reset --hard\nEOF",
    "echo a | cat\ncat <<'EOF'\ngit reset --hard\nEOF",
    "echo a &&\ncat <<'EOF'\ngit reset --hard\nEOF",
    "echo a \\\ncat <<'EOF'\ngit reset --hard\nEOF",
], ids=["commented-paren-group", "commented-brace-group", "quoted-paren-earlier",
        "pipe-earlier", "and-continuation", "backslash-continuation"])
def test_any_earlier_line_with_a_nesting_mark_stops_masking(command, dirty_repo):
    assert wg._mask_heredoc_bodies(command) == command
    _refused(command, dirty_repo)


@pytest.mark.parametrize("command", [
    'echo "$(git reset --hard)"',
    'echo "\\"$(git reset --hard)\\""',
    'echo "\\"$(git commit -m \\"x\\"; git reset --hard)\\""',
    'echo "`git reset --hard`"',
    'echo "\\"`git reset --hard`\\""',
    'echo "$(echo $(git reset --hard))"',
    'echo "$(git reset --hard"',
    'echo "`git reset --hard"',
    'echo "$(echo hi"',
], ids=["plain", "escaped-outer-quotes", "escaped-inner-quotes", "backtick", "backtick-escaped-quotes",
        "nested", "unclosed-substitution", "unclosed-backtick", "unclosed-benign"])
def test_a_substitution_inside_double_quotes_is_scanned_as_a_command(command, dirty_repo):
    assert wg.mentions_destructive_git(command) is True
    assert "unaccounted" in _kinds(command) or "destructive" in _kinds(command)
    _refused(command, dirty_repo)


@pytest.mark.parametrize("command", [
    'echo "\\$(git reset --hard)"',
    'echo "\\`git reset --hard\\`"',
    'echo "$(date)" "quoted"',
], ids=["escaped-dollar", "escaped-backtick", "benign-substitution"])
def test_an_escaped_or_harmless_substitution_in_double_quotes_is_allowed(command, dirty_repo):
    assert wg.classify(command, dirty_repo) == ("allow", "")


def test_a_real_command_after_a_masked_heredoc_is_still_scanned(dirty_repo):
    command = "cat <<'EOF'\ntext\nEOF\ngit reset --hard"
    assert _refused(command, dirty_repo) == wg.refusal_message("reset-hard", 1)


def test_a_command_after_an_unmasked_body_is_not_swallowed_by_a_nested_heredoc(dirty_repo):
    command = "bash <<'EOF'\ncat <<'X'\nEOF\ngit reset --hard\nX"
    assert _refused(command, dirty_repo) == wg.refusal_message("reset-hard", 1)


def test_masking_blanks_the_body_and_keeps_the_terminator():
    command = "cat <<'EOF'\ngit reset --hard\nEOF"
    assert wg._mask_heredoc_bodies(command) == "cat <<'EOF'\n\nEOF"


def test_command_without_a_newline_is_untouched():
    command = "cat <<'EOF'"
    assert wg._mask_heredoc_bodies(command) == command


# --- backslash escapes, as bash reads them --------------------------------------

def test_escaped_quote_inside_double_quotes_does_not_close_the_string(dirty_repo):
    command = 'gh pr comment 1 --body "text \\"git reset --hard\\" text"'
    assert _kinds(command) == ["safe"]
    assert wg.mentions_destructive_git(command) is False
    assert wg.classify(command, dirty_repo) == ("allow", "")


def test_escaped_quote_prose_with_a_discard_is_allowed(dirty_repo):
    command = 'gh pr comment 1 --body "the reviewer said \\"never: git checkout -- f.txt\\""'
    assert wg.classify(command, dirty_repo) == ("allow", "")


def test_escaped_quote_outside_quotes_opens_no_quote():
    records = wg.segment_accounting('echo \\"; git reset --hard; echo \\"')
    assert [r["kind"] for r in records] == ["safe", "destructive", "safe"]
    assert records[1]["action"] == "reset-hard"
    records = wg.segment_accounting("echo it\\'s; git reset --hard")
    assert [r["kind"] for r in records] == ["safe", "destructive"]


def test_escaped_separators_outside_quotes_split_nothing():
    assert wg._split_segments("find . -name x -exec echo {} \\; -print") == [
        "find . -name x -exec echo {} \\; -print"]
    assert wg._split_segments("echo a\\|b \\& c \\(d\\)") == ["echo a\\|b \\& c \\(d\\)"]


def test_backslash_newline_continuation_is_kept():
    segments = wg._split_segments("git checkout \\\n -- f.txt")
    assert len(segments) == 1
    assert wg._tokenize_segment(segments[0]) == ["git", "checkout", "--", "f.txt"]


def test_backslash_before_a_dollar_or_backtick_in_double_quotes_is_literal():
    assert wg._split_segments('echo "a \\$ b \\` c"; git reset --hard') == [
        'echo "a \\$ b \\` c"', "git reset --hard"]


def test_backslash_inside_single_quotes_is_literal():
    records = wg.segment_accounting("echo 'a\\'; git reset --hard")
    assert [r["kind"] for r in records] == ["safe", "destructive"]


def test_escaped_backslash_inside_double_quotes_lets_the_quote_close():
    records = wg.segment_accounting('echo "a\\\\"; git reset --hard')
    assert [r["kind"] for r in records] == ["safe", "destructive"]


def test_tokenizer_keeps_an_escaped_quote_inside_its_token():
    assert wg._tokenize_segment('echo "a \\"b\\" c" d') == ["echo", 'a \\"b\\" c', "d"]
    assert wg._tokenize_segment("echo a\\ b c") == ["echo", "a\\ b", "c"]


def test_backslash_git_is_still_seen_as_a_git_word():
    assert wg.mentions_destructive_git("\\git reset --hard") is True
