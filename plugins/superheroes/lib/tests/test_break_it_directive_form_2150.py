"""#2150: a break-it test written in the project's own directive form comes through review kept."""
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import round_driver as RD  # noqa: E402
import test_break_it_loop as TL  # noqa: E402  (its `World` drives `RD._fold`)
from test_break_it_loop import world  # noqa: E402,F401  (the fixture, reused by name)
from test_test_role_seat import _render_panel, NEW  # noqa: E402

CHECK = "scripts/check_directives" + ".py"  # the fixture project's directive validator
JSTEST = "tests/charge_once.test" + ".js"  # the JS break-it test
CHARGE = TL.CHARGE_PATH  # the World's changed file
_AGENT_FILE = os.path.join(os.path.dirname(_LIB), "agents", "test-role.md")

_CLAUDE_MD = (
    "Every test file that reads a repository file starts with `// gate-reads: <globs> — <reason>`, "
    "checked by `scripts/check_directives.py`.\n")
_CHECK_SOURCE = (
    "import re\n"
    "import sys\n"
    "\n"
    "DIRECTIVE = re.compile(r'^// gate-reads: \\S.* \\u2014 \\S.+$', re.MULTILINE)\n"
    "bad = []\n"
    "for path in sys.argv[1:]:\n"
    "    with open(path, encoding='utf-8') as handle:\n"
    "        text = handle.read()\n"
    "    if 'readFileSync' in text and not DIRECTIVE.search(text):\n"
    "        bad.append(path)\n"
    "for path in bad:\n"
    "    print(path)\n"
    "sys.exit(1 if bad else 0)\n")

_JS_BODY = (
    "const assert = require('node:assert');\n"
    "const fs = require('node:fs');\n"
    "const path = require('node:path');\n"
    "const source = fs.readFileSync(path.join(__dirname, '..', '%s'), 'utf8');\n"
    "assert.ok(source.includes('if not ledger:'), 'the charge retries without an idempotency guard');\n"
    % CHARGE)
BARE = "// gate-reads: " + CHARGE + "\n" + _JS_BODY
FULL = ("// gate-reads: " + CHARGE + " — reads the charge source to pin the idempotency guard\n"
        + _JS_BODY)


def _write_project_rule(repo):
    """The fixture project's own rule: a CLAUDE.md line and the check it names (left uncommitted)."""
    TL._write(repo, "CLAUDE.md", _CLAUDE_MD)
    TL._write(repo, CHECK, _CHECK_SOURCE)


def _run_check(cwd, *paths):
    return subprocess.run([sys.executable, str(cwd / CHECK)] + list(paths), cwd=str(cwd),
                          capture_output=True, text=True)


def _js_finding(content):
    """The Python finding's keys with `file` and the block's `path` at the JS test, run by `node`."""
    block = "break-it-test v1\npath: %s\nrun: node %s\n---\n%s" % (JSTEST, JSTEST, content)
    return dict(TL._break_it_finding(), file=JSTEST, suggestion=block)


@pytest.fixture
def ruled_world(world):
    _write_project_rule(world.repo)
    return world


def _fold_failing(world, content):
    """Fold the JS finding; its run must FAIL on the panel head, else the loop drops it and nothing is fixed."""
    world.fold_panel(_js_finding(content))
    (run,) = world.round_record["breakItRuns"]
    assert run["outcome"] == "failed", run
    assert [f["file"] for f in world.state["_toVerify"]] == [JSTEST]
    return world.key_of_failed_run()


def _fix_with(world, content):
    """Fixed disposition, the JS test written at its path, then `fix` commits it with everything else."""
    world.disposition("fixed")
    TL._write(world.repo, JSTEST, content)
    world.fix(None)
    assert TL._git(world.repo, "show", "HEAD:" + JSTEST) == content.strip()


def test_the_projects_check_rejects_the_bare_form_and_accepts_the_full_one(ruled_world, tmp_path):
    # bites on: a fixture check that does not tell the bare directive from the full one, which would make T4/T5 prove nothing
    bare, full = tmp_path / "bare.test.js", tmp_path / "full.test.js"
    bare.write_text(BARE, encoding="utf-8")
    full.write_text(FULL, encoding="utf-8")
    refused = _run_check(ruled_world.repo, str(bare))
    assert (refused.returncode, refused.stdout.strip()) == (1, str(bare)), refused
    accepted = _run_check(ruled_world.repo, str(full))
    assert (accepted.returncode, accepted.stdout) == (0, ""), accepted


def test_the_test_roles_panel_order_carries_the_content_rules_after_the_run_rules(tmp_path):
    # bites on: the content rules dropped from the grammar render, moved off the run rules, or leaking to another seat
    text = _render_panel(tmp_path, NEW)
    grammar = "```\n%s\n```\n\n%s\n\n%s" % (break_it.BLOCK_TEMPLATE, break_it.RUN_RULES, break_it.CONTENT_RULES)
    assert text.count(break_it.CONTENT_RULES) == 1
    assert grammar in text
    assert text.index(break_it.RUN_RULES) + len(break_it.RUN_RULES) + 2 == text.index(break_it.CONTENT_RULES)
    assert break_it.CONTENT_RULES not in _render_panel(tmp_path, "code-reviewer")


def test_the_content_rules_and_the_agent_paragraph_name_no_project_or_marker():
    # bites on: a rule text naming a marker literal or a project, and the agent paragraph missing from its section
    with open(_AGENT_FILE, encoding="utf-8") as handle:
        agent = handle.read()
    start = agent.index("\n## Break-it tests")
    end = agent.index("\n## ", start + 1)
    section = agent[start:end]
    (paragraph,) = [p for p in section.split("\n\n")
                    if "the way the project's own rules require a committed test to be" in p]
    texts = {"CONTENT_RULES": break_it.CONTENT_RULES, "test-role.md paragraph": paragraph}
    for name, text in texts.items():
        for banned in ("gate-reads", "weekly"):
            assert banned not in text.lower(), (name, banned)
    paragraphs = section.split("\n\n")
    assert paragraphs[paragraphs.index(paragraph) - 1].startswith("For each touched area, write at least one")


def test_a_test_in_the_projects_full_directive_form_comes_through_review_kept(ruled_world):
    # bites on: the kept check reading a test the project's own rules accept, committed unchanged, as anything but kept
    world = ruled_world
    _fold_failing(world, FULL)
    _fix_with(world, FULL)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is False
    (row,) = world.round_record["breakItKept"]
    assert (row["path"], row["outcome"]) == (JSTEST, "kept") and row["outcome"] == break_it.KEPT, row
    committed = _run_check(world.repo, JSTEST)
    assert (committed.returncode, committed.stdout) == (0, ""), committed
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "converged"


def test_a_bare_directive_extended_at_commit_still_reads_changed_and_cannot_certify(ruled_world):
    # bites on: the field failure going quiet: a bare directive extended at commit must keep reading changed
    world = ruled_world
    _fold_failing(world, BARE)
    (run,) = world.round_record["breakItRuns"]
    assert run["content"] == BARE  # the body-match fallback has a record to search with
    _fix_with(world, FULL)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is True
    (row,) = world.round_record["breakItKept"]
    assert (row["path"], row["outcome"]) == (JSTEST, "changed") and row["outcome"] == break_it.KEPT_CHANGED, row
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "cannot-certify"
