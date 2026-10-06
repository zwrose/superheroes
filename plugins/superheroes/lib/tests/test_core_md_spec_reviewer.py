# plugins/superheroes/lib/tests/test_core_md_spec_reviewer.py
"""Conformance: the specReviewer writer, its CLI verb, and `confirm` keeping engine preferences."""
import contextlib
import importlib.util
import io
import json
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CM = _load("core_md")

_FACTS = {"verifyCommand": "npm test", "stackTags": ["node"],
          "threatModel": "single-user", "patterns": "- x: a.ts:1"}
_PREFS = {"reviewer": "codex", "builderDispatchTier": "sonnet",
          "codexModels": {"build": "gpt-4"}}


def _seed(tmp_path, prefs=None, status="confirmed"):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    facts = dict(_FACTS)
    if prefs is not None:
        facts["enginePreferences"] = dict(prefs)
    CM.write(repo, facts, status, root=store, now="2026-06-26")
    return repo, store


def test_write_spec_reviewer_sets_canonical_token_and_preserves_everything_else(tmp_path):
    repo, store = _seed(tmp_path, prefs=_PREFS)
    before = CM.read(repo, root=store)
    res = CM.write_spec_reviewer(repo, "Codex", root=store)
    assert res == {"action": "written"}
    got = CM.read(repo, root=store)
    assert got["enginePreferences"]["specReviewer"] == "codex"
    for key, value in _PREFS.items():
        assert got["enginePreferences"][key] == value
    for key in before:
        if key != "enginePreferences":
            assert got[key] == before[key]


def test_write_spec_reviewer_creates_the_prefs_block_when_absent(tmp_path):
    repo, store = _seed(tmp_path)
    assert CM.write_spec_reviewer(repo, "claude", root=store) == {"action": "written"}
    assert CM.read(repo, root=store)["enginePreferences"] == {"specReviewer": "claude"}


@pytest.mark.parametrize("blank", (None, "", "  "))
def test_write_spec_reviewer_blank_clears_the_key_only(tmp_path, blank):
    repo, store = _seed(tmp_path, prefs=dict(_PREFS, specReviewer="cursor"))
    res = CM.write_spec_reviewer(repo, blank, root=store)
    assert res == {"action": "written"}
    assert CM.read(repo, root=store)["enginePreferences"] == _PREFS


def test_write_spec_reviewer_clearing_an_absent_key_is_noop(tmp_path):
    repo, store = _seed(tmp_path, prefs=_PREFS)
    path = CM.core_path(repo, store)
    before = open(path, encoding="utf-8").read()
    assert CM.write_spec_reviewer(repo, None, root=store) == {"action": "noop"}
    assert open(path, encoding="utf-8").read() == before


@pytest.mark.parametrize("bad", ("gemini", "opus", 5, ["codex"], {}))
def test_write_spec_reviewer_refuses_unknown_engine_byte_identical(tmp_path, bad):
    repo, store = _seed(tmp_path, prefs=dict(_PREFS, specReviewer="claude"))
    path = CM.core_path(repo, store)
    before = open(path, encoding="utf-8").read()
    res = CM.write_spec_reviewer(repo, bad, root=store)
    assert res == {"action": "refused", "reason": "spec-reviewer-unknown-engine"}
    assert open(path, encoding="utf-8").read() == before


def test_write_spec_reviewer_refuses_when_profile_absent(tmp_path):
    repo = str(tmp_path)
    res = CM.write_spec_reviewer(repo, "codex", root=str(tmp_path / "store"))
    assert res["action"] == "refused"
    assert res["reason"] == CM.BUILDER_DISPATCH_REASON_ABSENT


