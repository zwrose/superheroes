"""#2011 WO-1: the refused-command stop rule has one home and reaches every plugin-written write order.

Part one pins `refusals_fault` and the composition of `ORDER_TEXT`. Part two is the census: each of
the three order surfaces (write-engine prompt, native preamble, implementer agent) is rendered or
read on its own and must carry the constant's text.
"""
import os

import pytest

import command_refusals as CR
import native_engine as NE
import round_orders as RO
import round_phases as RP
from test_engine_dispatch_write import (  # noqa: F401  (the autouse pin is a fixture)
    FakeRunner, ED, _build_ok_stdout, _dispatch_write, _linked_worktree, _pin_temp_base_to_tmp_path,
    _prompt,
)
from test_native_engine_1947 import (  # noqa: F401  (the autouse pin is a fixture)
    _make_repo, _open, _pin_env, _routed,
)
from test_round_orders import _GOLDEN_CONTEXTS, _base_context, _panel_placeholders

_PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_IMPLEMENTER_MD = os.path.join(_PLUGIN_ROOT, "agents", "implementer.md")
_BLOCK_HEADING = "## Refused or denied commands"


def _entry(**over):
    entry = {"command": "git push", "refusedBy": "hook", "hook": "no-push", "next": "stopped"}
    entry.update(over)
    return entry


def _without(key):
    entry = _entry()
    del entry[key]
    return entry


# a consuming project's PR shape (#2167): the cloud sandbox's own refusal message named its step
_SANDBOX_ROUTE_ENTRY = {
    "command": "cd app && npm test", "refusedBy": "sandbox", "hook": None,
    "route": "split into plain commands", "next": "ran cd and npm test as plain commands",
}


# --- refusals_fault -----------------------------------------------------------------------


@pytest.mark.parametrize("value", [
    [],
    [_entry()],
    [_without("hook")],
    [_entry(hook=None)],
    [_entry(refusedBy="permission", hook=None), _entry(refusedBy="sandbox")],
    [_entry(route="git checkout --theirs f.txt")],
    [_entry(route=None)],
    [_entry(refusedBy="permission", hook=None, route=None), _entry(refusedBy="sandbox", route=None)],
    [_entry(hook=None, route="gh pr view 5")],
    [_SANDBOX_ROUTE_ENTRY],
])
def test_refusals_fault_accepts_valid_lists(value):
    # axis: acceptance of valid refusals — see bite-proof record wo1_2011_stop_rule
    assert CR.refusals_fault(value) is None


@pytest.mark.parametrize("value,reason", [
    (None, "refusals not a list"),
    ({}, "refusals not a list"),
    ({"command": "x"}, "refusals not a list"),
    ("git push", "refusals not a list"),
    (["git push"], "refusals[0] not an object"),
    ([_entry(), None], "refusals[1] not an object"),
    ([_without("command")], "refusals[0].command missing"),
    ([_without("refusedBy")], "refusals[0].refusedBy missing"),
    ([_without("next")], "refusals[0].next missing"),
    ([_entry(command="")], "refusals[0].command blank"),
    ([_entry(command="   ")], "refusals[0].command blank"),
    ([_entry(command=3)], "refusals[0].command blank"),
    ([_entry(next=" \n")], "refusals[0].next blank"),
    ([_entry(), _entry(refusedBy="denied")], "refusals[1].refusedBy"),
    ([_entry(refusedBy=7)], "refusals[0].refusedBy"),
    ([_entry(refusedBy=None)], "refusals[0].refusedBy"),
    ([_entry(hook="")], "refusals[0].hook"),
    ([_entry(hook="  ")], "refusals[0].hook"),
    ([_entry(hook=5)], "refusals[0].hook"),
    ([_entry(foo="bar")], "refusals[0] unknown key: foo"),
    ([_entry(route="")], "refusals[0].route"),
    ([_entry(route="  ")], "refusals[0].route"),
    ([_entry(route=5)], "refusals[0].route"),
    ([_entry(route=["git status"])], "refusals[0].route"),
    ([_entry(refusedBy="permission", route="")], "refusals[0].route"),
    ([_entry(refusedBy="permission", hook=None, route="git status")],
     "refusals[0].route needs refusedBy hook or sandbox"),
    ([_entry(), _entry(refusedBy="permission", route="git status")],
     "refusals[1].route needs refusedBy hook or sandbox"),
    ([dict(_SANDBOX_ROUTE_ENTRY, route="  ")], "refusals[0].route"),
    ([dict(_SANDBOX_ROUTE_ENTRY, route=["split"])], "refusals[0].route"),
    ([dict(_SANDBOX_ROUTE_ENTRY, next="")], "refusals[0].next blank"),
    ([dict(_SANDBOX_ROUTE_ENTRY, refusedBy="cloud-sandbox")], "refusals[0].refusedBy"),
])
def test_refusals_fault_names_the_fault(value, reason):
    # axis: malformed-entry diagnostics — see bite-proof record wo1_2011_stop_rule
    assert CR.refusals_fault(value) == reason


