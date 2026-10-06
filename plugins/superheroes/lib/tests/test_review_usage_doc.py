"""Guards for the review template's usage doc and the glossary entries it links."""
import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
USAGE_DOC = PLUGIN / "theme" / "review-template.md"
GLOSSARY = PLUGIN / "rubric" / "glossary.md"

CAPABILITIES = '{"db": {"rules": [{"path": "", "read": "view", "write": "owner"}]}, "user": {}}'

# The same patterns test_review_template.py forbids in the shipped files.
PROVENANCE_PATTERNS = [
    r"\b(?:U?FR|NFR)-?\d", r"\bR\d{1,2}\b", r"\bC\d(?:-L\d)?\b", r"[Rr]uling \d",
    r"#\d{2,}", r"HANDOFF", r"discovery-notes",
]


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


# Bites on: the publish call losing its store and viewer declaration, or the doc dropping the answer document's shape.
def test_usage_doc_declares_the_store_and_document_shape():
    doc = _doc()
    assert "capabilities = %s" % CAPABILITIES in doc
    for value in ('"aligned"', '"discuss"', '"option"'):
        assert value in doc, "the doc doesn't show the answer value %s" % value
    assert "`answers/<card id>`" in doc


# Bites on: spec provenance (requirement, ruling, issue, work-item numbers or handoff references) leaking into the glossary section.
def test_new_glossary_section_carries_no_provenance():
    section = _section(GLOSSARY.read_text(encoding="utf-8"), "Review sheets")
    for pattern in PROVENANCE_PATTERNS:
        assert not re.search(pattern, section), "## Review sheets matches %s" % pattern
