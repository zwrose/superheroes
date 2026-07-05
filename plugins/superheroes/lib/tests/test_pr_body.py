# plugins/superheroes/lib/tests/test_pr_body.py
import dod_gate
import pr_body
import stub_markers

BULLETS = ["**One.** owner can do X", "**Two.** #112 reshape landed"]


def test_seed_dod_block_has_marker_and_one_row_per_bullet():
    block = pr_body.seed_dod_block(BULLETS)
    assert dod_gate.TABLE_MARKER in block
    # one data row per bullet (blank disposition + evidence)
    rows = [ln for ln in block.split("\n") if ln.startswith("| ") and "---" not in ln]
    # header + 2 data rows
    assert len(rows) == 3
    assert "| **One.** owner can do X |  |  |" in block


def test_seed_dod_block_empty_when_no_bullets():
    assert pr_body.seed_dod_block([]) == ""
    assert pr_body.seed_dod_block(None) == ""


def test_seeded_table_round_trips_through_the_gate_as_park():
    # A freshly seeded (blank) table must PARK the gate — nothing is disposed yet.
    block = pr_body.seed_dod_block(BULLETS)
    r = dod_gate.decide(BULLETS, block, spec_present=True)
    assert r["verdict"] == "park"


def test_stubbed_seams_block_from_diff_markers():
    diff = ("+++ b/acceptance_launch.py\n"
            "+x = 0  # STUB(#231): spend ceiling inert in live runs\n")
    markers = stub_markers.markers_in_diff(diff)
    block = pr_body.stubbed_seams_block(markers)
    assert pr_body.STUBS_MARKER in block
    assert "- `acceptance_launch.py` — spend ceiling inert in live runs (#231)" in block


def test_stubbed_seams_block_empty_omitted():
    assert pr_body.stubbed_seams_block([]) == ""


def test_compose_appends_both_blocks():
    body = pr_body.compose_body("base body",
                                pr_body.seed_dod_block(BULLETS),
                                pr_body.stubbed_seams_block(
                                    [{"file": "f.py", "issue": 9, "description": "d"}]))
    assert body.startswith("base body")
    assert dod_gate.TABLE_MARKER in body and pr_body.STUBS_MARKER in body


def test_compose_is_idempotent_on_markers():
    once = pr_body.compose_body("base", pr_body.seed_dod_block(BULLETS), "")
    twice = pr_body.compose_body(once, pr_body.seed_dod_block(BULLETS), "")
    assert once == twice  # the DoD marker already present -> not re-appended


def test_compose_empty_blocks_leaves_base():
    assert pr_body.compose_body("just base", "", "").rstrip() == "just base"
