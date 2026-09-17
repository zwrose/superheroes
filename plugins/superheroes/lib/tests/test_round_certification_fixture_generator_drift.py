"""Drift guard: generated certification fixtures must match the producer."""
import filecmp
import os
import shutil
import tempfile

from generate_round_certification_fixtures import FIXTURE_BUILDERS, GENERATED_ROOT, regenerate_all

_TESTS = os.path.dirname(os.path.abspath(__file__))


def _compare_trees(left, right):
    diff = filecmp.dircmp(left, right)
    if diff.left_only or diff.right_only or diff.diff_files or diff.funny_files:
        return False
    for sub in diff.subdirs.values():
        if sub.left_only or sub.right_only or sub.diff_files or sub.funny_files:
            return False
    return True


def test_generated_certification_fixtures_match_producer():
    scratch = tempfile.mkdtemp(prefix="rc-fixture-drift-")
    try:
        regenerate_all(scratch)
        if not _compare_trees(GENERATED_ROOT, scratch):
            missing = sorted(set(os.listdir(scratch)) - set(os.listdir(GENERATED_ROOT)))
            extra = sorted(set(os.listdir(GENERATED_ROOT)) - set(os.listdir(scratch)))
            raise AssertionError(
                "generated certification fixtures drifted from producer; "
                "regenerate with: cd plugins/superheroes/lib && "
                "/usr/bin/python3 -B tests/generate_round_certification_fixtures.py "
                "(missing in checked-in tree: %s; extra: %s)"
                % (missing, extra))
        assert len(FIXTURE_BUILDERS) == len(
            [name for name in os.listdir(GENERATED_ROOT)
             if os.path.isdir(os.path.join(GENERATED_ROOT, name))])
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
