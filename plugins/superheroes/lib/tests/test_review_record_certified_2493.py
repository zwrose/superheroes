"""A certified review means the change is low-risk to merge (#2493, #2494).

An open finding (left for the owner, or with no outcome) withholds the certificate exactly when it is Important,
Critical, of unknown severity, or a Minor or Nit whose risk reading is not exactly False (False: risk areas are
declared and none covers it, or the project's core.md declares none (no `riskAreas` key or an empty list); None: no
calibration file can be found, or the risk cannot be read). The record, its `leftForOwner` list, its
awaits-owner test, the carry rule and the leftover-accepting check all ask the same two predicates in
`review_record.py`. CI no longer decides the certificate; the record still carries it.
"""
import ast
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

import leftover_accepting as la
import review_record as rr
import test_review_record_owner_ruling as ruling
from test_review_record import PENDING, RED, Fake, account, build, finding, reviewer

LIB = Path(__file__).resolve().parents[1]
LEFT = {"outcome": "left-for-owner", "reason": "needs owner"}
NO_OUTCOME = {"outcome": None}
SHA = "a" * 40


class Certified(Fake):
    """A Fake whose withheld-path reader names nothing withheld and whose per-finding risk reader answers `risk`."""

    def __init__(self, risk=False, withheld=(), **kw):
        super().__init__(**kw)
        self.risk, self.withheld = risk, list(withheld)

    def readers(self):
        return {**super().readers(), "withheld_paths": lambda root, sha, paths: list(self.withheld),
                "finding_risk": lambda root, file: self.risk}


AREA = {"name": "Auth", "covers": ["src" + "/auth"], "why": "Holds sign-in.", "undo": "Hard: a leak stays out."}
CORE_BASE = '{"schemaVersion": 2, "verifyCommand": "npm test", "stackTags": ["node"], "projectConfiguration": %s}'


def git_repo(path):
    """An empty git repository at `path`, made with no user or system git configuration."""
    path.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=env)
    return path


def write_core(root, project_configuration):
    """A confirmed core.md under `root` whose `projectConfiguration` block is the given JSON text."""
    d = root / ".claude" / "superheroes"
    d.mkdir(parents=True)
    (d / "core.md").write_text(
        "<!-- superheroes-core: schemaVersion=2 status=confirmed created=2026-06-26 updated=2026-06-26 -->\n\n"
        "## Threat model\n\nsingle-user\n\n## Canonical patterns\n\n- x: a.ts:1\n\n"
        "```json superheroes-core\n%s\n```\n" % (CORE_BASE % project_configuration), encoding="utf-8")
    return str(root)


def acct(tmp_path, findings, **over):
    return account(repoRoot=str(tmp_path), findings=findings, **over)


def minor_nit():
    return [finding("f1", severity="Minor", **LEFT), finding("f2", severity="Nit", **LEFT)]


# --- the certificate lists a low-risk leftover, and withholds on a risk one -------------------------------------------

def test_1_a_minor_and_a_nit_outside_every_risk_area_are_listed_and_the_record_reads_reviewed(tmp_path):
    """axis: DoD-listed; a Minor or Nit left for the owner outside every declared risk area withholding the certificate."""
    rec = build(acct(tmp_path, minor_nit()), Certified(risk=False))
    assert rec["status"] == rr.REVIEWED and rec["whatIsMissing"] == []
    assert rec["leftForOwner"] == []
    assert rec["listedForMerge"] == ["f1", "f2"]
    keys = list(rec)
    assert keys.index("listedForMerge") == keys.index("leftForOwner") + 1
    text = rr.render(rec)
    assert ("Listed for the merge verdict (Minor or Nit, outside every declared risk area): f1, f2." in text)
    assert "Nothing waits for the owner." in text
    assert "listed for the merge verdict" not in rr._summary(dict(rec, listedForMerge=[]), 0).lower()
    compact = rr._summary(rec, 1)
    assert f"Listed for the merge verdict: 2 findings {rr.LISTED}." in compact


