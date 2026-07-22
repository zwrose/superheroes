#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_lens_docs.py
"""Guardian doc-freshness lens — instruction docs that point at things that are not there.

Stdlib-only, no external analyzer, no network — and GENUINELY tool-free
(`uses_external_tools = False`): `collect(ctx)` consults only the sweep-provided context
(`ctx["cwd"]` for the repo root, `ctx["verifyCommand"]` for the calibrated command) and
stdlib file reads, so it spawns nothing — no git, no `core_md.read`, no subprocess. An
owner's coding agents read this project's instruction docs before they write code, so a
doc that points at a moved or deleted path misleads every future build. Two subchecks:

  1. **Path-reference resolution** across the root instruction docs (CLAUDE.md,
     README.md, CONVENTIONS.md). Only the ROOT set is read at this collector version —
     nested CLAUDE.md files are out of scope, and the digest records exactly which docs
     were read so nobody mistakes "not looked at" for "clean". Candidate paths are
     extracted naively (markdown link targets, backtick code spans, bare prose tokens)
     and then MECHANICALLY filtered — URLs, anchors, placeholders/templates, out-of-repo
     absolute paths, prose words, slash-as-"or" pairs, and references that are not
     followable from the repo root (see `is_anchored`) — before anything is resolved or
     reaches the model. Every drop is counted by class in the digest's `funnel`, so a
     quiet run is a quiet run somebody can check rather than take on faith.
     The digest records the resolution state of EVERY surviving reference, resolved and
     unresolved alike, because the drift signal is "resolved last sweep, does not now"
     and diff() can only see that when both states are recorded.

  2. **Verify-command liveness BY PATH RESOLUTION ONLY.** This collector reads the
     calibrated `verifyCommand` — threaded in on the sweep context (`ctx["verifyCommand"]`,
     resolved once by `guardian_sweep.collect` from core.md; this lens reads no core.md and
     spawns no git itself) — and checks that the scripts and paths the command invokes
     still exist. It NEVER RUNS the verify command, and a `collected`
     result from this lens is therefore NOT a claim that the verify command passes — or
     even that it starts. Execution liveness already lives in two other places: the
     sweep's own `verify-command` FACT verdict (`guardian_sweep.verify_config`, which
     does run it) and the vitals collector (issue #539). Running this repo's suite
     (~62s) inside a sub-second lens would be the wrong cost in the wrong place; the
     cheap, high-signal half — a calibrated command pointing at a script that no longer
     exists — is what this subcheck adds.

Fail-closed: when NEITHER subcheck can collect (no readable instruction doc AND
verify-command uncollectable), the lens is `not-collected`, never a clean run. When the
reference subcheck cannot collect but verify-command can, the lens is `partial` with a
reason naming the missing docs — the verify candidates are kept. An unreadable doc, or
an absent calibration / `verifyCommand` alongside readable docs, also degrades to
`partial` and carries the portion it could not measure forward from `ctx["prevDigest"]`,
so the next sweep never reads a half-run as a fleet of fixed references.

**Absent vs unreadable docs (load-bearing):** references are carried forward for an
*unreadable* doc (collection failure — the doc may still exist; we could not read it).
References are NOT carried forward for an *absent* doc: absence is real repo state and
real drift. Consequence: if all instruction docs are absent, previously broken
references under those docs are reported as `resolved`, which reads as "fixed" when the
truth is "the doc is gone."
"""
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import guardian_collect  # noqa: E402

DIGEST_SCHEMA_VERSION = 1

DOC_FILES = ("CLAUDE.md", "README.md", "CONVENTIONS.md")
"""The root instruction-doc set. Nested CLAUDE.md files are NOT read at this version —
the digest's `docsRead` / `docsAbsent` lists say exactly what was covered."""

_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)[^)]*\)")
_CODE_SPAN = re.compile(r"`([^`\n]+)`")
_FENCE = re.compile(r"^\s*(```|~~~)")

# Extensions that make a separator-less token a plausible path rather than a prose word.
KNOWN_EXTENSIONS = (
    ".md", ".markdown", ".txt", ".rst",
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf",
    ".sh", ".bash", ".zsh", ".rb", ".go", ".rs", ".java", ".kt", ".swift",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".php", ".pl", ".lua", ".sql",
    ".html", ".css", ".scss", ".xml", ".csv", ".lock", ".env", ".gitignore",
)

