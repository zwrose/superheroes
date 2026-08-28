"""Tests for `round_commit` — the two-phase commit primitive for the round driver (#918).

The contract these pin is the REFUSAL REASON TOKEN, not merely an exception: every fail-closed
edge gets its own test asserting the exact ``reason``, because a caller routes on that string.
Also pinned: the crash-point matrix, journal dedup and torn-tail safety, and idempotent replay.
"""
import ast
import importlib.util
import json
import os
import shutil

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RC = _load("round_commit")

COMMIT_ID = "a" * 32


# --- helpers ----------------------------------------------------------------------------------

def _session(tmp_path):
    sd = str(tmp_path / "session")
    os.makedirs(sd, exist_ok=True)
    return sd


def _two_replace_commit(sd, stop_at=None, commit_id=COMMIT_ID):
    t1 = os.path.join(sd, "one.txt")
    t2 = os.path.join(sd, "sub", "two.txt")
    c = RC.begin(sd, "test", stop_at=stop_at, commit_id=commit_id)
    c.add_replace_file(t1, b"first")
    c.add_replace_file(t2, b"second")
    return c


def _journal_commit(sd, stop_at=None, commit_id=COMMIT_ID):
    journal = os.path.join(sd, "journal.jsonl")
    c = RC.begin(sd, "journal", stop_at=stop_at, commit_id=commit_id)
    c.add_journal_append(journal, {"cmd": "one", "seq": 1})
    c.add_journal_append(journal, {"cmd": "two", "seq": 2})
    return c, journal


# --- A. happy path ---------------------------------------------------------------------------

def test_happy_two_replace_file(tmp_path):
    sd = _session(tmp_path)
    t1 = os.path.join(sd, "one.txt")
    t2 = os.path.join(sd, "sub", "two.txt")
    c = RC.begin(sd, "happy")
    c.add_replace_file(t1, b"first")
    c.add_replace_file(t2, b"second")
    result = c.run()
    assert result["ok"] is True
    assert result["parts"] == 2
    assert open(t1, "rb").read() == b"first"
    assert open(t2, "rb").read() == b"second"
    assert os.listdir(RC.commits_root(sd)) == []


def test_happy_two_journal_append(tmp_path):
    sd = _session(tmp_path)
    c, journal = _journal_commit(sd)
    c.run()
    lines = open(journal, encoding="utf-8").read().strip().split("\n")
    assert len(lines) == 2
    rows = [json.loads(line) for line in lines]
    append_ids = [r["appendId"] for r in rows]
    assert len(set(append_ids)) == 2
    assert all("#" in aid for aid in append_ids)


def test_atomic_write_json_roundtrip(tmp_path):
    path = str(tmp_path / "obj.json")
    obj = {"b": 2, "a": 1}
    RC.atomic_write_json(path, obj)
    assert open(path, encoding="utf-8").read() == '{"a":1,"b":2}\n'
    assert not os.path.exists(path + ".tmp")
    loaded = json.loads(open(path, encoding="utf-8").read())
    assert loaded == obj


# --- B. crash-point matrix -------------------------------------------------------------------

@pytest.mark.parametrize("stop_at,expect_discard,expect_replay,expect_clean,"
                         "targets_exist,commits_empty",
                         [
                             ("staged", True, False, False, False, True),
                             ("sealed", False, True, False, True, False),
                             ("part:0", False, True, False, True, False),
                             ("applied", False, True, False, True, True),
                             ("done", False, False, True, True, True),
                             ("renamed", False, False, True, True, True),
                         ])
