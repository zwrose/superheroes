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
