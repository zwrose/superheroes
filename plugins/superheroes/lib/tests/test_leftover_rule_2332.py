"""#2332 gaps 2 and 3 of the leftover-acceptance rule: a leftover id and title are compared under one normalisation (a
wrapped id, a differently cased or dashed id, a title with other quotes or punctuation), and an acceptance that carries
``fixed-above #<PR> <commit>`` passes only when that PR is a higher member of this PR's own stack. One rule
(leftover_accepting), two callers (vet_slot handback --pr and vet_slot write). No real gh: every call is faked."""
import pytest

import leftover_accepting as la
import vet_slot as vs
from test_vet_slot_leftovers_2280 import (  # noqa: F401
    body, record_comment, comment, RECEIPT, Fake, REPO, PR, F1, F2, ACCEPT_ONLY_F1, handback, write, _gh_on_path)


def rec(*pairs):
    """A review record as ``review_record.read`` returns it, leaving each (id, title) for the owner."""
    findings = [{"id": i, "title": t, "outcome": "left-for-owner"} for i, t in pairs]
    return {"ok": True, "findings": findings, "leftForOwner": [i for i, _t in pairs]}


def gaps(record, accepting):
    return [g["id"] for g in la.missing(record, body(accepting))]


# --- gap 2: the id normalisation -------------------------------------------------------------------

def test_g2a_the_field_case_a_quoted_title_and_a_cased_id_are_named():
    record = rec(("f-1", 'the "retry" loop never backs off.'))
    accepting = "- F-1 — the retry loop never backs off: merging accepts slower recovery.\n"
    assert gaps(record, accepting) == []


@pytest.mark.parametrize("title, written", [
    ("the “retry” loop never backs off", "the retry loop never backs off"),
    ("the `retry` loop never backs off", "the retry loop never backs off"),
    ("a long-lived cache entry survives", "a long lived cache entry survives"),
    ("a long lived cache entry survives", "a long-lived cache entry survives"),
    ("The Retry Loop Never Backs Off", "the retry loop never backs off"),
    ("a long‑lived cache entry survives", "a long-lived cache entry survives"),
])
def test_g2a_a_title_is_compared_by_its_words(title, written):
    assert gaps(rec(("f-1", title)), "- f-1 %s: merging accepts it.\n" % written) == []


def test_g2a_a_title_with_other_words_is_still_missing():
    assert gaps(rec(("f-1", "the retry loop never backs off")), "- f-1 the retry loop backs off: accepted.\n") == ["f-1"]


@pytest.mark.parametrize("ids", [("F/1", "F.1.2"), ("f-1", "f-1-b")])
def test_g2b_distinct_ids_with_one_title_are_not_satisfied_by_one_acceptance(ids):
    first, second = ids
    record = rec((first, "same title here"), (second, "same title here"))
    assert gaps(record, "- %s same title here: accepted.\n" % second) == [first]


def test_g2c_ids_sharing_a_normal_form_are_matched_byte_for_byte():
    record = rec(("F-1", "same title here"), ("f-1", "same title here"))
    assert gaps(record, "- F-1 same title here: accepted.\n") == ["f-1"]
    assert gaps(record, "- f-1 same title here: accepted.\n") == ["F-1"]
    assert gaps(record, "- F-1 same title here: ok.\n- f-1 same title here: ok.\n") == []


@pytest.mark.parametrize("written", ["xf-1", "f-10", "f-1-b", "f-1x"])
def test_g2d_an_id_inside_other_text_does_not_name_it(written):
    assert gaps(rec(("f-1", "slow retry")), "- %s slow retry: accepted.\n" % written) == ["f-1"]


@pytest.mark.parametrize("written", ["f-1.", "f-1:", "f-1,", "`f-1`", "(f-1)", "**f-1**", "F‑1", "f–1", "F-1"])
def test_g2d_an_id_with_punctuation_around_it_or_another_dash_is_named(written):
    assert gaps(rec(("f-1", "slow retry")), "- %s slow retry: accepted.\n" % written) == []


def test_g2d_a_fallback_name_with_spaces_is_named_as_a_run_of_tokens():
    finding = {"file": "lib/x.py", "line": 12, "title": "slow retry", "outcome": "left-for-owner"}
    record = {"ok": True, "findings": [finding], "leftForOwner": ["at lib/x.py:12"]}
    assert gaps(record, "- at lib/x.py:12 slow retry: accepted.\n") == []
    assert gaps(record, "- (at lib/x.py:12). slow retry: accepted.\n") == []
    assert gaps(record, "- at lib/x.py:120 slow retry: accepted.\n") == ["at lib/x.py:12"]
    assert gaps(record, "- lib/x.py:12 at slow retry: accepted.\n") == ["at lib/x.py:12"]


def test_e2_a_title_of_punctuation_only_is_carried_byte_for_byte():
    record = rec(("f-1", "?!"))
    assert gaps(record, "- f-1 ?! accepted.\n") == []
    assert gaps(record, "- f-1 accepted.\n") == ["f-1"]


