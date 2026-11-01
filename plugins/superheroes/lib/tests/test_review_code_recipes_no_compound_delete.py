"""review-code's own recipes never put a delete inside a compound command (#2314, WO-E).

Three tests: a census over every .md under skills/review-code/, and two halt-behaviour tests that run the
rewritten SKILL.md recipes (the per-round diff write and the meta.json write) in a real bash against real
failures. Bite-proof record: bite_proofs/wo_e_2314_recipes.md.
"""
import json
import os
import re
import shlex
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REVIEW_CODE = os.path.normpath(os.path.join(_HERE, "..", "..", "skills", "review-code"))
_SKILL = os.path.join(_REVIEW_CODE, "SKILL.md")

_DELETE_WORDS = {"rm", "rmdir", "unlink"}
_DELETE_PAIRS = (("git", "rm"), ("git", "clean"), ("git", "worktree", "remove"))
_COMPOUND = re.compile(
    r"&&|\|\||;|(?<!\|)\|(?!\|)|\{ | \}|\( | \)|\b(?:bash|sh)\s+-c\b|\$\(|`"
)
_INLINE_SPAN = re.compile(r"`([^`]+)`")


def _tokens(text):
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return text.split()


def _is_delete(text):
    tokens = _tokens(text)
    if any(token in _DELETE_WORDS for token in tokens):
        return True
    for pair in _DELETE_PAIRS:
        width = len(pair)
        if any(tuple(tokens[i:i + width]) == pair for i in range(len(tokens) - width + 1)):
            return True
    return "find" in tokens and "-delete" in tokens


def _is_compound(text):
    return _COMPOUND.search(text) is not None


