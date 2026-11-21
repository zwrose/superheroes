#!/usr/bin/env python3
"""CI check for upgrade-note files (issue 2590): a thin wrapper over plugins/superheroes/lib/transition_notes.py.

Every decision lives in the lib module; this script only gathers the inputs (the working tree for the
head, read-only git for the base) and prints the result: one JSON object on stdout, one
`<file>: <token>: <detail>` line per problem on stderr. Exit 0 with no problem, 1 otherwise.

    scripts/pinned-python .github/scripts/check_transition_notes.py [--repo-root R] [--base SHA] [--release]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys

_GIT_TIMEOUT = 60
_PLUGIN = "plugins/superheroes"
_TRANSITION = "TRANSITION.md"
_LIB_REL = _PLUGIN + "/lib/transition_notes.py"


class _BaseUnresolvable(Exception):
    """The base commit, or something read from it, could not be had; `.detail` says what."""

    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


def _problem(file, token, detail):
    return {"file": file, "token": token, "detail": detail}


def _load_lib(repo_root):
    spec = importlib.util.spec_from_file_location(
        "transition_notes", os.path.join(repo_root, *_LIB_REL.split("/"))
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo_root, *args):
    """(returncode, stdout) of a read-only git call; a timeout is a _BaseUnresolvable."""
    argv = ["git", "-C", repo_root, *args]
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=_GIT_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired:
        raise _BaseUnresolvable("git " + " ".join(args) + " timed out after " + str(_GIT_TIMEOUT) + " seconds.")
    except OSError as exc:
        raise _BaseUnresolvable("git could not run: " + str(exc))
    return proc.returncode, proc.stdout


def _read_base(repo_root, sha, tn):
    """(base TRANSITION.md text, base notes in assembly order) at commit `sha`, read-only."""
    rc, _out = _git(repo_root, "rev-parse", "--verify", sha + "^{commit}")
    if rc != 0:
        raise _BaseUnresolvable("The base " + sha + " is not a commit in this repository.")
    rc, text = _git(repo_root, "show", sha + ":" + _PLUGIN + "/" + _TRANSITION)
    base_transition = text if rc == 0 else ""
    folder = _PLUGIN + "/" + tn.NOTES_DIRNAME + "/"
    rc, listing = _git(repo_root, "ls-tree", "--name-only", sha, folder)
    if rc != 0:
        raise _BaseUnresolvable("git ls-tree failed for " + folder + " at " + sha + ".")
    notes = []
    for path in listing.splitlines():
        name = path.rsplit("/", 1)[-1]
        if not name or name == tn.README_NAME:
            continue
        rc, body = _git(repo_root, "show", sha + ":" + path)
        if rc != 0:
            raise _BaseUnresolvable("git show failed for " + path + " at " + sha + ".")
        notes.append((name, body))
    notes.sort(key=lambda n: tn.sort_key(n[0]))
    return base_transition, notes


def _mode(base, release):
    if base and release:
        return "pr+release"
    if base:
        return "pr"
    if release:
        return "release"
    return "shape"


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Check upgrade-note files against the shape adopt-version reads.")
    ap.add_argument("--repo-root", default=os.path.dirname(os.path.dirname(here)))
    ap.add_argument("--base", default=None)
    ap.add_argument("--release", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.repo_root)
    tn = _load_lib(root)
    plugin_root = os.path.join(root, *_PLUGIN.split("/"))
    head_notes = tn.read_notes(plugin_root)
    mode = _mode(args.base is not None, args.release)

    # axis: the three CI questions answered by the lib on inputs gathered here; bites on a malformed note
    # file (shape), a note written straight into TRANSITION.md or removed without assembly (--base), a
    # note file left unassembled on the release PR (--release), and an unreadable base (fail closed).
    problems = []
    if args.base is None:
        problems.extend(tn.check_notes(head_notes))
    else:
        try:
            base_transition, base_notes = _read_base(root, args.base, tn)
            with open(os.path.join(plugin_root, _TRANSITION), encoding="utf-8") as fh:
                head_transition = fh.read()
        except _BaseUnresolvable as exc:
            problems.append(_problem(_TRANSITION, "base-unresolvable", exc.detail))
        except (OSError, ValueError) as exc:
            problems.append(_problem(_TRANSITION, "transition-unreadable", "TRANSITION.md at the head could not be read: " + str(exc)))
        else:
            problems.extend(tn.compare_pr(base_transition, head_transition, base_notes, head_notes))
    if args.release:
        problems.extend(tn.release_problems(head_notes))

    sys.stdout.write(json.dumps({
        "ok": not problems,
        "mode": mode,
        "problems": problems,
        "notes": [name for name, _text in head_notes],
    }) + "\n")
    for p in problems:
        sys.stderr.write(p["file"] + ": " + p["token"] + ": " + p["detail"] + "\n")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
