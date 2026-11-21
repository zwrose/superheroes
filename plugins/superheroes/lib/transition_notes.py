#!/usr/bin/env python3
"""Upgrade notes as per-PR files, assembled into TRANSITION.md at release (issue 2590).

Each pull request writes its upgrade note as its own file in the plugin's transition-notes folder,
so two open PRs never touch the same lines. The release doc pass runs `assemble`, which merges the
files into TRANSITION.md under a version and removes them.

A note file is: `### Before you upgrade`, one or more top-level `- ` bullets that each open with the
strict marker `**Before switching.**` or `**After switching.**`, then one or more `### <heading>`
sections. Assembly puts every bullet into the version's `### Before you upgrade` list (so
adopt_version reads it as that version's upgrade steps) and copies every section whole.

The pull-request check (`compare_pr`) reads TRANSITION.md only as a multiset of `### ` headings and a
count of upgrade-step bullets. A heading renamed or reworded in TRANSITION.md outside an assembly
therefore reads as an added heading, and is refused on purpose: write the change as a note file.

Pure functions take text and return values; `read_notes`, `transition_text` and `assemble` touch the
disk; `main` is the CLI, one JSON object on stdout per call.
"""
import argparse
import collections
import json
import os
import re
import sys

NOTES_DIRNAME = "transition-notes"
README_NAME = "README.md"
NOTE_NAME = re.compile(r"^[0-9]+(-[a-z0-9]+(?:-[a-z0-9]+)*)?\.md$")
UNRELEASED = "Unreleased"
BYU = "Before you upgrade"
INTRO = "Check these in a consuming project when it adopts {target}. Each step names the note it comes from."
MARKER = re.compile(r"^\*\*(Before|After) switching\.\*\*(?=\s|$)")

_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
_COMMENT = re.compile(r"^\s*<!--.*-->\s*$")
_LEADING_INT = re.compile(r"^[0-9]+")
_H12 = re.compile(r"^#{1,2} ")
_TRANSITION = "TRANSITION.md"


