from delta_surface import (
    parse_hunks, fixed_locations, split_fix_surface, shard_plan, _overlaps,
    DEFAULT_SHARD_MAX_LINES, DEFAULT_SHARD_MAX_FILES,
)


def _file_diff(path, hunks_body):
    return "\n".join([
        "diff --git a/%s b/%s" % (path, path),
        "index 1111111..2222222 100644",
        "--- a/%s" % path,
        "+++ b/%s" % path,
        hunks_body,
    ])


def mk_diff(sections):
    return "\n".join(_file_diff(p, body) for p, body in sections) + "\n"


# --- parse_hunks --------------------------------------------------------------

def test_parse_single_hunk_new_range():
    diff = mk_diff([("f.py", "@@ -1,2 +1,3 @@\n ctx\n+added\n ctx2")])
    hunks = parse_hunks(diff)
    assert list(hunks) == ["f.py"]
    assert hunks["f.py"] == [{"start": 1, "end": 3, "text": "@@ -1,2 +1,3 @@\n ctx\n+added\n ctx2"}]


def test_parse_multi_hunk_multi_file():
    diff = mk_diff([
        ("a.py", "@@ -1 +1 @@\n-x\n+y\n@@ -10,0 +20,2 @@\n+p\n+q"),
        ("b.py", "@@ -5,1 +5,1 @@\n-m\n+n"),
    ])
    hunks = parse_hunks(diff)
    assert [h["start"] for h in hunks["a.py"]] == [1, 20]
    assert [h["end"] for h in hunks["a.py"]] == [1, 21]
    assert hunks["b.py"][0] == {"start": 5, "end": 5, "text": "@@ -5,1 +5,1 @@\n-m\n+n"}


def test_parse_hunk_default_count_is_one():
    diff = mk_diff([("f.py", "@@ -3 +7 @@\n-a\n+b")])
    assert parse_hunks(diff)["f.py"][0] == {"start": 7, "end": 7, "text": "@@ -3 +7 @@\n-a\n+b"}


def test_parse_rename_returns_none():
    diff = "\n".join([
        "diff --git a/old.py b/new.py",
        "rename from old.py",
        "rename to new.py",
        "@@ -1 +1 @@",
        "+x",
    ])
    assert parse_hunks(diff) is None


def test_parse_quoted_path_returns_none():
    diff = 'diff --git "a/x y.py" "b/x y.py"\n@@ -1 +1 @@\n+z\n'
    assert parse_hunks(diff) is None


def test_parse_binary_returns_none():
    diff = "diff --git a/i.png b/i.png\nBinary files a/i.png and b/i.png differ\n"
    assert parse_hunks(diff) is None


def test_parse_git_binary_patch_returns_none():
    diff = "diff --git a/i.bin b/i.bin\nGIT binary patch\nliteral 4\n"
    assert parse_hunks(diff) is None


def test_parse_garbage_hunk_header_returns_none():
    diff = "diff --git a/f.py b/f.py\n@@ this is not a hunk header @@\n+x\n"
    assert parse_hunks(diff) is None


def test_parse_zero_count_new_side_hunk_is_zero_width_point():
    """#507 R3: a pure-deletion hunk `+c,0` has no new-side lines. It must be the zero-width
    point (c, c), never the inverted range (c, c-1) that `start + count - 1` would produce."""
    diff = mk_diff([("f.py", "@@ -40,3 +40,0 @@\n-a\n-b\n-c")])
    hunk = parse_hunks(diff)["f.py"][0]
    assert hunk["start"] == 40 and hunk["end"] == 40
    assert hunk["end"] >= hunk["start"]  # well-formed, never inverted


def test_overlaps_pure_deletion_hunk():
    """A pure-deletion hunk (zero-width point) overlaps a fixed range that contains its point and
    does NOT overlap one that misses it — so a deletion over a fixed line is audited, not lost."""
    over = parse_hunks(mk_diff([("f.py", "@@ -100,2 +100,0 @@\n-a\n-b")]))["f.py"][0]
    assert _overlaps(over, [(90, 110)]) is True   # deletion point 100 lands inside the fix window
    assert _overlaps(over, [(90, 99)]) is False   # window ends before the deletion point
    assert _overlaps(over, [(101, 110)]) is False  # window starts after the deletion point


