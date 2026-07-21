#!/usr/bin/env python3
"""Capture review-loop convergence runner output as golden JSON fixtures.

Runs ``review_loop_runner.js`` for every fixture under ``fixtures/review_loop/``
and writes pretty-printed, key-sorted JSON to ``fixtures/review_loop/goldens/``.
``telemetry_failure.json`` is also captured with ``--fail-telemetry``.

Normalization (applied recursively before writing):
  - Any string value whose dict key contains ``path`` or ``dir`` (case-insensitive)
    is replaced with ``os.path.basename(value)`` so absolute tmp session dirs do not
    leak into goldens.
  - No timestamp or duration fields appear in current runner output; if added later,
    extend ``normalize`` below and document the rule here.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parents[2]
FIXTURES = EVAL_DIR / "fixtures" / "review_loop"
RUNNER = EVAL_DIR / "review_loop_runner.js"
DEFAULT_GOLDENS = FIXTURES / "goldens"
FAIL_TELEMETRY_FIXTURE = "telemetry_failure.json"


def normalize(obj):
    """Return a copy of *obj* with nondeterministic fields normalized."""
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            if isinstance(value, str) and ("path" in key.lower() or "dir" in key.lower()):
                out[key] = os.path.basename(value)
            else:
                out[key] = normalize(value)
        return out
    if isinstance(obj, list):
        return [normalize(item) for item in obj]
    return obj


def run_fixture(fixture_path: Path, extra_args: list[str]) -> dict:
    proc = subprocess.run(
        ["node", str(RUNNER), str(fixture_path), *extra_args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)
    return json.loads(proc.stdout)


def write_golden(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize(payload)
    text = json.dumps(normalized, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def capture(output_dir: Path) -> None:
    fixtures = sorted(FIXTURES.glob("*.json"))
    if not fixtures:
        raise SystemExit(f"no fixtures found in {FIXTURES}")

    for fixture_path in fixtures:
        stem = fixture_path.stem
        payload = run_fixture(fixture_path, [])
        write_golden(output_dir / f"{stem}.golden.json", payload)

        if fixture_path.name == FAIL_TELEMETRY_FIXTURE:
            fail_payload = run_fixture(fixture_path, ["--fail-telemetry"])
            write_golden(
                output_dir / f"{stem}.fail-telemetry.golden.json",
                fail_payload,
            )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_GOLDENS,
        help=f"directory for golden files (default: {DEFAULT_GOLDENS})",
    )
    args = parser.parse_args(argv)
    capture(args.output_dir)


if __name__ == "__main__":
    main()
