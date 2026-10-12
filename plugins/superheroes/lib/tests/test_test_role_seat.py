"""The test role holds the review panel's test seat under one key, `test-role`.

- The seat key is spelled the one way in every live reader; `test-reviewer` survives only as the
  legacy pin alias (and the one doc sentence that names it).
- A saved pin under the old key is read as the test role's pin; an explicit `test-role` pin wins.
- The Test and Code seats' panel orders name their agent file as a role brief; no other seat's does.
"""
import os

import pytest

import core_md
import engine_pref
import model_registry
import round_driver as RD
import round_orders as RO
import round_panel_contract
import round_phases as RP
import seat_map

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.normpath(os.path.join(_HERE, ".."))
_PLUGIN = os.path.normpath(os.path.join(_LIB, ".."))

NEW = "test-role"
OLD = "test-reviewer"
THREE_VENDORS = ["claude", "codex", "cursor"]

# Shipped files that may spell the old key: the alias constant's home, and the one doc sentence
# telling an owner an old pin still works.
_LEGACY_SPELLING_HOMES = {
    os.path.join("lib", "seat_map.py"),
    os.path.join("skills", "configure", "reference", "view-and-tune.md"),
}


# --- Invariant: one seat key ------------------------------------------------------------------


def test_every_roster_holds_the_test_role_and_not_the_old_key():
    # bites on: a roster that still seats, names or keys the test seat under the old spelling
    rosters = {
        "seat_map.LENS_SEATS": seat_map.LENS_SEATS,
        "seat_map.PANEL_ROSTER": seat_map.PANEL_ROSTER,
        "round_panel_contract.DEFAULT_PANEL_DIMENSIONS": round_panel_contract.DEFAULT_PANEL_DIMENSIONS,
        "round_driver.AGENT_SUFFIX": tuple(RD.AGENT_SUFFIX),
    }
    for label, roster in rosters.items():
        assert NEW in roster, "%s lost %s" % (label, NEW)
        assert OLD not in roster, "%s still holds %s" % (label, OLD)


@pytest.mark.parametrize("live_vendors", [["claude"], THREE_VENDORS])
def test_no_composed_panel_holds_both_seats(live_vendors):
    # bites on: a seat map that composes the old and new test seats side by side
    for seed in range(4):
        built = seat_map.build(seat_map.PANEL_ROSTER, live_vendors, "xai", "anthropic", seed)
        assert NEW in built["seats"]
        assert OLD not in built["seats"]