# --- fixed_locations ----------------------------------------------------------

def test_fixed_locations_margin():
    locs = fixed_locations([{"file": "f.py", "line": 100}], margin=10)
    assert locs == {"f.py": [(90, 110)]}


def test_fixed_locations_skips_malformed_entries():
    locs = fixed_locations([{"file": "f.py", "line": "nope"}, {"line": 3}, "junk",
                            {"file": "g.py", "line": 5}])
    assert locs == {"g.py": [(-5, 15)]}


# --- split_fix_surface: overlap partition -------------------------------------

def test_split_partitions_audit_vs_new_surface():
    reviewed = mk_diff([("f.py", "@@ -1 +1 @@\n-old\n+new")])
    # head diff for f.py changed: the fix site near line 100 + a NEW hunk near line 300
    head = mk_diff([("f.py", "@@ -1,1 +100,1 @@\n-old\n+fixed\n@@ -200,0 +300,2 @@\n+brand\n+new")])
    fix_batch = [{"file": "f.py", "line": 100, "title": "t", "severity": "Important"}]
    out = split_fix_surface(reviewed, head, fix_batch)
    assert out["unknown"] is False
    assert [h["start"] for h in out["auditTargets"]["f.py"]] == [100]
    assert [h["start"] for h in out["newSurface"]["f.py"]] == [300]


def test_split_boundary_exactly_plus_ten_overlaps():
    reviewed = mk_diff([("f.py", "@@ -1 +1 @@\n-x\n+a")])
    # fixed line 100 → [90,110]; a hunk ending exactly at 90 overlaps, one before does not
    head = mk_diff([("f.py", "@@ -80,1 +80,11 @@\n" + "\n".join("+l%d" % i for i in range(11)))])
    # hunk start 80, count 11 -> end 90 == lower bound -> overlaps
    fix_batch = [{"file": "f.py", "line": 100, "title": "t", "severity": "Important"}]
    out = split_fix_surface(reviewed, head, fix_batch)
    assert "f.py" in out["auditTargets"]
    assert out["newSurface"] == {}


def test_split_boundary_just_below_is_new_surface():
    reviewed = mk_diff([("f.py", "@@ -1 +1 @@\n-x\n+a")])
    # hunk 80..89 (count 10) -> end 89 < 90 lower bound -> NOT overlapping
    head = mk_diff([("f.py", "@@ -80,1 +80,10 @@\n" + "\n".join("+l%d" % i for i in range(10)))])
    fix_batch = [{"file": "f.py", "line": 100, "title": "t", "severity": "Important"}]
    out = split_fix_surface(reviewed, head, fix_batch)
    assert out["auditTargets"] == {}
    assert [h["start"] for h in out["newSurface"]["f.py"]] == [80]


def test_split_unchanged_file_is_ignored():
    same = mk_diff([("f.py", "@@ -1 +100,1 @@\n-old\n+fixed")])
    fix_batch = [{"file": "f.py", "line": 100, "title": "t", "severity": "Important"}]
    out = split_fix_surface(same, same, fix_batch)
    assert out == {"auditTargets": {}, "newSurface": {}, "unknown": False}


def test_split_new_file_touched_only_in_head():
    reviewed = mk_diff([("f.py", "@@ -1 +1 @@\n-x\n+y")])
    head = mk_diff([("f.py", "@@ -1 +1 @@\n-x\n+y"),
                    ("g.py", "@@ -0,0 +1,2 @@\n+new\n+file")])
    fix_batch = [{"file": "f.py", "line": 5, "title": "t", "severity": "Important"}]
    out = split_fix_surface(reviewed, head, fix_batch)
    # f.py unchanged between the two diffs; g.py is brand-new surface with no fix over it
    assert out["auditTargets"] == {}
    assert [h["start"] for h in out["newSurface"]["g.py"]] == [1]


# --- split_fix_surface: file removal → fail-closed into new surface -----------

