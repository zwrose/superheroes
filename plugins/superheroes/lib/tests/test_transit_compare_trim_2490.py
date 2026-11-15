"""Tests for the transit comparison's common prefix and suffix trim (#2490): `cloud_builder.transit_compare`
runs `difflib` only between the common prefix and the common suffix of the two normalized bodies, and reports
positions in the whole bodies.

The trimmed result is pinned equal to the untrimmed one (`_transit_changes(a, b, trim=False)`, which runs the
matcher on the whole strings) on cases small enough for the untrimmed run to finish fast. One speed test builds a
full-size record part and never calls the untrimmed path. One test pins the known limit: in ambiguous repetitive
text the trimmed run can place an edit at another offset than the untrimmed run, describing the same edit.

No test touches the network or a real `gh`.

bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2490_transit_trim.md
"""
import difflib
import json
import os
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder as cb  # noqa: E402
import review_record as rr  # noqa: E402


def _lines(start, stop, tag="rec"):
    """Varied numbered lines, never one character repeated."""
    return [f"line {i:04d} {tag} value {(i * 7919) % 1009} of the record, ref {(i * 31) % 97:02d}"
            for i in range(start, stop)]


BASE = "\n".join(_lines(0, 90))  # about 4,200 characters
MID = len(BASE) // 2


def _swap(text, at, new):
    """`text` with the one character at `at` replaced by `new` (which differs from it)."""
    assert text[at] != new
    return text[:at] + new + text[at + 1:]


def _several_changes():
    out = BASE
    for k in range(1, 6):
        out = _swap(out, k * 600, "#")
    return out


def _many_changes():
    out = BASE
    for k in range(1, 13):
        out = _swap(out, k * 300, "#")
    return out


SHARED_HEAD = "\n".join(_lines(0, 45, "head"))
SHARED_TAIL = "\n".join(_lines(100, 130, "tail"))
TAIL_ONLY = "\n".join(_lines(50, 90))
# the preamble starts with a character the tail does not, so the one inserted span has a single placement
PREAMBLE = "preamble: the notes below were kept\nand a second preamble line\n"
ASTRAL_HEAD ="héllo \U0001F600 wörld \U0001F680 café\n"

# (id, sent, found): two normalized, differing bodies
DIFFERING = [
    ("start", BASE, "#" + BASE[1:]),
    ("end", BASE, BASE[:-1] + "#"),
    ("middle", BASE, _swap(BASE, MID, "#")),
    ("long-prefix-and-suffix-short-change", SHARED_HEAD + "\nOLD section here\n" + SHARED_TAIL,
     SHARED_HEAD + "\nNEW sect\n" + SHARED_TAIL),
    ("several-separate-changes", BASE, _several_changes()),
    ("more-changes-than-the-cap", BASE, _many_changes()),
    ("e2-sent-empty", "", BASE),
    ("e2-found-empty", BASE, ""),
    ("e3-sent-is-a-prefix", "\n".join(_lines(0, 40)), BASE),
    ("e3-found-is-a-prefix", BASE, "\n".join(_lines(0, 40))),
    ("e4-sent-is-a-suffix", TAIL_ONLY, PREAMBLE + TAIL_ONLY),
    ("e4-found-is-a-suffix", PREAMBLE + TAIL_ONLY, TAIL_ONLY),
    ("e7-aaa-aa", "aaa", "aa"),
    ("e7-aa-aaa", "aa", "aaa"),
    ("e8-non-ascii-and-astral-prefix", ASTRAL_HEAD + BASE, ASTRAL_HEAD + _swap(BASE, MID, "#")),
]


