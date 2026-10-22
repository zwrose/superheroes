#!/usr/bin/env python3
"""Find a break-it test by what it checks, not by its bytes (#2053).

Stdlib only. ``locate`` takes the test file the loop ran and the files the final diff carries, and
says whether the test's statements (its fixture and assertions) appear unchanged, up to formatting
and the test's title, exactly once at module level of one of them. The language fronts
(``break_it_body_py``, ``break_it_body_js``) parse a file into one record per module-level statement;
this module compares the records and refuses whatever it cannot compare: every unreadable file, every
second copy, every binding the host file changes and every module-level test setup the host adds.
Nothing is raised, and a result that is not ``found`` never reads as kept."""
import importlib
import os
import posixpath
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

_FRONTS = ("break_it_body_py", "break_it_body_js")


def _fronts():
    """The loaded fronts; one that is missing is skipped, so its suffixes read unsupported."""
    loaded = []
    for name in _FRONTS:
        try:
            loaded.append(importlib.import_module(name))
        except ImportError:
            continue
    return loaded


def supported_suffixes():
    return frozenset(suffix for front in _fronts() for suffix in front.EXTENSIONS)


def _suffix(path):
    return posixpath.splitext(path.lower())[1] if isinstance(path, str) else ""


def _result(status, reason=None, path=None, titles=None):
    return {"status": status, "reason": reason, "path": path, "titles": titles or []}


def _unresolved(reason):
    return _result("unresolved", reason)


def _front_for(suffix):
    for front in _fronts():
        if suffix in front.EXTENSIONS:
            return front
    return None


def _outside(records, window, original):
    """The refusal reason for the first candidate record outside the matched window that changes what the test
    means, else ``None``."""
    orig_pairs = {pair for rec in original for pair in rec["imports"]}
    names = set()
    for rec in original:
        names |= rec["binds"] | rec["uses"]
    orig_keys = {rec["key"] for rec in original}
    # axis: every import the original bound is bound the same way in the file that holds the test — see bite-proof record wo_a_2053_break_it_body
    if not orig_pairs <= {pair for rec in records for pair in rec["imports"]}:
        return "binding-conflict"
    for index, rec in enumerate(records):
        if index in window:
            continue
        # axis: module-level test setup the host adds is refused, because it would change the test's run — see bite-proof record wo_a_2053_break_it_body
        if rec["hook"] and rec["key"] not in orig_keys:
            return "host-setup"
        for pair in rec["imports"]:
            if pair in orig_pairs:
                continue
            # axis: an import outside the window that rebinds a name the test uses, or star-imports over it, is refused — see bite-proof record wo_a_2053_break_it_body
            if pair[0] == "*" or pair[0] in names:
                return "binding-conflict"
        # axis: a statement outside the window that rebinds a name the test uses is refused — see bite-proof record wo_a_2053_break_it_body
        if rec["kind"] == "stmt" and rec["binds"] & names:
            return "binding-conflict"
    return None


def locate(content, path, candidates):
    """Find the test ``content`` (the file at ``path``) in ``candidates``, a list of ``(path, text)`` where ``text``
    is the decoded file or ``None`` when it could not be decoded.

    Returns ``{"status", "reason", "path", "titles"}``. ``status`` is ``unsupported`` (no front reads
    ``path``), ``none`` (no candidate holds the test), ``unresolved`` (``reason`` says why the search
    cannot decide) or ``found`` (``path`` is the candidate; ``titles`` the ``(old, new)`` pairs that differ)."""
    front = _front_for(_suffix(path))
    if front is None:
        return _result("unsupported")
    try:
        original = front.parse(content)
    except ValueError:
        return _unresolved("body-unparseable")
    body = [rec for rec in original if rec["kind"] == "stmt"]
    if not body:
        return _unresolved("body-empty")
    old_titles = [title for rec in body for title in rec["titles"]]
    names = set()
    for rec in body:
        names |= rec["binds"] | rec["uses"]
    names -= set(old_titles)
    keys = [rec["key"] for rec in body]
    unparseable = False
    matches = []
    for cand_path, text in candidates:
        if _suffix(cand_path) not in front.EXTENSIONS:
            continue
        if text is None:
            unparseable = True
            continue
        if not all(name in text for name in names):
            continue
        try:
            records = front.parse(text)
        except ValueError:
            # axis: a candidate that passes the prefilter and cannot be read leaves the search undecided, even beside a match — see bite-proof record wo_a_2053_break_it_body
            unparseable = True
            continue
        stmts = [index for index, rec in enumerate(records) if rec["kind"] == "stmt"]
        for start in range(len(stmts) - len(body) + 1):
            window = stmts[start:start + len(body)]
            if [records[i]["key"] for i in window] == keys:
                matches.append((cand_path, records, window))
    if unparseable:
        return _unresolved("body-unparseable")
    if not matches:
        return _result("none")
    # axis: a second copy of the test anywhere in the diff makes the match ambiguous, never kept — see bite-proof record wo_a_2053_break_it_body
    if len(matches) > 1:
        return _unresolved("match-ambiguous")
    cand_path, records, window = matches[0]
    reason = _outside(records, set(window), original)
    if reason:
        return _unresolved(reason)
    new_titles = [title for i in window for title in records[i]["titles"]]
    return _result("found", None, cand_path, [(old, new) for old, new in zip(old_titles, new_titles) if old != new])
