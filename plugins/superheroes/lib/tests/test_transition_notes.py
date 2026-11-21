import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import adopt_version as av  # noqa: E402
import transition_notes as tn  # noqa: E402


def good(n, marker="After", heading=None):
    heading = heading or "Heading %s" % n
    return (
        "### Before you upgrade\n\n"
        "- **%s switching.** Step %s.\n\n"
        "### %s\n\n"
        "Body %s.\n" % (marker, n, heading, n)
    )


def tokens(problems):
    return [p["token"] for p in problems]


NOTE_A = """\
### Before you upgrade

- **Before switching.** Twelve step: do the twelve thing first.

### Twelve heading

Twelve body line.

```text
### not a heading
# not a heading either
```
"""

NOTE_B = """\
<!-- written for issue 3 -->

### Before you upgrade

- **After switching.** Three step: this one runs after the switch,
  and carries a continuation line.

### Three heading

Three body line.
"""

NOTES = [("12.md", NOTE_A), ("3-two.md", NOTE_B)]
SEC_A = "### Twelve heading" + NOTE_A.split("### Twelve heading")[1].rstrip("\n")
SEC_B = "### Three heading" + NOTE_B.split("### Three heading")[1].rstrip("\n")
STEP_A = "- **Before switching.** Twelve step: do the twelve thing first.\n"

OLD_SECTION = """\
## 1.0.0

### Before you upgrade

Check these in a consuming project when it adopts 1.0.0. Each step names the note it comes from.

- **After switching.** Old step.

### Old heading

Old body.
"""

TRANSITION = "# Transition notes\n\nHeader prose.\n\n" + OLD_SECTION

TRANSITION_U = """\
# Transition notes

Header prose.

## Unreleased

### Before you upgrade

Check these in a consuming project when it adopts the next release. Each step names the note it comes from.

- **After switching.** Hand bullet.

### Hand heading

Hand body.

""" + OLD_SECTION

ASSEMBLED_BODY = """\
- **After switching.** Hand bullet.
- **After switching.** Three step: this one runs after the switch,
  and carries a continuation line.
- **Before switching.** Twelve step: do the twelve thing first.

### Hand heading

Hand body.

""" + SEC_B + "\n\n" + SEC_A + "\n"


def expected_into_existing(label):
    return (
        "# Transition notes\n\nHeader prose.\n\n## %s\n\n### Before you upgrade\n\n%s\n\n"
        % (label, tn.INTRO.format(target=label))
    ) + ASSEMBLED_BODY + "\n" + OLD_SECTION


def make_root(tmp_path, notes=(), transition=TRANSITION):
    root = tmp_path / "plugin"
    folder = root / tn.NOTES_DIRNAME
    folder.mkdir(parents=True)
    (root / "TRANSITION.md").write_text(transition)
    (folder / tn.README_NAME).write_text("How to write a note.\n")
    for name, text in notes:
        (folder / name).write_text(text)
    return root


# ---------------------------------------------------------------- the note shape, one test per token


def test_control_note_is_well_formed():
    assert tn.parse_note("101.md", good(101))["problems"] == []
    assert tn.parse_note("101-some-slug.md", good(101))["problems"] == []
    assert tn.check_notes([("101.md", good(101)), ("102.md", good(102))]) == []


def test_token_note_name_invalid():
    for name in ("notes.md", "12.txt", "12-Bad.md", "12-.md", "12_x.md"):
        assert tokens(tn.parse_note(name, good(12))["problems"]) == ["note-name-invalid"], name
    assert tokens(tn.check_notes([("12.txt", good(12))])) == ["note-name-invalid"]


def test_token_note_byu_missing():
    text = "### Other heading\n\nbody\n"
    assert tokens(tn.parse_note("1.md", text)["problems"]) == ["note-byu-missing"]
    assert tokens(tn.parse_note("1.md", "<!-- only a comment -->\n")["problems"]) == ["note-byu-missing"]


def test_token_note_byu_repeated():
    text = good(1) + "\n### Before you upgrade\n\n- **After switching.** Again.\n"
    assert tokens(tn.parse_note("1.md", text)["problems"]) == ["note-byu-repeated"]