@pytest.mark.parametrize("a, b", [(a, b) for _, a, b in DIFFERING], ids=[i for i, _, _ in DIFFERING])
def test_trimmed_equals_untrimmed(a, b):
    assert a != b
    trimmed = cb._transit_changes(a, b, trim=True)
    assert trimmed == cb._transit_changes(a, b, trim=False)
    result = cb.transit_compare(a, b)
    assert result["transit"] == cb.TRANSIT_CHANGED
    assert (result["changeCount"], result["changes"]) == trimmed
    assert result["changeCount"] >= 1
    assert len(result["changes"]) == min(result["changeCount"], cb.TRANSIT_MAX_CHANGES)


def test_the_cap_case_really_exceeds_the_cap():
    count, changes = cb._transit_changes(BASE, _many_changes(), trim=True)
    assert count > cb.TRANSIT_MAX_CHANGES
    assert len(changes) == cb.TRANSIT_MAX_CHANGES


def test_a_change_names_its_line_position_and_excerpts_in_the_whole_body():
    found = _swap(BASE, MID, "#")
    result = cb.transit_compare(BASE, found)
    assert result["changeCount"] == 1
    change = result["changes"][0]
    assert change["at"] == MID
    assert change["line"] == BASE.count("\n", 0, MID) + 1
    assert change["line"] > 1
    assert change["sent"] == BASE[MID]
    assert change["found"] == "#"


def test_a_non_ascii_and_astral_prefix_shifts_by_python_string_indexes():
    a = ASTRAL_HEAD + BASE
    b = ASTRAL_HEAD + _swap(BASE, MID, "#")
    result = cb.transit_compare(a, b)
    change = result["changes"][0]
    assert change["at"] == len(ASTRAL_HEAD) + MID
    assert a[change["at"]] == change["sent"]
    assert change["line"] == a.count("\n", 0, change["at"]) + 1


def test_e7_overlap_case_reports_the_one_dropped_character():
    result = cb.transit_compare("aaa", "aa")
    assert result["changeCount"] == 1
    assert result["changes"] == [{"line": 1, "at": 2, "sent": "a", "found": ""}]
    swapped = cb.transit_compare("aa", "aaa")
    assert swapped["changeCount"] == 1
    assert swapped["changes"] == [{"line": 1, "at": 2, "sent": "", "found": "a"}]


