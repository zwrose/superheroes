"""The stack-card qualifier and the membership reasons each have one home; the copies that read them follow it."""
import os

import test_issue_contract as T
from test_issue_contract import _Members, _build_ready, _head, _in_stack, _pr_row, _vet, _world, ic

_REFERENCE = os.path.join(os.path.dirname(ic.__file__), os.pardir, "skills", "showrunner", "reference")


def _read(name):
    with open(os.path.join(_REFERENCE, name), encoding="utf-8") as fh:
        return fh.read()


def test_the_membership_fakes_use_the_readers_exported_reasons():
    # axis: a fake that hand-types a reason drifts from the reader the judge compares against
    assert T.NOT_LINKED["reason"] == ic.stack_check.REASON_NOT_LINKED
    assert T.STACK_UNREADABLE["reason"] == ic.stack_check.REASON_STACK_UNREADABLE


def test_the_hold_message_is_built_from_the_loaded_qualifier(tmp_path, capsys, monkeypatch):
    # axis: the plain-PARKED hold names whatever qualifier the form holds, never a hand-typed copy
    monkeypatch.setattr(ic, "STACK_CARD_QUALIFIER", "a renamed qualifier for #")
    fake = _world(prs=[_pr_row(101, closes=12, vet=_vet("PARKED", _head(101)))])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert "or PARKED a renamed qualifier for #50," in out["blockers"]["held"][0]["why"]


def test_no_reference_doc_carries_a_copy_of_the_qualifier():
    # axis: no reference doc restates the qualifier its one home holds
    for name in ("routing.md", "vet-receipt.md", "dispatch-preflight.md"):
        assert ic.STACK_CARD_QUALIFIER not in _read(name), name
