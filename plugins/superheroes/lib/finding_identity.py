#!/usr/bin/env python3
"""The one deterministic finding-identity normalization (CONVENTIONS §11 single home).

Imported by circuit_breaker (dedupe/recurrence), review_handoff (UFR-3 dedupe), and
review_acceptance (the FR-14 recorded trace key). Reword-sensitive by construction — each
consumer is assigned the failure direction safe for it (see the plan's "Finding identity").

`clamp_title` is re-exported from `review_memory` (its canonical home — also consumed by
`review_memory.class_key`) so every caller here gets the same bounded title everywhere else
in the system uses, rather than a second clamp definition.
"""

import re

from review_memory import clamp_title

_NON_WORD = re.compile(r"[^\w\s]", re.ASCII)   # JS \w is ASCII-only — match it
_WS = re.compile(r"\s+", re.ASCII)


def normalize_title(title):
    t = title.lower()
    t = _NON_WORD.sub("", t)
    t = _WS.sub(" ", t)
    return t.strip()


def finding_label(finding):
    return finding.get("title") or finding.get("summary") or ""


def finding_identity(finding):
    return f"{finding.get('file') or ''}::{normalize_title(clamp_title(finding_label(finding)))}"
