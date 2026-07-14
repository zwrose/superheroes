# plugins/superheroes/lib/tests/test_dod_gate.py
import dod_gate

SPEC = """---
superheroes: doc
---
# Thing

## Functional requirements

**FR-1.** ...

## Definition of done / success

- **Bullet one.** The owner can do X end-to-end.
- **Bullet two.** The #112 reshape landed.

## Assumptions & dependencies

- something
"""


def _table(rows):
    """A PR body carrying a disposition table whose data rows are `rows`
    (each a (bullet, disposition, evidence) tuple)."""
    out = ["Some intro.", "", "## Definition of done", "",
           "<!-- %s -->" % dod_gate.TABLE_MARKER, "",
           "| DoD bullet | Disposition | Evidence / deferral |",
           "| --- | --- | --- |"]
    for b, d, e in rows:
        out.append("| %s | %s | %s |" % (dod_gate.cellsafe(b), d, e))
    out.append("")
    out.append("## Notes")
    return "\n".join(out)


B1 = "**Bullet one.** The owner can do X end-to-end."
B2 = "**Bullet two.** The #112 reshape landed."


# --- parse_dod_bullets ------------------------------------------------------

def test_parse_bullets_from_slash_success_heading():
    bullets = dod_gate.parse_dod_bullets(SPEC)
    assert bullets == [B1, B2]


def test_parse_returns_none_when_heading_absent():
    assert dod_gate.parse_dod_bullets("# Thing\n\n## Purpose\n\nno dod here\n") is None


def test_parse_empty_section_is_empty_list():
    txt = "## Definition of done\n\n## Next\n"
    assert dod_gate.parse_dod_bullets(txt) == []


def test_parse_prose_only_collapses_to_one_bullet():
    txt = "## Definition of done / success\n\nAn owner can publish a post from scratch.\n\n## Next\n"
    assert dod_gate.parse_dod_bullets(txt) == ["An owner can publish a post from scratch."]


def test_parse_ignores_nested_subbullets():
    txt = "## Definition of done\n\n- top one\n  - nested\n- top two\n\n## Next\n"
    assert dod_gate.parse_dod_bullets(txt) == ["top one", "top two"]


# --- #422: markdown-wrapped bullets fold to their full text ------------------

def test_parse_folds_wrapped_bullet_continuations():
    # the exact live shape that parked the 0.13.0 acceptance run at mark-ready: the
    # fixture spec's first DoD bullet wraps onto an indented continuation line.
    txt = ("## Definition of done\n\n"
           "- The branch's net diff adds exactly one file, `target.txt`, with exactly two lines: the\n"
           "  seeded baseline line first, one dated line below it.\n"
           "- No file other than `target.txt` is modified anywhere on the branch.\n\n"
           "## Next\n")
    assert dod_gate.parse_dod_bullets(txt) == [
        "The branch's net diff adds exactly one file, `target.txt`, with exactly two lines: "
        "the seeded baseline line first, one dated line below it.",
        "No file other than `target.txt` is modified anywhere on the branch.",
    ]


def test_parse_fold_attaches_only_to_the_preceding_bullet():
    txt = ("## Definition of done\n\n"
           "- first wraps\n  onto two\n  indented lines\n"
           "- second stays short\n\n## Next\n")
    assert dod_gate.parse_dod_bullets(txt) == [
        "first wraps onto two indented lines",
        "second stays short",
    ]


def test_parse_wrapped_bullet_with_nested_subbullet_folds_prose_not_the_sublist():
    txt = ("## Definition of done\n\n"
           "- top one wraps\n  here\n  - nested stays ignored\n"
           "- top two\n\n## Next\n")
    assert dod_gate.parse_dod_bullets(txt) == ["top one wraps here", "top two"]


