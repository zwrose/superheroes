#!/usr/bin/env python3
"""Best-effort SessionStart context assembler.

A slash-command-spawned session (e.g. `/superheroes:architect-discovery` in a
worktree) never receives the project-context layer a plain chat start auto-loads
— project/user `CLAUDE.md`, the env block, the `MEMORY.md` head — nor an
expandable plugin-root for the host-tool-map pointer. This module re-assembles
that layer so the `session_start.py` hook can inject it via `additionalContext`,
making the spawn path first-class.

Design contract (see docs/superpowers/specs/2026-06-21-discovery-entry-path-bootstrap-design.md):

- **Best-effort, never raises.** Each source is gathered in its own try/except;
  a failed/absent source is omitted and a one-line breadcrumb (`<source>:
  <reason>`) is written to **stderr** — NEVER the file contents (stderr is the
  hook log; leaking contents there would defeat the diagnosable-not-leaky bar).
- **All git goes through `store_core`** (`run_git`'s 10s timeout, `get_gitdir`'s
  absolute common-dir) so a hung `git` can't stall every session start. The one
  exception is `project_memory`'s root walk, which is deliberately
  subprocess-free (a filesystem ascent, not a git call).
- **Budget.** `assemble` keeps the block under `char_budget` as a safety margin
  (no hard `additionalContext` cap was found; this is belt-and-suspenders). A
  present source dropped by the budget is named in an in-block omitted-line AND
  breadcrumbed, so it is never silently indistinguishable from an absent file.

Stdlib-only.
"""
import collections
import datetime
import os
import sys

import store_core

_MEMORY_HEAD_LINES = 200
_HEADER = "## Superheroes session bootstrap\n"

# B6 (#315): per-assemble collector for GENUINE-FAILURE breadcrumbs (a read/git/probe ERROR, or a
# source dropped for budget) — the ones an owner's agent must be able to read back. A plain ABSENCE
# (no user CLAUDE.md, no MEMORY.md) is normal and is NOT collected. assemble() resets this at entry
# and folds any collected failures into an in-block diagnostics line, so a half-bootstrapped session
# leaves a breadcrumb IN the injected context (what the agent reads), not only in the hook's stderr.
# Reasons carry source names, paths, and exception *types* only — never file contents (the same
# diagnosable-not-leaky bar the stderr breadcrumb holds), so surfacing them in-block is safe.
_FAILURES = []


def _breadcrumb(source, reason):
    """One-line diagnostic to stderr (the hook log). Reason carries source names,
    paths, and exception *types* only — never file contents or secret values."""
    try:
        sys.stderr.write("superheroes bootstrap: %s — %s\n" % (source, reason))
    except Exception:
        pass


def _note_failure(source, reason):
    """A GENUINE bootstrap failure (an error, not a mere absence): breadcrumb it to stderr AND
    record it for the in-block diagnostics line so the running agent can read it back (B6, #315)."""
    _breadcrumb(source, reason)
    try:
        _FAILURES.append((source, reason))
    except Exception:
        pass


