"""Every rendered seat order states the allowance, and no review-seat text tells a seat to run a
command (#2071): the renderer's one chokepoint, the dispatch preamble, the templates, and the
no-denylist guard over all of them."""
import glob
import os
import re

import pytest

import engine_adapter as EA
import engine_dispatch as ED
import round_orders as RO
import round_phases as RP
import seat_allowance as SA
from test_round_orders import _GOLDEN_CONTEXTS

_HEADING = "## What you may run"
_REVIEW_PHASES = [p for p in RO.ORDER_PHASES if p != RP.P_FIXER]
_ORDERS_DIR = os.path.join(os.path.dirname(RO.__file__), "..", "rubric", "orders")

# The guard's probe data: a sample of program names, kept here and nowhere in shipped code.
_PROGRAM_SAMPLE = ("security", "curl", "bash", "sh", "zsh", "python", "node", "rm", "mongosh",
                   "osascript", "ssh")
_DENYLIST_VERB_RE = re.compile(
    r"(?i)\b(never|do not|don't|must not|cannot)\s+(run|execute|call|invoke)\b.{0,80}?`[^`]+`",
    re.S)
_ARGV_DENY_TOKENS = ("prefix_rule", "forbidden", "disabled_tools", "deny")
_REVIEW_SEAT = {"vendor": "codex", "model": "gpt-6.1-sol", "effort": "xhigh", "role": "brief-check"}


def _render(phase):
    text, reason = RO.render_order(phase, "golden-seat", _GOLDEN_CONTEXTS[phase]())
    assert reason is None, reason
    return text


def _allowance_block(text):
    """The text under the allowance heading, up to the next blank line."""
    assert text.count(_HEADING) == 1
    return text.split(_HEADING + "\n\n", 1)[1].split("\n\n", 1)[0]


def _denylist_faults(text):
    faults = []
    if _DENYLIST_VERB_RE.search(text):
        faults.append("a never-run clause followed by a backticked word")
    for name in _PROGRAM_SAMPLE:
        if re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", text):
            faults.append("program name %r" % name)
    return faults


def test_golden_contexts_cover_every_order_phase():
    assert set(_GOLDEN_CONTEXTS) == set(RO.ORDER_PHASES)


@pytest.mark.parametrize("phase", list(RO.ORDER_PHASES))
def test_every_order_states_its_allowance_exactly_once(phase):
    text = _render(phase)
    expected = SA.FIXER_ALLOWANCE if phase == RP.P_FIXER else SA.REVIEW_ALLOWANCE
    other = SA.REVIEW_ALLOWANCE if phase == RP.P_FIXER else SA.FIXER_ALLOWANCE
    assert text.count(expected) == 1
    assert _allowance_block(text) == expected
    assert other not in text


@pytest.mark.parametrize("phase", list(RO.ORDER_PHASES))
def test_unknown_phase_and_failed_render_refuse_before_the_block(phase):
    text, reason = RO.render_order("no-such-phase", "seat", _GOLDEN_CONTEXTS[phase]())
    assert text is None and reason == "no-template:no-such-phase"
    ctx = _GOLDEN_CONTEXTS[phase]()
    ctx["placeholders"] = dict(ctx["placeholders"], STRAY_KEY="x")
    text, reason = RO.render_order(phase, "seat", ctx)
    assert text is None and reason.startswith("unused-context-key:")


def test_preamble_carries_the_review_allowance_and_no_command_licence():
    assert SA.REVIEW_ALLOWANCE in ED.ANTIHIJACK_PREAMBLE
    assert "run read-only commands" not in ED.ANTIHIJACK_PREAMBLE


def test_review_templates_tell_no_seat_to_run_a_command():
    paths = sorted(glob.glob(os.path.join(_ORDERS_DIR, "dispatch-*.md")))
    assert paths
    hits = []
    for path in paths:
        if os.path.basename(path) == "dispatch-fixer.md":
            continue
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        for phrase in ("shell range", "read-only command", "grep the"):
            if phrase in body:
                hits.append("%s: %r" % (os.path.basename(path), phrase))
    assert not hits, "; ".join(hits)


def test_allowance_texts_are_positive_and_list_no_programs():
    texts = {
        "REVIEW_ALLOWANCE": SA.REVIEW_ALLOWANCE,
        "FIXER_ALLOWANCE": SA.FIXER_ALLOWANCE,
        "ANTIHIJACK_PREAMBLE": ED.ANTIHIJACK_PREAMBLE,
    }
    for phase in RO.ORDER_PHASES:
        texts["order:%s" % phase] = _allowance_block(_render(phase))
    faults = {name: _denylist_faults(text) for name, text in texts.items()}
    assert not {name: found for name, found in faults.items() if found}


def test_denylist_guard_bites_on_a_denylist_sentence():
    assert _denylist_faults("Never run `curl` or `rm` here.")
    assert _denylist_faults("You must not execute anything like `ssh`.")
    assert _denylist_faults("Use bash for it.")
    assert not _denylist_faults(SA.REVIEW_ALLOWANCE)


def test_codex_review_argv_carries_no_denylist_token():
    res = EA.build_argv_result(_REVIEW_SEAT, "review", {"cwd": "/tmp/view"})
    assert res.get("reason") is None, res
    argv = res["argv"]
    bad = [t for t in argv if any(w in t for w in _ARGV_DENY_TOKENS)]
    assert not bad, bad
