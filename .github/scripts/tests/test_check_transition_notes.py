"""check_transition_notes.py end to end: throwaway git repos, the script run as a subprocess.

Each case is a red then the fixed tree green. The temp repo carries a copy of the real lib module, so
the script loads it from `<repo root>/plugins/superheroes/lib/transition_notes.py` the way CI does.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_SCRIPT = os.path.join(_ROOT, ".github", "scripts", "check_transition_notes.py")
_REAL_LIB = os.path.join(_ROOT, "plugins", "superheroes", "lib", "transition_notes.py")

_GIT_ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1")

TRANSITION = """\
# Transition notes

Header prose.

## 1.0.0

### Before you upgrade

Check these in a consuming project when it adopts 1.0.0. Each step names the note it comes from.

- **After switching.** Old step.

### Old note

Old body.
"""

NOTE_7 = """\
### Before you upgrade

- **Before switching.** Seven step: do the seven thing first.

### New note

New body.
"""

NOTE_8_UNMARKED = NOTE_7.replace("**Before switching.** ", "")

DIRECT_TRANSITION = TRANSITION.replace(
    "- **After switching.** Old step.\n",
    "- **After switching.** Old step.\n- **Before switching.** Seven step: do the seven thing first.\n",
) + "\n### New note\n\nNew body.\n"

ZERO_SHA = "0" * 40


def _git(repo, *args, commit=False):
    argv = ["git", "-C", str(repo)]
    if commit:
        argv += ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    proc = subprocess.run(argv + list(args), capture_output=True, text=True, env=_GIT_ENV, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _plugin(repo):
    return repo / "plugins" / "superheroes"


def _notes_dir(repo):
    return _plugin(repo) / "transition-notes"


def _make_repo(tmp_path, base_notes=()):
    """A repo whose one commit holds TRANSITION.md, the notes README, `base_notes` and the lib copy."""
    repo = tmp_path / "repo"
    (repo / "plugins" / "superheroes" / "lib").mkdir(parents=True)
    _notes_dir(repo).mkdir()
    (_plugin(repo) / "TRANSITION.md").write_text(TRANSITION)
    (_notes_dir(repo) / "README.md").write_text("How to write a note.\n")
    for name, text in base_notes:
        (_notes_dir(repo) / name).write_text(text)
    shutil.copyfile(_REAL_LIB, str(_plugin(repo) / "lib" / "transition_notes.py"))
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base", commit=True)
    return repo, _git(repo, "rev-parse", "HEAD")


def _lib(repo):
    spec = importlib.util.spec_from_file_location("tn_copy", str(_plugin(repo) / "lib" / "transition_notes.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(repo, *flags):
    proc = subprocess.run(
        [sys.executable, _SCRIPT, "--repo-root", str(repo), *flags],
        capture_output=True, text=True, env=_GIT_ENV, timeout=120,
    )
    return proc.returncode, json.loads(proc.stdout), proc.stderr


def _tokens(result):
    return [p["token"] for p in result["problems"]]


def test_malformed_note_is_refused_then_fixed_passes(tmp_path):
    repo, _base = _make_repo(tmp_path)
    (_notes_dir(repo) / "8.md").write_text(NOTE_8_UNMARKED)
    code, result, err = _run(repo)
    assert code == 1
    assert result["ok"] is False
    assert _tokens(result) == ["note-bullet-unmarked"]
    assert "8.md: note-bullet-unmarked: " in err
    (_notes_dir(repo) / "8.md").write_text(NOTE_7)
    code, result, err = _run(repo)
    assert code == 0
    assert result["ok"] is True
    assert result["notes"] == ["8.md"]
    assert err == ""


def test_note_written_straight_into_transition_is_refused_then_moved_to_a_file_passes(tmp_path):
    repo, base = _make_repo(tmp_path)
    (_plugin(repo) / "TRANSITION.md").write_text(DIRECT_TRANSITION)
    code, result, err = _run(repo, "--base", base)
    assert code == 1
    assert result["mode"] == "pr"
    assert sorted(_tokens(result)) == ["transition-bullet-added", "transition-heading-added"]
    assert "TRANSITION.md: transition-heading-added: " in err
    (_plugin(repo) / "TRANSITION.md").write_text(TRANSITION)
    (_notes_dir(repo) / "7.md").write_text(NOTE_7)
    code, result, err = _run(repo, "--base", base)
    assert code == 0
    assert result["ok"] is True
    assert result["notes"] == ["7.md"]


def test_assembly_missing_its_section_is_refused_then_the_real_assembly_passes(tmp_path):
    repo, base = _make_repo(tmp_path, base_notes=[("7.md", NOTE_7)])
    # The note is deleted but TRANSITION.md is unchanged: its section never reached the file.
    os.remove(str(_notes_dir(repo) / "7.md"))
    code, result, err = _run(repo, "--base", base)
    assert code == 1
    assert "note-removed-unassembled" in _tokens(result)
    assert "7.md: note-removed-unassembled: " in err
    # The release doc pass's own assembly of the same note.
    (_notes_dir(repo) / "7.md").write_text(NOTE_7)
    assembled = _lib(repo).assemble(str(_plugin(repo)), "1.1.0")
    assert assembled["ok"] is True
    code, result, err = _run(repo, "--base", base)
    assert code == 0
    assert result["ok"] is True


def test_assembly_by_the_release_doc_pass_passes(tmp_path):
    repo, base = _make_repo(tmp_path, base_notes=[("7.md", NOTE_7)])
    assembled = _lib(repo).assemble(str(_plugin(repo)), "1.1.0")
    assert assembled["ok"] is True
    assert not os.path.exists(str(_notes_dir(repo) / "7.md"))
    code, result, err = _run(repo, "--base", base)
    assert code == 0
    assert result["mode"] == "pr"
    assert result["ok"] is True
    assert result["notes"] == []


def test_release_pr_refuses_an_unassembled_note_then_passes_after_assembly(tmp_path):
    repo, base = _make_repo(tmp_path, base_notes=[("7.md", NOTE_7)])
    code, result, err = _run(repo, "--base", base, "--release")
    assert code == 1
    assert result["mode"] == "pr+release"
    assert _tokens(result) == ["note-unassembled-at-release"]
    assert "7.md: note-unassembled-at-release: " in err
    assembled = _lib(repo).assemble(str(_plugin(repo)), "1.1.0")
    assert assembled["ok"] is True
    code, result, err = _run(repo, "--base", base, "--release")
    assert code == 0
    assert result["mode"] == "pr+release"
    assert result["ok"] is True


def test_release_alone_refuses_a_note_then_passes_without_one(tmp_path):
    repo, _base = _make_repo(tmp_path)
    (_notes_dir(repo) / "7.md").write_text(NOTE_7)
    code, result, err = _run(repo, "--release")
    assert code == 1
    assert result["mode"] == "release"
    assert _tokens(result) == ["note-unassembled-at-release"]
    os.remove(str(_notes_dir(repo) / "7.md"))
    code, result, err = _run(repo, "--release")
    assert code == 0
    assert result["mode"] == "release"
    assert result["ok"] is True


def test_unresolvable_base_is_refused_then_a_real_base_passes(tmp_path):
    repo, base = _make_repo(tmp_path)
    code, result, err = _run(repo, "--base", ZERO_SHA)
    assert code == 1
    assert result["ok"] is False
    assert _tokens(result) == ["base-unresolvable"]
    assert result["problems"][0]["file"] == "TRANSITION.md"
    assert "TRANSITION.md: base-unresolvable: " in err
    code, result, err = _run(repo, "--base", base)
    assert code == 0
    assert result["ok"] is True


def test_shape_mode_on_a_well_formed_tree_passes(tmp_path):
    repo, _base = _make_repo(tmp_path)
    code, result, err = _run(repo)
    assert code == 0
    assert result == {"ok": True, "mode": "shape", "problems": [], "notes": []}
    assert err == ""