def test_token_note_byu_empty():
    text = "### Before you upgrade\n\n### Heading 1\n\nBody.\n"
    assert tokens(tn.parse_note("1.md", text)["problems"]) == ["note-byu-empty"]


def test_token_note_byu_stray():
    text = (
        "### Before you upgrade\n\n"
        "Some prose that assembly would lose.\n"
        "- **After switching.** Step.\n\n"
        "### Heading 1\n\nBody.\n"
    )
    assert tokens(tn.parse_note("1.md", text)["problems"]) == ["note-byu-stray"]


def test_token_note_bullet_unmarked():
    long_bullet = "Do the thing without any marker at all, and keep going on and on for a long while here"
    text = "### Before you upgrade\n\n- %s\n\n### Heading 1\n\nBody.\n" % long_bullet
    problems = tn.parse_note("1.md", text)["problems"]
    assert tokens(problems) == ["note-bullet-unmarked"]
    assert long_bullet[:60] in problems[0]["detail"]
    assert long_bullet[:61] not in problems[0]["detail"]
    for bad in ("**Before switching:** lenient colon form", "**Before switching.**glued", "**Sometime.** other"):
        text = "### Before you upgrade\n\n- %s\n\n### Heading 1\n\nBody.\n" % bad
        assert tokens(tn.parse_note("1.md", text)["problems"]) == ["note-bullet-unmarked"], bad
    two = "### Before you upgrade\n\n- first one\n- second one\n\n### Heading 1\n\nBody.\n"
    assert tokens(tn.parse_note("1.md", two)["problems"]) == ["note-bullet-unmarked"] * 2


def test_token_note_section_missing():
    text = "### Before you upgrade\n\n- **After switching.** Step.\n"
    assert tokens(tn.parse_note("1.md", text)["problems"]) == ["note-section-missing"]


def test_token_note_heading_level():
    for bad in ("# Title", "## Subtitle"):
        text = good(1) + "\n%s\n" % bad
        assert tokens(tn.parse_note("1.md", text)["problems"]) == ["note-heading-level"], bad


def test_token_note_fence_unbalanced():
    text = good(1) + "\n```\nnever closed\n"
    assert tokens(tn.parse_note("1.md", text)["problems"]) == ["note-fence-unbalanced"]


def test_token_note_heading_duplicate():
    across = [("1.md", good(1, heading="Same")), ("2.md", good(2, heading="Same"))]
    assert tokens(tn.check_notes(across)) == ["note-heading-duplicate"]
    twice = good(1) + "\n### Heading 1\n\nAgain.\n"
    assert tokens(tn.check_notes([("1.md", twice)])) == ["note-heading-duplicate"]
    assert tn.check_notes([("1.md", good(1)), ("2.md", good(2))]) == []


def test_token_note_empty():
    for text in ("", "   \n\n\t\n"):
        assert tokens(tn.parse_note("1.md", text)["problems"]) == ["note-empty"]
    assert tokens(tn.parse_note("bad name.txt", "")["problems"]) == ["note-empty"]


def test_parse_note_returns_bullets_and_whole_sections():
    note = tn.parse_note("3-two.md", NOTE_B)
    assert note["problems"] == []
    assert note["name"] == "3-two.md"
    assert note["bullets"] == [
        "- **After switching.** Three step: this one runs after the switch,\n"
        "  and carries a continuation line."
    ]
    assert note["sections"] == [{"heading": "Three heading", "text": SEC_B}]
    note = tn.parse_note("12.md", NOTE_A)
    assert note["problems"] == []
    assert note["sections"] == [{"heading": "Twelve heading", "text": SEC_A}]


def test_parse_note_fenced_headings_are_opaque():
    text = good(1) + "\n```\n# not a heading\n### Heading 1\n```\n\n#### deeper is fine\n"
    note = tn.parse_note("1.md", text)
    assert note["problems"] == []
    assert [s["heading"] for s in note["sections"]] == ["Heading 1"]