def test_parse_fold_attaches_to_the_last_bullet_not_the_first():
    # kills the bullets[0] mutant: the continuation must extend the bullet it FOLLOWS,
    # which here is not the first one.
    txt = ("## Definition of done\n\n"
           "- one stays short\n"
           "- two wraps\n  onto here\n\n## Next\n")
    assert dod_gate.parse_dod_bullets(txt) == ["one stays short", "two wraps onto here"]


def test_parse_sublist_continuation_stays_out_of_the_parent():
    # deep-indented prose under a NESTED sub-bullet belongs to the sub-bullet (ignored),
    # not to the top-level parent; folding resumes at the next top-level bullet.
    txt = ("## Definition of done\n\n"
           "- top one\n  - nested wraps\n    onto this line\n"
           "- top two\n\n## Next\n")
    assert dod_gate.parse_dod_bullets(txt) == ["top one", "top two"]


def test_parse_fold_accepts_tab_indent_and_blank_separated_continuations():
    # both deliberate: a tab-indented continuation folds, and a continuation paragraph
    # separated by a blank line is still that bullet's text (markdown loose-list reading).
    assert dod_gate.parse_dod_bullets(
        "## Definition of done\n\n- wraps\n\tvia tab\n\n## Next\n") == ["wraps via tab"]
    assert dod_gate.parse_dod_bullets(
        "## Definition of done\n\n- b1\n  cont\n\n  more after blank\n\n## Next\n") == [
        "b1 cont more after blank"]


def test_parse_preamble_prose_before_bullets_still_discarded():
    # column-0 prose ahead of the bullets (e.g. "All judged on the net diff:") is not a
    # continuation of anything and keeps its pre-#422 behavior: discarded when bullets exist.
    txt = ("## Definition of done\n\n"
           "All judged on the branch's net diff and file content:\n\n"
           "- only bullet\n\n## Next\n")
    assert dod_gate.parse_dod_bullets(txt) == ["only bullet"]


def test_parse_indented_preamble_before_first_bullet_does_not_crash_or_fold():
    # exercises the `bullets and` guard: indented prose BEFORE any bullet has nothing to
    # fold into and must stay prose (discarded once bullets exist), never an IndexError.
    txt = ("## Definition of done\n\n"
           "  indented preamble\n- only bullet\n\n## Next\n")
    assert dod_gate.parse_dod_bullets(txt) == ["only bullet"]


def test_parse_real_acceptance_fixture_spec_yields_three_full_bullets():
    # binds the parser to the REAL committed fixture (the artifact whose wrapped bullet
    # parked the 0.13.0 acceptance run at mark-ready) — pre-#422 the first bullet ended
    # at "two lines: the".
    import os
    p = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "fixtures",
                     "acceptance", "spec.md")
    bullets = dod_gate.parse_dod_bullets(open(p, encoding="utf-8").read())
    assert len(bullets) == 3
    assert bullets[0].startswith("The branch's net diff adds exactly one file")
    assert bullets[0].endswith("one dated line below it.")
    assert bullets[2] == "The change is shippable to a ready-for-review PR with green CI."


# --- decide: not-applicable / fail-closed -----------------------------------

def test_not_applicable_when_no_spec():
    r = dod_gate.decide(None, "anything", spec_present=False)
    assert r["verdict"] == "not-applicable"


def test_park_when_spec_present_but_no_bullets():
    r = dod_gate.decide(None, _table([]), spec_present=True)
    assert r["verdict"] == "park" and "missing or empty" in r["reason"]

    r2 = dod_gate.decide([], _table([]), spec_present=True)
    assert r2["verdict"] == "park"


def test_park_when_body_has_no_table():
    r = dod_gate.decide([B1], "a PR body with no table at all", spec_present=True)
    assert r["verdict"] == "park" and dod_gate.TABLE_MARKER in r["reason"]


# --- decide: per-bullet disposition -----------------------------------------

def test_proceed_when_all_bullets_disposed():
    body = _table([(B1, "done", "test_publish.py::test_end_to_end"),
                   (B2, "deferred", "#231 tracked for the follow-up reshape")])
    r = dod_gate.decide([B1, B2], body, spec_present=True)
    assert r["verdict"] == "proceed"