# Anything carrying one of these is a template, a glob, or a shell redirect — never a
# concrete project path. `…` is the owner-facing ellipsis that shows up in doc excerpts.
_PLACEHOLDER_CHARS = "<>${}|*?…"
_URL_PREFIXES = ("http://", "https://", "ftp://", "mailto:", "www.", "//")
_LEAD_TRIM = "([{\"'"
_TRAIL_TRIM = ".,;:!?)]}\"'"
_WIN_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")

# Drop classes recorded in the digest funnel, so "what the mechanical filter killed"
# is auditable instead of invisible.
DROP_CLASSES = (
    "empty",              # nothing left after trimming
    "url",                # http(s)://, mailto:, //host, www.
    "anchor",             # bare #fragment
    "placeholder",        # <work-item>, ${VAR}, globs, shell redirects, ellipses
    "outside-repo",       # /abs, ~/home, C:\ — not repo-relative references
    "typographic",        # §4.1/§4.3, spec↔spec.md — prose typography, not paths
    "prose-token",        # no separator and no known extension: an ordinary word
    "prose-alternative",  # issue/PR, UI/UX: a slash used as "or", not as a path
    "unanchored",         # not followable from the repo root (see is_anchored)
)


def _trim_token(token):
    """Strip markdown wrappers and sentence punctuation from a raw token."""
    tok = (token or "").strip()
    for mark in ("***", "**", "*"):
        if tok.startswith(mark) and tok.endswith(mark) and len(tok) > 2 * len(mark):
            tok = tok[len(mark):-len(mark)]
            break
    while tok and tok[0] in _LEAD_TRIM:
        tok = tok[1:]
    while tok and tok[-1] in _TRAIL_TRIM:
        tok = tok[:-1]
    return tok


def normalize_candidate(token):
    """Mechanical validation of one naive token → (repo_relative_path, drop_class).

    Exactly one of the two is non-None. This is the middle step of the funnel: it runs
    BEFORE any resolution and before anything can reach the model, so prose words, URLs,
    and `<placeholder>` templates never become candidates. Shape only — no filesystem
    access happens here (anchoring is `is_anchored`, resolution is the step after that).
    """
    tok = _trim_token(token)
    if not tok:
        return (None, "empty")
    if tok.startswith("#"):
        return (None, "anchor")
    low = tok.lower()
    if "://" in low or low.startswith(_URL_PREFIXES):
        return (None, "url")
    # Drop the in-page anchor / query / pytest-nodeid suffix, keep the file it hangs off.
    tok = tok.split("#", 1)[0].split("?", 1)[0].split("::", 1)[0]
    if not tok:
        return (None, "anchor")
    if any(ch in tok for ch in _PLACEHOLDER_CHARS) or "..." in tok:
        return (None, "placeholder")
    if tok.startswith("/") or tok.startswith("~") or _WIN_DRIVE.match(tok):
        # Absolute and home-anchored paths are not repo-relative references; calling them
        # "missing from this repo" would be a lie, not a finding.
        return (None, "outside-repo")
    while tok.startswith("./"):
        tok = tok[2:]
    if tok in ("", ".", ".."):
        return (None, "empty")
    if any(ord(ch) > 127 for ch in tok):
        # `§4.1/§4.3`, `spec↔spec.md`, en-dashes: typography, not a path in this repo.
        return (None, "typographic")
    has_sep = "/" in tok
    base = tok.rsplit("/", 1)[-1]
    # Bare recognized dotfiles (`.gitignore`, `.env`): os.path.splitext('.gitignore')
    # yields ('.gitignore', '') — empty extension — so also accept a basename that is
    # itself listed in KNOWN_EXTENSIONS.
    ext = os.path.splitext(tok)[1].lower()
    has_ext = ext in KNOWN_EXTENSIONS or base.lower() in KNOWN_EXTENSIONS
    if not has_sep and not has_ext:
        return (None, "prose-token")
    if has_sep and not has_ext and not tok.endswith("/"):
        # `issue/PR`, `UI/UX`, `merge/release/force-push` — prose alternatives written
        # with a slash. A real reference names a file (extension) or a directory
        # (trailing slash); this shape names neither.
        return (None, "prose-alternative")
    return (tok, None)


