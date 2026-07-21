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


def _expected_optional():
    return set(core_md._HEROES) - HS.MANDATORY


def test_declined_empty_by_default(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    assert HS.read_declined(repo, store) == set()


def test_read_declined_fails_open_on_malformed_json(tmp_path):
    # /code-review #4: a valid-JSON list with a non-string/non-hashable element must NOT raise
    # (set([{...}]) → TypeError) — the fail-open contract says corrupt reads as no declines.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    import mode_registry as MR
    MR.ensure_project_store(repo, store)
    import json
    open(HS._declined_path(repo, store), "w").write(json.dumps([{"x": 1}, 123, "test-pilot"]))
    got = HS.read_declined(repo, store)            # must not raise
    assert got == {"test-pilot"}                    # non-string/non-hashable elements ignored


def test_mark_declined_persists_and_is_idempotent(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    res = HS.mark_declined(repo, "test-pilot", store)
    assert res["declined"] == ["test-pilot"]
    # survives a re-read (persisted to the machine-local store)
    assert HS.read_declined(repo, store) == {"test-pilot"}
    # idempotent
    assert HS.mark_declined(repo, "test-pilot", store)["declined"] == ["test-pilot"]


def test_offerable_treats_empty_placeholder_layer_as_not_set_up(tmp_path):
    # /code-review #12: a present-but-empty placeholder layer (interrupted set-up) must NOT count
    # as set up — the hero stays offerable so the owner can finish it.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    layer = core_md._layer_path(repo, "test-pilot", store)
    os.makedirs(os.path.dirname(layer), exist_ok=True)
    open(layer, "w").write(core_md._render_layer("", "test-pilot", "provisional", "2026-06-26"))
    assert "test-pilot" in HS.offerable(repo, store)


def test_mark_declined_unknown_hero_is_noop(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    HS.mark_declined(repo, "not-a-hero", store)
    assert HS.read_declined(repo, store) == set()


def test_offerable_lists_optional_unset_undeclined_only(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    # fresh: every optional hero is offerable; review-crew (mandatory) is NOT
    assert set(HS.offerable(repo, store)) == _expected_optional()


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
    expected = _expected_optional()
    HS.main(["offerable", "--cwd", repo, "--root", store])
    assert set(json.loads(capsys.readouterr().out)["offerable"]) == expected
    HS.main(["decline", "--cwd", repo, "--root", store, "--hero", "test-pilot"])
    capsys.readouterr()
    HS.main(["offerable", "--cwd", repo, "--root", store])
    assert set(json.loads(capsys.readouterr().out)["offerable"]) == (expected - {"test-pilot"})
