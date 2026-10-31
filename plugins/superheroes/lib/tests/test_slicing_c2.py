"""Tests for slicing (layer C2): the size slicer and the unread-share arithmetic. No git; diffs are built here."""
import re

import pytest

import countable_lines as cl
import slicing

BAR = cl.COUNTABLE_LINES_BAR
_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


# --------------------------------------------------------------------------------------------
# Diff builders
# --------------------------------------------------------------------------------------------

def _hunk(old_start, new_start, body):
    old = sum(1 for op, _ in body if op in " -")
    new = sum(1 for op, _ in body if op in " +")
    text = "@@ -%d,%d +%d,%d @@\n" % (old_start, old, new_start, new)
    return text + "".join("%s%s\n" % (op, line) for op, line in body)


def _added(path, n, start=1):
    return [("+", "%s line %d" % (path, start + i)) for i in range(n)]


def _new_file(path, n):
    head = "diff --git a/%s b/%s\nnew file mode 100644\nindex 0000000..2222222\n--- /dev/null\n+++ b/%s\n" % (path, path, path)
    return head + _hunk(0, 1, _added(path, n))


def _modify(path, *hunks):
    head = "diff --git a/%s b/%s\nindex 1111111..2222222 100644\n--- a/%s\n+++ b/%s\n" % (path, path, path, path)
    return head + "".join(hunks)


def _delete(path, n):
    head = "diff --git a/%s b/%s\ndeleted file mode 100644\nindex 1111111..0000000\n--- a/%s\n+++ /dev/null\n" % (path, path, path)
    body = [("-", "%s line %d" % (path, i + 1)) for i in range(n)]
    return head + _hunk(1, 0, body)


def _copy(path, source, *hunks):
    head = "diff --git a/%s b/%s\nsimilarity index 90%%\ncopy from %s\ncopy to %s\n" % (source, path, source, path)
    if hunks:
        head += "index 1111111..2222222 100644\n--- a/%s\n+++ b/%s\n" % (source, path)
    return head + "".join(hunks)


def _row(file, lines, counted=True, why=None):
    return {"file": file, "lines": lines, "counted": counted, "why": why}


def _cr(countable, rows, unsettled=()):
    return {"countable": countable, "bar": BAR, "files": list(rows), "unsettled": list(unsettled)}


def _counted_rows(diff):
    return [_row(s["file"], s["added"] + s["removed"]) for s in cl.parse_sections(diff)]


def _simple(diff):
    rows = _counted_rows(diff)
    return _cr(sum(r["lines"] for r in rows), rows)


# --------------------------------------------------------------------------------------------
# Checkers
# --------------------------------------------------------------------------------------------

def _assert_hunks_valid(diff):
    """Every hunk header's old and new counts match its body."""
    cur = None

    def finish():
        if cur is not None:
            assert (cur["old"], cur["new"]) == (cur["want_old"], cur["want_new"]), cur

    for line in diff.split("\n"):
        found = _HUNK.match(line)
        if found:
            finish()
            cur = {
                "want_old": 1 if found.group(2) is None else int(found.group(2)),
                "want_new": 1 if found.group(4) is None else int(found.group(4)),
                "old": 0,
                "new": 0,
            }
        elif line.startswith("diff --git "):
            finish()
            cur = None
        elif cur is not None and line:
            if line[0] in " -":
                cur["old"] += 1
            if line[0] in " +":
                cur["new"] += 1
    finish()


def _is_file_level(section):
    return section["unreadable"] or section["binary"] or section["status"] == "deleted" or not section["headLines"]


