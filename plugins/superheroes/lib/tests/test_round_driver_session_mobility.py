"""Layer 2i session mobility — the relocate verb (#1272)."""
import importlib.util
import json
import os
import shutil
import subprocess

import pytest

RC = None  # set after RD loads

_LIB = os.path.join(os.path.dirname(__file__), os.pardir)
_SPEC = importlib.util.spec_from_file_location(
    "round_driver", os.path.join(_LIB, "round_driver.py"))
RD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RD)
RC = RD.round_commit

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
    subprocess.check_call(["git", "-C", root_a, "worktree", "add", "-q", "-b", "mobility-b", root_b, "HEAD"])
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


def _stop_at_kind(monkeypatch, kind, stop_at, n=0):
    real = RD.round_commit.begin
    counts = {}

    def wrapper(session_dir, commit_kind, **kw):
        idx = counts.get(commit_kind, 0)
        if commit_kind == kind and idx == n:
            kw["stop_at"] = stop_at
        counts[commit_kind] = idx + 1
        return real(session_dir, commit_kind, **kw)

    monkeypatch.setattr(RD.round_commit, "begin", wrapper)


def _commits_empty(session_dir):
    root = RC.commits_root(session_dir)
    return not os.path.exists(root) or os.listdir(root) == []


def _snapshot_relocate(session_dir):
    meta_path = os.path.join(session_dir, "meta.json")
    state_path = os.path.join(session_dir, RD.STATE_FILE)
    journal_path = os.path.join(session_dir, RD.JOURNAL_FILE)
    return {
        "meta": _read_bytes(meta_path),
        "state": _read_bytes(state_path),
        "journal": _read_bytes(journal_path),
    }


def _assert_relocate_agree(session_dir, before, relocated_row):
    snap = _snapshot_relocate(session_dir)
    assert snap["meta"] != before["meta"]
    assert snap["state"] != before["state"]
    assert snap["journal"].startswith(before["journal"])
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    assert meta["repoRoot"] == relocated_row["newRoot"]
    assert state["config"]["repoRoot"] == relocated_row["newRoot"]
    row = next(r for r in reversed(_journal_rows(session_dir))
               if r.get("outcome") == "relocated")
    for field in _RELOCATED_FIELDS:
        assert field in row


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