# the one exception to the stop rule, pinned once as a literal
_EXCEPTION_SENTENCE = (
    "The one exception: when the refusing guard's or hook's own refusal message names a route "
    "(an exact command or tool to use instead), you may take exactly that route, once, and record "
    "it as that entry's route; every other form, and every auto-mode classifier denial, stays a stop."
)


def test_a_route_is_valid_from_a_hook_or_the_sandbox_only():
    # axis: a route is read from the refusers whose own message can name one, never from a permission denial (#2167)
    assert CR.ROUTE_REFUSED_BY == ("hook", "sandbox")
    assert set(CR.ROUTE_REFUSED_BY) < set(CR.REFUSED_BY)
    assert CR.refusals_fault([_SANDBOX_ROUTE_ENTRY]) is None
    assert CR.refusals_fault([_entry(route="git checkout --theirs f.txt")]) is None
    assert CR.refusals_fault([dict(_SANDBOX_ROUTE_ENTRY, refusedBy="permission")]) == (
        "refusals[0].route needs refusedBy hook or sandbox")


def test_stop_rule_ends_with_the_one_exception():
    # axis: the stop rule carries its one exception, and the order text carries the stop rule — see bite-proof record wo_a_2054_route
    assert CR.STOP_RULE.endswith(" " + _EXCEPTION_SENTENCE)
    assert CR.STOP_RULE.count("exception") == 1
    assert _EXCEPTION_SENTENCE in CR.ORDER_TEXT
    assert CR.ORDER_TEXT.startswith(CR.STOP_RULE)


def test_order_text_composition():
    # axis: the composition of ORDER_TEXT — see bite-proof record wo1_2011_stop_rule
    assert CR.ORDER_TEXT.startswith(CR.STOP_RULE)
    assert CR.REFUSAL_MEANING in CR.ORDER_TEXT
    assert CR.ENTRY_SHAPE in CR.ORDER_TEXT
    for member in CR.REFUSED_BY + CR.ENTRY_REQUIRED + CR.ENTRY_OPTIONAL:
        assert member in CR.ENTRY_SHAPE


@pytest.mark.parametrize("phrase", [
    "permission denial",
    "hook refusal",
    "sandbox refusal",
    "shell-command checker",
    "auto-mode classifier",
    "approval that nobody answers",
])
def test_refusal_meaning_names_each_kind(phrase):
    # axis: the meaning names every kind of refusal — see bite-proof record wo6_2011_sendback
    assert phrase in CR.REFUSAL_MEANING


# --- the census: one test per order surface ------------------------------------------------


def test_review_order_carries_no_refusal_block():
    ctx = _GOLDEN_CONTEXTS[RP.P_PANEL]()
    text, reason = RO.render_order(RP.P_PANEL, "golden-seat", ctx)
    assert reason is None, reason
    assert _BLOCK_HEADING not in text
    assert CR.ORDER_TEXT not in text
    engine_ctx = _base_context(host_seat=False, placeholders=_panel_placeholders())
    text, reason = RO.render_order(RP.P_PANEL, "code-reviewer", engine_ctx)
    assert reason is None, reason
    assert CR.ORDER_TEXT not in text