def test_crash_point_matrix(tmp_path, stop_at, expect_discard, expect_replay,
                            expect_clean, targets_exist, commits_empty):
    sd = _session(tmp_path)
    t1 = os.path.join(sd, "one.txt")
    t2 = os.path.join(sd, "sub", "two.txt")
    c = _two_replace_commit(sd, stop_at=stop_at)
    with pytest.raises(RC.StopPoint) as exc:
        c.run()
    assert exc.value.where == stop_at

    if stop_at == "renamed":
        root = RC.commits_root(sd)
        cleanup = os.path.join(root, RC._cleanup_name(COMMIT_ID))
        assert os.path.isdir(cleanup)

    result = RC.recover(sd)
    if expect_discard:
        assert result["discarded"] == [COMMIT_ID]
    if expect_replay:
        assert result["replayed"] == [COMMIT_ID]
    if expect_clean:
        assert result["cleaned"] == [COMMIT_ID]

    if targets_exist:
        assert open(t1, "rb").read() == b"first"
        assert open(t2, "rb").read() == b"second"
    else:
        assert not os.path.exists(t1)
        assert not os.path.exists(t2)

    if commits_empty:
        assert not os.path.exists(RC.commits_root(sd)) or os.listdir(RC.commits_root(sd)) == []


def test_applied_idempotent_bytes(tmp_path):
    sd = _session(tmp_path)
    t1 = os.path.join(sd, "one.txt")
    t2 = os.path.join(sd, "sub", "two.txt")
    c = _two_replace_commit(sd, stop_at="applied")
    with pytest.raises(RC.StopPoint):
        c.run()
    RC.recover(sd)
    assert open(t1, "rb").read() == b"first"
    assert open(t2, "rb").read() == b"second"
    RC.recover(sd)
    assert open(t1, "rb").read() == b"first"
    assert open(t2, "rb").read() == b"second"


# --- C. idempotency and journal safety -------------------------------------------------------

def test_recover_twice_after_sealed_noop(tmp_path):
    sd = _session(tmp_path)
    c, journal = _journal_commit(sd, stop_at="sealed")
    with pytest.raises(RC.StopPoint):
        c.run()
    RC.recover(sd)
    lines1 = open(journal, encoding="utf-8").read().strip().split("\n")
    RC.recover(sd)
    lines2 = open(journal, encoding="utf-8").read().strip().split("\n")
    assert lines1 == lines2
    assert len(lines2) == 2


def test_torn_tail_preserved(tmp_path):
    sd = _session(tmp_path)
    journal = os.path.join(sd, "journal.jsonl")
    with open(journal, "wb") as fh:
        fh.write(b'{"partial":')
    cid = "b" * 32
    c = RC.begin(sd, "torn", commit_id=cid)
    c.add_journal_append(journal, {"cmd": "after-torn"})
    c.run()
    raw = open(journal, "rb").read()
    assert b'{"partial":' in raw
    lines = raw.split(b"\n")
    parsed = []
    for line in lines:
        if not line.strip():
            continue
        try:
            parsed.append(json.loads(line.decode("utf-8")))
        except ValueError:
            pass
    append_rows = [p for p in parsed if isinstance(p, dict) and "appendId" in p]
    assert len(append_rows) == 1
    assert append_rows[0]["appendId"] == "%s#0" % cid