def test_pin_under_both_keys_composes_one_seat():
    # bites on: the old-key pin seating a second (unknown) seat next to the test role
    pins = {OLD: {"vendor": "claude"}, NEW: {"vendor": "claude"}}
    built = seat_map.build(seat_map.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", 0, pins=pins)
    assert NEW in built["seats"] and OLD not in built["seats"]
    assert not [d for d in built["degradations"]
                if d["constraint"] == "pin" and "unknown seat" in d["reason"]]


def _shipped_files():
    # lib, skills and rubric/orders, minus tests and bytecode; a file that is not UTF-8 text
    # is not a reader of the key.
    for sub in ("lib", "skills", os.path.join("rubric", "orders")):
        for dirpath, dirnames, filenames in os.walk(os.path.join(_PLUGIN, sub)):
            dirnames[:] = [d for d in dirnames if d not in ("tests", "__pycache__")]
            for name in filenames:
                yield os.path.join(dirpath, name)


def test_old_key_is_spelled_only_at_its_legacy_homes():
    # bites on: a live reader (code or doc) still naming the old seat key
    found = set()
    for path in _shipped_files():
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        if OLD in text:
            found.add(os.path.relpath(path, _PLUGIN))
    assert found == _LEGACY_SPELLING_HOMES, "old seat key spelled outside its legacy homes: %s" % sorted(
        found - _LEGACY_SPELLING_HOMES)


def test_alias_is_defined_once_and_both_normalizers_read_it():
    # bites on: a second alias table, or a normalizer carrying its own copy of the mapping
    assert seat_map.LEGACY_SEAT_ALIASES == {OLD: NEW}
    with open(os.path.join(_LIB, "seat_map.py"), encoding="utf-8") as fh:
        assert fh.read().count('"%s"' % OLD) == 1
    with open(os.path.join(_LIB, "engine_pref.py"), encoding="utf-8") as fh:
        assert "LEGACY_SEAT_ALIASES" in fh.read()


# --- Invariant: an old pin carries over -------------------------------------------------------

_PIN_A = {"vendor": "codex", "model": "m-a"}
_PIN_B = {"vendor": "claude"}


def _engine_pref_edges():
    # (raw map, expected pins, expected invalid keys)
    return [
        ("both keys: canonical wins", {OLD: _PIN_A, NEW: _PIN_B}, {NEW: _PIN_B}, set()),
        ("legacy alone, invalid: reported under the canonical key",
         {OLD: "codex"}, {}, {NEW}),
        ("both keys, legacy invalid: legacy shadowed, not reported",
         {OLD: "codex", NEW: _PIN_B}, {NEW: _PIN_B}, set()),
        ("both keys, canonical invalid: canonical reported, legacy shadowed",
         {OLD: _PIN_A, NEW: "codex"}, {}, {NEW}),
        ("legacy alone: applied to the test role", {OLD: _PIN_A}, {NEW: _PIN_A}, set()),
        ("neither: unchanged", {"code-reviewer": _PIN_A}, {"code-reviewer": _PIN_A}, set()),
    ]


@pytest.mark.parametrize("label,raw,pins,invalid_keys", _engine_pref_edges(),
                         ids=[e[0] for e in _engine_pref_edges()])
def test_engine_pref_seat_pin_alias_truth_table(label, raw, pins, invalid_keys):
    # bites on: the loaded-preferences path applying the legacy key with the wrong precedence
    got = engine_pref.normalize_seat_pin_map(raw)
    assert got["pins"] == pins
    assert set(got["invalid"]) == invalid_keys


def test_engine_pref_seat_pin_non_dict_is_unchanged():
    # bites on: the alias loop running before the non-dict refusal
    assert engine_pref.normalize_seat_pin_map(["x"]) == {"pins": {}, "invalid": {}}


def _seat_map_edges():
    # (raw map, expected normalized, expected error tokens)
    return [
        ("both keys: canonical wins", {OLD: _PIN_A, NEW: _PIN_B}, {NEW: _PIN_B}, []),
        ("legacy alone, invalid: reported under the canonical key",
         {OLD: 7}, {}, ["pins-invalid:%s" % NEW]),
        ("both keys, legacy invalid: legacy shadowed, not reported",
         {OLD: 7, NEW: _PIN_B}, {NEW: _PIN_B}, []),
        ("both keys, canonical invalid: canonical reported, legacy shadowed",
         {OLD: _PIN_A, NEW: 7}, {}, ["pins-invalid:%s" % NEW]),
        ("legacy alone: applied to the test role", {OLD: _PIN_A}, {NEW: _PIN_A}, []),
        ("legacy alone, string shorthand: applied to the test role",
         {OLD: "codex"}, {NEW: {"vendor": "codex"}}, []),
        ("neither: unchanged", {"code-reviewer": _PIN_A}, {"code-reviewer": _PIN_A}, []),
    ]


@pytest.mark.parametrize("label,raw,normalized,errors", _seat_map_edges(),
                         ids=[e[0] for e in _seat_map_edges()])
def test_seat_map_normalize_pins_alias_truth_table(label, raw, normalized, errors):
    # bites on: the compose --pins path applying the legacy key with the wrong precedence
    assert seat_map.normalize_pins(raw) == (normalized, errors)


def test_seat_map_normalize_pins_non_dict_is_unchanged():
    # bites on: the alias loop running before the non-dict refusal
    assert seat_map.normalize_pins(["x"]) == ({}, ["pins-invalid"])
    assert seat_map.normalize_pins(None) == ({}, [])


def _write_core(repo, prefs):
    core_md.write(repo, {"verifyCommand": "npm test", "stackTags": [], "threatModel": "x",
                         "patterns": "", "enginePreferences": prefs}, "confirmed",
                  root=os.path.join(repo, "store"), now="2026-06-30")


def test_old_pin_in_a_project_core_md_seats_the_test_role(tmp_path):
    # bites on: a project's saved old-key pin being dropped or left under the old key
    model, effort = model_registry.allowlist("reviewer-deep", "codex")[0]
    pin = {"vendor": "codex", "model": model}
    repo = str(tmp_path)
    _write_core(repo, {"seatPins": {OLD: pin}})
    core_file = core_md.core_path(repo, root=os.path.join(repo, "store"))
    with open(core_file, encoding="utf-8") as fh:
        before = fh.read()
    loaded = engine_pref.load_engine_prefs(repo, root=os.path.join(repo, "store"))
    assert loaded["seatPins"] == {NEW: pin}
    assert "invalidSeatPins" not in loaded
    # the raw map the review setup feeds `seat_map compose --pins`, and the loaded one, both seat it
    for pins in ({OLD: pin}, loaded["seatPins"]):
        built = seat_map.build(seat_map.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", 0,
                               pins=pins)
        seat = built["seats"][NEW]
        assert (seat["vendor"], seat["model"], seat["source"]) == ("codex", model, "pinned")
    # nothing is rewritten on disk
    with open(core_file, encoding="utf-8") as fh:
        assert fh.read() == before
    assert OLD in before


# --- Invariant: the Test and Code seats' panel orders name their role brief --------------------

_ROLE_BRIEF_MARK = "- Your role brief (read it first; it binds over the generic assignment above): "


def _render_panel(tmp_path, seat_key):
    session_dir = str(tmp_path / ("session-" + seat_key))
    os.makedirs(session_dir)
    state = {"config": {"repoRoot": str(tmp_path)}, "reviewedDiff": "diff --git a/f b/f\n",
             "headDiff": "diff --git a/f b/f\n", "_fixBatch": []}
    paths = {
        "storage_key": "probe.a0",
        "landing_path": os.path.join(session_dir, "landing.json"),
        "envelope_landing_path": os.path.join(session_dir, "env.json"),
        "bare_payload_path": os.path.join(session_dir, "bare.json"),
        "envelope_stub_path": os.path.join(session_dir, "stub.json"),
        "order_path": os.path.join(session_dir, "order.md"),
    }
    placeholders = RD._order_placeholders(
        RP.P_PANEL, seat_key, 0, state, state["config"], {}, session_dir, 1, paths,
        RD.CHANNEL_FILE)
    context = {
        "session_dir": session_dir, "round": 1, "attempt": 0,
        "diff_path": placeholders["DIFF_PATH"], "rubric_path": placeholders["RUBRIC_PATH"],
        "core_path": "", "layer_path": "", "repo_root": str(tmp_path),
        "landing_path": paths["landing_path"], "envelope_stub_path": paths["envelope_stub_path"],
        "ratified_residuals": "", "residuals_provenance": "", "residuals_read_failure": None,
        "payload": {}, "host_seat": False, "placeholders": placeholders,
    }
    text, reason = RO.render_order(RP.P_PANEL, seat_key, context)
    assert reason is None, reason
    return text


def _role_brief_lines(text):
    return [line for line in text.splitlines() if line.startswith(_ROLE_BRIEF_MARK)]


def test_test_seat_panel_order_names_the_test_role_brief(tmp_path):
    # bites on: the Test seat's order dropping or misdirecting its role brief
    lines = _role_brief_lines(_render_panel(tmp_path, NEW))
    assert len(lines) == 1
    brief = lines[0][len(_ROLE_BRIEF_MARK):]
    assert os.path.isabs(brief)
    assert brief.endswith(os.path.join("agents", "test-role.md"))
    assert os.path.isfile(brief)


def test_code_seat_panel_order_names_the_code_reviewer_brief(tmp_path):
    # bites on: the Code seat's order dropping or misdirecting its role brief
    lines = _role_brief_lines(_render_panel(tmp_path, "code-reviewer"))
    assert len(lines) == 1
    assert lines[0].endswith(os.path.join("agents", "code-reviewer.md"))
    assert os.path.isfile(lines[0][len(_ROLE_BRIEF_MARK):])


@pytest.mark.parametrize("seat_key", ["security-reviewer", "architecture-reviewer",
                                      "premortem-reviewer"])
def test_other_seats_panel_orders_name_no_role_brief(tmp_path, seat_key):
    # bites on: a seat with no role brief getting a line (or a stray placeholder) in its order
    text = _render_panel(tmp_path, seat_key)
    assert "role brief" not in text
    assert "{{" not in text


def test_role_brief_root_is_the_rubric_root():
    # bites on: a second hard-coded plugin root for the role brief
    rubric_root = os.path.dirname(os.path.dirname(RD._shipped_rubric_path()))
    assert RD._role_brief_path(NEW) == os.path.join(rubric_root, "agents", "test-role.md")
