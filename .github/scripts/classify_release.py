#!/usr/bin/env python3
"""Deterministic release classifier (stdlib only) — the single home of the release-class globs.

Reads the set of files a release ships (the commit range being released) and answers exactly
one question: which live verification instruments does this release *owe* before it can be cut?

Two axes, from the globs below (issue #237):

- **spine-carrying** — the showrunner pipeline the acceptance harness exercises end-to-end
  changed. Anchored on the committed spine bundle (`showrunner.bundle.js`, which CI keeps
  drift-locked to its 27 source modules via `bundle_showrunner.js --check`, so a change to any
  bundled module forces a bundle change in the same commit), plus the spine entry/bundler and
  the loop / phase / review-round-policy machinery named in the issue. Owes the **acceptance**
  run.
- **reviewer-touching** — a reviewer seat's methodology changed (`agents/*-reviewer.md`) or the
  shared rubric it reads (`rubric/*`). Owes the **benchmark** (review A/B eval).

A release can be both, or **neither** (docs-only / repo-plumbing) — a neither release owes no
instrument and its evidence check is trivially green.

These globs live in EXACTLY ONE place (this module). The CI evidence check consumes this
classifier; the runbook and the `release-eval` skill never re-derive the globs (#231) — the skill
is driven entirely by the check's owed-summary.

The matcher is a pure function over a list of repo-relative paths so it is unit-testable without
git; the CLI resolves the range via git and prints the owed instruments + the exact commands.
"""
import argparse
import fnmatch
import json
import subprocess
import sys

# --- the globs (repo-relative, fnmatch) --------------------------------------------------

# Spine = what the acceptance harness validates end-to-end. `showrunner.bundle.js` is
# drift-locked to every bundled module, so listing it covers all 27 JS spine modules; the
# remaining patterns add the entry, the bundler, and the loop / phase / policy machinery
# (including the Python deciders the skills invoke, which are not in the bundle).
SPINE_GLOBS = (
    "plugins/superheroes/lib/showrunner.js",
    "plugins/superheroes/lib/showrunner.bundle.js",
    "plugins/superheroes/lib/bundle_showrunner.js",
    "plugins/superheroes/lib/*loop*",
    "plugins/superheroes/lib/*phase*",
    "plugins/superheroes/lib/review_round_policy.*",
)

# Reviewer = a reviewer seat's methodology or the shared rubric it reads.
REVIEWER_GLOBS = (
    "plugins/superheroes/agents/*-reviewer.md",
    "plugins/superheroes/rubric/*",
)

# Instrument owed per axis.
SPINE_INSTRUMENT = "acceptance"
REVIEWER_INSTRUMENT = "benchmark"


def _match(path, globs):
    return any(fnmatch.fnmatch(path, g) for g in globs)


def classify(changed_paths):
    """Pure classifier over repo-relative changed paths.

    Returns a dict with the release class, the owed instruments (in a stable order), and the
    paths that triggered each axis (for a legible, auditable readout).
    """
    paths = [p for p in (changed_paths or []) if p]
    spine_hits = sorted({p for p in paths if _match(p, SPINE_GLOBS)})
    reviewer_hits = sorted({p for p in paths if _match(p, REVIEWER_GLOBS)})
    spine = bool(spine_hits)
    reviewer = bool(reviewer_hits)

    owed = []
    if spine:
        owed.append(SPINE_INSTRUMENT)
    if reviewer:
        owed.append(REVIEWER_INSTRUMENT)

    if spine and reviewer:
        cls = "spine-carrying+reviewer-touching"
    elif spine:
        cls = "spine-carrying"
    elif reviewer:
        cls = "reviewer-touching"
    else:
        cls = "neither"

    return {
        "class": cls,
        "spine": spine,
        "reviewer": reviewer,
        "owed": owed,
        "spine_hits": spine_hits,
        "reviewer_hits": reviewer_hits,
    }


# --- the commands each owed instrument runs (printed for humans / the runbook) ------------

def instrument_commands(root="<repo>", spine_lib="<repo>/plugins/superheroes/lib"):
    """The exact commands each instrument is run with. Placeholders keep the classifier
    checkout-agnostic; the runbook and readout substitute the real checkout path."""
    return {
        "acceptance": (
            "python3 plugins/superheroes/lib/acceptance_run.py "
            "--fixture plugins/superheroes/eval/fixtures/acceptance "
            f"--root {root} --spine-lib {spine_lib}"
        ),
        "benchmark": (
            "the review A/B dual-dispatch per plugins/superheroes/eval/README.md, then "
            "score with plugins/superheroes/eval/score.py; append the dated verdict to "
            "plugins/superheroes/eval/RESULTS.md"
        ),
    }


# --- git range resolution + CLI ----------------------------------------------------------

def _git(args):
    return subprocess.run(
        ["git"] + args, text=True, capture_output=True
    )


def last_release_tag(head="HEAD"):
    """The most recent `superheroes-v*` tag reachable from head (the last cut release), or
    None when there is no prior release (first-ever release)."""
    r = _git(["describe", "--tags", "--abbrev=0", "--match", "superheroes-v*", head])
    tag = r.stdout.strip()
    return tag if r.returncode == 0 and tag else None


def changed_paths_in_range(base, head="HEAD"):
    """Repo-relative paths that differ between base and head. When base is None (no prior
    release), every tracked file at head counts as shipping in this first release."""
    if base is None:
        r = _git(["ls-tree", "-r", "--name-only", head])
    else:
        r = _git(["diff", "--name-only", f"{base}..{head}"])
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit(2)
    return [line for line in r.stdout.splitlines() if line.strip()]


def render(result, base, head, commands):
    lines = [
        f"Release class: {result['class']}",
        f"Range: {base or '(no prior release — whole tree)'}..{head}",
        "",
    ]
    if not result["owed"]:
        lines.append("Owed instruments: none — docs-only / repo-plumbing release. Evidence "
                     "check is trivially green.")
        return "\n".join(lines)
    lines.append("Owed instruments:")
    for inst in result["owed"]:
        why = result["spine_hits"] if inst == SPINE_INSTRUMENT else result["reviewer_hits"]
        lines.append(f"  - {inst} (triggered by: {', '.join(why[:6])}"
                     f"{' …' if len(why) > 6 else ''})")
        lines.append(f"      run: {commands[inst]}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="classify a release and print owed instruments")
    ap.add_argument("--base", help="range base ref (default: last superheroes-v* tag)")
    ap.add_argument("--head", default="HEAD", help="range head ref (default: HEAD)")
    ap.add_argument("--json", action="store_true", help="emit the machine-readable owed summary")
    args = ap.parse_args(argv)

    base = args.base if args.base else last_release_tag(args.head)
    paths = changed_paths_in_range(base, args.head)
    result = classify(paths)
    commands = instrument_commands()

    if args.json:
        out = dict(result)
        out["base"] = base
        out["head"] = args.head
        out["commands"] = {k: commands[k] for k in result["owed"]}
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(render(result, base, args.head, commands))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
