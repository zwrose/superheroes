# plugins/superheroes/lib/tests/test_hero_setup.py
"""#121 Part C: per-hero setup state — decline tracking + the tune-menu's offerable set."""
import json
import os
import sys

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import core_md
import hero_setup as HS


def test_declined_empty_by_default(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    assert HS.read_declined(repo, store) == set()
    assert HS.is_declined(repo, "test-pilot", store) is False


def test_mark_declined_persists_and_is_idempotent(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    res = HS.mark_declined(repo, "test-pilot", store)
    assert res["declined"] == ["test-pilot"]
    assert HS.is_declined(repo, "test-pilot", store) is True
    # survives a re-read (persisted to the machine-local store)
    assert HS.read_declined(repo, store) == {"test-pilot"}
    # idempotent
    assert HS.mark_declined(repo, "test-pilot", store)["declined"] == ["test-pilot"]


def test_mark_declined_unknown_hero_is_noop(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    HS.mark_declined(repo, "not-a-hero", store)
    assert HS.read_declined(repo, store) == set()


def test_offerable_lists_optional_unset_undeclined_only(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    # fresh: test-pilot (optional) is offerable; review-crew (mandatory) is NOT
    off = HS.offerable(repo, store)
    assert "test-pilot" in off
    assert "review-crew" not in off


def test_offerable_excludes_a_set_up_hero(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    layer = core_md._layer_path(repo, "test-pilot", store)
    os.makedirs(os.path.dirname(layer), exist_ok=True)
    open(layer, "w").write("<!-- test-pilot: schemaVersion=1 status=confirmed -->\n\n## App launch\n- x\n")
    assert "test-pilot" not in HS.offerable(repo, store)


def test_offerable_excludes_a_declined_hero(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    HS.mark_declined(repo, "test-pilot", store)
    assert "test-pilot" not in HS.offerable(repo, store)


def test_cli_offerable_and_decline(tmp_path, capsys):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    HS.main(["offerable", "--cwd", repo, "--root", store])
    assert "test-pilot" in json.loads(capsys.readouterr().out)["offerable"]
    HS.main(["decline", "--cwd", repo, "--root", store, "--hero", "test-pilot"])
    capsys.readouterr()
    HS.main(["offerable", "--cwd", repo, "--root", store])
    assert "test-pilot" not in json.loads(capsys.readouterr().out)["offerable"]