# bite-proof: G19 — the state.config.repoRoot rewrite bites on the new checkout's config
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
    # bite-proof: G4 — terminal-session check bites on the terminal-state refusal
    ("relocate-session-terminal", "terminal"),
    # bite-proof: G13 — target HEAD vs recorded head compare bites on a moved-ahead target
    ("relocate-head-mismatch", "head_mismatch"),
    # bite-proof: G10 — base-mismatch bites on meta.baseRef vs config.baseRef disagreeing
    ("relocate-base-mismatch", "base_mismatch"),
    # bite-proof: G9 — repo-mismatch bites on origin vs recorded baseRepo disagreeing
    ("relocate-repo-mismatch", "repo_mismatch"),
    # bite-proof: G8 — repo-unverifiable bites on a missing baseRepo
    ("relocate-repo-unverifiable", "repo_unverifiable"),
    # bite-proof: G12a — meta_has != cfg_has bites when only one FIX_FOLD_HEAD copy is set
    ("relocate-head-ambiguous", "head_ambiguous"),
    # bite-proof: G5 — target-not-toplevel realpath-equality check bites on a non-toplevel target
    ("relocate-target-not-toplevel", "not_toplevel"),
    # bite-proof: G7 — same-checkout check bites when target equals the recorded checkout
    ("relocate-same-checkout", "same_checkout"),
    # bite-proof: G14 — records-path-bound check bites when recordsPath lies inside the old root
    ("relocate-records-path-bound", "records_bound"),
    # bite-proof: G17 — the session lock bites on a held lock refusing relocate
    ("relocate-locked", "locked"),
    # bite-proof: G3 — loop-state unreadable check bites when loop-state.json is missing
    ("relocate-session-unreadable", "unreadable"),
    # bite-proof: G6 — session-dir-moved check bites when invoked from a copied session dir
    ("relocate-session-dir-moved", "session_dir_moved"),
    # bite-proof: G1a — repoRoot presence/type check bites when repoRoot is missing
    ("relocate-session-unreadable", "unreadable_no_repo_root"),
    # bite-proof: G1b — repoRoot absolute check bites when repoRoot is a relative path
    ("relocate-session-unreadable", "unreadable_relative_repo_root"),
    # bite-proof: G2 — sessionDir presence/type check bites when sessionDir is missing
    ("relocate-session-unreadable", "unreadable_no_session_dir"),
    # relative sessionDir must refuse before cwd-dependent binding
    ("relocate-session-unreadable", "unreadable_relative_session_dir"),
    # whitespace-only sessionDir
    ("relocate-session-unreadable", "unreadable_whitespace_session_dir"),
    # detached target cannot carry the scope marker
    ("relocate-target-detached", "target_detached"),
    # bite-proof: G15 — target marker foreign bites when the target marker names another session
    ("relocate-target-marker-foreign", "target_marker_foreign"),
    # bite-proof: G16 — target marker unparseable bites on non-JSON marker content
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
    "relocate-session-unreadable-relative-session-dir",
    "relocate-session-unreadable-whitespace-session-dir",
    "relocate-target-detached",
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
    elif setup == "unreadable_relative_session_dir":
        meta = json.load(open(meta_path, encoding="utf-8"))
        meta["sessionDir"] = os.path.basename(session_dir)
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
    elif setup == "unreadable_whitespace_session_dir":
        meta = json.load(open(meta_path, encoding="utf-8"))
        meta["sessionDir"] = "   "
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
    elif setup == "target_detached":
        root_c = str(tmp_path / "repo_c")
        subprocess.check_call(
            ["git", "-C", repo["root_a"], "worktree", "add", "-q", "--detach", root_c, repo["head"]])
        target = subprocess.check_output(
            ["git", "-C", root_c, "rev-parse", "--show-toplevel"], text=True).strip()
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


# bite-proof: G13 — target HEAD vs recorded head compare bites on a moved-ahead target
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


# bite-proof: G12b — meta_key != cfg_key bites when both FIX_FOLD_HEAD copies are set and disagree
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