def _check_plan(pl, diff, proven=(), copies=None):
    """The five invariants of a sliced plan."""
    copies = copies or {}
    assert pl["sliced"] is True
    slices = pl["slices"]
    assert slices
    # 1. every slice weighs at most the bar
    assert all(s["weight"] <= BAR for s in slices), [s["weight"] for s in slices]
    # 2. the slice weights sum to the total weight
    assert sum(s["weight"] for s in slices) == pl["weight"]
    kept = cl.parse_sections(cl.reviewer_diff(diff, proven))
    seen = {}
    in_slices = {}
    for k, s in enumerate(slices):
        _assert_hunks_valid(s["diff"])
        for part in s["parts"]:
            in_slices.setdefault(part["file"], set()).add(k)
            for start, end in part["lines"]:
                for n in range(start, end + 1):
                    seen[(part["file"], n)] = seen.get((part["file"], n), 0) + 1
    for section in kept:
        file = section["file"]
        if file in copies:
            expected = set(range(1, copies[file] + 1))
        elif _is_file_level(section):
            # 4. a file-level section is in exactly one slice; one that alone outweighs the bar (weighed on raw
            # changed lines after an unreadable count) is cut by hunks, and the bar wins over "exactly one"
            if section["added"] + section["removed"] <= BAR:
                assert len(in_slices.get(file, ())) == 1, file
            else:
                assert in_slices.get(file), file
            continue
        else:
            expected = set(section["headLines"])
        # 3. every changed head line is in exactly one slice's parts
        for n in expected:
            assert seen.get((file, n)) == 1, (file, n, seen.get((file, n)))
    # 5. no proven copy is in any slice or slice diff
    proven_files = {p if isinstance(p, str) else p["file"] for p in proven}
    for s in slices:
        assert not proven_files & {p["file"] for p in s["parts"]}
        assert not proven_files & {sec["file"] for sec in cl.parse_sections(s["diff"])}


# --------------------------------------------------------------------------------------------
# Fixtures the partition invariant runs over
# --------------------------------------------------------------------------------------------

def _fx_folder():
    diff = "".join(_new_file("pkg/f%d.py" % i, 500) for i in range(6))
    return {"diff": diff, "cr": _simple(diff)}


def _fx_single_hunk():
    diff = _new_file("big.py", 2500)
    return {"diff": diff, "cr": _simple(diff)}


def _fx_deletion_heavy():
    ctx = [(" ", "ctx %d" % i) for i in range(3)]
    body = ctx + [("-", "old %d" % i) for i in range(1800)] + _added("new", 10) + ctx
    diff = _modify("del.py", _hunk(1, 1, body))
    return {"diff": diff, "cr": _simple(diff)}


def _fx_replacement():
    body = [("-", "old %d" % i) for i in range(700)] + _added("new", 700)
    diff = _modify("rep.py", _hunk(1, 1, body))
    return {"diff": diff, "cr": _simple(diff)}


def _fx_unsettled():
    diff = _modify("odd.bin.txt", _hunk(1, 1, [("-", "x")] + _added("odd", 1199)))
    cr = _cr(0, [_row("odd.bin.txt", 1200, False, "unsettled")], [{"file": "odd.bin.txt", "reason": "attribute-unreadable"}])
    return {"diff": diff, "cr": cr}


def _fx_no_count():
    diff = _new_file("a.py", 600) + _new_file("b.py", 600)
    return {"diff": diff, "cr": None}


def _fx_borderline():
    diff = _new_file("a.py", 600) + _new_file("b.py", 500)
    return {"diff": diff, "cr": _simple(diff)}


def _fx_proven_copy():
    diff = _new_file("vendor/copy.txt", 5000) + _new_file("src/a.py", 1100)
    cr = _cr(1100, [_row("vendor/copy.txt", 5000, False, "proven-copy"), _row("src/a.py", 1100)])
    return {"diff": diff, "cr": cr, "proven": ["vendor/copy.txt"]}


def _fx_lock_file():
    diff = _new_file("package-lock.json", 5000) + _new_file("src/a.py", 1100)
    cr = _cr(1100, [_row("package-lock.json", 5000, False, "lock-file"), _row("src/a.py", 1100)])
    return {"diff": diff, "cr": cr}


def _fx_copy_only():
    diff = _copy("copy.py", "src.py")
    return {"diff": diff, "cr": _cr(1200, [_row("copy.py", 1200)]), "copies": {"copy.py": 1200}}


def _fx_copy_with_hunks():
    hunk = _hunk(10, 10, [(" ", "c")] + _added("copy", 4) + [(" ", "c")])
    diff = _copy("copy.py", "src.py", hunk) + _new_file("other.py", 300)
    cr = _cr(1500, [_row("copy.py", 1200), _row("other.py", 300)])
    return {"diff": diff, "cr": cr, "copies": {"copy.py": 1200}}


def _fx_risk_deletion():
    diff = _delete("auth/secrets.py", 40) + _new_file("src/a.py", 1100)
    cr = _cr(1100, [_row("auth/secrets.py", 40, False, "deleted-whole"), _row("src/a.py", 1100)])
    return {"diff": diff, "cr": cr}


