#!/usr/bin/env python3
"""superheroes (acceptance harness): reserved stamp + fixture materializer & drift check.

Foundational layer of the standalone showrunner acceptance harness (work-item
`standalone-showrunner-acceptance-harness-df979d`). It owns three things, defined
here **once** and imported everywhere else in the harness (fixture, cleanup, reclaim):

  1. The reserved namespace prefix + the full-stamp token grammar. Every artifact the
     harness mints (throwaway work-item slug, branch, PR title) embeds a full stamp
     whole; every cleanup/reclaim decision routes on `parse_stamp` alone — so the
     harness only ever touches names that parse to a valid *full* stamp, never a bare
     prefix or a substring (UFR-3: never mutate real state).
  2. The fixture materializer: copies the committed fixture triple into a fresh
     stamped throwaway work-item slug (with `gates: {review: passed}` so preflight
     admits it) and reports the stamped names. Two materializations with distinct
     unique ids never collide.
  3. The drift check: the committed fixture is `ok` only when its declared
     `expected_phases` equals the pipeline's current phase list AND its single target
     file exists — else it names the drift (absent fixture, phase drift, missing target).

All functions are pure/deterministic given their inputs except `materialize`, which is
the one I/O function (it copies files). Nothing here reads a clock, network, or subprocess.

The stamp id grammar is deliberately hyphen-free (`[a-z0-9]+`): a unique id is normalized
by lowercasing and dropping every character outside `[a-z0-9]`. That keeps `parse_stamp`
unambiguous when the stamp is embedded inside a larger hyphenated name (e.g.
`wi-<stamp>-branch`): the id token stops cleanly at the first non-`[a-z0-9]` character,
so the parse never greedily swallows a surrounding suffix.
"""
import os
import re
import shutil

# The harness-owned namespace prefix. Every artifact the harness mints embeds a full
# stamp beginning with this. Defined once here; imported everywhere (cleanup, reclaim).
RESERVED_PREFIX = "accept-harness-"

# A full stamp is the reserved prefix followed by a non-empty hyphen-free id token.
# Anchored on a word/name boundary (start, or a non-[a-z0-9] separator like '-', ' ',
# '/', ':') so a bare prefix, a substring, or a prefix + invalid chars never parse.
_STAMP_RE = re.compile(r"(?:^|(?<=[^a-z0-9]))(" + re.escape(RESERVED_PREFIX) + r"[a-z0-9]+)")

# The fixture's declared-phase-list frontmatter key (read by expected_phases).
_PHASES_KEY = "expected_phases"


def _normalize_id(unique_id):
    """Lowercase and drop every character outside [a-z0-9], yielding a hyphen-free id
    token. Distinct inputs that differ only in dropped characters could collide, but the
    harness supplies opaque unique ids, and the caller is responsible for uniqueness of
    the *normalized* form (the materialize collision test passes distinct normalized ids)."""
    return re.sub(r"[^a-z0-9]", "", (unique_id or "").lower())


def make_stamp(unique_id):
    """Reserved prefix + normalized unique id -> the full stamp token."""
    norm = _normalize_id(unique_id)
    if not norm:
        raise ValueError("unique_id must contain at least one [a-z0-9] character after normalization")
    return RESERVED_PREFIX + norm


def parse_stamp(name):
    """Return the full stamp embedded in `name` (in its defined name position) if `name`
    contains a structurally-valid full stamp, else None. A bare reserved prefix, or the
    prefix followed by invalid (non-[a-z0-9]) characters, returns None — cleanup routes
    those to the reported-left-behind path, never a delete."""
    if not name:
        return None
    m = _STAMP_RE.search(name)
    return m.group(1) if m else None


# --- fixture I/O -----------------------------------------------------------

_FIXTURE_DOCS = ("spec.md", "plan.md", "tasks.md")
_TARGET_FILE = "target.txt"


def expected_phases(fixture_dir):
    """Read the fixture's declared `expected_phases` list from the tasks doc frontmatter.
    Missing fixture / tasks doc / key -> [] (drift_check then reports the drift)."""
    tasks_path = os.path.join(fixture_dir, "tasks.md")
    if not os.path.isfile(tasks_path):
        return []
    with open(tasks_path, encoding="utf-8") as fh:
        text = fh.read()
    return _parse_expected_phases(text)