def test_census_write_prompt(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    prompt_path = _prompt(tmp_path, "Implement exactly the assigned work order.\n")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt, prompt_path=prompt_path)
    assert res["ok"] is True
    with open(os.path.join(str(tmp_path / "run"), ED.PROMPT_NAME), encoding="utf-8") as fh:
        staged = fh.read()
    # axis: the stop rule reaches every plugin-written write order — see bite-proof record wo1_2011_stop_rule
    assert CR.ORDER_TEXT in staged
    assert staged.index(ED.WRITE_DISPATCH_PROCESS_RULE) < staged.index(CR.ORDER_TEXT)


def test_census_native_preamble(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    code, _out = _open(capsys, r, deadline=600, items=["src/new.txt"])
    assert code == 0
    with open(os.path.join(os.path.realpath(r.run), "agent-prompt.md"), encoding="utf-8") as fh:
        prompt = fh.read()
    # axis: the stop rule reaches every plugin-written write order — see bite-proof record wo1_2011_stop_rule
    assert CR.ORDER_TEXT in prompt
    assert "{ENROLL_COMMAND}" not in prompt
    assert "{RESULT_PATH}" not in prompt
    assert os.path.join(os.path.realpath(r.run), "result.json") in prompt


def test_native_preamble_constant_keeps_both_placeholders():
    assert "{ENROLL_COMMAND}" in NE.NATIVE_PREAMBLE
    assert "{RESULT_PATH}" in NE.NATIVE_PREAMBLE
    filled = (NE.NATIVE_PREAMBLE.replace("{ENROLL_COMMAND}", "enroll-here")
              .replace("{RESULT_PATH}", "/run/result.json"))
    assert "{ENROLL_COMMAND}" not in filled
    assert "{RESULT_PATH}" not in filled
    assert '{"status":' in filled


def test_census_implementer_md():
    with open(_IMPLEMENTER_MD, encoding="utf-8") as fh:
        body = fh.read()
    # axis: the stop rule reaches every plugin-written write order — see bite-proof record wo1_2011_stop_rule
    assert " ".join(CR.ORDER_TEXT.split()) in " ".join(body.split())
    ladder = body.index("Highest precedence first:")
    rung_one = body.index("1. **Never claim a run you did not make.**")
    assert ladder < body.index("**Refused or denied commands.**") < rung_one


# --- the file-write rule (#2126): one home, every implementer order -------------------------


def test_census_file_write_rule_write_prompt(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    prompt_path = _prompt(tmp_path, "Implement exactly the assigned work order.\n")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt, prompt_path=prompt_path)
    assert res["ok"] is True
    with open(os.path.join(str(tmp_path / "run"), ED.PROMPT_NAME), encoding="utf-8") as fh:
        staged = fh.read()
    # axis: the file-write rule reaches every implementer order — see bite-proof record wo_2126_file_write
    assert staged.count(CR.FILE_WRITE_RULE) == 1
    assert staged.index(CR.ORDER_TEXT) < staged.index(CR.FILE_WRITE_RULE)


def test_census_file_write_rule_native_preamble(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    code, _out = _open(capsys, r, deadline=600, items=["src/new.txt"])
    assert code == 0
    with open(os.path.join(os.path.realpath(r.run), "agent-prompt.md"), encoding="utf-8") as fh:
        prompt = fh.read()
    # axis: the file-write rule reaches every implementer order — see bite-proof record wo_2126_file_write
    assert prompt.count(CR.FILE_WRITE_RULE) == 1
    assert prompt.index(CR.FILE_WRITE_RULE) < prompt.index("The order follows, verbatim.")


def test_file_write_rule_has_one_home():
    # A hand copy of the sentence anywhere in the shipped plugin outside its home is a second copy.
    marker = "file-write and file-edit tools (Write and Edit on"
    home = os.path.join(_PLUGIN_ROOT, "lib", "command_refusals.py")
    copies = []
    for root, dirs, files in os.walk(_PLUGIN_ROOT):
        dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", ".git")]
        for name in files:
            if not name.endswith((".py", ".md", ".json", ".txt")):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8", errors="replace") as fh:
                if marker in " ".join(fh.read().split()):
                    copies.append(os.path.relpath(path, _PLUGIN_ROOT))
    assert copies == [os.path.relpath(home, _PLUGIN_ROOT)]
