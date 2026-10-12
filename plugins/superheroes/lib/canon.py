#!/usr/bin/env python3
"""The Canon write helper: every session holds or appends a Canon line through it.

`rubric/canon-contract.md` owns Canon's rules; this module enforces them at write time. It refuses
an entry that the contract's § What stays out, and where it goes keeps out of Canon, naming the
record's home as that section says it, mints the id by § The id rule, and keeps the file shape.

CLI (one JSON object on stdout; exit 0 on success, 1 on a refusal or failure):
  canon.py append --root R --session-id S [--held-file F] <entry fields>   # write one new entry
  canon.py append --root R --lines-file F                     # append held lines byte for byte
  canon.py hold   --root R --session-id S [--held-file F] <entry fields>
  canon.py ruling-record --date D --time T --words-file F --context C
                         [--post --repo O/R --collector N]    # the standard chat-ruling record

Entry fields: --ground owner-call|principle|ceded-call|take-back, --date, --scope, --ruling,
[--cedes KIND --example EX], [--supersedes ID], [--owners-words W], --where TEXT, [--written D].
`append` writes the file only; the session makes the Canon commit (§ Writing a ruling, steps 7-8).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

CONTRACT = os.path.join(os.path.dirname(_LIB_DIR), "rubric", "canon-contract.md")
STAYS_OUT = "rubric/canon-contract.md § What stays out, and where it goes"
HELD_MARKER = "<!-- superheroes:canon-held -->"
RULING_MARKER = "<!-- superheroes:chat-ruling -->"
SEP = " · "
GROUNDS = ("owner-call", "principle", "ceded-call", "take-back")
# A declared ground that names something § What stays out keeps out, mapped to how its home is read.
STAY_OUT_GROUNDS = {
    "go-word": "act", "launch-word": "act", "tier-word": "act", "force-push-word": "act",
    "filing-word": "act", "merge-word": "merge", "release-word": "merge",
    "disposition": "disposition", "bookkeeping": "board", "phase-bookkeeping": "board",
}
GO_VERBS = ("launch", "merge", "release", "cut", "ship", "publish", "file", "force-push", "tier",
            "go")
# The closed vocabulary a bare go-word may use after its go-verb: a pronoun, a reference or lane/tier
# word, and the filler a bare instruction carries. Any other token means it is not a bare go-word.
GO_TARGETS = ("it", "this", "that", "them", "pr", "full", "light", "micro")
GO_FILLER = ("now", "today", "tonight", "please", "in", "on", "the", "cloud", "local", "locally",
             "ahead")
_GO_REF_RE = re.compile(r"#\d+|v?\d+(?:\.\d+)+")
_ID_RE = re.compile(r"^- \*\*(\d{4}-\d{2}-\d{2})-([0-9a-z]{8})-([1-9]\d*)\*\*")
_DISPOSITION_RE = re.compile(r"^\s*(?:@?\d+(?:-\d+)?\s*[-–:=]\s*)?\(?[a-h]\)?\s*(?:[-–:,]|$)",
                             re.I)
_BOOKKEEPING_RE = re.compile(
    r"\bfiled as #\d+|\btracked (?:by|in|on) #\d+", re.I)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_SCOPE_RE = re.compile(r"standing|piece [a-z0-9][a-z0-9-]*")
HEADER = ("# Canon\n\nThis file is the project's Canon, the record of the owner's decisions. Its "
          "rules live in the\nsuperheroes plugin's `rubric/canon-contract.md`. Entries are "
          "appended one per line at the end\nand are never edited or deleted.\n\n## Entries\n\n")


class Refusal(Exception):
    def __init__(self, reason, detail, **extra):
        super().__init__(detail)
        self.payload = {"ok": False, "reason": reason, "detail": detail, **extra}


def _homes(text):
    """The homes § What stays out names, read from the contract itself so it stays their one home."""
    sec = text.split("## What stays out, and where it goes", 1)[-1].split("\n## ", 1)[0]
    sec = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", sec)
    homes = {}
    act = re.search(r"stays where it was given: ([^.]+)\.", sec.replace("\n", " "))
    board = re.search(r"The bookkeeping stays on ([^.]+)\.", sec.replace("\n", " "))
    if act:
        homes["act"] = "where it was given: " + act.group(1)
    if board:
        homes["board"] = board.group(1)
    for row in re.findall(r"^\|([^|\n]+)\|([^|\n]+)\|\s*$", sec, re.M):
        record, home = row[0].strip().lower(), row[1].strip()
        if "disposition" in record:
            homes["disposition"] = home
        elif "merge" in record and "release" in record:
            homes["merge"] = home
    return homes


def _refuse_stays_out(kind, why):
    try:
        with open(CONTRACT, encoding="utf-8") as fh:
            home = _homes(fh.read()).get(kind)
    except OSError:
        home = None
    raise Refusal("canon-stays-out", "%s stays out of Canon (%s)" % (why, STAYS_OUT),
                  kind=kind, home=home or "not found in %s; read it there" % STAYS_OUT)


def recognize(ruling, words):
    """The stays-out kind a ruling or the owner's words read as, or None. A narrow backstop with
    fixed shapes: a ruling that is a collector disposition, owner's words that are a bare go-word
    (a go-verb first, then only tokens of the closed GO_TARGETS / GO_FILLER / reference vocabulary), or an explicit issue-reference filing note.
    A disposition is read from the ruling text alone: an option letter answering an owner call
    is a real ruling when the ruling states one."""
    if _DISPOSITION_RE.match(ruling):
        return "disposition", "a collector disposition (%r)" % ruling[:60]
    words = _DISPOSITION_RE.sub("", words or "", count=1)
    tokens = [t.strip(".,;:!?\"'()") for t in words.lower().split()]
    if (tokens and tokens[0] in GO_VERBS and all(
            t in GO_TARGETS or t in GO_FILLER or _GO_REF_RE.fullmatch(t) for t in tokens[1:])):
        kind = "merge" if tokens[0] in ("merge", "release", "cut", "publish") else "act"
        return kind, "a go-word (%r)" % words[:60]
    hit = _BOOKKEEPING_RE.search(ruling)
    if hit:
        return "board", "issue-reference bookkeeping (%r)" % hit.group(0)
    return None


def _field(name, value):
    if len(("|" + value + "|").splitlines()) > 1 or SEP in value or not value.strip():
        raise Refusal("canon-bad-field", "%s must be one non-empty line with no ' · '" % name)
    return value


def entry_line(entry_id, date, scope, ruling, words_part, where):
    """The one entry-line format, in the contract's field order; `words_part` is the whole
    owner's-words field (or the cedes/supersedes fields joined before it by the caller)."""
    return SEP.join(["- **%s**" % entry_id, date, scope, ruling, words_part, "where: " + where])


