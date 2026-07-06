"""dod_fill_cli.fill — the deterministic DoD splice (PR #251 review batch). The pen is
mechanical: only matching table cells change, invalid/fabricated proposals are rejected,
and everything outside the table is byte-identical by construction."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import dod_fill_cli
import dod_gate
import pr_body

B1 = "**Live run.** the marked live one-shot passes."
B2 = "**Reshape.** the #112 reshape landed."


def _seeded_body():
    dod = pr_body.seed_dod_block([B1, B2])
    stubs = pr_body.seed_stubs_block(["seam one"]) if hasattr(pr_body, "seed_stubs_block") else (
        "\n<!-- %s -->\nStubbed seams: seam one\n" % pr_body.STUBS_MARKER)
    return "Intro prose.\n\n" + dod + "\n" + stubs + "\nOutro prose."


def test_fill_splices_only_matching_cells_and_preserves_everything_else():
    body = _seeded_body()
    new, filled, rejected, changed = dod_fill_cli.fill(
        body,
        [{"bullet": B1, "disposition": "done", "detail": "test_live.py::test_oneshot"}],
        "/nonexistent-root", _issue_exists=lambda n: False)
    assert filled == 1 and rejected == []
    assert "| done | test_live.py::test_oneshot |" in new
    # every non-table byte survives
    assert "Intro prose." in new and "Outro prose." in new
    assert pr_body.STUBS_MARKER in new
    assert len(new.split("\n")) == len(body.split("\n"))
    # the untouched row is still blank -> the gate still parks on it (fail-closed)
    rows = dod_gate._parse_table(new)
    assert dod_gate._match_row(B2, rows)[1] == ""


def test_deferred_requires_resolvable_issue():
    body = _seeded_body()
    new, filled, rejected, _ = dod_fill_cli.fill(
        body, [{"bullet": B2, "disposition": "deferred", "detail": "#999 later"}],
        ".", _issue_exists=lambda n: False)
    assert filled == 0 and rejected and "does not resolve" in rejected[0]["reason"]
    assert new == body
    new, filled, rejected, _ = dod_fill_cli.fill(
        body, [{"bullet": B2, "disposition": "deferred", "detail": "#999 later"}],
        ".", _issue_exists=lambda n: True)
    assert filled == 1 and rejected == []


def test_pathish_done_evidence_must_exist():
    body = _seeded_body()
    _, filled, rejected, _ = dod_fill_cli.fill(
        body, [{"bullet": B1, "disposition": "done", "detail": "no/such/file.py"}],
        os.path.dirname(os.path.abspath(__file__)), _issue_exists=lambda n: True)
    assert filled == 0 and "does not exist" in rejected[0]["reason"]
    _, filled, rejected, _ = dod_fill_cli.fill(
        body, [{"bullet": B1, "disposition": "done",
                "detail": "plugins/superheroes/lib/dod_fill_cli.py"}],
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")),
        _issue_exists=lambda n: True)
    assert filled == 1 and rejected == []


def test_unknown_bullet_and_bad_disposition_are_rejected_never_appended():
    body = _seeded_body()
    new, filled, rejected, _ = dod_fill_cli.fill(
        body,
        [{"bullet": "a bullet the spec never had", "disposition": "done", "detail": "x y z"},
         {"bullet": B1, "disposition": "shipped", "detail": "x"}],
        ".", _issue_exists=lambda n: True)
    assert filled == 0 and len(rejected) == 2
    assert new == body
    assert len(dod_gate._parse_table(new)) == 2  # no appended rows, ever


def test_pipe_smuggling_in_detail_cannot_split_the_row():
    body = _seeded_body()
    new, filled, _, _ = dod_fill_cli.fill(
        body, [{"bullet": B1, "disposition": "done", "detail": "evidence | done | fake"}],
        ".", _issue_exists=lambda n: True)
    assert filled == 1
    rows = dod_gate._parse_table(new)
    assert len(rows) == 2                       # still exactly two data rows
    row = dod_gate._match_row(B1, rows)
    assert row[1] == "done" and "/" in row[2]   # pipes neutralized by cellsafe