def test_journal_replay_no_duplicate(tmp_path):
    sd = _session(tmp_path)
    c, journal = _journal_commit(sd, stop_at="applied")
    with pytest.raises(RC.StopPoint):
        c.run()
    RC.recover(sd)
    rows = []
    for line in open(journal, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and "appendId" in obj:
            rows.append(obj)
    assert len(rows) == 2
    assert len([r for r in rows if r["appendId"] == "%s#0" % COMMIT_ID]) == 1


def test_journal_dedup_skips_non_dict(tmp_path):
    sd = _session(tmp_path)
    journal = os.path.join(sd, "journal.jsonl")
    with open(journal, "w", encoding="utf-8") as fh:
        fh.write("123\n")
    cid = "c" * 32
    c = RC.begin(sd, "nondict", commit_id=cid)
    c.add_journal_append(journal, {"cmd": "ok"})
    c.run()
    lines = open(journal, encoding="utf-8").read().strip().split("\n")
    assert "123" in lines
    dict_rows = [json.loads(l) for l in lines if l.startswith("{")]
    assert len(dict_rows) == 1


# --- D. fail-closed edges --------------------------------------------------------------------

def test_edge1_missing_commits_dir_noop(tmp_path):
    sd = _session(tmp_path)
    result = RC.recover(sd)
    assert result == {"ok": True, "replayed": [], "discarded": [], "cleaned": []}


def test_edge2_sealed_intent_unreadable(tmp_path):
    sd = _session(tmp_path)
    c = _two_replace_commit(sd, stop_at="sealed")
    with pytest.raises(RC.StopPoint):
        c.run()
    intent = os.path.join(RC.commits_root(sd), COMMIT_ID, "intent.json")
    with open(intent, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    with pytest.raises(RC.CommitRefused) as exc:
        RC.recover(sd)
    assert exc.value.reason == "intent-unreadable"


def test_edge3_unsealed_intent_unreadable_discarded(tmp_path):
    sd = _session(tmp_path)
    c = _two_replace_commit(sd, stop_at="staged")
    with pytest.raises(RC.StopPoint):
        c.run()
    intent = os.path.join(RC.commits_root(sd), COMMIT_ID, "intent.json")
    with open(intent, "w", encoding="utf-8") as fh:
        fh.write("{bad")
    result = RC.recover(sd)
    assert result["discarded"] == [COMMIT_ID]
    assert result["replayed"] == []


def test_edge4_staged_part_missing(tmp_path):
    sd = _session(tmp_path)
    c = _two_replace_commit(sd, stop_at="sealed")
    with pytest.raises(RC.StopPoint):
        c.run()
    part = os.path.join(RC.commits_root(sd), COMMIT_ID, "parts", "0")
    os.remove(part)
    with pytest.raises(RC.CommitRefused) as exc:
        RC.recover(sd)
    assert exc.value.reason == "staged-part-missing"


def test_edge5_staged_part_corrupt(tmp_path):
    sd = _session(tmp_path)
    t1 = os.path.join(sd, "one.txt")
    t2 = os.path.join(sd, "sub", "two.txt")
    c = RC.begin(sd, "ok", commit_id="d" * 32)
    c.add_replace_file(t1, b"first")
    c.add_replace_file(t2, b"second")
    c.run()
    assert open(t1, "rb").read() == b"first"

    c2 = _two_replace_commit(sd, stop_at="sealed", commit_id="e" * 32)
    with pytest.raises(RC.StopPoint):
        c2.run()
    part = os.path.join(RC.commits_root(sd), "e" * 32, "parts", "0")
    with open(part, "wb") as fh:
        fh.write(b"corrupted")
    with pytest.raises(RC.CommitRefused) as exc:
        RC.recover(sd)
    assert exc.value.reason == "staged-part-corrupt"


def test_edge6_target_escapes_session_add_and_replay(tmp_path):
    sd = _session(tmp_path)
    outside = str(tmp_path / "escape.txt")
    with pytest.raises(RC.CommitRefused) as exc:
        RC.begin(sd, "x").add_replace_file(outside, b"nope")
    assert exc.value.reason == "target-escapes-session"

    t1 = os.path.join(sd, "one.txt")
    c = RC.begin(sd, "ok-first", commit_id="f" * 32)
    c.add_replace_file(t1, b"ok")
    c.run()

    c2 = _two_replace_commit(sd, stop_at="sealed", commit_id="0" * 32)
    with pytest.raises(RC.StopPoint):
        c2.run()
    intent_path = os.path.join(RC.commits_root(sd), "0" * 32, "intent.json")
    intent = json.loads(open(intent_path, encoding="utf-8").read())
    intent["parts"][0]["target"] = "../escape.txt"
    with open(intent_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(intent, sort_keys=True, separators=(",", ":")) + "\n")
    escape = os.path.join(sd, "escape.txt")
    assert not os.path.exists(escape)
    with pytest.raises(RC.CommitRefused) as exc2:
        RC.recover(sd)
    assert exc2.value.reason == "target-escapes-session"
    assert not os.path.exists(escape)


def test_edge7_sidecar_target_unresolvable(tmp_path):
    sd = _session(tmp_path)
    sidecar = str(tmp_path / "sidecar.json")

    def _ok():
        return sidecar

    c = RC.begin(sd, "ok-sidecar", commit_id="1" * 32)
    c.add_external_sidecar(b'{"ok":true}', _ok)
    c.run()
    assert open(sidecar, "rb").read() == b'{"ok":true}'

    c2 = RC.begin(sd, "bad-sidecar", stop_at="sealed", commit_id="2" * 32)
    c2.add_external_sidecar(b"data", _ok)
    with pytest.raises(RC.StopPoint):
        c2.run()
    with pytest.raises(RC.CommitRefused) as exc:
        RC.recover(sd, sidecar_target=lambda: None)
    assert exc.value.reason == "sidecar-target-unresolvable"

    def _raise():
        raise RuntimeError("nope")

    c3 = RC.begin(sd, "raise-sidecar", stop_at="sealed", commit_id="3" * 32)
    c3.add_external_sidecar(b"data", _raise)
    with pytest.raises(RC.StopPoint):
        c3.run()
    with pytest.raises(RC.CommitRefused) as exc2:
        RC.recover(sd, sidecar_target=_raise)
    assert exc2.value.reason == "sidecar-target-unresolvable"


def test_edge8_commit_durability_unsupported(tmp_path, monkeypatch):
    sd = _session(tmp_path)
    import errno as _errno

    def _boom(directory):
        raise OSError(_errno.ENOTSUP, "nope")

    monkeypatch.setattr(RC, "fsync_dir_strict", _boom)
    c = _two_replace_commit(sd)
    with pytest.raises(RC.CommitRefused) as exc:
        c.run()
    assert exc.value.reason == "commit-durability-unsupported"
    assert not os.path.exists(os.path.join(sd, "one.txt"))


def test_edge9_journal_entry_not_a_mapping(tmp_path):
    sd = _session(tmp_path)
    journal = os.path.join(sd, "journal.jsonl")
    with pytest.raises(RC.CommitRefused) as exc:
        RC.begin(sd, "x").add_journal_append(journal, ["not", "a", "dict"])
    assert exc.value.reason == "journal-entry-not-a-mapping"


def test_edge10_commits_dir_unexpected_entry(tmp_path):
    sd = _session(tmp_path)
    root = RC.commits_root(sd)
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "stray.txt"), "w", encoding="utf-8") as fh:
        fh.write("x")
    with pytest.raises(RC.CommitRefused) as exc:
        RC.recover(sd)
    assert exc.value.reason == "commits-dir-unexpected-entry"