def is_anchored(repo, path):
    """True when `path` is FOLLOWABLE FROM THE REPO ROOT.

    A reference is only checkable when a reader starting at the repo root can follow it:
    its first segment must name something that exists at the top level. Two very common
    doc shapes are not followable and must never be reported as broken links —

      * context-relative shorthand — `lib/store_core.py`, `rubric/covenant.md` in prose
        that is speaking from inside `plugins/superheroes/`;
      * a bare filename used as a NAME rather than a path — `plugin.json`, `SKILL.md`.

    Reporting those as "does not exist" is a false missing-file claim, not a finding.
    The caller rescues any reference that was TRACKED on a previous sweep (see
    `collect`), so a reference that stops being followable because its whole top-level
    directory was deleted still surfaces as drift — whether it resolved then or was
    already broken.
    """
    head = path.split("/", 1)[0]
    if not head:
        return False
    return os.path.exists(os.path.join(repo, head))


def _line_tokens(line):
    """Naive candidate tokens on one line, each counted once: markdown link targets,
    words inside backtick code spans, then the remaining prose words."""
    tokens = []
    consumed = []

    def _overlaps(span):
        return any(span[0] < e and s < span[1] for s, e in consumed)

    for m in _MD_LINK.finditer(line):
        tokens.append(m.group(1))
        consumed.append(m.span())
    for m in _CODE_SPAN.finditer(line):
        if _overlaps(m.span()):
            continue
        tokens.extend(m.group(1).split())
        consumed.append(m.span())
    masked = list(line)
    for s, e in consumed:
        for i in range(s, min(e, len(masked))):
            masked[i] = " "
    tokens.extend("".join(masked).split())
    return tokens


