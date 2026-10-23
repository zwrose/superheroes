#!/usr/bin/env python3
"""The bite-proof record format an implementer order carries inline (#2082).

A sandboxed implementer cannot read ``rubric/bite-proof.md``, so an order that asks for a
bite-proof record carries the record's format in its prompt. The text is cut from the rubric at
dispatch time — the rubric stays the one source; nothing here keeps a copy of it.

``block_for(order_text)`` returns ``(block, reason)``: the block to insert when the authored
order names a bite-proof, ``""`` when it does not, and ``(None, REASON_UNREADABLE)`` when the
order asks but the rubric's format cannot be cut. "Names a bite-proof" is a best-effort scan: the
words ``bite-proof``/``bite proof`` anywhere in the order once every verbatim implementer-template
copy is masked (the template itself names bite-proofs on every order).
"""
from __future__ import annotations

import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import order_lint  # noqa: E402  mask_template — the one home of implementer-template masking

RUBRIC_PATH = os.path.join(os.path.dirname(_LIB_DIR), "rubric", "bite-proof.md")
REASON_UNREADABLE = "bite-proof-format-unreadable"
HEADING = "## Bite-proof record format (from the plugin's rubric/bite-proof.md)"

# The two cuts: the record's shape, and the disclosures owed when a proof cannot be produced.
RECORD_START = "**The bite-proof record for every detector your order adds or changes**"
RECORD_END = "**Where each part lives"
DISCLOSURE_START = "\n## When the proof cannot be produced\n"
DISCLOSURE_END = "\n## "

_ASKS = re.compile(r"bite[- ]proof", re.IGNORECASE)


def _cut(text, start, end):
    i = text.find(start)
    if i < 0 or text.find(start, i + 1) >= 0:
        return None
    j = text.find(end, i + len(start))
    if j < 0:
        return None
    return text[i:j].strip()


def format_text(path=None):
    """The record format cut from the rubric; None when unreadable or a marker is not unique."""
    try:
        with open(path or RUBRIC_PATH, encoding="utf-8") as fh:
            rubric = order_lint.normalize_newlines(fh.read())
    except (OSError, UnicodeDecodeError):
        return None
    record = _cut(rubric, RECORD_START, RECORD_END)
    disclosure = _cut(rubric, DISCLOSURE_START, DISCLOSURE_END)
    if not record or not disclosure:
        return None
    return HEADING + "\n\n" + record + "\n\n" + "#" + disclosure


def asks_for_record(order_text):
    masked, _ = order_lint.mask_template(order_text)
    return bool(_ASKS.search(masked))


def block_for(order_text, path=None):
    if not asks_for_record(order_text):
        return "", None
    text = format_text(path)
    # axis: an order that asks for a record never dispatches without the format — see bite-proof record wo_2082_format
    if text is None:
        return None, REASON_UNREADABLE
    return text, None
