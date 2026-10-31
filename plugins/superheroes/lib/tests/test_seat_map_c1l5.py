# plugins/superheroes/lib/tests/test_seat_map_c1l5.py
"""The seat map (#2209, layer C1-L5): both specialists or neither (I1), no seat of any kind is filled
from a maker's family and the build session's own family is always a maker (I2), and the narrative
family is gone (I3)."""
import importlib.util
import inspect
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load():
    spec = importlib.util.spec_from_file_location("seat_map", os.path.join(_LIB, "seat_map.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SM = _load()

import core_md as CM
import lane_call as LC
import model_registry as MR
import receipt_disclosures as RD

THREE_VENDORS = ["claude", "codex", "cursor"]
SPECIALISTS = ("security-reviewer", "premortem-reviewer")
CLEAR_ROSTER = ("code-reviewer", "test-role")
_PAYMENTS = {
    "name": "Payments",
    "covers": ["src/payments/*"],
    "why": "Charges customers.",
    "undo": "Hard: a charge needs a refund.",
}
_GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
_CORE_FACTS = {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
               "patterns": "- x: a.ts:1"}


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo), *_GIT_ID, *args], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _project(tmp_path, monkeypatch, *, areas=None):
    """A git repo whose head commit adds src/payments/charge.py and docs/notes.md, with a core.md (in
    the store the env points at) holding the given risk areas. Returns (repo, store, base, head)."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    store = str(tmp_path / "store")
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "src" / "payments").mkdir(parents=True)
    (repo / "src" / "payments" / "charge.py").write_text("x = 1\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "notes.md").write_text("notes\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    head = _git(repo, "rev-parse", "HEAD")
    CM.write(str(repo), dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    if areas is not None:
        assert CM.write_project_config_item(str(repo), CM.RISK_AREAS_KEY, areas, root=store)["action"] == "written"
    return str(repo), store, base, head


def _docs_commit(repo):
    """A commit on top of the head that changes only docs/other.md; returns (parent, sha)."""
    parent = _git(repo, "rev-parse", "HEAD")
    with open(os.path.join(repo, "docs", "other.md"), "w") as fh:
        fh.write("other\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "docs")
    return parent, _git(repo, "rev-parse", "HEAD")


def _compose(capsys, *argv):
    capsys.readouterr()
    assert SM.main(["x", "compose", *argv]) == 0
    return json.loads(capsys.readouterr().out)


def _both_or_neither(roster):
    seated = [s in roster for s in SPECIALISTS]
    assert seated[0] == seated[1], roster
    return seated[0]


# --- I1: both specialists or neither ---


def test_i1_a_change_touching_one_risk_area_seats_both_specialists(tmp_path, monkeypatch):
    # axis: touching a risk area seats the security AND the premortem reviewer — never one alone
    repo, store, _base, _head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    basis = LC.call(repo, ["src/payments/charge.py"], proposed="full", root=store)
    assert basis["floor"] == "full" and [t["name"] for t in basis["touched"]] == ["Payments"]
    roster = SM.roster_for(basis)
    assert all(s in roster for s in SPECIALISTS)
    assert set(roster) == set(CLEAR_ROSTER) | set(SPECIALISTS)


def test_i1_a_project_with_no_risk_areas_set_seats_both_specialists(tmp_path, monkeypatch):
    # axis: risk areas not set means risk is unclear, so both specialists are seated
    repo, store, _base, _head = _project(tmp_path, monkeypatch)
    basis = LC.call(repo, ["docs/notes.md"], proposed="full", root=store)
    assert basis["floor"] == "full" and basis["riskAreas"]["state"] != "set"
    roster = SM.roster_for(basis)
    assert all(s in roster for s in SPECIALISTS)


def test_i1_a_clear_change_touching_no_area_seats_neither_specialist(tmp_path, monkeypatch):
    # axis: a clear change that touches no area seats exactly the code reviewer and the test role
    repo, store, _base, _head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    basis = LC.call(repo, ["docs/notes.md"], proposed="full", root=store)
    assert basis["floor"] is None
    roster = SM.roster_for(basis)
    assert len(roster) == 2 and set(roster) == set(CLEAR_ROSTER)
    assert not any(s in roster for s in SPECIALISTS)


def test_i1_no_basis_seats_one_specialist_without_the_other(tmp_path, monkeypatch):
    # axis: across every way a floor comes out (and the unreadable bases) the specialists come as a pair
    repo, store, _base, _head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    unset = tmp_path / "unset"
    unset_repo, unset_store, _b, _h = _project(unset, monkeypatch)
    # the env points at the last project's store; every call below names its root
    bases = {
        "touches": (LC.call(repo, ["src/payments/charge.py"], proposed="full", root=store), True),
        "not-set": (LC.call(unset_repo, ["docs/notes.md"], proposed="full", root=unset_store), True),
        "unmatchable": (LC.call(repo, ["/abs/outside.py"], proposed="full", root=store), True),
        "no-paths": (LC.call(repo, [], proposed="full", root=store), True),
        "unavailable": (LC.unavailable("lane-basis-unavailable: test", proposed="full"), True),
        "clear": (LC.call(repo, ["docs/notes.md"], proposed="full", root=store), False),
        "none": (None, True),
        "empty": ({}, True),
        "no-floor-key": ({"lane": "full"}, True),
    }
    for name, (basis, want_specialists) in bases.items():
        assert _both_or_neither(SM.roster_for(basis)) is want_specialists, name


def test_i1_compose_seats_the_rosters_the_lane_call_names(tmp_path, monkeypatch, capsys):
    # axis: compose (the public path) composes the same rosters roster_for names for the same change
    repo, _store, base, head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    live = ["--live-vendors", "claude,codex,cursor", "--author-family", "xai", "--pr-number", "1",
            "--repo-root", repo]
    touched = _compose(capsys, *live, "--base-ref", base, "--head-sha", head)
    assert tuple(touched["roster"]) == SM.PANEL_ROSTER and set(touched["seats"]) == set(SM.PANEL_ROSTER)
    assert all(s in touched["seats"] for s in SPECIALISTS)

    parent, docs_head = _docs_commit(repo)
    clear = _compose(capsys, *live, "--base-ref", parent, "--head-sha", docs_head)
    assert len(clear["roster"]) == 2 and set(clear["roster"]) == set(CLEAR_ROSTER)
    assert set(clear["seats"]) == set(CLEAR_ROSTER)

    unset_repo, _unset_store, ubase, uhead = _project(tmp_path / "unset", monkeypatch)
    unset = _compose(capsys, "--live-vendors", "claude,codex,cursor", "--author-family", "xai",
                     "--pr-number", "1", "--repo-root", unset_repo, "--base-ref", ubase, "--head-sha", uhead)
    assert tuple(unset["roster"]) == SM.PANEL_ROSTER
    assert all(s in unset["seats"] for s in SPECIALISTS)


# --- I2: no seat of any kind is filled from a maker's family ---


def _filled_families(seat_map):
    return {e["family"] for e in seat_map["seats"].values() if e["source"] != SM.UNFILLED_SOURCE}


def test_i2_reviewer_seats_never_take_a_maker_family():
    # axis: every panel lens seat — (a) a live independent family fills it, never a maker's; (b) none live reads unfilled
    makers = {"xai", "openai"}
    seated = SM.build(SM.KNOWN_SEATS, THREE_VENDORS, "xai", 0, extra_maker_families=frozenset({"openai"}))
    assert seated["makerFamilies"] == sorted(makers)
    assert set(seated["seats"]) == set(SM.KNOWN_SEATS)
    for seat, entry in seated["seats"].items():
        assert entry["family"] not in makers, seat
    assert _filled_families(seated) == {"anthropic"}

    only_makers = SM.build(SM.KNOWN_SEATS, ["codex", "cursor"], "xai", 0, extra_maker_families=frozenset({"openai"}))
    assert set(only_makers["seats"]) == set(SM.KNOWN_SEATS)
    for seat, entry in only_makers["seats"].items():
        assert entry["source"] == SM.UNFILLED_SOURCE and entry["family"] is None, seat
        assert entry.get("vendor") is None, seat


def test_i2_test_reviewer_run_seat_never_takes_a_maker_family():
    # axis: the test-role seat (a fresh run of the test reviewer is seated through it)
    seated = SM.build(("test-role",), THREE_VENDORS, "xai", 0, extra_maker_families=frozenset({"openai"}))
    entry = seated["seats"]["test-role"]
    assert entry["source"] != SM.UNFILLED_SOURCE and entry["family"] == "anthropic"

    only_makers = SM.build(("test-role",), ["codex", "cursor"], "xai", 0, extra_maker_families=frozenset({"openai"}))
    entry = only_makers["seats"]["test-role"]
    assert entry["source"] == SM.UNFILLED_SOURCE and entry["family"] is None and entry.get("vendor") is None


def _nonpanel_map(role, vendors, host_family):
    cells = []
    for v in vendors:
        cell = MR.matrix_config(role, v)
        if cell is not None:
            cells.append([v, cell[0], cell[1]])
    return {"nonPanelLiveCells": cells, "nonPanelLiveCellsSource": "synthesized", "hostFamily": host_family}


@pytest.mark.parametrize("role", ["verifier", "reviewer-deep"], ids=["verifier", "scoped-finder"])
def test_i2_nonpanel_reviewer_never_takes_a_maker_family(role):
    # axis: the verifier and the scoped finder — (a) an independent family is picked, never a maker's; (b) none reads (None, None)
    config = {"vendors": ["claude", "codex"]}
    seat_map_ = _nonpanel_map(role, ["claude", "codex"], "anthropic")
    # (a) the host (anthropic) is a maker: the codex reviewer is picked even when claude is preferred
    vendor, family = RD.nonpanel_reviewer(config, seat_map_, role, "claude", maker_families=frozenset({"anthropic"}))
    assert (vendor, family) == ("codex", "openai")
    # (a) the other maker: the host seat is picked, and it carries the host family
    vendor, family = RD.nonpanel_reviewer(config, seat_map_, role, "codex", maker_families=frozenset({"openai"}))
    assert (vendor, family) == ("claude", "anthropic")
    # (b) only maker families are live
    assert RD.nonpanel_reviewer(config, seat_map_, role, "claude",
                                maker_families=frozenset({"anthropic", "openai"})) == (None, None)


def test_i2_fix_auditor_never_takes_a_maker_family():
    # axis: the fix auditor — (a) an auditor outside every maker family is picked; (b) none live leaves no auditor vendor
    config = {"vendors": ["claude", "codex"]}
    vendor, _fixer_family = RD.independent_auditor(config, "claude", maker_families=frozenset({"anthropic"}))
    assert vendor == "codex" and MR.family_for("auditor", vendor) == "openai"
    vendor, _fixer_family = RD.independent_auditor(config, "codex", maker_families=frozenset({"openai"}))
    assert vendor == "claude" and MR.family_for("auditor", vendor) == "anthropic"
    vendor, _fixer_family = RD.independent_auditor(config, "claude", maker_families=frozenset({"anthropic", "openai"}))
    assert vendor is None


def test_i2_codex_engine_on_an_anthropic_host_keeps_both_families_off_every_seat(capsys):
    # axis: the build session applies the fixes, so its family is a maker on every implementation engine
    receipt = _compose(capsys, "--live-vendors", "claude,codex", "--implementation-engine", "codex",
                       "--host-model", "claude-opus-5", "--pr-number", "2209")
    assert receipt["authorFamily"] == "openai" and receipt["hostFamily"] == "anthropic"
    assert receipt["makerFamilies"] == ["anthropic", "openai"]
    assert set(receipt["seats"]) == set(SM.PANEL_ROSTER)
    for seat, entry in receipt["seats"].items():
        assert entry["source"] == SM.UNFILLED_SOURCE and entry["family"] is None, seat
    assert [d["constraint"] for d in receipt["degradations"] if d["constraint"] == "maker-family-split"] == [
        "maker-family-split"]
    assert not any(d["constraint"] == "host-model-unknown" for d in receipt["degradations"])
    # the pickers that read the receipt's makers bar both families too
    makers = RD.maker_families(receipt)
    assert RD.independent_auditor({"vendors": ["claude", "codex"]}, "codex", maker_families=makers)[0] is None
    assert RD.nonpanel_reviewer({"vendors": ["claude", "codex"]}, receipt, "verifier", "claude",
                                maker_families=makers) == (None, None)


def test_i2_codex_engine_with_an_unknown_host_keeps_the_claude_fallback_family_off_every_seat(capsys):
    # axis: an unknown host model falls back to the claude host family, which is a maker
    receipt = _compose(capsys, "--live-vendors", "claude,codex", "--implementation-engine", "codex",
                       "--host-model", "", "--pr-number", "2209")
    assert receipt["authorFamily"] == "openai" and receipt["hostFamily"] is None
    assert receipt["makerFamilies"] == ["anthropic", "openai"]
    for seat, entry in receipt["seats"].items():
        assert entry["source"] == SM.UNFILLED_SOURCE and entry["family"] is None, seat
    assert len([d for d in receipt["degradations"] if d["constraint"] == "host-model-unknown"]) == 1


def test_i2_codex_engine_on_a_codex_host_adds_no_second_maker(capsys):
    # axis: the host family joins the makers only when it differs from the author family
    receipt = _compose(capsys, "--live-vendors", "claude,codex", "--implementation-engine", "codex",
                       "--host-model", "gpt-6.1-sol", "--pr-number", "2209")
    assert receipt["makerFamilies"] == ["openai"]
    assert not any(d["constraint"] == "maker-family-split" for d in receipt["degradations"])
    assert _filled_families(receipt) == {"anthropic"}


def test_i2_a_third_family_is_still_seated_beside_the_two_makers(capsys):
    # axis: (a) with an independent family live, the seats are filled from it alone; (b) no seat is left unfilled
    receipt = _compose(capsys, "--live-vendors", "claude,codex,cursor", "--implementation-engine", "codex",
                       "--host-model", "claude-opus-5", "--pr-number", "2209")
    assert receipt["makerFamilies"] == ["anthropic", "openai"]
    assert _filled_families(receipt) == {"xai"}
    assert set(receipt["seats"]) == set(SM.PANEL_ROSTER)
    unfilled = [seat for seat, entry in receipt["seats"].items() if entry["source"] == SM.UNFILLED_SOURCE]
    assert unfilled == [], unfilled
    assert [d for d in receipt["degradations"] if d["constraint"] == "seat-unfilled"] == []
    # every recorded maker family is out of the achievable set: no false constraint breach
    assert SM.classify_violations(receipt)["unexcused"] == []


# --- I3: the narrative family is removed ---


def test_i3_build_and_receipt_carry_no_narrative_family():
    built = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", 0)
    assert "narrativeFamily" not in built and "narrativeFamily" not in SM.to_receipt(built)
    assert "narrative_family" not in inspect.signature(SM.build).parameters
    # a map an older version stored still reads, and its key is not carried forward
    older = dict(built, narrativeFamily="openai")
    assert "narrativeFamily" not in SM.to_receipt(older)
    assert SM.to_receipt(older)["authorFamily"] == "xai"


def test_i3_the_narrative_family_flag_is_refused(capsys):
    with pytest.raises(SystemExit) as exc:
        SM.main(["x", "compose", "--live-vendors", "claude", "--author-family", "xai",
                 "--narrative-family", "anthropic"])
    assert exc.value.code != 0
    assert "--narrative-family" in capsys.readouterr().err
