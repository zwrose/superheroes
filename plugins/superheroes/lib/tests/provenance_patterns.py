"""The provenance patterns the shipped review-sheet files must never match, in one place."""

PROVENANCE_PATTERNS = [
    r"\b(?:U?FR|NFR)-?\d",
    r"\bR\d{1,2}\b",
    r"\bC\d(?:-L\d)?\b",
    r"[Rr]uling \d",
    r"#\d{2,}",
    r"HANDOFF",
    r"discovery-notes",
]