def test_edge11_commit_apply_failed_on_recover(tmp_path, monkeypatch):
    sd = _session(tmp_path)
    c = _two_replace_commit(sd, stop_at="sealed", commit_id="4" * 32)
    with pytest.raises(RC.StopPoint):
        c.run()

    def _replace_fail(*_a, **_k):
        raise OSError(13, "permission denied")

    monkeypatch.setattr(RC.os, "replace", _replace_fail)
    with pytest.raises(RC.CommitRefused) as exc:
        RC.recover(sd)
    assert exc.value.reason == "commit-apply-failed"


def test_edge11_commit_cleanup_failed_on_recover(tmp_path, monkeypatch):
    sd = _session(tmp_path)
    c = _two_replace_commit(sd, stop_at="done", commit_id="5" * 32)
    with pytest.raises(RC.StopPoint):
        c.run()
    monkeypatch.setattr(RC.shutil, "rmtree",
                        lambda *_a, **_k: (_ for _ in ()).throw(OSError(13, "nope")))
    with pytest.raises(RC.CommitRefused) as exc:
        RC.recover(sd)
    assert exc.value.reason == "commit-cleanup-failed"


def test_unknown_stop_point_at_begin(tmp_path):
    sd = _session(tmp_path)
    with pytest.raises(RC.CommitRefused) as exc:
        RC.begin(sd, "x", stop_at="not-a-real-stop")
    assert exc.value.reason == "unknown-stop-point"


