"""#2341: a fix whose whole delta is doctrine prose clears its audit on a `review-guarded` answer.

Pins, each at the place the rule is enforced:

T1  a prose-only delta (Markdown outside the test, eval and fixture trees) clears on `testWouldFail: review-guarded`
    and is listed in `reviewGuarded`;
T2  a delta that also touches code folds `not-discharged`, listed in `reviewGuardRefused`, naming the file;
T3  a Markdown file under a test tree is not prose;
T4  a Markdown file under an eval grader tree or a fixtures tree is not prose;
T5  an absent or empty delta is never prose-only;
T6  `review-guarded` is a fault on `right` and on `brokeNothing`;
T7  a `yes` answer clears whatever the delta touches (the new arm never reads a `yes`);
T8  the strict-mode schema lists the answer for `testWouldFail` only;
T9  the rendered fix-auditor order names the answer token (structure only; no sentence is pinned);
T10 an id later refused in the same pass is never listed in `reviewGuarded`;
T11 a header for a Markdown path that contains a space is read, so the fix clears;
T12 a header that is not `a/<f> b/<f>` for one non-empty `<f>` still refuses as no readable delta;
T13 a fix that renames a code file (and edits it) while editing a Markdown file is refused, the driver's own
    builder naming the renamed file under a `diff --git` line;
T14 positive control: a fix that edits only wording in a Markdown file clears, through the same builder;
T15 a fix that adds a code file whose name git quotes, plus a Markdown edit, is refused;
T16 a left-out proven copy with a quoted name stays out of the delta;
T17 a left-out copy never hides a changed file whose name differs from it in one invalid UTF-8 byte.

Bite-proof record: audit_review_guarded_2341
"""
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audits  # noqa: E402
import engine_result_channel as ERC  # noqa: E402
import round_driver as RD  # noqa: E402
import size_count  # noqa: E402
import test_round_orders as TRO  # noqa: E402

RUBRIC_MD = "plugins/superheroes/rubric/some-doctrine-2341.md"
ROOT_MD = "CLAUDE.md"
LIB_PY = "plugins/superheroes/lib/some_module_2341.py"
TEST_TREE_MD = "plugins/superheroes/lib/tests/bite_proofs/some_record_2341.md"
GRADER_MD = "plugins/superheroes/evals/s9-some-scenario/graders/some-grader.md"
FIXTURE_MD = "plugins/superheroes/lib/fixtures/orders/some-fixture-2341.md"


def _delta(*files):
    """A driver-built `fixerDelta`: per file one `diff --git a/<f> b/<f>` header, then that file's lines."""
    out = []
    for name in files:
        out.append("diff --git a/%s b/%s" % (name, name))
        out.extend(["--- a/%s" % name, "+++ b/%s" % name, "@@ -1 +1 @@", "-old", "+new"])
    return out


def _checks(**answers):
    return {name: {"answer": answers.get(name, "yes"), "why": "checked: %s" % name}
            for name in audits.CHECK_NAMES}


def _guarded(**extra):
    return dict({"id": "t0", "ruling": "discharged", "reason": "the fix resolves it",
                 "checks": _checks(testWouldFail=audits.REVIEW_GUARDED)}, **extra)


def _target(*files, **extra):
    target = {"id": "t0", "title": "T", "file": "f.py", "line": 1, "auditorVendor": "codex"}
    if files:
        target["fixerDelta"] = _delta(*files)
    target.update(extra)
    return target


def _fold(results, target):
    return audits.apply_audit_results([target], results, collection_manifest={"t0": "codex"})


def _only(outcome):
    (entry,) = outcome["audits"]
    return entry


def _refused(outcome):
    entry = _only(outcome)
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
    assert outcome["reviewGuardRefused"] == ["t0"] and outcome["reviewGuarded"] == []
    assert entry["ruling"] == "not-discharged" and "reviewGuarded" not in entry
    assert entry["reason"].startswith(
        "audit check failed: testWouldFail: review-guarded clears only a fix whose whole delta is prose; "
        "this fix's delta touches "), entry["reason"]
    return entry["reason"]


