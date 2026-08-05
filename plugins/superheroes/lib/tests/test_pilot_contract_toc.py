"""Census: pilot-contract.md's Contents list matches its `##` sections exactly (#866).

The band that built the pilot framework merged this file three times, each merge a union of two
branches' sections. `## Reclaim safety` came through one of those merges with no Contents entry at
all and stayed missing until the §13 re-walk found it by eye — the pre-existing census
(`test_pilot_auth_census.test_new_sections_in_contents`) only checks a hand-maintained list of
sections it was told about, so a section nobody added to that list is invisible to it.

This census is told nothing. It reads the `##` headings out of the document, reads the Contents
list, and requires them to agree one-for-one, in order, with correct numbering and a correct
GitHub anchor. A section added without a Contents entry fails here whatever it is called.
"""
import os
import re

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PILOT_CONTRACT = os.path.join(
    os.path.dirname(_LIB), "reference", "pilot-contract.md"
)

# `1. [Title](#anchor)` — the shape every Contents row uses.
_CONTENTS_ROW_RE = re.compile(r"^(\d+)\.\s+\[(.+?)\]\(#([^)]*)\)\s*$")


def _load_contract():
    with open(_PILOT_CONTRACT, "r", encoding="utf-8") as handle:
        return handle.read()


def _github_anchor(title):
    """Slug a heading the way GitHub does: lowercase, drop punctuation, spaces to hyphens.

    Punctuation is *removed* rather than replaced, which is why an em-dash surrounded by spaces
    yields a doubled hyphen — `Wave runtime — deadline` becomes `wave-runtime--deadline`.
    """
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9 \-]", "", slug)
    return slug.replace(" ", "-")


def _contents_rows(doc):
    separator = doc.find("\n---\n")
    assert separator != -1, "pilot-contract.md missing the Contents separator"
    rows = []
    for line in doc[:separator].splitlines():
        match = _CONTENTS_ROW_RE.match(line.strip())
        if match:
            rows.append((int(match.group(1)), match.group(2), match.group(3)))
    return rows


def _section_headings(doc):
    separator = doc.find("\n---\n")
    body = doc[separator:]
    return [line[3:].strip() for line in body.splitlines() if line.startswith("## ")]


def test_census_population_is_non_vacuous():
    # axis: a parse that silently found nothing would make every assertion below trivially true.
    doc = _load_contract()
    rows = _contents_rows(doc)
    headings = _section_headings(doc)
    assert len(rows) > 20, "Contents parsed to only %d rows" % len(rows)
    assert len(headings) > 20, "document parsed to only %d ## sections" % len(headings)


def test_every_section_has_exactly_one_contents_entry():
    # axis: a `##` section with no Contents entry — or a Contents entry naming no section —
    # reddens. This is the shape that let `## Reclaim safety` go unlisted through three merges.
    doc = _load_contract()
    listed = [row[1] for row in _contents_rows(doc)]
    headings = _section_headings(doc)

    missing = [h for h in headings if h not in listed]
    assert missing == [], (
        "sections with no Contents entry: %s (file: %s)"
        % (", ".join(missing), _PILOT_CONTRACT)
    )
    extra = [t for t in listed if t not in headings]
    assert extra == [], (
        "Contents entries naming no section: %s (file: %s)"
        % (", ".join(extra), _PILOT_CONTRACT)
    )
    duplicates = sorted({t for t in listed if listed.count(t) > 1})
    assert duplicates == [], (
        "Contents lists these more than once: %s (file: %s)"
        % (", ".join(duplicates), _PILOT_CONTRACT)
    )


def test_contents_order_and_numbering_track_the_document():
    # axis: an entry inserted without renumbering, or listed out of document order, reddens.
    doc = _load_contract()
    rows = _contents_rows(doc)
    headings = _section_headings(doc)
    assert [row[1] for row in rows] == headings, (
        "Contents order does not match document order (file: %s)" % _PILOT_CONTRACT
    )
    assert [row[0] for row in rows] == list(range(1, len(headings) + 1)), (
        "Contents numbering is not 1..%d in order: %s (file: %s)"
        % (len(headings), [row[0] for row in rows], _PILOT_CONTRACT)
    )


def test_every_contents_anchor_matches_its_heading():
    # axis: an entry whose link would not land on its own section reddens. Every wrong anchor is
    # named, not just the first, so one run tells you the whole repair.
    rows = _contents_rows(_load_contract())
    wrong = [
        "entry %d %r links to #%s, expected #%s" % (number, title, anchor, _github_anchor(title))
        for number, title, anchor in rows
        if anchor != _github_anchor(title)
    ]
    assert wrong == [], "%s (file: %s)" % ("; ".join(wrong), _PILOT_CONTRACT)
