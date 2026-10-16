"""The dry run of carrying a Merge forward: two PRs are published, answered and given a Merge, then brought current from main.

Everything goes through the commands' own `main`: `pr_sheet.py build` publishes each sheet (and republishes it with
`carriedForward`, or with `previousCommit` alone after a material fix), and `pr_sheet.py index` reads the sheets with their
store dumps. The rows of the index and `pr_state` must agree on every PR.
"""
import hashlib
import json
import shutil
from pathlib import Path

import pytest

import pr_sheet

LIB = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pr_sheet"
WORDS = json.loads((LIB.parent / "theme" / "sheet-words.json").read_text(encoding="utf-8"))
PRS = {211: ("record-small.json", "input-small.json"), 214: ("record-big.json", "input-big.json")}
BROUGHT_CURRENT = {"moved": "the branch was brought current with main, with no conflict", "whyNotMaterial": "main changed only files this PR does not touch"}


def run(capsys, *argv):
    """Runs the command through main; returns its exit code and the one JSON line it printed."""
    code = pr_sheet.main([str(arg) for arg in argv])
    return code, json.loads(capsys.readouterr().out)


class Train:
    """Two PRs, each published once, answered on every card and given a Merge, as a folder of sheets and store dumps."""

    def __init__(self, root, capsys):
        self.root, self.capsys = root, capsys
        self.inputs = root / "inputs"
        shutil.copytree(FIXTURES, self.inputs)
        self.sheets = {}
        for number, (_, source) in PRS.items():
            self.publish(number, "v1", self.inputs / source)
            self.save_merge(number)

    def path(self, number, version):
        return self.root / f"pr{number}" / version / "sheet.json"

    def publish(self, number, version, source):
        path = self.path(number, version)
        path.parent.mkdir(parents=True, exist_ok=True)
        code, said = run(self.capsys, "build", "--record", self.inputs / PRS[number][0], "--input", source, "--out", path)
        assert code == 0, said
        return path

    def save_merge(self, number):
        """Accept every card and walk every stop of the first sheet, then Merge: the store dump of the owner's whole sitting."""
        sheet_bytes = self.path(number, "v1").read_bytes()
        sheet = json.loads(sheet_bytes)
        answers = {}
        for position, card in enumerate(sheet["cards"]):
            options = [o for o in card["options"] if o["sendsBack"] is False]
            answer = {"answer": "option", "optionId": options[0]["id"]} if card["options"] else {"answer": "accept", "optionId": None}
            answers[card["id"]] = {**answer, "note": "", "revision": "%016x" % (0xA11CE0 + number + position)}
        walk = {stop["key"]: {"answer": "works" if stop["kind"] == "try" else "looks-right", "fix": None, "note": "", "shots": []}
                for stop in sheet["prSheet"].get("walk", {}).get("stops", [])}
        digest = hashlib.sha256(sheet_bytes).hexdigest()
        covers = sorted(f"answers/{card_id}@{doc['revision']}" for card_id, doc in answers.items())
        merge = {"verdict": "merge", "note": "", "sheet": digest, "covers": covers}
        store = self.root / f"pr{number}" / "store.json"
        store.write_text(json.dumps({"answers": answers, "walk": walk, "verdict": {digest: merge}}), encoding="utf-8")
        self.sheets[number] = sheet

    def republish(self, number, **more):
        """The PR's second sheet, built from its first by the input `more` adds to (carriedForward, or previousCommit alone)."""
        advisor = json.loads((self.inputs / PRS[number][1]).read_text(encoding="utf-8"))
        advisor.update(more)
        source = self.inputs / f"republish-{number}.json"
        source.write_text(json.dumps(advisor), encoding="utf-8")
        return self.publish(number, "v2", source)

    def carry(self, number):
        return self.republish(number, carriedForward={"fromSheet": str(self.path(number, "v1")), "heads": {str(number): (f"{number:x}" * 40)[:40]},
                                                      "date": "2026-10-13", **BROUGHT_CURRENT})

    def material_fix(self, number):
        return self.republish(number, previousCommit=self.sheets[number]["prSheet"]["commit"])

    def index(self, version_of):
        """The index over each PR's sheet of the version named, with its store; returns its rows by PR number."""
        entries = [{"number": n, "link": f"https://sheets.example.test/pr-{n}", "sheet": str(self.path(n, version_of[n])), "store": str(self.root / f"pr{n}" / "store.json")} for n in PRS]
        source = self.root / "index-input.json"
        source.write_text(json.dumps({"schema": "index-input/1", "questions": [], "mergeOrder": [211, 214], "prs": entries}), encoding="utf-8")
        code, said = run(self.capsys, "index", "--input", source, "--out", self.root / "index.json")
        assert code == 0, said
        rows = json.loads((self.root / "index.json").read_text(encoding="utf-8"))["index"]["rows"]
        return {row["number"]: row for row in rows}

    def state(self, number, version):
        store = json.loads((self.root / f"pr{number}" / "store.json").read_text(encoding="utf-8"))
        return pr_sheet.pr_state(self.path(number, version).read_bytes(), store, WORDS["pr"], WORDS["prAnswers"])


@pytest.fixture
def train(tmp_path, capsys):
    return Train(tmp_path, capsys)


def test_both_prs_start_ready_on_the_first_sheets(train):
    # Bites on: a dry run that does not begin from a standing Merge, so the carried rows below would prove nothing.
    rows = train.index({211: "v1", 214: "v1"})
    assert {n: row["state"] for n, row in rows.items()} == {211: "ready", 214: "ready"}
    assert rows[214]["accepted"] == rows[214]["total"] > 0 and rows[214]["walked"] == rows[214]["walkTotal"] > 0


def test_two_prs_brought_current_from_main_with_a_carry_both_stay_ready_on_the_index_and_in_pr_state(train):
    # Bites on: the index or pr_state reading only the new sheet's own digest, so a bring-current from main loses every owner's Merge.
    # Axis: the carried republish of a pr sheet with no cards and of one with cards and a walk both read the earlier sheet's Merge, on the index row and in pr_state.
    for number in PRS:
        train.carry(number)
    carried = json.loads(train.path(214, "v2").read_text(encoding="utf-8"))["prSheet"]
    assert carried["carriedForward"]["sheets"] == [hashlib.sha256(train.path(214, "v1").read_bytes()).hexdigest()]
    assert carried["previousCommit"] == train.sheets[214]["prSheet"]["commit"] and carried["commit"] != carried["previousCommit"]
    rows = train.index({211: "v2", 214: "v2"})
    assert {n: row["state"] for n, row in rows.items()} == {211: "ready", 214: "ready"}
    assert rows[214]["caption"].endswith(WORDS["index"]["ready"])
    assert [train.state(n, "v2")["state"] for n in PRS] == ["ready", "ready"]


def test_a_pr_republished_after_a_material_fix_goes_back_to_needs_you_while_the_carried_one_stays_ready(train):
    # Bites on: a material republish (previousCommit only) inheriting the earlier Merge, or the answers to unchanged cards being lost with it.
    # Axis: the same store, read for one carried sheet and one materially changed sheet, gives ready for the first and needs-you for the second.
    train.carry(211)
    train.material_fix(214)
    rows = train.index({211: "v2", 214: "v2"})
    assert rows[211]["state"] == "ready"
    assert rows[214]["state"] == "needs-you"
    assert rows[214]["accepted"] == rows[214]["total"] > 0
    assert train.state(211, "v2")["state"] == "ready" and train.state(214, "v2")["state"] == "needs-you"