def _fx_deletion_unreadable_count():
    diff = _delete("old/big.py", 1500) + _new_file("a.py", 10)
    return {"diff": diff, "cr": {"countable": "many"}}


FIXTURES = [
    _fx_folder, _fx_single_hunk, _fx_deletion_heavy, _fx_replacement, _fx_unsettled, _fx_no_count,
    _fx_borderline, _fx_proven_copy, _fx_lock_file, _fx_copy_only, _fx_copy_with_hunks, _fx_risk_deletion,
    _fx_deletion_unreadable_count,
]


def _plan_of(fx):
    return slicing.plan(fx["diff"], fx["cr"], fx.get("proven", ()))


@pytest.mark.parametrize("make", FIXTURES, ids=lambda f: f.__name__)
def test_partition_invariants_hold_for_every_fixture(make):
    fx = make()
    _check_plan(_plan_of(fx), fx["diff"], fx.get("proven", ()), fx.get("copies"))


# --------------------------------------------------------------------------------------------
# plan: the trigger and the cutting
# --------------------------------------------------------------------------------------------

def test_three_thousand_lines_in_one_folder_are_sliced_under_the_bar():
    fx = _fx_folder()
    pl = _plan_of(fx)
    assert pl["sliced"] and pl["weight"] == pl["countable"] == 3000 and pl["bar"] == BAR
    assert len(pl["slices"]) > 1
    assert all(s["weight"] <= BAR for s in pl["slices"])
    assert [s["id"] for s in pl["slices"]] == ["s1", "s2", "s3"]


def test_exactly_the_bar_is_not_sliced_and_one_more_line_is():
    at_bar = _new_file("a.py", BAR)
    pl = slicing.plan(at_bar, _simple(at_bar))
    assert pl["sliced"] is False and pl["slices"] == [] and pl["weight"] == BAR
    over = _new_file("a.py", BAR + 1)
    pl = slicing.plan(over, _simple(over))
    assert pl["sliced"] is True and pl["weight"] == BAR + 1
    _check_plan(pl, over)


def test_a_single_huge_hunk_is_cut_into_runs_that_parse_back():
    fx = _fx_single_hunk()
    pl = _plan_of(fx)
    assert [s["weight"] for s in pl["slices"]] == [1000, 1000, 500]
    added = 0
    texts = []
    for s in pl["slices"]:
        _assert_hunks_valid(s["diff"])
        sections = cl.parse_sections(s["diff"])
        assert [sec["file"] for sec in sections] == ["big.py"]
        added += sections[0]["added"]
        texts += sections[0]["addedLines"]
    assert added == 2500
    assert texts == ["big.py line %d" % i for i in range(1, 2501)]
    starts = [int(_HUNK.search(s["diff"]).group(3)) for s in pl["slices"]]
    assert starts == [1, 1001, 2001]
    _check_plan(pl, fx["diff"])


def test_a_deletion_heavy_hunk_weighs_removed_lines_and_is_cut():
    fx = _fx_deletion_heavy()
    pl = _plan_of(fx)
    assert pl["weight"] == 1810 and pl["sliced"]
    assert len(pl["slices"]) >= 2 and all(s["weight"] <= BAR for s in pl["slices"])
    removed = sum(sec["removed"] for s in pl["slices"] for sec in cl.parse_sections(s["diff"]))
    assert removed == 1800
    _check_plan(pl, fx["diff"])


def test_a_replacement_hunk_is_cut_so_no_slice_exceeds_the_bar():
    fx = _fx_replacement()
    pl = _plan_of(fx)
    assert pl["weight"] == 1400 and all(s["weight"] <= BAR for s in pl["slices"])
    assert len(pl["slices"]) == 2
    _check_plan(pl, fx["diff"])


def test_unsettled_weight_triggers_slicing_even_with_zero_countable():
    fx = _fx_unsettled()
    assert fx["cr"]["countable"] == 0
    pl = _plan_of(fx)
    assert pl["sliced"] and pl["countable"] == 1200 == pl["weight"]
    assert all(s["weight"] <= BAR for s in pl["slices"])
    _check_plan(pl, fx["diff"])


@pytest.mark.parametrize("bad", [None, "nope", [], {}, {"countable": -1, "files": []}, {"countable": True, "files": []},
                                 {"countable": 5}, {"countable": 5, "files": "x"}, {"countable": 5, "files": [], "unsettled": 3}])
