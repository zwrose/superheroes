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


# --- #422: wrapped bullets — full round trip + mixed-version healing ---------

WRAPPED_SPEC = ("## Definition of done\n\n"
                "- **Wrapped.** the net diff adds exactly one file with exactly\n"
                "  two lines below the seeded baseline.\n"
                "- **Short.** nothing else changes.\n\n## Next\n")


def test_wrapped_bullet_round_trips_seed_fill_decide():
    # the #422 claim itself: every consumer routes through the ONE parser, so a wrapped
    # bullet seeds, fills, and gates consistently. The filler proposal carries the raw
    # newline-embedded text a leaf reading the spec naturally would produce — the shared
    # cellsafe/_norm collapse must absorb it.
    bullets = dod_gate.parse_dod_bullets(WRAPPED_SPEC)
    assert len(bullets) == 2 and bullets[0].endswith("below the seeded baseline.")
    body = "Intro.\n\n" + pr_body.seed_dod_block(bullets) + "\nOutro."
    proposal = bullets[0].replace(" two lines", "\ntwo lines")
    new, filled, rejected, _ = dod_fill_cli.fill(
        body,
        [{"bullet": proposal, "disposition": "done", "detail": "gh pr diff: one file, two lines"},
         {"bullet": bullets[1], "disposition": "done", "detail": "gh pr diff --name-only: one path"}],
        "/nonexistent-root", _issue_exists=lambda n: False)
    assert filled == 2 and rejected == []
    verdict = dod_gate.decide(bullets, new, spec_present=True)
    assert verdict["verdict"] == "proceed"


def test_fill_heals_a_blank_truncated_row_from_a_pre_fold_seed():
    # mixed-version skew (#422 review finding): a table seeded by a PRE-fold spine carries
    # the wrapped bullet TRUNCATED at its first physical line. The fill may rewrite that
    # row's bullet cell only when it is provably safe: the row is still BLANK and exactly
    # one prefix candidate exists.
    truncated = "**Wrapped.** the net diff adds exactly one file with exactly"
    full = "**Wrapped.** the net diff adds exactly one file with exactly two lines below the seeded baseline."
    body = "Intro.\n\n" + pr_body.seed_dod_block([truncated, "**Short.** nothing else changes."]) + "\nOutro."
    new, filled, rejected, _ = dod_fill_cli.fill(
        body, [{"bullet": full, "disposition": "done", "detail": "gh pr diff: verified"}],
        "/nonexistent-root", _issue_exists=lambda n: False)
    assert filled == 1 and rejected == []
    # the healed row now carries the FULL bullet identity and gates cleanly against it
    rows = dod_gate._parse_table(new)
    row = dod_gate._match_row(full, rows)
    assert row is not None and row[1] == "done"
    assert len(new.split("\n")) == len(body.split("\n"))


def test_fill_never_heals_a_disposed_or_ambiguous_truncated_row():
    truncated = "**Wrapped.** the net diff adds exactly one file with exactly"
    full = "**Wrapped.** the net diff adds exactly one file with exactly two lines below the seeded baseline."
    # (a) the truncated row already carries a disposition -> data could be lost -> reject
    body = "Intro.\n\n" + pr_body.seed_dod_block([truncated]) + "\nOutro."
    disposed, filled, rejected, _ = dod_fill_cli.fill(
        body, [{"bullet": truncated, "disposition": "done", "detail": "earlier fill"}],
        "/nonexistent-root", _issue_exists=lambda n: False)
    assert filled == 1
    new, filled2, rejected2, _ = dod_fill_cli.fill(
        disposed, [{"bullet": full, "disposition": "done", "detail": "later fill"}],
        "/nonexistent-root", _issue_exists=lambda n: False)
    assert filled2 == 0 and rejected2 and rejected2[0]["reason"] == "no matching table row for this bullet"
    # (b) TWO blank prefix candidates -> ambiguous -> reject
    body2 = "Intro.\n\n" + pr_body.seed_dod_block(
        [truncated, "**Wrapped.** the net diff adds exactly one file"]) + "\nOutro."
    _, filled3, rejected3, _ = dod_fill_cli.fill(
        body2, [{"bullet": full, "disposition": "done", "detail": "x"}],
        "/nonexistent-root", _issue_exists=lambda n: False)
    assert filled3 == 0 and rejected3


def test_heal_with_wrong_bullet_text_still_parks_at_decide():
    # the load-bearing fail-closed direction: even if a leaf heals a blank truncated row
    # with FABRICATED text, decide() re-parses the spec and the real bullet now matches no
    # row -> park. A heal can corrupt cosmetics, never produce a false proceed.
    truncated = "**Wrapped.** the net diff adds exactly one file with exactly"
    spec = ("## Definition of done\n\n"
            "- **Wrapped.** the net diff adds exactly one file with exactly\n"
            "  two lines below the seeded baseline.\n\n## Next\n")
    bullets = dod_gate.parse_dod_bullets(spec)
    body = "Intro.\n\n" + pr_body.seed_dod_block([truncated]) + "\nOutro."
    fabricated = truncated + " nothing at all like the spec text"
    new, filled, rejected, _ = dod_fill_cli.fill(
        body, [{"bullet": fabricated, "disposition": "done", "detail": "made up"}],
        "/nonexistent-root", _issue_exists=lambda n: False)
    assert filled == 1  # the heal itself fires (blank row, word-boundary prefix)
    verdict = dod_gate.decide(bullets, new, spec_present=True)
    assert verdict["verdict"] == "park"


def test_heal_requires_word_boundary_prefix():
    # mid-word extension (the forgery shape) must NOT heal.
    body = "Intro.\n\n" + pr_body.seed_dod_block(["verify the exports"]) + "\nOutro."
    _, filled, rejected, _ = dod_fill_cli.fill(
        body, [{"bullet": "verify the exportservice too", "disposition": "done", "detail": "x"}],
        "/nonexistent-root", _issue_exists=lambda n: False)
    assert filled == 0 and rejected
