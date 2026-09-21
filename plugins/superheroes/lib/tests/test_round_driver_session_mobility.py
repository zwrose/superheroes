"""Layer 2i session mobility — the relocate verb (#1272)."""
import importlib.util
import json
import os
import shutil
import subprocess

import pytest

_LIB = os.path.join(os.path.dirname(__file__), os.pardir)
_SPEC = importlib.util.spec_from_file_location(
    "round_driver", os.path.join(_LIB, "round_driver.py"))
RD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RD)

import round_records as RR  # noqa: E402
import round_certification as RC  # noqa: E402
import store_core as SC  # noqa: E402

_RELOCATED_FIELDS = (
    "oldRoot", "newRoot", "oldBranch", "newBranch", "oldSessionDir", "newSessionDir",
    "head", "base", "by", "at", "rewritten",
)
_ANCHOR_PATH_ALLOWLIST = "state._ordersAnchors"


def _mobility_repo(tmp_path):
    root_a = str(tmp_path / "repo_a")
    os.makedirs(root_a, exist_ok=True)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=root_a)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=root_a)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=root_a)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=root_a)
    pin = subprocess.check_output(["git", "-C", root_a, "rev-parse", "HEAD"], text=True).strip()
    with open(os.path.join(root_a, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("a\n")
    subprocess.check_call(["git", "-C", root_a, "add", "f.py"])
    subprocess.check_call(["git", "-C", root_a, "commit", "-q", "-m", "change"])
    head = subprocess.check_output(["git", "-C", root_a, "rev-parse", "HEAD"], text=True).strip()
    subprocess.check_call(
        ["git", "-C", root_a, "remote", "add", "origin", "https://github.com/o/r.git"])
    root_b = str(tmp_path / "repo_b")
    subprocess.check_call(["git", "-C", root_a, "worktree", "add", "-q", "--detach", root_b, "HEAD"])
    toplevel_a = subprocess.check_output(
        ["git", "-C", root_a, "rev-parse", "--show-toplevel"], text=True).strip()
    toplevel_b = subprocess.check_output(
        ["git", "-C", root_b, "rev-parse", "--show-toplevel"], text=True).strip()
    branch = subprocess.check_output(
        ["git", "-C", root_a, "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    diff_text = subprocess.check_output(["git", "-C", root_a, "diff", "%s...HEAD" % pin], text=True)
    return {
        "root_a": toplevel_a,
        "root_b": toplevel_b,
        "pin": pin,
        "head": head,
        "branch": branch,
        "diff_text": diff_text,
    }


def _mobility_session(tmp_path, repo_info, session_name="session", bootstrap=True):
    session_dir = str(tmp_path / session_name)
    os.makedirs(session_dir, exist_ok=True)
    diff_path = os.path.join(session_dir, "round-1", "diff.txt")
    os.makedirs(os.path.dirname(diff_path), exist_ok=True)
    with open(diff_path, "w", encoding="utf-8") as fh:
        fh.write(repo_info["diff_text"])
    meta = {
        "mode": "branch",
        "baseRef": repo_info["pin"],
        "baseBranch": "main",
        "baseFetch": "fetched",
        "repoRoot": repo_info["root_a"],
        "headSha": repo_info["head"],
        "branch": repo_info["branch"],
        "sessionDir": os.path.realpath(session_dir),
    }
    with open(os.path.join(session_dir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    if bootstrap:
        rc = RD.main(["next", "--session-dir", session_dir, "--repo-root", repo_info["root_a"],
                      "--diff-path", diff_path, "--vendors", '["codex","cursor"]'])
        assert rc == 0, "bootstrap next must exit 0 with pending dispatch-panel"
    return {"session_dir": session_dir, "diff_path": diff_path, **repo_info}


def _cli_json(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _relocate(session_dir, repo_root, capsys, by="tester"):
    rc = RD.main(["relocate", "--session-dir", session_dir, "--repo-root", repo_root, "--by", by])
    return rc, _cli_json(capsys)


def _re_emit(session_dir, capsys, by="tester"):
    rc = RD.main(["re-emit", "--session-dir", session_dir, "--by", by])
    return rc, _cli_json(capsys)


def _stale_session(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    _relocate(session_dir, repo["root_b"], capsys)
    return repo, sess, session_dir


def _orders_dir(session_dir, rnd, phase):
    return os.path.join(session_dir, "round-%d" % rnd, "orders", phase)


def _collect_attempt_files(session_dir, rnd, phase, attempt):
    odir = _orders_dir(session_dir, rnd, phase)
    needle = ".a%d." % attempt
    paths = []
    if os.path.isdir(odir):
        for name in os.listdir(odir):
            if needle in name:
                paths.append(os.path.join(odir, name))
    return sorted(paths)


def _anchor_for(session_dir, rnd, phase, attempt):
    ok, state = RD.load_state(session_dir)
    return RD._orders_anchor(state, session_dir, rnd, phase, attempt)


def _read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _journal_rows(session_dir):
    return RD.read_journal(session_dir)


def _last_refused(session_dir, reason):
    for row in reversed(_journal_rows(session_dir)):
        if row.get("outcome") == "refused" and row.get("reason") == reason:
            return row
    return None


def _walk_strings(obj, prefix=""):
    if isinstance(obj, dict):
        for key, val in obj.items():
            child = "%s.%s" % (prefix, key) if prefix else key
            yield from _walk_strings(val, child)
    elif isinstance(obj, list):
        for idx, val in enumerate(obj):
            yield from _walk_strings(val, "%s[%d]" % (prefix, idx))
    elif isinstance(obj, str):
        yield prefix, obj


def _anchor_path_allowed(key_path):
    parts = key_path.split(".")
    if len(parts) < 4:
        return False
    return parts[0] == "state" and parts[1] == "_ordersAnchors" and parts[-1] == "path"


def _remove_dotted_path(root, dotted):
    parts = dotted.split(".")
    if parts[0] == "meta":
        parts = parts[1:]
        target = root.setdefault("meta", {})
    elif parts[0] == "state":
        parts = parts[1:]
        target = root.setdefault("state", {})
    else:
        return
    for part in parts[:-1]:
        if not isinstance(target, dict) or part not in target:
            return
        target = target[part]
    if isinstance(target, dict):
        target.pop(parts[-1], None)


def _snapshot_without_rewritten(meta_obj, state_obj, rewritten):
    snap = {"meta": json.loads(json.dumps(meta_obj)), "state": json.loads(json.dumps(state_obj))}
    for path in rewritten:
        _remove_dotted_path(snap, path)
    return snap


def _marker_path(repo_root):
    gitdir = SC.get_worktree_gitdir(repo_root)
    return os.path.join(gitdir, RD.SIDECAR_DIRNAME, "review-session.json")


def test_relocate_positive_and_next_from_new_checkout(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    rc_before = RD.main(["next", "--session-dir", session_dir, "--repo-root", repo["root_b"]])
    assert rc_before == 1
    out_before = _cli_json(capsys)
    assert out_before["ok"] is False
    assert out_before["reason"] == "base-repo-root-mismatch"
    rc, out = _relocate(session_dir, repo["root_b"], capsys)
    assert rc == 0
    assert out["ok"] is True
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    assert meta["repoRoot"] == repo["root_b"]
    assert state["config"]["repoRoot"] == repo["root_b"]
    target_branch = subprocess.check_output(
        ["git", "-C", repo["root_b"], "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    assert meta["branch"] == target_branch
    rc_after = RD.main(["next", "--session-dir", session_dir, "--repo-root", repo["root_b"]])
    assert rc_after == 0


def test_relocate_invariant_no_old_paths_survive(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    meta_before = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    state_before = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    _, out = _relocate(session_dir, repo["root_b"], capsys)
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    old_a = os.path.realpath(repo["root_a"])
    current_session = os.path.realpath(session_dir)
    for label, doc in (("meta", meta), ("state", state)):
        for key_path, value in _walk_strings(doc, label):
            if _anchor_path_allowed(key_path):
                continue
            if value == current_session:
                continue
            if value.startswith(old_a):
                pytest.fail("old path survived at %s: %s" % (key_path, value))
    snap_before = _snapshot_without_rewritten(meta_before, state_before, out["relocated"]["rewritten"])
    snap_after = _snapshot_without_rewritten(meta, state, out["relocated"]["rewritten"])
    assert snap_before == snap_after


def test_relocate_journal_appended_not_rewritten(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    journal_path = os.path.join(session_dir, RD.JOURNAL_FILE)
    before_bytes = _read_bytes(journal_path)
    _, out = _relocate(session_dir, repo["root_b"], capsys)
    after_bytes = _read_bytes(journal_path)
    assert after_bytes.startswith(before_bytes)
    row = next(r for r in reversed(_journal_rows(session_dir)) if r.get("outcome") == "relocated")
    for field in _RELOCATED_FIELDS:
        assert field in row


@pytest.mark.parametrize("reason,setup", [
    ("relocate-session-terminal", "terminal"),
    ("relocate-head-mismatch", "head_mismatch"),
    ("relocate-base-mismatch", "base_mismatch"),
    ("relocate-repo-mismatch", "repo_mismatch"),
    ("relocate-repo-unverifiable", "repo_unverifiable"),
    ("relocate-head-ambiguous", "head_ambiguous"),
    ("relocate-target-not-toplevel", "not_toplevel"),
    ("relocate-same-checkout", "same_checkout"),
    ("relocate-records-path-bound", "records_bound"),
    ("relocate-locked", "locked"),
    ("relocate-session-unreadable", "unreadable"),
])
def test_relocate_refusal_tokens(tmp_path, capsys, reason, setup):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    meta_path = os.path.join(session_dir, "meta.json")
    state_path = os.path.join(session_dir, RD.STATE_FILE)
    target = repo["root_b"]
    if setup == "terminal":
        ok, state = RD.load_state(session_dir)
        state["terminal"] = "converged"
        RD.save_state(session_dir, state)
    elif setup == "head_mismatch":
        subprocess.check_call(["git", "-C", repo["root_b"], "commit", "-q", "--allow-empty", "-m", "ahead"])
    elif setup == "base_mismatch":
        meta = json.load(open(meta_path, encoding="utf-8"))
        meta["baseRef"] = repo["head"]
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
    elif setup == "repo_mismatch":
        clone = str(tmp_path / "clone_b")
        subprocess.check_call(["git", "clone", "-q", repo["root_a"], clone])
        subprocess.check_call(
            ["git", "-C", clone, "remote", "set-url", "origin", "https://github.com/o/other.git"])
        target = subprocess.check_output(
            ["git", "-C", clone, "rev-parse", "--show-toplevel"], text=True).strip()
    elif setup == "repo_unverifiable":
        ok, state = RD.load_state(session_dir)
        state["config"].pop("baseRepo", None)
        RD.save_state(session_dir, state)
    elif setup == "head_ambiguous":
        meta = json.load(open(meta_path, encoding="utf-8"))
        meta[RD.FIX_FOLD_HEAD_KEY] = repo["head"]
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
    elif setup == "not_toplevel":
        target = os.path.join(repo["root_b"], "subdir")
        os.makedirs(target, exist_ok=True)
    elif setup == "same_checkout":
        target = repo["root_a"]
    elif setup == "records_bound":
        ok, state = RD.load_state(session_dir)
        bound = os.path.join(repo["root_a"], "records.json")
        with open(bound, "w", encoding="utf-8") as fh:
            fh.write("{}")
        state["config"]["recordsPath"] = bound
        RD.save_state(session_dir, state)
    elif setup == "locked":
        RR.atomic_write_json(RR.session_lock_path(session_dir),
                             {"pid": 424242, "createdAt": "2026-08-07T00:00:00"})
    elif setup == "unreadable":
        os.remove(state_path)
    meta_before = _read_bytes(meta_path)
    state_before = _read_bytes(state_path) if os.path.isfile(state_path) else None
    if setup == "not_toplevel":
        out = RD.cmd_relocate(session_dir, target, "tester")
        rc = 1 if not out.get("ok") else 0
    else:
        rc, out = _relocate(session_dir, target, capsys)
    assert rc == 1
    assert out["ok"] is False
    assert out["reason"] == reason
    refused = _last_refused(session_dir, reason)
    assert refused is not None
    assert _read_bytes(meta_path) == meta_before
    if state_before is not None:
        assert _read_bytes(state_path) == state_before


def test_relocate_refuses_target_ahead_of_recorded_head(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    subprocess.check_call(["git", "-C", repo["root_b"], "commit", "-q", "--allow-empty", "-m", "fix"])
    rc, out = _relocate(session_dir, repo["root_b"], capsys)
    assert rc == 1
    assert out["reason"] == "relocate-head-mismatch"


def test_relocate_honors_agreeing_fix_fold_head(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    subprocess.check_call(["git", "-C", repo["root_b"], "commit", "-q", "--allow-empty", "-m", "fix"])
    h2 = subprocess.check_output(["git", "-C", repo["root_b"], "rev-parse", "HEAD"], text=True).strip()
    meta_path = os.path.join(session_dir, "meta.json")
    meta = json.load(open(meta_path, encoding="utf-8"))
    meta[RD.FIX_FOLD_HEAD_KEY] = h2
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    ok, state = RD.load_state(session_dir)
    state["config"][RD.FIX_FOLD_HEAD_KEY] = h2
    RD.save_state(session_dir, state)
    rc, out = _relocate(session_dir, repo["root_b"], capsys)
    assert rc == 0
    assert out["ok"] is True
    assert out["relocated"]["head"] == h2


def test_relocate_refuses_when_fix_fold_head_copies_disagree(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    meta_path = os.path.join(session_dir, "meta.json")
    state_path = os.path.join(session_dir, RD.STATE_FILE)
    meta = json.load(open(meta_path, encoding="utf-8"))
    meta[RD.FIX_FOLD_HEAD_KEY] = repo["head"]
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    ok, state = RD.load_state(session_dir)
    state["config"][RD.FIX_FOLD_HEAD_KEY] = "a" * 40
    RD.save_state(session_dir, state)
    meta_before = _read_bytes(meta_path)
    state_before = _read_bytes(state_path)
    rc, out = _relocate(session_dir, repo["root_b"], capsys)
    assert rc == 1
    assert out["reason"] == "relocate-head-ambiguous"
    assert _read_bytes(meta_path) == meta_before
    assert _read_bytes(state_path) == state_before


def test_relocate_mid_fix_head_mismatch_at_setup_head(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    subprocess.check_call(["git", "-C", repo["root_b"], "commit", "-q", "--allow-empty", "-m", "fix"])
    h2 = subprocess.check_output(["git", "-C", repo["root_b"], "rev-parse", "HEAD"], text=True).strip()
    root_c = str(tmp_path / "repo_c")
    subprocess.check_call(
        ["git", "-C", repo["root_a"], "worktree", "add", "-q", "--detach", root_c, repo["head"]])
    target = subprocess.check_output(
        ["git", "-C", root_c, "rev-parse", "--show-toplevel"], text=True).strip()
    meta_path = os.path.join(session_dir, "meta.json")
    meta = json.load(open(meta_path, encoding="utf-8"))
    meta[RD.FIX_FOLD_HEAD_KEY] = h2
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    ok, state = RD.load_state(session_dir)
    state["config"][RD.FIX_FOLD_HEAD_KEY] = h2
    RD.save_state(session_dir, state)
    rc, out = _relocate(session_dir, target, capsys)
    assert rc == 1
    assert out["reason"] == "relocate-head-mismatch"


def test_relocate_pending_verify_landing_path_rewritten(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    session_dir2 = str(tmp_path / "session2")
    shutil.copytree(session_dir, session_dir2)
    ok, state = RD.load_state(session_dir2)
    pending = state.setdefault("pending", {})
    payload = pending.setdefault("payload", {})
    rnd, attempt = 1, 1
    verify_skey = RR.storage_key("verify")
    payload["verify"] = {
        "round": rnd,
        "attempt": attempt,
        "landingPath": RR.bare_payload_path(
            session_dir, rnd, "run-verify", verify_skey, attempt),
    }
    RD.save_state(session_dir2, state)
    _, out = _relocate(session_dir2, repo["root_b"], capsys)
    assert out["ok"] is True
    state = json.load(open(os.path.join(session_dir2, RD.STATE_FILE), encoding="utf-8"))
    landing = state["pending"]["payload"]["verify"]["landingPath"]
    expected = RR.bare_payload_path(session_dir2, rnd, "run-verify", verify_skey, attempt)
    assert landing == expected
    assert "state.pending.payload.verify.landingPath" in out["relocated"]["rewritten"]


def test_relocate_marker_retirement(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    subprocess.check_call(["git", "-C", repo["root_b"], "checkout", "-q", "-b", "mobility-marker"])
    _, out = _relocate(session_dir, repo["root_b"], capsys)
    assert out["markerRetirement"] == "retired"
    marker_b = _marker_path(repo["root_b"])
    assert os.path.isfile(marker_b)
    marker = json.load(open(marker_b, encoding="utf-8"))
    assert marker["sessionDir"] == os.path.realpath(session_dir)
    assert marker["repoRoot"] == repo["root_b"]
    assert not os.path.isfile(_marker_path(repo["root_a"]))
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    target_branch = subprocess.check_output(
        ["git", "-C", repo["root_b"], "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    assert meta["branch"] == target_branch


def test_re_emit_positive_after_relocate(tmp_path, capsys):
    repo, sess, session_dir = _stale_session(tmp_path, capsys)
    rnd, phase, old_attempt = 1, "dispatch-panel", 0
    a0_files = {p: _read_bytes(p) for p in _collect_attempt_files(session_dir, rnd, phase, old_attempt)}
    anchor0_before = _anchor_for(session_dir, rnd, phase, old_attempt)
    journal_path = os.path.join(session_dir, RD.JOURNAL_FILE)
    journal_before = _read_bytes(journal_path)
    rc, out = _re_emit(session_dir, capsys)
    assert rc == 0
    assert out["ok"] is True
    assert out["attempt"] == 1
    ok, state = RD.load_state(session_dir)
    assert state["pending"]["attempt"] == 1
    root_b = os.path.realpath(repo["root_b"])
    a1_files = _collect_attempt_files(session_dir, rnd, phase, 1)
    assert a1_files
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    assert os.path.realpath(meta["repoRoot"]) == root_b
    a0_md = next(p for p in a0_files if p.endswith(".md"))
    a1_md = next(p for p in a1_files if p.endswith(".md"))
    assert _read_bytes(a0_md) != _read_bytes(a1_md)
    for path, content in a0_files.items():
        assert _read_bytes(path) == content
    anchor0_after = _anchor_for(session_dir, rnd, phase, old_attempt)
    assert json.dumps(anchor0_after, sort_keys=True) == json.dumps(anchor0_before, sort_keys=True)
    anchor1 = _anchor_for(session_dir, rnd, phase, 1)
    assert anchor1["headSha"] == repo["head"]
    rows = _journal_rows(session_dir)
    superseded_idx = next(i for i, r in enumerate(rows)
                          if r.get("outcome") == "orders-superseded")
    emitted_idx = next(i for i, r in enumerate(rows)
                       if r.get("outcome") == "orders-emitted" and r.get("attempt") == 1
                       and r.get("cmd") == "re-emit")
    assert superseded_idx < emitted_idx
    superseded = rows[superseded_idx]
    emitted = rows[emitted_idx]
    assert superseded["supersededManifestSha256"] == anchor0_before["manifestSha256"]
    assert superseded["supersededOrderSha256"] == anchor0_before["orders"]
    assert _read_bytes(journal_path).startswith(journal_before)


def test_re_emit_certification_open_close(tmp_path, capsys):
    repo, sess, session_dir = _stale_session(tmp_path, capsys)
    rnd, phase = 1, "dispatch-panel"
    _re_emit(session_dir, capsys)
    unclosed, refusal = RC._journal_open_seats(RD.read_journal(session_dir), session_dir)
    assert refusal is None
    attempt0_keys = [k for k, _ in unclosed if k[2] == 0]
    assert not attempt0_keys
    attempt1_keys = [k for k, _ in unclosed if k[2] == 1 and k[0] == phase and k[1] == rnd]
    assert attempt1_keys
    manifest_path = RD._orders_manifest_path(session_dir, rnd, phase, 1)
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    expected_slots = len(manifest.get("seats") or {})
    assert len(attempt1_keys) == expected_slots


def test_re_emit_late_attempt0_landing_keeps_seat_open(tmp_path, capsys):
    repo, sess, session_dir = _stale_session(tmp_path, capsys)
    rnd, phase, old_attempt = 1, "dispatch-panel", 0
    _re_emit(session_dir, capsys)
    ok, state = RD.load_state(session_dir)
    roster, _ = RD._roster_of(session_dir, state, "re-emit", phase, rnd, old_attempt)
    first_seat = roster[0]
    slot = RR.storage_key(first_seat, 0)
    payload_path = RR.bare_payload_path(session_dir, rnd, phase, slot, old_attempt)
    os.makedirs(os.path.dirname(payload_path), exist_ok=True)
    with open(payload_path, "w", encoding="utf-8") as fh:
        fh.write("{}")
    unclosed, refusal = RC._journal_open_seats(RD.read_journal(session_dir), session_dir)
    assert refusal is None
    late_keys = [
        k for k, _ in unclosed
        if k[2] == old_attempt and k[0] == phase and k[1] == rnd and k[3] == first_seat
    ]
    assert len(late_keys) == 1


def test_relocate_same_checkout_moved_session_dir_keeps_marker(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    session_dir2 = str(tmp_path / "session2")
    shutil.copytree(session_dir, session_dir2)
    _, out = _relocate(session_dir2, repo["root_a"], capsys)
    assert out["ok"] is True
    marker = _marker_path(repo["root_a"])
    assert os.path.isfile(marker)
    marker_doc = json.load(open(marker, encoding="utf-8"))
    assert marker_doc["sessionDir"] == os.path.realpath(session_dir2)


def test_re_emit_cli_exit_codes(tmp_path, capsys):
    repo, sess, session_dir = _stale_session(tmp_path, capsys)
    rc_ok, out_ok = _re_emit(session_dir, capsys)
    assert rc_ok == 0 and out_ok["ok"] is True
    rc_refuse, out_refuse = _re_emit(session_dir, capsys)
    assert rc_refuse == 1 and out_refuse["ok"] is False


@pytest.mark.parametrize("reason,setup", [
    ("re-emit-not-stale", "not_stale"),
    ("re-emit-head-moved", "head_moved"),
    ("re-emit-attempt-has-results", "has_results"),
    ("re-emit-no-pending-order", "no_pending"),
    ("re-emit-no-anchor", "no_anchor"),
    ("re-emit-head-unresolved", "head_unresolved"),
    ("re-emit-locked", "locked"),
])
def test_re_emit_refusal_tokens(tmp_path, capsys, reason, setup):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    meta_path = os.path.join(session_dir, "meta.json")
    state_path = os.path.join(session_dir, RD.STATE_FILE)
    if setup == "not_stale":
        pass
    elif setup == "head_moved":
        _relocate(session_dir, repo["root_b"], capsys)
        subprocess.check_call(
            ["git", "-C", repo["root_b"], "commit", "-q", "--allow-empty", "-m", "ahead"])
    elif setup == "has_results":
        _relocate(session_dir, repo["root_b"], capsys)
        ok, state = RD.load_state(session_dir)
        rnd, phase, attempt = state["pending"]["round"], state["pending"]["phase"], 0
        roster, _ = RD._roster_of(session_dir, state, "re-emit", phase, rnd, attempt)
        slot = RR.storage_key(roster[0], 0)
        payload_path = RR.bare_payload_path(session_dir, rnd, phase, slot, attempt)
        os.makedirs(os.path.dirname(payload_path), exist_ok=True)
        with open(payload_path, "w", encoding="utf-8") as fh:
            fh.write("{}")
    elif setup == "no_pending":
        ok, state = RD.load_state(session_dir)
        state["pending"] = None
        RD.save_state(session_dir, state)
    elif setup == "no_anchor":
        _relocate(session_dir, repo["root_b"], capsys)
        ok, state = RD.load_state(session_dir)
        rnd, phase, attempt = state["pending"]["round"], state["pending"]["phase"], 0
        anchors = state.get("_ordersAnchors") or {}
        anchors.pop(RD._anchor_key(rnd, phase, attempt), None)
        state["_ordersAnchors"] = anchors
        RD.save_state(session_dir, state)
        manifest_path = RD._orders_manifest_path(session_dir, rnd, phase, attempt)
        aside = manifest_path + ".aside"
        os.rename(manifest_path, aside)
    elif setup == "head_unresolved":
        _relocate(session_dir, repo["root_b"], capsys)
        subprocess.check_call(["git", "-C", repo["root_a"], "worktree", "remove", "--force",
                               repo["root_b"]])
    elif setup == "locked":
        _relocate(session_dir, repo["root_b"], capsys)
        RR.atomic_write_json(RR.session_lock_path(session_dir),
                             {"pid": 424242, "createdAt": "2026-08-07T00:00:00"})
    meta_before = _read_bytes(meta_path)
    state_before = _read_bytes(state_path)
    rc, out = _re_emit(session_dir, capsys)
    assert rc == 1
    assert out["ok"] is False
    assert out["reason"] == reason
    refused = _last_refused(session_dir, reason)
    assert refused is not None
    assert _read_bytes(meta_path) == meta_before
    assert _read_bytes(state_path) == state_before


def test_relocate_invariant_moved_session_dir(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    session_dir2 = str(tmp_path / "session2")
    shutil.copytree(session_dir, session_dir2)
    meta2_path = os.path.join(session_dir2, "meta.json")
    _, out = _relocate(session_dir2, repo["root_b"], capsys)
    old_a = os.path.realpath(repo["root_a"])
    old_s = os.path.realpath(session_dir)
    current_s2 = os.path.realpath(session_dir2)
    state2 = json.load(open(os.path.join(session_dir2, RD.STATE_FILE), encoding="utf-8"))
    meta2 = json.load(open(meta2_path, encoding="utf-8"))
    assert meta2["sessionDir"] == current_s2
    assert "meta.sessionDir" in out["relocated"]["rewritten"]
    for label, doc in (("meta", meta2), ("state", state2)):
        for key_path, value in _walk_strings(doc, label):
            if _anchor_path_allowed(key_path):
                continue
            if value == current_s2:
                continue
            if value.startswith(old_a) or value.startswith(old_s + os.sep) or value == old_s:
                pytest.fail("old path survived at %s: %s" % (key_path, value))


def test_re_emit_after_session_dir_move_names_the_new_dir(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    session_dir2 = str(tmp_path / "session2")
    shutil.copytree(session_dir, session_dir2)
    _relocate(session_dir2, repo["root_b"], capsys)
    rnd, phase = 1, "dispatch-panel"
    a0_files_before = {
        p: _read_bytes(p) for p in _collect_attempt_files(session_dir2, rnd, phase, 0)
    }
    rc, out = _re_emit(session_dir2, capsys)
    assert rc == 0
    assert out["ok"] is True
    # Orders embed the bootstrap session path (not always os.path.realpath on macOS).
    # Prefix with os.sep so a path like /tmp/session does not match /tmp/session2.
    old_s_prefix = session_dir + os.sep
    a1_md_files = [p for p in _collect_attempt_files(session_dir2, rnd, phase, 1)
                   if p.endswith(".md")]
    assert a1_md_files
    for path in a1_md_files:
        content = _read_bytes(path)
        assert session_dir2.encode() in content
        assert old_s_prefix.encode() not in content
    for path, content in a0_files_before.items():
        assert _read_bytes(path) == content
    a0_md_files = [p for p in a0_files_before if p.endswith(".md")]
    for path in a0_md_files:
        assert old_s_prefix.encode() in _read_bytes(path)


def test_re_emit_refuses_when_a_result_is_recorded_in_the_journal(tmp_path, capsys):
    repo, sess, session_dir = _stale_session(tmp_path, capsys)
    ok, state = RD.load_state(session_dir)
    rnd, phase, attempt = state["pending"]["round"], state["pending"]["phase"], 0
    roster, _ = RD._roster_of(session_dir, state, "re-emit", phase, rnd, attempt)
    first_seat = roster[0]
    journal_path = os.path.join(session_dir, RD.JOURNAL_FILE)
    row = {
        "cmd": "record-result",
        "outcome": "recorded",
        "round": 1,
        "phase": "dispatch-panel",
        "attempt": 0,
        "seat": first_seat,
        "occurrence": 0,
    }
    with open(journal_path, "a", encoding="utf-8") as fh:
        # Bypass _journal_append on purpose — the seeded row stands in for a real record
        # and the revision-identity fields are irrelevant to this check.
        fh.write(json.dumps(row) + "\n")
    rc, out = _re_emit(session_dir, capsys)
    assert rc == 1
    assert out["ok"] is False
    assert out["reason"] == "re-emit-attempt-has-results"
    assert "journal:%s" % first_seat in out["names"]


def test_relocate_refuses_a_base_pin_that_does_not_resolve_in_the_target(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    meta_path = os.path.join(session_dir, "meta.json")
    state_path = os.path.join(session_dir, RD.STATE_FILE)
    bogus_pin = "1234567890abcdef" * 2 + "12345678"
    meta = json.load(open(meta_path, encoding="utf-8"))
    meta["baseRef"] = bogus_pin
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    ok, state = RD.load_state(session_dir)
    state["config"]["baseRef"] = bogus_pin
    RD.save_state(session_dir, state)
    meta_before = _read_bytes(meta_path)
    state_before = _read_bytes(state_path)
    rc, out = _relocate(session_dir, repo["root_b"], capsys)
    assert rc == 1
    assert out["reason"] == "relocate-base-mismatch"
    assert _read_bytes(meta_path) == meta_before
    assert _read_bytes(state_path) == state_before


def test_relocate_refuses_none_session_dir(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    meta_path = os.path.join(session_dir, "meta.json")
    state_path = os.path.join(session_dir, RD.STATE_FILE)
    meta = json.load(open(meta_path, encoding="utf-8"))
    meta["sessionDir"] = None
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    meta_before = _read_bytes(meta_path)
    state_before = _read_bytes(state_path)
    rc, out = _relocate(session_dir, repo["root_b"], capsys)
    assert rc == 1
    assert out["reason"] == "relocate-session-unreadable"
    assert _read_bytes(meta_path) == meta_before
    assert _read_bytes(state_path) == state_before


def test_relocate_marker_not_ours_left_alone(tmp_path):
    repo = _mobility_repo(tmp_path)
    other_dir = str(tmp_path / "other_session")
    os.makedirs(other_dir, exist_ok=True)
    other_marker = {
        "schema": "review-session/1",
        "sessionDir": os.path.realpath(other_dir),
        "startedAt": "2026-01-01T00:00:00Z",
        "repoRoot": repo["root_a"],
        "branch": repo["branch"],
    }
    marker_a = _marker_path(repo["root_a"])
    os.makedirs(os.path.dirname(marker_a), exist_ok=True)
    with open(marker_a, "w", encoding="utf-8") as fh:
        json.dump(other_marker, fh)
    outcome = RD._retire_relocate_marker(repo["root_a"], str(tmp_path / "session"))
    assert outcome == "not-ours"
    assert json.load(open(marker_a, encoding="utf-8"))["sessionDir"] == os.path.realpath(other_dir)
