"""The kept-profile wording check survives the normal release assembly.

Reads one named test module; assembly touches only a synthetic temporary plugin.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

_HERE = Path(__file__).resolve().parent
_LIB = _HERE.parent
_PLUGIN = _LIB.parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import leftover_settings as ls  # noqa: E402


def test_upgrade_wording_check_survives_release_assembly(tmp_path, monkeypatch):
    # axis: the upgrade wording check passes before and after assembly moves a pending note into TRANSITION.md and removes its old file; all fixture writes stay under tmp_path
    root = tmp_path / "plugin"
    notes = root / "transition-notes"
    notes.mkdir(parents=True)
    transition = root / "TRANSITION.md"
    transition.write_text("# Transition notes\n", encoding="utf-8")
    pending = notes / "2594.md"
    pending.write_text(
        "### Before you upgrade\n\n"
        "- **After switching.** Read the kept-profile warning.\n\n"
        "### Kept profile warning\n\n"
        + ls.KEPT_TEST_PILOT_PROFILE_SENTENCE + "\n",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location(
        "kept_profile_wording_release_probe",
        _HERE / "test_kept_test_pilot_sentence_2610.py",
    )
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    monkeypatch.setattr(guard, "_PLUGIN", str(root))
    guard.test_upgrade_note_carries_the_sentence()

    completed = subprocess.run(
        [sys.executable, "-B", str(_LIB / "transition_notes.py"),
         "assemble", "--plugin-root", str(root), "--version", "1.0.0"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["ok"] is True
    assert not pending.exists()
    assert ls.KEPT_TEST_PILOT_PROFILE_SENTENCE in transition.read_text(encoding="utf-8")
    guard.test_upgrade_note_carries_the_sentence()