def test_parse_note_continuation_across_blank_lines():
    text = (
        "### Before you upgrade\n\n"
        "- **After switching.** One\n\n"
        "  still one\n\n"
        "- **Before switching.** Two\n\n"
        "### Heading 1\n\nBody.\n"
    )
    note = tn.parse_note("1.md", text)
    assert note["problems"] == []
    assert note["bullets"] == [
        "- **After switching.** One\n  still one",
        "- **Before switching.** Two",
    ]


# ------------------------------------------------------------------------ reading and ordering


def test_sort_key_numeric_before_string_order():
    names = ["12.md", "3-two.md", "100.md", "abc.md", "7.md", "10-x.md"]
    assert sorted(names, key=tn.sort_key) == ["3-two.md", "7.md", "10-x.md", "12.md", "100.md", "abc.md"]
    assert tn.sort_key("12-a.md") == (12, "12-a.md")


def test_read_notes_absent_folder(tmp_path):
    assert tn.read_notes(str(tmp_path)) == []
    assert tn.notes_dir("/x") == os.path.join("/x", "transition-notes")


def test_read_notes_order_readme_and_any_extension(tmp_path):
    root = make_root(tmp_path, notes=[("12.md", "a"), ("3-two.md", "b"), ("5.txt", "c")])
    (root / tn.NOTES_DIRNAME / "sub").mkdir()
    got = tn.read_notes(str(root))
    assert got == [("3-two.md", "b"), ("5.txt", "c"), ("12.md", "a")]


# ------------------------------------------------------------------------------- render


def test_structure_counts_headings_and_bullets():
    text = (
        "### Not counted before any section\n\n"
        "## 1.0.0\n\n"
        "### Before you upgrade\n\nintro\n\n- one\n- two\n  cont\n\n"
        "### A heading\n\n```\n### fenced\n- fenced\n```\n\n"
        "## 0.9.0\n\n### B heading\n\n- not under Before you upgrade\n"
    )
    assert tn.structure(text) == {"headings": ["A heading", "B heading"], "bullets": 2}
    assert tn.structure("") == {"headings": [], "bullets": 0}


def test_render_new_section_above_existing_section():
    out = tn.render(TRANSITION, NOTES, "1.1.0")
    intro = tn.INTRO.format(target="1.1.0")
    expected = TRANSITION.replace(
        "## 1.0.0\n",
        "## 1.1.0\n\n### Before you upgrade\n\n%s\n\n"
        "- **After switching.** Three step: this one runs after the switch,\n"
        "  and carries a continuation line.\n"
        "- **Before switching.** Twelve step: do the twelve thing first.\n\n"
        "%s\n\n%s\n\n## 1.0.0\n" % (intro, SEC_B, SEC_A),
    )
    assert out == expected
    assert out.index("## 1.1.0") < out.index("## 1.0.0")
    assert out.index("Three step") < out.index("Twelve step")
    assert SEC_A in out and SEC_B in out
    assert out.endswith("\n") and not out.endswith("\n\n")
    assert "\n\n\n" not in out


def test_render_new_section_when_no_section_exists():
    out = tn.render("# Transition notes\n\nHeader prose.\n", [("1.md", good(1))], tn.UNRELEASED)
    assert out == (
        "# Transition notes\n\nHeader prose.\n\n## Unreleased\n\n### Before you upgrade\n\n"
        + tn.INTRO.format(target="the next release")
        + "\n\n- **After switching.** Step 1.\n\n### Heading 1\n\nBody 1."
        + "\n"
    )


def test_render_into_existing_unreleased_renamed_to_version():
    out = tn.render(TRANSITION_U, NOTES, "1.1.0")
    assert out == expected_into_existing("1.1.0")
    assert "## Unreleased" not in out
    assert out.index("Hand bullet") < out.index("Three step") < out.index("Twelve step")
    assert out.index("Hand body") < out.index("### Three heading") < out.index("### Twelve heading")


def test_render_rename_keeps_a_custom_intro():
    custom = TRANSITION_U.replace(tn.INTRO.format(target="the next release"), "A hand-written intro.")
    out = tn.render(custom, NOTES, "1.1.0")
    assert "A hand-written intro." in out
    assert tn.INTRO.format(target="1.1.0") not in out
    assert "## 1.1.0" in out