class NoteError(ValueError):
    """Raised when notes (or the label) are refused; `.problems` lists every problem."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(p["token"] + " (" + p["file"] + ")" for p in self.problems))


def _p(file, token, detail):
    return {"file": file, "token": token, "detail": detail}


def _fence(line):
    return line.strip().startswith("```")


def _intro(label):
    return INTRO.format(target="the next release" if label == UNRELEASED else label)


def notes_dir(plugin_root):
    return os.path.join(plugin_root, NOTES_DIRNAME)


def sort_key(name):
    """Assembly order: (leading integer, name); a name with no leading integer sorts last, by name."""
    m = _LEADING_INT.match(name)
    return (int(m.group(0)) if m else float("inf"), name)


def read_notes(plugin_root):
    """Every regular file in the notes folder except the README, any extension, in assembly order."""
    folder = notes_dir(plugin_root)
    if not os.path.isdir(folder):
        return []
    out = []
    for fname in sorted(os.listdir(folder), key=sort_key):
        path = os.path.join(folder, fname)
        if fname == README_NAME or not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            out.append((fname, fh.read()))
    return out


# axis: refusal of a malformed note file (one token per distinct shape failure); parse_note bites
# on shape, check_notes on the cross-note duplicate heading. Each token's raise is one statement.
def parse_note(name, text):
    problems = []
    note = {"name": name, "bullets": [], "sections": [], "problems": problems}
    if not text.strip():
        problems.append(_p(name, "note-empty", "The note file is empty."))
        return note
    if not NOTE_NAME.match(name):
        problems.append(_p(name, "note-name-invalid", "The file name must be the issue number, optionally followed by a lowercase slug, ending in .md."))
    lines = text.split("\n")
    state, fence = [], False
    for ln in lines:
        if _fence(ln):
            state.append("close" if fence else "open")
            fence = not fence
        else:
            state.append("in" if fence else "")
    if fence:
        problems.append(_p(name, "note-fence-unbalanced", "A code fence is opened and never closed."))
    for k, ln in enumerate(lines):
        if not state[k] and _H12.match(ln):
            problems.append(_p(name, "note-heading-level", "A # or ## heading would break the version section: " + ln.strip()[:60]))
    first = 0
    while first < len(lines) and (not lines[first].strip() or _COMMENT.match(lines[first])):
        first += 1
    head = lines[first] if first < len(lines) else ""
    byu_ok = not state[first] and head.startswith("### ") and head[4:].strip() == BYU if first < len(lines) else False
    if not byu_ok:
        problems.append(_p(name, "note-byu-missing", "The first content line must be the heading ### " + BYU + "."))
    region = "byu" if byu_ok else "pre"
    bullets, sections, cur = [], [], None
    for k in range(first + 1 if byu_ok else first, len(lines)):
        ln, st = lines[k], state[k]
        if not st and ln.startswith("### "):
            title = ln[4:].strip()
            if title == BYU:
                if byu_ok:
                    problems.append(_p(name, "note-byu-repeated", "The heading ### " + BYU + " appears more than once."))
                region, cur = "byu", None
            else:
                region, cur = "section", {"heading": title, "lines": [ln]}
                sections.append(cur)
        elif region == "section":
            cur["lines"].append(ln)
        elif region == "byu":
            if st in ("in", "close") or not ln.strip():
                continue
            if not st and ln.startswith("- "):
                bullets.append([ln])
            elif not st and ln[:1].isspace() and bullets:
                bullets[-1].append(ln)
            else:
                problems.append(_p(name, "note-byu-stray", "Only bullets may sit under ### " + BYU + ", and this line would be lost: " + ln.strip()[:60]))
    if byu_ok and not bullets:
        problems.append(_p(name, "note-byu-empty", "The ### " + BYU + " list has no bullet."))
    note["bullets"] = ["\n".join(b).rstrip() for b in bullets]
    for sec in sections:
        body = sec["lines"]
        while body and not body[-1].strip():
            body.pop()
        note["sections"].append({"heading": sec["heading"], "text": "\n".join(body)})
    for b in note["bullets"]:
        if not MARKER.match(b[2:].lstrip()):
            problems.append(_p(name, "note-bullet-unmarked", "A bullet must open with **Before switching.** or **After switching.**: " + b[2:].strip()[:60]))
    if byu_ok and not sections:
        problems.append(_p(name, "note-section-missing", "The note has no ### section after its bullets."))
    return note


def check_notes(notes):
    problems, seen = [], {}
    for name, text in notes:
        note = parse_note(name, text)
        problems.extend(note["problems"])
        for sec in note["sections"]:
            heading = sec["heading"]
            if heading in seen:
                problems.append(_p(name, "note-heading-duplicate", "The section heading ### " + heading + " is already used in " + seen[heading] + "."))
            else:
                seen[heading] = name
    return problems


def _lines_of(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _sections_of(lines):
    """[[start, end, heading], ...] for each `## ` section outside a fence."""
    out, fence = [], False
    for i, ln in enumerate(lines):
        if _fence(ln):
            fence = not fence
        elif not fence and ln.startswith("## "):
            out.append([i, len(lines), ln[3:].strip()])
    for k in range(len(out) - 1):
        out[k][1] = out[k + 1][0]
    return out


def _scan_byu(sec):
    """In one section's lines (index 0 is its `## ` line): None when it has no `### Before you upgrade`
    subsection, else (start, end, intro, last): the heading's index, the index where the subsection
    ends, the index of its intro line (or None) and the index of its last bullet line (or None)."""
    fence, start, end = False, None, len(sec)
    for i in range(1, len(sec)):
        ln = sec[i]
        if _fence(ln):
            fence = not fence
        elif not fence and ln.startswith(("### ", "#### ")):
            if start is None:
                if ln.startswith("### ") and ln[4:].strip() == BYU:
                    start = i
            else:
                end = i
                break
    if start is None:
        return None
    intro = last = None
    fence = False
    for j in range(start + 1, end):
        ln = sec[j]
        if _fence(ln) or fence:
            # A fenced block after a bullet is that bullet's continuation (a command it shows), so
            # the bullet ends at the fence's close, never before its opening line.
            if _fence(ln):
                fence = not fence
            if last is not None:
                last = j
        elif not ln.strip():
            continue
        elif ln.startswith("- "):
            last = j
        elif ln[:1].isspace() and last is not None:
            last = j
        elif intro is None and last is None:
            intro = j
    return start, end, intro, last


def _fill(sec, label, bullet_lines, section_texts):
    """The section's lines with the notes' bullets and sections added."""
    span = _scan_byu(sec)
    if bullet_lines:
        if span is None:
            body = sec[1:]
            while body and not body[0].strip():
                body.pop(0)
            sec = [sec[0], "", "### " + BYU, "", _intro(label), ""] + bullet_lines + ([""] + body if body else [])
        else:
            start, _end, intro, last = span
            if last is not None:
                sec = sec[:last + 1] + bullet_lines + sec[last + 1:]
            elif intro is not None:
                sec = sec[:intro + 1] + [""] + bullet_lines + sec[intro + 1:]
            else:
                add = ["", _intro(label), ""] + bullet_lines
                if start + 1 < len(sec) and sec[start + 1].strip():
                    add.append("")
                sec = sec[:start + 1] + add + sec[start + 1:]
    while sec and not sec[-1].strip():
        sec = sec[:-1]
    for text in section_texts:
        sec = sec + [""] + text.split("\n")
    return sec


def render(transition_text, notes, label):
    """TRANSITION.md's text with `notes` assembled under `label` (UNRELEASED or X.Y.Z)."""
    problems = []
    if label != UNRELEASED and not (isinstance(label, str) and _VERSION.fullmatch(label)):
        problems.append(_p(_TRANSITION, "version-invalid", "The label must be Unreleased or a version X.Y.Z."))
    problems.extend(check_notes(notes))
    if problems:
        raise NoteError(problems)
    parsed = [parse_note(n, t) for n, t in sorted(notes, key=lambda n: sort_key(n[0]))]
    bullet_lines = [ln for p in parsed for b in p["bullets"] for ln in b.split("\n")]
    section_texts = [s["text"] for p in parsed for s in p["sections"]]
    lines = _lines_of(transition_text)
    secs = _sections_of(lines)
    exact = [s for s in secs if s[2] == label]
    renamed = [s for s in secs if s[2] == UNRELEASED] if label != UNRELEASED and not exact else []
    if exact or renamed:
        start, end, _heading = (exact or renamed)[0]
        sec = list(lines[start:end])
        if renamed:
            sec[0] = "## " + label
            span = _scan_byu(sec)
            if span is not None and span[2] is not None and sec[span[2]] == _intro(UNRELEASED):
                sec[span[2]] = _intro(label)
        elif not parsed:
            return transition_text
        sec = _fill(sec, label, bullet_lines, section_texts)
        rest = lines[end:]
        out = lines[:start] + sec + ([""] + rest if rest else [])
        return "\n".join(out) + "\n"
    if not parsed:
        return transition_text
    new = ["## " + label, "", "### " + BYU, "", _intro(label), ""] + bullet_lines
    for text in section_texts:
        new += [""] + text.split("\n")
    cut = secs[0][0] if secs else len(lines)
    head = lines[:cut]
    while head and not head[-1].strip():
        head.pop()
    out = head + ([""] if head else []) + new + ([""] + lines[cut:] if secs else [])
    return "\n".join(out) + "\n"


