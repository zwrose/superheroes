"""Units for the ``owner-command-in-body`` handback refusal in vet_slot.py. No gh, no network."""
import json

import pytest

import vet_slot as vs

SKELETON = """## Advisor vet
<!-- superheroes:advisor-vet -->
slot text

<!-- superheroes:build-record -->
<details><summary>Build record</summary>

### Follow-ups for the advisor

Follow-ups: none
<!-- superheroes:followups none -->
</details>
"""

FENCE = "```"


def _body(owner_half="", build_record=""):
    """A valid handback body; ``owner_half`` sits above the advisor-vet heading."""
    head = owner_half + "\n" if owner_half else ""
    return head + SKELETON.replace("</details>\n", build_record + "</details>\n")


def _block(*lines, lang="bash", fence=FENCE, close=True):
    out = [fence + lang] + list(lines)
    if close:
        out.append(fence)
    return "\n".join(out) + "\n"


def _refused(body, line, language, tool):
    result = vs.check_handback(body)
    assert result["ok"] is False
    assert result["reason"] == "owner-command-in-body"
    expected = "the fenced %s block opening at line %d names %s" % (language, line, tool)
    assert expected in result["detail"]
    return result


def _passes(body):
    result = vs.check_handback(body)
    assert result == {"ok": True, "verb": "handback", "followups": []}


# ---- refuse: the DoD rows -------------------------------------------------------------------

def test_dod_row_1_mongorestore_block_refuses():
    body = _body(_block('mongorestore --drop --uri "$URI" dump/'))
    _refused(body, 1, "bash", "mongorestore")


def test_dod_row_2_keychain_find_generic_password_refuses():
    body = _body(_block("security find-generic-password -s staging -w"))
    _refused(body, 1, "bash", "security find-generic-password")


def test_keychain_find_internet_password_in_substitution_refuses():
    body = _body(_block('TOKEN=$(security find-internet-password -s host -w)'))
    _refused(body, 1, "bash", "security find-internet-password")


@pytest.mark.parametrize("tool", ["mongosh", "mongo", "mongodump", "mongorestore", "psql", "pg_dump",
                                  "pg_restore", "mysql", "mysqldump", "redis-cli", "sqlite3"])
def test_literal_database_tool_names_refuse(tool):
    _refused(_body(_block(tool + " --help")), 1, "bash", tool)


def test_database_tool_list_is_pinned_to_literals():
    assert set(vs.DATABASE_TOOLS) == {"mongosh", "mongo", "mongodump", "mongorestore", "psql", "pg_dump",
                                      "pg_restore", "mysql", "mysqldump", "redis-cli", "sqlite3"}


# ---- refuse: opener forms -------------------------------------------------------------------

@pytest.mark.parametrize("lang,named", [
    ("sh", "sh"), ("zsh", "zsh"), ("shell", "shell"), ("", "no-language"),
    ("{.bash}", "bash"), ("{.bash .numberLines}", "bash"), ("BASH", "bash"),
])
def test_each_shell_language_refuses(lang, named):
    body = _body(_block("psql -h host", lang=lang))
    _refused(body, 1, named, "psql")


@pytest.mark.parametrize("label", ["console", "shell-session", "sh-session", "shellsession", "terminal",
                                   "shell-script", "ksh", "fish", "text", "txt", "plaintext", "Console"])
def test_added_shell_labels_refuse_a_named_tool(label):
    body = _body(_block("$ mongosh --eval 1", lang=label))
    _refused(body, 1, label.lower(), "mongosh")


@pytest.mark.parametrize("label", ["console", "shell-session", "sh-session", "shellsession", "terminal",
                                   "shell-script", "ksh", "fish", "text", "txt", "plaintext"])
def test_added_shell_labels_pass_without_a_named_tool(label):
    _passes(_body(_block("$ ls -la", lang=label)))


def test_tilde_fence_refuses():
    body = _body(_block("psql -h host", fence="~~~"))
    _refused(body, 1, "bash", "psql")


def test_four_backtick_fence_refuses():
    body = _body(_block("psql -h host", fence="````"))
    _refused(body, 1, "bash", "psql")


def test_unterminated_fence_runs_to_the_end_of_the_body():
    text = "```bash\nmongosh --eval 'db.x.find()'\n"
    assert vs.owner_command_blocks(text) == [{"line": 1, "language": "bash", "tool": "mongosh"}]