def test_an_unreadable_count_slices_on_raw_changed_lines(bad):
    diff = _new_file("a.py", 600) + _new_file("b.py", 600)
    pl = slicing.plan(diff, bad)
    assert pl["sliced"] and pl["countable"] == pl["weight"] == 1200
    _check_plan(pl, diff)


def test_borderline_packing_never_builds_a_slice_above_the_bar():
    fx = _fx_borderline()
    pl = _plan_of(fx)
    assert pl["sliced"]
    assert [s["weight"] for s in pl["slices"]] == [600, 500]
    assert [[p["file"] for p in s["parts"]] for s in pl["slices"]] == [["a.py"], ["b.py"]]


# --------------------------------------------------------------------------------------------
# plan: files that weigh nothing, copies
# --------------------------------------------------------------------------------------------

def test_a_proven_copy_is_in_no_slice_no_diff_no_unread_part_and_no_share():
    fx = _fx_proven_copy()
    pl = _plan_of(fx)
    assert pl["sliced"] and pl["countable"] == 1100
    _check_plan(pl, fx["diff"], fx["proven"])
    for s in pl["slices"]:
        assert "vendor/copy.txt" not in s["diff"]
        assert all(p["file"] != "vendor/copy.txt" for p in s["parts"])
    assigned = {"seat%d" % k: s["parts"] for k, s in enumerate(pl["slices"])}
    unread = slicing.unread_obligations(assigned, {})
    assert unread and all(o["file"] != "vendor/copy.txt" for o in unread)
    share = slicing.unread_share(unread, pl, fx["cr"])
    assert all(p["file"] != "vendor/copy.txt" for p in share["parts"])
    assert share["unreadLines"] == share["countableLines"] == 1100
    # proven given as a dict entry works the same
    again = slicing.plan(fx["diff"], fx["cr"], [{"file": "vendor/copy.txt", "source": "s", "sha256": "0" * 64}])
    assert again == pl
    assert all(s["id"].startswith("u") for s in slicing.slice_parts_for(
        [{"file": "vendor/copy.txt", "lines": [[1, 50]]}, {"file": "src/a.py", "lines": [[1, 50]]}], pl, fx["cr"]))
    got = slicing.slice_parts_for([{"file": "vendor/copy.txt", "lines": [[1, 50]]}], pl, fx["cr"])
    assert got == []


def test_a_lock_file_rides_in_a_slice_at_zero_weight_and_the_share_never_exceeds_the_count():
    fx = _fx_lock_file()
    pl = _plan_of(fx)
    _check_plan(pl, fx["diff"])
    holders = [s for s in pl["slices"] if any(p["file"] == "package-lock.json" for p in s["parts"])]
    assert len(holders) == 1
    assert "package-lock.json" in holders[0]["diff"]
    assert sum(s["weight"] for s in pl["slices"]) == 1100
    assigned = {"seat%d" % k: s["parts"] for k, s in enumerate(pl["slices"])}
    unread = slicing.unread_obligations(assigned, {})
    share = slicing.unread_share(unread, pl, fx["cr"])
    assert share["unreadLines"] == 1100 == share["countableLines"]
    assert any(p["file"] == "package-lock.json" for p in share["parts"])


def test_an_unproven_copy_only_change_owes_the_whole_head_file_in_chunks():
    fx = _fx_copy_only()
    pl = _plan_of(fx)
    assert pl["sliced"] and pl["weight"] == 1200
    assert [s["weight"] for s in pl["slices"]] == [1000, 200]
    assert [s["parts"] for s in pl["slices"]] == [
        [{"file": "copy.py", "lines": [[1, 1000]]}],
        [{"file": "copy.py", "lines": [[1001, 1200]]}],
    ]
    assert all("copy from src.py" in s["diff"] for s in pl["slices"])
    _check_plan(pl, fx["diff"], copies=fx["copies"])


def test_an_unproven_copy_with_differences_carries_its_diff_in_every_chunk():
    fx = _fx_copy_with_hunks()
    pl = _plan_of(fx)
    assert pl["weight"] == 1500
    _check_plan(pl, fx["diff"], copies=fx["copies"])
    chunk_slices = [s for s in pl["slices"] if any(p["file"] == "copy.py" for p in s["parts"])]
    assert len(chunk_slices) == 2
    assert all(s["diff"].count("+copy line 1\n") == 1 for s in chunk_slices)


# --------------------------------------------------------------------------------------------
# unread_obligations, merge_parts
# --------------------------------------------------------------------------------------------