# --- T1 -----------------------------------------------------------------------------------------------------------

def test_t1_a_prose_only_delta_clears_on_a_review_guarded_answer():
    # axis: G1 — the clear arm for a prose-only `review-guarded` result
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    outcome = _fold([_guarded()], _target(RUBRIC_MD, ROOT_MD))
    entry = _only(outcome)
    assert outcome["discharged"] == ["t0"] and outcome["notDischarged"] == []
    assert outcome["reviewGuarded"] == ["t0"] and outcome["reviewGuardRefused"] == []
    assert entry["ruling"] == "discharged"
    assert entry["reviewGuarded"] == {"answer": audits.REVIEW_GUARDED, "why": "checked: testWouldFail"}


def test_t1_a_new_issue_ruling_clears_on_the_same_answer_and_keeps_its_new_issue():
    result = _guarded(ruling="discharged-but-new-issue", newIssues=[{"title": "leak", "file": "f.md", "line": 2}])
    outcome = _fold([result], _target(RUBRIC_MD))
    assert outcome["discharged"] == ["t0"] and outcome["reviewGuarded"] == ["t0"]
    assert _only(outcome)["ruling"] == "discharged-but-new-issue"
    assert [i["title"] for i in outcome["newIssues"]] == ["leak"]


def test_t1_the_why_is_stripped_on_the_entry():
    result = _guarded()
    result["checks"]["testWouldFail"]["why"] = "  only prose changed  "
    outcome = _fold([result], _target(RUBRIC_MD))
    assert _only(outcome)["reviewGuarded"]["why"] == "only prose changed"


def test_t1_a_not_discharged_ruling_with_the_answer_is_accepted_as_is():
    outcome = _fold([_guarded(ruling="not-discharged", reason="still wrong")], _target(LIB_PY))
    assert audits.audit_checks_fault(_guarded(ruling="not-discharged")) is None
    assert outcome["notDischarged"] == ["t0"] and outcome["malformed"] == []
    assert outcome["reviewGuardRefused"] == [] and outcome["reviewGuarded"] == []
    assert _only(outcome)["reason"] == "still wrong"


# --- T2 -----------------------------------------------------------------------------------------------------------

def test_t2_a_delta_that_touches_code_is_refused_naming_the_file():
    # axis: G2 — the `.md` extension test
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    reason = _refused(_fold([_guarded()], _target(RUBRIC_MD, LIB_PY)))
    assert LIB_PY in reason and RUBRIC_MD not in reason


def test_t2_a_refused_new_issue_ruling_keeps_its_new_issue():
    result = _guarded(ruling="discharged-but-new-issue", newIssues=[{"title": "leak"}])
    outcome = _fold([result], _target(LIB_PY))
    _refused(outcome)
    assert [i["title"] for i in outcome["newIssues"]] == ["leak"]


# --- T3 -----------------------------------------------------------------------------------------------------------

def test_t3_a_markdown_file_under_a_test_tree_is_not_prose():
    # axis: G3 — the test-tree test
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    reason = _refused(_fold([_guarded()], _target(TEST_TREE_MD)))
    assert TEST_TREE_MD in reason


# --- T4 -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", [GRADER_MD, FIXTURE_MD], ids=["eval-grader", "fixtures"])
def test_t4_a_markdown_file_under_a_non_prose_tree_is_not_prose(path):
    # axis: G4 — the non-prose component set
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    assert path.endswith(".md") and not size_count.is_test_path(path)
    reason = _refused(_fold([_guarded()], _target(path)))
    assert path in reason


def test_t4_the_component_match_ignores_case():
    assert audits.prose_only_delta(_target("plugins/superheroes/Evals/x/Graders/g.MD")) == (
        False, ["plugins/superheroes/Evals/x/Graders/g.MD"])


