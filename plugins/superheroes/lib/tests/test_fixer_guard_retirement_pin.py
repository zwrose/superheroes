"""Retirement pin for fixer file-scope guard removal (#1299).

Bites on: code surfaces this order owns — the escalation module must not expose the
guard machinery, and the rendered dispatch-fixer order must not cite the wrapper or
guard step — plus prose surfaces: retired vocabulary absent from review-discipline.md
and auto-fix-loop.md.

**Birth duties.** Under ``rubric/review-discipline.md``, section ``Prefer shapes that cannot fail``:

- **Bite-proof** — recorded at ``lib/tests/bite_proofs/wo_1299_fixer_guard_retirement_pin.md``.
- **Retirement condition and tag** — entry **S14** on the project's keep-or-retire record.
- **By-construction coverage** — the fixer-order leg renders through
  ``round_driver._build_order_render_context``, the same construction path the loop uses
  before dispatch; the prose legs read a closed ``_RETIRED_VOCAB_SURFACES`` enumeration.
"""
import importlib.util
import os
import sys

import pytest

import round_orders as RO
import round_phases as RP

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_PLUGIN_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_ESCALATION_PATH = os.path.join(_LIB, "escalation.py")
_REVIEW_DISCIPLINE = os.path.join(_PLUGIN_ROOT, "rubric", "review-discipline.md")
_AUTO_FIX_LOOP = os.path.join(
    _PLUGIN_ROOT, "skills", "review-code", "reference", "auto-fix-loop.md",
)

_RETIRED_VOCAB_SURFACES = (
    (_REVIEW_DISCIPLINE, ("### The safety-machinery route", "safety machinery")),
    (_AUTO_FIX_LOOP, ("safety machinery", "file-scope guard")),
)

_FIXER_ORDER_FORBIDDEN = (
    "ESCALATION_WRAPPER_PATH",
    "Escalation guard",
    "file-scope guard",
)


def _load_escalation():
    spec = importlib.util.spec_from_file_location("fixer_pin_escalation", _ESCALATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _assert_fixer_order_has_no_guard_instruction(text):
    for needle in _FIXER_ORDER_FORBIDDEN:
        assert needle not in text, "dispatch-fixer order must not cite %r" % needle


def _render_fixer_order_via_round_driver(tmp_path):
    import round_driver as RD

    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": repo, "fixerVendor": "codex"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "fixBatch": [],
    }
    row = RD._seat_transport_row(state, RP.P_FIXER, "fixer", 0, state["config"], {"fixes": []}, repo)
    ctx, _paths = RD._build_order_render_context(
        session_dir, state, 2, RP.P_FIXER, 0, "fixer", 0, {"fixes": []}, row,
    )
    return RO.render_order(RP.P_FIXER, "fixer", ctx)


def test_escalation_module_has_no_file_scope_guard():
    esc = _load_escalation()
    assert not hasattr(esc, "SAFETY_MACHINERY")
    assert not hasattr(esc, "is_safety_machinery")


def test_dispatch_fixer_order_has_no_guard_instruction(tmp_path):
    text, reason = _render_fixer_order_via_round_driver(tmp_path)
    assert reason is None
    _assert_fixer_order_has_no_guard_instruction(text)


@pytest.mark.parametrize(
    "path,literals",
    _RETIRED_VOCAB_SURFACES,
    ids=[os.path.basename(p) for p, _ in _RETIRED_VOCAB_SURFACES],
)
def test_retired_guard_vocabulary_absent(path, literals):
    text = _read(path)
    for literal in literals:
        assert literal not in text, "%s: retired vocabulary %r present" % (path, literal)