def test_e3_a_leftover_with_no_title_is_checked_by_id_alone():
    record = {"ok": True, "findings": [{"id": "f-4", "outcome": "left-for-owner"}], "leftForOwner": ["f-4"]}
    assert gaps(record, "- F-4 accepted as is.\n") == []
    assert gaps(record, "None\n") == ["f-4"]


def test_normalise_id_folds_case_form_and_dashes():
    assert la.normalise_id("F‐1") == la.normalise_id("f-1") == "f-1"
    assert la.normalise_id("ＦＯＯ—１") == "foo-1"


# --- gap 3: the fixed-above disposition, parsed ----------------------------------------------------

F2_TITLE = "a stale cache entry survives restart"


def fa(accepting):
    return la.fixed_above(rec(("f-2", F2_TITLE)), body(accepting))


def test_g3_parse_the_full_form_resolves_the_leftover():
    accepting = "- f-2 %s — fixed-above #123 1a2b3c4: the layer above removes it.\n" % F2_TITLE
    assert fa(accepting) == [{"id": "f-2", "title": F2_TITLE, "layer": 123, "commit": "1a2b3c4"}]
    assert fa(accepting.replace("1a2b3c4", "`1a2b3c4`"))[0]["commit"] == "1a2b3c4"
    assert fa(accepting.replace("1a2b3c4", "a" * 40))[0]["commit"] == "a" * 40


@pytest.mark.parametrize("text", [
    "fixed-above",
    "fixed-above 123 1a2b3c4",
    "fixed-above #123 1a2b3c",
    "fixed-above #123 1A2B3C4",
    "fixed-above #0 1a2b3c4",
    "fixed-above #123 1a2b3c4d" + "e" * 40,
    "not-fixed-above #123 1a2b3c4",
])
def test_g3_parse_the_word_alone_or_a_malformed_form_is_plain_text(text):
    assert fa("- f-2 %s — %s: accepted.\n" % (F2_TITLE, text)) == []


def test_g3_parse_a_leftover_not_named_by_the_disposition_item_is_not_listed():
    record = rec(("f-1", "the retry loop never backs off"), ("f-2", F2_TITLE))
    accepting = ("- f-1 the retry loop never backs off: accepted.\n"
                 "- f-2 %s — fixed-above #43 1a2b3c4: fixed.\n" % F2_TITLE)
    assert [c["id"] for c in la.fixed_above(record, body(accepting))] == ["f-2"]


def test_e6_the_first_item_carrying_the_disposition_decides():
    accepting = ("- f-2 %s: accepted plain.\n"
                 "- f-2 %s — fixed-above #43 1a2b3c4: fixed.\n" % (F2_TITLE, F2_TITLE))
    assert [(c["id"], c["layer"]) for c in fa(accepting)] == [("f-2", 43)]
    twice = accepting + "- f-2 %s — fixed-above #44 2b3c4d5: again.\n" % F2_TITLE
    assert [(c["id"], c["layer"]) for c in fa(twice)] == [("f-2", 43)]


def test_e4_fixed_above_over_an_unreadable_record_raises():
    with pytest.raises(la.Unreadable):
        la.fixed_above({"ok": False, "reason": "review-record-missing"}, body("None\n"))


# --- gap 3: the stack check in both callers --------------------------------------------------------

FIXED_ABOVE_ACCEPTING = ACCEPT_ONLY_F1 + "- f-2 %s — fixed-above #43 1a2b3c4: the layer above removes it.\n" % F2_TITLE


def named(layer):
    return ACCEPT_ONLY_F1 + "- f-2 %s — fixed-above #%d 1a2b3c4: the layer above removes it.\n" % (F2_TITLE, layer)


class Membership:
    """A stand-in for ``stack_check.read_membership`` that records its calls."""

    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def __call__(self, *, pr, repo, run=None, **kw):
        self.calls.append((pr, repo))
        if self.error is not None:
            raise self.error
        return self.result


def stack(*numbers):
    return {"ok": True, "members": [{"position": n, "number": num} for n, num in enumerate(numbers, 1)]}


def use(monkeypatch, membership):
    monkeypatch.setattr(vs.stack_check, "read_membership", membership)
    return membership


COMMENTS = [record_comment([F1, F2])]


def test_g3a_a_named_layer_above_this_pr_in_its_stack_passes(monkeypatch, tmp_path):
    membership = use(monkeypatch, Membership(stack(PR, 43)))
    assert handback(body(named(43)), COMMENTS)["ok"] is True
    result, fake = write(body(named(43)), [RECEIPT] + COMMENTS, tmp_path)
    assert result["ok"] is True and len(fake.edited) == 1
    assert membership.calls == [(PR, REPO), (PR, REPO)]


def test_g3b_a_named_pr_that_is_not_in_the_stack_is_refused_by_both_callers(monkeypatch, tmp_path):
    use(monkeypatch, Membership(stack(PR, 43)))
    result = handback(body(named(99)), COMMENTS)
    assert result["ok"] is False and result["reason"] == "fixed-above-not-in-stack"
    assert "f-2" in result["detail"] and "#99" in result["detail"]
    result, fake = write(body(named(99)), [RECEIPT] + COMMENTS, tmp_path)
    assert result["ok"] is False and result["reason"] == "fixed-above-not-in-stack"
    assert "f-2" in result["detail"] and "#99" in result["detail"] and fake.edited == []