# --- T5 -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("target", [
    pytest.param(_target(), id="no-fixerDelta-key"),
    pytest.param(_target(fixerDelta=[]), id="empty-list"),
    pytest.param(_target(fixerDelta=["+ a line with no header"]), id="no-header-lines"),
])
def test_t5_an_absent_or_empty_delta_is_refused_as_no_recorded_delta(target):
    # axis: G6 — the empty/absent delta refusal
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    reason = _refused(_fold([_guarded()], target))
    assert reason.endswith("this fix's delta touches no recorded delta")


@pytest.mark.parametrize("target", [
    pytest.param("not a target", id="target-not-a-dict"),
    pytest.param(None, id="target-none"),
    pytest.param(_target(fixerDelta="diff --git a/x.md b/x.md"), id="delta-not-a-list"),
    pytest.param(_target(fixerDelta=["diff --git a/x.md b/y.md"]), id="paths-differ"),
    pytest.param(_target(fixerDelta=["diff --git x.md x.md"]), id="no-a-b-prefix"),
    pytest.param(_target(fixerDelta=["diff --git a/x.md b/x.md extra"]), id="extra-token"),
    pytest.param(_target(fixerDelta=["diff --git a/ b/"]), id="empty-path"),
    pytest.param(_target(fixerDelta=_delta(RUBRIC_MD) + ["diff --git a/x.md b/z.md"]), id="one-bad-header"),
])
def test_t5_an_unreadable_delta_is_never_prose_only(target):
    assert audits.prose_only_delta(target) == (False, [])


# --- T6 -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["right", "brokeNothing"])
def test_t6_review_guarded_is_a_fault_on_any_check_but_test_would_fail(name):
    # axis: G5 — the per-check answer set
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    result = _guarded(checks=_checks(**{name: audits.REVIEW_GUARDED}))
    fault = audits.audit_checks_fault(result)
    assert fault is not None and "checks.%s" % name in fault and audits.REVIEW_GUARDED in fault, fault
    outcome = _fold([result], _target(RUBRIC_MD))
    assert outcome["malformed"] == ["t0"] and outcome["notDischarged"] == ["t0"]
    assert outcome["discharged"] == [] and outcome["reviewGuarded"] == []
    assert _only(outcome)["reason"] == "audit refused: %s" % fault


def test_t6_each_check_has_its_own_answer_set():
    assert audits.check_answers("right") == audits.CHECK_ANSWERS
    assert audits.check_answers("brokeNothing") == audits.CHECK_ANSWERS
    assert audits.check_answers("testWouldFail") == audits.CHECK_ANSWERS + (
        audits.REVIEW_GUARDED, audits.WORTHLESS_TEST_REMOVED)
    assert audits.audit_checks_fault(_guarded()) is None


def test_t6_a_no_on_another_check_wins_over_review_guarded():
    outcome = _fold([_guarded(checks=_checks(right="no", testWouldFail=audits.REVIEW_GUARDED))],
                    _target(RUBRIC_MD))
    assert outcome["notDischarged"] == ["t0"] and outcome["reviewGuarded"] == []
    assert outcome["reviewGuardRefused"] == []
    assert _only(outcome)["reason"] == "audit check failed: right: checked: right"


# --- T7 -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("files", [(RUBRIC_MD,), (LIB_PY,), (TEST_TREE_MD,), ()],
                         ids=["prose-only", "code", "test-tree", "no-delta"])
def test_t7_a_yes_answer_clears_whatever_the_delta_touches(files):
    result = _guarded(checks=_checks())
    outcome = _fold([result], _target(*files))
    assert outcome["discharged"] == ["t0"] and outcome["notDischarged"] == []
    assert outcome["reviewGuarded"] == [] and outcome["reviewGuardRefused"] == []
    assert "reviewGuarded" not in _only(outcome)


# --- T8 -----------------------------------------------------------------------------------------------------------

def test_t8_the_strict_schema_lists_the_answer_for_test_would_fail_only():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, expected_result_kind="ruling")
    checks = schema["properties"]["result"]["properties"]["checks"]["properties"]
    for name in audits.CHECK_NAMES:
        assert checks[name]["properties"]["answer"]["enum"] == list(audits.check_answers(name))
    assert audits.REVIEW_GUARDED in checks["testWouldFail"]["properties"]["answer"]["enum"]
    assert audits.REVIEW_GUARDED not in checks["right"]["properties"]["answer"]["enum"]
    assert audits.REVIEW_GUARDED not in checks["brokeNothing"]["properties"]["answer"]["enum"]


