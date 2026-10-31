"""A big change's round-1 panel reviews it in size slices.

On a fresh session whose round-1 change weighs more than the countable-lines bar, the round-1 panel roster is the
whole-change seats plus, for each slice, its own seats. A change at or under the bar keeps the configured roster.
A slice seat is told its slice (a scope line, and for a native seat a diff holding only that slice), takes its lens's
vendor from the seat map, and writes a findings file of its own.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c2_wo4a_sliced_panel.md
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import countable_lines as cl  # noqa: E402
import round_driver as RD  # noqa: E402
import round_orders as RO  # noqa: E402
import round_phases as RP  # noqa: E402

BAR = cl.COUNTABLE_LINES_BAR
PAYMENTS = "src/payments/charge.py"
OTHER = "src/other/util.py"
RISK_AREAS = [{"name": "Payments", "covers": ["src/payments/*"], "why": "Charges customers.",
               "undo": "Hard: a charge needs a refund."}]
_IDENTITY = ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid"]


@pytest.fixture(autouse=True)
def _pin_git(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _git(root, *args):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    proc = subprocess.run(["git", "-C", str(root), *_IDENTITY, *args], env=env, capture_output=True, text=True, check=True)
    return proc.stdout


def _core_md(areas):
    block = json.dumps({"schemaVersion": 3, "verifyCommand": "npm test", "stackTags": ["node"],
                        "projectConfiguration": {"riskAreas": areas}}, indent=2)
    return ("<!-- superheroes-core: schemaVersion=3 status=confirmed created=2026-06-26 updated=2026-06-26 -->\n\n"
            "## Threat model\n\nsingle-user\n\n## Canonical patterns\n\n- x: a.ts:1\n\n"
            "```json superheroes-core\n%s\n```\n" % block).encode("utf-8")


def _repo(tmp_path, areas=None):
    """A git checkout with one commit; ``areas`` None leaves the risk areas unset (no core.md)."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "README.md").write_bytes(b"readme\n")
    if areas is not None:
        (root / ".claude" / "superheroes").mkdir(parents=True)
        (root / ".claude" / "superheroes" / "core.md").write_bytes(_core_md(areas))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _added(path, n):
    """The diff section of a new file of ``n`` added lines."""
    body = "".join("+%s line %d\n" % (os.path.basename(path), i) for i in range(n))
    return ("diff --git a/%s b/%s\nnew file mode 100644\nindex 0000000..1111111\n--- /dev/null\n+++ b/%s\n"
            "@@ -0,0 +1,%d @@\n%s" % (path, path, path, n, body))


def _state(root, diff, **cfg_over):
    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": diff, "fixerVendor": "claude",
           "repoRoot": str(root)}
    cfg.update(cfg_over)
    return RD.new_state(cfg)


def _session_dir(tmp_path):
    sdir = tmp_path / "session"
    (sdir / "round-1").mkdir(parents=True)
    return str(sdir)


def _placeholders(state, sdir, seat_key, channel=None):
    return RD._order_placeholders(RD.P_PANEL, seat_key, 0, state, state["config"], None, sdir, 1, {},
                                  channel or RD.CHANNEL_FILE)


def _slice_ids(state):
    return [s["id"] for s in state["slicePlan"]["slices"]]


def _files_of(text):
    return {s["file"] for s in cl.parse_sections(text)}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _three_thousand():
    return "".join(_added("pkg/f%d.py" % i, 1000) for i in range(3))


# --- the plan and the roster ---------------------------------------------------------------------------------------

def test_a_three_thousand_line_change_under_one_folder_seats_a_code_and_a_test_reviewer_per_slice(tmp_path):
    # FR-5
    state = _state(_repo(tmp_path), _three_thousand())
    plan = state["slicePlan"]
    assert plan["sliced"] is True and len(plan["slices"]) > 1
    assert all("diff" not in s for s in plan["slices"]), "the state keeps no per-slice diff text"
    roster = RP.panel_roster(state, state["config"])
    assert "code-reviewer" not in roster and "test-role" not in roster
    for sid in _slice_ids(state):
        assert "code-reviewer:" + sid in roster and "test-role:" + sid in roster
    whole = [d for d in RP.panel_dimensions(state["config"]) if d not in RP.SLICED_LENSES]
    assert roster[:len(whole)] == whole
    assert isinstance(state["sliceCount"], dict) or state["sliceCount"] is None