def build_line(a, entry_id):
    """One entry line in the contract's field order, after the ground and stays-out checks."""
    if a.ground in STAY_OUT_GROUNDS:
        _refuse_stays_out(STAY_OUT_GROUNDS[a.ground], "a declared %s" % a.ground)
    if a.ground not in GROUNDS:
        raise Refusal("canon-unknown-ground", "ground must be one of %s" % ", ".join(GROUNDS))
    hit = recognize(a.ruling, a.owners_words)
    if hit:
        _refuse_stays_out(*hit)
    if not _DATE_RE.fullmatch(a.date or ""):
        raise Refusal("canon-bad-field", "--date must be YYYY-MM-DD (UTC)")
    if not _SCOPE_RE.fullmatch(a.scope or ""):
        raise Refusal("canon-bad-field", "--scope must be 'standing' or 'piece <work-item slug>'")
    if a.ground == "principle" and a.scope != "standing":
        raise Refusal("canon-bad-field", "a principle is a standing ruling: --scope standing")
    if a.ground == "ceded-call" and not (a.cedes and a.example and a.scope == "standing"):
        raise Refusal("canon-bad-field", "a ceded call is standing and needs --cedes and --example")
    if a.ground == "take-back" and not a.supersedes:
        raise Refusal("canon-bad-field", "a take-back supersedes the ceded entry: --supersedes")
    if (a.cedes or a.example) and a.ground != "ceded-call":
        raise Refusal("canon-bad-field", "--cedes and --example belong to a ceded call only")
    where = _field("--where", a.where)
    ruling = _field("--ruling", a.ruling)
    mid = []
    if a.cedes:
        mid.append("cedes: %s; example: %s" % (_field("--cedes", a.cedes),
                                               _field("--example", a.example)))
    if a.supersedes:
        mid.append("supersedes: " + _field("--supersedes", a.supersedes))
    mid.append('owner\'s words: "%s"' % _field("--owners-words", a.owners_words)
               if a.owners_words else "owner's words: none recorded")
    line = entry_line(entry_id, a.date, a.scope, ruling, SEP.join(mid), where)
    if not _entry_shape_ok(line):
        raise Refusal("canon-bad-field", "the entry would not read back in the Canon shape; "
                      "check --cedes, --supersedes and --owners-words for leading blanks")
    return line