def _read_transition(plugin_root):
    with open(os.path.join(plugin_root, _TRANSITION), encoding="utf-8") as fh:
        return fh.read()


def transition_text(plugin_root):
    """TRANSITION.md's text with the notes folder rendered under Unreleased; what readers call
    instead of opening TRANSITION.md. Raises NoteError when the notes are malformed."""
    return render(_read_transition(plugin_root), read_notes(plugin_root), UNRELEASED)


def structure(transition_text):
    """{"headings": every ### heading inside a ## section (Before you upgrade excluded), "bullets":
    the count of top-level `- ` bullets under every ### Before you upgrade}; fences skipped."""
    headings, bullets = [], 0
    fence = in_section = in_byu = False
    for ln in transition_text.split("\n"):
        if _fence(ln):
            fence = not fence
        elif fence:
            continue
        elif ln.startswith("## "):
            in_section, in_byu = True, False
        elif ln.startswith("### "):
            title = ln[4:].strip()
            in_byu = title == BYU
            if in_section and not in_byu:
                headings.append(title)
        elif ln.startswith("#### "):
            in_byu = False
        elif in_byu and in_section and ln.startswith("- "):
            bullets += 1
    return {"headings": headings, "bullets": bullets}


# axis: a pull request that edits TRANSITION.md other than by assembling its removed notes; bites on
# an added heading, an added bullet, a removed note whose heading or bullet did not reach the file.
def compare_pr(base_transition, head_transition, base_notes, head_notes):
    problems = []
    base, head = structure(base_transition), structure(head_transition)
    head_names = {n for n, _ in head_notes}
    removed = [parse_note(n, t) for n, t in base_notes if n not in head_names]
    removed_headings = collections.Counter(s["heading"] for p in removed for s in p["sections"])
    removed_bullets = sum(len(p["bullets"]) for p in removed)
    added = collections.Counter(head["headings"]) - collections.Counter(base["headings"])
    for heading in sorted((added - removed_headings).elements()):
        problems.append(_p(_TRANSITION, "transition-heading-added", "The heading ### " + heading + " was added to TRANSITION.md; write the note as a file in the notes folder instead."))
    uncovered = collections.Counter(added)
    for p in removed:
        for sec in p["sections"]:
            if uncovered[sec["heading"]] > 0:
                uncovered[sec["heading"]] -= 1
            else:
                problems.append(_p(p["name"], "note-removed-unassembled", "The note was removed but its section ### " + sec["heading"] + " did not reach TRANSITION.md."))
    delta = head["bullets"] - base["bullets"]
    if delta > removed_bullets:
        problems.append(_p(_TRANSITION, "transition-bullet-added", "TRANSITION.md gained " + str(delta - removed_bullets) + " upgrade-step bullet(s) that no removed note accounts for; write them in a note file."))
    if delta < removed_bullets:
        problems.append(_p(_TRANSITION, "note-removed-unassembled", "Removed notes held " + str(removed_bullets) + " bullet(s) but TRANSITION.md gained " + str(delta) + ", a shortfall of " + str(removed_bullets - delta) + "."))
    problems.extend(check_notes(head_notes))
    return problems