def test_2_a_minor_in_a_declared_risk_area_stays_a_card(tmp_path):
    """axis: DoD-risk; a Minor in a declared risk area being listed instead of waiting for the owner."""
    rec = build(acct(tmp_path, [finding("f1", severity="Minor", **LEFT)]), Certified(risk=True))
    assert rec["status"] == rr.AWAITS_OWNER
    assert rec["leftForOwner"] == ["f1"] and rec["listedForMerge"] == []
    assert rec["whatIsMissing"] == [rr.leftover_line(rec["findings"][0])]
    assert rec["findings"][0]["inRiskArea"] is True


def test_3_a_minor_of_unknown_risk_stays_a_card(tmp_path):
    """axis: unknown risk; a Minor whose risk could not be read being listed, as if it were outside every risk area."""
    rec = build(acct(tmp_path, [finding("f1", severity="Minor", **LEFT)]), Certified(risk=None))
    assert rec["status"] == rr.AWAITS_OWNER
    assert rec["leftForOwner"] == ["f1"] and rec["listedForMerge"] == []
    assert rec["findings"][0]["inRiskArea"] is None


@pytest.mark.parametrize("stamp", [{}, {"inRiskArea": None}])
def test_4_an_earlier_record_with_no_stamp_is_not_listed(stamp):
    """axis: the stamp is exactly False; a finding of an earlier record with no stamp (or a null one) being listed."""
    f = {"id": "f1", "severity": "Minor", "outcome": "left-for-owner", **stamp}
    assert rr.listed_for_merge(f) is False
    assert rr.waits_for_owner(f, [f]) is True
    assert rr.listed_for_merge(dict(f, inRiskArea=False)) is True
    assert rr.waits_for_owner(dict(f, inRiskArea=False), [dict(f, inRiskArea=False)]) is False
    assert rr.listed_for_merge("not a finding") is False


def test_5_an_account_value_for_inriskarea_is_ignored(tmp_path):
    """axis: the writer's own stamp; an account's inRiskArea value being trusted over the risk reader."""
    own = finding("f1", severity="Minor", inRiskArea=False, **LEFT)
    rec = build(acct(tmp_path, [own]), Certified(risk=True))
    assert rec["findings"][0]["inRiskArea"] is True
    assert rec["status"] == rr.AWAITS_OWNER and rec["leftForOwner"] == ["f1"]


def test_6_the_production_reader_asks_the_one_risk_area_reader(tmp_path):
    """axis: the production risk reader; a file in a declared area read as outside it, or a fault read as outside it."""
    declared = tmp_path / "declared"
    declared.mkdir()
    root = write_core(declared, '{"riskAreas": [%s]}' % json.dumps(AREA))
    assert rr._finding_risk(root, "src/auth/login.py") is True
    assert rr._finding_risk(root, "docs/readme.md") is False
    assert rr._finding_risk(root, "../x") is None
    empty = tmp_path / "empty"
    empty.mkdir()
    assert rr._finding_risk(write_core(empty, '{"riskAreas": []}'), "src/auth/login.py") is False
    nokey = tmp_path / "nokey"
    nokey.mkdir()
    assert rr._finding_risk(write_core(nokey, "{}"), "src/auth/login.py") is False
    # a git repository holding no core.md: the calibration cannot be found, so the risk is unknown, never "declares none"
    bare = git_repo(tmp_path / "bare")
    assert rr._finding_risk(str(bare), "src/auth/login.py") is None
    broken = tmp_path / "broken"
    broken.mkdir()
    assert rr._finding_risk(write_core(broken, '["risk"]'), "src/auth/login.py") is None
    assert rr._finding_risk(root, None) is None
    assert rr._finding_risk(root, "") is None
    assert rr._finding_risk(None, "src/auth/login.py") is None
    assert rr._finding_risk("", "src/auth/login.py") is None


def test_7_an_important_finding_whose_decision_is_on_record_is_decided_and_the_record_reads_reviewed(tmp_path):
    """axis: DoD-decision; an Important finding with a decision on record still waiting, or a ruled one withholding."""
    def readers(**kw):
        return {**ruling.readers(**kw), "withheld_paths": lambda root, sha, paths: []}

    base = {**ruling.account([ruling.entry()]), "lane": "full", "laneReason": "the change touches the review record",
            "makers": [{"family": "anthropic"}], "reviewers": [reviewer("r1")], "repoRoot": str(tmp_path)}
    rec = rr.build_record(base, readers())
    (f,) = rec["findings"]
    assert f["severity"] == "Important" and f["outcome"] == "ruling"
    assert rec["status"] == rr.REVIEWED and rec["leftForOwner"] == [] and rec["whatIsMissing"] == []


