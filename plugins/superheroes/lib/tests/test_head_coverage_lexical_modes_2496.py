# plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py
"""Issue 2543 review round 1: the head-coverage check reads a file's mode, and reads a Python comment by its tokens.

M1  an executable-bit change after review, in either direction, is never reconstructed: it reads needs-review;
M2  a copy proof whose file changed its mode after review proves nothing;
L1  a comment-looking line inside a Python triple-quoted string is data: changing it reads needs-review;
L2  a real Python comment change still reads judgement;
L3  a comment in a language with no lexer here (YAML) reads needs-review.

Bite-proof record: i2496_wo_a_head_coverage (E-mode, E-lex)
"""
import hashlib
import os
import stat
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import head_coverage as HC  # noqa: E402
import test_returning_review_c1l11 as TR  # noqa: E402
from test_returning_review_c1l11 import _isolated_git  # noqa: E402,F401  (autouse: no global git config)

SHARED = "src/shared.py"


def _set_executable(repo, rel, on):
    path = os.path.join(repo.root, rel)
    mode = os.stat(path).st_mode
    os.chmod(path, mode | stat.S_IXUSR if on else mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def _tree_mode(repo, rev, rel):
    return repo.git("ls-tree", rev, "--", rel).split()[0]


@pytest.mark.parametrize("reviewed_executable", [False, True], ids=["make-executable", "remove-executable"])
def test_an_executable_bit_change_after_review_reads_needs_review(tmp_path, reviewed_executable):
    # axis: a file whose mode differs between X and the head is never reconstructed — see bite-proof record i2496_wo_a_head_coverage (E-mode)
    repo = TR.Repo(tmp_path)
    if reviewed_executable:
        _set_executable(repo, SHARED, True)
        repo.commit("make the shared file executable")
    base, reviewed, earlier = TR.returning(repo)
    _set_executable(repo, SHARED, not reviewed_executable)
    head = repo.commit("change only the executable bit")
    assert repo.git("rev-parse", "%s:%s" % (reviewed, SHARED)) == repo.git("rev-parse", "%s:%s" % (head, SHARED))
    assert _tree_mode(repo, reviewed, SHARED) != _tree_mode(repo, head, SHARED)
    got = HC.check(repo.root, base, earlier, head)
    assert got["answer"] == "needs-review", got
    assert got["files"] == [SHARED] and got["reconstructed"] == [], got


def test_a_copy_proof_for_a_file_whose_mode_changed_proves_nothing(tmp_path):
    # axis: a copy proves bytes only, so a copied file whose mode changed after review stays changed
    repo = TR.Repo(tmp_path)
    copied = "vendor/tool.py"
    text = "value = 1\n"
    base, reviewed, earlier = TR.returning(repo, first={"src/app.py": TR.numbered("app", 10), copied: text})
    _set_executable(repo, copied, True)
    head = repo.commit("make the copied file executable")
    proof = [{"file": copied, "source": "upstream/tool.py", "sha256": hashlib.sha256(text.encode()).hexdigest()}]
    got = HC.check(repo.root, base, earlier, head, proof=proof)
    assert got["answer"] == "needs-review" and got["copies"] == [] and copied in got["files"], got


def test_a_comment_looking_line_inside_a_python_string_is_data(tmp_path):
    # axis: a comment-looking line counts as a comment only where the tokenizer reads it as one — see bite-proof record i2496_wo_a_head_coverage (E-lex)
    repo = TR.Repo(tmp_path)
    app = "src/config.py"
    base, reviewed, earlier = TR.returning(repo, first={app: 'CONFIG = """\n# old\n"""\n'})
    repo.write(app, 'CONFIG = """\n# new\n"""\n')
    repo.commit("change the string's interior line")
    got = HC.check(repo.root, base, earlier, repo.git("rev-parse", "HEAD"))
    assert got["answer"] == "needs-review" and got["files"] == [app] and got["hunks"] == [], got


def test_a_blank_line_inside_a_python_string_is_data(tmp_path):
    repo = TR.Repo(tmp_path)
    app = "src/config.py"
    base, reviewed, earlier = TR.returning(repo, first={app: 'CONFIG = """\nx\n"""\n'})
    repo.write(app, 'CONFIG = """\nx\n\n"""\n')
    repo.commit("add a blank line inside the string")
    got = HC.check(repo.root, base, earlier, repo.git("rev-parse", "HEAD"))
    assert got["answer"] == "needs-review", got


def test_a_real_python_comment_change_still_reads_judgement(tmp_path):
    repo = TR.Repo(tmp_path)
    app = "src/config.py"
    base, reviewed, earlier = TR.returning(repo, first={app: 'CONFIG = """\n# old\n"""\n# a note\nX = 1\n'})
    repo.write(app, 'CONFIG = """\n# old\n"""\n# a better note\n\nX = 1\n')
    repo.commit("reword the note")
    got = HC.check(repo.root, base, earlier, repo.git("rev-parse", "HEAD"))
    assert got["answer"] == "judgement" and got["files"] == [app], got


def test_a_yaml_comment_change_reads_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    ci = "config/settings.yml"
    base, reviewed, earlier = TR.returning(repo, first={"src/app.py": TR.numbered("app", 10), ci: "key: 1\n# note\n"})
    repo.write(ci, "key: 1\n# a better note\n")
    repo.commit("reword the yaml note")
    got = HC.check(repo.root, base, earlier, repo.git("rev-parse", "HEAD"))
    assert got["answer"] == "needs-review" and got["files"] == [ci], got