def test_render_rename_without_notes_renames_and_rewrites_intro():
    out = tn.render(TRANSITION_U, [], "1.1.0")
    assert out == TRANSITION_U.replace("## Unreleased", "## 1.1.0").replace("the next release", "1.1.0")


def test_render_into_existing_version_section():
    existing = TRANSITION_U.replace("## Unreleased", "## 1.1.0").replace("the next release", "1.1.0")
    assert tn.render(existing, NOTES, "1.1.0") == expected_into_existing("1.1.0")


def test_render_into_existing_section_without_before_you_upgrade():
    text = "# T\n\n## 1.1.0\n\n### Existing\n\nExisting body.\n"
    out = tn.render(text, [("1.md", good(1))], "1.1.0")
    assert out == (
        "# T\n\n## 1.1.0\n\n### Before you upgrade\n\n" + tn.INTRO.format(target="1.1.0")
        + "\n\n- **After switching.** Step 1.\n\n### Existing\n\nExisting body.\n\n### Heading 1\n\nBody 1.\n"
    )


def test_render_into_before_you_upgrade_with_intro_only():
    intro = tn.INTRO.format(target="1.1.0")
    text = "# T\n\n## 1.1.0\n\n### Before you upgrade\n\n%s\n\n### Existing\n\nExisting body.\n" % intro
    out = tn.render(text, [("1.md", good(1))], "1.1.0")
    assert out == (
        "# T\n\n## 1.1.0\n\n### Before you upgrade\n\n%s\n\n- **After switching.** Step 1.\n\n"
        "### Existing\n\nExisting body.\n\n### Heading 1\n\nBody 1.\n" % intro
    )


def test_render_no_notes_and_no_target_is_unchanged():
    assert tn.render(TRANSITION, [], "1.1.0") == TRANSITION
    assert tn.render(TRANSITION, [], tn.UNRELEASED) == TRANSITION
    assert tn.render(TRANSITION_U, [], tn.UNRELEASED) == TRANSITION_U


def test_render_refuses_bad_label_and_bad_notes():
    for label in ("1.1", "v1.1.0", "unreleased", "1.1.0\n", ""):
        with pytest.raises(tn.NoteError) as info:
            tn.render(TRANSITION, NOTES, label)
        assert tokens(info.value.problems) == ["version-invalid"], label
    with pytest.raises(tn.NoteError) as info:
        tn.render(TRANSITION, [("bad.md", "")], "1.1.0")
    assert tokens(info.value.problems) == ["note-empty"]
    assert isinstance(info.value, ValueError)


def test_render_sorts_notes_into_assembly_order():
    assert tn.render(TRANSITION, NOTES[::-1], "1.1.0") == tn.render(TRANSITION, NOTES, "1.1.0")


# ----------------------------------------------------------------------------- assemble


def test_assemble_writes_transition_and_removes_files(tmp_path):
    root = make_root(tmp_path, notes=NOTES)
    result = tn.assemble(str(root), "1.1.0")
    folder = root / tn.NOTES_DIRNAME
    assert result == {
        "ok": True,
        "version": "1.1.0",
        "assembled": ["3-two.md", "12.md"],
        "transition": str(root / "TRANSITION.md"),
    }
    assert sorted(os.listdir(folder)) == ["README.md"]
    assert (root / "TRANSITION.md").read_text() == tn.render(TRANSITION, NOTES, "1.1.0")
    assert sorted(os.listdir(root)) == ["TRANSITION.md", "transition-notes"]


def test_assemble_twice_is_stable(tmp_path):
    root = make_root(tmp_path, notes=NOTES)
    assert tn.assemble(str(root), "1.1.0")["ok"] is True
    first = (root / "TRANSITION.md").read_bytes()
    again = tn.assemble(str(root), "1.1.0")
    assert again["ok"] is True and again["assembled"] == []
    assert (root / "TRANSITION.md").read_bytes() == first


