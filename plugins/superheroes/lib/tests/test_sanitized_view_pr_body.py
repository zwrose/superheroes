"""Tests for PR-body staging in sanitized_view (#609 stage 2)."""
import os
import stat
import sys

import pytest

_LIB = os.path.join(os.path.dirname(__file__), "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import sanitized_view as sv


@pytest.fixture(autouse=True)
def _pin_temp_base_to_tmp_path(tmp_path, monkeypatch):
    base = str(tmp_path / "sanitized-temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(sv.tempfile, "gettempdir", lambda: base)
    yield


def _session(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    return str(session)


def _pr_body(session_dir, content=b"PR body text\n"):
    path = os.path.join(session_dir, "pr-body.md")
    with open(path, "wb") as fh:
        fh.write(content)
    return path


def _view_root(tmp_path):
    root = tmp_path / "view"
    root.mkdir()
    return str(root)


def test_stage_pr_body_happy_path(tmp_path):
    session = _session(tmp_path)
    body_path = _pr_body(session)
    view = _view_root(tmp_path)
    info = sv._stage_pr_body(view, body_path, session)
    assert info == {"prBodyPath": sv.PR_BODY_FILE_NAME, "prBodyBytes": len(b"PR body text\n")}
    staged = os.path.join(view, sv.PR_BODY_FILE_NAME)
    assert os.path.isfile(staged)
    with open(staged, "rb") as fh:
        assert fh.read() == b"PR body text\n"


def test_stage_pr_body_missing_path(tmp_path):
    session = _session(tmp_path)
    view = _view_root(tmp_path)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv._stage_pr_body(view, os.path.join(session, "nope.md"), session)
    assert exc.value.detail == "sanitized-view-pr-body-missing"


def test_stage_pr_body_not_regular_file(tmp_path):
    session = _session(tmp_path)
    view = _view_root(tmp_path)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv._stage_pr_body(view, session, session)
    assert exc.value.detail == "sanitized-view-pr-body-missing"


def test_stage_pr_body_session_unresolvable(tmp_path):
    session = _session(tmp_path)
    body_path = _pr_body(session)
    view = _view_root(tmp_path)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv._stage_pr_body(view, body_path, os.path.join(session, "missing", "dir"))
    assert exc.value.detail == "sanitized-view-pr-body-outside-session"


def test_stage_pr_body_outside_session(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    body_path = _pr_body(str(outside))
    session = _session(tmp_path)
    view = _view_root(tmp_path)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv._stage_pr_body(view, body_path, session)
    assert exc.value.detail == "sanitized-view-pr-body-outside-session"


def test_stage_pr_body_name_collision(tmp_path):
    session = _session(tmp_path)
    body_path = _pr_body(session)
    view = _view_root(tmp_path)
    with open(os.path.join(view, sv.PR_BODY_FILE_NAME), "w", encoding="utf-8") as fh:
        fh.write("existing\n")
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv._stage_pr_body(view, body_path, session)
    assert exc.value.detail == "sanitized-view-pr-body-name-collision"


def test_stage_pr_body_unreadable(tmp_path):
    session = _session(tmp_path)
    body_path = _pr_body(session)
    os.chmod(body_path, 0)
    view = _view_root(tmp_path)
    try:
        with pytest.raises(sv.SanitizedViewError) as exc:
            sv._stage_pr_body(view, body_path, session)
        assert exc.value.detail == "sanitized-view-pr-body-unreadable"
    finally:
        os.chmod(body_path, stat.S_IRUSR | stat.S_IWUSR)


def test_stage_pr_body_empty(tmp_path):
    session = _session(tmp_path)
    body_path = _pr_body(session, content=b"")
    view = _view_root(tmp_path)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv._stage_pr_body(view, body_path, session)
    assert exc.value.detail == "sanitized-view-pr-body-empty"


def test_stage_pr_body_too_large(tmp_path):
    session = _session(tmp_path)
    body_path = _pr_body(session, content=b"x" * (sv.PR_BODY_MAX_BYTES + 1))
    view = _view_root(tmp_path)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv._stage_pr_body(view, body_path, session)
    assert exc.value.detail == "sanitized-view-pr-body-too-large"


def test_stage_pr_body_unwritable(tmp_path, monkeypatch):
    session = _session(tmp_path)
    body_path = _pr_body(session)
    view = _view_root(tmp_path)

    real_open = os.open

    def failing_open(path, flags, *args, **kwargs):
        if os.path.basename(path) == sv.PR_BODY_FILE_NAME:
            raise OSError("simulated unwritable")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", failing_open)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv._stage_pr_body(view, body_path, session)
    assert exc.value.detail == "sanitized-view-pr-body-unwritable"


def test_stage_pr_body_readback_mismatch(tmp_path, monkeypatch):
    session = _session(tmp_path)
    body_path = _pr_body(session)
    view = _view_root(tmp_path)
    dest_path = os.path.join(view, sv.PR_BODY_FILE_NAME)
    real_open = open

    def patched_open(path, *args, **kwargs):
        if path == dest_path and args and args[0] == "rb":
            class _Fake:
                def read(self, *_a, **_k):
                    return b"tampered"
                def __enter__(self):
                    return self
                def __exit__(self, *_a):
                    return False
            return _Fake()
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", patched_open)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv._stage_pr_body(view, body_path, session)
    assert exc.value.detail == "sanitized-view-pr-body-readback-mismatch"


def _init_min_repo(path):
    import subprocess
    path = str(path)
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "-C", path, "init", "-q"], check=True)
    with open(os.path.join(path, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("hello\n")
    subprocess.run(["git", "-C", path, "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "i"],
        check=True,
    )
    return path


def test_build_sanitized_view_pr_body_neither(tmp_path):
    repo = _init_min_repo(tmp_path / "repo")
    view = sv.build_sanitized_view(repo)
    assert view["prBodyPath"] is None
    assert view["prBodyBytes"] is None
    sv.destroy_sanitized_view(view["path"])


def test_build_sanitized_view_pr_body_unpaired_pr_only(tmp_path):
    repo = _init_min_repo(tmp_path / "repo")
    session = _session(tmp_path)
    body = _pr_body(session)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo, pr_body_path=body)
    assert exc.value.detail == "sanitized-view-pr-body-args-unpaired"


def test_build_sanitized_view_pr_body_unpaired_session_only(tmp_path):
    repo = _init_min_repo(tmp_path / "repo")
    session = _session(tmp_path)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo, session_dir=session)
    assert exc.value.detail == "sanitized-view-pr-body-args-unpaired"


def test_build_sanitized_view_pr_body_both(tmp_path):
    repo = _init_min_repo(tmp_path / "repo")
    session = _session(tmp_path)
    body = _pr_body(session, content=b"staged body\n")
    view = sv.build_sanitized_view(repo, pr_body_path=body, session_dir=session)
    assert view["prBodyPath"] == sv.PR_BODY_FILE_NAME
    assert view["prBodyBytes"] == len(b"staged body\n")
    staged = os.path.join(view["path"], sv.PR_BODY_FILE_NAME)
    assert os.path.isfile(staged)
    sv.destroy_sanitized_view(view["path"])
