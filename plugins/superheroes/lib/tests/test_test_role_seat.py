"""The test role holds the review panel's test seat under one key, `test-role`.

- The seat key is spelled the one way in every live reader; `test-reviewer` survives only as the
  legacy pin alias (and the one doc sentence that names it).
- A saved pin under the old key is read as the test role's pin; an explicit `test-role` pin wins.
- The Test and Code seats' panel orders name their agent file as a role brief; no other seat's does.
"""
import json
import os
import subprocess

import pytest

import break_it
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
        built = seat_map.build(seat_map.PANEL_ROSTER, live_vendors, "xai", seed)
        assert NEW in built["seats"]
        assert OLD not in built["seats"]


def test_pin_under_both_keys_composes_one_seat():
    # bites on: the old-key pin seating a second (unknown) seat next to the test role
    pins = {OLD: {"vendor": "claude"}, NEW: {"vendor": "claude"}}
    built = seat_map.build(seat_map.PANEL_ROSTER, THREE_VENDORS, "xai", 0, pins=pins)
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
        built = seat_map.build(seat_map.PANEL_ROSTER, THREE_VENDORS, "xai", 0,
                               pins=pins)
        seat = built["seats"][NEW]
        assert (seat["vendor"], seat["model"], seat["source"]) == ("codex", model, "pinned")
    # nothing is rewritten on disk
    with open(core_file, encoding="utf-8") as fh:
        assert fh.read() == before
    assert OLD in before


# --- Invariant: the Test and Code seats' panel orders name their role brief --------------------

_ROLE_BRIEF_MARK = "- Your role brief (read it first; it binds over the generic assignment above): "


