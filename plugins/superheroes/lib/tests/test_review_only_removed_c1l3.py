"""Detector for review-code's removed read-only path.

Code review runs only as its one review-and-fix loop. This file proves, by running the shipped
text rather than reading it:

- the removed-flags block in SKILL.md answers `--review-only` and `--post` plainly, exits 1, and
  nothing after it runs; ordinary arguments pass through silently;
- the verify refusal in reference/setup.md halts when the resolver reports a refusal or the
  command is empty, and passes only a configured command with no refusal;
- the read-only path's text and contract file are gone from skills/review-code/.

The verify-refusal lines are extracted from setup.md starting at the `VERIFY_CMD=$(` line, so the
resolver call above it (`VERIFY_JSON=$(python3 ... review_code_config.py ...)`) is not run: the
test replaces that line with a direct `VERIFY_JSON` assignment (the environment variable below).
"""
import os
import re
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))
REVIEW_CODE = os.path.join(PLUGIN, "skills", "review-code")
SKILL_MD = os.path.join(REVIEW_CODE, "SKILL.md")
SETUP_MD = os.path.join(REVIEW_CODE, "reference", "setup.md")
HEADLESS_MD = os.path.join(REVIEW_CODE, "reference", "headless-presentation.md")

NOTICE_ANCHOR = "**Two flags were removed"
NO_VERIFY_MESSAGE = (
    "Code review is not available until a verify command is set. Code review needs a command "
    "that verifies this project's code; set one with /superheroes:configure."
)

needs_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="jq is required to run the block")


def _read_lines(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().split("\n")


def _removal_notice_span():
    """(start, end, block): the notice paragraph's line index, the closing fence's index, and the
    first bash fence after the paragraph (the removed-flags block)."""
    lines = _read_lines(SKILL_MD)
    start = next((i for i, line in enumerate(lines) if line.startswith(NOTICE_ANCHOR)), None)
    assert start is not None, "SKILL.md: removed-flags paragraph %r not found" % NOTICE_ANCHOR
    open_idx = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == "```bash"), None)
    assert open_idx is not None, "SKILL.md: no bash fence after the removed-flags paragraph"
    close_idx = next((i for i in range(open_idx + 1, len(lines)) if lines[i].strip() == "```"), None)
    assert close_idx is not None, "SKILL.md: removed-flags block is not closed"
    block = "\n".join(lines[open_idx + 1:close_idx])
    assert block.strip(), "SKILL.md: removed-flags block is empty"
    return start, close_idx, block


def _run_removed_flags_block(tmp_path, args):
    """Run the block, then a sentinel `touch "$MARK"`; return (code, stdout, stderr, ran_after)."""
    _, _, block = _removal_notice_span()
    mark = tmp_path / "mark"
    script = block + '\ntouch "$MARK"\n'
    env = {"PATH": os.environ.get("PATH", ""), "REVIEW_CODE_ARGS": args, "MARK": str(mark)}
    out = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True,
                         timeout=60, stdin=subprocess.DEVNULL)
    return out.returncode, out.stdout, out.stderr, mark.exists()


def _verify_refusal_lines():
    """The setup.md lines from `VERIFY_CMD=$(` through the refusal line."""
    lines = _read_lines(SETUP_MD)
    start = next((i for i, line in enumerate(lines) if line.startswith("VERIFY_CMD=$(")), None)
    assert start is not None, "setup.md: the `VERIFY_CMD=$(` line not found"
    end = next((i for i in range(start, len(lines))
                if lines[i].startswith('[ -z "$NO_VERIFY" ]')), None)
    assert end is not None, "setup.md: the verify refusal line `[ -z \"$NO_VERIFY\" ]...` not found"
    return "\n".join(lines[start:end + 1])


def _run_verify_refusal(verify_json):
    script = _verify_refusal_lines() + '\nprintf "%s" "$VERIFY_CMD"\n'
    env = {"PATH": os.environ.get("PATH", ""), "VERIFY_JSON": verify_json}
    out = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True,
                         timeout=60, stdin=subprocess.DEVNULL)
    return out.returncode, out.stdout, out.stderr


# --- the removed-flags block -------------------------------------------------


def test_review_only_flag_is_answered_and_runs_nothing(tmp_path):
    code, out, err, ran_after = _run_removed_flags_block(tmp_path, "--review-only")
    assert code == 1, (out, err)
    assert out == (
        "review-code: --review-only was removed. Code review runs only as its one "
        "review-and-fix loop, so nothing ran. Run /superheroes:review-code without --review-only.\n"
    )
    assert not ran_after, "the sentinel after the block ran: the flag did not stop the run"