_MID_RE = re.compile(r"(?:cedes: [^\x00\s][^\x00]*)?(?:\x00?supersedes: [^\x00\s][^\x00]*)?")


def _entry_shape_ok(line):
    """The one entry shape: id, date, scope, a ruling, optional cedes then supersedes, the owner's
    words and a final `where:` field, every one non-empty."""
    f = line.split(SEP)
    m = _ID_RE.match(line)
    if not m or len(f) < 6 or f[0] != m.group(0) or not (
            _DATE_RE.fullmatch(f[1]) and _SCOPE_RE.fullmatch(f[2]) and f[3].strip()):
        return False
    mid = "\x00".join(f[4:-2])
    return bool(_MID_RE.fullmatch(mid) and f[-2].startswith("owner's words: ")
                and f[-2][len("owner's words: "):].strip() and f[-1].startswith("where: ")
                and f[-1][len("where: "):].strip())


def _git(cwd, *args):
    import definition_doc
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                          env=definition_doc._scrubbed_git_env())


def _locate(root):
    """The lookup plus the default-branch copy's text ('' when none): § Writing a ruling, steps 2-3."""
    import definition_doc
    try:
        loc = definition_doc.resolve_canon(root=root)
    except Exception as exc:  # CanonLookupError, UnknownSchemaVersion: both fail closed
        raise Refusal("canon-lookup-failed", str(exc))
    if _git(loc["gitRoot"], "rev-parse", "--git-dir").returncode != 0:
        raise Refusal("canon-not-git", "gitRoot %s is not a git repository" % loc["gitRoot"])
    top = _git(loc["gitRoot"], "rev-parse", "--show-toplevel").stdout.strip()
    if not top or os.path.realpath(top) != os.path.realpath(loc["gitRoot"]):
        raise Refusal("canon-not-git", "gitRoot %s is not its own git repository" % loc["gitRoot"])
    default_text = ""
    if loc["home"] == "repo" and loc["defaultRef"]:
        rel = os.path.relpath(loc["path"], loc["gitRoot"]).replace(os.sep, "/")
        probe = _git(loc["gitRoot"], "ls-tree", loc["defaultRef"], "--", rel)
        if probe.returncode != 0:
            raise Refusal("canon-probe-failed", probe.stderr.strip() or "git ls-tree failed")
        if probe.stdout.strip():
            shown = _git(loc["gitRoot"], "show", "%s:%s" % (loc["defaultRef"], rel))
            if shown.returncode != 0:
                raise Refusal("canon-probe-failed", shown.stderr.strip() or "git show failed")
            default_text = shown.stdout
    working = ""
    if os.path.isfile(loc["path"]):
        with open(loc["path"], encoding="utf-8") as fh:
            working = fh.read()
    cut = working.rsplit("\n", 1)[-1]  # the unterminated tail: a write that stopped mid-entry
    body = False
    for l in working.splitlines():  # a failed append can leave a cut entry: fence further writes
        body = body or l == "## Entries"
        torn = l.startswith("- **") or (body and (l.startswith("- *") or (
            l == cut and l.strip() and "- **".startswith(l))))
        if torn and (l == cut or not _entry_shape_ok(l)):
            raise Refusal("canon-partial-entry", "Canon ends in an incomplete entry (%r), likely "
                          "from a failed write; repair it by hand before any further write"
                          % l[:80])
    return loc, working, default_text