def extract_references(text):
    """Naive extraction over a doc's text → [(token, line_no, in_fence), ...].

    Fenced blocks are KEPT (see `validation_guidance`): a fenced path in this project's
    docs is usually a real command against real project files, and "illustrative vs real"
    is not a distinction that can be drawn mechanically. `in_fence` rides along into the
    receipt so the model's validation step can weigh it.
    """
    out = []
    in_fence = False
    for lineno, line in enumerate((text or "").splitlines(), start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        for tok in _line_tokens(line):
            out.append((tok, lineno, in_fence))
    return out


def _read_doc(path):
    """(text, None) or (None, reason). Absent is distinct from unreadable."""
    if not os.path.isfile(path):
        return (None, "absent")
    try:
        with open(path, encoding="utf-8") as fh:
            return (fh.read(), None)
    except (OSError, UnicodeDecodeError) as exc:
        return (None, "unreadable: %s" % exc)


def _repo_root(ctx):
    """Repo top-level = the sweep's cwd (realpath).

    Matches the sibling deps/deadcode lenses: the base seam runs collectors from a neutral
    cwd and hands the repo in as `ctx["cwd"]`. This lens re-derives nothing via git — a
    `git rev-parse` would spawn, and this lens is tool-free by contract — so it takes the
    cwd it was given directly.
    """
    cwd = (ctx or {}).get("cwd") or "."
    return os.path.realpath(cwd)


def _ref_id(doc, path):
    return "docs:ref:%s:%s" % (doc, path)


def _verify_id(path):
    return "docs:verify-cmd:%s" % path


_STEP_SPLIT = re.compile(r"&&|\|\||[;\n|]")


def verify_command_paths(vcmd):
    """[(path, step), ...] — the file/dir paths a verify command invokes.

    Same mechanical filter as the doc references, plus: flags are dropped, and a bare
    executable name (`python3`, `pytest`) falls out as a prose token. This reads the
    command; it never runs it.
    """
    out = []
    seen = set()
    for raw_step in _STEP_SPLIT.split(vcmd or ""):
        step = raw_step.strip()
        if not step:
            continue
        for word in step.split():
            if word.startswith("-"):
                continue
            path, _drop = normalize_candidate(word)
            if path is None:
                continue
            key = (path, step)
            if key in seen:
                continue
            seen.add(key)
            out.append((path, step))
    return out


def _resolves(repo, relpath):
    return os.path.exists(os.path.join(repo, relpath))


def _previously_tracked(prev_digest):
    """Reference ids present on the previous sweep (resolved or unresolved).

    A reference that was already tracked must survive losing its top-level anchor —
    including one that was already broken — rather than vanishing as `unanchored`.
    """
    return set(_refs_of(prev_digest))


def _carry_forward(prev_digest, refs, prefix):
    """Copy every prev-digest reference under `prefix` into `refs` (carry-forward for a
    portion this run could not measure). Never overwrites something measured this run."""
    prev = (prev_digest or {})
    prev_refs = prev.get("references") if isinstance(prev, dict) else None
    if not isinstance(prev_refs, dict):
        return 0
    carried = 0
    for rid, rec in prev_refs.items():
        if rid.startswith(prefix) and rid not in refs and isinstance(rec, dict):
            copy = dict(rec)
            copy["carriedForward"] = True
            refs[rid] = copy
            carried += 1
    return carried


class DocsLens(object):
    """The doc-freshness lens object registered as `LENS`."""

    name = "docs"
    collector_version = "1.0.0"
    required_facts = ()
    # Genuinely tool-free: collect() spawns nothing (no git, no core_md.read, no
    # subprocess). The harness proves this at runtime (see conformance_cases /
    # conformance_fixture and the no-spawn proof in test_guardian_conformance).
    uses_external_tools = False
    cost = {
        # MEASURED on the superheroes repo (CLAUDE.md + README.md + CONVENTIONS.md,
        # 9,323 naive tokens → 72 surviving occurrences → 2 unresolved): 5 consecutive
        # collect() calls ran well under 0.06s. The repo root and the calibrated
        # verifyCommand are handed in on ctx, so there is no git rev-parse and no core.md
        # read in the hot path anymore — only stdlib file reads. Rounded up for headroom.
        "collectorSeconds": 0.06,
        "note": (
            "Pure stdlib file reads over the root instruction docs; no analyzer, no "
            "network, no subprocess. The repo root (ctx['cwd']) and the calibrated "
            "verifyCommand (ctx['verifyCommand']) are supplied by the sweep. The verify "
            "command is READ for the paths it names, never run."
        ),
    }

    validation_guidance = (
        "Each candidate is a path referenced by an instruction doc (or by the calibrated "
        "verify command) that does not exist in the repo. The collector already dropped "
        "URLs, anchors, `<placeholder>` templates and globs, absolute/home-anchored paths, "
        "prose words, slash-as-'or' pairs (`issue/PR`), and references that are not "
        "followable from the repo root — context-relative shorthand (`lib/foo.py` written "
        "from inside a subtree) and bare filenames used as names (`plugin.json`) — "
        "mechanically. It did NOT drop paths inside fenced code blocks — "
        "in this project's docs a fenced path is usually a real command against real "
        "project files, and illustrative-vs-real cannot be told apart mechanically — so "
        "each receipt says whether the occurrence was inside a fence and you decide. "
        "Reject a candidate when: the doc discusses the file AS RETIRED or moved (a "
        "changelog, a history note, an anti-pattern); the path is an illustrative or "
        "hypothetical example (`lib/foo.py`, `src/example.ts`); the path is a per-project "
        "layout name from generic guidance rather than this project's own layout; the "
        "file lives outside this repo (another checkout, a dependency, the user's home); "
        "or the path sits inside quoted external material (an excerpt, an issue body, "
        "a transcript); or the candidate is a relative-to-what ambiguity — before "
        "treating the reference as broken, check whether the surrounding section (a "
        "table header, an intro sentence, a heading) establishes a different base "
        "(plugin root, package root, or other context the section names) and whether "
        "the path resolves against that base; a reference that resolves against its "
        "stated or clearly-implied base is a validated rejection, not a finding. What "
        "survives is a doc telling a future agent to read something that is not there."
    )

    consequence_template = (
        "One sentence naming the doc, the dead path, and who pays: \"<doc> points "
        "<n> future builds at `<path>`, which moved or was deleted; the next agent that "
        "follows it will write against a file that does not exist.\" The cost is MISLED "
        "FUTURE WORK — an agent reading stale instructions — never tidiness or aesthetics. "
        "Price the effort from the receipt (a one-line path fix is small; a doc section "
        "describing a layout that no longer exists is not)."
    )

    def collect(self, ctx):
        ctx = ctx or {}
        repo = _repo_root(ctx)
        refs = {}
        candidates = []
        docs_read, docs_absent, docs_unreadable = [], [], []
        funnel = {"extracted": 0, "afterMechanical": 0, "drops": {}}

        previously_tracked = _previously_tracked(ctx.get("prevDigest"))

        for doc in DOC_FILES:
            text, reason = _read_doc(os.path.join(repo, doc))
            if text is None:
                if reason == "absent":
                    docs_absent.append(doc)
                else:
                    docs_unreadable.append({"doc": doc, "reason": reason})
                continue
            docs_read.append(doc)
            occurrences = {}
            for token, lineno, in_fence in extract_references(text):
                funnel["extracted"] += 1
                path, drop = normalize_candidate(token)
                if path is None:
                    funnel["drops"][drop] = funnel["drops"].get(drop, 0) + 1
                    continue
                # A reference tracked on a previous sweep stays tracked even if it is no
                # longer followable from the root — whether it resolved then or was
                # already broken. "Present last sweep, unanchored now" must not vanish.
                if (not is_anchored(repo, path)
                        and _ref_id(doc, path) not in previously_tracked):
                    funnel["drops"]["unanchored"] = funnel["drops"].get("unanchored", 0) + 1
                    continue
                funnel["afterMechanical"] += 1
                occurrences.setdefault(path, []).append((lineno, in_fence))
            for path, hits in occurrences.items():
                rid = _ref_id(doc, path)
                resolved = _resolves(repo, path)
                refs[rid] = {
                    "doc": doc,
                    "path": path,
                    "resolved": resolved,
                    "occurrences": len(hits),
                }
                if not resolved:
                    candidates.append({
                        "id": rid,
                        "metric": len(hits),
                        "doc": doc,
                        "path": path,
                        "lines": [ln for ln, _f in hits],
                        "receipt": _ref_receipt(doc, path, hits),
                    })

        # Snapshot the funnel's output BEFORE the verify subcheck and the carry-forward
        # add entries to `refs` — otherwise "how many references did the mechanical
        # filter yield" would silently absorb rows that never went through it.
        unique_doc_refs = len(refs)
        unresolved_doc_refs = len(candidates)

        degradations = []
        for entry in docs_unreadable:
            _carry_forward(ctx.get("prevDigest"), refs,
                           "docs:ref:%s:" % entry["doc"])
            degradations.append("%s %s" % (entry["doc"], entry["reason"]))

        verify = self._collect_verify(ctx, repo, refs, candidates)
        if verify["reason"]:
            _carry_forward(ctx.get("prevDigest"), refs, "docs:verify-cmd:")
            degradations.append(verify["reason"])

        if not docs_read:
            # No instruction docs readable. If verify-command still collected, that is
            # partial (keep its candidates) — not whole-lens not-collected. Only when
            # NEITHER subcheck can collect do we refuse the run entirely.
            missing = "no instruction doc readable at repo root: %s" % (
                ", ".join(DOC_FILES),)
            if docs_unreadable:
                missing += " (%s)" % "; ".join(
                    "%s %s" % (u["doc"], u["reason"]) for u in docs_unreadable)
            if verify["reason"] is not None:
                out = {"candidates": [], "digest": None}
                out.update(guardian_collect.not_collected(
                    "%s; %s" % (missing, verify["reason"])))
                return out
            degradations.insert(0, missing)

        digest = {
            "schemaVersion": DIGEST_SCHEMA_VERSION,
            "docsRead": docs_read,
            "docsAbsent": docs_absent,
            "docsUnreadable": [u["doc"] for u in docs_unreadable],
            "verifyCommand": verify["state"],
            # The audit trail for "45 naive → 8 mechanical → N to the model": every stage
            # count and every drop class, so a quiet run is a quiet run you can check.
            "funnel": {
                "extracted": funnel["extracted"],
                "afterMechanical": funnel["afterMechanical"],
                "uniqueReferences": unique_doc_refs,
                "unresolvedReferences": unresolved_doc_refs,
                "verifyPathsChecked": len(verify["state"].get("pathsChecked") or []),
                "unresolved": len(candidates),
                "drops": funnel["drops"],
            },
            "references": refs,
        }
        out = {"candidates": candidates, "digest": digest}
        if degradations:
            out.update(guardian_collect.partial("; ".join(degradations)))
        else:
            out.update(guardian_collect.collected())
        return out

    def _collect_verify(self, ctx, repo, refs, candidates):
        """Subcheck 2. Returns {"state": <digest fragment>, "reason": str|None}.

        The calibrated `verifyCommand` is threaded in on `ctx["verifyCommand"]` by the
        sweep (`guardian_sweep.collect` resolves it once from core.md alongside the
        verify-command FACT and hands it in) — this lens reads no core.md and spawns no
        git itself. A missing `ctx["verifyCommand"]` (None — no calibration threaded) or
        an empty one is not a clean bill of health: `reason` is non-None, the subcheck
        does NOT collect (never a spawn, never a false clean), and the lens degrades to
        `partial`.
        """
        ctx = ctx or {}
        vcmd = ctx.get("verifyCommand")
        if vcmd is None:
            return _verify_uncollected(
                "no calibration threaded into the sweep context (ctx['verifyCommand'] "
                "absent — no verifyCommand was resolved for this sweep)")
        if not str(vcmd).strip():
            return _verify_uncollected("calibration records no verifyCommand")

        paths = verify_command_paths(str(vcmd))
        checked = []
        for path, step in paths:
            rid = _verify_id(path)
            resolved = _resolves(repo, path)
            checked.append(path)
            if rid in refs:
                # The same script named by two steps normalizes to one id; a duplicate id
                # inside one sweep is dropped as malformed by the shell, so aggregate.
                continue
            refs[rid] = {
                "doc": "core.md:verifyCommand",
                "path": path,
                "resolved": resolved,
                "occurrences": 1,
            }
            if not resolved:
                candidates.append({
                    "id": rid,
                    "metric": 1,
                    "doc": "core.md:verifyCommand",
                    "path": path,
                    "step": step,
                    "receipt": (
                        "calibrated verifyCommand step `%s` invokes `%s`, which does not "
                        "exist in the repo (path resolution only — the command was NOT "
                        "run)" % (step, path)),
                })
        return {
            "state": {"status": "collected", "pathsChecked": sorted(set(checked))},
            "reason": None,
        }

    def diff(self, prev_digest, cur_digest):
        """Drift over the digest's resolution map.

        new      — unresolved now and (resolved before, or newly present and already broken)
        resolved — unresolved before and (resolving now, or gone)
        worsened — unresolved in both, with more occurrences now
        """
        prev = _refs_of(prev_digest)
        cur = _refs_of(cur_digest)
        new, worsened, resolved = [], [], []
        for rid, rec in cur.items():
            if rec.get("resolved"):
                continue
            before = prev.get(rid)
            if before is None or before.get("resolved"):
                new.append(rid)
            elif _count(rec) > _count(before):
                worsened.append(rid)
        for rid, rec in prev.items():
            if rec.get("resolved"):
                continue
            after = cur.get(rid)
            if after is None or after.get("resolved"):
                resolved.append(rid)
        return {
            "new": sorted(new),
            "worsened": sorted(worsened),
            "resolved": sorted(resolved),
        }

    def red_lines(self, candidates):
        """Doc drift is never a red line — it misleads future work, it does not break
        the build. It surfaces through drift like any other candidate."""
        return []

    def degrade(self, reason):
        return {"lens": self.name, "degraded": True, "reason": reason}

    # ---------------------------------------------------------------------- conformance

    def conformance_fixture(self):
        """Minimal doc set the no-spawn proof will actually read.

        A single readable root doc (`CLAUDE.md`) whose only reference resolves against
        itself — so the proof exercises the real read/anchor/resolve path but raises no
        candidate. The harness runs this under every spawn primitive patched to raise; a
        genuinely tool-free `collect()` must complete on it without touching one.
        """
        return {"CLAUDE.md": _CONFORMANCE_DOC}

    def conformance_cases(self):
        """The three TOOL_FREE_CONFORMANCE_SCENARIOS (see lens-contract.md).

        The harness never sets `ctx["verifyCommand"]`, so the verify subcheck always
        degrades (uncollected) and carries the `docs:verify-cmd:` portion forward from the
        prior digest — that is the carry-forward vehicle these cases exercise. (The harness
        materializes an `unreadable` path as a **directory**, which this lens reads as an
        *absent* doc, not an *unreadable* one — so the prior findings under an unreadable
        path live on the verify subcheck, never under the vanished doc, which is exactly
        why they must not be resolved.)

        - `unreadable-input` — a readable `CLAUDE.md` plus a directory at `README.md`
          (read as absent) → `partial`; the prior unresolved verify finding is carried, so
          `diff()` resolves nothing (no false clean).
        - `all-inputs-unavailable` — no docs and no verifyCommand → whole-lens
          `not-collected` with a reason; the prior digest holds no unresolved reference, so
          nothing is resolved.
        - `partial-carry-forward` — same shape as `unreadable-input`; a `partial` result
          preserves the prior digest (`diff()` resolves nothing).
        """
        return {
            "unreadable-input": {
                "fixture": {"CLAUDE.md": _CONFORMANCE_DOC},
                "unreadable": ["README.md"],
                "prev_digest": _conformance_prev_with_verify_finding(),
                "config": None,
            },
            "all-inputs-unavailable": {
                "fixture": {},
                "prev_digest": {
                    "schemaVersion": DIGEST_SCHEMA_VERSION, "references": {}},
                "config": None,
            },
            "partial-carry-forward": {
                "fixture": {"CLAUDE.md": _CONFORMANCE_DOC},
                "unreadable": ["README.md"],
                "prev_digest": _conformance_prev_with_verify_finding(),
                "config": None,
            },
        }


_CONFORMANCE_DOC = "# Project\n\nRead `CLAUDE.md` first.\n"


def _conformance_prev_with_verify_finding():
    """A prior digest carrying one unresolved verify-command finding.

    The verify subcheck always degrades in conformance (no `ctx["verifyCommand"]`), so it
    carries this id forward — proving `diff()` never resolves a finding measurement
    stopped on.
    """
    vid = "docs:verify-cmd:scripts/verify.sh"
    return {
        "schemaVersion": DIGEST_SCHEMA_VERSION,
        "references": {
            vid: {
                "doc": "core.md:verifyCommand",
                "path": "scripts/verify.sh",
                "resolved": False,
                "occurrences": 1,
            },
        },
    }


def _verify_uncollected(reason):
    """The verify subcheck's not-collected fragment + the lens-level degradation line."""
    return {
        "state": {"status": "not-collected", "reason": reason},
        "reason": "verify-command subcheck not collected: %s" % reason,
    }


def _refs_of(digest):
    refs = (digest or {}).get("references") if isinstance(digest, dict) else None
    if not isinstance(refs, dict):
        return {}
    return {k: v for k, v in refs.items() if isinstance(v, dict)}


def _count(rec):
    try:
        return int(rec.get("occurrences", 1))
    except (TypeError, ValueError):
        return 1


def _ref_receipt(doc, path, hits):
    lines = ", ".join(str(ln) for ln, _f in hits)
    fenced = sum(1 for _ln, f in hits if f)
    where = ""
    if fenced == len(hits):
        where = " (inside a fenced code block)"
    elif fenced:
        where = " (%d of %d occurrences inside a fenced code block)" % (fenced, len(hits))
    return (
        "%s:%s references `%s`, which does not exist in the repo — %d occurrence%s at "
        "line%s %s%s"
        % (doc, hits[0][0], path, len(hits), "" if len(hits) == 1 else "s",
           "" if len(hits) == 1 else "s", lines, where))


LENS = DocsLens()
# Module-level roster the production loader registers (guardian_lens.PRODUCTION_LENS_MODULES).
LENSES = (LENS,)
