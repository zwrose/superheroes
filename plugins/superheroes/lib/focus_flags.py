"""Mechanical focus flags: grep-detected additive review emphasis from a round diff (#511).

Pure + deterministic + stdlib-only. The review-code specialist dispatch
(`skills/review-code/reference/auto-fix-loop.md`) is the wired consumer: before a
round's finders are dispatched, the orchestrator runs this over the round diff and
appends each emitted line into every specialist's `Focus:` block.

Design authority: ratified #474 (position 15) — "mechanical focus flags: grep-detected
additive brief flags (migration file -> rollback emphasis; lockfile changed ->
supply-chain check) — ADDITIONS ONLY, never classifier-driven lens removal." This module
has NO authority: it can only ADD emphasis. It never removes a lens, drops a finding, or
down-scopes a review. A trigger must be grep-grounded in the diff — no false injection.
No trigger -> no flag.
"""
import re
import sys

# Dependency lockfiles, matched by exact filename (basename).
_LOCKFILES = frozenset({
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "npm-shrinkwrap.json",
    "Cargo.lock",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "Gemfile.lock",
    "composer.lock",
    "go.sum",
})

# Migration filename shapes (basename): NNN_*.sql, V<n>__*.sql, *.migration.*
_MIGRATION_NAME_RES = (
    re.compile(r"^\d+[_-].*\.sql$", re.IGNORECASE),   # 001_add_users.sql
    re.compile(r"^V\d+__.*\.sql$", re.IGNORECASE),    # V3__add_index.sql (Flyway)
    re.compile(r".*\.migration\..*", re.IGNORECASE),  # foo.migration.ts
)

# `diff --git a/<path> b/<path>` and `+++ b/<path>` header shapes.
_DIFF_GIT_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
_PLUS_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
# Hunk boundary: a `@@ ... @@` line opens the hunk body (added/removed source lines).
_HUNK_RE = re.compile(r"^@@")


def _changed_paths(diff_text):
    """Return the ordered, de-duplicated set of changed file paths parsed from a unified
    diff (from `diff --git` headers and `+++ b/` headers). `/dev/null` is dropped.

    Tracks diff structure so a `+++ `/`--- ` line only counts as a header when NOT inside a
    hunk body: an added source line like `+++ package-lock.json` renders as `+++ ...` and
    must not be misread as a `+++ b/` header. A `diff --git ` line returns to header
    context; an `@@` line enters the hunk body."""
    paths = []
    seen = set()
    in_hunk = False

    def _add(p):
        p = p.strip()
        if not p or p == "/dev/null":
            return
        # Strip a trailing tab-appended git decoration if present.
        p = p.split("\t", 1)[0]
        if p not in seen:
            seen.add(p)
            paths.append(p)

    for line in diff_text.splitlines():
        m = _DIFF_GIT_RE.match(line)
        if m:
            in_hunk = False  # back to header context for this file's stanza
            _add(m.group(2))  # the b/ side (post-image path)
            continue
        if _HUNK_RE.match(line):
            in_hunk = True  # subsequent +/- lines are hunk body, not headers
            continue
        if in_hunk:
            continue  # ignore `+++`/`--- ` inside a hunk — those are source lines
        m = _PLUS_RE.match(line)
        if m:
            _add(m.group(1))
    return paths


def _is_migration(path):
    segs = path.split("/")
    if "migrations" in segs[:-1] or "migrate" in segs[:-1]:
        return True
    base = segs[-1]
    return any(rx.match(base) for rx in _MIGRATION_NAME_RES)


def _is_lockfile(path):
    return path.split("/")[-1] in _LOCKFILES


def _compact(names, limit=3):
    """Name the representative file(s) compactly for a flag body."""
    if len(names) <= limit:
        return ", ".join(names)
    return ", ".join(names[:limit]) + f" (+{len(names) - limit} more)"


def compute_focus_flags(diff_text):
    """Parse a unified diff for changed file paths and return additive focus-flag strings.

    Additions only: each returned string ADDS review emphasis; the function never removes a
    lens, drops a finding, or down-scopes coverage. Each rule fires at most once (deduped),
    naming the representative changed file(s). No grep-grounded trigger -> empty list."""
    if not diff_text:
        return []
    paths = _changed_paths(diff_text)

    migrations = [p for p in paths if _is_migration(p)]
    lockfiles = [p for p in paths if _is_lockfile(p)]

    flags = []
    if migrations:
        flags.append(
            "Migration changed (" + _compact(migrations) + "): audit the migration's "
            "rollback / down-path and data-safety — reversibility, ordering, and "
            "partial-failure/rerun behavior."
        )
    if lockfiles:
        flags.append(
            "Dependency lockfile changed (" + _compact(lockfiles) + "): supply-chain "
            "check — confirm added/updated deps are intended, pinned, and from expected "
            "sources."
        )
    return flags


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: focus_flags.py <diff_path>\n")
        return 2
    with open(argv[1], "r", encoding="utf-8", errors="replace") as fh:
        diff_text = fh.read()
    for flag in compute_focus_flags(diff_text):
        sys.stdout.write(flag + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