def ids_in(*texts):
    return {m.group(0)[4:-2] for t in texts for m in map(_ID_RE.match, t.splitlines()) if m}


def next_seq(id_prefix, *texts):
    """The next n after the highest one `id_prefix` ('<date>-<session>-') used in the texts."""
    used = [int(i.rsplit("-", 1)[1]) for i in ids_in(*texts) if i.startswith(id_prefix)]
    return max(used, default=0) + 1


def mint_id(written, session_id, *texts):
    """§ The id rule: continue from the highest n this session prefix used on that date."""
    prefix = (session_id or "")[:8].lower()
    if not re.fullmatch(r"[0-9a-z]{8}", prefix):
        raise Refusal("canon-bad-field", "--session-id needs 8 leading [0-9a-z] characters")
    if not _DATE_RE.fullmatch(written):
        raise Refusal("canon-bad-field", "--written must be YYYY-MM-DD (UTC)")
    id_prefix = "%s-%s-" % (written, prefix)
    return "%s%d" % (id_prefix, next_seq(id_prefix, *texts))


ATTRIBUTES_LINE = "canon.md merge=union"


def ensure_attributes(path):
    """Add the union-merge attribute to the .gitattributes at `path`, creating it if absent."""
    try:
        with open(path, encoding="utf-8") as fh:
            have = fh.read()
    except FileNotFoundError:
        have = None
    if have is not None and ATTRIBUTES_LINE in [ln.strip() for ln in have.splitlines()]:
        return
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        if have and not have.endswith("\n"):
            fh.write("\n")
        fh.write(ATTRIBUTES_LINE + "\n")


