"""Round-trip smoke for the head-content producer (#1271 layer 2, WO-A2)."""
import base64
import hashlib
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import round_driver as RD
import round_records


def _git_head(repo):
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _init_repo(tmp_path, files):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_bytes(content.encode("utf-8"))
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo, _git_head(repo)


def _session_dir(tmp_path, repo, head):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    meta = {"sessionId": "head-content-smoke", "headSha": head, "repoRoot": str(repo)}
    meta_path = session_dir / round_records.META_FILE
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
        fh.write("\n")
    return session_dir


def _load_blobs(session_dir):
    path = os.path.join(session_dir, RD.HEAD_CONTENT_BLOBS_FILE)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _read_row(blobs, path):
    for row in blobs.get("reads") or []:
        if row.get("path") == path:
            return row
    return None


def _independent_git_bytes(repo, head, path):
    proc = subprocess.run(
        ["git", "show", "%s:%s" % (head, path)],
        cwd=repo,
        check=True,
        capture_output=True,
        text=False,
    )
    return proc.stdout


def test_head_content_text_with_trailing_newline(tmp_path):
    content = b"hello world\n"
    repo, head = _init_repo(tmp_path, {"a.txt": content})
    session_dir = _session_dir(tmp_path, repo, head)
    RD._persist_head_content_blobs(
        str(session_dir), {"config": {"headSha": head}}, head_sha=head, paths=["a.txt"]
    )
    blobs = _load_blobs(session_dir)
    assert blobs["schema"] == "head-content-blobs/2"
    assert blobs["headSha"] == head
    assert "present" not in json.dumps(blobs)
    assert "fixCommits" not in blobs
    row = _read_row(blobs, "a.txt")
    assert row["readError"] is None
    independent = _independent_git_bytes(repo, head, "a.txt")
    assert row["contentDigest"] == hashlib.sha256(independent).hexdigest()
    assert row["bytes"] == len(independent)
    assert base64.b64decode(blobs["files"]["a.txt"]) == independent


def test_head_content_non_utf8_round_trips(tmp_path):
    content = b"\xff\xfe\xfd\x00binary"
    repo, head = _init_repo(tmp_path, {"b.bin": content})
    session_dir = _session_dir(tmp_path, repo, head)
    RD._persist_head_content_blobs(
        str(session_dir), {"config": {"headSha": head}}, head_sha=head, paths=["b.bin"]
    )
    blobs = _load_blobs(session_dir)
    row = _read_row(blobs, "b.bin")
    assert row["readError"] is None
    assert row["contentDigest"] == hashlib.sha256(content).hexdigest()
    assert base64.b64decode(blobs["files"]["b.bin"]) == content


def test_head_content_missing_path_is_failed_read(tmp_path):
    repo, head = _init_repo(tmp_path, {"exists.txt": b"ok\n"})
    session_dir = _session_dir(tmp_path, repo, head)
    RD._persist_head_content_blobs(
        str(session_dir),
        {"config": {"headSha": head}},
        head_sha=head,
        paths=["missing.py"],
    )
    blobs = _load_blobs(session_dir)
    row = _read_row(blobs, "missing.py")
    assert isinstance(row["readError"], str) and row["readError"]
    assert row["contentDigest"] is None
    assert row["bytes"] is None
    assert "missing.py" not in blobs.get("files", {})


def test_head_content_unresolved_head_is_failed_read(tmp_path):
    repo, head = _init_repo(tmp_path, {"c.txt": b"data\n"})
    session_dir = _session_dir(tmp_path, repo, head)
    bad_head = "deadbeef" * 5  # 40 hex, does not resolve in this repo
    RD._persist_head_content_blobs(
        str(session_dir),
        {"config": {"headSha": bad_head}},
        head_sha=bad_head,
        paths=["c.txt"],
    )
    blobs = _load_blobs(session_dir)
    row = _read_row(blobs, "c.txt")
    assert isinstance(row["readError"], str) and row["readError"]
    assert row["contentDigest"] is None
    assert row["bytes"] is None
    assert "c.txt" not in blobs.get("files", {})
