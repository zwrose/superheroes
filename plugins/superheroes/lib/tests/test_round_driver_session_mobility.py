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
import store_core as SC  # noqa: E402

_RELOCATED_FIELDS = (
    "oldRoot", "newRoot", "oldBranch", "newBranch",
    "sessionDir", "head", "base", "by", "at", "rewritten",
)


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


def _session_file_snapshot(session_dir):
    snap = {}
    for dirpath, _dirnames, filenames in os.walk(session_dir):
        for name in filenames:
            path = os.path.join(dirpath, name)
            relpath = os.path.relpath(path, session_dir)
            snap[relpath] = _read_bytes(path)
    return snap


def _is_driver_scratch_relpath(relpath):
    base = os.path.basename(relpath)
    if base == RR.LOCK_FILE:
        return True
    if base.startswith(".cleanup-"):
        return True
    if ".commit-" in base and base.endswith(".tmp"):
        return True
    if relpath == "commits" or relpath.startswith("commits" + os.sep):
        return True
    return False


def _seed_pending_verify_landing(session_dir):
    ok, state = RD.load_state(session_dir)
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
    RD.save_state(session_dir, state)
    return payload["verify"]["landingPath"]


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
    assert "oldSessionDir" not in row
    assert "newSessionDir" not in row


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
    ("relocate-session-dir-moved", "session_dir_moved"),
    ("relocate-session-unreadable", "unreadable_no_repo_root"),
    ("relocate-session-unreadable", "unreadable_relative_repo_root"),
    ("relocate-session-unreadable", "unreadable_no_session_dir"),
    ("relocate-target-marker-foreign", "target_marker_foreign"),
    ("relocate-target-marker-foreign", "target_marker_not_json"),
], ids=[
    "relocate-session-terminal",
    "relocate-head-mismatch",
    "relocate-base-mismatch",
    "relocate-repo-mismatch",
    "relocate-repo-unverifiable",
    "relocate-head-ambiguous",
    "relocate-target-not-toplevel",
    "relocate-same-checkout",
    "relocate-records-path-bound",
    "relocate-locked",
    "relocate-session-unreadable-state-missing",
    "relocate-session-dir-moved",
    "relocate-session-unreadable-no-repo-root",
    "relocate-session-unreadable-relative-repo-root",
    "relocate-session-unreadable-no-session-dir",
    "relocate-target-marker-foreign",
    "relocate-target-marker-not-json",
])
def test_relocate_refusal_tokens(tmp_path, capsys, reason, setup):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    meta_path = os.path.join(session_dir, "meta.json")
    state_path = os.path.join(session_dir, RD.STATE_FILE)
    target = repo["root_b"]
    marker_path = None
    marker_before = None
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
    elif setup == "session_dir_moved":
        session_dir2 = str(tmp_path / "session2")
        shutil.copytree(session_dir, session_dir2)
        session_dir = session_dir2
        meta_path = os.path.join(session_dir, "meta.json")
        state_path = os.path.join(session_dir, RD.STATE_FILE)
    elif setup == "unreadable_no_repo_root":
        meta = json.load(open(meta_path, encoding="utf-8"))
        meta.pop("repoRoot", None)
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
    elif setup == "unreadable_relative_repo_root":
        meta = json.load(open(meta_path, encoding="utf-8"))
        meta["repoRoot"] = "repo_a"
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
    elif setup == "unreadable_no_session_dir":
        meta = json.load(open(meta_path, encoding="utf-8"))
        meta.pop("sessionDir", None)
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
    elif setup == "target_marker_foreign":
        other_dir = str(tmp_path / "other_session")
        os.makedirs(other_dir, exist_ok=True)
        marker_path = _marker_path(target)
        os.makedirs(os.path.dirname(marker_path), exist_ok=True)
        other_marker = {
            "schema": "review-session/1",
            "sessionDir": os.path.realpath(other_dir),
            "startedAt": "2026-01-01T00:00:00Z",
            "repoRoot": target,
            "branch": repo["branch"],
        }
        with open(marker_path, "w", encoding="utf-8") as fh:
            json.dump(other_marker, fh)
        marker_before = _read_bytes(marker_path)
    elif setup == "target_marker_not_json":
        marker_path = _marker_path(target)
        os.makedirs(os.path.dirname(marker_path), exist_ok=True)
        with open(marker_path, "w", encoding="utf-8") as fh:
            fh.write("not json")
        marker_before = _read_bytes(marker_path)
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
    if marker_path is not None:
        assert _read_bytes(marker_path) == marker_before


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


def test_relocate_marker_kept_when_target_detached(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    marker_a = _marker_path(repo["root_a"])
    assert os.path.isfile(marker_a)
    _, out = _relocate(session_dir, repo["root_b"], capsys)
    assert out["markerRetirement"] == "kept-no-target-marker"
    assert os.path.isfile(marker_a)


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


def test_relocate_same_checkout_refused_even_from_the_recorded_session_dir(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    meta_path = os.path.join(session_dir, "meta.json")
    state_path = os.path.join(session_dir, RD.STATE_FILE)
    meta_before = _read_bytes(meta_path)
    state_before = _read_bytes(state_path)
    rc, out = _relocate(session_dir, repo["root_a"], capsys)
    assert rc == 1
    assert out["reason"] == "relocate-same-checkout"
    assert _read_bytes(meta_path) == meta_before
    assert _read_bytes(state_path) == state_before


def test_relocate_session_dir_moved_refuses_before_same_checkout(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    session_dir2 = str(tmp_path / "session2")
    shutil.copytree(session_dir, session_dir2)
    meta_path = os.path.join(session_dir2, "meta.json")
    state_path = os.path.join(session_dir2, RD.STATE_FILE)
    meta_before = _read_bytes(meta_path)
    state_before = _read_bytes(state_path)
    rc, out = _relocate(session_dir2, repo["root_a"], capsys)
    assert rc == 1
    assert out["reason"] == "relocate-session-dir-moved"
    assert _read_bytes(meta_path) == meta_before
    assert _read_bytes(state_path) == state_before


def test_relocate_changes_nothing_else_in_the_session(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    landing_before = _seed_pending_verify_landing(session_dir)
    before_snap = _session_file_snapshot(session_dir)
    journal_path = os.path.join(session_dir, RD.JOURNAL_FILE)
    journal_before = _read_bytes(journal_path)
    _, out = _relocate(session_dir, repo["root_b"], capsys)
    assert out["ok"] is True
    after_snap = _session_file_snapshot(session_dir)
    rewritten = set(out["relocated"]["rewritten"])
    assert "state.pending.payload.verify.landingPath" not in rewritten
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    landing_after = state["pending"]["payload"]["verify"]["landingPath"]
    assert landing_after == landing_before
    assert _read_bytes(journal_path).startswith(journal_before)
    exempt = {"meta.json", RD.STATE_FILE, RD.JOURNAL_FILE}
    for relpath, content in before_snap.items():
        assert relpath in after_snap, "file removed: %s" % relpath
        if relpath not in exempt:
            assert after_snap[relpath] == content, "unexpected change: %s" % relpath
    for relpath in after_snap:
        if relpath in before_snap:
            continue
        assert _is_driver_scratch_relpath(relpath), "unexpected new file: %s" % relpath


def test_relocate_rewritten_keys_are_exactly_the_checkout_keys(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    _, out = _relocate(session_dir, repo["root_b"], capsys)
    assert out["ok"] is True
    assert out["relocated"]["rewritten"] == sorted(
        ["meta.branch", "meta.repoRoot", "state.config.repoRoot"])
