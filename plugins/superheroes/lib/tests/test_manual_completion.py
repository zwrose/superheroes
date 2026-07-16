# plugins/superheroes/lib/tests/test_manual_completion.py
"""#450 manual-completion receipt — pure core. When an owner/advisor takes over a PARKED run
and finishes it BY HAND, this module supplies the terminal journal event type + terminal
checkpoint phase that make the run record truthful. These tests pin the pure transforms; the
IO leaf + record-reader integration live in test_manual_completion_entry.py."""
import checkpoint as ckpt_lib
import manual_completion as mc


def test_terminal_phase_is_the_shipped_manual_marker():
    assert mc.TERMINAL_PHASE == ckpt_lib.SHIPPED_MANUAL
    assert mc.TERMINAL_PHASE in ckpt_lib.TERMINAL_PHASES
    # The terminal marker is NOT one of the resumable pipeline phases — a resume must never
    # try to re-enter a hand-shipped run at "shipped-manual".
    assert mc.TERMINAL_PHASE not in ckpt_lib.CURRENT_PHASES


def test_event_type_matches_the_journal_vocabulary():
    import journal
    assert mc.EVENT_TYPE == "manual_completion"
    assert mc.EVENT_TYPE in journal.EVENT_TYPES


def test_build_payload_carries_pr_and_optional_fields():
    assert mc.build_payload(420) == {"pr": 420}
    assert mc.build_payload("https://x/pr/420", head_sha="abc123", note="finished by hand") == {
        "pr": "https://x/pr/420", "headSha": "abc123", "note": "finished by hand"}
    # Empty optionals are omitted (never a null-valued key).
    assert mc.build_payload(1, head_sha=None, note="") == {"pr": 1}


def test_pr_record_is_the_ready_dict_shape_record_readers_expect():
    # run_watch._read_checkpoint reads pr.url; render_brief reads pr.isDraft — a hand-shipped
    # PR is ready (isDraft False).
    rec = mc.pr_record(420)
    assert rec == {"isDraft": False, "number": 420}
    rec = mc.pr_record("https://github.com/o/r/pull/420")
    assert rec["isDraft"] is False and rec["url"] == "https://github.com/o/r/pull/420"
    assert rec["number"] == 420
    rec = mc.pr_record("#420", url="https://x/pr/420")
    assert rec == {"isDraft": False, "number": 420, "url": "https://x/pr/420"}


def test_pr_number_survives_a_url_query_string_or_fragment():
    # A /pull/<n> path wins so a trailing ?query or #fragment can't shadow the real PR number,
    # while a bare "#420" ref still resolves via the trailing-digit scan.
    assert mc._as_number("https://github.com/o/r/pull/420") == 420
    assert mc._as_number("https://github.com/o/r/pull/420?w=1") == 420
    assert mc._as_number("https://github.com/o/r/pull/420#issuecomment-9") == 420
    assert mc._as_number("https://github.com/o/r/pull/420/files") == 420
    assert mc._as_number("#420") == 420
    assert mc._as_number("420") == 420
    assert mc._as_number("not-a-pr") is None


def test_advance_checkpoint_sets_terminal_phase_and_pr_and_preserves_the_cursor():
    cp = ckpt_lib.new("wi-x", "feat/x", phase="build",
                      last_good_step=4, last_good_phase="workhorse")
    out = mc.advance_checkpoint(cp, 420)
    assert out["phase"] == mc.TERMINAL_PHASE
    assert out["pr"] == {"isDraft": False, "number": 420}
    # The resume cursor is a truthful record of where the spine actually got to before the
    # hand-off — advance leaves it UNTOUCHED (and checkpoint validation couples the pair).
    assert out["lastGoodStep"] == 4 and out["lastGoodPhase"] == "workhorse"
    # Pure: the input dict is not mutated.
    assert cp["phase"] == "build" and cp.get("pr") is None


def test_advanced_checkpoint_round_trips_through_the_validator(tmp_path):
    # The terminal checkpoint must survive checkpoint.write/read unchanged — never flagged
    # _incompatible (which would make the record park-on-read).
    cp = ckpt_lib.new("wi-y", "feat/y", phase="build",
                      last_good_step=4, last_good_phase="workhorse")
    out = mc.advance_checkpoint(cp, "https://x/pr/9", url="https://x/pr/9")
    path = str(tmp_path / "checkpoint.json")
    ckpt_lib.write(path, out)
    back = ckpt_lib.read(path)
    assert not back.get("_incompatible")
    assert back["phase"] == mc.TERMINAL_PHASE
    assert back["pr"]["isDraft"] is False


def test_is_manually_completed_reads_the_terminal_marker():
    assert mc.is_manually_completed({"phase": mc.TERMINAL_PHASE}) is True
    assert mc.is_manually_completed({"phase": "build"}) is False
    assert mc.is_manually_completed(None) is False
