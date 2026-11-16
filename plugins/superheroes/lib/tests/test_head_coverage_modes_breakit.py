"""Regression: identical blob contents cannot certify an executable-bit change."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
for _path in (_HERE, os.path.dirname(_HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import head_coverage as HC  # noqa: E402
import test_returning_review_c1l11 as TR  # noqa: E402
from test_returning_review_c1l11 import _isolated_git  # noqa: E402,F401  (autouse: no global git config)


@pytest.mark.parametrize(
    "reviewed_executable", [False, True], ids=["make-executable", "remove-executable"]
)
def test_mode_changes_are_not_proven_from_identical_blobs(tmp_path, reviewed_executable):
    # axis: either executable-bit change after review requires review despite identical blob contents.
    repo = TR.Repo(tmp_path)
    path = "src/shared.py"
    if reviewed_executable:
        repo.git("update-index", "--chmod=+x", path)
        # the working-tree file carries the bit too, so a later `git add -A` keeps the mode
        os.chmod(os.path.join(repo.root, path), 0o755)
        repo.git("commit", "-q", "-m", "make the reviewed file executable")
    base, reviewed, record = TR.returning(repo)

    chmod = "--chmod=-x" if reviewed_executable else "--chmod=+x"
    repo.git("update-index", chmod, path)
    os.chmod(os.path.join(repo.root, path), 0o644 if reviewed_executable else 0o755)
    repo.git("commit", "-q", "-m", "change only the executable bit")
    head = repo.git("rev-parse", "HEAD")

    assert repo.git("rev-parse", f"{reviewed}:{path}") == repo.git("rev-parse", f"{head}:{path}")
    old_mode = repo.git("ls-tree", reviewed, "--", path).split()[0]
    new_mode = repo.git("ls-tree", head, "--", path).split()[0]
    expected = ("100755", "100644") if reviewed_executable else ("100644", "100755")
    assert (old_mode, new_mode) == expected

    got = HC.check(repo.root, base, record, head)
    assert got["answer"] == "needs-review", got
    assert got["files"] == [path], got
    assert got["reconstructed"] == [], got
