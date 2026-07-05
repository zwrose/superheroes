#!/usr/bin/env python3
"""Deterministic release classifier (stdlib only) — the single home of the release-class rules.

Reads the set of files a release ships (the commit range being released) and answers exactly
one question: which live verification instruments does this release *owe* before it can be cut?

Two axes (issue #237):

- **spine-carrying** — the showrunner pipeline the acceptance harness exercises end-to-end
  changed. Two mechanisms, because JS and Python have different safety nets:
  - **JS side (positive globs).** The committed `showrunner.bundle.js` is drift-locked to its
    source modules — CI (`bundle_showrunner.js --check`) fails any PR that changes a bundled
    module without rebuilding the bundle — so matching the bundle + entry + bundler catches every
    JS spine change. Kept narrow.
  - **Python side (default-IN / exclude-out, FAIL CLOSED).** Python deciders have no bundle
    drift-lock, so a positive-glob allowlist silently under-owns — a NEW decider (or an existing
    one nobody remembered to list, e.g. `pr_entry.py`, `dod_gate.py`) would classify "neither" and
    owe no acceptance run even though it is live spine. So EVERY `plugins/superheroes/lib/**` file
    (minus `lib/tests/**`) is spine-carrying by default, MINUS a short curated list of non-runtime
    modules the live pipeline never exercises (calibration / configure / view layer). The safe
    direction is over-owning an acceptance run; silently owing nothing is not.
- **reviewer-touching** — a reviewer seat's methodology changed (`agents/*-reviewer.md`) or the
  shared rubric it reads (`rubric/*`). Owes the **benchmark** (review A/B eval).

A release can be both, or **neither** (docs-only / repo-plumbing) — a neither release owes no
instrument and its evidence check is trivially green.

These rules live in EXACTLY ONE place (this module). The CI evidence check consumes this
classifier; the runbook and the `release-eval` skill never re-derive them (#231) — the skill is
driven entirely by the check's owed-summary.

The matcher is a pure function over a list of repo-relative paths so it is unit-testable without
git; the CLI resolves the range via git and prints the owed instruments + the exact commands.
"""
import argparse
import fnmatch
import json
import subprocess
import sys

# --- spine classification (repo-relative paths) ------------------------------------------

_LIB_PREFIX = "plugins/superheroes/lib/"
_LIB_TESTS_PREFIX = "plugins/superheroes/lib/tests/"

# JS side — kept as-is (bundle drift-lock, see module docstring). Narrow on purpose.
SPINE_GLOBS = (
    "plugins/superheroes/lib/showrunner.js",
    "plugins/superheroes/lib/showrunner.bundle.js",
    "plugins/superheroes/lib/bundle_showrunner.js",
    "plugins/superheroes/lib/*loop*",
    "plugins/superheroes/lib/*phase*",
    "plugins/superheroes/lib/review_round_policy.*",
)

# Python side — default-IN. A lib/*.py file is spine UNLESS its basename is one of these
# explicitly non-runtime modules. KEEP THIS LIST SHORT and justify every entry against the ACTUAL
# pipeline: an exclude is only safe if NO phase of the acceptance run (plan → review → tasks →
# review → build → review-code → test-pilot → ship) reaches it. A wrong exclude silently owes
# nothing — the exact fail-open bug this design closes; a missing exclude merely over-owns an
# acceptance run (acceptable). When in doubt, do NOT exclude. (Deliberately excluded from this set,
# because they ARE pipeline-reachable and must stay spine: `calibration_resolve.py` /
# `core_md.py` — exec'd in the review phases; `architect_config.py` — reached via
# `definition_doc` on the showrunner gate paths.)
_PY_SPINE_EXCLUDE = frozenset({
    "catalog.py",  # marketplace catalog helper (validate/repo plumbing; no pipeline caller)
})
# ...plus every `configure_*.py` (the whole `configure` skill's internals; the pipeline never
# runs `configure`, so none of them is reachable from an acceptance run).
_PY_SPINE_EXCLUDE_GLOBS = ("configure_*.py",)

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


def _is_spine(path):
    """Spine-carrying? Test files never owe an acceptance run; the JS globs are the bundle
    drift-lock; every other lib/*.py is spine by default unless explicitly excluded (fail closed)."""
    if path.startswith(_LIB_TESTS_PREFIX):
        return False
    if _match(path, SPINE_GLOBS):
        return True
    if path.startswith(_LIB_PREFIX) and path.endswith(".py"):
        base = path.rsplit("/", 1)[-1]
        if base in _PY_SPINE_EXCLUDE or _match(base, _PY_SPINE_EXCLUDE_GLOBS):
            return False
        return True
    return False


def classify(changed_paths):
    """Pure classifier over repo-relative changed paths.

    Returns a dict with the release class, the owed instruments (in a stable order), and the
    paths that triggered each axis (for a legible, auditable readout).
    """
    paths = [p for p in (changed_paths or []) if p]
    spine_hits = sorted({p for p in paths if _is_spine(p)})
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