@pytest.mark.parametrize("members, layer", [
    ((PR, 43), PR),  # this PR itself is not above itself
    ((41, PR, 43), 41),  # a lower layer
])
def test_g3c_a_named_layer_at_or_below_this_pr_is_refused(monkeypatch, members, layer):
    use(monkeypatch, Membership(stack(*members)))
    result = handback(body(named(layer)), COMMENTS)
    assert result["ok"] is False and result["reason"] == "fixed-above-not-in-stack"
    assert "#%d" % layer in result["detail"] and "at or below" in result["detail"]


def test_g3c_every_failing_claim_is_named(monkeypatch):
    use(monkeypatch, Membership(stack(PR, 43)))
    both = (ACCEPT_ONLY_F1 + "- f-2 %s — fixed-above #99 1a2b3c4: gone.\n" % F2_TITLE)
    twin = {"id": "f-3", "title": "typo in the help text", "outcome": "left-for-owner"}
    both += "- f-3 typo in the help text — fixed-above #43 2b3c4d5: gone.\n"
    result = handback(body(both), [record_comment([F1, F2, twin])])
    assert result["reason"] == "fixed-above-not-in-stack"
    assert "f-2" in result["detail"] and "#99" in result["detail"] and "f-3" not in result["detail"]


@pytest.mark.parametrize("read, reason", [
    ({"ok": False, "reason": "not-linked", "detail": "PR is in no stack"}, "fixed-above-not-in-stack"),
    ("not a dict", "fixed-above-not-in-stack"),
    ({"ok": False, "reason": "stack-unreadable", "detail": "gh failed"}, "fixed-above-unverified"),
    (stack(41, 43), "fixed-above-unverified"),  # this PR is absent from the members
    ({"ok": True, "members": "x"}, "fixed-above-unverified"),
    ({"ok": True}, "fixed-above-unverified"),
])
def test_g3d_a_membership_read_that_does_not_place_this_pr_is_refused(monkeypatch, tmp_path, read, reason):
    use(monkeypatch, Membership(read))
    result = handback(body(named(43)), COMMENTS)
    assert result["ok"] is False and result["reason"] == reason and "f-2" in result["detail"]
    result, fake = write(body(named(43)), [RECEIPT] + COMMENTS, tmp_path)
    assert result["reason"] == reason and fake.edited == []


def test_g3d_the_not_ok_read_names_its_reason_and_detail(monkeypatch):
    use(monkeypatch, Membership({"ok": False, "reason": "stack-unreadable", "detail": "gh failed"}))
    detail = handback(body(named(43)), COMMENTS)["detail"]
    assert "stack-unreadable" in detail and "gh failed" in detail


def test_g3d_a_reader_that_raises_is_unverified(monkeypatch, tmp_path):
    use(monkeypatch, Membership(error=RuntimeError("boom")))
    result = handback(body(named(43)), COMMENTS)
    assert result["reason"] == "fixed-above-unverified" and "boom" in result["detail"]
    result, fake = write(body(named(43)), [RECEIPT] + COMMENTS, tmp_path)
    assert result["reason"] == "fixed-above-unverified" and fake.edited == []


def test_g3d_the_membership_is_read_with_the_callers_run(monkeypatch):
    seen = []

    def reader(*, pr, repo, run=None, **kw):
        seen.append(run)
        return stack(PR, 43)

    use(monkeypatch, reader)
    fake = Fake(body(named(43)), COMMENTS)
    assert vs.run_verb("handback", PR, REPO, run=fake)["ok"] is True
    assert seen == [fake]


def test_g3e_no_fixed_above_acceptance_never_reads_the_stack(monkeypatch, tmp_path):
    membership = use(monkeypatch, Membership(error=AssertionError("must not be read")))
    plain = ACCEPT_ONLY_F1 + "- f-2 %s: merging accepts fixed-above as a word.\n" % F2_TITLE
    assert handback(body(plain), COMMENTS)["ok"] is True
    result, _fake = write(body(plain), [RECEIPT] + COMMENTS, tmp_path)
    assert result["ok"] is True
    assert membership.calls == []


def test_a_missing_leftover_is_refused_before_the_stack_is_read(monkeypatch):
    membership = use(monkeypatch, Membership(stack(PR, 43)))
    result = handback(body(ACCEPT_ONLY_F1), COMMENTS)
    assert result["reason"] == "leftover-not-accepted" and membership.calls == []


def test_a_hold_write_does_not_read_the_stack(monkeypatch, tmp_path):
    membership = use(monkeypatch, Membership(stack(PR)))
    result, _fake = write(body(named(99)), [RECEIPT] + COMMENTS, tmp_path, verdict="NOT-READY")
    assert result["ok"] is True and membership.calls == []
