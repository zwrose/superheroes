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


def test_a_body_beside_the_pinned_ones_that_is_not_pinned_refuses(world):
    # Axis: a breakdown vet that leaves one child body out of its pins is stale; the child is never silently dropped from the card.
    base, folder, _ = world
    (base / "vet-3.md").write_text(vet_text(folder, 3, "Breakdown", pins=[p for p in PINNED if p != "children/B.md"]), encoding="utf-8")
    found = problems_of(world)
    assert len(found) == 1 and found[0].startswith("children/B.md sits in the breakdown's body home") and "needs a new vet" in found[0]


def test_a_pinned_link_to_another_pinned_body_is_not_read_as_unpinned(world):
    # Axis: the sibling check compares resolved paths, so a pinned name that links to another pinned body inside the folder is pinned.
    base, folder, _ = world
    (folder / "children" / "C.md").symlink_to(folder / "children" / "A.md")
    (base / "vet-3.md").write_text(vet_text(folder, 3, "Breakdown", pins=[*PINNED, "children/C.md"]), encoding="utf-8")
    assert len(bullets(build(world))) == len(PINNED) + 1


@pytest.mark.parametrize("pinned", [False, True], ids=["unpinned-loop", "pinned-loop"])
def test_a_link_loop_is_a_refusal_never_a_crash(world, pinned):
    # Axis: a body that links to itself refuses with a named problem through the command, whether or not the vet pins it.
    base, folder, _ = world
    (folder / "children" / "loop.md").symlink_to(folder / "children" / "loop.md")
    pin = f"docs/superheroes/{SLUG}/children/loop.md"
    text = vet_text(folder, 3, "Breakdown", pins=PINNED)
    (base / "vet-3.md").write_text(text.replace("Vet done:", f"{pin} {'0' * 64}\nVet done:") if pinned else text, encoding="utf-8")
    done = cli(world)
    expected = f"breakdown pin {pin} is outside the spec's folder" if pinned else "children/loop.md sits in the breakdown's body home"
    assert done.returncode == 1 and "Traceback" not in done.stderr and any(expected in p for p in json.loads(done.stdout)["problems"])


@pytest.mark.parametrize("escape", ["dotdot", "symlink"])
def test_a_pin_that_resolves_outside_the_folder_refuses(world, escape):
    # Axis: a pin naming the slug but resolving out of the folder (through .. or a symlink) refuses, even when its hash matches.
    base, folder, _ = world
    outside = base / "outside.md"
    outside.write_text("Not part of the package.\n", encoding="utf-8")
    if escape == "dotdot":
        pin = f"docs/superheroes/{SLUG}/../outside.md"
    else:
        (folder / "children" / "link.md").symlink_to(outside)
        pin = f"docs/superheroes/{SLUG}/children/link.md"
    text = vet_text(folder, 3, "Breakdown", pins=PINNED).replace("Vet done:", f"{pin} {content_hash(outside)}\nVet done:")
    (base / "vet-3.md").write_text(text, encoding="utf-8")
    assert any(f"breakdown pin {pin} is outside the spec's folder" in p for p in problems_of(world))


@pytest.mark.parametrize("ci", [{}, None, {"state": "green"}, {"state": "", "commit": None}])
def test_malformed_ci_is_a_refusal_never_a_crash(world, ci):
    # Axis: a malformed spec.ci is named as a problem, through the API and the command, never a traceback.
    base, _, advisor = world
    given = {**advisor, "spec": {**advisor["spec"], "ci": ci}}
    assert any(p.startswith("spec ci must be") for p in problems_of(world, given))
    (base / "input.json").write_text(json.dumps(given), encoding="utf-8")
    done = cli(world)
    assert done.returncode == 1 and "Traceback" not in done.stderr and any(p.startswith("spec ci must be") for p in json.loads(done.stdout)["problems"])


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


@pytest.mark.parametrize("rel", ["seams/S.md", "seams/deep/S.md", "children/nested/D.md"])
def test_an_unpinned_body_in_the_home_refuses_in_a_folder_with_no_pinned_body(world, rel):
    # Axis: the home scan reads all of children/ and seams/, not only the folders the pins sit in, so a forgotten pin cannot file unseen.
    _, folder, _ = world
    (folder / rel).parent.mkdir(parents=True, exist_ok=True)
    (folder / rel).write_text("A seam body the vet forgot to pin.\n", encoding="utf-8")
    found = problems_of(world)
    assert len(found) == 1 and found[0].startswith(f"{rel} sits in the breakdown's body home") and "needs a new vet" in found[0]


