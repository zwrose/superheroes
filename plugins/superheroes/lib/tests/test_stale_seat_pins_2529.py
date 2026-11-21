"""A core.md `enginePreferences.seatPins` key naming a seat no roster may name is NAMED (report
only) in configure's view and in the review-crew doctor's report (#2529).

"A seat no roster may name" is: not in seat_map.KNOWN_SEATS and not a key of
seat_map.LEGACY_SEAT_ALIASES (the legacy `test-reviewer` key is a live alias, never stale). Nothing
here writes, rewrites or drops a pin; a pin naming a live seat renders as it always did.

Bite-proof record: bite_proofs/wo_stale_seat_pins_2529.md.
"""
import json
import os
import subprocess

import configure_view as cv
import core_md
import mode_registry as mr
import repo_doctor
import seat_map
import store_core as sc

VIEW_HEADER = ("Seat pins for seats no roster has (the panel never seats them; "
               "remove them from core.md seatPins):")
DOCTOR_NOTE = ("review-crew calibration note: core.md seatPins names a seat no roster has "
               "(grounding-seat) — the panel never seats it; remove the pin with "
               "/superheroes:configure")
REJECTED_HEADER = "Rejected seat pins (not applied — seat falls back to rotation):"


# --------------------------------------------------------------------------- #
# Helpers (local copies of the patterns in test_configure_view / test_repo_doctor)
# --------------------------------------------------------------------------- #

def _init_repo(d, remote=None):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)


def _core_text(seat_pins, verify="pytest"):
    facts = {"verifyCommand": verify, "stackTags": ["py"], "threatModel": "single-user",
             "patterns": ""}
    if seat_pins is not None:
        facts["enginePreferences"] = {"seatPins": seat_pins}
    return core_md.render_core(facts, "confirmed", "2026-07-19", "2026-07-19")


def _seed_view(repo_dir, seat_pins):
    """Seed core.md engine preferences the way test_configure_view._seed_core_and_layer does.
    Returns the store root to hand to cv.render."""
    _init_repo(repo_dir, "git@github.com:o/r.git")
    root = str(repo_dir / "store")
    mr.write_registry(str(repo_dir), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(repo_dir), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"), _core_text(seat_pins))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nscope\n")
    return root


def _view_lines(tmp_path, seat_pins):
    repo_dir = tmp_path / "viewrepo"
    repo_dir.mkdir()
    root = _seed_view(repo_dir, seat_pins)
    return cv.render(str(repo_dir), root=root).splitlines()


def _make_root(tmp_path):
    """A git repo root with a fake `verifybin` on PATH (the pattern test_repo_doctor.make_root uses)."""
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    vb = bindir / "verifybin"
    vb.write_text("#!/bin/sh\nexit 0\n")
    vb.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "--allow-empty", "-m", "init"],
                   check=True, capture_output=True)
    return str(root), env