def test_external_sidecar_happy(tmp_path):
    sd = _session(tmp_path)
    sidecar = str(tmp_path / "outside.json")

    def _resolve():
        return sidecar

    c = RC.begin(sd, "sidecar")
    c.add_external_sidecar(b'{"verdict":"ok"}', _resolve)
    result = c.run()
    assert sidecar in result["targets"]
    assert open(sidecar, "rb").read() == b'{"verdict":"ok"}'


# --- F1–F6 fixes (#918) ----------------------------------------------------------------------

def test_f1_invalid_commit_id_refused_no_commits_dir(tmp_path):
    sd = _session(tmp_path)
    with pytest.raises(RC.CommitRefused) as exc:
        RC.begin(sd, "probe", commit_id="pinned-1", stop_at="sealed")
    assert exc.value.reason == "invalid-commit-id"
    assert exc.value.detail == "pinned-1"
    assert not os.path.exists(RC.commits_root(sd))


def test_f1_valid_commit_id_sealed_then_recover_replays(tmp_path):
    sd = _session(tmp_path)
    cid = "a" * 32
    target = os.path.join(sd, "x.txt")
    c = RC.begin(sd, "probe", commit_id=cid, stop_at="sealed")
    c.add_replace_file(target, b"hello")
    with pytest.raises(RC.StopPoint) as exc:
        c.run()
    assert exc.value.where == "sealed"
    RC.recover(sd)
    assert open(target, "rb").read() == b"hello"
    assert not os.path.exists(RC.commits_root(sd)) or os.listdir(RC.commits_root(sd)) == []


def test_f2_deep_replace_fsyncs_session_dir(tmp_path, monkeypatch):
    sd = _session(tmp_path)
    deep = os.path.join(sd, "a", "b", "c", "deep.txt")
    recorded = set()
    real_fsync = RC.fsync_dir_strict

    def _recording_fsync(directory):
        recorded.add(directory)
        return real_fsync(directory)

    monkeypatch.setattr(RC, "fsync_dir_strict", _recording_fsync)
    c = RC.begin(sd, "deep", commit_id="9" * 32)
    c.add_replace_file(deep, b"staged-bytes")
    c.run()
    assert open(deep, "rb").read() == b"staged-bytes"
    assert not os.path.exists(RC.commits_root(sd)) or os.listdir(RC.commits_root(sd)) == []
    session_real = os.path.realpath(sd)
    assert session_real in recorded
    assert os.path.join(session_real, "a") in recorded
    assert os.path.join(session_real, "a", "b") in recorded
    assert os.path.join(session_real, "a", "b", "c") in recorded


def test_f3_single_apply_parts_census():
    source = open(os.path.join(_LIB, "round_commit.py"), encoding="utf-8").read()
    tree = ast.parse(source)
    apply_helpers = {
        "_apply_replace_file", "_apply_journal_append", "_apply_external_sidecar",
    }
    appliers = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        called = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                if child.func.id in apply_helpers:
                    called.add(child.func.id)
        if called == apply_helpers:
            appliers.add(node.name)
    assert appliers == {"_apply_parts"}


def test_f5_unsealed_discard_clean(tmp_path):
    sd = _session(tmp_path)
    c = _two_replace_commit(sd, stop_at="staged", commit_id="6" * 32)
    with pytest.raises(RC.StopPoint):
        c.run()
    result = RC.recover(sd)
    assert result["discarded"] == ["6" * 32]
    assert not os.path.exists(os.path.join(sd, "one.txt"))


def test_f5_unsealed_discard_rmtree_failure(tmp_path, monkeypatch):
    sd = _session(tmp_path)
    c = _two_replace_commit(sd, stop_at="staged", commit_id="7" * 32)
    with pytest.raises(RC.StopPoint):
        c.run()
    real_rmtree = shutil.rmtree

    def _boom(path, *args, **kwargs):
        raise OSError(13, "nope")

    monkeypatch.setattr(RC.shutil, "rmtree", _boom)
    with pytest.raises(RC.CommitRefused) as exc:
        RC.recover(sd)
    assert exc.value.reason == "commit-cleanup-failed"