def test_an_unpinned_epic_body_refuses(world):
    # Axis: epic.md is part of the home, so an epic body the vet leaves out of its pins refuses.
    base, folder, _ = world
    (base / "vet-3.md").write_text(vet_text(folder, 3, "Breakdown", pins=[p for p in PINNED if p != "epic.md"]), encoding="utf-8")
    found = problems_of(world)
    assert len(found) == 1 and found[0].startswith("epic.md sits in the breakdown's body home")


def test_a_pinned_body_outside_the_home_refuses(world):
    # Axis: a body pinned at the folder's top level (the shape vet 700's probe B7 built clean) refuses, so the home holds every body.
    base, folder, _ = world
    (folder / "child.md").write_text("A body saved beside the spec.\n", encoding="utf-8")
    (base / "vet-3.md").write_text(vet_text(folder, 3, "Breakdown", pins=[*PINNED, "child.md"]), encoding="utf-8")
    found = problems_of(world)
    assert len(found) == 1 and found[0].startswith(f"breakdown pin docs/superheroes/{SLUG}/child.md is a body outside the breakdown's home")


@pytest.fixture
def single(world):
    """The world cut down to a single-issue spec: no epic, no coverage map, one child body in children/ and the vet pinning only it."""
    base, folder, advisor = world
    for rel in ("epic.md", "coverage-map.md", "children/A.md", "children/B.md"):
        (folder / rel).unlink()
    (folder / "children" / "C1.md").write_text("The single child's body.\n", encoding="utf-8")
    (base / "vet-3.md").write_text(vet_text(folder, 3, "Breakdown", pins=["children/C1.md"]), encoding="utf-8")
    return world


def test_a_single_issue_sheet_counts_one_body_and_one_pin(single):
    # Axis: the one/many word pairs: a single-issue spec's sheet reads "1 body" and "pins 1 file", never "1 bodies" or "pins 1 files".
    sheet = build(single)
    (card,) = sheet["cards"]
    assert card["question"] == WORDS["breakdownTitleOne"] and "1 body the filing" in card["question"]
    assert sheet["prSheet"]["history"][-1] == WORDS["specPin"] and "pins 1 file," in WORDS["specPin"]
    assert len(bullets(sheet)) == 1


def test_a_single_issue_spec_with_an_unpinned_body_beside_its_pinned_one_refuses(single):
    # Axis: the single-issue body sits in children/, so an unpinned body beside it refuses (vet 700 probe B7 built this clean).
    _, folder, _ = single
    (folder / "children" / "C1-unpinned.md").write_text("A second body nobody pinned.\n", encoding="utf-8")
    found = problems_of(single)
    assert len(found) == 1 and found[0].startswith("children/C1-unpinned.md sits in the breakdown's body home")


def test_a_duplicate_pin_refuses(world):
    # Axis: vet 700 leg M1: a vet record that pins one file twice refuses.
    base, folder, _ = world
    (base / "vet-3.md").write_text(vet_text(folder, 3, "Breakdown", pins=[*PINNED, "children/A.md"]), encoding="utf-8")
    assert problems_of(world) == ["the newest vet record pins a file more than once"]


def test_a_vet_record_for_another_spec_refuses(world):
    # Axis: vet 700 leg M2: a vet record whose header names another work item refuses, naming its round.
    base = world[0]
    text = (base / "vet-2.md").read_text(encoding="utf-8").replace(f"spec `{SLUG}`", "spec `another-spec-9f9f9f`")
    (base / "vet-2.md").write_text(text, encoding="utf-8")
    assert problems_of(world) == [f"vet record round 2 is for spec another-spec-9f9f9f, not {SLUG}"]


def test_a_vet_done_line_that_disagrees_with_its_header_refuses(world):
    # Axis: vet 700 leg M3: a Vet done: line naming another round or verdict than the header refuses, naming the file.
    base = world[0]
    text = (base / "vet-2.md").read_text(encoding="utf-8").replace("Vet done: round 2 · clean", "Vet done: round 2 · findings")
    (base / "vet-2.md").write_text(text, encoding="utf-8")
    found = problems_of(world)
    assert len(found) == 1 and found[0].startswith("vet record vet-2.md: its Vet done: line names round 2 findings")


def test_a_same_family_checks_seat_is_marked_not_independent(world):
    # Axis: vet 700 leg M4: "Same family: yes" sets the reviewer's notIndependent flag and adds the not-independent history line.
    _, folder, _ = world
    path = folder / "checks-record.md"
    path.write_text(path.read_text(encoding="utf-8").replace("- Same family: no", "- Same family: yes"), encoding="utf-8")
    part = build(world)["prSheet"]
    assert part["whatChanged"]["reviewers"][0]["notIndependent"] is True
    assert WORDS["historyNotIndependent"].replace("{name}", WORDS["specChecksReviewer"]) in " ".join(part["history"])