@pytest.mark.parametrize("lines", [BAR, BAR - 1], ids=["at-the-bar", "below-the-bar"])
def test_a_change_at_or_under_the_bar_keeps_the_configured_roster(tmp_path, lines):
    state = _state(_repo(tmp_path), _added("pkg/one.py", lines))
    assert state["slicePlan"]["sliced"] is False and state["slicePlan"]["slices"] == []
    assert RP.panel_roster(state, state["config"]) == RP.panel_dimensions(state["config"])
    assert RD._advance(state, state["config"])["payload"]["slices"] == []


def test_a_state_with_no_diff_text_stores_no_plan_and_keeps_the_roster(tmp_path):
    state = RD.new_state({"leg": "code", "vendors": ["claude", "codex"], "fixerVendor": "claude"})
    assert "slicePlan" not in state and "sliceCount" not in state
    assert RP.panel_roster(state, state["config"]) == RP.panel_dimensions(state["config"])


def test_a_later_round_of_a_sliced_change_seats_the_configured_roster(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    state["round"] = 2
    assert RP.panel_roster(state, state["config"]) == RP.panel_dimensions(state["config"])


def test_a_hand_made_plan_without_security_keys_seats_no_security_slice_seat(tmp_path):
    state = _state(_repo(tmp_path), _added("pkg/one.py", 3))
    state["slicePlan"] = {"sliced": True, "slices": [{"id": "s1", "parts": [{"file": "a.py", "lines": []}]},
                                                      {"id": "s2", "parts": [{"file": "b.py", "lines": []}]}]}
    roster = RP.panel_roster(state, state["config"])
    assert "code-reviewer:s1" in roster and "test-role:s2" in roster
    assert not [k for k in roster if k.startswith("security-reviewer")]


@pytest.mark.parametrize("key,lens", [
    ("code-reviewer", "code-reviewer"), ("code-reviewer:s1", "code-reviewer"), ("test-role:s12", "test-role"),
    ("verifier:abc", "verifier:abc"), ("nonsense:s1", "nonsense:s1"), ("", "")])
def test_seat_lens_reads_the_lens_of_a_slice_seat_key_and_leaves_any_other_key_alone(key, lens):
    assert RP.seat_lens(key) == lens


def test_the_panel_payload_names_the_cut(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    payload = RD._advance(state, state["config"])["payload"]
    roster = RP.panel_roster(state, state["config"])
    assert payload["dimensions"] == roster
    assert [s["id"] for s in payload["slices"]] == _slice_ids(state)
    for entry in payload["slices"]:
        # risk areas are not set here, so every slice also seats the security lens
        assert entry["seats"] == ["code-reviewer:" + entry["id"], "test-role:" + entry["id"],
                                  "security-reviewer:" + entry["id"]]


def test_the_premortem_reviewer_is_one_whole_change_seat_with_the_whole_diff_and_no_scope_line(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    roster = RP.panel_roster(state, state["config"])
    assert roster.count("premortem-reviewer") == 1
    assert not [k for k in roster if k.startswith("premortem-reviewer:")]
    sdir = _session_dir(tmp_path)
    ph = _placeholders(state, sdir, "premortem-reviewer")
    assert ph["DIFF_PATH"] == os.path.join(sdir, "round-1", "diff.txt")
    assert ph["SLICE_SCOPE_LINE"] == ""
    assert _read(ph["DIFF_PATH"]) == _three_thousand()


# --- security seating ----------------------------------------------------------------------------------------------

def _risk_diff():
    return _added(PAYMENTS, BAR - 100) + _added(OTHER, BAR + 100)


def test_a_slice_touching_a_configured_risk_area_gets_a_security_seat_and_one_that_does_not_gets_none(tmp_path):
    state = _state(_repo(tmp_path, RISK_AREAS), _risk_diff())
    slices = state["slicePlan"]["slices"]
    assert len(slices) > 1
    roster = RP.panel_roster(state, state["config"])
    touching = [s for s in slices if any(p["file"] == PAYMENTS for p in s["parts"])]
    clear = [s for s in slices if s not in touching]
    assert touching and clear
    for s in touching:
        assert s["security"] is True and "security-reviewer:" + s["id"] in roster
    for s in clear:
        assert s["security"] is False and "security-reviewer:" + s["id"] not in roster
    assert "security-reviewer" not in roster


def test_a_file_renamed_out_of_a_risk_area_still_gets_its_slice_a_security_seat(tmp_path):
    moved = "src/other/charge.py"
    rename = ("diff --git a/%s b/%s\nsimilarity index 90%%\nrename from %s\nrename to %s\nindex 1111111..2222222 100644\n"
              "--- a/%s\n+++ b/%s\n@@ -1,1 +1,2 @@\n ctx\n+added\n" % (PAYMENTS, moved, PAYMENTS, moved, PAYMENTS, moved))
    state = _state(_repo(tmp_path, RISK_AREAS), rename + _added(OTHER, BAR + 100))
    slices = state["slicePlan"]["slices"]
    assert len(slices) > 1
    holding = [s for s in slices if any(p["file"] == moved for p in s["parts"])]
    assert holding
    roster = RP.panel_roster(state, state["config"])
    for s in holding:
        assert s["security"] is True and "security-reviewer:" + s["id"] in roster


def test_with_risk_areas_not_set_every_slice_gets_a_security_seat(tmp_path):
    state = _state(_repo(tmp_path), _risk_diff())
    roster = RP.panel_roster(state, state["config"])
    assert state["slicePlan"]["slices"]
    for s in state["slicePlan"]["slices"]:
        assert s["security"] is True and "security-reviewer:" + s["id"] in roster


def test_a_panel_without_the_security_lens_seats_no_security_slice_seat(tmp_path):
    dims = [d for d in RP.DIMENSIONS if d != "security-reviewer"]
    state = _state(_repo(tmp_path), _risk_diff(), dimensions=dims)
    assert state["slicePlan"]["sliced"] is True
    roster = RP.panel_roster(state, state["config"])
    assert all(s["security"] is False for s in state["slicePlan"]["slices"])
    assert not [k for k in roster if k.startswith("security-reviewer")]
    assert "code-reviewer:s1" in roster


# --- what a slice seat is told -------------------------------------------------------------------------------------

def test_a_native_slice_seat_is_given_a_diff_holding_only_its_slice_and_a_scope_line_naming_its_parts(tmp_path):
    state = _state(_repo(tmp_path, RISK_AREAS), _risk_diff())
    sdir = _session_dir(tmp_path)
    for sl in state["slicePlan"]["slices"]:
        seat = "code-reviewer:" + sl["id"]
        ph = _placeholders(state, sdir, seat)
        assert os.path.dirname(ph["DIFF_PATH"]) == os.path.join(sdir, "round-1", "slices")
        text = _read(ph["DIFF_PATH"])
        files = {p["file"] for p in sl["parts"]}
        assert _files_of(text) == files
        # the delivered lines of each file are exactly the lines its part owns (a same-file chunk cannot stand in for another)
        delivered = {s["file"]: s["addedLines"] for s in cl.parse_sections(text)}
        for part in sl["parts"]:
            expected = [os.path.basename(part["file"]) + " line " + str(n - 1)
                        for start, end in part["lines"] for n in range(start, end + 1)]
            assert delivered[part["file"]] == expected
        assert ph["SLICE_SCOPE_LINE"].startswith("Your slice: %s. Review only these parts of the change" % sl["id"])
        for part in sl["parts"]:
            assert part["file"] in ph["SLICE_SCOPE_LINE"]
            for start, end in part["lines"]:
                assert "%d-%d" % (start, end) in ph["SLICE_SCOPE_LINE"]
    whole = _read(os.path.join(sdir, "round-1", "diff.txt"))
    assert _files_of(whole) == {PAYMENTS, OTHER}


def test_a_rendered_slice_seat_order_carries_the_scope_line_and_a_whole_change_seat_order_does_not(tmp_path):
    state = _state(_repo(tmp_path), _risk_diff())
    sdir = _session_dir(tmp_path)
    row = {"vendor": "claude", "model": None, "engine": None}
    sid = _slice_ids(state)[0]
    texts = {}
    for seat in ("code-reviewer:" + sid, "architecture-reviewer"):
        context, _paths = RD._build_order_render_context(sdir, state, 1, RD.P_PANEL, 0, seat, 0, {}, row)
        texts[seat], reason = RO.render_order(RD.P_PANEL, seat, context)
        assert reason is None, reason
    assert "Your slice: %s. Review only these parts of the change" % sid in texts["code-reviewer:" + sid]
    assert "Your slice:" not in texts["architecture-reviewer"]


def test_two_code_reviewer_slice_seats_write_findings_files_of_their_own(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    sdir = _session_dir(tmp_path)
    ids = _slice_ids(state)
    assert len(ids) > 1
    paths = [_placeholders(state, sdir, "code-reviewer:" + sid)["FINDINGS_OUTPUT_PATH"] for sid in ids]
    assert len(set(paths)) == len(paths)
    plain = _placeholders(state, sdir, "architecture-reviewer")["FINDINGS_OUTPUT_PATH"]
    assert os.path.basename(plain) == "findings-architecture.json"


def test_an_engine_slice_seat_keeps_the_reviewer_diff_and_is_narrowed_by_its_scope_line_alone(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    sdir = _session_dir(tmp_path)
    sid = _slice_ids(state)[0]
    ph = _placeholders(state, sdir, "code-reviewer:" + sid, channel=RD.CHANNEL_STDOUT)
    assert ph["DIFF_PATH"] == os.path.join(sdir, "round-1", "diff.txt")
    assert ph["SLICE_SCOPE_LINE"].startswith("Your slice: %s." % sid)
    assert not os.path.exists(os.path.join(sdir, "round-1", "slices"))


def test_a_slice_the_re_derived_plan_does_not_hold_falls_back_to_the_reviewer_diff_with_the_scope_line(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    state["slicePlan"]["slices"][0]["parts"] = [{"file": "pkg/elsewhere.py", "lines": []}]
    sdir = _session_dir(tmp_path)
    sid = state["slicePlan"]["slices"][0]["id"]
    ph = _placeholders(state, sdir, "code-reviewer:" + sid)
    assert ph["DIFF_PATH"] == os.path.join(sdir, "round-1", "diff.txt")
    assert "pkg/elsewhere.py" in ph["SLICE_SCOPE_LINE"]


# --- the seat map and the hand submit ------------------------------------------------------------------------------

def test_a_slice_seat_takes_its_lenss_vendor_from_the_seat_map(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    seat_map = {"seats": {"code-reviewer": {"vendor": "codex", "model": "m1", "engine": "codex"},
                          "test-role": {"vendor": "claude", "model": "m2", "engine": None}}}
    sid = _slice_ids(state)[0]
    assert RD._seat_map_configured_vendor(seat_map, "code-reviewer:" + sid) == "codex"
    assert RD._seat_map_configured_vendor(seat_map, "test-role:" + sid) == "claude"
    assert RD._seat_map_configured_vendor(seat_map, "premortem-reviewer") is None
    row = RD._seat_dispatch_row(state, "code-reviewer:" + sid, seat_map=seat_map)
    assert row == {"vendor": "codex", "model": "m1", "engine": "codex"}
    assert RD._seat_is_engine(row)


def test_a_hand_submit_keyed_by_the_sliced_roster_folds_and_a_key_outside_it_is_refused(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    roster = RP.panel_roster(state, state["config"])
    by_id = {sl["id"]: sl for sl in state["slicePlan"]["slices"]}
    seats = {key: {"findings": [], **({"readParts": by_id[key.partition(":")[2]]["parts"]} if RP.is_slice_seat(key) else {})}
             for key in roster}
    assert RD.panel_seat_key_fault(roster, {"seats": seats}) is None
    fault = RD.panel_seat_key_fault(roster, {"seats": dict(seats, **{"code-reviewer": {"findings": []}})})
    assert fault and "unknown seat key(s): code-reviewer" in fault
    RD._fold(state, state["config"], RD.P_PANEL, {"seats": seats})
    coverage = state["rounds"]["1"]["lensCoverage"]
    assert coverage == {"ran": len(roster), "expected": len(roster), "floor": False}
    assert state["step"] == RD.P_SEAMS
    assert set(state["rounds"]["1"]["seatStatus"]) == set(roster)


def test_a_slice_seat_left_out_of_a_hand_submit_folds_missing(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    roster = RP.panel_roster(state, state["config"])
    gone = "code-reviewer:" + _slice_ids(state)[0]
    seats = {key: {"findings": []} for key in roster if key != gone}
    RD._fold(state, state["config"], RD.P_PANEL, {"seats": seats})
    assert state["rounds"]["1"]["seatStatus"][gone] == "missing"
    assert state["rounds"]["1"]["lensCoverage"]["ran"] == len(roster) - 1


def test_an_unfilled_lens_rejects_every_one_of_its_slice_seats_even_with_a_valid_finding(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    roster = RP.panel_roster(state, state["config"])
    code_seats = [k for k in roster if k.startswith("code-reviewer:")]
    assert len(code_seats) > 1
    by_id = {sl["id"]: sl for sl in state["slicePlan"]["slices"]}
    finding = {"title": "ghost bug", "severity": "Important", "consequence": "A real consequence follows.",
               "file": "pkg/f0.py", "line": 1}
    seats = {key: {"findings": [dict(finding)] if key in code_seats else [],
                   **({"readParts": by_id[key.partition(":")[2]]["parts"]} if RP.is_slice_seat(key) else {})}
             for key in roster}
    ran = {"vendor": "claude", "model": "m", "source": "default"}
    seat_map = {"seats": {**{RP.seat_lens(k): dict(ran) for k in roster},
                          "code-reviewer": {"vendor": None, "model": None, "effort": None, "tier": "deep",
                                            "family": None, "source": "unfilled"}}}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    record = state["rounds"]["1"]
    for key in code_seats:
        assert record["seatStatus"][key] == "missing"
    assert not [f for f in state.get("_toVerify", []) if f.get("title") == "ghost bug"]
    assert not [f for f in state.get("_sliceCarry", []) if f.get("title") == "ghost bug"]
    assert state["fullPanelRan"] is False


def test_a_copy_out_of_a_risk_area_still_gets_its_slice_a_security_seat(tmp_path):
    moved = "src/other/charge.py"
    copy = ("diff --git a/%s b/%s\nsimilarity index 90%%\ncopy from %s\ncopy to %s\nindex 1111111..2222222 100644\n"
            "--- a/%s\n+++ b/%s\n@@ -1,1 +1,2 @@\n ctx\n+added\n" % (PAYMENTS, moved, PAYMENTS, moved, PAYMENTS, moved))
    assert RD._rename_sources(copy) == {moved: PAYMENTS}
    state = _state(_repo(tmp_path, RISK_AREAS), copy + _added(OTHER, BAR + 100))
    slices = state["slicePlan"]["slices"]
    holding = [s for s in slices if any(p["file"] == moved for p in s["parts"])]
    assert len(slices) > 1 and holding
    roster = RP.panel_roster(state, state["config"])
    for s in holding:
        assert s["security"] is True and "security-reviewer:" + s["id"] in roster


# --- a proven copy -------------------------------------------------------------------------------------------------

def test_a_proven_copy_in_a_sliced_change_is_named_in_no_slice_seats_order_or_scope_line(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "README.md").write_bytes(b"readme\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    base = _git(root, "rev-parse", "HEAD").strip()
    copy_path = "src/vendored/copy.py"
    copy_bytes = b"".join(b"copied %d\n" % i for i in range(1, 401))
    for rel, data in ((copy_path, copy_bytes),
                      ("src/a.py", b"".join(b"a %d\n" % i for i in range(700))),
                      ("src/b.py", b"".join(b"b %d\n" % i for i in range(700)))):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "head")
    diff = _git(root, "diff", base + "...HEAD")
    proof = {"schema": "copy-proof/1", "copies": [
        {"file": copy_path, "source": "vendor/orig.py", "sha256": hashlib.sha256(copy_bytes).hexdigest()}]}
    state = _state(root, diff, copyProof=proof)
    assert [c["file"] for c in state["provenCopies"]] == [copy_path]
    plan = state["slicePlan"]
    assert plan["sliced"] is True and len(plan["slices"]) > 1
    sdir = _session_dir(tmp_path)
    for sl in plan["slices"]:
        assert copy_path not in {p["file"] for p in sl["parts"]}
        for lens in ("code-reviewer", "test-role"):
            ph = _placeholders(state, sdir, "%s:%s" % (lens, sl["id"]))
            assert copy_path not in ph["SLICE_SCOPE_LINE"]
            assert copy_path not in _read(ph["DIFF_PATH"])


# --- the session record reads a slice seat by its lens ------------------------------------------------------------

@pytest.mark.parametrize("seat, listed", [("test-role", False), ("test-role:s1", False), ("code-reviewer:s1", True)],
                         ids=["whole-change-test-role", "slice-test-role", "slice-code-reviewer"])
def test_a_passed_break_it_proposal_from_a_test_role_slice_seat_is_settled_like_the_whole_change_seats(monkeypatch, seat,
                                                                                                    listed):
    import review_record_session as rs
    proposal = {"title": "boundary breaks", "file": "src/a.py", "line": 1, "taxonomy": "break-it-test",
                "severity": "Important", "consequence": "a bad input gets through"}
    monkeypatch.setattr(rs, "_raised_reports", lambda *a, **k: [(RP.P_PANEL, 1, seat, [proposal])])
    rounds = {"1": {"breakItRuns": [{"outcome": "passed", "title": "boundary breaks", "file": "src/a.py"}]}}
    rows = rs._unfolded("unused", [], rounds, [])
    assert [r["reviewer"] for r in rows] == ([seat] if listed else [])