@pytest.mark.parametrize("severity", ["Important", "Critical"])
def test_8_an_important_or_critical_finding_left_for_the_owner_waits_whatever_its_risk_reading(tmp_path, severity):
    """axis: DoD-important; an Important or Critical finding left for the owner being listed when it is outside every risk area."""
    rec = build(acct(tmp_path, [finding("f1", severity=severity, **LEFT)]), Certified(risk=False))
    assert rec["status"] == rr.AWAITS_OWNER
    assert rec["leftForOwner"] == ["f1"] and rec["listedForMerge"] == []
    assert rec["whatIsMissing"] == [rr.leftover_line(rec["findings"][0])]


@pytest.mark.parametrize("severity", ["Minor", "Nit"])
def test_9_a_minor_with_no_outcome_is_listed_outside_a_risk_area_and_a_card_inside_one(tmp_path, severity):
    """axis: 2494 no-outcome Minor; an unsettled Minor or Nit outside every risk area withholding, or one inside a risk area listed."""
    f = finding("f1", severity=severity, reason=None, **NO_OUTCOME)
    out = build(acct(tmp_path, [f]), Certified(risk=False))
    assert out["status"] == rr.REVIEWED and out["whatIsMissing"] == []
    assert out["listedForMerge"] == ["f1"] and out["leftForOwner"] == []
    inside = build(acct(tmp_path, [f]), Certified(risk=True))
    assert inside["status"] == rr.AWAITS_OWNER
    assert inside["whatIsMissing"] == [rr.leftover_line(inside["findings"][0])]
    assert inside["leftForOwner"] == ["f1"] and inside["listedForMerge"] == []
    assert not [m for rec in (out, inside) for m in rec["whatIsMissing"] if "has no outcome" in m]


@pytest.mark.parametrize("severity", ["Important", "Critical"])
def test_10_an_important_or_critical_finding_with_no_outcome_keeps_its_line_and_the_record_not_reviewed(tmp_path, severity):
    """axis: 2494 no-outcome Important; an unsettled Important or Critical finding being listed or read as a card."""
    rec = build(acct(tmp_path, [finding("f1", severity=severity, reason=None, **NO_OUTCOME)]), Certified(risk=False))
    assert rec["status"] == rr.NOT_REVIEWED
    assert "finding f1 has no outcome" in rec["whatIsMissing"]
    assert rec["leftForOwner"] == [] and rec["listedForMerge"] == []


def test_11_a_minor_with_no_reason_adds_a_line_only_inside_a_risk_area(tmp_path):
    """axis: no reason; a fixed Minor outside every risk area withholding for a blank reason, or one inside a risk area passing."""
    f = finding("f1", severity="Minor", outcome="fixed", reason="")
    out = build(acct(tmp_path, [f]), Certified(risk=False))
    assert out["whatIsMissing"] == [] and out["status"] == rr.REVIEWED
    inside = build(acct(tmp_path, [f]), Certified(risk=True))
    assert inside["whatIsMissing"] == ["finding f1 has no reason"] and inside["status"] == rr.NOT_REVIEWED
    important = build(acct(tmp_path, [dict(f, severity="Important")]), Certified(risk=False))
    assert important["whatIsMissing"] == ["finding f1 has no reason"]


