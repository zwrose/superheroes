"""Drift guard: generated certification fixtures must match the producer."""
import os
import shutil
import tempfile

from generate_round_certification_fixtures import FIXTURE_BUILDERS, GENERATED_ROOT, regenerate_all

_TESTS = os.path.dirname(os.path.abspath(__file__))


def _relative_file_map(root):
    rel_paths = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            abs_path = os.path.join(dirpath, filename)
            rel = os.path.relpath(abs_path, root)
            with open(abs_path, "rb") as fh:
                rel_paths[rel] = fh.read()
    return rel_paths


def _compare_trees(left, right):
    left_files = _relative_file_map(left)
    right_files = _relative_file_map(right)
    if set(left_files.keys()) != set(right_files.keys()):
        return False
    for rel in left_files:
        if left_files[rel] != right_files[rel]:
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
