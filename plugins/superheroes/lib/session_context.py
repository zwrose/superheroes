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


def _breadcrumb(source, reason):
    """One-line diagnostic to stderr (the hook log). Reason carries source names,
    paths, and exception *types* only — never file contents or secret values."""
    try:
        sys.stderr.write("superheroes bootstrap: %s — %s\n" % (source, reason))
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
            _breadcrumb("Project CLAUDE.md", "read error for %s (%s)" % (f, type(exc).__name__))
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
        _breadcrumb("User CLAUDE.md", "read error (%s)" % type(exc).__name__)
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
        _breadcrumb("Environment", "date unavailable (%s)" % type(exc).__name__)
    try:
        email = store_core.run_git(cwd or ".", "config", "user.email")
    except Exception as exc:
        email = None
        _breadcrumb("Environment", "git config user.email errored (%s)" % type(exc).__name__)
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
        _breadcrumb("Auto-memory (MEMORY.md head)", "gitdir resolve errored (%s)" % type(exc).__name__)
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
        _breadcrumb("Auto-memory (MEMORY.md head)", "read error (%s)" % type(exc).__name__)
        return ""


def auto_memory_head(cwd, transcript_path):
    """First 200 lines of the project's auto-memory MEMORY.md (matching a native
    load). '' when absent/unreadable."""
    try:
        path = _memory_md_path(cwd, transcript_path)
    except Exception as exc:
        _breadcrumb("Auto-memory (MEMORY.md head)", "path resolve errored (%s)" % type(exc).__name__)
        return ""
    return _read_memory_head(path)


# ----------------------------------------------------------------- review discipline
def _discipline_doc(plugin_root):
    return os.path.join(os.path.abspath(plugin_root or "."), "rubric", "review-discipline.md")


def review_discipline(cwd, plugin_root):
    """Compact review-discipline note, injected ONLY for a superheroes-calibrated project
    (a storage-mode registry entry, or any hero calibration evidence). The probe is strictly
    READ-ONLY — never mode_registry.resolve(), which can backfill-WRITE the registry; a
    session-start hook must not mutate project state. Any probe error → '' with a breadcrumb
    (this is guidance; absence is the status quo, and injecting it into non-superheroes
    projects would be noise)."""
    try:
        import mode_registry
        calibrated = mode_registry.read_registry(cwd) is not None
        if not calibrated:
            verdict = mode_registry.evidence_verdict(mode_registry.hero_evidence(cwd))
            calibrated = verdict != "none"
    except Exception as exc:
        _breadcrumb("Review discipline", "calibration probe errored (%s)" % type(exc).__name__)
        return ""
    if not calibrated:
        return ""
    return (
        "This project is calibrated with superheroes, whose review convention applies to "
        "every session working here: **every PR gets a real review before handback**, no "
        "matter how small the diff or how it was built. Pipeline work reviews itself; a "
        "direct build ends with `/superheroes:review-code` (or an explicit owner-directed "
        "review) before the PR is handed back; a review that halts with an open blocker is "
        "resolved or explicitly owner-accepted in the PR body — never quietly merged. "
        "\"Too small to review\" is never a reason to skip. Full statement: %s"
        % _discipline_doc(plugin_root)
    )


# ----------------------------------------------------------------- assemble
_Rec = collections.namedtuple("_Rec", "name text hint")


def assemble(cwd, transcript_path, plugin_root, host, char_budget=9000):
    """Compose the injected `additionalContext` block, best-effort, never raising.

    Priority order: resolved roots → review discipline (calibrated projects only)
    → project CLAUDE.md → env block → user CLAUDE.md → MEMORY.md head.
    The block stays under char_budget; an oversized
    source is truncated with a marker and stops the walk, and any present source
    dropped by that stop is named in an in-block omitted-line AND breadcrumbed
    (finding C2)."""
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
            _breadcrumb("Auto-memory (MEMORY.md head)", "path resolve errored (%s)" % type(exc).__name__)
            mem_path = None
        records = [
            _Rec("Resolved plugin roots", resolved_roots(plugin_root, host),
                 os.path.join(os.path.abspath(plugin_root or "."), "hosts", "%s-tools.md" % host)),
            # Second record, immediately after resolved roots: both are small and
            # constant-size, so placement guarantees the note for any sane budget.
            # Every variable-size source (each with truncate/omit handling) follows.
            _Rec("Review discipline", review_discipline(cwd, plugin_root),
                 _discipline_doc(plugin_root)),
            _Rec("Project CLAUDE.md", _read_claude_chain(chain),
                 ", ".join(chain) or None),
            _Rec("Environment", env_block(cwd), None),
            _Rec("User CLAUDE.md", user_memory(), _user_claude_md_path()),
            _Rec("Auto-memory (MEMORY.md head)", _read_memory_head(mem_path), mem_path),
        ]
    except Exception as exc:
        _breadcrumb("assemble", "source gather errored (%s)" % type(exc).__name__)
        return _HEADER

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
            _breadcrumb(r.name, "omitted for space (budget=%d) at %s" % (char_budget, r.hint or "n/a"))

    return "".join(out).rstrip("\n") + "\n"