def test_split_file_removed_between_reviewed_and_head_is_new_surface():
    """#507 R2 v0: a file present in the reviewed diff but ABSENT from the head diff was removed
    (or fully reverted) by the fix. It has no head hunks, so it would otherwise vanish from BOTH
    surfaces and escape audit AND scoped review. It fails closed into `newSurface` as a removal
    marker the scoped finder must scan — a deleted guard is never invisible."""
    reviewed = mk_diff([("evil.py", "@@ -1,2 +1,2 @@\n-a\n+b"),
                        ("fixed.py", "@@ -1 +100,1 @@\n-old\n+new")])
    # head: evil.py gone; only the audited hunk over fixed.py line 100 remains
    head = mk_diff([("fixed.py", "@@ -1 +100,1 @@\n-old\n+patched")])
    fix_batch = [{"file": "fixed.py", "line": 100, "title": "t", "severity": "Important"}]
    out = split_fix_surface(reviewed, head, fix_batch)
    assert out["unknown"] is False
    # the audited hunk stays an audit target
    assert [h["start"] for h in out["auditTargets"]["fixed.py"]] == [100]
    # the removed file rides new surface (non-empty → the driver dispatches the scoped finder)
    assert "evil.py" in out["newSurface"]
    assert out["newSurface"]["evil.py"][0]["removed"] is True


def test_split_file_removed_when_only_non_overlap_change():
    """The regression exactly: the ONLY non-overlap change is a whole-file removal. `newSurface`
    must be non-empty so the driver never skips the scoped finder over the vanished path."""
    reviewed = mk_diff([("evil.py", "@@ -1,2 +1,2 @@\n-a\n+b"),
                        ("fixed.py", "@@ -1 +100,1 @@\n-old\n+new")])
    head = mk_diff([("fixed.py", "@@ -1 +100,1 @@\n-old\n+patched")])
    fix_batch = [{"file": "fixed.py", "line": 100, "title": "t", "severity": "Important"}]
    out = split_fix_surface(reviewed, head, fix_batch)
    assert out["newSurface"], "a whole-file removal must never leave an empty new surface"


# --- split_fix_surface: fail-closed unknown -----------------------------------

def test_split_unknown_on_bad_reviewed_diff():
    head = mk_diff([("f.py", "@@ -1 +1 @@\n+x")])
    fix_batch = [{"file": "f.py", "line": 1, "title": "t", "severity": "Important"}]
    out = split_fix_surface("diff --git a/old b/new\n@@ -1 +1 @@\n+x", head, fix_batch)
    assert out == {"auditTargets": {}, "newSurface": {}, "unknown": True}


def test_split_unknown_on_binary_head_diff():
    reviewed = mk_diff([("f.py", "@@ -1 +1 @@\n+x")])
    head = "diff --git a/i.png b/i.png\nBinary files a/i.png and b/i.png differ\n"
    fix_batch = [{"file": "f.py", "line": 1, "title": "t", "severity": "Important"}]
    assert split_fix_surface(reviewed, head, fix_batch)["unknown"] is True


def test_split_unknown_on_empty_fix_batch():
    d = mk_diff([("f.py", "@@ -1 +1 @@\n+x")])
    assert split_fix_surface(d, d, [])["unknown"] is True


def test_split_unknown_on_fix_batch_missing_file_or_line():
    d = mk_diff([("f.py", "@@ -1 +1 @@\n+x")])
    for bad in ([{"line": 5}], [{"file": "f.py"}], [{"file": "f.py", "line": "x"}], "nope"):
        assert split_fix_surface(d, d, bad)["unknown"] is True


def test_split_unknown_on_garbage():
    out = split_fix_surface("total garbage", "more garbage",
                            [{"file": "f.py", "line": 1, "title": "t", "severity": "Important"}])
    # neither diff has a `diff --git` header -> both parse to {} (parseable-but-empty), and no
    # file is changed; unknown stays False (a genuinely empty pair is not the fail-closed case)
    assert out["unknown"] is False
    assert out["auditTargets"] == {} and out["newSurface"] == {}


# --- shard_plan ---------------------------------------------------------------

def _n_line_diff(path, n_added):
    body = "@@ -1 +1,%d @@\n" % n_added + "\n".join("+l%d" % i for i in range(n_added))
    return _file_diff(path, body)