def _write_core(root, seat_pins):
    core_dir = os.path.join(root, ".claude", "superheroes")
    os.makedirs(core_dir, exist_ok=True)
    path = os.path.join(core_dir, "core.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_core_text(seat_pins, verify="verifybin --run"))
    return path


def _write_layer(tmp_path, ack="{}"):
    layer = tmp_path / "review-crew.md"
    layer.write_text(
        "<!-- review-crew: schemaVersion=1 status=confirmed created=2026-01-01 "
        "updated=2026-01-01 rubric-version=2 nudge-ack=%s -->\n\n## Focus hints\n- code: x\n" % ack)
    return str(layer)


def _write_profile(tmp_path, ack="{}"):
    p = tmp_path / "review-profile.md"
    p.write_text(
        "<!-- review-profile · managed by review-crew · schema 1 -->\n"
        "<!-- provenance -->\n"
        "schema: 1\n"
        "plugin: review-crew@0.1.0\n"
        "rubric-version: 2\n"
        "generated: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "status: stable\n"
        "nudge-ack: %s\n"
        "signals:\n"
        "  dep-set: []\n"
        "  default-branch: main\n"
        "  forge: github\n"
        "<!-- end provenance -->\n"
        "\n## Verify\ncommand: verifybin --run\n" % ack)
    return str(p)


def _run(profile, root, env, capsys, rubric=2):
    rc = repo_doctor.main(["repo_doctor.py", profile, "review-crew@0.1.0", str(rubric),
                           "--root", root], env=env)
    assert rc == 0
    return json.loads(capsys.readouterr().out)


def _assert_stale_named_not_drift(res):
    assert res["staleSeatPins"] == ["grounding-seat"]
    assert res["message"] == DOCTOR_NOTE
    assert res["drift"] == []
    assert "grounding-seat" not in json.dumps(res["drift"])
    assert res["signal_hash"] != ""


# --------------------------------------------------------------------------- #
# seat_map.unknown_pin_seats
# --------------------------------------------------------------------------- #

def test_unknown_pin_seats_names_only_seats_no_roster_may_name():
    assert seat_map.unknown_pin_seats(["grounding-seat", "nope-seat"]) == [
        "grounding-seat", "nope-seat"]
    # a dict passes its keys; the result is sorted
    assert seat_map.unknown_pin_seats({"nope-seat": 1, "code-reviewer": 2,
                                       "grounding-seat": 3}) == ["grounding-seat", "nope-seat"]
    # every known seat is live
    assert seat_map.unknown_pin_seats(list(seat_map.KNOWN_SEATS)) == []
    # non-string keys are ignored, never raised on
    assert seat_map.unknown_pin_seats(["grounding-seat", 3, None, b"x", ("t",), 4.5]) == [
        "grounding-seat"]
    assert seat_map.unknown_pin_seats(7) == []
    assert seat_map.unknown_pin_seats(None) == []
    assert seat_map.unknown_pin_seats(k for k in ("nope-seat",)) == ["nope-seat"]


def test_unknown_pin_seats_never_names_the_legacy_alias():
    # `test-reviewer` is a live alias for the test role, never stale
    assert "test-reviewer" in seat_map.LEGACY_SEAT_ALIASES
    assert seat_map.unknown_pin_seats(["test-reviewer"]) == []
    assert seat_map.unknown_pin_seats(["test-reviewer", "grounding-seat"]) == ["grounding-seat"]


# --------------------------------------------------------------------------- #
# configure view
# --------------------------------------------------------------------------- #

def test_view_names_a_stale_seat_pin_and_leaves_a_live_pin_line_as_is(tmp_path):
    lines = _view_lines(tmp_path, {
        "code-reviewer": {"vendor": "codex"},
        "grounding-seat": {"vendor": "codex"},
    })
    assert VIEW_HEADER in lines
    assert lines.count("  grounding-seat ⚠") == 1
    # the live pin reads exactly as it did before; the stale one keeps its existing line too
    assert "Review-panel seat pins:" in lines
    assert "  code-reviewer: codex" in lines
    assert "  grounding-seat: codex" in lines
    assert "  code-reviewer ⚠" not in lines
    # the new block sits after the pin list and before the blank line that follows the section
    at = lines.index(VIEW_HEADER)
    assert at > lines.index("Review-panel seat pins:")
    assert lines[at + 1] == "  grounding-seat ⚠"
    assert lines[at + 2] == ""


def test_view_names_a_stale_seat_whose_pin_is_broken(tmp_path):
    lines = _view_lines(tmp_path, {"grounding-seat": "nope"})
    # still under the Rejected block, as it is today
    assert REJECTED_HEADER in lines
    assert "  grounding-seat: pin must be an object with a vendor ⚠" in lines
    # and now named under the new block too
    assert VIEW_HEADER in lines
    assert "  grounding-seat ⚠" in lines


def test_view_has_no_stale_block_when_every_pin_names_a_live_seat(tmp_path):
    screen_lines = _view_lines(tmp_path, {
        "code-reviewer": {"vendor": "codex"},
        "test-reviewer": {"vendor": "claude"},
    })
    assert "Review-panel seat pins:" in screen_lines
    assert "  code-reviewer: codex" in screen_lines
    assert VIEW_HEADER not in screen_lines
    assert not any("Seat pins for seats no roster has" in line for line in screen_lines)


# --------------------------------------------------------------------------- #
# the doctor
# --------------------------------------------------------------------------- #

def test_doctor_unified_layer_names_a_stale_seat_pin(tmp_path, capsys):
    root, env = _make_root(tmp_path)
    _write_core(root, {"grounding-seat": {"vendor": "codex"}, "code-reviewer": {"vendor": "codex"}})
    res = _run(_write_layer(tmp_path), root, env, capsys)
    _assert_stale_named_not_drift(res)
    assert res["nudge_acked"] is False
    h = res["signal_hash"]
    # the hash written into the layer's nudge-ack acknowledges it
    res2 = _run(_write_layer(tmp_path, ack="{%s: true}" % h), root, env, capsys)
    assert res2["signal_hash"] == h
    assert res2["nudge_acked"] is True


def test_doctor_legacy_profile_names_a_stale_seat_pin(tmp_path, capsys):
    root, env = _make_root(tmp_path)
    _write_core(root, {"grounding-seat": {"vendor": "codex"}, "code-reviewer": {"vendor": "codex"}})
    res = _run(_write_profile(tmp_path), root, env, capsys)
    _assert_stale_named_not_drift(res)
    assert res["nudge_acked"] is False
    h = res["signal_hash"]
    # the hash written into the profile's nudge-ack acknowledges it
    res2 = _run(_write_profile(tmp_path, ack="{'%s': true}" % h), root, env, capsys)
    assert res2["signal_hash"] == h
    assert res2["nudge_acked"] is True


def test_doctor_live_pins_only_leave_the_hash_as_it_was(tmp_path, capsys):
    root, env = _make_root(tmp_path)
    profile = _write_profile(tmp_path)
    # real drift (engine rubric 3 > profile 2), so the hash is non-empty and worth comparing
    _write_core(root, None)
    base = _run(profile, root, env, capsys, rubric=3)
    assert base["drift"] != []
    assert base["signal_hash"] != ""
    _write_core(root, {
        "code-reviewer": {"vendor": "codex"},
        "security-reviewer": {"vendor": "claude"},
        "test-reviewer": {"vendor": "claude"},   # the live legacy alias
    })
    live = _run(profile, root, env, capsys, rubric=3)
    assert live["staleSeatPins"] == []
    assert live["signal_hash"] == base["signal_hash"]
    assert live["drift"] == base["drift"]
    assert live["message"] == base["message"]
    assert "calibration note" not in live["message"]


def test_doctor_stale_pin_fails_soft_on_every_unreadable_shape(tmp_path, monkeypatch):
    root, _env = _make_root(tmp_path)
    # core.md absent
    assert repo_doctor._stale_seat_pins(root) == []
    # core.md malformed
    core_dir = os.path.join(root, ".claude", "superheroes")
    os.makedirs(core_dir, exist_ok=True)
    with open(os.path.join(core_dir, "core.md"), "w", encoding="utf-8") as fh:
        fh.write("this is not a core file\n")
    assert repo_doctor._stale_seat_pins(root) == []
    # seatPins not an object
    _write_core(root, ["grounding-seat"])
    assert repo_doctor._stale_seat_pins(root) == []
    # a stale key with a broken pin is still named (the doctor reads raw keys)
    _write_core(root, {"grounding-seat": "nope"})
    assert repo_doctor._stale_seat_pins(root) == ["grounding-seat"]
    # any exception -> []
    def boom(**_kw):
        raise RuntimeError("boom")
    monkeypatch.setattr(core_md, "engine_preferences_for_gate", boom)
    assert repo_doctor._stale_seat_pins(root) == []


def test_report_only_never_rewrites_core_md(tmp_path, capsys):
    pins = {"grounding-seat": {"vendor": "codex"}, "test-reviewer": {"vendor": "claude"}}
    view_dir = tmp_path / "viewrepo"
    view_dir.mkdir()
    store = _seed_view(view_dir, pins)
    view_core = view_dir / ".claude" / "superheroes" / "core.md"
    doc_root, env = _make_root(tmp_path)
    doc_core = _write_core(doc_root, pins)

    view_before = view_core.read_bytes()
    with open(doc_core, "rb") as fh:
        doc_before = fh.read()

    screen = cv.render(str(view_dir), root=store)
    res = _run(_write_layer(tmp_path), doc_root, env, capsys)

    # both really did name the stale pin ...
    assert VIEW_HEADER in screen.splitlines()
    assert res["staleSeatPins"] == ["grounding-seat"]
    # ... and neither wrote, rewrote or dropped it
    assert view_core.read_bytes() == view_before
    with open(doc_core, "rb") as fh:
        assert fh.read() == doc_before