def test_unterminated_fence_below_markers_refuses():
    body = _body() + FENCE + "bash\nmongosh --eval 'db.x.find()'\n"
    result = vs.check_handback(body)
    assert result["ok"] is False
    assert result["reason"] == "owner-command-in-body"
    assert "names mongosh" in result["detail"]


# ---- refuse: containers ---------------------------------------------------------------------

def test_blockquoted_block_refuses():
    body = _body("> ```bash\n> mongorestore dump\n> ```")
    _refused(body, 1, "bash", "mongorestore")


def test_quoted_fence_ends_when_its_blockquote_ends():
    body = _body("> ```text\n> prior output\n\n```bash\nmongorestore --drop dump/\n```")
    _refused(body, 4, "bash", "mongorestore")


def test_block_nested_under_numbered_list_item_refuses():
    body = _body("1. Restore the dump:\n\n    ```bash\n    mongorestore dump\n    ```")
    _refused(body, 3, "bash", "mongorestore")


def test_list_item_then_blockquote_block_refuses():
    body = _body("- > ```bash\n  > mongorestore --drop dump/\n  > ```")
    _refused(body, 1, "bash", "mongorestore")


def test_blockquote_then_list_item_block_refuses():
    body = _body("> - ```bash\n>   mongorestore --drop dump/\n>   ```")
    _refused(body, 1, "bash", "mongorestore")


def test_keychain_read_across_backslash_continuation_refuses():
    body = _body(_block("security \\", "find-generic-password -s staging -w"))
    _refused(body, 1, "bash", "security find-generic-password")


def test_block_inside_build_record_refuses():
    record = "\n" + _block("psql -c 'select 1'")
    body = _body(build_record=record)
    result = vs.check_handback(body)
    assert result["reason"] == "owner-command-in-body"
    assert "block opening at line 13 names psql" in result["detail"]


def test_f2_regression_block_after_closed_html_comment_refuses():
    body = _body("<!--\n```json\n-->\n\n```bash\nmongorestore --drop dump\n```")
    _refused(body, 5, "bash", "mongorestore")


def test_two_offending_blocks_one_refusal_names_both_lines():
    body = _body(_block("psql -h a") + "\n" + _block("mysql -u root", lang="sh"))
    result = vs.check_handback(body)
    assert result["reason"] == "owner-command-in-body"
    assert "the fenced bash block opening at line 1 names psql" in result["detail"]
    assert "the fenced sh block opening at line 5 names mysql" in result["detail"]
    assert result["detail"].count(vs.OWNER_COMMAND_ADVICE) == 1


# ---- fail-closed edges ----------------------------------------------------------------------

def test_crlf_line_endings_still_refuse():
    body = _body(_block("psql -h host")).replace("\n", "\r\n")
    _refused(body, 1, "bash", "psql")


def test_fence_inside_fence_is_content():
    outer = "````json\n```bash\npsql -h host\n```\n````\n"
    _passes(_body(outer))
    assert vs.owner_command_blocks(outer) == []


def test_inline_triple_backtick_with_backtick_in_info_is_not_a_fence():
    text = "```bash `psql` ```\nmore prose\n"
    assert list(vs._owner_shell_blocks(text)) == []


def test_closer_shorter_than_opener_is_content():
    text = "````bash\n```\npsql -h host\n````\n"
    assert vs.owner_command_blocks(text) == [{"line": 1, "language": "bash", "tool": "psql"}]


def test_tilde_fence_not_closed_by_backticks():
    text = "~~~text\n```\n~~~\n```bash\npsql -h host\n```\n"
    assert vs.owner_command_blocks(text) == [{"line": 4, "language": "bash", "tool": "psql"}]
    text = "~~~bash\n```\npsql -h host\n~~~\n"
    assert vs.owner_command_blocks(text) == [{"line": 1, "language": "bash", "tool": "psql"}]
    text = "~~~text\n```\n~~~\n"
    assert vs.owner_command_blocks(text) == []


def test_comment_closed_on_its_own_line_enters_no_comment_state():
    body = _body("<!-- note -->\n```bash\npsql -h host\n```")
    _refused(body, 2, "bash", "psql")


# ---- pass -----------------------------------------------------------------------------------