# --- T9 -----------------------------------------------------------------------------------------------------------

def test_t9_the_rendered_fix_auditor_order_names_the_answer_token():
    rendered = TRO._render_golden("dispatch-audits")
    assert "`%s`" % audits.REVIEW_GUARDED in rendered


# --- T10 ----------------------------------------------------------------------------------------------------------

def test_t10_an_id_refused_later_in_the_same_pass_is_not_listed_as_review_guarded():
    # axis: G7 — the `reviewGuarded` listing only on a final clear
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    outcome = _fold([_guarded(unnamedChange="also reworks the retry policy")], _target(RUBRIC_MD))
    entry = _only(outcome)
    assert outcome["unnamedChange"] == ["t0"] and outcome["notDischarged"] == ["t0"]
    assert outcome["discharged"] == [] and outcome["reviewGuarded"] == []
    assert entry["ruling"] == "not-discharged" and "reviewGuarded" not in entry


def test_t10_a_malformed_field_after_the_gate_leaves_no_listing():
    outcome = _fold([_guarded(unnamedChange=7)], _target(RUBRIC_MD))
    assert outcome["malformed"] == ["t0"] and outcome["reviewGuarded"] == []
    assert "reviewGuarded" not in _only(outcome)


# --- T11 ----------------------------------------------------------------------------------------------------------

SPACED_MD = "plugins/superheroes/rubric/Design Notes 2341.md"


def test_t11_a_header_for_a_markdown_path_with_a_space_is_read_and_clears():
    # axis: G8 — the space-preserving header read
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    target = _target(SPACED_MD)
    assert target["fixerDelta"][0] == "diff --git a/%s b/%s" % (SPACED_MD, SPACED_MD)
    outcome = _fold([_guarded()], target)
    entry = _only(outcome)
    assert outcome["discharged"] == ["t0"] and outcome["notDischarged"] == []
    assert outcome["reviewGuarded"] == ["t0"]
    assert entry["ruling"] == "discharged" and entry["reviewGuarded"] is not None


# --- T12 ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("header", [
    pytest.param("diff --git a/my doc.md b/my dox.md", id="different-paths-both-with-spaces"),
    pytest.param("diff --git a/my doc.md b/my_doc.md", id="space-on-one-side-only"),
    pytest.param("diff --git a/my doc.md c/my doc.md", id="b-separator-missing"),
    pytest.param("diff --git a/ b/", id="empty-path"),
])
def test_t12_a_header_that_is_not_one_path_twice_refuses_as_no_readable_delta(header):
    # axis: G9 — the whole-string equality check
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    target = _target(fixerDelta=[header])
    assert audits.prose_only_delta(target) == (False, [])
    reason = _refused(_fold([_guarded()], target))
    assert reason.endswith("this fix's delta touches no recorded delta")


# --- T13-T15: the delta the driver's own builder writes from real `git diff -M` text ------------------------------

# The throwaway fixture repo's commits carry an inline identity; nothing is signed.
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
MOD = "pkg/module.py"
RENAMED = "pkg/module_renamed.py"
GUIDE = "docs/guide.md"
OTHER = "other.txt"
MOD_BODY = "".join("def f%d():\n    return %d\n" % (n, n) for n in range(6))
GUIDE_BODY = "# Guide\n\nUse the tool carefully.\n"


@pytest.fixture(autouse=True)
def _pinned_git_config(monkeypatch, tmp_path):
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _write(repo, name, body):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _commit(repo, message, stage=True):
    if stage:
        _git(repo, "add", "-A")
    _git(repo, *(_ID + ["commit", "-q", "-m", message]))