def test_f6_commit_id_collision(tmp_path):
    sd = _session(tmp_path)
    cid = "8" * 32
    c1 = RC.begin(sd, "first", commit_id=cid, stop_at="sealed")
    c1.add_replace_file(os.path.join(sd, "one.txt"), b"first")
    with pytest.raises(RC.StopPoint):
        c1.run()
    intent_path = os.path.join(RC.commits_root(sd), cid, "intent.json")
    intent_bytes = open(intent_path, "rb").read()
    c2 = RC.begin(sd, "second", commit_id=cid)
    c2.add_replace_file(os.path.join(sd, "two.txt"), b"second")
    with pytest.raises(RC.CommitRefused) as exc:
        c2.run()
    assert exc.value.reason == "commit-id-collision"
    assert exc.value.detail == cid
    assert open(intent_path, "rb").read() == intent_bytes


# --- FIX-3 review round 1 (#918) -------------------------------------------------------------

def test_r1_stage_fsyncs_parts_dir_before_sealed(tmp_path, monkeypatch):
    sd = _session(tmp_path)
    recorded = []
    sealed_seen = []
    real_fsync = RC.fsync_dir_strict
    commit_dir = os.path.join(RC.commits_root(sd), COMMIT_ID)
    parts_dir = os.path.join(commit_dir, RC._PARTS)
    sealed_path = os.path.join(commit_dir, RC._SEALED)

    def _recording_fsync(directory):
        recorded.append(directory)
        sealed_seen.append(os.path.exists(sealed_path))
        return real_fsync(directory)

    monkeypatch.setattr(RC, "fsync_dir_strict", _recording_fsync)
    c = _two_replace_commit(sd)
    c.run()
    assert parts_dir in recorded
    parts_idx = recorded.index(parts_dir)
    assert sealed_seen[parts_idx] is False


def test_r2_ensure_parent_fsyncs_parent_after_child_created(tmp_path, monkeypatch):
    sd = _session(tmp_path)
    deep = os.path.join(sd, "a", "b", "c", "deep.txt")
    created = []
    fsync_events = []
    real_fsync = RC.fsync_dir_strict
    real_makedirs = os.makedirs

    def _tracking_makedirs(path, *args, **kwargs):
        real_makedirs(path, *args, **kwargs)
        created.append(os.path.realpath(path))

    def _recording_fsync(directory):
        directory = os.path.realpath(directory)
        fsync_events.append((directory, list(created)))
        return real_fsync(directory)

    monkeypatch.setattr(os, "makedirs", _tracking_makedirs)
    monkeypatch.setattr(RC, "fsync_dir_strict", _recording_fsync)
    c = RC.begin(sd, "deep", commit_id="9" * 32)
    c.add_replace_file(deep, b"staged-bytes")
    c.run()

    session_real = os.path.realpath(sd)
    new_dirs = [os.path.join(session_real, "a"),
                os.path.join(session_real, "a", "b"),
                os.path.join(session_real, "a", "b", "c")]
    for new_dir in new_dirs:
        parent = os.path.dirname(new_dir)
        assert any(directory == parent and new_dir in seen_created
                   for directory, seen_created in fsync_events), (
            "parent %r not fsynced after child %r existed" % (parent, new_dir))


def test_r6_stage_oserror_becomes_commit_staging_failed(tmp_path, monkeypatch):
    sd = _session(tmp_path)
    real_fsync = os.fsync

    def _boom(fd):
        raise OSError(28, "no space left on device")

    monkeypatch.setattr(os, "fsync", _boom)
    c = _two_replace_commit(sd, commit_id="c" * 32)
    with pytest.raises(RC.CommitRefused) as exc:
        c.run()
    assert exc.value.reason == "commit-staging-failed"
    result = RC.recover(sd)
    assert "c" * 32 in result["discarded"]
    assert not os.path.exists(os.path.join(sd, "one.txt"))


# --- targetKind sidecar recovery (#1196 WO-A) -------------------------------------------------

