# plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py
"""Issue 2543 review round 1: the head-coverage check reads a file's mode, and reads a Python comment by its tokens.

M1  an executable-bit change after review, in either direction, is never reconstructed: it reads needs-review;
M2  a copy proof whose file changed its mode after review proves nothing;
L1  a comment-looking line inside a Python triple-quoted string is data: changing it reads needs-review;
L2  a real Python comment change still reads judgement;
L3  a comment in a language with no lexer here (YAML) reads needs-review;
M3  a mode read git failed is not an absent file: a copy proof never drops a file whose mode could not be read;
L4  every line inside an f-string, debug or not, is significant: a blank line added inside one reads needs-review;
R1  a rename after review, even to a prose name, reads needs-review; a rename the review already read does not block
    a later prose edit;
R2  one rule for rename sources: a source path is read exactly when a changed file names it and no copy proof settled
    it, so a copy proof on a rename's destination proves, and a move that deletes code is never hidden by one.

Bite-proof record: i2496_wo_a_head_coverage (E-mode, E-lex, E-mode-read, E-fstring, E-rename, E-rename-one-rule)
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
import returning_review as R  # noqa: E402
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


def test_a_failed_mode_read_keeps_a_copied_file_changed(tmp_path):
    # axis: a mode git could not read is not an absent file, so a copy proof never drops a file whose mode is unknown — see bite-proof record i2496_wo_a_head_coverage (E-mode-read)
    repo = TR.Repo(tmp_path)
    copied = "vendor/lib.py"
    text = TR.numbered("vendored", 40)
    base, reviewed, earlier = TR.returning(repo)
    repo.write(copied, text)
    head = repo.commit("vendor a copy")
    proof = [{"file": copied, "source": "upstream/lib.py", "sha256": hashlib.sha256(text.encode()).hexdigest()}]
    # the copy proof proves the file when git reads every mode
    proven = HC.check(repo.root, base, earlier, head, proof=proof)
    assert proven["answer"] == "proven" and [c["file"] for c in proven["copies"]] == [copied], proven
    real = R.production_git(repo.root)
    calls = []

    def no_ls_tree(argv):
        if argv[0] == "ls-tree":
            calls.append(argv)
            return 128, ""
        return real(argv)

    got = HC.check(repo.root, base, earlier, head, proof=proof, git=no_ls_tree)
    assert calls, "the check never read a mode through the seam"
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


def test_a_blank_line_inside_a_debug_fstring_changes_the_value_and_reads_needs_review(tmp_path):
    # axis: every line inside an f-string is significant, since a debug f-string's `=` keeps the text before it — see bite-proof record i2496_wo_a_head_coverage (E-fstring)
    repo = TR.Repo(tmp_path)
    app = "src/config.py"
    base, reviewed, earlier = TR.returning(repo, first={app: 'CONFIG = f"""{1\n=}"""\n'})
    repo.write(app, 'CONFIG = f"""{1\n\n=}"""\n')
    repo.commit("add a blank line inside the debug f-string")
    got = HC.check(repo.root, base, earlier, repo.git("rev-parse", "HEAD"))
    assert got["answer"] == "needs-review" and got["files"] == [app] and got["hunks"] == [], got


def test_a_blank_line_inside_a_plain_fstring_braces_reads_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    app = "src/config.py"
    base, reviewed, earlier = TR.returning(repo, first={app: 'CONFIG = f"""{1\n+2}"""\n'})
    repo.write(app, 'CONFIG = f"""{1\n\n+2}"""\n')
    repo.commit("add a blank line inside the braces of a plain f-string")
    got = HC.check(repo.root, base, earlier, repo.git("rev-parse", "HEAD"))
    assert got["answer"] == "needs-review" and got["files"] == [app] and got["hunks"] == [], got


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


@pytest.mark.parametrize("dest", ["shared.md", "docs/shared.txt"])
def test_a_rename_after_review_to_a_prose_name_reads_needs_review(tmp_path, dest):
    # axis: a renamed file is never reconstructed, copy-proven or read as an added prose file — see bite-proof record i2496_wo_a_head_coverage (E-rename)
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    os.makedirs(os.path.join(repo.root, os.path.dirname(dest) or "."), exist_ok=True)
    repo.git("mv", SHARED, dest)
    head = repo.commit("move the shared module to a prose name")
    got = HC.check(repo.root, base, earlier, head)
    assert got["answer"] == "needs-review" and dest in got["files"] and got["reconstructed"] == [], got


def test_a_copy_proven_restore_of_a_reviewed_renames_source_does_not_block_a_comment_edit(tmp_path):
    # axis: only a move after the review brings its source paths into the qualification diff, and never a path a copy proof settled
    repo = TR.Repo(tmp_path)
    base = repo.git("rev-parse", "main")
    app = "src/app.py"
    repo.git("mv", SHARED, app)
    reviewed = repo.commit("first leg: the reviewed rename")
    earlier = TR.earlier_record(reviewed)
    restored = "restored = 1\n"
    repo.write(SHARED, restored)
    repo.write(app, repo.read(app) + "# a note\n")
    head = repo.commit("restore the old path from upstream, and a comment")
    proof = [{"file": SHARED, "source": "upstream/shared.py", "sha256": hashlib.sha256(restored.encode()).hexdigest()}]
    got = HC.check(repo.root, base, earlier, head, proof=proof)
    assert got["answer"] == "judgement" and got["files"] == [app], got
    assert [c["file"] for c in got["copies"]] == [SHARED], got


def test_a_move_after_review_into_a_reviewed_prose_path_still_reads_the_source_deletion(tmp_path):
    # axis: every remaining file brings its rename sources in, so overwriting a reviewed prose file by a move still shows the code it deletes
    repo = TR.Repo(tmp_path)
    doc = "docs/shared.md"
    base, reviewed, earlier = TR.returning(repo, first={"src/app.py": TR.numbered("app", 10), doc: "notes\n"})
    repo.git("mv", "-f", SHARED, doc)
    head = repo.commit("move the shared module over the reviewed notes")
    got = HC.check(repo.root, base, earlier, head)
    assert got["answer"] == "needs-review", got


def _reviewed_rename_then_copy_proven_update(tmp_path):
    """A reviewed rename of the shared module to ``src/core.py``, then an update of ``src/core.py`` at the head that a
    copy proof covers; returns ``(repo, base, earlier, head, proof)``."""
    repo = TR.Repo(tmp_path)
    core = "src/core.py"
    base = repo.git("rev-parse", "main")
    repo.git("mv", SHARED, core)
    reviewed = repo.commit("first leg: the reviewed rename")
    earlier = TR.earlier_record(reviewed)
    updated = repo.read(core) + "core_extra = 1\n"
    repo.write(core, updated)
    head = repo.commit("update the core module from upstream")
    proof = [{"file": core, "source": "upstream/core.py", "sha256": hashlib.sha256(updated.encode()).hexdigest()}]
    return repo, base, earlier, head, proof


def test_a_copy_proven_update_of_a_reviewed_renames_destination_reads_proven(tmp_path):
    # axis: a copy proof is judged on the file's own bytes and mode alone, so a rename the review already read never blocks it — see bite-proof record i2496_wo_a_head_coverage (E-rename-one-rule)
    repo, base, earlier, head, proof = _reviewed_rename_then_copy_proven_update(tmp_path)
    got = HC.check(repo.root, base, earlier, head, proof=proof)
    assert got["answer"] == "proven", got
    assert [c["file"] for c in got["copies"]] == ["src/core.py"] and got["files"] == [], got


def test_a_failed_read_of_the_outstanding_sources_reads_needs_review(tmp_path):
    # axis: a git failure reading the outstanding rename sources is a review owed, never a proven answer — see bite-proof record i2496_wo_a_head_coverage (E-rename-one-rule)
    repo, base, earlier, head, proof = _reviewed_rename_then_copy_proven_update(tmp_path)
    real = R.production_git(repo.root)
    calls = []

    def no_source_diff(argv):
        if argv[0] == "diff" and argv[-1] == SHARED:
            calls.append(argv)
            return 128, ""
        return real(argv)

    got = HC.check(repo.root, base, earlier, head, proof=proof, git=no_source_diff)
    assert calls, "the check never read the outstanding source through the seam"
    assert got["answer"] == "needs-review" and got["why"][0].startswith("diff-unreadable"), got
    assert [c["file"] for c in got["copies"]] == ["src/core.py"], got


def test_a_move_after_review_over_a_reviewed_prose_path_with_a_copy_proof_reads_the_source_deletion(tmp_path):
    # axis: a move that deletes code is never hidden by a copy proof on its destination — see bite-proof record i2496_wo_a_head_coverage (E-rename-one-rule)
    repo = TR.Repo(tmp_path)
    doc = "docs/shared.md"
    base, reviewed, earlier = TR.returning(repo, first={"src/app.py": TR.numbered("app", 10), doc: "notes\n"})
    repo.git("mv", "-f", SHARED, doc)
    head = repo.commit("move the shared module over the reviewed notes")
    proof = [{"file": doc, "source": "upstream/shared.md", "sha256": hashlib.sha256(repo.read(doc).encode()).hexdigest()}]
    got = HC.check(repo.root, base, earlier, head, proof=proof)
    assert got["answer"] == "needs-review", got


def test_a_move_over_a_reviewed_prose_path_that_a_copy_proof_settles_reads_the_source_deletion(tmp_path):
    # axis: a move that deletes code is never hidden by a copy proof on its destination, even a proof git re-validates — see bite-proof record i2496_wo_a_head_coverage (E-rename-one-rule)
    repo = TR.Repo(tmp_path)
    doc = "docs/shared.md"
    base, reviewed, earlier = TR.returning(repo, first={"src/app.py": TR.numbered("app", 10), doc: "notes\n"})
    repo.git("mv", "-f", SHARED, doc)
    # a pure move has no blob line in git's section, so a proof on it is dropped; an edit beside the move makes git show one
    repo.write(doc, repo.read(doc) + "more_notes = 1\n")
    head = repo.commit("move the shared module over the reviewed notes, with an edit")
    proof = [{"file": doc, "source": "upstream/shared.md", "sha256": hashlib.sha256(repo.read(doc).encode()).hexdigest()}]
    got = HC.check(repo.root, base, earlier, head, proof=proof)
    assert [c["file"] for c in got["copies"]] == [doc], "the proof must be one git re-validates: %r" % (got,)
    assert got["answer"] == "needs-review" and got["files"] == [], got


def test_a_judgement_that_rests_on_a_source_path_lists_that_paths_hunks(tmp_path):
    # axis: every section the judgement rests on is listed for the vet to read, a source path's included — see bite-proof record i2496_wo_a_head_coverage (E-hunks)
    repo = TR.Repo(tmp_path)
    doc = "docs/notes.md"
    base, reviewed, earlier = TR.returning(repo, first={"src/app.py": TR.numbered("app", 10), doc: "notes\n"})
    repo.git("mv", "-f", "README.md", doc)
    repo.write(doc, repo.read(doc) + "more notes\n")
    head = repo.commit("move the readme over the reviewed notes, with an edit")
    proof = [{"file": doc, "source": "upstream/notes.md", "sha256": hashlib.sha256(repo.read(doc).encode()).hexdigest()}]
    got = HC.check(repo.root, base, earlier, head, proof=proof)
    assert [c["file"] for c in got["copies"]] == [doc], got
    assert got["answer"] == "judgement", got
    assert "README.md" in got["files"] and any(h["file"] == "README.md" for h in got["hunks"]), got


def test_a_file_renamed_before_review_and_edited_in_prose_after_still_reads_judgement(tmp_path):
    repo = TR.Repo(tmp_path)
    base = repo.git("rev-parse", "main")
    os.makedirs(os.path.join(repo.root, "docs"), exist_ok=True)
    repo.git("mv", "README.md", "docs/README.md")
    repo.write("src/app.py", TR.numbered("app", 10))
    reviewed = repo.commit("first leg, with a move the review reads")
    earlier = TR.earlier_record(reviewed)
    repo.write("docs/README.md", "readme\nmore\n")
    head = repo.commit("docs")
    got = HC.check(repo.root, base, earlier, head)
    assert got["answer"] == "judgement" and got["files"] == ["docs/README.md"], got