def test_post_flag_is_answered_and_runs_nothing(tmp_path):
    code, out, err, ran_after = _run_removed_flags_block(tmp_path, "--post")
    assert code == 1, (out, err)
    assert out == (
        "review-code: --post was removed. Code review runs only as its one "
        "review-and-fix loop, so nothing ran. Run /superheroes:review-code without --post.\n"
    )
    assert not ran_after, "the sentinel after the block ran: the flag did not stop the run"


@pytest.mark.parametrize("args", ["pr 12 --focus x", "branch", "--result-file /tmp/r.json", ""])
def test_ordinary_arguments_pass_through(tmp_path, args):
    code, out, err, ran_after = _run_removed_flags_block(tmp_path, args)
    assert code == 0, (out, err)
    assert out == "" and err == ""
    assert ran_after, "the sentinel after the block did not run on an ordinary invocation"


def test_a_removed_flag_among_other_arguments_is_still_answered(tmp_path):
    code, out, _, ran_after = _run_removed_flags_block(tmp_path, "pr 12 --review-only --focus x")
    assert code == 1
    assert "--review-only was removed" in out
    assert not ran_after


# --- the verify refusal ------------------------------------------------------


@needs_jq
@pytest.mark.parametrize("verify_json", [
    '{"verifyCommand": null, "verifyRefusal": {"reason": "verify-command-required", '
    '"message": "%s"}}' % NO_VERIFY_MESSAGE,
    '{"verifyCommand": "pytest -q", "verifyRefusal": {"reason": "verify-command-required", '
    '"message": "%s"}}' % NO_VERIFY_MESSAGE,
], ids=["no-command", "command-but-refusal-reported"])
def test_setup_refuses_when_the_resolver_reports_a_refusal(verify_json):
    code, out, err = _run_verify_refusal(verify_json)
    assert code == 1, (out, err)
    assert err == "review-code: %s\n" % NO_VERIFY_MESSAGE


@needs_jq
def test_setup_refuses_when_the_resolver_result_is_empty():
    # The resolver call falls back to `{}` when it fails; that must refuse with its own
    # diagnostic, not a second copy of the resolver's authoritative refusal message.
    code, out, err = _run_verify_refusal("{}")
    assert code == 1, (out, err)
    assert err.startswith("review-code: the verify-command resolver did not return a result")
    assert NO_VERIFY_MESSAGE not in "\n".join(_read_lines(SETUP_MD))
    assert "|| VERIFY_JSON='{}'" in "\n".join(_read_lines(SETUP_MD)), (
        "setup.md no longer falls back to `{}` when the resolver fails")


@needs_jq
def test_setup_passes_a_configured_command():
    code, out, err = _run_verify_refusal('{"verifyCommand": "pytest -q", "verifyRefusal": null}')
    assert code == 0, (out, err)
    assert out == "pytest -q"
    assert err == ""


# --- the read-only path is gone from skills/review-code/ ---------------------


def _review_code_files():
    for root, _dirs, names in os.walk(REVIEW_CODE):
        for name in sorted(names):
            yield os.path.join(root, name)


def _text_outside_the_removal_notice(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if os.path.abspath(path) != os.path.abspath(SKILL_MD):
        return text
    start, end, _ = _removal_notice_span()
    lines = text.split("\n")
    return "\n".join(lines[:start] + lines[end + 1:])


def test_no_file_names_the_review_only_flag_outside_the_removal_notice():
    hits = [os.path.relpath(p, PLUGIN) for p in _review_code_files()
            if "--review-only" in _text_outside_the_removal_notice(p)]
    assert hits == []


def test_the_headless_presentation_contract_file_is_gone():
    assert not os.path.exists(HEADLESS_MD)


def test_no_file_names_a_review_only_or_unverified_verify_mode():
    pattern = re.compile(r"mode:\s*`?(review-only|unverified)")
    hits = [os.path.relpath(p, PLUGIN) for p in _review_code_files()
            if pattern.search(_text_outside_the_removal_notice(p))]
    assert hits == []


def test_skill_has_no_read_only_section_and_no_review_path_variable():
    with open(SKILL_MD, encoding="utf-8") as fh:
        text = fh.read()
    assert not re.search(r"^#+\s*Read-Only Path", text, re.MULTILINE)
    assert "REVIEW_PATH" not in text
