#!/usr/bin/env python3
"""Best-effort SessionStart context assembler.

Current Claude Code natively loads the project-context layer — project/user
``CLAUDE.md``, the env block, the ``MEMORY.md`` head — on **all** spawn paths:
plain chat, headless ``-p``, and slash-command spawn (probe-verified #627 F1 on
Claude Code 2.1.219). This module injects ONLY what the harness does not supply
and a superheroes session uniquely needs: the resolved absolute plugin + host-tool-map
roots, and the distilled covenant (calibrated projects only).

The slim set depends on the harness continuing to auto-load the project layer;
that residual dependency is watched by ``lib/harness_probe.py`` (run it on harness
upgrades) and a regression's fallback is restoring the dropped records (a one-commit
revert).

Design contract (see docs/superpowers/specs/2026-06-21-discovery-entry-path-bootstrap-design.md):

- **Best-effort, never raises.** Each source is gathered in its own try/except;
  a failed/absent source is omitted and a one-line breadcrumb (``<source>:
  <reason>``) is written to **stderr** — NEVER the file contents (stderr is the
  hook log; leaking contents there would defeat the diagnosable-not-leaky bar).
- **Budget.** ``assemble`` keeps the block under ``char_budget`` as belt-and-suspenders
  (with only two small records this no longer triggers at normal size; the loop
  remains so truncated/omitted sources are never silently indistinguishable from
  absent files). A present source dropped by the budget is named in an in-block
  omitted-line AND breadcrumbed.

Stdlib-only.
"""
import collections
import os
import sys

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


# ----------------------------------------------------------------- cache hygiene nudge
_NUDGE_MAX_CHARS = 400
_NUDGE_TAIL = (
    ". Nothing was deleted — this scan is read-only. "
    "advisor: propose a manual review/cleanup with the owner."
)


def cache_hygiene(plugin_root):
    """One-line advisor nudge when OLDER plugin-version dirs hold stale `.in_use`
    markers. READ-ONLY — reports, never deletes. '' when nothing is stale (a clean
    bootstrap stays byte-identical to before)."""
    try:
        import cache_markers
        result = cache_markers.scan_stale_siblings(plugin_root)
        dirs = result.get("dirs") or []
        markers = int(result.get("markers") or 0)
        if not dirs:
            return ""

        n_dirs = len(dirs)
        count_part = ": %d stale marker(s)" % markers
        head = "Stale plugin-cache markers found in %d older version dir(s) (" % n_dirs

        def render(dir_list):
            inner = ", ".join(dir_list)
            return head + inner + ")" + count_part + _NUDGE_TAIL

        line = render(dirs)
        if len(line) <= _NUDGE_MAX_CHARS:
            return line

        shown = list(dirs)
        while len(shown) > 1:
            hidden = n_dirs - len(shown)
            dir_list = list(shown)
            if hidden > 0:
                dir_list.append("+%d more" % hidden)
            candidate = render(dir_list)
            if len(candidate) <= _NUDGE_MAX_CHARS:
                return candidate
            shown.pop()

        hidden = n_dirs - 1
        suffix_label = ", +%d more" % hidden if hidden > 0 else ""
        dir_list = [shown[0] + suffix_label] if shown else ["+%d more" % n_dirs]
        candidate = render(dir_list)
        if len(candidate) <= _NUDGE_MAX_CHARS:
            return candidate
        return candidate[:_NUDGE_MAX_CHARS].rstrip()
    except Exception as exc:
        _breadcrumb("Plugin cache hygiene", type(exc).__name__)
        return ""


# ----------------------------------------------------------------- assemble
_Rec = collections.namedtuple("_Rec", "name text hint")


def assemble(cwd, transcript_path, plugin_root, host, char_budget=9000):
    """Compose the injected `additionalContext` block, best-effort, never raising.

    Priority order: resolved roots → plugin cache hygiene nudge → covenant (calibrated
    projects only).
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
        cache_parent = os.path.dirname(os.path.abspath(plugin_root or "."))
        records = [
            _Rec("Resolved plugin roots", resolved_roots(plugin_root, host),
                 os.path.join(os.path.abspath(plugin_root or "."), "hosts", "%s-tools.md" % host)),
            _Rec("Plugin cache hygiene", cache_hygiene(plugin_root), cache_parent),
            _Rec("Covenant", covenant(cwd, plugin_root),
                 _covenant_doc(plugin_root)),
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