def test_identical_and_normalization_only_differences_read_matched_and_never_trim(monkeypatch):
    calls = []
    real = cb._transit_changes

    def spy(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(cb, "_transit_changes", spy)
    assert cb.transit_compare(BASE, BASE) == {"transit": cb.TRANSIT_MATCHED}
    assert cb.transit_compare(BASE, BASE.replace("\n", "\r\n")) == {"transit": cb.TRANSIT_MATCHED}
    assert cb.transit_compare(BASE, BASE + "   \n\t\n") == {"transit": cb.TRANSIT_MATCHED}
    assert cb.transit_compare(BASE + "  \n", BASE) == {"transit": cb.TRANSIT_MATCHED}
    assert cb.transit_compare(BASE, BASE + "\n" + cb.CLOUD_FOOTER) == {"transit": cb.TRANSIT_MATCHED}
    assert cb.transit_compare("", "") == {"transit": cb.TRANSIT_MATCHED}
    assert calls == []


def test_a_difference_beyond_normalization_reaches_the_trimmed_comparison(monkeypatch):
    calls = []
    real = cb._transit_changes

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(cb, "_transit_changes", spy)
    found = _swap(BASE, MID, "#")
    assert cb.transit_compare(BASE.replace("\n", "\r\n") + "  ", found)["transit"] == cb.TRANSIT_CHANGED
    assert len(calls) == 1
    assert calls[0][0] == (BASE, found)
    assert calls[0][1] == {"trim": True}


def test_not_checked_returns_are_unchanged():
    assert cb.transit_compare(None, "x") == {"transit": cb.TRANSIT_NOT_CHECKED, "why": "the sent text could not be read"}
    assert cb.transit_compare("x", None) == {"transit": cb.TRANSIT_NOT_CHECKED, "why": "the text could not be read back"}
    assert cb.transit_compare(5, "x")["transit"] == cb.TRANSIT_NOT_CHECKED

    class Broken(str):
        def replace(self, *args, **kwargs):
            raise RuntimeError("boom")

    assert cb.transit_compare(Broken("x"), "y") == {"transit": cb.TRANSIT_NOT_CHECKED, "why": "the comparison failed"}


def _long_json_text():
    records = [{"id": i, "title": f"finding {i} of the long review", "where": f"src/mod_{i % 41}/file_{i % 7}.py:{i * 3 + 1}",
                "note": f"the value {(i * 7919) % 1009} was read as {(i * 104729) % 9973} instead of {(i * 31) % 97}"}
               for i in range(1100)]
    return json.dumps(records, separators=(",", ":"))


def test_a_full_size_part_with_one_changed_character_compares_fast():
    text = _long_json_text()
    part = rr._part_bodies(text)[0]
    assert len(part) >= 60000
    assert len(part) <= rr.MAX_BODY_CHARS
    at = len(part) // 2
    changed = _swap(part, at, "#" if part[at] != "#" else "%")
    started = time.monotonic()
    result = cb.transit_compare(part, changed)
    elapsed = time.monotonic() - started
    assert result["transit"] == cb.TRANSIT_CHANGED
    assert result["changeCount"] == 1
    change = result["changes"][0]
    assert change["at"] == at
    assert change["line"] == part.count("\n", 0, at) + 1
    assert change["line"] > 1
    assert change["sent"] == part[at]
    # axis: the elapsed bound is what fails when the trim is gone, because the untrimmed matcher takes far longer at this size — see bite-proof record wo_2490_transit_trim
    assert elapsed < 5, f"transit_compare took {elapsed:.1f}s on a {len(part)}-character part"


def _prefix_len(a, b):
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n


def _suffix_len(a, b, cap):
    n = 0
    while n < cap and a[len(a) - 1 - n] == b[len(b) - 1 - n]:
        n += 1
    return n


def _edit_script(a, b, trim):
    """Whole-string opcodes turning `a` into `b`: the matcher over the trimmed middle, shifted by the prefix length."""
    p = s = 0
    if trim:
        p = _prefix_len(a, b)
        s = _suffix_len(a, b, min(len(a), len(b)) - p)
    ops = [("equal", 0, p, 0, p)]
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a[p:len(a) - s], b[p:len(b) - s],
                                                       autojunk=False).get_opcodes():
        ops.append((tag, i1 + p, i2 + p, j1 + p, j2 + p))
    ops.append(("equal", len(a) - s, len(a), len(b) - s, len(b)))
    return ops


def _apply(a, b, ops):
    """The text the script builds from `a`: the span of `a` for an equal op, the span of `b` otherwise."""
    out, ai, bj = [], 0, 0
    for tag, i1, i2, j1, j2 in ops:
        assert (i1, j1) == (ai, bj), "the script leaves a gap or an overlap"
        out.append(a[i1:i2] if tag == "equal" else b[j1:j2])
        ai, bj = i2, j2
    assert (ai, bj) == (len(a), len(b)), "the script does not cover both strings"
    return "".join(out)


def test_trim_may_place_an_ambiguous_edit_elsewhere_but_counts_the_same():
    a, b = "AAAB", "AAAAB"
    trimmed = cb._transit_changes(a, b, trim=True)
    untrimmed = cb._transit_changes(a, b, trim=False)
    assert trimmed[0] == untrimmed[0] == 1
    # the known limit: the same edit, placed at a different offset
    assert [c["at"] for c in untrimmed[1]] == [0]
    assert [c["at"] for c in trimmed[1]] == [3]
    assert _apply(a, b, _edit_script(a, b, trim=True)) == b
    assert _apply(a, b, _edit_script(a, b, trim=False)) == b
    assert _edit_script(a, b, trim=True) != _edit_script(a, b, trim=False)
