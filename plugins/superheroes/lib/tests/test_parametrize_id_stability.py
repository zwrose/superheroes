"""Guard: `test_pilot_malformed_input.py` collects the same test IDs in every process (#894).

That file parametrizes over a hostile-value list containing `object()`. With the original
`ids=lambda v: repr(v)[:40]`, `repr(object())` embeds a per-process memory address — so every
pytest process collected a *different* ID for those cases. `pytest -n auto` aborts outright when
its workers disagree on node IDs (spike #816 measured zero tests run), and anything else that
compares IDs across processes is latently broken the same way. #816's collection-diff found this
was the only unstable ID in all 8,086 tests.

This guard closes the *class* for that file rather than the one `object()` instance: collect it
twice in two fresh processes under different hash seeds, and require the node IDs to be identical
and free of any `0x…` address. Any future parametrization whose IDs leak process-local state
fails here instead of at the next xdist attempt.
"""
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# .../<repo>/plugins/superheroes/lib/tests -> <repo>
_REPO_ROOT = os.path.realpath(os.path.join(_HERE, "..", "..", "..", ".."))
_TARGET = os.path.join(_HERE, "test_pilot_malformed_input.py")

_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")


def _collect_ids(hash_seed):
    """Node IDs `--collect-only` reports for the target file, from a fresh process."""
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            _TARGET,
            "--collect-only",
            "-q",
            # Pinned condition: xdist/randomly/cacheprovider are disabled so the two runs
            # differ only in hash seed. Made unobservable by the pin: ID perturbation caused
            # BY one of those plugins rather than by the `ids=` callable itself — this guard
            # covers the callable, which is where #894's defect and its class live.
            "-p",
            "no:xdist",
            "-p",
            "no:randomly",
            "-p",
            "no:cacheprovider",
        ],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "collection of %s failed (exit %d)\nstdout:\n%s\nstderr:\n%s"
        % (_TARGET, proc.returncode, proc.stdout, proc.stderr)
    )
    # `-q --collect-only` prints one node ID per line plus a trailing count summary.
    ids = [line.split("::", 1)[1] for line in proc.stdout.splitlines() if "::" in line]
    assert ids, "collected no tests from %s — the guard would pass vacuously" % _TARGET
    return ids


def test_malformed_input_parametrize_ids_are_process_independent():
    first = _collect_ids("0")
    second = _collect_ids("1")

    # Axis 1 — cross-process AGREEMENT: the same file collects byte-identical node IDs in two
    # fresh processes. Bites on any `ids=` output that varies with process-local state.
    assert first == second, (
        "two independent --collect-only runs of %s disagree on test IDs — a parametrize `ids=` "
        "is leaking process-local state (a memory address, a hash-ordered repr), which aborts "
        "`pytest -n auto`. First difference: %r != %r"
        % (
            os.path.basename(_TARGET),
            next((a for a, b in zip(first, second) if a != b), None),
            next((b for a, b in zip(first, second) if a != b), None),
        )
    )

    # Axis 2 — ADDRESS SHAPE: no collected ID carries a `0x…` pointer. Independent of axis 1,
    # which two processes can satisfy by chance (or with a constant address literal baked in).
    leaked = sorted({node_id for node_id in first if _ADDRESS.search(node_id)})
    assert not leaked, (
        "test IDs in %s embed a memory address (`0x…`), which differs per process and aborts "
        "`pytest -n auto`; use a type-name or index-based `ids=` instead. Offenders: %r"
        % (os.path.basename(_TARGET), leaked[:5])
    )