def test_shard_not_big_under_thresholds():
    diff = _n_line_diff("plugins/x.py", 10) + "\n"
    plan = shard_plan(diff)
    assert plan["big"] is False
    assert plan["changedLines"] == 10
    assert plan["changedFiles"] == 1
    assert plan["thresholds"] == {"maxLines": DEFAULT_SHARD_MAX_LINES,
                                  "maxFiles": DEFAULT_SHARD_MAX_FILES}


def test_shard_lines_at_boundary_not_big():
    diff = _n_line_diff("plugins/x.py", 100) + "\n"
    assert shard_plan(diff, max_lines=100)["big"] is False


def test_shard_lines_over_boundary_big():
    diff = _n_line_diff("plugins/x.py", 101) + "\n"
    plan = shard_plan(diff, max_lines=100)
    assert plan["big"] is True
    assert plan["changedLines"] == 101


def test_shard_files_at_and_over_boundary():
    at = mk_diff([("plugins/f%d.py" % i, "@@ -1 +1 @@\n+x") for i in range(3)])
    assert shard_plan(at, max_files=3)["big"] is False
    over = mk_diff([("plugins/f%d.py" % i, "@@ -1 +1 @@\n+x") for i in range(4)])
    assert shard_plan(over, max_files=3)["big"] is True


def test_shard_groups_by_top_segment_deterministic():
    diff = mk_diff([
        ("plugins/superheroes/lib/a.py", "@@ -1 +1 @@\n+x"),
        ("eval/lib/b.py", "@@ -1 +1 @@\n+x"),
        (".github/workflows/ci.yml", "@@ -1 +1 @@\n+x"),
        ("README.md", "@@ -1 +1 @@\n+x"),
        ("plugins/superheroes/lib/c.py", "@@ -1 +1 @@\n+x"),
    ])
    plan = shard_plan(diff)
    keys = [s["key"] for s in plan["shards"]]
    assert keys == sorted(keys)
    assert keys == [".", ".github", "eval", "plugins"]
    plugins_shard = next(s for s in plan["shards"] if s["key"] == "plugins")
    assert plugins_shard["files"] == ["plugins/superheroes/lib/a.py",
                                      "plugins/superheroes/lib/c.py"]
    root_shard = next(s for s in plan["shards"] if s["key"] == ".")
    assert root_shard["files"] == ["README.md"]


def test_shard_unparseable_diff_is_big_and_unknown():
    plan = shard_plan('diff --git "a/x y" "b/x y"\n@@ -1 +1 @@\n+z\n')
    assert plan == {"big": True, "shards": [], "unknown": True}


def test_shard_rename_form_is_big_and_unknown():
    """#507 R3: `_scan_diff` must fail closed on a rename form (differing a/ b/ paths or a
    `rename from`/`rename to` marker) exactly as `parse_hunks` does — otherwise an oversized
    rename diff scans as a small parseable surface and skips the fan-out."""
    rename = "\n".join([
        "diff --git a/old.py b/new.py",
        "rename from old.py",
        "rename to new.py",
        "@@ -1 +1 @@",
        "+x",
    ]) + "\n"
    assert shard_plan(rename) == {"big": True, "shards": [], "unknown": True}


def test_shard_binary_marker_is_big_and_unknown():
    """#507 R3: a binary marker fails closed to the fan-out verdict, mirroring `parse_hunks`."""
    binary = "diff --git a/i.png b/i.png\nBinary files a/i.png and b/i.png differ\n"
    assert shard_plan(binary) == {"big": True, "shards": [], "unknown": True}
    git_binary = "diff --git a/i.bin b/i.bin\nGIT binary patch\nliteral 4\n"
    assert shard_plan(git_binary) == {"big": True, "shards": [], "unknown": True}


def test_split_unknown_on_rename_head_diff():
    """The same rename form makes `split_fix_surface` fail closed to an unknown surface — the two
    consumers of the diff never disagree about whether it is parseable."""
    reviewed = mk_diff([("f.py", "@@ -1 +1 @@\n+x")])
    head = "\n".join([
        "diff --git a/old.py b/new.py",
        "rename from old.py",
        "rename to new.py",
        "@@ -1 +1 @@",
        "+x",
    ]) + "\n"
    fix_batch = [{"file": "f.py", "line": 1, "title": "t", "severity": "Important"}]
    assert split_fix_surface(reviewed, head, fix_batch)["unknown"] is True