def test_a_whole_file_deletion_is_a_file_level_part_met_by_any_entry_naming_it():
    fx = _fx_risk_deletion()
    pl = _plan_of(fx)
    _check_plan(pl, fx["diff"])
    holders = [s for s in pl["slices"] if any(p["file"] == "auth/secrets.py" for p in s["parts"])]
    assert len(holders) == 1
    assert {"file": "auth/secrets.py", "lines": []} in holders[0]["parts"]
    assigned = {"a": holders[0]["parts"], "b": holders[0]["parts"], "c": holders[0]["parts"]}
    reads = {
        "a": [{"file": "auth/secrets.py", "lines": [[1, 3]]}],
        "b": [{"file": "auth/secrets.py", "lines": []}],
        "c": [{"file": "src/a.py", "lines": [[1, 5000]]}],
    }
    got = slicing.unread_obligations(assigned, reads)
    assert [o for o in got if o["file"] == "auth/secrets.py"] == [{"seat": "c", "file": "auth/secrets.py", "lines": []}]


def test_each_seat_is_subtracted_against_its_own_read_list_only():
    parts = [{"file": "x.py", "lines": [[1, 100]]}, {"file": "y.py", "lines": [[5, 9]]}]
    got = slicing.unread_obligations({"code": parts, "test": parts}, {"code": [dict(p) for p in parts], "test": []})
    assert got == [
        {"seat": "test", "file": "x.py", "lines": [[1, 100]]},
        {"seat": "test", "file": "y.py", "lines": [[5, 9]]},
    ]


def test_a_partial_read_leaves_exactly_what_the_seat_did_not_read():
    parts = [{"file": "x.py", "lines": [[1, 100]]}]
    got = slicing.unread_obligations({"s": parts}, {"s": [{"file": "x.py", "lines": [[10, 20], [50, 60]]}]})
    assert got == [{"seat": "s", "file": "x.py", "lines": [[1, 9], [21, 49], [61, 100]]}]


@pytest.mark.parametrize("reads", [
    {},
    {"other": [{"file": "x.py", "lines": [[1, 100]]}]},
    {"s": "x.py"},
    {"s": None},
    {"s": {"file": "x.py", "lines": [[1, 100]]}},
    {"s": [None, 3, {"file": 5, "lines": [[1, 100]]}, {"file": "x.py", "lines": "all"}, {"file": "x.py", "lines": [[0, 5], [9, 3]]}]},
])
def test_a_missing_seat_a_non_list_or_malformed_entries_read_nothing(reads):
    got = slicing.unread_obligations({"s": [{"file": "x.py", "lines": [[1, 100]]}]}, reads)
    assert got == [{"seat": "s", "file": "x.py", "lines": [[1, 100]]}]
    assert slicing.unread_obligations({"s": [{"file": "x.py", "lines": [[1, 100]]}]}, None) == got


def test_merge_parts_keeps_first_seen_order_merges_ranges_and_keeps_file_level_only_when_alone():
    got = slicing.merge_parts([
        {"seat": "a", "file": "b.py", "lines": [[5, 9]]},
        {"seat": "a", "file": "a.py", "lines": []},
        {"seat": "b", "file": "b.py", "lines": [[1, 4], [20, 30]]},
        {"seat": "b", "file": "b.py", "lines": []},
        {"seat": "b", "file": "c.py", "lines": []},
        {"seat": "b", "file": "a.py", "lines": []},
        {"file": "", "lines": [[1, 2]]},
        "junk",
    ])
    assert got == [
        {"file": "b.py", "lines": [[1, 9], [20, 30]]},
        {"file": "a.py", "lines": []},
        {"file": "c.py", "lines": []},
    ]


# --------------------------------------------------------------------------------------------
# unread_share, slice_parts_for
# --------------------------------------------------------------------------------------------

def test_unread_share_counts_each_weighted_line_once_and_clamps_to_the_countable_lines():
    cr = _cr(100, [_row("a.py", 100), _row("gen.py", 900, False, "generated"), _row("old.py", 20, False, "deleted-whole")])
    pl = {"countable": 100}
    unread = [
        {"seat": "x", "file": "a.py", "lines": [[1, 60]]},
        {"seat": "y", "file": "a.py", "lines": [[40, 80]]},
        {"seat": "x", "file": "gen.py", "lines": [[1, 900]]},
        {"seat": "x", "file": "old.py", "lines": []},
    ]
    share = slicing.unread_share(unread, pl, cr)
    assert share["unreadLines"] == 80 and share["countableLines"] == 100
    assert [p["file"] for p in share["parts"]] == ["a.py", "gen.py", "old.py"]
    clamped = slicing.unread_share([{"file": "a.py", "lines": [[1, 500]]}], pl, cr)
    assert clamped["unreadLines"] == 100