def test_assemble_refuses_malformed_note_and_writes_nothing(tmp_path):
    root = make_root(tmp_path, notes=NOTES + [("7-bad.md", "no heading here\n")])
    before = (root / "TRANSITION.md").read_bytes()
    result = tn.assemble(str(root), "1.1.0")
    assert (root / "TRANSITION.md").read_bytes() == before
    assert sorted(os.listdir(root / tn.NOTES_DIRNAME)) == ["12.md", "3-two.md", "7-bad.md", "README.md"]
    assert result["ok"] is False
    assert result["reason"] == "notes-malformed"
    assert tokens(result["problems"]) == ["note-byu-missing"]


def test_assemble_refusals_for_version_and_transition(tmp_path):
    root = make_root(tmp_path, notes=NOTES)
    for bad in ("Unreleased", "1.1", "x"):
        result = tn.assemble(str(root), bad)
        assert result["ok"] is False and result["reason"] == "version-invalid"
    assert sorted(os.listdir(root / tn.NOTES_DIRNAME)) == ["12.md", "3-two.md", "README.md"]
    os.remove(root / "TRANSITION.md")
    result = tn.assemble(str(root), "1.1.0")
    assert result["ok"] is False and result["reason"] == "transition-unreadable"
    assert sorted(os.listdir(root / tn.NOTES_DIRNAME)) == ["12.md", "3-two.md", "README.md"]


# ------------------------------------------------------------ adopt-version round trip


def _cache(tmp_path, name, transition):
    cache = tmp_path / name
    (cache / "1.0.0").mkdir(parents=True)
    (cache / "1.1.0").mkdir()
    (cache / "1.1.0" / "TRANSITION.md").write_text(transition)
    return cache


def _plan_sections(capsys, cache):
    code = av.main([
        "plan", "--role", "showrunner", "--from", "1.0.0", "--to", "1.1.0", "--cache-dir", str(cache),
    ])
    assert code == 0
    data = json.loads(capsys.readouterr().out.strip())
    return data["transitionSections"]


def test_adopt_version_reads_assembled_notes_as_upgrade_steps(capsys, tmp_path):
    notes = [
        ("1-first.md", good(1, marker="Before")),
        ("2-second.md", good(2, marker="After")),
    ]
    rendered = tn.render("# Transition notes\n\nHeader prose.\n", notes, "1.1.0")
    sections = _plan_sections(capsys, _cache(tmp_path, "assembled", rendered))
    assert [s["version"] for s in sections] == ["1.1.0"]
    steps = sections[0]["upgradeSteps"]
    bullets = [b for n in notes for b in tn.parse_note(*n)["bullets"]]
    assert [s["text"] for s in steps] == [b[2:] for b in bullets]
    assert [s["when"] for s in steps] == ["before-switching", "after-switching"]
    assert [s["marked"] for s in steps] == [True, True]
    assert sections[0]["beforeYouUpgrade"] is True

    typed = """\
# Transition notes

Header prose.

## 1.1.0

### Before you upgrade

Check these in a consuming project when it adopts 1.1.0. Each step names the note it comes from.

- **Before switching.** Step 1.
- **After switching.** Step 2.

### Heading 1

Body 1.

### Heading 2

Body 2.
"""
    hand = _plan_sections(capsys, _cache(tmp_path, "typed", typed))[0]["upgradeSteps"]
    assert [(s["text"], s["when"]) for s in hand] == [(s["text"], s["when"]) for s in steps]
    assert sections[0]["subheadings"] == ["Before you upgrade", "Heading 1", "Heading 2"]


# --------------------------------------------------------- two PRs merge without conflict


def _git(repo, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
         "-C", str(repo), *args],
        capture_output=True, text=True, env=env,
    )