def test_relocate_refuses_inflight_fixer(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    meta_path = os.path.join(session_dir, "meta.json")
    state_path = os.path.join(session_dir, RD.STATE_FILE)
    ok, state = RD.load_state(session_dir)
    state["step"] = RD.P_FIXER
    state["pending"] = {"action": RD.P_FIXER, "round": 1, "phase": RD.P_FIXER, "attempt": 0,
                        "payload": {}}
    RD.save_state(session_dir, state)
    meta_before = _read_bytes(meta_path)
    state_before = _read_bytes(state_path)
    rc, out = _relocate(session_dir, repo["root_b"], capsys)
    assert rc == 1
    assert out["reason"] == "relocate-inflight-fixer"
    assert _read_bytes(meta_path) == meta_before
    assert _read_bytes(state_path) == state_before
    assert not os.path.lexists(_marker_path(repo["root_b"]))


# bite-proof: G15b — a claimed target refuses a second session
def test_relocate_second_claimant_refused_after_first_claims_the_target(tmp_path, capsys):
    """Sequential claim-then-claim: the second session is refused and the marker keeps the first. Concurrent claims are not tested (relocate is single-actor)."""
    repo = _mobility_repo(tmp_path)
    sess1 = _mobility_session(tmp_path, repo, session_name="session1")
    sess2 = _mobility_session(tmp_path, repo, session_name="session2")
    rc1, out1 = _relocate(sess1["session_dir"], repo["root_b"], capsys)
    assert rc1 == 0
    assert out1["ok"] is True
    marker_path = _marker_path(repo["root_b"])
    marker = json.load(open(marker_path, encoding="utf-8"))
    assert marker["sessionDir"] == os.path.realpath(sess1["session_dir"])
    meta_path2 = os.path.join(sess2["session_dir"], "meta.json")
    state_path2 = os.path.join(sess2["session_dir"], RD.STATE_FILE)
    meta_before2 = _read_bytes(meta_path2)
    state_before2 = _read_bytes(state_path2)
    marker_before = _read_bytes(marker_path)
    rc2, out2 = _relocate(sess2["session_dir"], repo["root_b"], capsys)
    assert rc2 == 1
    assert out2["reason"] == "relocate-target-marker-foreign"
    assert _read_bytes(marker_path) == marker_before
    assert _read_bytes(meta_path2) == meta_before2
    assert _read_bytes(state_path2) == state_before2


def test_relocate_target_marker_idempotent_retry(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    subprocess.check_call(["git", "-C", repo["root_b"], "checkout", "-q", "-b", "mobility-retry"])
    marker_path = _marker_path(repo["root_b"])
    claim = RD._relocate_target_marker_content(
        session_dir, repo["root_b"], "mobility-retry")
    os.makedirs(os.path.dirname(marker_path), exist_ok=True)
    with open(marker_path, "w", encoding="utf-8") as fh:
        json.dump(claim, fh)
    rc, out = _relocate(session_dir, repo["root_b"], capsys)
    assert rc == 0
    assert out["ok"] is True
    marker = json.load(open(marker_path, encoding="utf-8"))
    assert marker["sessionDir"] == os.path.realpath(session_dir)
    assert marker["branch"] == "mobility-retry"


def test_relocate_target_marker_stale_branch_refreshed(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    subprocess.check_call(["git", "-C", repo["root_b"], "checkout", "-q", "-b", "branch-a"])
    marker_path = _marker_path(repo["root_b"])
    stale = RD._relocate_target_marker_content(session_dir, repo["root_b"], "branch-a")
    os.makedirs(os.path.dirname(marker_path), exist_ok=True)
    with open(marker_path, "w", encoding="utf-8") as fh:
        json.dump(stale, fh)
    subprocess.check_call(["git", "-C", repo["root_b"], "checkout", "-q", "-b", "branch-b"])
    rc, out = _relocate(session_dir, repo["root_b"], capsys)
    assert rc == 0
    assert out["ok"] is True
    marker = json.load(open(marker_path, encoding="utf-8"))
    assert marker["branch"] == "branch-b"
    assert marker["repoRoot"] == repo["root_b"]


def test_relocate_claim_write_failure_leaves_no_marker(tmp_path, monkeypatch):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    marker_path = _marker_path(repo["root_b"])
    branch = subprocess.check_output(
        ["git", "-C", repo["root_b"], "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    content = RD._relocate_target_marker_content(session_dir, repo["root_b"], branch)
    real_open = open

    def failing_open(path, *args, **kwargs):
        if str(path).endswith(".claim.tmp"):
            raise OSError("simulated write failure")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)
    ok, created, reason = RD._relocate_claim_target_marker(marker_path, content,
                                                           os.path.realpath(session_dir))
    assert not ok
    assert reason == "unwritable"
    assert not os.path.lexists(marker_path)


def test_relocate_commit_refused_removes_claimed_marker(tmp_path, capsys, monkeypatch):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    subprocess.check_call(["git", "-C", repo["root_b"], "checkout", "-q", "-b", "mobility-refuse"])
    marker_path = _marker_path(repo["root_b"])

    def refuse_run(self):
        raise RD.round_commit.CommitRefused("test-refusal")

    monkeypatch.setattr(RD.round_commit.Commit, "run", refuse_run)
    rc, out = _relocate(session_dir, repo["root_b"], capsys)
    assert rc == 1
    assert not out.get("ok")
    assert not os.path.lexists(marker_path)


@pytest.mark.parametrize("stop_at", ["staged", "sealed", "part:0"])
def test_relocate_crash_matrix(tmp_path, capsys, monkeypatch, stop_at):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    subprocess.check_call(["git", "-C", repo["root_b"], "checkout", "-q", "-b", "mobility-crash"])
    before = _snapshot_relocate(session_dir)
    _stop_at_kind(monkeypatch, "relocate", stop_at)
    with pytest.raises(RC.StopPoint):
        RD.cmd_relocate(session_dir, repo["root_b"], "tester")
    RC.recover(session_dir)
    if stop_at == "staged":
        after = _snapshot_relocate(session_dir)
        assert after == before
        rc, out = _relocate(session_dir, repo["root_b"], capsys)
        assert rc == 0
        assert out["ok"] is True
    else:
        _assert_relocate_agree(session_dir, before, {"newRoot": repo["root_b"]})
    assert _commits_empty(session_dir)
    rc_after = RD.main(["next", "--session-dir", session_dir, "--repo-root", repo["root_b"]])
    assert rc_after == 0


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


# bite-proof: G11 — resolved_pin is None bites on an unresolvable base pin (UNPROVEN — see record)
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


def test_relocate_marker_retirement_survives_interleaved_replacement(tmp_path, monkeypatch):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    other_dir = str(tmp_path / "other_session")
    os.makedirs(other_dir, exist_ok=True)
    marker_a = _marker_path(repo["root_a"])
    ours = RD._relocate_target_marker_content(session_dir, repo["root_a"], repo["branch"])
    os.makedirs(os.path.dirname(marker_a), exist_ok=True)
    with open(marker_a, "w", encoding="utf-8") as fh:
        json.dump(ours, fh)
    real_rename = os.rename

    def racing_rename(src, dst):
        result = real_rename(src, dst)
        if src == marker_a and dst == marker_a + ".retire.tmp":
            replacement = {
                "schema": "review-session/1",
                "sessionDir": os.path.realpath(other_dir),
                "startedAt": "2026-01-01T00:00:00Z",
                "repoRoot": repo["root_a"],
                "branch": repo["branch"],
            }
            RD.round_commit.atomic_write_bytes(
                marker_a, RD._canonical(replacement).encode("utf-8"))
        return result

    monkeypatch.setattr(os, "rename", racing_rename)
    outcome = RD._retire_relocate_marker(repo["root_a"], session_dir)
    assert outcome == "retired"
    surviving = json.load(open(marker_a, encoding="utf-8"))
    assert surviving["sessionDir"] == os.path.realpath(other_dir)
    assert not os.path.exists(marker_a + ".retire.tmp")


def test_relocate_post_commit_crash_repaired_by_same_target_retry(tmp_path, capsys, monkeypatch):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    subprocess.check_call(["git", "-C", repo["root_b"], "checkout", "-q", "-b", "mobility-repair"])
    calls = {"n": 0}
    real_retire = RD._retire_relocate_marker

    def retire_once(old_root, session_dir_arg):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated post-commit crash")
        return real_retire(old_root, session_dir_arg)

    monkeypatch.setattr(RD, "_retire_relocate_marker", retire_once)
    with pytest.raises(RuntimeError):
        RD.cmd_relocate(session_dir, repo["root_b"], "tester")
    assert os.path.isfile(_marker_path(repo["root_a"]))
    assert os.path.isfile(_marker_path(repo["root_b"]))
    rc, out = _relocate(session_dir, repo["root_b"], capsys)
    assert rc == 0
    assert out["ok"] is True
    assert out.get("repaired") is True
    assert out["markerRetirement"] == "retired"
    assert not os.path.isfile(_marker_path(repo["root_a"]))


# bite-proof: G20 — the not-ours ownership check bites on a foreign marker's sessionDir
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


# bite-proof: G7 — same-checkout check bites even invoked from the recorded session dir
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


# bite-proof: G6 — session-dir-moved check bites before the same-checkout check (ordering axis)
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


# bite-proof: G18 — rewritten-only mutation bites on any extra non-checkout key rewrite
def test_relocate_rewritten_keys_are_exactly_the_checkout_keys(tmp_path, capsys):
    repo = _mobility_repo(tmp_path)
    sess = _mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    _, out = _relocate(session_dir, repo["root_b"], capsys)
    assert out["ok"] is True
    assert out["relocated"]["rewritten"] == sorted(
        ["meta.branch", "meta.repoRoot", "state.config.repoRoot"])