def test_slice_parts_for_cuts_unread_ranges_into_u_slices_with_only_the_touching_hunks():
    first = _hunk(10, 10, [(" ", "c")] + _added("p", 300, 11) + [(" ", "c")])
    second = _hunk(5000, 5000, [(" ", "c")] + _added("q", 900, 5001) + [(" ", "c")])
    diff = _modify("big.py", first, second) + _new_file("lock.json", 700) + _new_file("auth.py", 300)
    cr = _cr(1500, [_row("big.py", 1200), _row("lock.json", 700, False, "lock-file"), _row("auth.py", 300)])
    pl = slicing.plan(diff, cr)
    _check_plan(pl, diff)
    unread = [
        {"file": "big.py", "lines": [[5001, 5100]]},
        {"file": "lock.json", "lines": [[1, 10]]},
        {"file": "auth.py", "lines": [[1, 300]]},
    ]
    got = slicing.slice_parts_for(unread, pl, cr)
    assert [s["id"] for s in got] == ["u1"]
    only = got[0]
    assert only["weight"] == 100 + 300
    assert "+q line 5001\n" in only["diff"] and "+p line 11\n" not in only["diff"]
    assert {"file": "lock.json", "lines": [[1, 10]]} in only["parts"]
    for s in got:
        _assert_hunks_valid(s["diff"])


def test_slice_parts_for_splits_a_wide_unread_range_into_slices_under_the_bar():
    fx = _fx_single_hunk()
    pl = _plan_of(fx)
    got = slicing.slice_parts_for([{"file": "big.py", "lines": [[1, 2500]]}], pl, fx["cr"])
    assert [s["id"] for s in got] == ["u1", "u2", "u3"]
    assert [s["weight"] for s in got] == [1000, 1000, 500]
    assert all(s["weight"] <= BAR for s in got)
    assert [s["parts"] for s in got] == [
        [{"file": "big.py", "lines": [[1, 1000]]}],
        [{"file": "big.py", "lines": [[1001, 2000]]}],
        [{"file": "big.py", "lines": [[2001, 2500]]}],
    ]
    for s in got:
        _assert_hunks_valid(s["diff"])


def test_slice_parts_for_gives_a_file_level_part_its_whole_section():
    fx = _fx_risk_deletion()
    pl = _plan_of(fx)
    got = slicing.slice_parts_for([{"file": "auth/secrets.py", "lines": []}], pl, fx["cr"])
    assert len(got) == 1 and got[0]["weight"] == 0
    assert got[0]["parts"] == [{"file": "auth/secrets.py", "lines": []}]
    original = cl.parse_sections(fx["diff"])[0]["text"]
    assert got[0]["diff"] == original


def test_slice_parts_for_charges_the_unread_lines_of_an_unproven_copy():
    fx = _fx_copy_only()
    pl = _plan_of(fx)
    got = slicing.slice_parts_for([{"file": "copy.py", "lines": [[1, 1200]]}], pl, fx["cr"])
    assert [s["weight"] for s in got] == [1000, 200]
    assert all("copy from src.py" in s["diff"] for s in got)


# --------------------------------------------------------------------------------------------
# Fail-closed on malformed input
# --------------------------------------------------------------------------------------------

def test_malformed_inputs_never_raise():
    assert slicing.plan(None, None) == {"sliced": False, "weight": 0, "countable": 0, "bar": BAR, "slices": []}
    assert slicing.plan(12, "x", 5)["slices"] == []
    assert slicing.unread_obligations(None, None) == []
    assert slicing.unread_obligations({"a": 5, "b": [None, {"file": ""}, {"file": 3}]}, 7) == []
    assert slicing.merge_parts(None) == []
    assert slicing.unread_share(None, None, None) == {"unreadLines": 0, "countableLines": 0, "parts": []}
    assert slicing.slice_parts_for(None, None, None) == []
    assert slicing.slice_parts_for([{"file": "a.py", "lines": [[1, 5]]}], {"slices": [None, {"diff": 4}]}, None) == []
