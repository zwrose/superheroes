"""Guards for the PR sheet builder's spec-PR mode: a spec PR's sheet built from its checks record, vet records and breakdown pins."""
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import pr_sheet
import sheet_prose

LIB = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pr_sheet"
PACKAGE = FIXTURES / "spec-package" / "a-small-spec-0a1b2c"
WORDS = json.loads((LIB.parent / "theme" / "sheet-words.json").read_text(encoding="utf-8"))["pr"]
SLUG = PACKAGE.name
PINNED = ["coverage-map.md", "epic.md", "children/A.md", "children/B.md"]
BODIES = ["epic.md", "children/A.md", "children/B.md"]
HEADS = {1: "1" * 40, 2: "2" * 40, 3: "3" * 40}


def content_hash(path):
    with open(path, encoding="utf-8") as handle:
        return hashlib.sha256(handle.read().encode("utf-8")).hexdigest()


def vet_text(folder, number, kind="Spec", verdict="clean", pins=None):
    """One spec-vet record in the template's shape (skills/showrunner/reference/spec-vet.md § The vet record)."""
    spec_hash = content_hash(folder / "spec.md")
    lines = ["<!-- superheroes:spec-vet -->",
             f"**{kind} vet, round {number}** · spec `{SLUG}` · head `{HEADS[number]}` · spec hash `{spec_hash}` · size `full`",
             f"**Verdict:** `{verdict}`", "", "| Id | Kind | Where | What is wrong | Source it fails |", "|---|---|---|---|---|", "None", "",
             "**Owner calls for the final sheet:**", "None", ""]
    if pins is not None:
        lines += ["Breakdown pins:", *(f"docs/superheroes/{SLUG}/{p} {content_hash(folder / p)}" for p in pins)]
    return "\n".join(lines + [f"Vet done: round {number} · {verdict} · {spec_hash}"]) + "\n"


@pytest.fixture
def world(tmp_path):
    """A copy of the fixture spec package, its three vet records (two spec rounds, then the breakdown vet) and the input naming them."""
    folder = tmp_path / SLUG
    shutil.copytree(PACKAGE, folder)
    texts = [vet_text(folder, 1, verdict="findings"), vet_text(folder, 2), vet_text(folder, 3, "Breakdown", pins=PINNED)]
    for n, text in enumerate(texts, 1):
        (tmp_path / f"vet-{n}.md").write_text(text, encoding="utf-8")
    advisor = {"schema": "pr-sheet-input/1", "kind": "pr", "number": 41, "title": "Spec: a small spec", "summary": "A small spec and its breakdown.",
               "spec": {"folder": SLUG, "vetRecords": [f"vet-{n}.md" for n in (1, 2, 3)], "ci": {"state": "passing", "commit": HEADS[3]}}}
    (tmp_path / "input.json").write_text(json.dumps(advisor), encoding="utf-8")
    (tmp_path / "body.md").write_text("## What we're accepting\n\nNone\n", encoding="utf-8")
    return tmp_path, folder, advisor


def build(world, advisor=None, records=()):
    base, _, given = world
    return pr_sheet.build(list(records), copy.deepcopy(advisor or given), WORDS, spec_base=base)


def problems_of(world, advisor=None, records=()):
    with pytest.raises(pr_sheet.Refusal) as caught:
        build(world, advisor, records)
    return caught.value.problems


def bullets(sheet):
    (card,) = sheet["cards"]
    return card["context"][0]["blocks"][0]["bullets"]


def cli(world, *extra):
    base = world[0]
    args = [sys.executable, "-B", str(LIB / "pr_sheet.py"), "build", "--input", str(base / "input.json"), "--out", str(base / "out" / "sheet.json"),
            "--pr-body", f"41={base / 'body.md'}", *extra]
    (base / "out").mkdir(exist_ok=True)
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


def test_a_spec_sheet_builds_from_the_spec_package(world):
    # Axis: the sheet's facts come from the spec's artifacts: the reviewer and rounds from the checks record, the commit and history from the vet records.
    sheet = build(world)
    assert sheet_prose.check_sheet(sheet) == [] and sheet["kind"] == "pr"
    part = sheet["prSheet"]
    assert part["commit"] == HEADS[3] and part["whatChanged"]["ci"] == {"state": "passing", "commit": HEADS[3]}
    assert part["whatChanged"]["reviewers"] == [{"name": WORDS["specChecksReviewer"], "family": "openai", "ran": "reported-by-session", "notIndependent": False}]
    assert part["whatChanged"]["rounds"] == 2 and part["whatChanged"]["lane"] is None
    assert part["history"][1:] == ["Spec vet, round 1: findings, on 1111111.", "Spec vet, round 2: clean, on 2222222.",
                                   "Breakdown vet, round 3: clean, on 3333333.", _fill_pins(len(PINNED))]


def _fill_pins(count):
    return WORDS["specPins"].replace("{count}", str(count))


def test_every_breakdown_child_and_pin_appears_with_its_hash(world):
    # Axis: the breakdown card lists every body the filing creates and every artifact, each with its path and pinned hash; the title counts the bodies.
    _, folder, _ = world
    sheet = build(world)
    (card,) = sheet["cards"]
    assert card["callKind"] == WORDS["breakdownKind"] and card["options"] == []
    assert card["question"] == WORDS["breakdownTitle"].replace("{count}", str(len(BODIES)))
    shown = bullets(sheet)
    assert len(shown) == len(PINNED)
    for rel in PINNED:
        path, digest = f"docs/superheroes/{SLUG}/{rel}", content_hash(folder / rel)
        word = "breakdownBody" if rel in BODIES else "breakdownArtifact"
        assert WORDS[word].replace("{path}", path).replace("{hash}", digest) in shown


