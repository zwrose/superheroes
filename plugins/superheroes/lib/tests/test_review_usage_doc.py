"""Guards for the review template's usage doc and the glossary entries it links."""
import json
import re
from pathlib import Path

from provenance_patterns import PROVENANCE_PATTERNS

PLUGIN = Path(__file__).resolve().parents[2]
USAGE_DOC = PLUGIN / "theme" / "review-template.md"
GLOSSARY = PLUGIN / "rubric" / "glossary.md"



def _doc():
    return USAGE_DOC.read_text(encoding="utf-8")


def _section(text, heading):
    """The body of the `## heading` section, up to the next `## ` heading."""
    match = re.search(r"^## %s\n(.*?)(?=^## |\Z)" % re.escape(heading), text, re.S | re.M)
    assert match, "no ## %s section" % heading
    return match.group(1)


def _slug(heading_text):
    return heading_text.strip().lower().replace(" ", "-")


# Bites on: the glossary losing its Review sheets section, or the Card or Sheet entry, or an entry with no definition.
def test_glossary_defines_card_and_sheet():
    section = _section(GLOSSARY.read_text(encoding="utf-8"), "Review sheets")
    for term in ("Card", "Sheet"):
        match = re.search(r"^### %s\n\n(.*?)(?=^#{2,3} |\Z)" % term, section, re.S | re.M)
        assert match, "no ### %s under ## Review sheets" % term
        assert match.group(1).strip(), "### %s has no definition" % term


# Bites on: a glossary link in the usage doc that no longer resolves, or the doc defining card or sheet itself.
def test_usage_doc_links_the_glossary_terms():
    doc = _doc()
    glossary = GLOSSARY.read_text(encoding="utf-8")
    anchors = {_slug(heading) for heading in re.findall(r"^#{2,3} (.+)$", glossary, re.M)}
    for term in ("card", "sheet"):
        link = "(../rubric/glossary.md#%s)" % term
        assert link in doc, "the usage doc doesn't link %s" % link
        assert term in anchors, "the glossary has no heading for #%s" % term
    for line in doc.splitlines():
        assert not re.match(r"\s*(?:\*\*(?:Card|Sheet)|(?:Card|Sheet):)", line), "the doc defines a term: %s" % line


# Bites on: an answer rule stated a second time (or dropped), so the doc and a reader disagree about which wording rules.
def test_usage_doc_states_each_answer_rule_once():
    doc = " ".join(_doc().split())
    sentinels = {
        "read together": "never acts on a single tap",
        "disagreeing note": "is read as Discuss",
        "chat-prose fallback": "numbered chat prose",
    }
    for rule, phrase in sentinels.items():
        assert doc.count(phrase) == 1, "%s: %r appears %d times" % (rule, phrase, doc.count(phrase))


# Bites on: the "Who uses it" section naming a use beyond discovery's sheets and the owner's request.
def test_usage_doc_names_no_other_expected_use():
    section = _section(_doc(), "Who uses it")
    lowered = section.lower()
    assert "discovery" in lowered and "remainder" in lowered and "final" in lowered
    for banned in ("PR walk", "merge review", "vet", "showrunner", "advisor"):
        assert banned.lower() not in lowered, "the section names %r" % banned


# Bites on: the publish call losing its store and viewer declaration (the owner-only write or the view read), or the doc dropping the answer document's shape.
def test_usage_doc_declares_the_store_and_document_shape():
    doc = _doc()
    # The doc's own publish call is the one home of the declaration; the test reads it, never restates it.
    declared = re.findall(r"^capabilities = (.+)$", doc, re.M)
    assert len(declared) == 1, "the doc declares capabilities %d times" % len(declared)
    capabilities = json.loads(declared[0])
    # Properties of the declaration, not a copy of it: a root rule limits writes to the owner, and the viewer is declared.
    root = [rule for rule in capabilities["db"]["rules"] if rule["path"] == ""]
    assert len(root) == 1 and root[0]["write"] == "owner", "the declaration no longer limits writes to the owner"
    assert root[0]["read"] == "view", "the declaration no longer lets everyone who can open the sheet read it"
    assert "user" in capabilities
    assert "`sheet.schema.json` defines at `$defs/answer`" in doc, "the doc doesn't cite the answer document's schema"


# Bites on: spec provenance (requirement, ruling, issue, work-item numbers or handoff references) leaking into the glossary section.
def test_new_glossary_section_carries_no_provenance():
    section = _section(GLOSSARY.read_text(encoding="utf-8"), "Review sheets")
    for pattern in PROVENANCE_PATTERNS:
        assert not re.search(pattern, section), "## Review sheets matches %s" % pattern


# Bites on: the layout section going missing, dropping the Previous and Next, Why only these, not-loaded or never-folds statements, naming Done for now again, or no longer saying that leaving needs no button and what the footer tells the owner.
def test_usage_doc_describes_the_sheet_layout():
    section = " ".join(_section(_doc(), "How a sheet is laid out").split())
    for phrase in ("Previous", "Next", "Why only these", "answers not loaded", "never folds",
                   "comes back when the same link is opened again", "leaving needs no button",
                   "go back to the chat and say they're done once every answer shows it is saved"):
        assert phrase in section, "the layout section doesn't name %r" % phrase
    assert "Done for now" not in _doc(), "the doc still names Done for now"