def _units(path):
    """Yield (line, text) for each logical line of every ```bash fence and each inline span outside fences."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    fence = None  # None outside a fence, "bash" in a bash fence, "other" in any other fence
    pending = None  # (start line, text so far) of a `\`-continued logical line
    for number, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if fence is None:
            if stripped.startswith("```"):
                fence = "bash" if stripped[3:].strip() == "bash" else "other"
                continue
            for span in _INLINE_SPAN.findall(raw):
                yield number, span
            continue
        if stripped == "```":
            if pending is not None:
                yield pending
                pending = None
            fence = None
            continue
        if fence != "bash":
            continue
        start, text = pending if pending is not None else (number, "")
        if raw.endswith("\\"):
            pending = (start, text + raw[:-1] + " ")
        else:
            pending = None
            yield start, text + raw


def _review_code_markdown():
    for root, _dirs, files in os.walk(_REVIEW_CODE):
        for name in sorted(files):
            if name.endswith(".md"):
                yield os.path.join(root, name)


def _skill_fence(needle):
    with open(_SKILL, encoding="utf-8") as handle:
        text = handle.read()
    fences = re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL)
    return next(block for block in fences if needle in block)


def test_no_review_code_recipe_puts_a_delete_inside_a_compound_command():
    # axis: no fenced bash block and no inline span under skills/review-code/ carries a delete inside a compound command — bite-proof record wo_e_2314_recipes
    hits = []
    plain_deletes = []
    for path in _review_code_markdown():
        rel = os.path.relpath(path, _REVIEW_CODE)
        for line, text in _units(path):
            if not _is_delete(text):
                continue
            if _is_compound(text):
                hits.append((rel, line, text))
            else:
                plain_deletes.append((rel, line, text))
    assert not hits, "a delete rides a compound command:\n" + "\n".join(
        "%s:%d: %s" % hit for hit in hits
    )
    # the plain `find … -delete 2>/dev/null` span in reference/verification-pass.md is a non-compound delete:
    # seeing it proves the scan reaches inline spans under reference/
    assert plain_deletes, "the scan saw no delete at all"
    assert any(rel == os.path.join("reference", "verification-pass.md") for rel, _l, _t in plain_deletes)


def _git(root, env, *args):
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        check=True, capture_output=True, env=env,
    )


def _run(script, env, cwd):
    return subprocess.run(
        ["bash", "-c", script + "\necho REACHED-END\n"],
        capture_output=True, text=True, env=env, cwd=str(cwd), timeout=120,
    )


def _failing_mv_path(tmp_path):
    shim = tmp_path / "shim"
    shim.mkdir()
    mv = shim / "mv"
    mv.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    os.chmod(mv, 0o755)
    return str(shim) + os.pathsep + os.environ["PATH"]


def _clean_env(**extra):
    env = dict(os.environ)
    for name in ("FOCUS_JSON", "LOC", "SOURCE", "PROVISIONAL"):
        env.pop(name, None)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.update(extra)
    return env


def _diff_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    env = _clean_env()
    _git(root, env, "init", "-q", "-b", "main")
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    _git(root, env, "add", "a.txt")
    _git(root, env, "commit", "-q", "-m", "first")
    first = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, env=env
    ).stdout.strip()
    (root / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
    _git(root, env, "commit", "-q", "-am", "second")
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, env=env
    ).stdout.strip()
    return root, first, head


def test_the_diff_recipe_halts_on_each_failure(tmp_path):
    # axis: each step of the rewritten diff recipe halts (exit 1, its own message, nothing after) on its own failure — bite-proof record wo_e_2314_recipes
    script = _skill_fence("diff.txt.tmp").replace("<round>", "1")
    root, first, head = _diff_repo(tmp_path)
    session = tmp_path / "session"
    (session / "round-1").mkdir(parents=True)
    diff_txt = session / "round-1" / "diff.txt"

    def run(base_ref, path=None):
        extra = {"SESSION_DIR": str(session), "BASE_REF": base_ref}
        if path is not None:
            extra["PATH"] = path
        return _run(script, _clean_env(**extra), root)

    # (a) a good base: the recipe runs to the end and leaves a non-empty diff.txt
    good = run(first)
    assert good.returncode == 0, good.stderr
    assert "REACHED-END" in good.stdout
    assert diff_txt.stat().st_size > 0
    diff_txt.unlink()

    # (b) the producer fails
    bad = run("not-a-commit")
    assert bad.returncode == 1, (bad.returncode, bad.stderr)
    assert "git diff against not-a-commit FAILED" in bad.stderr
    assert "REACHED-END" not in bad.stdout
    assert not diff_txt.exists()

    # (c) mv fails (a PATH shim whose mv only exits 1)
    moved = run(first, path=_failing_mv_path(tmp_path))
    assert moved.returncode == 1, (moved.returncode, moved.stderr)
    assert "git diff against %s FAILED" % first in moved.stderr
    assert "REACHED-END" not in moved.stdout
    assert not diff_txt.exists()

    # (d) an empty diff: the guard halts
    empty = run(head)
    assert empty.returncode == 1, (empty.returncode, empty.stderr)
    assert "is EMPTY" in empty.stderr
    assert "REACHED-END" not in empty.stdout


def test_the_meta_json_recipe_halts_on_each_failure(tmp_path):
    # axis: each step of the rewritten meta.json recipe halts (exit 1, its own message, nothing after) on its own failure — bite-proof record wo_e_2314_recipes
    if shutil.which("jq") is None:
        pytest.skip("jq not installed")
    script = _skill_fence("meta.json.tmp")
    session = tmp_path / "session"
    session.mkdir()

    def run(session_dir, path=None):
        extra = {
            "MODE": "pr", "BRANCH": "b", "HEAD_SHA": "a" * 40, "BASE_REF": "b" * 40, "BASE_BRANCH": "main",
            "REPO": "o/r", "REPO_ROOT": str(tmp_path), "BASE_FETCH": "fetched", "VERIFY_CMD": "none",
            "PR_NUMBER": "1", "SESSION_DIR": str(session_dir),
        }
        if path is not None:
            extra["PATH"] = path
        return _run(script, _clean_env(**extra), tmp_path)

    # (a) success: meta.json is written and parses
    good = run(session)
    assert good.returncode == 0, good.stderr
    assert "REACHED-END" in good.stdout
    with open(session / "meta.json", encoding="utf-8") as handle:
        assert json.load(handle)["mode"] == "pr"
    (session / "meta.json").unlink()

    # (b) the producer fails: the > redirection cannot open a file under a directory that does not exist
    broken = run(tmp_path / "no-such-parent" / "session")
    assert broken.returncode == 1, (broken.returncode, broken.stderr)
    assert "could not write meta.json" in broken.stderr
    assert "REACHED-END" not in broken.stdout

    # (c) mv fails (a PATH shim whose mv only exits 1)
    moved = run(session, path=_failing_mv_path(tmp_path))
    assert moved.returncode == 1, (moved.returncode, moved.stderr)
    assert "could not write meta.json" in moved.stderr
    assert "REACHED-END" not in moved.stdout
    assert not (session / "meta.json").exists()
    (session / "meta.json.tmp").unlink(missing_ok=True)

    # (d) the producer fails after its redirection opened the file: the session directory exists (so the > and the
    # mv would both succeed) and a PATH shim named jq only exits 1; only the producer's own guard can halt here
    jq_shim = tmp_path / "jq-shim"
    jq_shim.mkdir()
    jq = jq_shim / "jq"
    jq.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    os.chmod(jq, 0o755)
    produced = run(session, path=str(jq_shim) + os.pathsep + os.environ["PATH"])
    assert produced.returncode == 1, (produced.returncode, produced.stderr)
    assert "could not write meta.json" in produced.stderr
    assert "REACHED-END" not in produced.stdout
    assert not (session / "meta.json").exists()
    assert (session / "meta.json.tmp").exists()