def test_target_kind_sidecar_round_trips_intent_and_resolves_on_recovery(tmp_path):
  sd = _session(tmp_path)
  target = str(tmp_path / "records.json")

  def _resolve():
      return target

  c = RC.begin(sd, "kind-sidecar", commit_id="1" * 32, stop_at="sealed")
  c.add_external_sidecar(b'{"round":1}', _resolve, target_kind="round-records")
  with pytest.raises(RC.StopPoint):
      c.run()
  intent_path = os.path.join(RC.commits_root(sd), "1" * 32, "intent.json")
  intent = json.loads(open(intent_path, encoding="utf-8").read())
  assert intent["parts"][0]["targetKind"] == "round-records"

  def _resolver_for(part_spec):
      if part_spec.get("targetKind") == "round-records":
          return _resolve
      return None

  RC.recover(sd, sidecar_resolver_for=_resolver_for)
  assert open(target, "rb").read() == b'{"round":1}'


def test_target_kind_sidecar_refuses_without_sidecar_resolver_for(tmp_path):
  sd = _session(tmp_path)
  fallback = str(tmp_path / "fallback.json")

  def _resolve():
      return fallback

  c = RC.begin(sd, "kind-refuse-none", commit_id="2" * 32, stop_at="sealed")
  c.add_external_sidecar(b"data", _resolve, target_kind="review-receipt")
  with pytest.raises(RC.StopPoint):
      c.run()
  with pytest.raises(RC.CommitRefused) as exc:
      RC.recover(sd, sidecar_target=lambda: fallback)
  assert exc.value.reason == "sidecar-target-unresolvable"
  assert not os.path.exists(fallback)


def test_target_kind_sidecar_refuses_when_resolver_returns_none(tmp_path):
  sd = _session(tmp_path)
  target = str(tmp_path / "records.json")

  c = RC.begin(sd, "kind-refuse-null", commit_id="3" * 32, stop_at="sealed")
  c.add_external_sidecar(b"data", lambda: target, target_kind="round-records")
  with pytest.raises(RC.StopPoint):
      c.run()

  def _resolver_for(part_spec):
      if part_spec.get("targetKind") == "round-records":
          return None
      return lambda: target

  with pytest.raises(RC.CommitRefused) as exc:
      RC.recover(sd, sidecar_resolver_for=_resolver_for)
  assert exc.value.reason == "sidecar-target-unresolvable"
  assert not os.path.exists(target)


def test_sidecar_without_target_kind_recovers_via_sidecar_target(tmp_path):
  sd = _session(tmp_path)
  sidecar = str(tmp_path / "legacy.json")

  def _resolve():
      return sidecar

  c = RC.begin(sd, "legacy-sidecar", commit_id="4" * 32, stop_at="sealed")
  c.add_external_sidecar(b'{"legacy":true}', _resolve)
  with pytest.raises(RC.StopPoint):
      c.run()
  intent_path = os.path.join(RC.commits_root(sd), "4" * 32, "intent.json")
  intent = json.loads(open(intent_path, encoding="utf-8").read())
  assert "targetKind" not in intent["parts"][0]
  RC.recover(sd, sidecar_target=_resolve)
  assert open(sidecar, "rb").read() == b'{"legacy":true}'


def test_two_target_kind_sidecars_land_on_distinct_targets(tmp_path):
  sd = _session(tmp_path)
  records = str(tmp_path / "records.json")
  receipt = str(tmp_path / "receipt.json")

  def _records():
      return records

  def _receipt():
      return receipt

  c = RC.begin(sd, "dual-sidecar", commit_id="5" * 32, stop_at="sealed")
  c.add_external_sidecar(b'{"kind":"records"}', _records, target_kind="round-records")
  c.add_external_sidecar(b'{"kind":"receipt"}', _receipt, target_kind="review-receipt")
  with pytest.raises(RC.StopPoint):
      c.run()

  def _resolver_for(part_spec):
      kind = part_spec.get("targetKind")
      if kind == "round-records":
          return _records
      if kind == "review-receipt":
          return _receipt
      return None

  RC.recover(sd, sidecar_resolver_for=_resolver_for)
  assert open(records, "rb").read() == b'{"kind":"records"}'
  assert open(receipt, "rb").read() == b'{"kind":"receipt"}'