def test_write_spec_reviewer_refuses_unparseable_profile(tmp_path):
    repo, store = _seed(tmp_path, prefs=_PREFS)
    path = CM.core_path(repo, store)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not a core profile at all\n")
    before = open(path, "rb").read()
    res = CM.write_spec_reviewer(repo, "codex", root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.BUILDER_DISPATCH_REASON_UNPARSEABLE
    assert open(path, "rb").read() == before


def test_write_spec_reviewer_schema_behind_is_not_rewritten(tmp_path):
    repo, store = _seed(tmp_path, prefs=_PREFS)
    path = CM.core_path(repo, store)
    text = open(path, encoding="utf-8").read()
    newer = text.replace('"schemaVersion": %d' % CM.SCHEMA_VERSION,
                         '"schemaVersion": %d' % (CM.SCHEMA_VERSION + 1))
    assert newer != text
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(newer)
    res = CM.write_spec_reviewer(repo, "codex", root=store)
    assert res["action"] == "behind"
    assert res["reason"] == CM.BUILDER_DISPATCH_DEFER_SCHEMA_BEHIND
    assert open(path, encoding="utf-8").read() == newer


def test_write_spec_reviewer_lock_contended_is_deferred(tmp_path, monkeypatch):
    repo, store = _seed(tmp_path, prefs=_PREFS)
    path = CM.core_path(repo, store)
    before = open(path, encoding="utf-8").read()

    @contextlib.contextmanager
    def contended(cwd, root=None):
        yield False

    monkeypatch.setattr(CM.mode_registry, "config_lock", contended)
    res = CM.write_spec_reviewer(repo, "codex", root=store)
    assert res == {"action": "deferred", "reason": CM.BUILDER_DISPATCH_DEFER_LOCK_CONTENDED}
    assert open(path, encoding="utf-8").read() == before


def _raise_oserror(*_args, **_kwargs):
    raise OSError("disk full")


def test_write_spec_reviewer_write_failure_names_the_seat_not_the_builder_tier(tmp_path, monkeypatch):
    repo, store = _seed(tmp_path, prefs=_PREFS)
    monkeypatch.setattr(CM.store_core, "atomic_write", _raise_oserror)
    res = CM.write_spec_reviewer(repo, "codex", root=store)
    assert res == {"action": "deferred", "reason": "spec-reviewer-write-failed"}


def test_write_spec_reviewer_round_trip_refusal_names_the_seat_not_the_builder_tier(tmp_path, monkeypatch):
    repo, store = _seed(tmp_path, prefs=_PREFS)
    monkeypatch.setattr(CM, "_engine_pref_round_trip_ok", lambda *args, **kwargs: False)
    res = CM.write_spec_reviewer(repo, "codex", root=store)
    assert res == {"action": "refused", "reason": "spec-reviewer-round-trip-refused"}


def test_write_builder_dispatch_tier_write_failure_keeps_the_builder_token(tmp_path, monkeypatch):
    repo, store = _seed(tmp_path, prefs=_PREFS)
    monkeypatch.setattr(CM.store_core, "atomic_write", _raise_oserror)
    res = CM.write_builder_dispatch_tier(repo, "opus", root=store)
    assert res == {"action": "deferred", "reason": "builder-tier-write-failed"}


def test_write_builder_dispatch_tier_round_trip_refusal_keeps_the_builder_token(tmp_path, monkeypatch):
    repo, store = _seed(tmp_path, prefs=_PREFS)
    monkeypatch.setattr(CM, "_engine_pref_round_trip_ok", lambda *args, **kwargs: False)
    res = CM.write_builder_dispatch_tier(repo, "opus", root=store)
    assert res == {"action": "refused", "reason": "builder-dispatch-round-trip-refused"}


def test_cli_write_spec_reviewer_round_trip(tmp_path, capsys, monkeypatch):
    repo, store = _seed(tmp_path, prefs=_PREFS)
    monkeypatch.setattr("sys.stdin", io.StringIO("cursor\n"))
    assert CM.main(["write-spec-reviewer", "--cwd", repo, "--root", store]) == 0
    assert json.loads(capsys.readouterr().out) == {"action": "written"}
    assert CM.read(repo, root=store)["enginePreferences"]["specReviewer"] == "cursor"
    monkeypatch.setattr("sys.stdin", io.StringIO("gemini\n"))
    assert CM.main(["write-spec-reviewer", "--cwd", repo, "--root", store]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "action": "refused", "reason": "spec-reviewer-unknown-engine"}
    monkeypatch.setattr("sys.stdin", io.StringIO("  \n"))
    assert CM.main(["write-spec-reviewer", "--cwd", repo, "--root", store]) == 0
    assert json.loads(capsys.readouterr().out) == {"action": "written"}
    assert CM.read(repo, root=store)["enginePreferences"] == _PREFS


def test_confirm_preserves_engine_preferences(tmp_path):
    # E12: confirming a provisional core keeps the seat, the builder tier and a role.
    prefs = dict(_PREFS, specReviewer="codex")
    repo, store = _seed(tmp_path, prefs=prefs, status="provisional")
    assert CM.read(repo, root=store)["enginePreferences"] == prefs
    assert CM.confirm(repo, root=store, now="2026-06-28")["action"] == "confirmed"
    got = CM.read(repo, root=store)
    assert got["status"] == "confirmed"
    assert got["enginePreferences"] == prefs


def test_confirm_without_engine_preferences_is_unchanged(tmp_path):
    # E13: no enginePreferences on the provisional core → none appears, other facts untouched.
    repo, store = _seed(tmp_path, status="provisional")
    assert CM.confirm(repo, root=store, now="2026-06-28")["action"] == "confirmed"
    got = CM.read(repo, root=store)
    assert got["status"] == "confirmed"
    assert got["enginePreferences"] == {}
    assert got["verifyCommand"] == "npm test"
    assert got["created"] == "2026-06-26"