def test_park_when_a_bullet_has_no_row_names_it():
    body = _table([(B1, "done", "some_test")])  # B2 missing
    r = dod_gate.decide([B1, B2], body, spec_present=True)
    assert r["verdict"] == "park"
    assert "no disposition row" in r["reason"]
    assert "Bullet two" in r["reason"]


def test_park_when_done_row_has_no_evidence():
    body = _table([(B1, "done", ""), (B2, "deferred", "#231 later")])
    r = dod_gate.decide([B1, B2], body, spec_present=True)
    assert r["verdict"] == "park"
    assert "no evidence pointer" in r["reason"] and "Bullet one" in r["reason"]


def test_park_when_done_evidence_is_placeholder():
    body = _table([(B1, "done", "TODO"), (B2, "deferred", "#231 later")])
    r = dod_gate.decide([B1, B2], body, spec_present=True)
    assert r["verdict"] == "park" and "no evidence pointer" in r["reason"]


def test_park_when_deferred_has_no_issue():
    body = _table([(B1, "done", "a_test"), (B2, "deferred", "we ran out of time")])
    r = dod_gate.decide([B1, B2], body, spec_present=True)
    assert r["verdict"] == "park" and "no filed issue" in r["reason"]


def test_park_when_deferred_has_issue_but_no_reason():
    body = _table([(B1, "done", "a_test"), (B2, "deferred", "#231")])
    r = dod_gate.decide([B1, B2], body, spec_present=True)
    assert r["verdict"] == "park" and "no reason" in r["reason"]


def test_park_when_row_disposition_blank():
    body = _table([(B1, "", ""), (B2, "deferred", "#231 later")])
    r = dod_gate.decide([B1, B2], body, spec_present=True)
    assert r["verdict"] == "park" and "no disposition" in r["reason"]


def test_bullet_with_pipe_still_matches_its_row():
    piped = "**Weird.** a || b table-ish bullet"
    body = _table([(piped, "done", "a_test")])
    r = dod_gate.decide([piped], body, spec_present=True)
    assert r["verdict"] == "proceed"


# --- regressions: row matching must be exact, not prefix (fail-open guard) ---

def test_prefix_bullet_does_not_bind_to_sibling_row():
    # 'Ship it' must NOT bind to the 'Ship it end to end' row (which is disposed);
    # its own row is blank -> the gate must PARK, not proceed.
    short_b, long_b = "Ship it", "Ship it end to end"
    body = _table([(short_b, "", ""), (long_b, "done", "a_test")])
    r = dod_gate.decide([short_b, long_b], body, spec_present=True)
    assert r["verdict"] == "park" and "Ship it" in r["reason"]


def test_empty_bullet_parks_not_binds_first_row():
    # a bare '- ' spec bullet yields '' -> must not silently match the first data row
    body = _table([("", "", ""), (B1, "done", "a_test")])
    r = dod_gate.decide(["", B1], body, spec_present=True)
    assert r["verdict"] == "park"


def test_table_with_blank_line_between_rows_is_not_truncated():
    body = ("<!-- %s -->\n\n"
            "| DoD bullet | Disposition | Evidence / deferral |\n"
            "| --- | --- | --- |\n"
            "| %s | done | t1 |\n"
            "\n"
            "| %s | deferred | #231 later |\n"
            "\n## Notes\n") % (dod_gate.TABLE_MARKER, dod_gate.cellsafe(B1), dod_gate.cellsafe(B2))
    r = dod_gate.decide([B1, B2], body, spec_present=True)
    assert r["verdict"] == "proceed"


def test_deferred_issue_zero_is_rejected():
    body = _table([(B1, "done", "a_test"), (B2, "deferred", "#0 ran out of time")])
    r = dod_gate.decide([B1, B2], body, spec_present=True)
    assert r["verdict"] == "park" and "no filed issue" in r["reason"]