def _parse_expected_phases(text):
    """Parse the frontmatter `expected_phases:` block — a plain YAML list of `- item`
    lines. Kept dependency-free (no yaml import) so this pure helper stays import-light."""
    lines = text.splitlines()
    # Locate the frontmatter fence.
    if not lines or lines[0].strip() != "---":
        return []
    fm_end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm_end = i
            break
    if fm_end is None:
        return []
    phases = []
    in_block = False
    for line in lines[1:fm_end]:
        stripped = line.strip()
        if not in_block:
            if stripped == _PHASES_KEY + ":":
                in_block = True
            continue
        # inside the block: collect `- item` lines; a non-indented key ends it.
        if stripped.startswith("- "):
            phases.append(stripped[2:].strip())
        elif stripped == "" :
            continue
        elif not line.startswith((" ", "\t")):
            # a new top-level key ends the list block
            break
        else:
            break
    return phases


def materialize(unique_id, fixture_dir, dest_store_dir):
    """Copy the committed fixture triple into a fresh stamped throwaway work-item slug
    (with `gates: {review: passed}` so preflight admits it) and return the stamped names.
    Two materializations with distinct unique ids never collide. This is the one I/O
    function in this module."""
    stamp = make_stamp(unique_id)
    work_item = stamp                      # the stamped throwaway work-item slug
    branch = "wi-%s" % stamp               # the stamped build branch
    pr_title = "%s acceptance fixture" % stamp

    dest_dir = os.path.join(dest_store_dir, work_item)
    os.makedirs(dest_dir, exist_ok=True)

    paths = []
    for doc in _FIXTURE_DOCS:
        src = os.path.join(fixture_dir, doc)
        with open(src, encoding="utf-8") as fh:
            body = fh.read()
        body = _rewrite_work_item(body, work_item)
        if doc == "tasks.md":
            body = _ensure_passed_gate(body)
        out = os.path.join(dest_dir, doc)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(body)
        paths.append(out)

    # copy the target file alongside so the materialized work-item is self-contained
    src_target = os.path.join(fixture_dir, _TARGET_FILE)
    if os.path.isfile(src_target):
        out_target = os.path.join(dest_dir, _TARGET_FILE)
        shutil.copyfile(src_target, out_target)
        paths.append(out_target)

    return {"work_item": work_item, "branch": branch, "pr_title": pr_title, "paths": paths}


def _rewrite_work_item(body, work_item):
    """Rewrite each frontmatter `workItem:` reference (top-level and the nested
    `parent: {workItem: ...}`) to the stamped slug, so the materialized triple's linkage
    points at the throwaway work-item rather than the fixture placeholder."""
    body = re.sub(r"(?m)^workItem:\s*\S+\s*$", "workItem: %s" % work_item, body)
    body = re.sub(r"(workItem:\s*)([A-Za-z0-9_-]+)(\s*,\s*docType:)",
                  r"\g<1>%s\g<3>" % work_item, body)
    return body


def _ensure_passed_gate(body):
    """Guarantee the tasks doc carries `gates: {review: passed}` so preflight admits the
    throwaway work-item. Rewrites an existing gates line; if absent, no-op (the committed
    fixture already declares it)."""
    if "gates: {review: passed}" in body:
        return body
    return re.sub(r"(?m)^gates:.*$", "gates: {review: passed}", body)


def drift_check(fixture_dir, pipeline_phases, target_exists):
    """`ok` only when the fixture's declared `expected_phases` equals `pipeline_phases`
    AND its single target file exists; else `ok: False` naming the drift (absent fixture,
    phase-list drift, or missing target). Fail-closed: an absent/unreadable fixture fails."""
    if not fixture_dir or not os.path.isdir(fixture_dir):
        return {"ok": False, "reason": "fixture directory is absent or unreadable: %r" % fixture_dir}
    declared = expected_phases(fixture_dir)
    if not declared:
        return {"ok": False, "reason": "fixture declares no expected_phases (absent fixture tasks or phase list)"}
    if list(declared) != list(pipeline_phases):
        return {"ok": False,
                "reason": "phase-list drift: fixture expected_phases %r != pipeline phases %r"
                          % (list(declared), list(pipeline_phases))}
    if not target_exists:
        return {"ok": False, "reason": "fixture target file is missing"}
    return {"ok": True, "reason": "no drift: phases match and target exists"}
