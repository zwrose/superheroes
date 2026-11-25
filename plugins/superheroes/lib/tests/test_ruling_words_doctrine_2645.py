"""A recorded "fix it" ruling goes to the build as a fix, and the vet reads ruling words (#2645).

The review record settles a finding through `ownerRulings` without reading what the owner's words
decide, so the instruction text carries the rule in three homes, each stating only its own part:
the review-record doctrine (a recorded ruling settles a finding only as it stands), the builder's
charter (a fix-ordering ruling goes to the build as a fix), and the vet doctrine (the vet reads the
words and holds a PR whose ordered fix is missing). The vet is executed by a session, not by code,
so these tests guard the instruction text: each fails when its home drops its part or when a part
is stated in a second home.

Reads three named Markdown files; it never enumerates the plugin tree.
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN = os.path.dirname(os.path.dirname(_HERE))

_RECORD = ("skills", "review-code", "reference", "review-record.md")
_BUILDER = ("skills", "workhorse", "SKILL.md")
_VET = ("skills", "showrunner", "reference", "vet-receipt.md")


def _read(parts):
    with open(os.path.join(_PLUGIN, *parts), encoding="utf-8") as fh:
        return fh.read()


def _flat(text):
    return re.sub(r"\s+", " ", text)


def _owner_rulings_entry():
    record = _read(_RECORD)
    lines = [line for line in record.splitlines() if line.startswith("- Optional `ownerRulings`:")]
    assert len(lines) == 1, "review-record.md must hold exactly one ownerRulings entry"
    return lines[0]


def _followable_ruling_paragraph():
    vet = _read(_VET)
    paras = [p for p in vet.split("\n\n") if p.startswith('A `ruling` whose reason starts `owner ruling "<words>" (<url>)` is followable.')]
    assert len(paras) == 1, "vet-receipt.md must hold exactly one followable-ruling paragraph"
    return _flat(paras[0])


def _builder_rule():
    builder = _flat(_read(_BUILDER))
    start = builder.index("**A ruling that orders a fix goes to the build as a fix")
    return builder[start:builder.index("**Bounded acceptance", start)]


def test_record_entry_says_a_ruling_settles_only_as_it_stands_and_points_fix_rulings_to_the_builder():
    # axis: the ownerRulings entry states that the writer never reads what the words decide, so a recorded ruling settles the finding only as it stands, and sends a fix-ordering ruling to the builder's charter
    entry = _owner_rulings_entry()
    assert "A recorded ruling settles the finding only as it stands" in entry
    assert "never reads what they decide" in entry
    assert "Hand over only a ruling that accepts the finding as it stands" in entry
    assert "a ruling that orders a fix goes to the build as the builder's charter says (`skills/workhorse/SKILL.md` § 10)" in entry


def test_builder_routes_a_fix_ruling_to_the_build_never_to_owner_rulings():
    # axis: the builder's charter sends a fix-ordering ruling to the build (the loop's guidance ruling with no owner-ruling citation while a loop runs, else a fix and a fresh review), never to ownerRulings
    rule = _builder_rule()
    assert "goes to the build as a fix, never to `ownerRulings`" in rule
    assert "`guidance` ruling with no `owner-ruling` `decidedBy`" in rule
    assert "make the fix and have it reviewed afresh" in rule


def test_vet_reads_the_words_and_holds_a_pr_whose_ordered_fix_is_missing():
    # axis: the vet's followable-ruling paragraph reads every owner ruling's words, checks an ordered fix at the record's final commit and on a differing head, and holds the PR when any check fails
    para = _followable_ruling_paragraph()
    assert "The vet also reads the ruling's words" in para
    assert "where the words order a fix, the vet confirms that fix holds at the record's final commit" in para
    assert "when the PR head differs from it, on the head being vetted too" in para
    assert para.endswith("If any of these fails, the row holds the PR.")


def test_each_part_is_stated_in_one_home():
    # axis: no part of the rule is stated twice: the settles-as-it-stands rule lives only in the record doctrine, the routing only in the builder's charter, and the words check only in the vet doctrine
    record = _flat(_read(_RECORD))
    builder = _flat(_read(_BUILDER))
    vet = _flat(_read(_VET))
    homes = {"record": record, "builder": builder, "vet": vet}
    parts = {
        "settles the finding only as it stands": "record",
        "goes to the build as a fix, never to `ownerRulings`": "builder",
        "The vet also reads the ruling's words": "vet",
    }
    for phrase, home in parts.items():
        found = sorted(name for name, text in homes.items() if phrase in text)
        assert found == [home], f"{phrase!r} is stated in {found}, expected only {home}"
        assert homes[home].count(phrase) == 1, f"{phrase!r} is stated more than once in {home}"
