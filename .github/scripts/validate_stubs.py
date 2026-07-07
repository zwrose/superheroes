#!/usr/bin/env python3
"""Deterministic no-silent-stubs validator (issue #228, stdlib only).

Run from the repo root in CI. Scans the plugin's Python/JS source for STUB markers and
fails on any marker missing a valid issue reference — a deliberately-unwired seam must
carry `# STUB(#NNN): <what is unwired and the live effect>` so it is tracked, not silent.

The marker grammar + the reserved `#NNN` placeholder live in the plugin's `stub_markers`
lib (single source of truth, shared with the draft-PR body generator). This script only
walks the tree and reports. It does NOT detect *unmarked* stubs — that is out of scope by
design (it catches only stubs the author already flagged but under-specified).
"""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LIB = os.path.join(REPO, "plugins", "superheroes", "lib")
sys.path.insert(0, LIB)
import stub_markers  # noqa: E402  (plugin lib is the single source of truth for the grammar)

SCAN_EXTS = (".py", ".js")
# Test trees legitimately embed example/fixture markers (malformed on purpose); the bundle
# is a generated artifact whose source is scanned already. Neither is a production seam.
_SKIP_DIR_SEGMENTS = ("/tests/", "/node_modules/", "/.git/")
_SKIP_BASENAME_SUFFIXES = (".bundle.js",)


def _should_scan(path):
    rel = "/" + os.path.relpath(path, REPO).replace(os.sep, "/")
    if any(seg in rel for seg in _SKIP_DIR_SEGMENTS):
        return False
    base = os.path.basename(path)
    if base.startswith("test_") or base.endswith(_SKIP_BASENAME_SUFFIXES):
        return False
    return base.endswith(SCAN_EXTS)


def iter_source_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("tests", "node_modules", ".git")]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if _should_scan(path):
                yield path


def gather_violations(root):
    """Walk `root` and collect every malformed STUB marker as a
    "<relpath>:<line>: <reason>" string. Pure over the tree for unit testing."""
    errors = []
    for path in sorted(iter_source_files(root)):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        rel = os.path.relpath(path, REPO)
        for v in stub_markers.find_violations(text):
            errors.append("%s:%s: %s" % (rel, v["line"], v["reason"]))
    return errors


def main(argv=None):
    import argparse
    argparse.ArgumentParser(description="validate STUB markers carry an issue reference").parse_args(argv or [])
    errors = gather_violations(os.path.join(REPO, "plugins"))
    if errors:
        sys.stderr.write("\n✗ %d STUB marker problem(s) — every stub needs a tracked issue:\n" % len(errors))
        for e in errors:
            sys.stderr.write("  - %s\n" % e)
        sys.stderr.write("\nFix: mark each seam `# STUB(#<issue>): <what is unwired and the live effect>`.\n")
        return 1
    print("✓ all STUB markers carry an issue reference")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