# axis: a note file still present when a release is cut (the release pass must have assembled it).
def release_problems(head_notes):
    return [_p(name, "note-unassembled-at-release", "The note file is still present at release; run the assemble step first.")
            for name, _text in head_notes]


def assemble(plugin_root, version):
    """Validate, render under `version`, write TRANSITION.md atomically, then remove each note file."""
    if not (isinstance(version, str) and _VERSION.fullmatch(version)):
        return {"ok": False, "reason": "version-invalid", "detail": "The version must be X.Y.Z."}
    try:
        text = _read_transition(plugin_root)
    except (OSError, ValueError) as exc:
        return {"ok": False, "reason": "transition-unreadable", "detail": str(exc)}
    notes = read_notes(plugin_root)
    try:
        new_text = render(text, notes, version)
    except NoteError as exc:
        return {"ok": False, "reason": "notes-malformed", "problems": exc.problems}
    path = os.path.join(plugin_root, _TRANSITION)
    if new_text != text:
        tmp = path + ".tmp-" + str(os.getpid())
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new_text)
            os.replace(tmp, path)
        except OSError as exc:
            return {"ok": False, "reason": "transition-unwritable", "detail": str(exc)}
    removed, stuck = [], []
    for name, _text in notes:
        try:
            os.remove(os.path.join(notes_dir(plugin_root), name))
            removed.append(name)
        except OSError as exc:
            stuck.append({"file": name, "detail": str(exc)})
    if stuck:
        return {"ok": False, "reason": "note-remove-failed", "assembled": removed, "stuck": stuck, "transition": path}
    return {"ok": True, "version": version, "assembled": removed, "transition": path}


def _emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="transition_notes.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("check", "render", "assemble"):
        sp = sub.add_parser(cmd)
        sp.add_argument("--plugin-root", required=True)
        if cmd == "assemble":
            sp.add_argument("--version", required=True)
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    root = args.plugin_root
    if args.cmd == "check":
        notes = read_notes(root)
        problems = check_notes(notes)
        _emit({"ok": not problems, "problems": problems, "notes": [n for n, _ in notes]})
        return 0 if not problems else 1
    if args.cmd == "render":
        try:
            _emit({"ok": True, "text": transition_text(root)})
            return 0
        except NoteError as exc:
            _emit({"ok": False, "reason": "notes-malformed", "problems": exc.problems})
        except (OSError, ValueError) as exc:
            _emit({"ok": False, "reason": "transition-unreadable", "detail": str(exc)})
        return 1
    result = assemble(root, args.version)
    _emit(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