@pytest.mark.parametrize("order", [("a", "b"), ("b", "a")])
def test_two_prs_merge_with_no_conflict(tmp_path, order):
    repo = tmp_path / "repo"
    folder = repo / tn.NOTES_DIRNAME
    folder.mkdir(parents=True)
    (repo / "TRANSITION.md").write_text(TRANSITION_U)
    (folder / tn.README_NAME).write_text("How to write a note.\n")
    for step in (("init", "-q"), ("checkout", "-q", "-b", "main"), ("add", "-A"), ("commit", "-q", "-m", "base")):
        done = _git(repo, *step)
        assert done.returncode == 0, done.stderr
    for branch, fname, n in (("a", "101.md", 101), ("b", "102.md", 102)):
        for step in (("checkout", "-q", "-b", branch, "main"), ):
            assert _git(repo, *step).returncode == 0
        (folder / fname).write_text(good(n))
        for step in (("add", "-A"), ("commit", "-q", "-m", "note " + fname), ("checkout", "-q", "main")):
            done = _git(repo, *step)
            assert done.returncode == 0, done.stderr
    for branch in order:
        done = _git(repo, "merge", "--no-edit", branch)
        assert done.returncode == 0, done.stdout + done.stderr
    assert [n for n, _ in tn.read_notes(str(repo))] == ["101.md", "102.md"]
    assert tn.check_notes(tn.read_notes(str(repo))) == []


# ------------------------------------------------------------------------ doctrine reader


def test_transition_text_reads_notes_and_survives_assembly(tmp_path):
    sentence = "A distinctive zebra-quartz sentence the doctrine tests look for."
    note = good(9).replace("Body 9.", sentence)
    root = make_root(tmp_path, notes=[("9.md", note)])
    before = tn.transition_text(str(root))
    heads = [ln for ln in before.split("\n") if ln.startswith("## ")]
    assert heads == ["## Unreleased", "## 1.0.0"]
    assert before.index("## Unreleased") < before.index(sentence) < before.index("## 1.0.0")
    assert sentence not in (root / "TRANSITION.md").read_text()

    assert tn.assemble(str(root), "2.0.0")["ok"] is True
    raw = (root / "TRANSITION.md").read_text()
    assert [ln for ln in raw.split("\n") if ln.startswith("## ")] == ["## 2.0.0", "## 1.0.0"]
    assert raw.index("## 2.0.0") < raw.index(sentence) < raw.index("## 1.0.0")
    after = tn.transition_text(str(root))
    assert sentence in after
    assert "## Unreleased" not in after
    assert after == raw


def test_transition_text_without_notes_is_the_file(tmp_path):
    root = make_root(tmp_path)
    assert tn.transition_text(str(root)) == TRANSITION


def test_transition_text_raises_on_malformed_notes(tmp_path):
    root = make_root(tmp_path, notes=[("9.md", "garbage\n")])
    with pytest.raises(tn.NoteError) as info:
        tn.transition_text(str(root))
    assert tokens(info.value.problems) == ["note-byu-missing"]


# --------------------------------------------------------------------------- compare_pr


def test_compare_direct_heading_is_refused():
    head = TRANSITION + "\n### New direct heading\n\nBody.\n"
    assert tokens(tn.compare_pr(TRANSITION, head, [], [])) == ["transition-heading-added"]


def test_compare_swapped_heading_is_refused():
    head = TRANSITION.replace("### Old heading", "### A different heading")
    assert tokens(tn.compare_pr(TRANSITION, head, [], [])) == ["transition-heading-added"]


def test_compare_direct_bullet_is_refused():
    old = "- **After switching.** Old step.\n"
    head = TRANSITION.replace(old, old + "- **After switching.** A direct bullet.\n")
    assert tokens(tn.compare_pr(TRANSITION, head, [], [])) == ["transition-bullet-added"]


def test_compare_well_formed_assembly_is_clean():
    head = tn.render(TRANSITION, NOTES, "1.1.0")
    assert tn.compare_pr(TRANSITION, head, NOTES, []) == []
    into = tn.render(TRANSITION_U, NOTES, "1.1.0")
    assert tn.compare_pr(TRANSITION_U, into, NOTES, []) == []


def test_compare_assembly_dropping_a_section_is_refused():
    head = tn.render(TRANSITION, NOTES, "1.1.0")
    assert "\n\n" + SEC_A in head
    short = head.replace("\n\n" + SEC_A, "")
    problems = tn.compare_pr(TRANSITION, short, NOTES, [])
    assert tokens(problems) == ["note-removed-unassembled"]
    assert problems[0]["file"] == "12.md"
    assert "Twelve heading" in problems[0]["detail"]