def test_dod_row_3_pinned_python_pytest_block_passes():
    body = _body(_block("scripts/pinned-python -m pytest plugins/superheroes/lib/tests/ -q"))
    _passes(body)


def test_non_shell_fences_mentioning_tools_pass():
    body = _body(_block("mongosh", "psql -h host", lang="json")
                 + "\n" + _block("mongosh", "psql -h host", lang="diff"))
    _passes(body)


@pytest.mark.parametrize("label", ["powershell", "ps1"])
def test_powershell_labels_naming_a_tool_pass(label):
    _passes(_body(_block("mongosh --eval 1", lang=label)))


def test_inline_code_in_prose_passes():
    body = _body("Run `psql` or `mongorestore --drop` yourself.\n")
    _passes(body)


def test_html_comment_hidden_shell_block_passes():
    body = _body("<!--\n```bash\npsql -h host\n```\n-->")
    _passes(body)


@pytest.mark.parametrize("command", [
    "pip install postgresql-client-config",
    "export URI=mongodb://localhost",
    "mysql_config --version",
    "cd mongo/data",
    "ssh root@psql",
    "mytool --filter=psql_extra",
])
def test_whole_word_non_matches_pass(command):
    _passes(_body(_block(command)))


# ---- shell comments -------------------------------------------------------------------------

def test_plain_comment_naming_a_tool_passes():
    _passes(_body(_block("# then run mongosh by hand")))


def test_comment_holding_a_dollar_paren_substitution_refuses():
    _refused(_body(_block("# $(psql -c 'x')")), 1, "bash", "psql")


def test_trailing_comment_holding_a_backtick_substitution_refuses():
    _refused(_body(_block("echo hi  # see `mongosh`")), 1, "bash", "mongosh")


# ---- accepted over-refusal ------------------------------------------------------------------

@pytest.mark.parametrize("lines,tool", [
    (["python3 -m pytest -k psql"], "psql"),
    (["brew install mongosh"], "mongosh"),
    (["echo mongosh"], "mongosh"),
    (["cat <<'EOF'", "psql", "EOF"], "psql"),
])
def test_accepted_over_refusal_a_mere_mention_in_a_shell_block_refuses(lines, tool):
    _refused(_body(_block(*lines)), 1, "bash", tool)


# ---- entry points and unchanged verbs ---------------------------------------------------------

def test_write_and_check_analysis_do_not_refuse_the_body():
    body = _body(_block("mongorestore dump"))
    advisor_at, build_at, ids = vs.analyze_body(body)
    assert advisor_at < build_at
    assert ids is None


def test_run_verb_body_file_refuses(tmp_path):
    path = tmp_path / "body.md"
    path.write_text(_body(_block("mongorestore --drop dump/")), encoding="utf-8")
    result = vs.run_verb("handback", None, None, body_file=str(path))
    assert result["ok"] is False
    assert result["reason"] == "owner-command-in-body"


def test_main_body_file_exits_1_with_json_reason(tmp_path, capsys):
    path = tmp_path / "body.md"
    path.write_text(_body(_block("security find-generic-password -s staging -w")), encoding="utf-8")
    code = vs.main(["handback", "--body-file", str(path)])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["ok"] is False
    assert out["reason"] == "owner-command-in-body"


def test_main_body_file_clean_body_exits_0(tmp_path, capsys):
    path = tmp_path / "body.md"
    path.write_text(_body(_block("scripts/pinned-python -m pytest -q")), encoding="utf-8")
    assert vs.main(["handback", "--body-file", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_double_quoted_keychain_subcommand_refuses():
    body = _body(_block('security "find-generic-password" -s staging -w'))
    _refused(body, 1, "bash", "security find-generic-password")


def test_single_quoted_security_and_subcommand_refuses():
    body = _body(_block("'security' 'find-internet-password'"))
    _refused(body, 1, "bash", "security find-internet-password")


def test_inline_code_comment_opener_does_not_hide_later_fence():
    body = _body("The parser recognizes `<!--` comments.\n\n" + _block("mongorestore --drop dump/"))
    _refused(body, 3, "bash", "mongorestore")


def test_backslash_ending_a_shell_comment_does_not_join_next_line():
    body = _body(_block("# use the existing dump \\", "mongorestore --drop dump/"))
    _refused(body, 1, "bash", "mongorestore")
