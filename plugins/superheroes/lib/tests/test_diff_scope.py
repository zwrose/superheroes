"""Anchor-set parsing for the round diff (`diff_scope.parse_diff_lines`).

This is the hunk-walk `round_driver.mechanical_compile` drops findings against,
so a parse that under-reports anchorable lines silently drops real findings.
Covers what the deleted `test_resolve_diff_lines*.py` covered at the PARSE
level; the `--post` comment-relocation half those files also covered went away
with the mode (#1121).
"""
from diff_scope import parse_diff_lines


def test_added_and_context_lines_are_anchorable():
    diff = ("diff --git a/foo.ts b/foo.ts\n--- a/foo.ts\n+++ b/foo.ts\n"
            "@@ -1,3 +1,4 @@\n line1\n+line2\n line3\n line4\n")
    # context line1 -> 1, added line2 -> 2, context line3 -> 3, context line4 -> 4
    assert parse_diff_lines(diff)["foo.ts"] == {1, 2, 3, 4}


def test_new_file_all_plus_lines():
    diff = ("diff --git a/new.ts b/new.ts\n--- /dev/null\n+++ b/new.ts\n"
            "@@ -0,0 +1,3 @@\n+a\n+b\n+c\n")
    assert parse_diff_lines(diff)["new.ts"] == {1, 2, 3}


def test_deletion_lines_do_not_advance_the_new_file_counter():
    # A '-' line consumes no NEW-file line number. If it did, every anchor after
    # a deletion would be off by one and its finding dropped as out-of-scope.
    diff = ("diff --git a/foo.ts b/foo.ts\n--- a/foo.ts\n+++ b/foo.ts\n"
            "@@ -1,3 +1,2 @@\n line1\n-gone\n+kept\n")
    assert parse_diff_lines(diff)["foo.ts"] == {1, 2}


def test_multiple_hunks_each_restart_at_their_own_header():
    diff = ("diff --git a/foo.ts b/foo.ts\n--- a/foo.ts\n+++ b/foo.ts\n"
            "@@ -1,1 +1,2 @@\n line1\n+added2\n"
            "@@ -10,1 +11,2 @@\n line11\n+added12\n")
    assert parse_diff_lines(diff)["foo.ts"] == {1, 2, 11, 12}


def test_two_files_keep_separate_anchor_sets():
    diff = ("diff --git a/a.ts b/a.ts\n--- a/a.ts\n+++ b/a.ts\n"
            "@@ -1,0 +1,1 @@\n+a1\n"
            "diff --git a/b.ts b/b.ts\n--- a/b.ts\n+++ b/b.ts\n"
            "@@ -1,0 +5,1 @@\n+b5\n")
    valid = parse_diff_lines(diff)
    assert valid["a.ts"] == {1}
    assert valid["b.ts"] == {5}


def test_crlf_diff_does_not_corrupt_filename():
    # CRLF line endings must not leave a trailing \r in the parsed file path —
    # a finding citing "foo.ts" would otherwise match nothing and be dropped.
    diff = ("diff --git a/foo.ts b/foo.ts\r\n--- a/foo.ts\r\n+++ b/foo.ts\r\n"
            "@@ -1,3 +1,4 @@\r\n line1\r\n+line2\r\n line3\r\n line4\r\n")
    valid = parse_diff_lines(diff)
    assert "foo.ts" in valid          # NOT "foo.ts\r"
    assert "foo.ts\r" not in valid
    assert 2 in valid["foo.ts"]


def test_no_prefix_diff_is_unsupported_and_yields_no_anchors():
    # Documented limitation: '+++ foo.ts' (no b/ prefix) is not recognized, so
    # the file has no anchorable lines at all.
    diff = ("diff --git foo.ts foo.ts\n--- foo.ts\n+++ foo.ts\n"
            "@@ -1,1 +1,2 @@\n line1\n+line2")
    assert parse_diff_lines(diff) == {}


def test_dev_null_right_side_is_not_a_file():
    # A pure deletion has '+++ /dev/null' — no RIGHT-side file to anchor to.
    diff = ("diff --git a/gone.ts b/gone.ts\n--- a/gone.ts\n+++ /dev/null\n"
            "@@ -1,2 +0,0 @@\n-a\n-b\n")
    assert parse_diff_lines(diff) == {}


def test_empty_diff_has_no_anchors():
    assert parse_diff_lines("") == {}