def test_compare_assembly_dropping_a_bullet_is_refused():
    head = tn.render(TRANSITION, NOTES, "1.1.0")
    assert STEP_A in head
    short = head.replace(STEP_A, "")
    problems = tn.compare_pr(TRANSITION, short, NOTES, [])
    assert tokens(problems) == ["note-removed-unassembled"]
    assert "shortfall" in problems[0]["detail"]


def test_compare_note_file_only_pr_is_clean():
    assert tn.compare_pr(TRANSITION, TRANSITION, [], [("101.md", good(101))]) == []
    assert tn.compare_pr(TRANSITION, TRANSITION, [("101.md", good(101))], [("101.md", good(101))]) == []
    bad = tn.compare_pr(TRANSITION, TRANSITION, [], [("101.md", "garbage\n")])
    assert tokens(bad) == ["note-byu-missing"]


# ------------------------------------------------------------------------ release_problems


def test_release_problems_one_per_note():
    problems = tn.release_problems([("1.md", good(1)), ("2.md", good(2))])
    assert tokens(problems) == ["note-unassembled-at-release"] * 2
    assert [p["file"] for p in problems] == ["1.md", "2.md"]
    assert tokens(tn.release_problems([("1.md", good(1))])) == ["note-unassembled-at-release"]


def test_release_problems_none():
    assert tn.release_problems([]) == []


# ------------------------------------------------------------------------------------ CLI


def _run(capsys, *argv):
    code = tn.main(list(argv))
    out = capsys.readouterr().out.strip()
    return code, json.loads(out) if out else None


def test_cli_check(capsys, tmp_path):
    root = make_root(tmp_path, notes=NOTES)
    code, data = _run(capsys, "check", "--plugin-root", str(root))
    assert code == 0
    assert data == {"ok": True, "problems": [], "notes": ["3-two.md", "12.md"]}
    (root / tn.NOTES_DIRNAME / "7-bad.md").write_text("garbage\n")
    code, data = _run(capsys, "check", "--plugin-root", str(root))
    assert code == 1
    assert data["ok"] is False
    assert tokens(data["problems"]) == ["note-byu-missing"]
    assert data["notes"] == ["3-two.md", "7-bad.md", "12.md"]


def test_cli_render(capsys, tmp_path):
    root = make_root(tmp_path, notes=NOTES)
    code, data = _run(capsys, "render", "--plugin-root", str(root))
    assert code == 0
    assert data == {"ok": True, "text": tn.render(TRANSITION, NOTES, tn.UNRELEASED)}
    (root / tn.NOTES_DIRNAME / "7-bad.md").write_text("garbage\n")
    code, data = _run(capsys, "render", "--plugin-root", str(root))
    assert code == 1
    assert data["reason"] == "notes-malformed" and data["ok"] is False


def test_cli_assemble(capsys, tmp_path):
    root = make_root(tmp_path, notes=NOTES)
    code, data = _run(capsys, "assemble", "--plugin-root", str(root), "--version", "1.1.0")
    assert code == 0
    assert set(data) == {"ok", "version", "assembled", "transition"}
    assert data["ok"] is True and data["version"] == "1.1.0"
    assert data["assembled"] == ["3-two.md", "12.md"]
    assert sorted(os.listdir(root / tn.NOTES_DIRNAME)) == ["README.md"]
    code, data = _run(capsys, "assemble", "--plugin-root", str(root), "--version", "bad")
    assert code == 1 and data["reason"] == "version-invalid"


def test_cli_usage_errors_exit_two(capsys, tmp_path):
    assert tn.main([]) == 2
    assert tn.main(["check"]) == 2
    assert tn.main(["assemble", "--plugin-root", str(tmp_path)]) == 2
    assert tn.main(["nope", "--plugin-root", str(tmp_path)]) == 2
    capsys.readouterr()


def test_cli_as_a_script(tmp_path):
    root = make_root(tmp_path, notes=NOTES)
    done = subprocess.run(
        [sys.executable, "-B", os.path.join(_LIB, "transition_notes.py"), "check", "--plugin-root", str(root)],
        capture_output=True, text=True,
    )
    assert done.returncode == 0
    assert json.loads(done.stdout)["ok"] is True