def _write(loc, working, lines):
    """Append whole lines at the end, creating the file shape and the union-merge attribute."""
    path = loc["path"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    paths = [path]
    if loc["home"] == "repo":  # first: a failure here leaves Canon unwritten, so a retry is safe
        attrs = os.path.join(os.path.dirname(path), ".gitattributes")
        ensure_attributes(attrs)
        paths.append(attrs)
    # an existing Canon is only ever appended to, never reopened for writing from the start
    lead = HEADER if not working else ("" if working.endswith("\n") else "\n")
    with open(path, "a" if working else "w", encoding="utf-8", newline="\n") as fh:
        fh.write(lead + "".join(l + "\n" for l in lines))
    return paths


def _entry_lines(lines):
    """The entry lines of a batch; an entry-shaped line with a damaged id is refused, not dropped."""
    for l in lines:
        if l.startswith("- **") and not _ID_RE.match(l):
            raise Refusal("canon-bad-line", "damaged Canon entry id; repair it, nothing was "
                          "changed: %r" % l[:80])
    return [l for l in lines if _ID_RE.match(l)]


def _held_lines(text):
    lines = text.splitlines()
    if lines and lines[0].strip() != HELD_MARKER:
        raise Refusal("canon-held-not-marked", "the held comment's first line must be "
                      + HELD_MARKER)
    return _whole_entries(lines[1:])


def _whole_entries(lines):
    """The entry lines of a batch, every one whole; a wrapped, indented or stray line is refused
    (the marker and blank lines excepted), never silently dropped."""
    entries = _entry_lines(lines)
    for l in lines:
        if l.strip() and l.strip() != HELD_MARKER and not _ID_RE.match(l):
            raise Refusal("canon-bad-line", "the batch has a line that is not a Canon entry (a "
                          "wrapped or indented entry?); repair it first: %r" % l[:80])
    for l in entries:
        if not _entry_shape_ok(l):
            raise Refusal("canon-bad-line", "an entry is not a whole Canon line; repair it "
                          "first: %r" % l[:80])
    return entries


def _check_held_line(line):
    """A held line re-passes the stays-out checks before it is appended byte for byte."""
    fields = line.split(SEP)
    words = next((f[len("owner's words: "):].strip('"') for f in fields
                  if f.startswith("owner's words: ")), "")
    if not _entry_shape_ok(line):
        raise Refusal("canon-bad-line", "not a Canon entry line: %r" % line[:80])
    hit = recognize(fields[3], "" if words == "none recorded" else words)
    if hit:
        _refuse_stays_out(*hit)


def _read_held(path):
    """The held comment's entry lines ([] when no file is given); the marker rule is `hold`'s."""
    if not path:
        return []
    with open(path, encoding="utf-8") as fh:
        held = fh.read()
    return _held_lines(held) if held.strip() else []


def _lines_by_id(text):
    by_id = {}
    for line in text.splitlines():
        if _ID_RE.match(line):
            by_id.setdefault(_ID_RE.match(line).group(0)[4:-2], set()).add(line)
    return by_id


def _check_conflicts(lines, working, default_text):
    """Refuse the batch when an id is already held, or repeated in the batch, with other text:
    two entries sharing one id resolve for no reader, so the owner decides which stands."""
    in_working, in_default, in_batch = _lines_by_id(working), _lines_by_id(default_text), {}
    conflicts = []
    for line in lines:
        entry_id = _ID_RE.match(line).group(0)[4:-2]
        clash = (any(line != t for t in in_working.get(entry_id, ()))
                 or any(line != t for t in in_default.get(entry_id, ()))
                 or in_batch.setdefault(entry_id, line) != line)
        if clash and entry_id not in conflicts:
            conflicts.append(entry_id)
    if conflicts:
        raise Refusal("canon-id-conflict", "Canon already holds, or this batch repeats, %s with "
                      "different text; two entries sharing one id resolve for no reader, so the "
                      "owner decides which stands (rubric/canon-contract.md § Append only, and "
                      "supersession)" % ", ".join(conflicts), ids=conflicts)


def cmd_append(a):
    import mode_registry
    # one writer at a time from the baseline read to the write: the project store's config lock
    with mode_registry.config_lock(a.root) as got:
        if not got:
            raise Refusal("canon-lock-contended", "another writer holds the project store's "
                          "configuration lock; run the append again")
        return _append_locked(a)


def _append_locked(a):
    loc, working, default_text = _locate(a.root)
    held = _read_held(a.held_file)
    if a.lines_file:
        with open(a.lines_file, encoding="utf-8") as fh:
            lines = _whole_entries([l.rstrip("\n") for l in fh])
        if not lines:
            raise Refusal("canon-bad-line", "no Canon entry lines in %s" % a.lines_file)
        for line in lines:
            _check_held_line(line)
        _check_conflicts(lines, working, default_text)
        present, skipped, fresh = ids_in(working, default_text), [], []
        for line in lines:
            if _ID_RE.match(line).group(0)[4:-2] in present or line in fresh:
                skipped.append(line)
            else:
                fresh.append(line)
        lines = fresh
    else:
        written = a.written or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        entry_id = mint_id(written, a.session_id, working, default_text, "\n".join(held))
        lines, skipped = [build_line(a, entry_id)], []
    paths = _write(loc, working, lines) if lines else []
    return {"ok": True, "appended": lines, "skipped": skipped, "path": loc["path"],
            "home": loc["home"], "gitRoot": loc["gitRoot"], "commitPaths": paths}


def cmd_hold(a):
    loc, working, default_text = _locate(a.root)
    if loc["home"] != "repo":
        raise Refusal("canon-store-never-held", "project-store Canon is committed at once: "
                      "use append, never hold")
    lines = _read_held(a.held_file)
    written = a.written or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    entry_id = mint_id(written, a.session_id, working, default_text, "\n".join(lines))
    line = build_line(a, entry_id)
    return {"ok": True, "id": entry_id, "line": line,
            "comment": "\n".join([HELD_MARKER, *lines, line]) + "\n"}


def ruling_record(date, time, words, context):
    """The standard record for a ruling given in chat: a dated collector comment quoting the owner."""
    if not _DATE_RE.fullmatch(date) or not re.fullmatch(r"\d{2}:\d{2}", time):
        raise Refusal("canon-bad-field", "--date is YYYY-MM-DD and --time is HH:MM, both UTC")
    if not words.strip() or not context.strip():
        raise Refusal("canon-bad-field", "the owner's words and the context are both required")
    quoted = "\n".join("> " + l if l else ">" for l in words.strip("\n").splitlines())
    return ("%s\n**Owner ruling given in chat** · %s %s UTC\n\nThe owner's words, verbatim:\n\n%s"
            "\n\nWhat it rules on: %s\n" % (RULING_MARKER, date, time, quoted, context.strip()))


def cmd_ruling_record(a):
    with open(a.words_file, encoding="utf-8") as fh:
        body = ruling_record(a.date, a.time, fh.read(), a.context)
    if not a.post:
        return {"ok": True, "body": body, "permalink": None}
    if not (a.repo and a.collector):
        raise Refusal("canon-bad-field", "--post needs --repo and --collector")
    got = subprocess.run(["gh", "api", "repos/%s/issues/%d/comments" % (a.repo, a.collector),
                          "-f", "body=" + body, "--jq", ".html_url"],
                         capture_output=True, text=True)
    if got.returncode != 0 or not got.stdout.strip():
        raise Refusal("canon-post-failed", got.stderr.strip() or "gh returned no permalink")
    return {"ok": True, "body": body, "permalink": got.stdout.strip()}


def _parser():
    p = argparse.ArgumentParser(prog="canon.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("append", "hold"):
        s = sub.add_parser(name)
        s.add_argument("--root", default=".")
        s.add_argument("--session-id")
        s.add_argument("--written", help="the UTC date the entry is written (default: today)")
        for f in ("ground", "date", "scope", "ruling", "cedes", "example", "supersedes",
                  "owners-words", "where"):
            s.add_argument("--" + f)
        s.add_argument("--held-file", help="the current held comment's body")
        if name == "append":
            s.add_argument("--lines-file", help="held lines to append byte for byte")
    r = sub.add_parser("ruling-record")
    for f in ("date", "time", "words-file", "context"):
        r.add_argument("--" + f, required=True)
    r.add_argument("--post", action="store_true")
    r.add_argument("--repo")
    r.add_argument("--collector", type=int)
    return p


def main(argv):
    a = _parser().parse_args(argv[1:])
    try:
        if a.cmd in ("append", "hold") and not getattr(a, "lines_file", None):
            missing = [f for f in ("session_id", "ground", "date", "scope", "ruling", "where")
                       if not getattr(a, f)]
            if missing:
                raise Refusal("canon-bad-field", "missing: " + ", ".join("--" + m.replace("_", "-")
                                                                         for m in missing))
        out = {"append": cmd_append, "hold": cmd_hold, "ruling-record": cmd_ruling_record}[a.cmd](a)
    except Refusal as exc:
        out = exc.payload
    except OSError as exc:
        out = {"ok": False, "reason": "canon-write-failed", "detail": "%s: %s; Canon's entries "
               "may hold part of an entry (an existing Canon is only appended to); check the "
               "file's last line and `git status`, repair it, then run it again" % (type(exc).__name__, exc)}
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