def _read_text(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


# ----------------------------------------------------------------- resolved roots
def resolved_roots(plugin_root, host):
    """Context note stating the absolute plugin root + absolute host-map path, so a
    skill's `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<host>-tools.md` Read lands
    on the real file. No env exports — context injection only."""
    root = os.path.abspath(plugin_root or ".")
    host_map = os.path.join(root, "hosts", "%s-tools.md" % host)
    return (
        "Plugin root (absolute): %s\n"
        "Host tool map (absolute): %s\n"
        "When a skill tells you to read `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/<path>`, "
        "treat `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}` as the plugin root above and read "
        "that absolute path (this also fixes the host-tool-map pointer)." % (root, host_map)
    )


# ----------------------------------------------------------------- project CLAUDE.md
def _claude_md_chain(cwd):
    """Absolute paths of every CLAUDE.md from `cwd` up to (and including) the repo
    root, by a SUBPROCESS-FREE filesystem ascent. Stops at the first dir holding a
    `.git` entry — a dir in a normal checkout, a *file* in a linked worktree, so
    `os.path.exists` catches both — or the filesystem root."""
    paths = []
    if not cwd:
        return paths
    try:
        d = os.path.abspath(cwd)
        while True:
            f = os.path.join(d, "CLAUDE.md")
            if os.path.isfile(f):
                paths.append(f)
            if os.path.exists(os.path.join(d, ".git")):
                break
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    except Exception:
        pass
    return paths


def _read_claude_chain(chain):
    """Read + concatenate a precomputed CLAUDE.md chain. '' (with a breadcrumb) when
    the chain is empty. Split from project_memory so assemble can resolve the chain
    once and reuse it for both the section text and the hint (no double walk)."""
    if not chain:
        _breadcrumb("Project CLAUDE.md", "no CLAUDE.md found from cwd up to repo root")
        return ""
    out = []
    for f in chain:
        try:
            out.append(_read_text(f))
        except Exception as exc:
            _note_failure("Project CLAUDE.md", "read error for %s (%s)" % (f, type(exc).__name__))
    return "\n\n".join(t for t in out if t).rstrip("\n")


def project_memory(cwd):
    """The project CLAUDE.md chain (cwd → repo root), concatenated. '' if none."""
    return _read_claude_chain(_claude_md_chain(cwd))


# ----------------------------------------------------------------- user CLAUDE.md
def _user_claude_md_path():
    return os.path.expanduser(os.path.join("~", ".claude", "CLAUDE.md"))


def user_memory():
    """User-level ~/.claude/CLAUDE.md, or '' when absent."""
    path = _user_claude_md_path()
    if not os.path.isfile(path):
        _breadcrumb("User CLAUDE.md", "not found at %s" % path)
        return ""
    try:
        return _read_text(path).rstrip("\n")
    except Exception as exc:
        _note_failure("User CLAUDE.md", "read error (%s)" % type(exc).__name__)
        return ""


# ----------------------------------------------------------------- env block
def env_block(cwd):
    """The cheap, stable parts of a native env block: today's date + git user email.
    The email goes through store_core.run_git (10s timeout) — a hung `git config`
    (askpass, stalled mount) must not stall every session start."""
    parts = []
    try:
        parts.append("Today's date: %s" % datetime.date.today().isoformat())
    except Exception as exc:
        _note_failure("Environment", "date unavailable (%s)" % type(exc).__name__)
    try:
        email = store_core.run_git(cwd or ".", "config", "user.email")
    except Exception as exc:
        email = None
        _note_failure("Environment", "git config user.email errored (%s)" % type(exc).__name__)
    if email:
        parts.append("Git user email: %s" % email)
    else:
        _breadcrumb("Environment", "git config user.email unavailable")
    return "\n".join(parts)


# ----------------------------------------------------------------- auto-memory (MEMORY.md)
def _encode_project_path(abs_path):
    """Auto-memory dir encoding: replace `/` and `.` with `-`
    (e.g. /Users/z/superheroes -> -Users-z-superheroes). Intentionally lossy and
    matches Claude Code's own native auto-memory keying — two paths differing only by
    `.` vs `-` collide to the same dir here exactly as they do natively, so the
    bootstrap surfaces the same MEMORY.md a native start would (parity, not a bug)."""
    return abs_path.replace("/", "-").replace(".", "-")


def _projects_base(transcript_path):
    """The `~/.claude/projects` base. Prefer it from transcript_path (everything up
    to and including a `/projects/` segment), but ONLY when that marker is present;
    else $CLAUDE_CONFIG_DIR/projects, else ~/.claude/projects (finding C6)."""
    if transcript_path:
        seg = os.sep + "projects" + os.sep
        i = transcript_path.find(seg)
        if i != -1:
            return transcript_path[:i] + os.sep + "projects"
    ccd = os.environ.get("CLAUDE_CONFIG_DIR")
    if ccd:
        return os.path.join(ccd, "projects")
    return os.path.expanduser(os.path.join("~", ".claude", "projects"))


def _main_repo_root(cwd):
    """Absolute MAIN-repo root (shared by all worktrees). Via store_core.get_gitdir
    (absolute common-dir, timeout-guarded) — its parent when it points at a `.git`,
    else the get_gitdir value itself (its non-git realpath(cwd) fallback). Never a
    bare `git rev-parse` (finding C1). Falls back to $CLAUDE_PROJECT_DIR / cwd."""
    try:
        gitdir = store_core.get_gitdir(cwd or ".")
        if gitdir:
            if os.path.basename(gitdir) == ".git":
                return os.path.dirname(gitdir)
            return gitdir
    except Exception as exc:
        _note_failure("Auto-memory (MEMORY.md head)", "gitdir resolve errored (%s)" % type(exc).__name__)
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.path.abspath(cwd or ".")


def _memory_md_path(cwd, transcript_path):
    base = _projects_base(transcript_path)
    encoded = _encode_project_path(os.path.abspath(_main_repo_root(cwd)))
    return os.path.join(base, encoded, "memory", "MEMORY.md")


def _read_memory_head(path):
    """Read the first 200 lines of a precomputed MEMORY.md path. '' when the path is
    falsy (resolution already breadcrumbed) or the file is absent/unreadable. Split
    from auto_memory_head so assemble can resolve the path once (one git call, not
    two) and reuse it for both the section text and the hint."""
    if not path:
        return ""
    if not os.path.isfile(path):
        _breadcrumb("Auto-memory (MEMORY.md head)", "not found at %s" % path)
        return ""
    try:
        lines = []
        with open(path, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= _MEMORY_HEAD_LINES:
                    break
                lines.append(line)
        return "".join(lines).rstrip("\n")
    except Exception as exc:
        _note_failure("Auto-memory (MEMORY.md head)", "read error (%s)" % type(exc).__name__)
        return ""


def auto_memory_head(cwd, transcript_path):
    """First 200 lines of the project's auto-memory MEMORY.md (matching a native
    load). '' when absent/unreadable."""
    try:
        path = _memory_md_path(cwd, transcript_path)
    except Exception as exc:
        _note_failure("Auto-memory (MEMORY.md head)", "path resolve errored (%s)" % type(exc).__name__)
        return ""
    return _read_memory_head(path)


# ----------------------------------------------------------------- covenant
def _covenant_doc(plugin_root):
    return os.path.join(os.path.abspath(plugin_root or "."), "rubric", "covenant.md")


def covenant(cwd, plugin_root):
    """The distilled superheroes covenant (`rubric/covenant.md`), injected ONLY for a
    superheroes-calibrated project (a storage-mode registry entry, or any hero calibration
    evidence). This REPLACES the older review-discipline-only note — the covenant subsumes
    its injection (its "review before handback" hard line carries the review convention and
    points back at the canonical `rubric/review-discipline.md`, which stays put).

    The calibration probe is strictly READ-ONLY — never `mode_registry.resolve()`, which can
    backfill-WRITE the registry; a session-start hook must not mutate project state. A probe
    error → '' with a breadcrumb (this is guidance; absence is the status quo, and injecting
    it into a non-superheroes project would be noise).

    The covenant text is READ from the plugin install (`rubric/covenant.md`), never the
    project repo — so injection leaves ZERO repo traces in both storage modes. An unreadable
    covenant on a CALIBRATED project is a genuine failure (the file ships with the plugin),
    so it is `_note_failure`'d (folded into the in-block diagnostics the owner's agent can
    read back) rather than treated as a silent absence — a calibrated session must never lose
    its covenant quietly."""
    try:
        import mode_registry
        calibrated = mode_registry.read_registry(cwd) is not None
        if not calibrated:
            verdict = mode_registry.evidence_verdict(mode_registry.hero_evidence(cwd))
            calibrated = verdict != "none"
    except Exception as exc:
        _note_failure("Covenant", "calibration probe errored (%s)" % type(exc).__name__)
        return ""
    if not calibrated:
        return ""
    path = _covenant_doc(plugin_root)
    try:
        return _read_text(path).strip()
    except Exception as exc:
        _note_failure("Covenant", "read error for %s (%s)" % (path, type(exc).__name__))
        return ""


# ----------------------------------------------------------------- assemble
_Rec = collections.namedtuple("_Rec", "name text hint")


def assemble(cwd, transcript_path, plugin_root, host, char_budget=9000):
    """Compose the injected `additionalContext` block, best-effort, never raising.

    Priority order: resolved roots → covenant (calibrated projects only)
    → project CLAUDE.md → env block → user CLAUDE.md → MEMORY.md head.
    The block stays under char_budget; an oversized
    source is truncated with a marker and stops the walk, and any present source
    dropped by that stop is named in an in-block omitted-line AND breadcrumbed
    (finding C2).

    B6 (#315): any GENUINE-failure breadcrumb collected during this assemble (a read/git/probe
    ERROR, or a budget drop) is also folded into an in-block "bootstrap diagnostics" line, so a
    half-bootstrapped session leaves a breadcrumb the running agent can read back — not only in the
    hook's stderr (which an owner's agent cannot see)."""
    del _FAILURES[:]                                  # reset the per-assemble failure collector
    try:
        # Resolve the multi-call source locations ONCE and reuse them for both the
        # section text and the _Rec.hint, so the Auto-memory git resolution
        # (get_gitdir) runs a single time per assemble on the always-on hot path
        # rather than twice (premortem-001). _claude_md_chain is subprocess-free but
        # likewise resolved once.
        chain = _claude_md_chain(cwd)
        try:
            mem_path = _memory_md_path(cwd, transcript_path)
        except Exception as exc:
            _note_failure("Auto-memory (MEMORY.md head)", "path resolve errored (%s)" % type(exc).__name__)
            mem_path = None
        records = [
            _Rec("Resolved plugin roots", resolved_roots(plugin_root, host),
                 os.path.join(os.path.abspath(plugin_root or "."), "hosts", "%s-tools.md" % host)),
            # Second record, immediately after resolved roots: resolved roots is small and
            # constant-size and the covenant is a fixed ~50-line doc, so placement guarantees
            # the covenant for any sane budget. Every variable-size source (each with
            # truncate/omit handling) follows.
            _Rec("Covenant", covenant(cwd, plugin_root),
                 _covenant_doc(plugin_root)),
            _Rec("Project CLAUDE.md", _read_claude_chain(chain),
                 ", ".join(chain) or None),
            _Rec("Environment", env_block(cwd), None),
            _Rec("User CLAUDE.md", user_memory(), _user_claude_md_path()),
            _Rec("Auto-memory (MEMORY.md head)", _read_memory_head(mem_path), mem_path),
        ]
    except Exception as exc:
        _note_failure("assemble", "source gather errored (%s)" % type(exc).__name__)
        return "".join([_HEADER] + _diagnostics_lines()).rstrip("\n") + "\n"

    out = [_HEADER]
    running = len(_HEADER)
    present = [r for r in records if r.text and r.text.strip()]
    omitted = []
    stopped = False
    for r in present:
        if stopped:
            omitted.append(r)
            continue
        sect_head = "\n### %s\n" % r.name
        section = sect_head + r.text.strip() + "\n"
        if running + len(section) <= char_budget:
            out.append(section)
            running += len(section)
        else:
            marker = "\n…(truncated for space — full content at %s)\n" % (r.hint or "its source file")
            room = char_budget - running - len(sect_head) - len(marker)
            if room > 0:
                out.append(sect_head + r.text.strip()[:room].rstrip() + marker)
            else:
                omitted.append(r)
            stopped = True

    if omitted:
        names = ", ".join(r.name for r in omitted)
        paths = "; ".join((r.hint or r.name) for r in omitted)
        out.append("\n…(%d source(s) omitted for space: %s — at %s)\n"
                   % (len(omitted), names, paths))
        for r in omitted:
            _note_failure(r.name, "omitted for space (budget=%d) at %s" % (char_budget, r.hint or "n/a"))

    out += _diagnostics_lines()
    return "".join(out).rstrip("\n") + "\n"


def _diagnostics_lines():
    """B6 (#315): render the collected genuine-failure breadcrumbs as an in-block diagnostics line
    (source names + reasons only — never file contents). '' (no lines) when nothing failed, so a
    clean bootstrap is byte-identical to before."""
    if not _FAILURES:
        return []
    items = "; ".join("%s: %s" % (src, reason) for src, reason in _FAILURES)
    return ["\n### Bootstrap diagnostics\n",
            "Some bootstrap sources did not load fully (names/reasons only, no contents): "
            + items + "\n"]