def test_a_stale_pin_refuses_and_is_never_shown_as_accepted(world):
    # Axis: a pinned file whose hash no longer matches refuses the build, naming the pin; the command writes no sheet.
    base, folder, _ = world
    with open(folder / "children" / "B.md", "a", encoding="utf-8") as handle:
        handle.write("A line added after the breakdown vet.\n")
    found = problems_of(world)
    assert len(found) == 1 and f"breakdown pin docs/superheroes/{SLUG}/children/B.md hashes to" in found[0] and "needs a new vet" in found[0]
    done = cli(world)
    assert done.returncode == 1 and not (base / "out" / "sheet.json").exists()
    assert any("children/B.md" in p for p in json.loads(done.stdout)["problems"])


def test_a_missing_pinned_file_and_a_pin_outside_the_folder_refuse(world):
    # Axis: a pin that cannot be read, or that sits outside the spec's folder, refuses rather than being dropped from the card.
    base, folder, advisor = world
    (folder / "children" / "A.md").unlink()
    text = (base / "vet-3.md").read_text(encoding="utf-8").replace("Vet done:", f"elsewhere/x.md {'0' * 64}\nVet done:")
    (base / "vet-3.md").write_text(text, encoding="utf-8")
    found = problems_of(world)
    assert any("children/A.md could not be read" in p for p in found) and any("elsewhere/x.md is outside the spec's folder" in p for p in found)


def test_the_cli_builds_a_spec_sheet_with_no_record(world):
    # Axis: the command takes no --record when the input names spec, and writes a sheet the page check accepts.
    base = world[0]
    done = cli(world)
    assert done.returncode == 0, done.stdout + done.stderr
    sheet = json.loads((base / "out" / "sheet.json").read_text(encoding="utf-8"))
    assert sheet_prose.check_sheet(sheet) == [] and sheet["prSheet"]["nothingListed"] is True and len(sheet["cards"]) == 1


def test_a_code_pr_without_its_record_still_refuses(world, tmp_path):
    # Axis: the mode is named by the input, never guessed: an input without spec and no --record is the usage error it always was.
    base, _, advisor = world
    code = {k: v for k, v in advisor.items() if k != "spec"}
    (base / "input.json").write_text(json.dumps(code), encoding="utf-8")
    done = cli(world)
    assert done.returncode == 2 and "--record" in done.stderr and not (base / "out" / "sheet.json").exists()
    with pytest.raises(pr_sheet.Refusal) as caught:
        pr_sheet.build([], code, WORDS)
    assert caught.value.problems == ["a pr sheet takes exactly one record, got 0"]


def test_a_spec_sheet_refuses_a_review_record_and_a_stack(world):
    # Axis: the spec-PR mode takes no review record and is a pr sheet only.
    found = problems_of(world, records=[{"schema": "x"}])
    assert any("takes no review record" in p for p in found)
    stack = {**world[2], "kind": "stack", "prs": [{"number": 41, "title": "a"}, {"number": 42, "title": "b"}]}
    assert any('must be kind "pr"' in p for p in problems_of(world, stack))


def test_the_newest_record_must_be_a_clean_breakdown_vet_on_the_spec_as_it_stands(world):
    # Axis: a spec edited after its vet, a newest record that is not a clean breakdown vet, and a missing round each refuse.
    base, folder, advisor = world
    (base / "vet-3.md").write_text(vet_text(folder, 3, "Breakdown", verdict="findings", pins=PINNED), encoding="utf-8")
    assert any("must be a clean breakdown vet" in p for p in problems_of(world))
    (base / "vet-3.md").write_text(vet_text(folder, 3, "Breakdown", pins=PINNED), encoding="utf-8")
    skipped = {**advisor, "spec": {**advisor["spec"], "vetRecords": ["vet-1.md", "vet-3.md"]}}
    assert any("give every round's record" in p for p in problems_of(world, skipped))
    with open(folder / "spec.md", "a", encoding="utf-8") as handle:
        handle.write("An edit after the vet.\n")
    assert any("the spec changed after its vet" in p for p in problems_of(world))


def test_a_file_that_is_not_a_vet_record_refuses(world):
    # Axis: a vet record file without the marker, header, verdict and a Vet done: line last refuses, naming the file.
    base = world[0]
    (base / "vet-2.md").write_text("Looks fine to me.\n", encoding="utf-8")
    assert any("vet record vet-2.md is not a vet record" in p for p in problems_of(world))


def test_the_merge_verdict_reads_as_on_a_code_pr_sheet(world):
    # Axis: Merge stands on a spec sheet by the same pr_state rule as a code PR's: the breakdown accepted and covers naming the answer.
    sheet = build(world)
    data = (json.dumps(sheet, indent=2) + "\n").encode("utf-8")
    digest, (card,) = hashlib.sha256(data).hexdigest(), sheet["cards"]
    answer = {"answer": "accept", "optionId": None, "note": "", "revision": "0123456789abcdef"}
    verdict = {"sheet": digest, "verdict": "merge", "note": "", "covers": [f"answers/{card['id']}@0123456789abcdef"]}
    assert sheet_prose.fits_definition("answer", answer) and sheet_prose.fits_definition("verdict", verdict)
    store = {"answers": {card["id"]: answer}, "verdict": {digest: verdict}}
    assert pr_sheet.pr_state(data, store)["state"] == "ready"
    assert pr_sheet.pr_state(data, {"answers": {card["id"]: answer}})["state"] == "needs-you"