def _render_panel(tmp_path, seat_key, repo=None, base=None, head=None):
    repo_root = str(repo) if repo is not None else str(tmp_path)
    session_dir = str(tmp_path / ("session-" + seat_key))
    os.makedirs(session_dir)
    config = {"repoRoot": repo_root}
    if base is not None:
        config["baseRef"] = base
    if head is not None:
        config["headSha"] = head
    state = {"config": config, "reviewedDiff": "diff --git a/f b/f\n",
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
        "core_path": "", "layer_path": "", "repo_root": repo_root,
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
def test_other_seats_panel_orders_name_their_own_role_brief(tmp_path, seat_key):
    # bites on: a lens seat's order dropping or misdirecting its own role brief (every lens seat
    # carries one now — #1797), or a stray placeholder left in the order
    text = _render_panel(tmp_path, seat_key)
    lines = _role_brief_lines(text)
    assert len(lines) == 1
    assert lines[0].endswith(os.path.join("agents", "%s.md" % seat_key))
    assert os.path.isfile(lines[0][len(_ROLE_BRIEF_MARK):])
    assert "{{" not in text


def test_role_brief_root_is_the_rubric_root():
    # bites on: a second hard-coded plugin root for the role brief
    rubric_root = os.path.dirname(os.path.dirname(RD._shipped_rubric_path()))
    assert RD._role_brief_path(NEW) == os.path.join(rubric_root, "agents", "test-role.md")


# --- Invariant: the test role's panel order names the risk areas the change touches -----------

_RISK_MARK = "- Risk areas this change touches: "
_PAYMENTS_AREA = dict(name="payments", covers=["src/payments"], why="Charges customers.",
                      undo="Hard: a charge needs a refund.")


def _git(repo, *args):
    done = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _write(repo, rel, text="x\n"):
    path = os.path.join(str(repo), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _risk_repo(tmp_path, with_risk_areas=True):
    """A throwaway git repo whose in-repo core.md declares a `payments` risk area, with a base
    commit holding `src/payments/old.py` and `src/payments/a.py`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    block = dict(schemaVersion=2, verifyCommand="npm test", stackTags=["node"])
    if with_risk_areas:
        block["projectConfiguration"] = dict(riskAreas=[_PAYMENTS_AREA])
    _write(repo, ".claude/superheroes/core.md", (
        "<!-- superheroes-core: schemaVersion=2 status=confirmed created=2026-06-26 "
        "updated=2026-06-26 -->\n\n## Threat model\n\nsingle-user\n\n"
        "## Canonical patterns\n\n- x: a.ts:1\n\n"
        "```json superheroes-core\n%s\n```\n" % json.dumps(block, indent=2)))
    _write(repo, "src/payments/old.py")
    _write(repo, "src/payments/a.py")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo, _git(repo, "rev-parse", "HEAD")


def _risk_lines(tmp_path, change, seat_key=NEW, base=None, with_risk_areas=True):
    """The risk-areas lines of `seat_key`'s panel order for the change `change(repo)` commits."""
    repo, base_sha = _risk_repo(tmp_path, with_risk_areas)
    change(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    head = _git(repo, "rev-parse", "HEAD")
    text = _render_panel(tmp_path, seat_key, repo=repo, base=base or base_sha, head=head)
    return [line for line in text.splitlines() if line.startswith(_RISK_MARK)]


def test_r1_new_file_in_a_risk_area_is_named(tmp_path):
    # bites on: the change's touched risk area not reaching the test role's order
    lines = _risk_lines(tmp_path, lambda r: _write(r, "src/payments/charge.py"))
    assert len(lines) == 1
    assert lines[0].startswith(_RISK_MARK + "payments (matched: src/payments/charge.py)")


def test_r2_deleted_file_in_a_risk_area_is_named(tmp_path):
    # bites on: a deletion dropping out of the changed paths
    lines = _risk_lines(tmp_path, lambda r: os.remove(os.path.join(str(r), "src/payments/old.py")))
    assert len(lines) == 1
    assert "payments (matched: src/payments/old.py)" in lines[0]


def test_r3_rename_out_of_a_risk_area_names_the_old_path(tmp_path):
    # bites on: --no-renames dropped, so a rename out of the area lists only the new path
    def rename(repo):
        os.makedirs(os.path.join(str(repo), "src/other"))
        os.rename(os.path.join(str(repo), "src/payments/a.py"),
                  os.path.join(str(repo), "src/other/a.py"))
    lines = _risk_lines(tmp_path, rename)
    assert len(lines) == 1
    assert "payments (matched: src/payments/a.py)" in lines[0]


def test_r4_change_outside_every_risk_area_says_so(tmp_path):
    lines = _risk_lines(tmp_path, lambda r: _write(r, "docs/x.md"))
    assert lines == [_RISK_MARK + "none of this project's risk areas"]


def test_r5_no_risk_areas_key_says_not_set_missing(tmp_path):
    # bites on: a store with no riskAreas key reading as "touches none"
    lines = _risk_lines(tmp_path, lambda r: _write(r, "src/payments/charge.py"),
                        with_risk_areas=False)
    assert len(lines) == 1
    assert lines[0].startswith(_RISK_MARK + "not set (missing")


def test_r6_unresolvable_base_says_changed_paths_unreadable(tmp_path):
    # bites on: a failed git read reading as "touches none" or raising
    lines = _risk_lines(tmp_path, lambda r: _write(r, "src/payments/charge.py"),
                        base="no-such-ref-1800")
    assert len(lines) == 1
    assert lines[0].startswith(_RISK_MARK + "not set (changed-paths-unreadable: ")


def test_r7_other_seats_order_carries_no_risk_areas_line(tmp_path):
    # bites on: the test-role-only gate — every seat's order getting the line
    lines = _risk_lines(tmp_path, lambda r: _write(r, "src/payments/charge.py"),
                        seat_key="code-reviewer")
    assert lines == []


# --- Invariant: the test role's panel order renders the break-it block grammar -----------------

_GRAMMAR_MARK = "- The break-it block (a break-it finding's suggestion is exactly this; the loop parses it):"


def test_test_role_order_renders_the_break_it_grammar_and_it_parses(tmp_path):
    # bites on: the grammar's render dropping, the test-role-only gate, or a render that does not parse
    text = _render_panel(tmp_path, NEW)
    assert "{{" not in text
    marker = text.index(_GRAMMAR_MARK)
    rendered = "%s\n\n```\n%s\n```\n\n%s\n" % (
        _GRAMMAR_MARK, break_it.BLOCK_TEMPLATE, break_it.RUN_RULES)
    assert text[marker:].startswith(rendered)
    fenced = text[marker:].split("```\n")[1].split("\n```")[0]
    lines = fenced.split("\n")
    assert lines[0] == "break-it-test v1" and lines[3] == "---"
    assert lines[1].startswith("path: <") and lines[2].startswith("run: <")
    lines[1], lines[2] = "path: tests/test_x.py", "run: python tests/test_x.py"
    block, refusal = break_it.parse_block("\n".join(lines[:4]) + "\nassert True\n")
    assert refusal is None
    assert (block["path"], block["run"], block["content"]) == (
        "tests/test_x.py", "python tests/test_x.py", "assert True\n")
    assert "break-it-test v1" not in _render_panel(tmp_path, "code-reviewer")


def test_test_role_order_break_it_grammar_path_line_names_both_kinds_of_finding(tmp_path):
    # bites on: the rendered path line telling an attached finding its path is the finding's file
    text = _render_panel(tmp_path, NEW)
    fenced = text[text.index(_GRAMMAR_MARK):].split("```\n")[1].split("\n```")[0]
    path_line = fenced.split("\n")[1]
    assert path_line.startswith("path: <") and path_line.endswith(">")
    assert "does not exist yet" in path_line
    assert "for a per-area finding the same path as `file`" in path_line
    assert "for an attached finding not the finding's `file`" in path_line
    assert "the same repo-relative path as `file`>" not in path_line