def test_12_a_repeat_of_a_listed_finding_keeps_its_own_card(tmp_path):
    """axis: repeat holding; a listed Minor holding the owner's one card for an Important repeat of it."""
    earlier = finding("e", severity="Minor", findingKey="e-key", **LEFT)
    repeat = finding("r", severity="Important", findingKey="r-key", repeatOf={"findingKey": "e-key", "id": None, "fixHolds": None}, **LEFT)
    rec = build(acct(tmp_path, [earlier, repeat]), Certified(risk=False))
    assert rec["listedForMerge"] == ["e"]
    assert rec["leftForOwner"] == ["r"]
    assert rec["whatIsMissing"] == [rr.leftover_line(repeat)]
    assert rec["status"] == rr.AWAITS_OWNER
    held = rec["findings"]
    assert rr.repeat_held_elsewhere(held[1], held) is False
    both = build(acct(tmp_path, [dict(earlier, severity="Important"), repeat]), Certified(risk=False))
    assert both["leftForOwner"] == ["e"]


@pytest.mark.parametrize("ci, state, source", [(RED, "red", "GitHub checks"), (PENDING, "pending", "GitHub checks"),
                                               (None, "none", "unavailable")], ids=["red", "pending", "unavailable"])
def test_13_ci_is_not_part_of_the_certificate_but_the_record_still_carries_it(tmp_path, ci, state, source):
    """axis: CI out of the certificate; a red, pending or unread CI withholding the record, or the CI reading dropped."""
    rec = build(acct(tmp_path, []), Certified(ci=ci))
    assert rec["status"] == rr.REVIEWED and rec["whatIsMissing"] == []
    assert not [m for m in rec["whatIsMissing"] if m.startswith("CI ")]
    assert not [c for c in rec["checked"] if c.startswith("CI on")]
    assert rec["checked"][0].startswith("Reviewers that ran: ")
    assert "CI on the final commit" not in rr.render(rec)
    assert rec["ci"]["state"] == state and rec["ci"]["source"] == source


def test_14_the_carry_rule_admits_a_listed_or_waiting_finding_and_refuses_an_important_with_no_outcome():
    """axis: carry; an earlier Important or Critical finding with no outcome carried as settled, or a Minor with none refused."""
    def decide(*args, **kwargs):
        return {"read": rr.returning_review.READ_CHANGED, "changedFiles": [], "why": []}

    def ask(*findings):
        prior = {"finalCommit": {"sha": SHA}, "findings": list(findings),
                 "reviewers": [{"name": "r", "ran": rr.RAN_ENGINE_RECORD, "coversFinalCommit": True}]}
        return rr.carry_refusal(prior, SHA, "/r", "b" * 40, "c" * 40, [], decide)

    minor = {"id": "m", "severity": "Minor", "file": "a.py", "outcome": None}
    assert ask(minor) is None
    assert ask(dict(minor, inRiskArea=False)) is None
    assert ask(dict(minor, inRiskArea=True)) is None
    assert ask(dict(minor, severity="Nit")) is None
    for severity in ("Important", "Critical", "Strange"):
        assert ask(dict(minor, severity=severity)) == "an earlier finding is still open"
        assert ask(dict(minor, severity=severity, inRiskArea=False)) == "an earlier finding is still open"
    assert ask(dict(minor, severity=None)) == "an earlier finding is still open"
    assert ask(minor, dict(minor, id="i", severity="Important")) == "an earlier finding is still open"


def test_15_the_leftover_check_asks_for_the_waiting_set_only():
    """axis: leftover accepting; a no-outcome risk-area Minor going unasked, or a listed Minor still being asked for."""
    waiting = {"id": "f1", "title": "Slow retry", "severity": "Minor", "outcome": None, "inRiskArea": True}
    assert la.missing({"ok": True, "findings": [waiting], "leftForOwner": ["f1"]}, "") == [{"id": "f1", "title": "Slow retry"}]
    listed = dict(waiting, outcome="left-for-owner", inRiskArea=False)
    with pytest.raises(la.Unreadable) as raised:
        la.missing({"ok": True, "findings": [listed], "leftForOwner": ["f1"]}, "")
    assert "names no finding left for the owner" in str(raised.value)