def _index_only_files(repo, names):
    """Put `names` (raw bytes, possibly not valid UTF-8) into git's index as blobs, never on the filesystem
    (macOS APFS refuses such names)."""
    entries = b""
    for name in names:
        hashed = subprocess.run(["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
                                input=b"def f():\n    return 1\n", capture_output=True)
        assert hashed.returncode == 0, hashed.stderr
        entries += b"100644 " + hashed.stdout.strip() + b"\t" + name + b"\n"
    updated = subprocess.run(["git", "-C", str(repo), "update-index", "--add", "--index-info"],
                             input=entries, capture_output=True)
    assert updated.returncode == 0, updated.stderr


def _built_delta(tmp_path, fix, stage=True):
    """Commit `base` (MOD, GUIDE, OTHER), `reviewed` (the PR's change: OTHER only) and `fixed` (what `fix(repo)`
    does on top of it); return `(reviewed_diff, head_diff, delta)` with the delta built by the driver.
    `stage=False` leaves staging to `fix` (no `git add -A` before the `fixed` commit)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "base")
    _write(repo, MOD, MOD_BODY)
    _write(repo, GUIDE, GUIDE_BODY)
    _write(repo, OTHER, "one\n")
    _commit(repo, "base")
    _git(repo, "checkout", "-q", "-b", "reviewed")
    _write(repo, OTHER, "one\ntwo\n")
    _commit(repo, "reviewed")
    _git(repo, "checkout", "-q", "-b", "fixed")
    fix(repo)
    _commit(repo, "fixed", stage=stage)
    diffs = [_git(repo, "diff", "-M", "--src-prefix=a/", "--dst-prefix=b/", "base...%s" % tip)
             for tip in ("reviewed", "fixed")]
    return diffs[0], diffs[1], RD._attempt_fixer_delta(diffs[0], diffs[1])


def _reword_guide(repo):
    _write(repo, GUIDE, "# Guide\n\nUse the tool with care.\n")


def _headers(delta):
    return [ln for ln in delta if ln.startswith("diff --git ")]


def test_t13_a_fix_that_renames_a_code_file_is_refused_though_it_also_edits_a_guide(tmp_path):
    # axis: G10 — a two-path (rename) section is emitted under its own header
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    def fix(repo):
        _git(repo, "mv", MOD, RENAMED)
        _write(repo, RENAMED, MOD_BODY.replace("return 3", "return 33"))
        _reword_guide(repo)

    reviewed_diff, head_diff, delta = _built_delta(tmp_path, fix)
    assert "rename from %s" % MOD in head_diff and "rename to %s" % RENAMED in head_diff
    renamed = [h for h in _headers(delta) if RENAMED in h]
    assert renamed == ["diff --git a/%s b/%s" % (MOD, RENAMED)]
    assert "diff --git a/%s b/%s" % (GUIDE, GUIDE) in delta
    target = _target(fixerDelta=delta)
    assert audits.prose_only_delta(target) == (False, [])
    outcome = _fold([_guarded()], target)
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
    assert outcome["reviewGuardRefused"] == ["t0"] and outcome["reviewGuarded"] == []
    assert _only(outcome)["ruling"] == "not-discharged"


def test_t14_a_fix_that_only_rewords_a_guide_clears_through_the_same_builder(tmp_path):
    # positive control for T13 and T15: the same fixture, a prose-only fix
    _, _, delta = _built_delta(tmp_path, _reword_guide)
    assert _headers(delta) == ["diff --git a/%s b/%s" % (GUIDE, GUIDE)]
    outcome = _fold([_guarded()], _target(fixerDelta=delta))
    assert outcome["discharged"] == ["t0"] and outcome["notDischarged"] == []
    assert outcome["reviewGuarded"] == ["t0"] and outcome["reviewGuardRefused"] == []


def test_t15_a_fix_that_adds_a_code_file_with_a_quoted_name_is_refused(tmp_path):
    # axis: G11 — a header that does not read `a/<f> b/<f>` (git-quoted path) is emitted under its own header
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    quoted = "pkg/café.py"

    def fix(repo):
        _write(repo, quoted, "def cafe():\n    return 1\n")
        _reword_guide(repo)

    _, head_diff, delta = _built_delta(tmp_path, fix)
    observed = [h for h in _headers(head_diff.splitlines()) if "caf" in h]
    assert len(observed) == 1, head_diff
    assert '"' in observed[0], observed  # git quotes the non-ASCII name under the default core.quotePath
    assert observed[0] in delta
    assert "diff --git a/%s b/%s" % (GUIDE, GUIDE) in delta
    target = _target(fixerDelta=delta)
    assert audits.prose_only_delta(target) == (False, [])
    outcome = _fold([_guarded()], target)
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
    assert outcome["reviewGuardRefused"] == ["t0"] and outcome["reviewGuarded"] == []


def test_t13_edges_a_pure_rename_a_left_alone_rename_a_left_out_header_and_empty_diffs(tmp_path):
    def pure_rename(repo):
        _git(repo, "mv", MOD, RENAMED)

    reviewed_diff, head_diff, delta = _built_delta(tmp_path, pure_rename)
    assert "similarity index 100%" in head_diff and "@@" not in head_diff.split("diff --git")[-1]
    assert _headers(delta) == ["diff --git a/%s b/%s" % (MOD, RENAMED)]
    assert RD._attempt_fixer_delta(reviewed_diff, head_diff, leave_out=(RENAMED,)) == []
    assert RD._attempt_fixer_delta(head_diff, head_diff) == []
    assert RD._attempt_fixer_delta(None, None) == []
    assert RD._attempt_fixer_delta("", "") == []
    assert RD._attempt_fixer_delta(head_diff, "") != []


def test_t16_a_left_out_proven_copy_with_a_quoted_name_stays_out_of_the_delta(tmp_path):
    # axis: G12 — `leave_out` is honoured for a git-quoted header, so a proven copy never enters the delta
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    quoted = "pkg/café.py"

    def fix(repo):
        _write(repo, quoted, "def cafe():\n    return 1\n")
        _reword_guide(repo)

    reviewed_diff, head_diff, _ = _built_delta(tmp_path, fix)
    delta = RD._attempt_fixer_delta(reviewed_diff, head_diff, leave_out=(quoted,))
    assert _headers(delta) == ["diff --git a/%s b/%s" % (GUIDE, GUIDE)]
    outcome = _fold([_guarded()], _target(fixerDelta=delta))
    assert outcome["discharged"] == ["t0"] and outcome["reviewGuarded"] == ["t0"]


def test_t17_a_left_out_copy_never_hides_a_changed_file_whose_name_differs_in_one_invalid_byte(tmp_path):
    # axis: G13 — `leave_out` compares the exact destination, so two names that differ in one invalid byte stay distinct
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_review_guarded_2341.md
    left_out_bytes, changed_bytes = b"pkg/bad\xff.py", b"pkg/bad\xfe.py"
    left_out, changed = os.fsdecode(left_out_bytes), os.fsdecode(changed_bytes)

    def fix(repo):
        # the two names exist only as git index entries: filesystems such as macOS APFS refuse them on disk
        _index_only_files(repo, (left_out_bytes, changed_bytes))
        _reword_guide(repo)
        _git(repo, "add", GUIDE)

    reviewed_diff, head_diff, _ = _built_delta(tmp_path, fix, stage=False)
    header_left_out = [h for h in _headers(head_diff.splitlines()) if "\\377" in h]
    header_changed = [h for h in _headers(head_diff.splitlines()) if "\\376" in h]
    assert len(header_left_out) == 1 and len(header_changed) == 1, head_diff
    delta = RD._attempt_fixer_delta(reviewed_diff, head_diff, leave_out=(left_out,))
    assert header_changed[0] in delta
    assert header_left_out[0] not in delta
    assert "diff --git a/%s b/%s" % (GUIDE, GUIDE) in delta
    assert left_out != changed
    target = _target(fixerDelta=delta)
    assert audits.prose_only_delta(target) == (False, [])
    outcome = _fold([_guarded()], target)
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
    assert outcome["reviewGuardRefused"] == ["t0"] and outcome["reviewGuarded"] == []