# Bites on: the layout section no longer saying Previous and Next also sit below the open card, that the folded "Answered" row and "Declined findings" show ▶ closed and ▼ open, or that pinching a laptop trackpad zooms the picture.
def test_usage_doc_describes_the_cues_the_second_stepper_and_the_trackpad_pinch():
    section = _squeezed(_section(_doc(), "How a sheet is laid out"))
    for phrase in (
        "Previous and Next also sit below the open card",
        'The folded "Answered" row, and a final sheet\'s "Declined findings", show ▶ when closed and ▼ when open.',
        "On a laptop, pinching the trackpad zooms the open picture about the pointer, as a phone pinch does.",
    ):
        assert phrase in section, "the layout section doesn't say %r" % phrase


# Bites on: the fallback section no longer pointing at the prose renderer, or pointing at a script that isn't there.
def test_usage_doc_names_the_prose_renderer():
    section = " ".join(_section(_doc(), "When the host can't show a sheet").split())
    assert "lib/sheet_prose.py" in section, "the fallback section doesn't name lib/sheet_prose.py"
    assert "render --sheet" in section, "the fallback section doesn't show the render command"
    assert (PLUGIN / "lib" / "sheet_prose.py").is_file(), "plugins/superheroes/lib/sheet_prose.py doesn't exist"


# Bites on: the publishing section dropping pictures from the staged folder or from `files` (the example call included), the rule that a changed picture is published under a new path, or the rule that a final sheet's pictures are never published by URL; or the layout section no longer telling the owner how a picture opens, zooms and goes missing.
def test_usage_doc_publishes_pictures_with_the_sheet():
    section = " ".join(_section(_doc(), "Publishing a sheet").split())
    for phrase in (
        "Copy every picture a card names by a relative `src` into the staged folder at that same relative path, and add it to `files` under that path.",
        '"plan.png": "<staged plan.png>"',
        "A picture whose `src` is a URL loads from that URL",
        "the sheet shows it as missing",
    ):
        assert phrase in section, "the publishing section doesn't say %r" % phrase
    assert "A changed picture is published under a new path (a new name), so changing a picture always changes `sheet.json` and, on a final sheet, starts it unsigned." in section
    assert "A final sheet's pictures are published with the sheet, never by URL, because a URL picture can change without the sheet changing." in section

    layout = " ".join(_section(_doc(), "How a sheet is laid out").split())
    for phrase in ("Tap a picture on a card to open it on its own", "Pinch or double-tap to zoom", "Close returns to the card", "This picture is missing", "can still be answered"):
        assert phrase in layout, "the layout section doesn't say %r" % phrase


def _squeezed(section):
    return " ".join(section.split())


# Bites on: "How answers come back" losing the reading rule for a final sheet: the verdict document's path, the digest of the published file, reading both together, unanswered meaning ask, a saved Approve not counting alone, or the rules about a single tap and a disagreeing note.
def test_usage_doc_states_the_reading_rule_for_a_final_sheet():
    section = _squeezed(_section(_doc(), "How answers come back"))
    for phrase in (
        "`verdict/<digest>`",
        "SHA-256 of the `sheet.json` it published",
        "shasum -a 256 sheet.json",
        "reads `answers` and `verdict/<digest>` together",
        "uses it only when its `sheet` equals that digest",
        "unanswered",
        "the session asks rather than assuming",
        "A saved Approve never counts as approval on its own; the owner's word in the chat does.",
        "never acts on a single tap",
        "is read as Discuss",
    ):
        assert phrase in section, "the reading rule doesn't say %r" % phrase
    for retired in ("Send verdict", "/sends", "draft"):
        assert retired not in section, "the reading rule still names %r" % retired


# Bites on: "A final sheet" going back to a Send verdict button or draft paths, losing the verdict's path and schema definition, the digest rule (exact bytes, a byte-order mark included, equal to `sheet`), the restore rule for this revision only, the no-`crypto.subtle` line, the next-step line below the last card, or the no-cards case.
def test_usage_doc_describes_the_final_sheet():
    section = _squeezed(_section(_doc(), "A final sheet"))
    for phrase in (
        "`verdict/<digest>`",
        "`$defs/verdict`",
        "Saving…, Saved, Not saved and Try again",
        "exact bytes of the published `sheet.json`",
        "byte-order mark",
        "the document's `sheet` equals it",
        "starts unsigned",
        "reads only the document whose id is its own digest",
        "Another revision's document is ignored",
        "no `crypto.subtle`",
        "Directly below the last card",
        "`sheet-words.json`",
        "a box says what happens next",
        "may have no cards",
    ):
        assert phrase in section, "the final-sheet section doesn't say %r" % phrase
    for retired in ("draft", "/sends", "sendId", "freez", "Verdict sent"):
        assert retired not in section, "the final-sheet section still says %r" % retired
    # Send verdict is named only in the sentence that says there is no such button.
    mentions = [sentence for sentence in re.split(r"(?<=\.) ", section) if "Send verdict" in sentence]
    assert mentions == ["There is no Send verdict button."], mentions
    doc = _doc()
    assert doc.index("## How a sheet is laid out") < doc.index("## A final sheet") < doc.index("## How answers come back")


# Bites on: the usage doc carrying a requirement number, a ruling number, an issue number or a handoff reference.
def test_usage_doc_carries_no_provenance():
    doc = _doc()
    for pattern in PROVENANCE_PATTERNS:
        assert not re.search(pattern, doc), "the usage doc matches %s" % pattern