def test_16_no_site_pairs_the_left_for_owner_outcome_with_the_repeat_test_outside_the_predicates():
    """axis: the one-home census; a copy of the awaits-owner test reading the outcome and the repeat holder on its own."""
    homes = ("listed_for_merge", "waits_for_owner", "repeat_held_elsewhere")
    pair = re.compile(r"_LEFT_FOR_OWNER[\s\S]{0,120}?repeat_held_elsewhere")
    copies, found = [], []
    for name in ("review_record.py", "leftover_accepting.py"):
        text = (LIB / name).read_text(encoding="utf-8")
        lines = text.split("\n")
        for node in ast.parse(text).body:
            if isinstance(node, ast.FunctionDef) and node.name in homes:
                found.append(node.name)
                for n in range(node.lineno - 1, node.end_lineno):
                    lines[n] = ""
        rest = "\n".join(lines)
        copies += [f"{name}:{rest.count(chr(10), 0, m.start()) + 1}" for m in pair.finditer(rest)]
    assert copies == []
    assert sorted(found) == sorted(homes)


@pytest.mark.parametrize("reason", [None, "still open when the review loop ended"])
def test_17_an_owner_ruling_on_a_no_outcome_minor_card_settles_it(tmp_path, reason):
    """axis: E-ruling-card; a valid owner ruling on a no-outcome Minor card left unapplied, so the card keeps waiting."""
    def readers(**kw):
        return {**ruling.readers(**kw), "withheld_paths": lambda root, sha, paths: [], "finding_risk": lambda root, file: True}

    card = dict(ruling.X, severity="Minor", outcome=None, reason=reason)
    base = {**ruling.account([ruling.entry()], findings=[card]), "lane": "full", "laneReason": "the review record",
            "makers": [{"family": "anthropic"}], "reviewers": [reviewer("r1")], "repoRoot": str(tmp_path)}
    rec = rr.build_record(base, readers())
    (f,) = rec["findings"]
    assert f["outcome"] == "ruling" and f["decidedBy"]["kind"] == "owner-ruling"
    assert rec["status"] == rr.REVIEWED and rec["leftForOwner"] == [] and rec["whatIsMissing"] == []
    # without the ruling the same card waits for the owner
    bare = rr.build_record({**base, "ownerRulings": []}, readers())
    assert bare["leftForOwner"] == ["f-1"] and bare["status"] == rr.AWAITS_OWNER


def test_17b_an_owner_ruling_on_a_no_outcome_important_leaves_it_open(tmp_path):
    """axis: E-ruling-card; the conversion reaching an Important with no outcome, which is a missing outcome, not a card."""
    def readers(**kw):
        return {**ruling.readers(**kw), "withheld_paths": lambda root, sha, paths: [], "finding_risk": lambda root, file: True}

    open_important = dict(ruling.X, outcome=None)
    base = {**ruling.account([ruling.entry()], findings=[open_important]), "lane": "full", "laneReason": "the review record",
            "makers": [{"family": "anthropic"}], "reviewers": [reviewer("r1")], "repoRoot": str(tmp_path)}
    rec = rr.build_record(base, readers())
    (f,) = rec["findings"]
    assert f["outcome"] is None and rec["status"] == rr.NOT_REVIEWED
    assert "finding f-1 has no outcome" in rec["whatIsMissing"]


def test_18_a_project_whose_calibration_cannot_be_found_keeps_a_minor_as_a_card(tmp_path):
    """axis: E-absent; a repository with no core.md read as declaring no risk area, so its Minor is listed, not a card.
    The readers carry no `finding_risk`, so `rr._readers` supplies the production reader (`rr._finding_risk`)."""
    def readers():
        got = Certified().readers()
        del got["finding_risk"]
        return got

    minor = [finding("f1", severity="Minor", **LEFT)]
    no_core = git_repo(tmp_path / "no_core")
    rec = rr.build_record(account(repoRoot=str(no_core), findings=minor), readers())
    assert rec["findings"][0]["inRiskArea"] is None
    assert rec["status"] == rr.AWAITS_OWNER
    assert rec["leftForOwner"] == ["f1"] and rec["listedForMerge"] == []
    no_key = git_repo(tmp_path / "no_key")
    write_core(no_key, "{}")
    rec = rr.build_record(account(repoRoot=str(no_key), findings=minor), readers())
    assert rec["findings"][0]["inRiskArea"] is False
    assert rec["status"] == rr.REVIEWED and rec["whatIsMissing"] == []
    assert rec["leftForOwner"] == [] and rec["listedForMerge"] == ["f1"]
